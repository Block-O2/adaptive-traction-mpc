"""I-A only. No plant or synthetic receipt. Preserve every subcheck even on limited clearance."""
from pathlib import Path
import json
import math
import os
import sys
from dataclasses import asdict

import numpy as np

HERE=Path(__file__).resolve().parent
V1=HERE.parent/"ihear_lab_stage1_fgdw_v1"
sys.path.insert(0,str(V1))
import probe_v2 as old
from reference import Segment,Origin,Stop,Window,GRID,H,RAMP,F,I,pair,time_value,sample
from certification import normal_motion,stop_motion,continuous_geometry,mechanics
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1
from traction_mpc_stage5.loaded_execution import with_explicit_robot_target
from traction_mpc_stage5.full3d_adaptive_integration_v1.startup_alignment import tool_increment_certificate
from traction_mpc_stage5.hold_stabilizer import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.architecture_recovery_v2.effective_model import fit_effective_geometry
from interval_certificate import BED_HEIGHT_M, THIGH_RADIUS_M
from native_integration import model_key
import inspect, ast

def read(path):return json.loads(path.read_text())

class StaticHold:
    duration=GRID
    duration_s=float(GRID)
    def __init__(self,stop):
        self.endpoint=stop.jet(stop.duration)
        assert all(v==I(0) for row in self.endpoint[1:] for v in row)
    def jet(self,t):
        if not 0<=time_value(t)<=GRID:raise ValueError("outside static hold")
        return self.endpoint
    def sample(self,t):return sample(self.jet(t))

def vec(x):return np.concatenate([x.q_rad,x.dq_rad_s,x.ddq_rad_s2])

def search_domain():
    # Use the existing fit's own numerical search limits only as a domain diagnostic.
    tree=ast.parse(inspect.getsource(fit_effective_geometry))
    ends={}
    for stmt in ast.walk(tree):
        if isinstance(stmt,ast.Assign) and len(stmt.targets)==1 and isinstance(stmt.targets[0],ast.Name):
            key=stmt.targets[0].id
            if key in ("lower","upper"):ends[key]=ast.literal_eval(stmt.value.args[0])
    return list(zip(ends["lower"][1:],ends["upper"][1:]))

