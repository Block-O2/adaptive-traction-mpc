"""Every completed native row joins an actual applied receipt; full archives include inherited prefixes."""
import os,sys,json,gzip,time
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime';start=time.time();out=[]
records=[json.loads(s) for s in (R/'ATTEMPTS.jsonl').read_text().splitlines()]
for row in records:
 if row['event']!='START':continue
 ident=row['id'];path=R/'source/results'/ident/'runtime_artifacts.json.gz'
 if not path.exists():out.append({'id':ident,'status':'PARTIAL_NO_FINAL_RAW'});continue
 with gzip.open(path,'rt') as f:d=json.load(f)
 n=d['wall_physics']['native_states_evaluation_only'];rr=d['wall_physics']['command_receipts'];t=np.array([v['time_s'] for v in n]);tau=np.array([v['command_torque_nm'] for v in n]);seen=np.zeros(len(t),np.int8);bad=[];joins=0
 for r in rr:
  if not r.get('applied'):continue
  lo=int(np.searchsorted(t,r['start_physics_s']+1e-10,side='right'));hi=int(np.searchsorted(t,r['end_physics_s']+1e-10,side='right'));count=hi-lo
  if count!=r['native_steps'] or not np.all(tau[lo:hi]==r['command_torque_nm']):bad.append(r['receipt_index'])
  seen[lo:hi]+=1;joins+=count
 res={'id':ident,'status':'PASS' if not bad and np.all(seen==1) else 'FAIL','native_rows':len(n),'applied_receipts':sum(bool(r.get('applied')) for r in rr),'joined_rows':joins,'bad_receipts':bad,'unowned_native_rows':int(np.sum(seen==0)),'multiply_owned_native_rows':int(np.sum(seen>1))};out.append(res);print(ident,res['status'],len(n),flush=True);del d,n,rr,t,tau,seen
result={'status':'PASS' if all(x['status']=='PASS' for x in out) else 'REVIEW_REQUIRED','rows':out,'wall_s':time.time()-start,'scope':'All full archived rows including inherited prefixes; rows are not unique newly executed physics. Time interval(start,end], step count and exact6-axis command torque ownership. Original scorer separately audits native physics/safety and scientific receipts.'};(P/'audit/ALL_RECEIPT_NATIVE_IDENTITY.json').write_text(json.dumps(result,indent=2)+'\n')
