from task_bootstrap import *
def main():
 events=[json.loads(l) for l in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if l.strip()];starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END'];done={e['id'] for e in ends};rows=[]
 for p in sorted((STUDY/'output').glob('*_RESULT.json')):
  r=json.loads(p.read_text());m=r.get('metric',{});rows.append(dict(id=r['id'],worker=r['status'],valid=m.get('valid',False),physical_status=m.get('status'),J_F=m.get('J_F') if m.get('valid') else None,error=r.get('error')))
 resource=STUDY/'output/RESOURCE_LOG.jsonl';rs=json.loads(resource.read_text().splitlines()[-1]) if resource.exists() else {}
 print(json.dumps(dict(elapsed_h=(time.time()-START)/3600,attempts=len(starts),ended=len(ends),active=[e['id'] for e in starts if e['id'] not in done],valid_runs=sum(r['valid'] for r in rows),invalid_or_failed=len(rows)-sum(r['valid'] for r in rows),last_results=rows[-10:],resources={k:rs.get(k) for k in ('unix','mem_available','swap_used','PSS','windows','oom_kill')})))
if __name__=='__main__':main()
