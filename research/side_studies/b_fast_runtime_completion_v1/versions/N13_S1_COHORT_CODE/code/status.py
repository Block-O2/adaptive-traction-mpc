from task_bootstrap import *
events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts={e['id']:e for e in events if e['event']=='START'};ends={e['id']:e for e in events if e['event']=='END'}
results=[]
for id in ends:
 p=STUDY/'output'/(id+'_RESULT.json')
 if p.exists():
  r=json.loads(p.read_text());m=r.get('metric',{});results.append(dict(id=id,worker=r['status'],valid=m.get('valid'),physical_status=m.get('status'),J_F=m.get('J_F'),error=r.get('error')))
p=STUDY/'output/RESOURCE_LOG.jsonl';resource=json.loads(p.read_text().splitlines()[-1]) if p.exists() and p.stat().st_size else {}
print(json.dumps(dict(elapsed_h=(time.time()-START)/3600,attempts=len(starts),ended=len(ends),active=[k for k in starts if k not in ends],results=results,resources={k:resource.get(k) for k in ('unix','mem_available','swap_used','PSS','windows','oom_kill')})))
