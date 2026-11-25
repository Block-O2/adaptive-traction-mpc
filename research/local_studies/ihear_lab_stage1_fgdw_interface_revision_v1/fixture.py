"""Frozen RT2 inputs, shared only as read-only offline evidence."""
from pathlib import Path
import hashlib
import json
import sys
from types import SimpleNamespace
import numpy as np

HERE=Path(__file__).resolve().parent
PREV=HERE.parent/'ihear_lab_stage1_fgdw_interface_v1'
sys.path.insert(0,str(PREV))
import run_ia as ia
from run_ia import old
from reference import F,GRID,H,RAMP,Origin,Segment,Stop,Window,pair
from certification import normal_motion,stop_motion,continuous_geometry,mechanics
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

def read(p):
    return json.loads(p.read_text())

def serialize(x):
    def convert(v):
        if isinstance(v,np.ndarray):return v.tolist()
        if isinstance(v,np.generic):return v.item()
        raise TypeError(type(v).__name__)
    return json.dumps(x,sort_keys=True,default=convert,allow_nan=False,separators=(',',':'))

def seal(name,value):
    with (HERE/name).open('x') as stream:stream.write(serialize(value)+'\n')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fixture():
    prev=read(PREV/'ia.json')
    b,spec,sch,_=old.native_context()
    raw=read(old.RT2/'B/native/runtime_artifacts.json')
    summary=read(old.RT2/'B/native/summary.json')
    row=next(x for x in raw['trace'] if x.get('stage')=='TASK')
    stamp=row['time_s']
    causal=next(z for z in raw['wall_physics']['causal_sensor_estimates'] if z['sample_time_s']==stamp)
    caps={z['source_capture_ns'] for z in raw['wall_physics']['command_receipts'] if z.get('source_sample_time_s')==stamp}
    assert len(caps)==1 and causal['motion_source_sample_s']==stamp and str(causal['model_version'])==str(b.sequence)
    assert stamp>raw['startup_alignment']['removal']['actual_physics_time_s']
    q=np.asarray(row['q_ref_rad']);x=np.asarray(causal['estimated_state'])
    assert np.array_equal(x,row['estimated_state']) and row['task_elapsed_s']==0
    goal=np.asarray(spec.outbound_goal_target_rad)
    clear=sch.clearance_evaluator;model=b.human_model()
    V=np.asarray(spec.task_joint_velocity_limit_rad_s)*sch.reference_velocity_fraction
    A=np.asarray(spec.task_joint_acceleration_limit_rad_s2)*sch.reference_acceleration_fraction
    rom=np.column_stack([np.maximum(np.asarray(spec.q_bounds_rad)[:,0],model.q_min_rad),np.minimum(np.asarray(spec.q_bounds_rad)[:,1],model.q_max_rad)])
    assert clear.shank_contract.geometry is clear.envelope.geometry
    assert clear.shank_contract.shank_length_upper_m==clear.envelope.shank_length_upper_m
    assert clear.shank_contract.margin_m==clear.envelope.existing_shank_margin_m
    assert sch.require_continuous_nonpenetrating_path and sch.preserve_task_endpoint_clearance_floor
    task_contract=ia.HumanWaypointMPCShadowContractV1(spec,model,ia.default_engineering_cuff_allocator())
    return SimpleNamespace(b=b,spec=spec,sch=sch,clear=clear,q=q,x=x,F=np.asarray(row['cuff_force_world_n']),goal=goal,
        stamp=stamp,capture=caps.pop(),valid=causal['human_motion_valid'],obs_a=np.asarray(causal['human_motion_acceleration_rad_s2']),
        phase=old.TaskPhase.OUTBOUND,V=V,A=A,omega=prev['omega'],rom=rom,contract=task_contract,registered=summary['session_clearance_contract'],
        elapsed=row['task_elapsed_s'],phase_limit=spec.phase_timeout_s,task_limit=30.,model=model)

def current_state(c,first):
    x=c.x;error=x[:2]-first.q_rad
    limits_v=np.asarray(c.spec.task_joint_velocity_limit_rad_s)
    limits_a=np.asarray(c.spec.task_joint_acceleration_limit_rad_s2)
    ready=(c.valid and np.all(np.isfinite(np.r_[x,c.obs_a])) and np.all(x[:2]>=c.rom[:,0]) and np.all(x[:2]<=c.rom[:,1])
           and c.clear.evaluate(x[:2])>=0 and np.all(abs(x[2:])<=limits_v) and np.all(abs(c.obs_a)<=limits_a)
           and np.all(c.V+abs(x[2:]-first.dq_rad_s)<=limits_v) and np.all(c.A+abs(c.obs_a-first.ddq_rad_s2)<=limits_a))
    if not ready:raise ValueError('CURRENT_MODEL_STATE_REJECTED')
    return error

def mapped_target(c,ref):
    cand=old.runtime._candidate('fgdw_revision',c.phase,ref.q_rad,ref.dq_rad_s,c.spec)
    mapped=c.contract.prepare(cand)
    loaded=mapped.execution_target
    native=ia.with_explicit_robot_target(loaded,mapped.reference).robot_cuff_target
    tcp=native.world_from_cuff.compose(ia.STAGE5_GEOMETRY.end_effector_from_cuff.inverse())
    n=c.model.geometry.joint_axis_world
    lever=tcp.translation-native.world_from_cuff.translation
    human=loaded.human_cuff_target
    robot=loaded.robot_cuff_target
    normals=[n@human.world_from_cuff.translation,n@native.world_from_cuff.translation,n@tcp.translation,
        n@human.linear_velocity_world_m_s,n@robot.linear_velocity_world_m_s,
        n@(robot.linear_velocity_world_m_s+np.cross(robot.angular_velocity_world_rad_s,lever)),
        n@native.linear_velocity_world_m_s,n@(native.linear_velocity_world_m_s+np.cross(native.angular_velocity_world_rad_s,lever))]
    return native.world_from_cuff,dict(normals=normals,human=human.world_from_cuff.translation,cuff=native.world_from_cuff.translation,tcp=tcp.translation)

def joins(seg,st,node):
    # Independent one-sided analytic endpoint evaluations, in the OUTBOUND fixture coordinates.
    head=seg.sample(node)
    jumps=[np.max(abs(ia.vec(head)-ia.vec(st.sample(0))))]
    if not st.stationary:
        q,v,a=head.q_rad,head.dq_rad_s,head.ddq_rad_s2
        T=float(RAMP);ub=v+a*T/2
        qb=q+v*T+a*T*T/3
        brake_origin=qb+ub*float(GRID)
        final=brake_origin+ub*float(st.brake)/2
        for t,p,speed in [(RAMP,qb,ub),(H,brake_origin,ub),(st.duration,final,np.zeros(2))]:
            jumps.append(np.max(abs(np.r_[p,speed,[0.,0.]]-ia.vec(st.sample(t)))))
    if max(jumps)>1e-10:raise ValueError('C2_JUNCTION')
    return jumps
