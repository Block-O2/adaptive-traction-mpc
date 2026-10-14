"""Read-only numerical diagnostic of archived physical records; no controller imports."""
from pathlib import Path
import json,gzip,hashlib
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');D=R/'docs/professor_update_2026-10-14'
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
records=[]
for label,name in [('Baseline B','development_repair2_B0_original'),('18D development best','development_repair2_quality_NATIVE_SCALAR_18_063')]:
 run=P/'source/results'/name;z=np.load(P/'motion_series'/(name+'.npz'));t=z['time_s'];t0=float(t[0]);v=np.degrees(z['true_dq_rad_s']);acc=np.degrees(z['acceleration_rad_s2']);jerk=np.degrees(z['jerk_rad_s3']);phase=z['phase']
 derivative_a=np.gradient(z['true_dq_rad_s'],t,axis=0,edge_order=2);derivative_j=np.gradient(derivative_a,t,axis=0,edge_order=2)
 assert np.array_equal(derivative_a,z['acceleration_rad_s2']) and np.array_equal(derivative_j,z['jerk_rad_s3'])
 tr=np.load(run/'trace.npz');mask=tr['stage']=='TASK';ts=tr['time_s'][mask];rv=np.degrees(tr['reference_dq_rad_s'][mask]);samplev=np.degrees(tr['evaluation_only_human_state_rad_rad_s'][mask,2:]);d=samplev-rv
 ix=np.searchsorted(t,ts);ix=np.clip(ix,0,len(t)-1);ix=np.where((ix>0)&(abs(t[np.maximum(ix-1,0)]-ts)<abs(t[ix]-ts)),np.maximum(ix-1,0),ix)
 assert np.max(abs(t[ix]-ts))<1e-7;assert np.max(abs(v[ix]-samplev))<1e-8
 summary=json.loads((run/'summary.json').read_text())
 with gzip.open(run/'runtime_artifacts.json.gz','rt') as f:art=json.load(f)
 events=[]
 for dec in summary['decisions']:
  rid=dec['timing_request_id'];activation=float(dec['actual_schedule_start_physics_s']);request=float(dec['decision_request_time_s']);events.append({'kind':'request','time_s':request-t0,'request_id':rid,'phase':dec['phase']});events.append({'kind':'activation','time_s':activation-t0,'request_id':rid,'phase':dec['phase'],'outcome':dec['activation_outcome'],'reference_boundary_continuity':dec.get('reference_boundary_continuity')})
 for ev in art['rolling_splice_events']:
  if ev.get('actual_splice_physics_s') is not None:events.append({'kind':'suffix_effective','time_s':float(ev['actual_splice_physics_s'])-t0,'request_id':ev['request_id'],'outcome':ev['outcome'],'composite_activation_s':ev['composite_activation_physics_s']-t0})
 # Receipt entries inside causal command baselines record actual applied-command ownership.
 receipts={}
 for attempt in art['execution_attempts']:
  for con in attempt.get('incremental_acceleration_projection',{}).get('window_command_baseline',{}).get('contributions',[]):
   if 'receipt_index' in con:receipts[int(con['receipt_index'])]=float(con['time_s'])-t0
 receipts=[{'receipt_index':i,'time_s':tt} for i,tt in sorted(receipts.items(),key=lambda x:x[1]) if -1e-7<=tt<=t[-1]-t0+1e-7]
 acts=[e for e in events if e['kind']=='activation'];splices=[e for e in events if e['kind']=='suffix_effective']
 def near(now,arr):
  if not arr:return None
  e=min(arr,key=lambda r:abs(now-r['time_s']));return {**e,'delta_ms':1000*(now-e['time_s'])}
 extrema=[]
 for signal,values,timegrid in [('velocity_error_5ms',d,ts-t0),('raw_acceleration',acc,t-t0),('raw_jerk',jerk,t-t0)]:
  for j,joint in enumerate(['hip','knee']):
   k=int(np.argmax(abs(values[:,j])));now=float(timegrid[k]);nearest_receipt=near(now,receipts)
   extrema.append({'signal':signal,'joint':joint,'time_s':now,'signed_value':float(values[k,j]),'abs_value':float(abs(values[k,j])),'phase':str(phase[int(np.argmin(abs(t-t0-now)))]),'nearest_activation':near(now,acts),'nearest_suffix':near(now,splices),'nearest_receipt':nearest_receipt,'endpoint_derivative_stencil':bool(signal!='velocity_error_5ms' and (k<2 or k>len(t)-3))})
 phase_stats=[]
 for ph in ['OUTBOUND','HOLD','RETURN']:
  m=tr['task_phase'][mask]==ph
  phase_stats.append({'phase':ph,'start_s':float((ts-t0)[m][0]),'end_s':float((ts-t0)[m][-1]),'max_abs_velocity_error_deg_s':abs(d[m]).max(axis=0).tolist(),'rms_velocity_error_deg_s':np.sqrt(np.mean(d[m]**2,axis=0)).tolist(),'true_reference_velocity_correlation':[float(np.corrcoef(samplev[m,j],rv[m,j])[0,1]) if np.std(rv[m,j])>1e-8 else None for j in range(2)]})
 # Continuity is evaluated as sampled changes across nearest 5ms intervals, not jumps.
 event_changes=[]
 for ev in splices:
  k=int(np.argmin(abs(ts-t0-ev['time_s'])));lo=max(k-1,0);hi=min(k+1,len(ts)-1)
  event_changes.append({'suffix_time_s':ev['time_s'],'reference_change_over_10ms_deg_s':(rv[hi]-rv[lo]).tolist(),'true_change_over_10ms_deg_s':(samplev[hi]-samplev[lo]).tolist()})
 rec={'label':label,'case':name,'task_t0_absolute_s':t0,'native_samples':len(t),'native_dt_s':float(np.median(np.diff(t))),'task_duration_s':float(t[-1]-t0),'reference_samples':len(ts),'reference_dt_s':float(np.median(np.diff(ts))),'derivative_reconstruction':'np.gradient(raw true dq, absolute time, axis=0, edge_order=2), then same gradient for jerk; exactly matches archived arrays','native_trace_alignment_max_error_s':float(np.max(abs(t[ix]-ts))),'extrema':extrema,'phase_statistics':phase_stats,'events':events,'receipts':receipts,'reference_suffix_sampled_changes':event_changes,'source_files':[{'path':str(f),'sha256':sha(f)} for f in [P/'motion_series'/(name+'.npz'),run/'trace.npz',run/'summary.json',run/'runtime_artifacts.json.gz',run/'native_reference.npz']]}
 records.append(rec)
 print('CASE',label,'RMS_PHASE',phase_stats,flush=True)
 print('EXTREMA',[{k:r[k] for k in ['signal','joint','time_s','abs_value','nearest_activation','nearest_suffix','nearest_receipt']} for r in extrema],flush=True)
 print('EVENTS',len(acts),len(splices),'RECEIPTS',len(receipts),'LARGEST_REF_CHANGE_10MS',np.max(abs(np.asarray([e['reference_change_over_10ms_deg_s'] for e in event_changes])),axis=0),flush=True)
(D/'evidence/VELOCITY_DIAGNOSTIC_DATA.json').write_text(json.dumps({'scope':'read-only archived-data explanatory diagnostic; no new physics or algorithm change','filtering':'none; raw archived native derivatives and 5ms reference trace','time_basis':'task elapsed simulation time; wall timestamps never treated as simulation timestamps','cases':records},ensure_ascii=False,indent=2))
