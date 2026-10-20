import os,sys
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
if os.getpriority(os.PRIO_PROCESS,0)<19:os.nice(19-os.getpriority(os.PRIO_PROCESS,0))
"""Bounded current-version qualification; wrappers only observe production calls."""
from pathlib import Path
import os,sys,json,hashlib,time,gzip,traceback,resource,csv
import numpy as np
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1'); R=W/'snapshot'; S=R/'stages/stage5_personalized_motion_learning'
D=W; OUT=W/'runs'
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
    payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key,geometry=rt._jsonable(dict(vars(model.geometry))))
    signature=json.dumps(payload['geometry'],sort_keys=True,separators=(',',':')).encode();payload['geometry_sha256']=hashlib.sha256(signature).hexdigest()
    emit_consumption(kind,payload)
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
    contract=json.loads((D/'CONTRACT.json').read_text()); contract['cases']=[dict(id=e['id'],path=e['case_path'],sha256=e['case_sha256'],case=e['case']) for e in contract['conditions']]
    assert sha(R/contract['options_path'])==contract['options_sha256']
    options=json.loads((R/contract['options_path']).read_text())
    all_rows=[]
    selected=sys.argv[1:] or [c['id'] for c in contract['cases']]
    for c in contract['cases']:
        if c['id'] not in selected:continue
        assert sha(R/c['path'])==c['sha256']
        # All arms share exact truth and commissioning trajectory; execution options untouched.
        for arm in (os.environ['LAB_STUDY_ARM'],):
            out=OUT/f"{c['id']}__{arm}"
            if (out/'qualification.json').exists() and json.loads((out/'qualification.json').read_text())['completion'] != 'EXCEPTION':continue
            if out.exists():out=OUT/f"{c['id']}__{arm}__attempt02"
            out.mkdir(parents=True,exist_ok=False); consumers.clear(); capture={'stop_check':resource_stop}; context={}
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
                # Temporary inherited raw artifacts; compact scorer/model evidence must be
                # extracted before the prospective retention review.
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
            state=json.loads((D/'STATE.json').read_text()); state.update(status='RUNNING',phase='PRIMARY_HUMAN_QUALIFICATION',last_completed=f"{c['id']}__{arm}",next_action='Continue frozen three-arm case matrix');save(D/'STATE.json',state)
            capture.clear();context.clear();import gc;gc.collect()
    save(D/'INHERITED_HARNESS_AGGREGATE.json',{'status':'MEASUREMENTS_PENDING_CLASSIFICATION','runs':[json.loads(p.read_text()) for p in sorted(OUT.glob('*/qualification.json'))]})


