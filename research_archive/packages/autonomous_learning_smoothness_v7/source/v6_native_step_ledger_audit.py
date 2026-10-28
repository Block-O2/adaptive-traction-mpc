"""Independent native-row and time-grid count, including paid partial prefixes."""
from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
def read(q):return json.loads(q.read_text())
def put(n,x):
 q=P/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def one(s):
 ident=s['id'];dp=P/'runtime/output'/(ident+'_DATA.json');pp=P/'runtime/output'/(ident+'_PARTIAL_COMPUTE.json')
 d=read(dp) if dp.exists() else None;metric=d['metric'] if d else read(pp)
 child=d.get('child') if d else None;fork=child['physical_time_at_fork'] if child else 0.
 raw=P/'runtime/source/results'/ident/'runtime_artifacts.json.gz';count=0;new=0;last=None;first=None;bad=[]
 for row in array_items(raw,'native_states_evaluation_only'):
  t=float(row['time_s']);first=t if first is None else first
  if last is not None:
   dt=t-last
   if dt<-1e-9:bad.append('NON_MONOTONIC_NATIVE_TIME')
   if abs(dt-.00025)>1e-7 and abs(dt)>1e-9:bad.append('WRONG_NATIVE_GRID')
  if last is None or t>last+1e-10:
   count+=1
   if t>fork+1e-9:new+=1
  last=t
 expected=metric['actual_new_native_physics_steps'];clock_count=round((last-fork)/.00025)
 if new!=expected:bad.append('NEW_NATIVE_ROW_COUNT_MISMATCH')
 if clock_count!=expected:bad.append('NATIVE_CLOCK_COUNT_MISMATCH')
 return dict(id=ident,status='PASS' if not bad else 'FAIL',raw_native_unique_rows=count,
   fork_physical_s=fork,first_native_s=first,last_native_s=last,
   independently_counted_new_native_steps=new,clock_count=clock_count,recorded_new_native_steps=expected,
   partial_prefix=d is None,errors=sorted(set(bad)))
def summary():
 rows=[read(f) for f in sorted((P/'audit/native_ledger').glob('*.json'))];ev=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in ev if r['event']=='START']
 out=dict(status='PASS' if len(rows)==len(starts) and all(r['status']=='PASS' for r in rows) else 'FAIL' if any(r['status']=='FAIL' for r in rows) else 'IN_PROGRESS',
  updated_unix=time.time(),physical_START=len(starts),audited=len(rows),
  independently_counted_new_native_steps=sum(r.get('independently_counted_new_native_steps',0) for r in rows),
  partial_prefixes=sum(r.get('partial_prefix',False) for r in rows),errors=[r for r in rows if r['status']!='PASS'],
  method='Count monotone native raw timestamps strictly after actual fork time (or0 for cold parent); independently close clock interval at0.25ms. Inherited native prefixes are not recharged; intentional partial parents counted and never ranked.')
 put('audit/NATIVE_STEP_LEDGER_REPLAY.json',out);return out
def drain():
 ev=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];end={r['id'] for r in ev if r['event']=='END'};n=0
 for r in ev:
  if r['event']!='START' or r['id'] not in end or (P/'audit/native_ledger'/(r['id']+'.json')).exists():continue
  result=one(r);put('audit/native_ledger/'+r['id']+'.json',result);n+=1
 return n
def main():
 start=time.time();stop=read(P/'ACTIVATION.json')['hard_stop_unix']-600
 put('owned/NATIVE_LEDGER_SERVICE_START.json',dict(pid=os.getpid(),started_unix=start,deadline_unix=stop,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
 try:
  while True:
   n=drain();s=summary()
   if n:print('NATIVE_LEDGER',s['status'],s['audited'],'new',s['independently_counted_new_native_steps'],flush=True)
   if '--once' in sys.argv or (P/'CLOSURE_START.json').exists() or time.time()>stop:break
   time.sleep(6)
 finally:put('owned/NATIVE_LEDGER_SERVICE_END.json',dict(pid=os.getpid(),ended_unix=time.time(),wall_s=time.time()-start))
if __name__=='__main__':main()
