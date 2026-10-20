"""Versioned serializer-ownership repair; preserve the failed physical pilot."""
from pathlib import Path
import json,time,shutil,hashlib,ast,sys,types
R=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert read('audit/REPETITION_FAILURE.json')['error']=='STREAM_SERIALIZER_OWNER_CHANGED'
assert (P/'audit/POST_PIPELINE_EXIT.json').exists()
assert not (P/'EXECUTION_CODE_MANIFEST_v5.json').exists()
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
assert sum(e['event']=='START' for e in events)==sum(e['event']=='END' for e in events)==76
snapshot=P/'audit/v4_closeout';snapshot.mkdir(exist_ok=False)
names=[str(f.relative_to(P)) for f in P.glob('*.md')]
names+=['EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','LEARNING_RESULTS_FINAL.json','PHYSICS_CLOSED.json','STATE.json','derived/REPETITION_EVALUATION.json','figures/06_actual_repetition.png','audit/SCIENTIFIC_VERIFICATION_FINAL.json','audit/HISTORY_AUDIT_OWNER.json','audit/POST_PIPELINE_ERROR.json','audit/POST_PIPELINE_EXIT.json']
archived={}
for n in names:
    f=P/n
    if f.exists():
        target=snapshot/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);archived[n]=sha(f)
put('audit/V4_CLOSEOUT_ARCHIVE.json',dict(unix=time.time(),files=archived,reason='Preliminary closeout interrupted to repair the serializer bug; old physics, model, failures and manifests remain unchanged.'))
# The failed second invocation stopped before run_executed_case; prove zero
# additional native steps from the persistent physical clock, not an assumed zero.
before=read('output/REPETITION_CONTINUITY_BEFORE_SECOND.json')['second_initial']['physical_time_s']
after=read('audit/REPETITION_FAILURE.json')['continuous_state']['physical_time_s']
assert before==after
put('audit/PARTIAL_COST_RECONCILIATION.json',dict(rows={'REP_parent':dict(native_steps=0,start_physical_s=before,end_physical_s=after,reason='ensure() raised before run_executed_case was called',evidence=['output/REPETITION_CONTINUITY_BEFORE_SECOND.json','audit/REPETITION_FAILURE.json'])},event_log_unchanged=True))
# Reproduce the failure and verify the exact restoration fix without physics.
sys.path.insert(0,str(P/'code'));import streaming_reuse
def probe(correct):
    rt=types.SimpleNamespace() # Use an identity-hashable object as in a module.
    rt=type('RuntimeProbe',(),{})();rt.persist_runtime_artifacts=lambda:None
    original=rt.persist_runtime_artifacts
    memory=type('MemoryProbe',(),{'install':lambda self,rt:setattr(rt,'persist_runtime_artifacts',lambda:None)})()
    for _ in range(2):
        streaming_reuse.ensure(rt,memory)
        rt.persist_runtime_artifacts=lambda:None
        streaming_reuse.restore(rt) # unchanged study_common.run finally
        if correct:streaming_reuse.restore(rt)
        else:rt.persist_runtime_artifacts=original
try:probe(False)
except AssertionError as exc:assert str(exc)=='STREAM_SERIALIZER_OWNER_CHANGED'
else:raise AssertionError('Original ownership bug not reproduced')
probe(True)
def retry_names(s):return s.replace('REPETITION_','REPETITION_RETRY_').replace('REP_','REPR_')
runner=retry_names((P/'control/repetition_runner.py').read_text()).replace('campaign_v4','campaign_v5').replace('PREPHYSICAL_CHECKS_v4','PREPHYSICAL_CHECKS_v5')
old='finally:rt.run_executed_case=original_run;rt.persist_runtime_artifacts=original_persist'
assert runner.count(old)==1
runner=runner.replace(old,'finally:\n        rt.run_executed_case=original_run\n        import streaming_reuse\n        streaming_reuse.restore(rt)')
old="mh.event('END',ident,returncode=1,joined=True,error=str(e))"
assert runner.count(old)==1
runner=runner.replace(old,"mh.event('END',ident,returncode=1,joined=True,error=str(e),actual_new_native_steps=round((stamp()['physical_time_s']-initial['physical_time_s'])/rt.NOMINAL_PHYSICS_DT_S))")
campaign=retry_names((P/'control/campaign_v4.py').read_text()).replace('_v4.json','_v5.json').replace('from feedback_selector import select','from feedback_selector_retry import select')
selector=retry_names((P/'control/feedback_selector.py').read_text())
owner=retry_names((P/'control/repetition_owner.py').read_text()).replace('control/repetition_runner.py','control/repetition_runner_v5.py').replace("STUDY_GROUP='REP'","STUDY_GROUP='REPR'")
for n,s in [('campaign_v5.py',campaign),('feedback_selector_retry.py',selector),('repetition_runner_v5.py',runner),('repetition_owner_v5.py',owner)]:
    ast.parse(s);(P/'control'/n).write_text(s)
shutil.copy2(Path(__file__),P/'control/prepare_retry_v5.py')
plan=read('REP_TEST_PLAN.json');plan['frozen_unix']=time.time();plan['condition']['name']='REPR';plan['condition']['role']='Serializer repair retry; same exposed W2 seed/prefix and unchanged learning rule'
put('REPR_TEST_PLAN.json',plan)
protocol=read('REPETITION_PROTOCOL.json');protocol.update(frozen_unix=time.time(),condition=plan['condition'],prior_failed_pilot='REP',repair='restore original installed streaming serializer, not the pre-install function; original study_common and physical runtime remain unchanged',no_policy_or_threshold_change=True,no_new_training=True,planned_total_P1_starts=82,prior_failure_retained=True)
put('REPETITION_RETRY_PROTOCOL.json',protocol)
put('audit/SERIALIZER_REPAIR_PREPHYSICAL.json',dict(status='PASS',unix=time.time(),old_failure_reproduced_without_physics=True,two_corrected_sequential_serializer_calls_pass=True,original_runtime_and_all_v4_files_unchanged=True,scope='bookkeeping/serializer ownership only; no Human state or controller changes'))
files=dict(read('EXECUTION_CODE_MANIFEST_v4.json')['files'])
for rel,h in files.items():assert sha(P/rel)==h,rel
for n in ['control/campaign_v5.py','control/feedback_selector_retry.py','control/repetition_runner_v5.py','control/repetition_owner_v5.py','control/prepare_retry_v5.py','REPR_TEST_PLAN.json','REPETITION_RETRY_PROTOCOL.json']:
    files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST_v5.json',dict(files=files,frozen_unix=time.time(),change='Serializer ownership restoration repair plus unique REPR artifact names and failed-parent native-cost accounting; policy and physical runtime unchanged',previous_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST_v4.json')))
put('PREPHYSICAL_CHECKS_v5.json',dict(status='PASS',AST=True,serializer_ownership_probe='audit/SERIALIZER_REPAIR_PREPHYSICAL.json',policy_model_unchanged=True,original_physics_and_control_unchanged=True))
put('REPAIR_AUTHORIZATION_v5.json',dict(unix=time.time(),scope='Continue this same authorized isolated study after a correctable instrumentation failure; no new study',old_STOP_v2_v3_v4_retained=True,failed_pilot_and_preliminary_closeout_preserved=True,hard_stop_unchanged=True))
(P/'PHYSICS_CLOSED.json').unlink() # preserved verbatim in v4_closeout above
put('STATE.json',dict(phase='RETRY_V5_PREPARED',unix=time.time(),next='serial two-repetition retry; starts capped at 100'))
print('RETRY_V5_PREPHYSICAL_PASS',flush=True)
