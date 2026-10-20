"""Bounded current-version qualification; wrappers only observe production calls."""
from pathlib import Path
import os,sys,json,hashlib,time,gzip,traceback,resource,csv
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1/source'); S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/adaptive_human_online_interface_v1'; OUT=S/'results/adaptive_human_online_interface_v1/human'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage4.estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(rt._jsonable(x),indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
consumers={}
def consume(kind,model,sequence):
    row=consumers.setdefault(kind,{'calls':0,'versions':{},'first':None,'last':None})
    beta=model.beta.tolist(); key=hashlib.sha256(np.asarray(model.beta,dtype='<f8').tobytes()+np.asarray(model.residual_weights_nm,dtype='<f8').tobytes()).hexdigest()
    payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key)
    row['calls']+=1; row['versions'][str(sequence)]=key
    if row['first'] is None:row['first']=payload
    row['last']=payload
orig_command=HumanWaypointMPCShadowContractV1.command
def command(self,*a,**kw):
    obs=kw.get('observation'); consume('execution',self.human_model,None if obs is None else obs.human_model_version)
    return orig_command(self,*a,**kw)
HumanWaypointMPCShadowContractV1.command=command
orig_decide=AdaptiveHumanWaypointHWMPCV22.decide
def decide(self,*a,**kw):
    b=kw['belief']; consume('planner',b.human_model(),b.sequence)
    return orig_decide(self,*a,**kw)
AdaptiveHumanWaypointHWMPCV22.decide=decide
orig_screen=AdaptiveMechanicsScreenV22.evaluate
def screen(self,belief,candidate,schedule):
    consume('mechanics',belief.human_model(),belief.sequence)
    return orig_screen(self,belief,candidate,schedule)