def run():
    archived=read(V1/'probe_result.json')
    reproduction=old.main()    # no historical writes, old failure is expected here only
    keys=['original_q','xhat','F','G','E','selected','r','omega','end_q','end_dq','end_ddq']
    eq={k:bool(np.array_equal(reproduction[k],archived[k])) for k in keys}
    assert all(eq.values()) and reproduction['base_positive']['feasible']
    assert not reproduction['native_admission']['returned'] and 'coefficients' in reproduction['native_admission']['message']
    b,spec,sch,_=old.native_context()
    raw=read(old.RT2/'B/native/runtime_artifacts.json')
    summary=read(old.RT2/'B/native/summary.json')
    stamp=reproduction['source_time_s']
    d=next(x for x in raw['trace'] if x.get('stage')=='TASK' and x['time_s']==stamp)
    e=next(x for x in raw['wall_physics']['causal_sensor_estimates'] if x['sample_time_s']==stamp)
    captures=[x['source_capture_ns'] for x in raw['wall_physics']['command_receipts'] if x.get('source_sample_time_s')==stamp]
    assert len(set(captures))<=1
    geom=b.human_model().geometry
    clear=sch.clearance_evaluator
    goal=np.asarray(spec.outbound_goal_target_rad); q=reproduction['original_q']
    V=reproduction['limits_v']; A=reproduction['limits_a']
    import hashlib
    origin=Origin('OUTBOUND',pair(q),(1,1),'offline-strict-rest',hashlib.sha256(repr(model_key(b,clear)).encode()).hexdigest(),old.clearance_geometry_signature(clear),stamp,captures[0] if captures else None)
    seg=Segment(origin,pair(reproduction['r']),reproduction['omega'])
    x=np.asarray(e['estimated_state']); obs_a=np.asarray(e['human_motion_acceleration_rad_s2'])
    offset=x[:2]-q
    rom=np.column_stack([np.maximum(np.asarray(spec.q_bounds_rad)[:,0],b.human_model().q_min_rad),np.minimum(np.asarray(spec.q_bounds_rad)[:,1],b.human_model().q_max_rad)])
    floor=max(0.,float(np.min(clear.evaluate(np.vstack([spec.start_return_target_rad,goal])))))
    end=seg.sample(H)
    compare=np.abs(vec(end)-np.r_[archived['end_q'],archived['end_dq'],archived['end_ddq']])
    assert max(compare)<=1e-10 and not hasattr(seg,'coefficients')
    assert normal_motion(seg,V,A,goal)
    angle_domain=search_domain()
    physical_domain=angle_domain.copy()
    physical_domain[0]=(BED_HEIGHT_M+THIGH_RADIUS_M+clear.envelope.registered_proximal_installation_gap_lower_m,angle_domain[0][1])
    physical_domain[2]=(angle_domain[2][0],min(angle_domain[2][1],clear.shank_contract.shank_length_upper_m))
    # This tightened family is a diagnostic only: anatomical hip gap is not a fitted hip error bound.
    def check(path):
        final=path.sample(path.duration)
        cand=old.runtime._candidate('fgdw_interface_fixture',old.TaskPhase.OUTBOUND,final.q_rad,final.dq_rad_s,spec)
        return dict(mechanics=mechanics(b,cand,path),
                    nominal=continuous_geometry(path,clear.envelope,(0.,0.),floor,rom),
                    shifted=continuous_geometry(path,clear.envelope,offset,0.,rom),
                    search_box_nominal=continuous_geometry(path,clear.envelope,(0.,0.),floor,rom,angle_domain),
                    search_box_shifted=continuous_geometry(path,clear.envelope,offset,0.,rom,angle_domain),
                    installation_diagnostic=continuous_geometry(path,clear.envelope,offset,0.,rom,physical_domain))
    normal=check(seg)
    phase_elapsed=d['task_elapsed_s']  # sample is exactly the TASK and OUTBOUND origin
    assert phase_elapsed==0 and e['human_motion_valid'] and str(e['model_version'])==str(b.sequence)
    age_independent_current=dict(offset=offset,observed_ddq=obs_a,acceleration_valid=e['human_motion_valid'],
        rom=bool(np.all(x[:2]>=rom[:,0]) and np.all(x[:2]<=rom[:,1])),clearance_m=float(clear.evaluate(x[:2])),
        velocity_valid=bool(np.all(V+abs(x[2:])<=spec.task_joint_velocity_limit_rad_s)),
        acceleration_valid_with_error=bool(np.all(A+abs(obs_a)<=spec.task_joint_acceleration_limit_rad_s2)))
    stops=[]
    for k in range(9):
        t=k*GRID; st=Stop(seg,t,A)
        motion=stop_motion(st,V,A,goal)
        if not motion:raise RuntimeError('unproved monotonic range: no endpoint-box use')
        first_jump=max(abs(vec(seg.sample(t))-vec(st.sample(0))))
        assert first_jump<=1e-10
        v0=seg.sample(t).dq_rad_s
        a0=seg.sample(t).ddq_rad_s2
        ub=v0+a0*float(RAMP)/2
        dist=v0*float(RAMP)+a0*float(RAMP)**2/3+float(GRID)*ub+ub*float(st.brake)/2
        end_err=st.sample(st.duration).q_rad-st.sample(0).q_rad-dist
        spans={'hold':StaticHold(st)}
        if not st.stationary:
            spans.update(bridge=Window(st,F(0),H),brake=Window(st,H,st.brake))
        checks=check(st)
        pieces={name:check(span) for name,span in spans.items()}
        reserve=float(t+st.duration+GRID)
        stops.append(dict(node_ms=5*k,duration_s=st.duration_s,brake_s=float(st.brake),ub=ub,distance=dist,
            distance_error=end_err,motion=motion,first_jump=first_jump,terminal_jet=vec(st.sample(st.duration)),
            reserve_s=reserve,phase_ok=reserve<=spec.phase_timeout_s-phase_elapsed,task_ok=reserve<=30.-d['task_elapsed_s'],
            whole=checks,pieces=pieces))
    contract=HumanWaypointMPCShadowContractV1(spec,b.human_model(),default_engineering_cuff_allocator())
    n=geom.joint_axis_world; plane=[]
    prev=None
    for k in range(9):
        ref=seg.sample(k*GRID)
        candidate=old.runtime._candidate('fgdw_plane',old.TaskPhase.OUTBOUND,ref.q_rad,ref.dq_rad_s,spec)
        mapping=contract.prepare(candidate);loaded=mapping.execution_target
        command=with_explicit_robot_target(loaded,mapping.reference)
        hr,cr=loaded.human_cuff_target,loaded.robot_cuff_target
        site=command.robot_cuff_target
        tcp=site.world_from_cuff.compose(STAGE5_GEOMETRY.end_effector_from_cuff.inverse())
        p=site.world_from_cuff.translation
        lever=tcp.translation-p
        check_tool=tool_increment_certificate(site.world_from_cuff if prev is None else prev,site.world_from_cuff)
        prev=site.world_from_cuff
        plane.append(dict(ms=5*k,human=hr.world_from_cuff.translation,cuff=p,tcp=tcp.translation,
             human_n=float(n@hr.world_from_cuff.translation),cuff_n=float(n@p),tcp_n=float(n@tcp.translation),
             human_vn=float(n@hr.linear_velocity_world_m_s),cuff_loaded_vn=float(n@cr.linear_velocity_world_m_s),
             tcp_loaded_vn=float(n@(cr.linear_velocity_world_m_s+np.cross(cr.angular_velocity_world_rad_s,lever))),
             cuff_command_vn=float(n@site.linear_velocity_world_m_s),
             tcp_command_vn=float(n@(site.linear_velocity_world_m_s+np.cross(site.angular_velocity_world_rad_s,lever))),
             allocated_wrench=mapping.equilibrium.physical_human_wrench_world,
             loaded_offset=p-hr.world_from_cuff.translation,tool=check_tool))
    return dict(reproduction=eq,original_block=reproduction['native_admission'],base_positive=reproduction['base_positive'],
        metadata=asdict(origin),identity=seg.identity,limits_v=V,limits_a=A,omega=seg.omega,r=seg.target,
        nominal_distance_at_end=[float(((u+z)/I(seg.omega)).mid) for u,z in zip(*seg.state(H)[1:])],
        sample_diff=compare,q0=q,end=vec(end),coefficients_present=hasattr(seg,'coefficients'),
        registered_contract=summary['session_clearance_contract'],fit=summary['commissioning']['geometry_fit'],
        diagnostic_search_box=angle_domain,installation_diagnostic_box=physical_domain,
        threshold_nominal=floor,rom=rom,current=age_independent_current,normal=normal,stops=stops,plane=plane,
        plane_n=n,plane_origin=geom.origin_world_m,alignment_removed=raw['startup_alignment']['removal'],
        allocator=type(contract.cuff_allocator).__name__,stiffness=CONTROLLER_NOMINAL_INTERFACE.translation_stiffness_n_m,
        native_receipts=0,write_attempts=0,physics_steps=0,source_capture_matches=captures,
        calibration_error_set_in_handoff=sorted(summary['commissioning']['geometry_fit'].keys()))

if __name__=='__main__':
    result=run()
    with (HERE/'ia.json').open('x') as stream:
        json.dump(result,stream,indent=1,default=lambda a:a.tolist() if isinstance(a,np.ndarray) else a.item(),allow_nan=False)
    print('I-A data saved',result['identity'])