from datetime import datetime,timezone
from lab_resource_guard import verify_release,ResourceStop
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import StateResidualBeliefUpdaterV22
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
from traction_mpc_stage3.human import soft_limit_torque
resource_stop=None
def emit_consumption(kind,payload):
    target=os.environ.get('LAB_RUN_DIR')
    if not target:return
    # Independent process files make spawned planner observations explicit.
    with (Path(target)/f'model_consumption_{os.getpid()}.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(kind=kind,pid=os.getpid(),payload=payload),allow_nan=False)+'\n')
original_observe=StateResidualBeliefUpdaterV22.observe_dynamics
def observe_dynamics(self,**kwargs):
    # Pre-update prediction, with no truth or extra sensor inputs.
    model=self.snapshot().human_model();q=np.asarray(kwargs['q_rad']);dq=np.asarray(kwargs['dq_rad_s']);ddq=np.asarray(kwargs['ddq_rad_s2']);tau=np.asarray(kwargs['applied_generalized_torque_nm'])
    pred=model.inverse_dynamics(q,dq,ddq)
    record=dict(q=q.tolist(),dq=dq.tolist(),ddq=ddq.tolist(),measured_torque=tau.tolist(),pre_update_prediction=pred.tolist(),pre_update_error=(tau-pred).tolist(),sequence_before=self.sequence)
    result=original_observe(self,**kwargs)
    record.update(sequence_after=self.sequence,diagnostics=rt._jsonable(result))
    target=os.environ.get('LAB_RUN_DIR')
    if target:
        with (Path(target)/f'prediction_updates_{os.getpid()}.jsonl').open('a') as stream:stream.write(json.dumps(record,allow_nan=False)+'\n')
    return result
StateResidualBeliefUpdaterV22.observe_dynamics=observe_dynamics
commissioned_task_model=None
task_prediction_previous=None
def copy_causal_model(model):
    return StateResidualHumanModel(model.geometry,np.asarray(model.beta).copy(),model.rom_human,residual_weights_nm=np.asarray(model.residual_weights_nm).copy(),residual_limit_nm=model.residual_limit_nm)
original_measured_input=rt.measured_transmitted_human_input
def task_measured_input(observation,interface,model):
    global commissioned_task_model,task_prediction_previous
    tau=original_measured_input(observation,interface,model)
    if not os.environ.get('LAB_RUN_DIR'):return tau
    # This frozen-runtime function is called only from the TASK loop. It uses
    # the original controller reconstruction, not true physical Human state.
    if commissioned_task_model is None:
        commissioned_task_model=copy_causal_model(model)
        save(Path(os.environ['LAB_RUN_DIR'])/'COMMISSIONED_MODEL_TASK_CHECKPOINT.json',dict(beta=commissioned_task_model.beta,residual_weights_nm=commissioned_task_model.residual_weights_nm,geometry=dict(vars(model.geometry)),source='actual causal TASK-entry model, not hidden truth'))
    current=dict(time_s=float(observation.sample_timestamp_s),state=observation.as_array().copy(),tau=np.asarray(tau).copy(),model=copy_causal_model(model))
    prev=task_prediction_previous
    if prev is None:task_prediction_previous=current;return tau
    dt=current['time_s']-prev['time_s']
    if dt>=.020-1e-12:
        q=prev['state'][:2];dq=prev['state'][2:];ddq=(current['state'][2:]-dq)/dt
        frozen=commissioned_task_model.inverse_dynamics(q,dq,ddq)
        prequential=prev['model'].inverse_dynamics(q,dq,ddq)
        record=dict(stage='TASK',time_s=prev['time_s'],interval_s=dt,q=q.tolist(),dq=dq.tolist(),ddq=ddq.tolist(),causal_reconstructed_torque=prev['tau'].tolist(),commissioning_frozen_prediction=frozen.tolist(),commissioning_frozen_error=(prev['tau']-frozen).tolist(),prequential_prediction=prequential.tolist(),prequential_error=(prev['tau']-prequential).tolist(),soft_limit_active=bool(np.linalg.norm(soft_limit_torque(q,dq,model.rom_human))>1e-8),definition='TASK data not used by commissioning; retrospective finite-difference torque prediction, not a future-state forecast. Prequential model captured before that sample could update parameters. Torque is reconstructed with current effective geometry, not evaluation truth.')
        with (Path(os.environ['LAB_RUN_DIR'])/'TASK_PREDICTION_SAMPLES.jsonl').open('a') as stream:stream.write(json.dumps(record,allow_nan=False)+'\n')
        task_prediction_previous=current
    return tau
rt.measured_transmitted_human_input=task_measured_input
def validate_only():
    prov=json.loads((W/'SOURCE_PROVENANCE.json').read_text());assert all(sha(R/p)==r['sha256'] for p,r in prov['source_files'].items())
    contract=json.loads((W/'CONTRACT.json').read_text());assert contract['status']=='FROZEN_BEFORE_DYNAMIC' and len(contract['conditions'])==7
    assert sha(R/contract['options_path'])==contract['options_sha256']
    for e in contract['conditions']:assert sha(Path(e['case_path']))==e['case_sha256']
    modules={k:str(v.__file__) for k,v in sys.modules.items() if k.startswith('traction_mpc') and getattr(v,'__file__',None)};assert all(p.startswith(str(R)) for p in modules.values())
    sys.path.insert(0,str(S/'scripts/high_rom_v1'))
    import evaluate_execution_mode,summarize_phase_b
    from traction_mpc_stage5.controller_interface import _prefix_native
    save(W/'HARNESS_VALIDATION.json',dict(status='CHECK_ONLY_PASS_DYNAMIC_UNTESTED',source_hash_count=len(prov['source_files']),case_hash_count=7,project_imports=modules,scorer_path=summarize_phase_b.__file__,mode_evaluator_path=evaluate_execution_mode.__file__,native_prefix_backend='NumPy source fallback' if _prefix_native is None else _prefix_native.__file__,simulation_launched=False))
if __name__=='__main__':
    validate_only()
    if '--execute' not in sys.argv:
        print('CHECK_ONLY_PASS: no dynamics; resource release absent.');sys.exit(0)
    sys.argv.remove('--execute');assert len(sys.argv)==2 and sys.argv[1] in [f'C{i}' for i in range(7)]
    assert os.environ.get('LAB_STUDY_ARM') in ('fixed_population','commissioning_only','continual_adaptive')
    audit=json.loads((W/'FEASIBILITY_AUDIT.json').read_text());setup=next(e for e in audit['rows'] if e['id']==sys.argv[1]);assert setup['setup_status']=='NECESSARY_STATIC_PRECHECK_PASS'
    state=json.loads((W/'STATE.json').read_text());assert state['active_seconds']<8*3600 and state['primary_attempts']<21
    run=OUT/(sys.argv[1]+'__'+os.environ['LAB_STUDY_ARM']);assert not run.exists(),'repeated run needs separate prospective diagnostic/noise-repeat registration'
    resources=verify_release(sha(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py'))
    owner_fd=os.open(W/'OWNER.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(owner_fd,str(os.getpid()).encode());os.close(owner_fd)
    resource_stop=ResourceStop(resources)
    os.environ['LAB_RUN_DIR']=str(run)
    # File records emitted only after the inherited harness creates this run.
    state['primary_attempts']+=1;save(W/'STATE.json',state)
    owner_start=time.monotonic()
    try:
        main()
    finally:
        state=json.loads((W/'STATE.json').read_text());state['active_seconds']+=time.monotonic()-owner_start;save(W/'STATE.json',state)
        (W/'OWNER.lock').unlink(missing_ok=True)