AdaptiveMechanicsScreenV22.evaluate=screen
def main():
    contract=json.loads((D/'EXPERIMENT_CONTRACT.json').read_text())
    assert sha(R/contract['options_path'])==contract['options_sha256']
    options=json.loads((R/contract['options_path']).read_text())
    all_rows=[]
    selected=sys.argv[1:] or [c['id'] for c in contract['cases']]
    for c in contract['cases']:
        if c['id'] not in selected:continue
        assert sha(R/c['path'])==c['sha256']
        # All arms share exact truth and commissioning trajectory; execution options untouched.
        for arm in ('continual_adaptive','commissioning_only','fixed_population'):
            out=OUT/f"{c['id']}__{arm}"
            if (out/'qualification.json').exists() and json.loads((out/'qualification.json').read_text())['completion'] != 'EXCEPTION':continue
            if out.exists():out=OUT/f"{c['id']}__{arm}__attempt02"
            out.mkdir(parents=True,exist_ok=False); consumers.clear(); capture={}; context={}
            start=time.monotonic(); print('START',c['id'],arm,flush=True)
            row=dict(condition=c['id'],arm=arm,evidence_category='current_version_development_qualification',case_path=c['path'],case_sha256=c['sha256'],human_truth=c['case']['physical'],task=c['case']['task'],parameter_names=list(DYNAMIC_BASE_PARAMETER_NAMES),command=sys.argv)
            try:
                summary=rt.run_executed_case(out,qualification_case=c['case'],qualification_arm=arm,
                    simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,
                    dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,
                    autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=capture,
                    execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context=context)
                z=np.load(out/'trace.npz'); mask=z['stage']=='TASK'; t=z['time_s'][mask]; dt=np.diff(t)
                f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1); m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
                estimated=z['estimated_human_state_rad_rad_s'][mask]; truth=z['evaluation_only_human_state_rad_rad_s'][mask]
                qref=z['reference_q_rad'][mask]; rv=z['reference_dq_rad_s'][mask]
                u=context['updater']; adaptation=summary.get('adaptation_trace',capture.get('runtime',{}).get('adaptation_trace',[]))
                artifact=json.loads((out/'runtime_artifacts.json').read_text())
                adaptation=artifact.get('adaptation_trace',adaptation)
                beta=z['task_beta']; residual=z['task_residual_weights_nm']; versions=z['controller_model_version'][mask]
                pred=[x['diagnostics'].get('residual_sample_nm') for x in adaptation if x.get('diagnostics',{}).get('residual_sample_nm') is not None]
                row.update(completion=summary['status'],abort_reason=summary.get('abort_reason'),duration_s=float(t[-1]-t[0]) if len(t)>1 else 0.,
                    J_F_task_n_s=float(f[:-1]@dt),force_mean_n=float(np.mean(f)) if len(f) else None,force_rms_n=float(np.sqrt(np.mean(f*f))) if len(f) else None,force_peak_n=float(np.max(f)) if len(f) else None,
                    moment_integral_nm_s=float(m[:-1]@dt),moment_peak_nm=float(np.max(m)) if len(m) else None,
                    tracking_rmse_rad=np.sqrt(np.mean((estimated[:,:2]-qref)**2,axis=0)) if len(t) else None,
                    tracking_truth_rmse_rad_evaluation_only=np.sqrt(np.mean((truth[:,:2]-qref)**2,axis=0)) if len(t) else None,
                    minimum_clearance_m=summary['task'].get('minimum_session_clearance_m_deployable'),minimum_true_clearance_m_evaluation_only=summary['task'].get('minimum_true_physical_clearance_m_evaluation_only'),
                    initial_beta=summary['commissioning']['handoff_belief']['beta'],final_beta=u.dynamics.beta,
                    first_task_beta=beta[0] if len(beta) else None,final_task_beta=beta[-1] if len(beta) else None,
                    accepted_dynamic_updates_total=u.dynamics.accepted_updates,dynamic_identifier_record=u.dynamics.record(),
                    continual_update_attempts=summary['task']['continual_adaptation_update_count'],
                    residual_update_count=u.residual_update_count,residual_model_changed=bool(len(residual) and np.any(residual[-1]!=residual[0])),
                    prediction_residual_rms_nm=np.sqrt(np.mean(np.asarray(pred)**2,axis=0)) if pred else None,
                    geometry_estimate=summary['commissioning']['geometry_fit'],geometry_used=summary['commissioning']['handoff_belief']['effective_geometry'],
                    controller_model_versions=sorted(set(versions.tolist())),consumers=dict(consumers),no_nan_task=bool(all(np.all(np.isfinite(z[k][mask])) for k in ('estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','physical_cuff_force_world_n','physical_cuff_moment_world_nm','cr12_q_rad'))),
                    boundary_continuity=summary['timing']['all_reference_boundaries_q_dq_ddq_continuous'],
                    runtime_adaptation_trace_count=len(adaptation))
                # Keep representative and failure traces; other raw artifacts compressed, not rewritten history.
                for name in ('runtime_artifacts.json','summary.json','learning_transitions.jsonl'):
                    p=out/name
                    with gzip.open(str(p)+'.gz','wb',compresslevel=3) as dest:dest.write(p.read_bytes())
                    p.unlink()
            except Exception as e:
                row.update(completion='EXCEPTION',exception=f'{type(e).__name__}:{e}',traceback=traceback.format_exc(),consumers=dict(consumers))
                (out/'exception.txt').write_text(traceback.format_exc())
            row.update(elapsed_host_s=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            save(out/'qualification.json',row); all_rows.append(row)
            print('DONE',c['id'],arm,row['completion'],row.get('abort_reason'),round(row['elapsed_host_s'],2),flush=True)
            state=json.loads((D/'STATE.json').read_text()); state.update(phase='HUMAN_QUALIFICATION',last_completed=f"{c['id']}__{arm}",next_action='Continue frozen three-arm case matrix');save(D/'STATE.json',state)
            capture.clear();context.clear();import gc;gc.collect()
    save(D/'CURRENT_HUMAN_ADAPTATION_VALIDATION.json',{'status':'MEASUREMENTS_PENDING_CLASSIFICATION','runs':[json.loads(p.read_text()) for p in sorted(OUT.glob('*/qualification.json'))]})
if __name__=='__main__':main()
