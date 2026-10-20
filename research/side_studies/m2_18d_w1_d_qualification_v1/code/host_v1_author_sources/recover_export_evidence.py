"""Read-only failed-export recovery; never promote a missing task summary."""
from pathlib import Path
import os,sys,json,gzip,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_w1_d_qualification_v1');sys.path.insert(0,str(S/'code'))
import numpy as np
def main():
 ident='005_M2_guard_off_retry'
 with gzip.open(S/'source/results'/ident/'runtime_artifacts.json.gz','rt') as f:x=json.load(f)
 wp=x['wall_physics'];receipts={r['receipt_index']:r for r in wp['command_receipts']};violations=[]
 for step in wp['native_states_evaluation_only']:
  r=receipts[step['command_id']]
  if r.get('apply_ns') is not None and step['native_grid_start_ns']<r['apply_ns']:violations.append('GRID_BEFORE_WRITE')
  if not np.array_equal(step['command_torque_nm'],r['command_torque_nm']):violations.append('TORQUE_OWNER_MISMATCH')
 expired=[r['receipt_index'] for r in receipts.values() if r.get('apply_ns') is not None and r['apply_ns']-r['source_capture_ns']>100_000_000]
 ipc=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text());co=[r['m2_worker_evidence'] for r in ipc['rows'] if 'm2_worker_evidence' in r];task={r['request_id']:r for r in x['requests'] if r['stage']=='TASK'}
 decisions=[d for d in x['task_decisions'] if d.get('plan_activated') and d.get('actual_schedule_start_physics_s') is not None]
 rows=[]
 for e in co:
  s=e.get('selection_row');rid=e['request_id'];req=task.get(rid,{});found=[d for d in decisions if d['timing_request_id']==rid];owned=[]
  for d in found:
   begin=d['actual_schedule_start_physics_s'];after=[z['actual_schedule_start_physics_s'] for z in decisions if z['actual_schedule_start_physics_s']>begin];end=min(after) if after else wp['physics_elapsed_s']
   owned += [r for r in receipts.values() if r.get('applied') and r.get('native_steps',0)>0 and begin<=r['start_physics_s']<end]
  phase=None if s is None else s['context']['phase'];i=5 if s is None else s['count_before'][phase];action=np.zeros(3) if s is None or i>=5 else np.asarray(s['applied_plan'])[('OUTBOUND','RETURN').index(phase),i];nonzero=bool(np.any(np.abs(action)>1e-12));steps=sum(r['native_steps'] for r in owned)
  rows.append(dict(request_id=rid,source_capture_ns=e['source_capture_ns'],selection=s,worker=e,lifecycle=req,applied_current_K3=action.tolist(),actual_native_steps=steps,physically_executed_nonzero=bool(nonzero and req.get('outcome')=='ACTIVATED' and steps>0),receipts=[{k:r.get(k) for k in ('receipt_index','source_capture_ns','apply_ns','sensor_age_at_apply_ms','q_ref_rad','dq_ref_rad_s','reference_version','start_physics_s','end_physics_s','native_steps')} for r in owned],join_authority='original task_decision actual_schedule_start_physics_s to next activated schedule; secondary failed-export evidence only'))
 out=dict(id=ident,status='FAILED_EXPORT_PARTIAL_EVIDENCE_ONLY',PHYSICAL_TASK_VALID='NOT_EVALUABLE_FULL_ORIGINAL_SUMMARY_MISSING',HOST_EXECUTION_CAUSAL_VALID='PASS' if not violations and not expired and len(wp['native_states_evaluation_only'])==sum(r['native_steps'] for r in receipts.values()) else 'FAIL',native_steps=len(wp['native_states_evaluation_only']),causal_violations=dict(collections.Counter(violations)),expired_writes=expired,actual_nonzero_count=sum(r['physically_executed_nonzero'] for r in rows),actual_nonzero_native_steps=sum(r['actual_native_steps'] for r in rows if r['physically_executed_nonzero']),rows=rows,full_task_pairing_valid=False,original_failure_preserved=True,Q_updates=0)
 (S/'reports'/(ident+'_RECOVERED_EXECUTION_EVIDENCE.json')).write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ('status','HOST_EXECUTION_CAUSAL_VALID','native_steps','actual_nonzero_count','actual_nonzero_native_steps')}))
if __name__=='__main__':main()
