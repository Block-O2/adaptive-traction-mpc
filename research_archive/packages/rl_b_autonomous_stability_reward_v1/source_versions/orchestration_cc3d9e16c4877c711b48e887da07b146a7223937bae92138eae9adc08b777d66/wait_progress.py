"""Bounded observer for a confirmed live queue; never launches research work."""
import argparse,json,os,time
from research_common import ROOT,HARD_STOP,read,atomic,now,pid_identity,same_pid,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--h1-target',type=int);p.add_argument('--until-file')
    p.add_argument('--only-new',action='store_true');a=p.parse_args()
    target=ROOT/a.until_file if a.until_file else None
    if target:assert target.resolve().is_relative_to(ROOT)
    started=time.time();end=min(started+a.seconds,HARD_STOP-660)
    out=ROOT/'audit/observers'/f'{int(started)}_{os.getpid()}'
    atomic(out/'START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),deadline=end,
           physics_allowed=False,source_sha256=sha(__file__),only_new_results=a.only_new))
    reason='BOUNDED_OBSERVATION_INTERVAL_END';last=0;seen=set()
    if a.only_new and (ROOT/'ALL_ATTEMPTS.jsonl').exists():
        for line in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines():
            try:x=json.loads(line)
            except json.JSONDecodeError:continue
            if x['mode']=='evaluation':seen.add(x['job_id'])
    try:
        while time.time()<end:
            services=[]
            for name in ['CAMPAIGN_PROCESS.json','WATCHDOG_START.json','STATUS_MONITOR_START.json']:
                x=read(ROOT/name,{})
                services.append(dict(name=name,alive=same_pid(x.get('identity'))))
            followups=[dict(name=str(path.relative_to(ROOT)),alive=same_pid(read(path).get('identity')))
                       for path in (ROOT/'followup_queues').glob('*/START.json')]
            services+=followups
            live_followup=any(x['alive'] for x in followups)
            active=[]
            for path in (ROOT/'owned').glob('*.json'):
                x=read(path)
                if not x.get('ended') and x.get('worker'):
                    active.append(dict(job=x['job'],pid=x['worker']['pid'],alive=same_pid(x['worker'])))
            if (ROOT/'STOP.json').exists() or (ROOT/'END.json').exists():reason='CAMPAIGN_STOPPED';break
            failure=ROOT/'QUEUE_FAILURE.json'
            recovery=read(ROOT/'INITIAL_QUEUE_CLOSURE_RECOVERY.json',{})
            recovered=failure.exists() and recovery.get('status')=='RECOVERED_NO_PHYSICS_REPLAY' and recovery.get('failure_sha256')==sha(failure)
            if failure.exists() and not recovered:reason='QUEUE_NEEDS_DIAGNOSIS';break
            if (ROOT/'FINITE_QUEUE_COMPLETE.json').exists() and not live_followup:reason='FINITE_QUEUE_COMPLETE_NEEDS_AGENT_REVIEW';break
            if a.h1_target and read(ROOT/'H1_STABILITY_RESULTS.json',{}).get('target',0)>=a.h1_target:
                reason='PRESPECIFIED_H1_ENDPOINTS_COMPLETE';break
            if target and target.exists():reason='REQUESTED_PHASE_ARTIFACT_READY';break
            if not services[0]['alive'] and not live_followup and not any(x['alive'] for x in active):
                reason='QUEUE_HANDLE_MISSING';break
            if time.time()-last>=50:
                budget=read(ROOT/'LEDGER.json',{});rows=[]
                log=ROOT/'ALL_ATTEMPTS.jsonl'
                if log.exists():
                    for line in log.read_text().splitlines():
                        try:x=json.loads(line)
                        except json.JSONDecodeError:continue
                        if x['mode']=='evaluation' and x['job_id'] not in seen:
                            rows.append(dict(job=x['job_id'],success=x['success'],task_s=x['task_s'],status=x['status']))
                            seen.add(x['job_id'])
                print(json.dumps(dict(time_utc=now(),active=active,confirmed_services=services,
                     training_attempts=budget.get('training_attempts'),evaluation_attempts=budget.get('evaluation_attempts'),
                     native_steps=budget.get('native_steps'),optimizer_steps=budget.get('optimizer_steps'),
                     frozen_results_new_to_observer=rows),ensure_ascii=False),flush=True)
                last=time.time()
            time.sleep(2)
    finally:
        atomic(out/'END.json',dict(time_utc=now(),reason=reason,elapsed_s=time.time()-started))
        print(json.dumps(dict(observer_end=reason,elapsed_s=time.time()-started)),flush=True)
if __name__=='__main__':main()
