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
 task_trace=[x for x in d.get('trace',[]) if x.get('stage')=='TASK'];task_begin=min((x['time_s'] for x in task_trace),default=float('inf'));task_end=max((x['time_s'] for x in task_trace),default=-float('inf'));task_receipts=[x for x in rr if x.get('applied') and task_begin-1e-9<=x['source_sample_time_s']<=task_end+1e-9];trace_map={round(x['time_s'],7):x for x in task_trace if x.get('robot_torque_components',{}).get('clipping') is not None};missing=[];tau_bad=[];clipping=0;reconstruct_error=0.
 for receipt in task_receipts:
  tr=trace_map.get(round(receipt['source_sample_time_s'],7))
  if tr is None:missing.append(receipt['receipt_index']);continue
  comp=tr['robot_torque_components'];actual=np.array(receipt['command_torque_nm']);applied=np.array(tr.get('applied_robot_tau_nm',actual));total=sum((np.array(comp[k]) for k in ['base','position','velocity','allocator','clipping']),np.zeros(6));reconstruct_error=max(reconstruct_error,float(np.max(abs(total-actual))))
  if not np.array_equal(applied,actual):tau_bad.append(receipt['receipt_index'])
  clipping+=bool(np.any(abs(np.array(comp['clipping']))>1e-9))
 guards=[e['clearance_feedback'] for e in d.get('execution_attempts',[]) if e.get('clearance_feedback')];guard_box_saturated=sum(bool(e.get('active') and np.any(np.isclose(abs(np.array(e['adjusted_acceleration_rad_s2'])),np.array(e['joint_acceleration_box_rad_s2']),rtol=0,atol=1e-9))) for e in guards)
 clipping_audit=dict(task_applied_receipts=len(task_receipts),joined_clipping_log_receipts=len(task_receipts)-len(missing),missing_receipts=missing,applied_torque_mismatch_receipts=tau_bad,task_robot_torque_clipped_commands=int(clipping),component_sum_max_error_nm=reconstruct_error,coverage='FULL_TASK_RECEIPT_JOIN' if not missing and not tau_bad and reconstruct_error<1e-8 else 'PARTIAL_NOT_EXHAUSTIVE',cadence='Measured original trace is5ms, plus terminal boundary nodes; no use of SAC wrapper20ms assumption')
 res={'id':ident,'status':'PASS' if not bad and np.all(seen==1) else 'FAIL','native_rows':len(n),'actual_torque_max_abs_nm':np.max(abs(tau),axis=0).tolist(),'task_clipping_audit':clipping_audit,'guard_acceleration_box_saturated_samples':int(guard_box_saturated),'applied_receipts':sum(bool(r.get('applied')) for r in rr),'joined_rows':joins,'bad_receipts':bad,'unowned_native_rows':int(np.sum(seen==0)),'multiply_owned_native_rows':int(np.sum(seen>1))};out.append(res);print(ident,res['status'],len(n),flush=True);del d,n,rr,t,tau,seen
result={'status':'PASS' if all(x['status']=='PASS' for x in out) else 'REVIEW_REQUIRED','rows':out,'wall_s':time.time()-start,'scope':'All full archived rows including inherited prefixes; rows are not unique newly executed physics. Time interval(start,end], step count and exact6-axis command torque ownership. Original scorer separately audits native physics/safety and scientific receipts.'};(P/'audit/ALL_RECEIPT_NATIVE_IDENTITY.json').write_text(json.dumps(result,indent=2)+'\n')
