"""Read-only delivery audit. Never starts or repeats a physical attempt."""
from pathlib import Path
import sys,json,hashlib,collections
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def check():
 plan=json.loads((S/'RUN_PLAN.json').read_text());assert plan['t0_unix']==1791385530 and plan['hard_stop_unix']==1791403530
 rows=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
 starts=collections.Counter(r['id'] for r in rows if r['event']=='START');ends=collections.Counter(r['id'] for r in rows if r['event']=='END')
 assert sum(starts.values())<=80 and all(v==1 for v in starts.values())
 ledger=json.loads((S/'TASK_LEDGER.json').read_text());assert set(starts)==set(ledger)
 closed=(S/'PACKAGE_CLOSED.json').exists()
 if closed:assert starts==ends and not any(r['status']=='RUNNING' for r in ledger.values())
 manifest=S/'FINAL_CODE_MANIFEST.json'
 verified=0
 if manifest.exists():
  for rel,value in json.loads(manifest.read_text()).items():
   wanted=value.get('sha256') if isinstance(value,dict) else value
   assert sha(S/rel)==wanted,rel;verified+=1
 print(json.dumps(dict(status='PASS',read_only=True,package_closed=closed,attempts=sum(starts.values()),verified_code_files=verified,B_FROZEN=json.loads((S/'STATE.json').read_text()).get('B_FROZEN',False),physical_dispatch=False)))
def review(ident):
 assert ident.replace('_','').replace('-','').isalnum()
 paths=[S/'reports'/f'{ident}_FUNCTIONAL.json',S/'versions'/f'{ident}_SCI_GATE.json',S/'output'/f'{ident}_RESULT.json']
 p=next(p for p in paths if p.exists());data=json.loads(p.read_text())
 if 'functional' in data:out={k:data.get(k) for k in ('id','functional','functional_checks','legacy_strict','service_gap_ms','actual_native_steps','causal_violations')}
 elif p.parent.name=='versions':out=data
 else:out={k:data.get(k) for k in ('id','status','error','wall_seconds')}
 print(json.dumps(dict(read_only=True,path=str(p),result=out)))
if __name__=='__main__':
 if sys.argv[1:] == ['--check']:check()
 elif len(sys.argv)==3 and sys.argv[1]=='--review':review(sys.argv[2])
 else:raise SystemExit('Use --check or --review EXISTING_ID; no physical reproduction is authorized by this utility.')
