from task_bootstrap import *
events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()]
starts={r['id']:r for r in events if r['event']=='START'};ends={r['id']:r for r in events if r['event']=='END'}
ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text())
prefix=sys.argv[1] if len(sys.argv)>1 else ''
tasks={k:v for k,v in ledger.items() if k.startswith(prefix)}
resources=STUDY/'output/RESOURCES.jsonl'
r=json.loads(resources.read_text().splitlines()[-1])
print(json.dumps(dict(elapsed_h=(time.time()-START)/3600,attempts=len(starts),ended=len(ends),active=[k for k in starts if k not in ends],phase_tasks=len(tasks),phase_done=sum(v['status']=='COMPLETE' for v in tasks.values()),phase_failed=[k for k,v in tasks.items() if v.get('worker_status')=='FAILED'],resource_age_s=time.time()-r['unix'],WSL_available_GiB=r['mem_available']/2**30,windows_commit_GiB=r['windows'].get('commit_headroom',0)/2**30,PSS_GiB=r['PSS']/2**30,swap_MiB=r['swap_used']/2**20,oom_kill=r['oom_kill'])))
