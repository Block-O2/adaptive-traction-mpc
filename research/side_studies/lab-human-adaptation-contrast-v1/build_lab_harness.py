"""Adapt only provenance/output instrumentation of the inherited harness."""
from pathlib import Path
import json,hashlib,ast,shutil
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1');P=W.parent/'human-size-contrast-v1';S=W/'snapshot/stages/stage5_personalized_motion_learning'
original=(P/'human_qualification_inherited.py.txt').read_text();text=original
text=text.replace("R=Path('/home/hank/coding/adaptive-traction-mpc-learning'); S=R/'stages/stage5_personalized_motion_learning'", "W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1'); R=W/'snapshot'; S=R/'stages/stage5_personalized_motion_learning'")
text=text.replace("D=S/'docs/adaptive_human_online_interface_v1'; OUT=S/'results/adaptive_human_online_interface_v1/human'", "D=W; OUT=W/'runs'")
text=text.replace("contract=json.loads((D/'EXPERIMENT_CONTRACT.json').read_text())", "contract=json.loads((D/'CONTRACT.json').read_text()); contract['cases']=[dict(id=e['id'],path=e['case_path'],sha256=e['case_sha256'],case=e['case']) for e in contract['conditions']]")
text=text.replace("for arm in ('continual_adaptive','commissioning_only','fixed_population'):", "for arm in (os.environ['LAB_STUDY_ARM'],):")
text=text.replace("capture={}; context={}", "capture={'stop_check':resource_stop}; context={}")
text=text.replace("# Keep representative and failure traces; other raw artifacts compressed, not rewritten history.", "# Temporary inherited raw artifacts; compact scorer/model evidence must be\n                # extracted before the prospective retention review.")
text=text.replace("state.update(phase='HUMAN_QUALIFICATION'", "state.update(status='RUNNING',phase='PRIMARY_HUMAN_QUALIFICATION'")
text=text.replace("'CURRENT_HUMAN_ADAPTATION_VALIDATION.json'", "'INHERITED_HARNESS_AGGREGATE.json'")
text=text.replace("if __name__=='__main__':main()", "")
text=text.replace("payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key)", "payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key,geometry=rt._jsonable(dict(vars(model.geometry))))\n    signature=json.dumps(payload['geometry'],sort_keys=True,separators=(',',':')).encode();payload['geometry_sha256']=hashlib.sha256(signature).hexdigest()\n    emit_consumption(kind,payload)")
# Guard is called before main. Instrumentation emits only causal model payloads.
footer='''
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
        stream.write(json.dumps(dict(kind=kind,pid=os.getpid(),payload=payload),allow_nan=False)+'\\n')
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
        with (Path(target)/f'prediction_updates_{os.getpid()}.jsonl').open('a') as stream:stream.write(json.dumps(record,allow_nan=False)+'\\n')
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
        with (Path(os.environ['LAB_RUN_DIR'])/'TASK_PREDICTION_SAMPLES.jsonl').open('a') as stream:stream.write(json.dumps(record,allow_nan=False)+'\\n')
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
'''
text+=footer
# Child and parent import this exact script before wrapper registration.
prefix="import os,sys\nfor k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'\nos.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True\nif os.getpriority(os.PRIO_PROCESS,0)<19:os.nice(19-os.getpriority(os.PRIO_PROCESS,0))\n"
text=prefix+text;ast.parse(text);(W/'human_qualification.py').write_text(text)
shutil.copy2(P/'human_qualification_inherited.py.txt',W/'human_qualification_inherited.py.txt')
staging=Path(__file__).parent
shutil.copy2(staging/'lab_resource_guard.py',W/'lab_resource_guard.py');shutil.copy2(__file__,W/'build_lab_harness.py')
print(json.dumps({'runner':str(W/'human_qualification.py'),'sha256':hashlib.sha256(text.encode()).hexdigest(),'algorithm_or_threshold_changed':False}))
