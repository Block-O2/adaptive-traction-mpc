from audit_common import *
def main():
 events=[json.loads(s) for s in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()] if (STUDY/'ATTEMPTS.jsonl').exists() else []
 starts={r['id'] for r in events if r['event']=='START'};ends={r['id'] for r in events if r['event']=='END'}
 results=[read(p) for p in (STUDY/'output').glob('*_RESULT.json')];outcomes=[read(p) for p in (STUDY/'output').glob('*_OUTCOME.json')]
 failures=[dict(id=r.get('id'),error=r.get('error') or (r.get('traceback','').splitlines()[-1] if r.get('traceback') else r['status'])) for r in results if r['status']!='COMPLETE']
 queued=sorted(p.stem for p in (STUDY/'queue').glob('*.json'));attempted=read(STUDY/'TASK_LEDGER.json') if (STUDY/'TASK_LEDGER.json').exists() else {};pending=[name for name in queued if name not in attempted]
 state=dict(phase='REGISTERED_DIAGNOSTICS_RUNNING' if pending or starts-ends else 'PHYSICS_COMPLETE_ANALYSIS',unix=time.time(),elapsed_hours=(time.time()-START)/3600,attempts=len(starts),ended=len(ends),active=sorted(starts-ends),top_level_completed=sum(r['status']=='COMPLETE' for r in results),branch_completed=len(outcomes),branch_qualified=sum(r['metric']['valid'] and r['metric']['matched_eligible'] for r in outcomes),failures=failures,next_queued=pending[:2],next_action='Complete registered fixed-pool continuations and 8 paired attribution runs; analyze saved outputs without training',start_unix=START,deadline_unix=START+6*3600,remaining_attempts=50-len(starts))
 save(STUDY/'STATE.json',state);print(json.dumps(state))
 resources=STUDY/'output/RESOURCES.jsonl'
 if resources.exists():
  r=json.loads(resources.read_text().splitlines()[-1]);print(json.dumps({k:r.get(k) for k in ('mem_available','swap_used','PSS','oom_kill','owned_count')}))
if __name__=='__main__':main()
