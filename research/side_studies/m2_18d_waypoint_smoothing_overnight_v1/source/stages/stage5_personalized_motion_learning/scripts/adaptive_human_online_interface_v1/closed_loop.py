from pathlib import Path
import sys,json,time,gzip,traceback,resource
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_online_v1 as rt
from traction_mpc_stage5.task import TaskPhase
def save(p,x):p.write_text(json.dumps(rt._jsonable(x),indent=2,allow_nan=False)+'\n')
def deterministic(phase,t,target,owned,**causal):
    # Finite changes in target intention; restore registered terminal target.
    if phase is TaskPhase.OUTBOUND and .5<=t<.7:return target+np.array([-.04,-.01])
    if phase is TaskPhase.OUTBOUND and .7<=t<.9:return target+np.array([-.01,-.04])
    return target
def local_switch(phase,t,target,owned,**causal):
    if phase is TaskPhase.OUTBOUND and .5<=t<.7:return owned.q_rad+np.array([.03,.005])
    if phase is TaskPhase.OUTBOUND and .7<=t<.9:return owned.q_rad+np.array([.005,.03])
    return target
def main():
    period=float(sys.argv[1]) if len(sys.argv)>1 else .05;pattern=sys.argv[2] if len(sys.argv)>2 else 'constant'
    suffix=sys.argv[3] if len(sys.argv)>3 else ''
    out=S/'results/adaptive_human_online_interface_v1/online'/f'nominal_{int(period*1000)}ms_{pattern}{suffix}'
    out.mkdir(parents=True,exist_ok=False);capture={};context={};start=time.monotonic()
    case=json.loads((S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text())
    contract=json.loads((D/'EXPERIMENT_CONTRACT.json').read_text());options=json.loads((R/contract['options_path']).read_text())
    row=dict(period_s=period,pattern=pattern,status='RUNNING',command=sys.argv,evidence_category='scientific_simulation_research_interface_qualification',truth=case['physical'],physical_source='unchanged CR12 torque + cuff interaction + Human V2 MuJoCo',old_baseline='human/high_rom_nominal_sync_120_v1__continual_adaptive__attempt02')
    try:
        callback=local_switch if pattern=='local_switch' else deterministic if pattern=='switch' else None
        summary=rt.run_executed_case(out,qualification_case=case,qualification_arm='continual_adaptive',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context=context,online_command_period_s=period,online_target_callback=callback)
        z=np.load(out/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];dt=np.diff(t);f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
        records=summary['online_reference_records'];accepted=[x for x in records if x.get('status')=='ACCEPTED']
        row.update(status=summary['status'],abort_reason=summary.get('abort_reason'),J_F_task_n_s=float(f[:-1]@dt),force_mean_n=float(np.mean(f)) if len(f) else None,force_rms_n=float(np.sqrt(np.mean(f*f))) if len(f) else None,force_peak_n=float(np.max(f)) if len(f) else None,moment_integral_nm_s=float(m[:-1]@dt),moment_peak_nm=float(np.max(m)) if len(m) else None,duration_s=float(t[-1]-t[0]) if len(t)>1 else 0.,minimum_clearance_m=summary['task'].get('minimum_session_clearance_m_deployable'),minimum_true_clearance_m_evaluation_only=summary['task'].get('minimum_true_physical_clearance_m_evaluation_only'),task=summary['task'],tracking_rmse_rad=np.sqrt(np.mean((z['estimated_human_state_rad_rad_s'][mask,:2]-z['reference_q_rad'][mask])**2,axis=0)) if len(t) else None,online_records=records,accepted_updates=len(accepted),no_nan=bool(all(np.all(np.isfinite(z[k][mask])) for k in ('reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n','cr12_q_rad'))),all_accepted_C2=all(x['activation_validation']['C2'] for x in accepted),robot_tracking_peak_m=max((np.linalg.norm(x['desired_cuff_position_world_m']-x['cuff_position_world_m']) for x in capture['runtime'].get('trace',[]) if 'desired_cuff_position_world_m' in x),default=None))
        for name in ('runtime_artifacts.json','summary.json','learning_transitions.jsonl'):
            p=out/name
            with gzip.open(str(p)+'.gz','wb',compresslevel=3) as f:f.write(p.read_bytes())
            p.unlink()
    except Exception as e:row.update(status='EXCEPTION',exception=str(e),traceback=traceback.format_exc());(out/'exception.txt').write_text(traceback.format_exc())
    row.update(elapsed_host_s=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(out/'result.json',row);save(D/'CR12_ONLINE_INTERFACE_CLOSED_LOOP.json',{'runs':[json.loads(p.read_text()) for p in sorted((out.parent).glob('*/result.json'))]})
    print(json.dumps({k:row.get(k) for k in ('status','abort_reason','exception','duration_s','J_F_task_n_s','accepted_updates','elapsed_host_s')}),flush=True)
if __name__=='__main__':main()
