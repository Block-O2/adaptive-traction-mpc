"""Observed fault disposition, receipts and current native proof handling."""
from pathlib import Path
import sys,json,subprocess,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');W=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
def read(path,default):return json.loads(path.read_text()) if path.exists() else default
def main():
 ident=sys.argv[1];result=read(S/'output'/(ident+'_RESULT.json'),{});cfg=result['inputs'];fault=cfg['fault_injection'];fid=fault['request_id']
 injection=read(S/'output'/(ident+'_FAULT_INJECTION.json'),{});multi=read(S/'output'/(ident+'_MULTIRATE.json'),{});requests=multi.get('native_requests',[])
 request=next((r for r in requests if r['request_id']==fid),None)
 artifact=S/'source/results'/ident/'runtime_artifacts.json.gz';summary=read(S/'source/results'/ident/'summary.json',{})
 pending=None;receipts=[];bridges=[];fallback=[]
 if artifact.exists():
  p=subprocess.run([sys.executable,str(W/'pending_feedback_audit.py'),ident],capture_output=True,text=True)
  if p.returncode==0:pending=read(S/'reports'/(ident+'_PENDING_FEEDBACK.json'),{});pending=next((r for r in pending['rows'] if r['request_id']==fid),None)
  receipts=list(array_items(artifact,'command_receipts'))
  bridges=[r for r in array_items(artifact,'future_handoff_bridges') if r.get('request_id')==fid]
  fallback=list(array_items(artifact,'safe_fallback_events'))
 admission=read(S/'output'/(ident+'_ADMISSION_CERTIFICATES.json'),{}).get('rows',[])
 decision=next((d for d in summary.get('decisions',[]) if d.get('timing_request_id')==fid),None)
 expirywrites=[r['receipt_index'] for r in receipts if r.get('apply_ns') is not None and r['apply_ns']-r['source_capture_ns']>100_000_000]
 error=result.get('error');checks={'fault_dispatch_observed':any(r.get('event','').endswith('FAULT_DISPATCH') for r in injection.get('rows',[])), 'no_expired_actual_writes':not expirywrites}
 checks['request_stage_and_id_bound']=request is not None and request['stage']==fault['stage']
 if fault['kind']=='expired_result':checks['expired_proposal_not_activated']=request is not None and request.get('outcome')!='ACTIVATED' and (decision is None or not decision.get('plan_activated'))
 if fault['kind']=='explicit_native_rejection':checks['rejected_proposal_not_activated']=request is None or (request.get('outcome')!='ACTIVATED' and (decision is None or not decision.get('plan_activated')))
 relevant=[]
 if request is not None:
  begin=request.get('result_collected_ns') or request['request_ns'];end=request.get('disposition_ns',request.get('activation_ns')) or begin
  relevant=[r for r in admission if r.get('event')=='CURRENT_MODEL_CHECK' and r.get('start_ns',0)>=begin and r.get('finish_ns',0)<=end]
 if fault['kind']=='model_version_mismatch':
  checks['corrupted_proof_identity_not_reused']=bool(relevant) and all(r.get('native_recompute') and not r.get('exact_all_input_match') for r in relevant)
 nextreq=next((r for r in requests if r['request_id']>fid),None)
 prior=[d for d in summary.get('decisions',[]) if d.get('plan_activated') and d.get('actual_activation_monotonic_ns',0) is not None and request is not None and d.get('actual_activation_monotonic_ns',0)<request['request_ns']]
 horizon=None
 if prior and request is not None:
  old=prior[-1];chosen=next((x for x in old.get('evaluations',[]) if x.get('label')==old.get('executed_label')),None)
  duration=(old.get('rolling_composite') or {}).get('total_duration_s')
  if duration is None and chosen:duration=chosen.get('schedule',{}).get('duration_s')
  start=old.get('actual_schedule_start_physics_s')
  if start is not None and duration is not None:horizon=dict(primary_request_id=old['timing_request_id'],original_start_s=start,original_duration_s=duration,original_endpoint_s=start+duration,remaining_at_source_sample_s=start+duration-request['source_sample_time_s'],interpretation='Original primary horizon only; admitted handoff bridge / safe escape below is separate original authority. A negative primary remainder is not a claim that an unbounded hold was authorized.')
 out=dict(id=ident,unix=time.time(),diagnostic_checks=checks,status='OBSERVED_CHECKS_PASS' if all(checks.values()) else 'INCOMPLETE_OR_FAILED_DIAGNOSTIC',worker_status=result['status'],worker_error=error,fault=fault,fault_evidence=injection,original_request=request,pending_feedback=pending,following_original_request=nextreq,current_state_checks_in_disposition=relevant,expired_actual_write_ids=expirywrites,task_complete=bool(summary.get('task',{}).get('phase_transitions') and summary['task']['phase_transitions'][-1].get('to')=='COMPLETE'),abort_reason=summary.get('abort_reason'),actual_write_count=sum(r.get('apply_ns') is not None for r in receipts),actual_native_steps=sum(r.get('native_steps',0) for r in receipts),known_invalid_action_execution_permitted=False,original_failure_status_preserved=True,executable_reference_horizon='See original request fallback_physics_s, pending physical owners, original reference records and following request. No new guaranteed continuation is asserted.',scope='Proof identity mismatch tests stale certificate handling against unchanged live model; it is not a live human-model publication injection.')
 out.update(original_primary_horizon=horizon,original_handoff_bridges=bridges,original_safe_fallback_events=fallback)
 (S/'reports'/(ident+'_FAULT_REVIEW.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('id','status','worker_status','worker_error','diagnostic_checks','pending_feedback','actual_native_steps','task_complete','abort_reason')}))
if __name__=='__main__':main()
