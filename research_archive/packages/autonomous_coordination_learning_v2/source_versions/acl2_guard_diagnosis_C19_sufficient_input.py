"""Zero-native replay of an observed original clearance-guard impulse."""
from pathlib import Path
from types import SimpleNamespace
import os,sys,time,json,gzip
import numpy as np
from acl2_shared import P,R,put,read,sha,utc,decision
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.high_rom_v1 import deployable_prior
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.clearance_feedback import clearance_acceleration_correction

def main():
    start=time.time();ident='CORE_C_019';path=R/'source/results'/ident;rawpath=path/'runtime_artifacts.json.gz';tracepath=path/'trace.npz'
    with gzip.open(rawpath,'rt') as f:raw=json.load(f)
    events=[e for e in raw['execution_attempts'] if e.get('clearance_feedback')]
    event=min(events,key=lambda e:e['clearance_feedback']['model_curvature_m_s2']);c=event['clearance_feedback'];when=event['source_sample_time_s']
    belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json');g=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});model=sc.rt.StateResidualHumanModel(g,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']));env=RigidTableReferenceEnvelopeV1(g)
    with np.load(tracepath) as z:
        i=int(np.argmin(abs(z['time_s']-when)));state=z['estimated_human_state_rad_rad_s'][i];q,dq=state[:2],state[2:]
        interface=SimpleNamespace(human_position_world_m=z['physical_cuff_position_world_m'][i],human_rotation_world=z['physical_cuff_rotation_world'][i],human_velocity_world_m_s=z['physical_cuff_linear_velocity_world_m_s'][i],human_angular_velocity_world_rad_s=z['physical_cuff_angular_velocity_world_rad_s'][i])
        refq=z['reference_q_rad'][i];refv=z['reference_dq_rad_s'][i];refa=z['reference_ddq_rad_s2'][i]
    sample=min(raw['wall_physics']['causal_sensor_estimates'],key=lambda e:abs(e['sample_time_s']-when));state_error=float(np.max(abs(state-np.asarray(sample['estimated_state']))))
    def axis(q):
        phi=q[0]-q[1];return float(np.cos(phi)*g.plane_x_world[2]+np.sin(phi)*g.plane_z_world[2])
    sweep=[]
    for h in [1e-3,1e-4,3e-5,1e-5,3e-6,1e-6,3e-7,1e-7]:
        central=float((env.margins(q+h*dq)['sleeve_m'][0]-2*env.margins(q)['sleeve_m'][0]+env.margins(q-h*dq)['sleeve_m'][0])/(h*h));sweep.append(dict(time_stencil_s=h,curvature_m_s2=central,axis_z_minus=axis(q-h*dq),axis_z_at=axis(q),axis_z_plus=axis(q+h*dq),opposite_cylinder_endpoint_branches=bool(axis(q-h*dq)*axis(q+h*dq)<0)))
    correction,replay=clearance_acceleration_correction(model,state,np.asarray(c['requested_acceleration_rad_s2']),interface,np.asarray(c['joint_acceleration_box_rad_s2']),response_s=c['response_s'],adverse_acceleration_m_s2=c['adverse_acceleration_m_s2'])
    # The archived physical cuff pose and controller reconstructed Human point
    # differ; retain that mismatch instead of claiming identical measurement.
    # This function consumes pose/twist only through measured gap and gap rate.
    # Adapt those two sufficient scalars to the exact causal record, then call
    # the unchanged original function. This is an algebraic replay adapter,
    # not a reconstructed physical state or a new sensor/plant input.
    direct_errors=dict(gap_m=float(replay['gap_m']-c['gap_m']),gap_velocity_m_s=float(replay['gap_velocity_m_s']-c['gap_velocity_m_s']))
    position=np.array(interface.human_position_world_m,copy=True);velocity=np.array(interface.human_velocity_world_m_s,copy=True)
    position[2]+=c['gap_m']-replay['gap_m'];velocity[2]+=c['gap_velocity_m_s']-replay['gap_velocity_m_s']
    interface=SimpleNamespace(human_position_world_m=position,human_rotation_world=interface.human_rotation_world,human_velocity_world_m_s=velocity,human_angular_velocity_world_rad_s=interface.human_angular_velocity_world_rad_s)
    correction,replay=clearance_acceleration_correction(model,state,np.asarray(c['requested_acceleration_rad_s2']),interface,np.asarray(c['joint_acceleration_box_rad_s2']),response_s=c['response_s'],adverse_acceleration_m_s2=c['adverse_acceleration_m_s2'])
    guard_curvature_error=abs(next(s['curvature_m_s2'] for s in sweep if s['time_stencil_s']==1e-5)-c['model_curvature_m_s2']);correction_error=float(np.max(abs(correction-np.asarray(c['correction_nm']))));gap_error=abs(replay['gap_m']-c['gap_m']);required_error=abs(replay['required_gap_acceleration_m_s2']-c['required_gap_acceleration_m_s2'])
    with np.load(R/'motion_series'/(ident+'.npz')) as z:
        t=z['time_s'];acc=np.degrees(z['acceleration_rad_s2']);jerk=np.degrees(z['jerk_rad_s3']);peak=np.argmax(abs(jerk),axis=0);energy=jerk*jerk;top=np.argsort(energy.sum(1))[-20:];motion=dict(acceleration_max_deg_s2=np.max(abs(acc),axis=0),jerk_peak_deg_s3=[jerk[i,j] for j,i in enumerate(peak)],jerk_peak_times=[t[i] for i in peak],top20_native_jerk_squared_fraction=float(energy[top].sum()/energy.sum()),top20_native_time_range_s=[float(t[top].min()),float(t[top].max())])
    original_source=Path(sys.modules[clearance_acceleration_correction.__module__].__file__)
    result=dict(utc=utc(),status='ORIGINAL_GUARD_REPLAY_PASS' if max(guard_curvature_error,correction_error,gap_error,required_error,state_error)<1e-8 else 'REVIEW_REQUIRED',attempt_id=ident,input_adapter=dict(kind='Exact recorded causal sufficient gap/gap-rate scalars; not a reconstructed full physical interface',direct_physical_trace_geometry_mismatch=direct_errors,position_z_adjustment_m=-direct_errors['gap_m'],velocity_z_adjustment_m_s=-direct_errors['gap_velocity_m_s']),native_steps=0,causal_source_sample_s=when,causal_estimated_state=state,causal_sensor_state_max_error=state_error,reference_at_event=dict(q_rad=refq,dq_rad_s=refv,ddq_rad_s2=refa),archived_clearance_record=c,replayed_original_guard_record=replay,replay_errors=dict(curvature=guard_curvature_error,correction_Nm=correction_error,gap_m=gap_error,required_acceleration=required_error),stencil_sweep=sweep,native_motion=motion,original_source_sha256=sha(original_source),raw_input_sha256={str(f.relative_to(P)):sha(f) for f in [tracepath,rawpath]},hypothesis_supported='The original sleeve lower envelope switches cylinder endpoints at near-horizontal alignment. Its central finite-difference second derivative crosses that nonsmooth minimum and becomes extremely negative, driving an original clearance correction to acceleration-box corners; the receipt-owned torque impulse precedes the native jerk burst.',not_claimed='No safety guard disabled, no altered original scorer/physics, no proven future robust replacement. This replays an observed computation; timing/path causation and general failure frequency require separate bounded original-chain interventions.',wall_s=time.time()-start,source_sha256=sha(__file__))
    put('audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json',result)
    decision('A GP-screened motion failure may arise from an unmodelled low-level event, not an illegal reference','Replay original causal clearance guard and sweep only the diagnostic finite-difference stencil',{'status':result['status'],'time_s':when,'curvature':c['model_curvature_m_s2'],'correction_Nm':c['correction_nm'],'jerk_energy_top20_fraction':motion['top20_native_jerk_squared_fraction']},'Original guard impulse and geometric cusp are computationally traceable; no guard or threshold is changed in physical tests','Keep failure in training/accounting; use bounded timing interventions under the original full chain to test sensitivity',['audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json','attempts/CORE_C_019_RESULT.json'])
    print('ORIGINAL_GUARD_REPLAY',result['status'],result['replay_errors'],flush=True)

if __name__=='__main__':main()
