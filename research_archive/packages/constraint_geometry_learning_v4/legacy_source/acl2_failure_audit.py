"""Audit failed/partial native ownership without promoting incomplete cost."""
import json,gzip
from pathlib import Path
import numpy as np
from acl2_shared import P,R,read,sha,utc
def audit(ident):
 path=R/'source/results'/ident;raw=path/'runtime_artifacts.json.gz';data=R/'output'/(ident+'_DATA.json');partial=R/'output'/(ident+'_PARTIAL_COMPUTE.json');errors=[]
 d=json.loads(data.read_text()) if data.exists() else None;p=json.loads(partial.read_text()) if partial.exists() else None
 with gzip.open(raw,'rt') as f:artifact=json.load(f)
 wall=artifact['wall_physics'];native=wall['native_states_evaluation_only'];receipts=[r for r in wall['command_receipts'] if r.get('applied') and r.get('native_steps',0)>0];receipts.sort(key=lambda r:r['start_physics_s'])
 nt=np.asarray([r['time_s'] for r in native]);start=np.asarray([r['start_physics_s'] for r in receipts]);end=np.asarray([r['end_physics_s'] for r in receipts]);ix=np.searchsorted(start,nt-.00025+1e-9,side='right')-1
 if np.any(ix<0):errors.append('UNOWNED_NATIVE')
 ix=np.clip(ix,0,len(receipts)-1);within=np.all((nt-.00025>=start[ix]-1e-8)&(nt-.00025<end[ix]+1e-8));counts=np.bincount(ix,minlength=len(receipts));expected=np.asarray([r['native_steps'] for r in receipts]);torque=np.asarray([r['command_torque_nm'] for r in native]);commands=np.asarray([r['command_torque_nm'] for r in receipts]);torque_error=float(np.max(abs(torque-commands[ix]),initial=0))
 if not within:errors.append('RECEIPT_INTERVAL')
 if not np.array_equal(counts,expected):errors.append('RECEIPT_NATIVE_COUNT')
 if torque_error!=0:errors.append('APPLIED_TORQUE')
 metric=d['metric'] if d is not None else p or {};recorded_total=metric.get('native_physics_steps');actual=metric.get('actual_new_native_physics_steps')
 if recorded_total is not None and int(recorded_total)!=len(native):errors.append('PARTIAL_NATIVE_COUNT')
 jf=jm=None;integral_error=None;trace=path/'trace.npz'
 if trace.exists():
  with np.load(trace) as z:
   idx=z['stage']=='TASK';t=z['time_s'][idx];f=z['physical_cuff_force_world_n'][idx];m=z['physical_cuff_moment_world_nm'][idx]
  if len(t)>1:
   dt=np.diff(t);jf=float(np.linalg.norm(f[:-1],axis=1)@dt);jm=float(np.linalg.norm(m[:-1],axis=1)@dt)
   if metric.get('J_F') is not None:
    integral_error=jf-metric['J_F']
    if abs(integral_error)>1e-7:errors.append('PARTIAL_FORCE_INTEGRAL')
 summary=json.loads((path/'summary.json').read_text()) if (path/'summary.json').exists() else {}
 return dict(id=ident,status='FAILED_TASK_RAW_AUDIT_PASS' if not errors and d is not None else 'PARTIAL_NATIVE_OWNERSHIP_PASS' if not errors else 'FAIL',errors=errors,formal_force_rank_allowed=False,task_complete=False,abort_reason=summary.get('abort_reason'),actual_new_native_steps=actual,full_archived_native_steps=len(native),positive_step_receipts=len(receipts),native_time_intervals_owned=bool(within),receipt_step_counts_exact=bool(np.array_equal(counts,expected)),torque_max_abs_error_Nm=torque_error,partial_JF_unranked=jf,partial_JM_unranked=jm,partial_JF_error_vs_original=integral_error,partial_compute=p,original_task_valid=metric.get('task_valid'),source_sha256=sha(__file__),audit_utc=utc(),input_sha256={str(f.relative_to(P)):sha(f) for f in [raw,data if data.exists() else partial] if f.exists()})
