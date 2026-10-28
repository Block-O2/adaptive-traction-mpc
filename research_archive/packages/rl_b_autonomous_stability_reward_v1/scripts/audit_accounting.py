"""Independent joins across admission ledger, episode summaries and PPO logs."""
from pathlib import Path
import sys,json,gzip,time
from research_common import ROOT,RUNTIME,read,atomic,now,sha,same_pid

def evidence(p):
    if p.exists():return json.loads(p.read_text())
    with gzip.open(str(p)+'.gz','rt') as f:return json.load(f)
def audit(final=False):
    value=read(ROOT/'LEDGER.json');attempts=value['attempts'];errors=[];checks=[]
    ids=[a['id'] for a in attempts];paths=[a['run'] for a in attempts]
    if len(set(ids))!=len(ids) or len(set(paths))!=len(paths):errors.append('DUPLICATE_ATTEMPT_ID_OR_RUN')
    counted={kind:sum(a['kind']==kind for a in attempts) for kind in ['training','evaluation']}
    for kind,n in counted.items():
        if value[kind+'_attempts']!=n:errors.append(kind+'_ATTEMPT_COUNTER_MISMATCH')
    settled=[a for a in attempts if a['settled']];open_=[a for a in attempts if not a['settled']]
    native=sum(a['native_steps'] for a in settled)
    if native!=value['native_steps']:errors.append('NATIVE_SETTLED_SUM_MISMATCH')
    if native+sum(a['reserved_native_steps'] for a in open_)>50000000:errors.append('NATIVE_WITH_RESERVATIONS_OVER_CAP')
    if len(open_)>1:errors.append('MORE_THAN_ONE_PHYSICAL_ENVIRONMENT_ADMITTED')
    adam=sum(a.get('optimizer_steps',0) for a in settled)
    adam+=sum(x['additional_Adam_updates'] for x in value.get('offline_update_recoveries',[]))
    if adam!=value['optimizer_steps']:errors.append('ACTUAL_ADAM_COUNTER_MISMATCH')
    decisions=sum(a.get('rl_decisions',0) for a in settled)
    if decisions!=value['rl_decisions']:errors.append('RL_DECISION_COUNTER_MISMATCH')
    wall_now=time.time()
    for a in settled:
        if not 0<=a['native_steps']<=a['reserved_native_steps']:errors.append(a['id']+':NATIVE_RANGE')
        # A live worker writes END immediately after settlement. Avoid treating
        # that documented atomic ordering as a missing closed evidence file.
        end_epoch=__import__('datetime').datetime.fromisoformat(a['end_utc']).timestamp()
        if not final and wall_now-end_epoch<2:continue
        run=Path(a['run']);start=read(run/'START.json');end=read(run/'END.json')
        result=read(run/'RESULT.json');row=dict(id=a['id'],run=a['run'],checks={})
        c=row['checks'];c['START_exists']=bool(start);c['END_exists']=bool(end)
        c['attempt_native_within_reservation']=a['native_steps']<=a['reserved_native_steps']
        if result:
            info=evidence(run/'env/episode_0001/episode_summary.json')
            c['ledger_row_native_equal']=a['native_steps']==result['native_steps']==info['native_steps_total']
            c['RL_decisions_equal']=a.get('rl_decisions',0)==result['rl_decisions']
            c['real_Adam_updates_equal']=a.get('optimizer_steps',0)==result['gradient_updates']
            c['task_native_duration_equal']=abs(info['task_native_steps']*.00025-info['task_s'])<1e-7
            c['full_partial_identity_equal']=(result['integral_scope']=='COMPLETE_TASK')==result['success']==info['success']
            c['original_independent_audits_pass']=result['independent_audit_pass'] is True
            c['native_receipt_audit_recorded']=(run/'env/episode_0001/CLOUD_CASE_AUDIT.json').exists()
        else:
            c['failure_explicitly_preserved']=bool(read(RUNTIME/'jobs'/a['job']/'FAILURE.json')) or bool(a.get('native_counting'))
        row['pass']=all(c.values());checks.append(row)
        if not row['pass']:errors.append(dict(attempt=a['id'],failed=[k for k,v in c.items() if not v]))
    if value['training_attempts']>450 or value['evaluation_attempts']>60:errors.append('ATTEMPT_CAP_EXCEEDED')
    if final and open_:errors.append('UNSETTLED_ATTEMPTS_AT_FINAL')
    engineering_records=[]
    for name in ['H2_AGGREGATION_ENGINEERING_TEST.json','PENDING_BUFFER_EQUIVALENCE_TEST.json']:
        e=read(ROOT/'audit'/name,{})
        if e:engineering_records.append(dict(artifact='audit/'+name,synthetic_Adam_updates=e.get('synthetic_Adam_updates',0)))
    out=dict(time_utc=now(),scope='FINAL_ALL_ATTEMPTS' if final else 'LIVE_SETTLED_ATTEMPTS_OLDER_THAN2s',
        pass_=not errors,errors=errors,admitted_attempts=len(attempts),settled_attempts=len(settled),open_attempts=open_,
        sums=dict(training_attempts=counted['training'],evaluation_attempts=counted['evaluation'],
             native_steps=native,real_Adam_updates=adam,RL_decisions=decisions),
        engineering_only_synthetic_Adam_updates=sum(e['synthetic_Adam_updates'] for e in engineering_records),
        engineering_update_records=engineering_records,
        synthetic_steps_in_task_training_ledger=False,checks=checks,
        source_sha256=sha(Path(__file__)),no_new_physics=True)
    atomic(ROOT/'audit'/('FINAL_ACCOUNTING_AUDIT.json' if final else 'LIVE_ACCOUNTING_AUDIT.json'),out)
    return out
if __name__=='__main__':
    x=audit('--final' in sys.argv);print(json.dumps({k:x[k] for k in ['pass_','errors','admitted_attempts','settled_attempts','sums','engineering_only_synthetic_Adam_updates']}))
    raise SystemExit(0 if x['pass_'] else 1)
