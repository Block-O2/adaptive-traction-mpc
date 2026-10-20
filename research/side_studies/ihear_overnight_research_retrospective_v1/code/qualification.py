"""Original evaluator plus frozen user qualification criteria; no threshold edits."""
from pathlib import Path
import sys,json,collections
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1')
sys.path.insert(0,str(S/'code'))
from audit import summarize,quantile
from stream_runtime_evidence import array_items
import numpy as np
def run(ident):
 summarize(ident)
 result=json.loads((S/'output'/(ident+'_RESULT.json')).read_text());audit=json.loads((S/'reports'/(ident+'_AUDIT.json')).read_text());ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());native=S/'source/results'/ident/'summary.json';summary=json.loads(native.read_text()) if native.exists() else {}
 requests=ev['native_requests'];task={r['request_id']:r for r in requests if r['stage']=='TASK'}
 activated=[r for r in task.values() if r['outcome']=='ACTIVATED'];decisions=summary.get('decisions',[])
 path=S/'source/results'/ident/'runtime_artifacts.json.gz';receipts=list(array_items(path,'command_receipts')) if path.exists() else []
 activation_owners={q.get('conservative_activation_ns',q.get('activation_ns')):rid for rid,q in task.items() if q['outcome']=='ACTIVATED'}
 intervals=[]
 for r in summary.get('learning_records',[]):
  index=r.get('decision_index')
  if index is not None and index<len(decisions) and r.get('selected_plan_activated'):
   intervals.append((r['start_time_s'],r['end_time_s'],decisions[index].get('timing_request_id')))
 receipt_owners={}
 for receipt in receipts:
  owner=receipt.get('plan_request_id',receipt.get('request_id'));authority='explicit original receipt owner'
  if owner not in task:
   owner=activation_owners.get(receipt.get('conservative_activation_ns'));authority='exact original activation stamp'
  if owner not in task and receipt.get('start_physics_s') is not None:
   matches=[rid for begin,end,rid in intervals if begin<=receipt['start_physics_s']<end]
   if len(matches)==1:owner=matches[0];authority='original native half-open active segment and decision request ID'
  if owner in task and receipt.get('applied') and receipt.get('native_steps',0)>0:receipt_owners.setdefault(owner,[]).append(dict(receipt_index=receipt.get('receipt_index'),native_steps=receipt['native_steps'],authority=authority))
 meaningful=[]
 for d in decisions:
  rid=d.get('timing_request_id');q=task.get(rid);delta=d.get('executed_action_delta_q_rad',[0.,0.])
  if not d.get('plan_activated') or d.get('phase') not in ('OUTBOUND','RETURN') or not np.any(np.abs(delta)>1e-12):continue
  physical=receipt_owners.get(rid,[])
  meaningful.append(dict(request_id=rid,phase=d['phase'],delta_q_rad=delta,activation_age_ms=None if q is None else q.get('activation_age_ms'),strict_fresh=q is not None and q.get('activation_age_ms',float('inf'))<55,receipt_native_steps=sum(r['native_steps'] for r in physical),physical_receipts=len(physical),receipts=physical))
 active_windows=[(r['worker_start_ns'],r['compute_finish_ns']) for r in requests if r.get('asynchronous') and 'worker_start_ns' in r and 'compute_finish_ns' in r]
 co=S/'output'/(ident+'_COMMISSIONING_OWNER.json')
 co_data=json.loads(co.read_text()) if co.exists() else {}
 active_windows += [(r['worker_start_ns'],r['estimate_ready_ns']) for r in co_data.get('rows',[]) if 'worker_start_ns' in r and 'estimate_ready_ns' in r]
 services=ev['rows']['fast'];groups={}
 for condition in ('planner_active','planner_idle'):
  rows=[r for r in services if any(a<=r['service_start_ns']<b for a,b in active_windows)==(condition=='planner_active')]
  durations=[(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in rows if r['service_finish_ns'] is not None]
  groups[condition]=dict(services=len(rows),service_compute_ms=quantile(durations),skipped_periods=sum(r['skipped_periods'] for r in rows),services_with_command_applied=sum(r.get('receipt_index') is not None for r in rows))
 metric=result.get('metric',{});physical=metric.get('physical_audit',{});original=physical.get('unchanged_evaluator',{});complete=summary.get('status')=='COMPLETE';strict_age=bool(activated) and all(r['activation_age_ms']<55 for r in activated)
 reasons=[]
 if not metric.get('matched_timing_valid',False):reasons.append('ORIGINAL_R2_TIMING_FAIL')
 if not metric.get('valid',False):reasons.append('ORIGINAL_COMPLETE_VALIDITY_FAIL')
 if not strict_age:reasons.append('STRICT_ACTIVATION_AGE_NOT_LT55')
 if audit['skipped_periods'] or original.get('realtime_execution_validity',{}).get('status')!='PASS':reasons.append('FAST_SERVICE_OR_NATIVE_REALTIME_FAIL')
 if not any(r['receipt_native_steps']>0 for r in meaningful):reasons.append('MEANINGFUL_B_EXECUTION_NOT_PROVEN')
 if any('HOST_LATENCY' in str(r) for r in summary.get('fallback_events',[])):reasons.append('HOST_LATENCY_FALLBACK')
 out=dict(id=ident,revision=result['inputs']['revision'],series=result['inputs'].get('host_series','development_smoke'),worker_status=result['status'],error=result.get('error'),complete_out_hold_return=complete,original_complete_VALID=bool(metric.get('valid',False)),original_r2_valid=bool(metric.get('matched_timing_valid',False)),original_physical_task_result=original.get('physical_task_result'),original_realtime_result=original.get('realtime_execution_validity'),original_abort_reason=summary.get('abort_reason'),phase_durations=metric.get('phase_durations'),meaningful_plans=meaningful,physically_executed_meaningful_count=sum(r['receipt_native_steps']>0 for r in meaningful),strict_fresh_meaningful_count=sum(r['strict_fresh'] and r['receipt_native_steps']>0 for r in meaningful),task_requests=len(task),task_activations=len(activated),activation_age_ms=quantile([r['activation_age_ms'] for r in activated]),strict55_miss_rate=sum(r['activation_age_ms']>=55 for r in activated)/len(activated) if activated else None,fast_idle_active=groups,service_gap_ms=audit['service_gap_ms'],service_compute_ms=audit['service_compute_ms'],miss_rate=audit['miss_rate'],planner_compute_ms=audit['planner_compute_ms'],planner_queue_ms=audit['planner_queue_ms'],qualified=not reasons,qualification_reasons=reasons)
 (S/'reports'/(ident+'_QUALIFICATION.json')).write_text(json.dumps(out,indent=2)+'\n')
 return out
def main():
 rows=[]
 for p in sorted((S/'output').glob('*_RESULT.json')):
  r=json.loads(p.read_text())
  if r.get('inputs',{}).get('execution_mode')=='REALTIME_CHARACTERIZATION':rows.append(run(r['id']))
 groups={}
 for key in set(r['revision']+'/'+r['series'] for r in rows):
  rs=[r for r in rows if r['revision']+'/'+r['series']==key]
  groups[key]=dict(attempts=len(rs),complete=sum(r['complete_out_hold_return'] for r in rs),r2_valid=sum(r['original_r2_valid'] for r in rs),qualified=sum(r['qualified'] for r in rs),meaningful=sum(r['physically_executed_meaningful_count'] for r in rs),fresh_meaningful=sum(r['strict_fresh_meaningful_count'] for r in rs))
 out=dict(status='B_HOST_QUALIFIED' if sum(r['qualified'] for r in rows if r['series']=='cold')>=4 and sum(r['qualified'] for r in rows if r['series']=='same_interpreter')>=4 else 'NOT_QUALIFIED',groups=groups,rows=rows,qualification_contract=dict(bridge_ms=40,strict_activation_age_ms='<55',generic_expiry_ms=100,fast_period_ms=5,original_evaluator_unchanged=True,original_r2_required=True),M2='NOT_RUN_UNLESS_B_HOST_QUALIFIED_AND_REMAINING_5400S')
 (S/'reports/HOST_QUALIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],groups=groups)),flush=True)
if __name__=='__main__':main()
