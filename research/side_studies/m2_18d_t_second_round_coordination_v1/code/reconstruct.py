"""Read sealed prior traces; write only this new package. No models or physics."""
from pathlib import Path
import json,sys,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1')
O=S.parent/'b_fast_runtime_completion_v1'
sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 allrows=[]
 for prefix,kind in [('082_','nominal'),('088_','nominal'),('095_','nominal'),('099_','nominal'),('103_','nominal_tail'),('079_','legal_deviation'),('101_','legal_deviation')]:
  path=next((O/'queue').glob(prefix+'*.json'));ident=path.stem
  sp=O/'source/results'/ident/'summary.json';mp=O/'output'/(ident+'_MULTIRATE.json');ap=sp.parent/'runtime_artifacts.json.gz'
  summary=json.loads(sp.read_text());m=json.loads(mp.read_text());trans=summary['task']['phase_transitions']
  entry=next(r for r in trans if r['to']=='HOLD');exit=next(r for r in trans if r['from']=='HOLD')
  hd=[d for d in summary['decisions'] if d.get('phase')=='HOLD'];rd=next(d for d in summary['decisions'] if d.get('phase')=='RETURN')
  request=next(r for r in m['native_requests'] if r['request_id']==rd['timing_request_id'])
  receipts=list(array_items(ap,'command_receipts'))
  activation=min((r for r in receipts if r.get('apply_ns') and r['apply_ns']>=request['validation_finish_ns'] and r.get('applied')),key=lambda r:r['apply_ns'])
  first=None
  for r in array_items(ap,'native_states_evaluation_only'):
   if r.get('command_id')==activation['receipt_index']:first=r;break
  events=[]
  def ev(name,physical,host,owner,dependency,prepare,authority,**extra):
   events.append(dict(event=name,physical_time_s=physical,host_ns=host,owner=owner,current_dependency=dependency,preparation_class=prepare,time_authority=authority,**extra))
  ev('HOLD_PHASE_RECORDED',entry['time_s'],None,'original sensor/reference guarded task clock','actual sensor state and completed OUTBOUND reference','C','summary transition; host event absent')
  for index,d in enumerate(hd):
   req=next(r for r in m['native_requests'] if r['request_id']==d['timing_request_id'])
   sch=d['evaluations'][0]['schedule'];start=d['actual_schedule_start_physics_s']
   ev('HOLD_SEGMENT_'+str(index+1)+'_ACTUAL_REFERENCE_START',start,req['activation_ns'],'original TASK and receipt-owned reference governor','full original admission','C','decision physical start; lifecycle activation is return-of-write, distinct from receipt actual-write',request_id=req['request_id'],source_capture_ns=req['sensor_capture_ns'],request_ns=req['request_ns'],duration_s=sch['duration_s'])
   candidates=[r for r in receipts if r.get('apply_ns') and r.get('reference_progress',{}).get('selected_progress_s',-1)>=sch['duration_s']-1e-12 and r.get('start_physics_s',-1)>=start and r.get('start_physics_s',1e99)<start+sch['duration_s']+.1]
   # Select first genuinely committed endpoint, not nominal elapsed extrapolation.
   endpoint=min(candidates,key=lambda r:r['apply_ns']) if candidates else None
   ev('HOLD_SEGMENT_'+str(index+1)+'_ENDPOINT_RECEIPT',None if endpoint is None else endpoint['start_physics_s'],None if endpoint is None else endpoint['apply_ns'],'original committed reference receipt','actual complete progress receipt, terminal q/dq/ddq','C','recorded receipt reference_progress' if endpoint else 'unavailable in this trace',receipt_index=None if endpoint is None else endpoint['receipt_index'],nominal_endpoint_physics_s=start+sch['duration_s'])
  ev('SHARED_1S_MINIMUM_GRID_THRESHOLD',entry['time_s']+1.,None,'SACExpertEnv.transition_allowed','previous phase elapsed >=1s; actual invocation separately instrumented','C','derived threshold only; not claimed observed invocation')
  hand=O/'output'/(ident+'_HOLD_HANDOFF_ATTRIBUTION.json')
  if hand.exists():
   h=json.loads(hand.read_text())['rows'];sensor=next(r for r in h if r['event']=='ORIGINAL_SENSOR_TASK_CLOCK' and r['before_phase']=='HOLD' and r['proposed_phase']=='RETURN')
   ev('FIRST_OBSERVED_VALID_0_5S_DWELL_PROPOSAL',sensor['physical_time_s'],sensor['host_ns'],'original SensorSupportedTaskClock','consecutive actual valid captured samples','C','original instrumented invocation',source_sample_s=sensor['sample_time_s'])
   safe=next(r for r in reversed(h) if r['event']=='ORIGINAL_REFERENCE_SAFE_TASK_TRANSITION' and r['before_phase']=='HOLD' and r['result_phase']=='RETURN')
   ev('LEGAL_GUARDED_RETURN_PHASE',exit['time_s'],safe['host_ns'],'reference_safe_task_transition','actual completion, terminal box, stationary reference, shared minimum, sensor dwell','C','recorded original call',before_phase_elapsed_s=safe['before_phase_elapsed_s'])
  else:
   ev('FIRST_OBSERVED_VALID_0_5S_DWELL_PROPOSAL',None,None,'original SensorSupportedTaskClock','actual captured samples','C','per-call dwell event not saved; do not invent it')
   ev('LEGAL_GUARDED_RETURN_PHASE',exit['time_s'],None,'reference_safe_task_transition','actual reference completion and minimum','C','summary transition; actual host call not saved')
  phases=[('RETURN_REQUEST','request_ns','C'),('SNAPSHOT_COMPLETE','snapshot_finish_ns','B'),('ENQUEUED','enqueue_ns','B'),('WORKER_START','worker_start_ns','B'),('PLANNER_READY','compute_finish_ns','B'),('COLLECTED','result_collected_ns','B'),('CURRENT_ADMISSION_START','validation_start_ns','C'),('CURRENT_ADMISSION_AND_CONSTRUCTION_DONE','validation_finish_ns','C'),('ACTUAL_ACTUATOR_WRITE',None,'C'),('LIFECYCLE_ACTIVATION_RETURN','activation_ns','C')]
  for name,key,cat in phases:
   host=activation['apply_ns'] if key is None else request.get(key)
   ev(name,activation['start_physics_s'] if key is None else (request['source_sample_time_s'] if key=='request_ns' else None),host,'TASK worker' if name in ('WORKER_START','PLANNER_READY') else 'single live plant owner','exact request state/model/reference' if cat=='B' else 'current legal boundary/current admission or actual command',cat,'actual request timestamp' if key else 'actual receipt apply_ns',request_id=request['request_id'],source_capture_ns=request['sensor_capture_ns'],reference_version=activation.get('reference_version'))
  ev('FIRST_RETURN_COMMAND_OWNED_NATIVE_STEP',None if first is None else first['physical_interval_start_s'],None if first is None else first['native_grid_start_ns'],'single live plant; actual RETURN command receipt','actual written command must own this grid interval','C','recorded command ownership',receipt_index=activation['receipt_index'],native_step_index=None if first is None else first['native_step_index'])
  keys=['sensor_capture_ns','request_ns','snapshot_finish_ns','enqueue_ns','worker_start_ns','compute_finish_ns','result_collected_ns','validation_start_ns','validation_finish_ns']
  nodes=[(key,request[key]) for key in keys]+[('receipt_apply_ns',activation['apply_ns']),('lifecycle_activation_ns',request['activation_ns'])]
  intervals=[dict(start_event=a,end_event=b,start_ns=ta,end_ns=tb,duration_ms=(tb-ta)/1e6) for (a,ta),(b,tb) in zip(nodes,nodes[1:])]
  assert all(r['duration_ms']>=0 for r in intervals)
  hold=exit['time_s']-entry['time_s'];nominal_last=hd[-1]['actual_schedule_start_physics_s']+hd[-1]['evaluations'][0]['schedule']['duration_s']
  row=dict(id=ident,kind=kind,HOLD_s=hold,RETURN_source_equals_scored_HOLD_exit=request['source_sample_time_s']==exit['time_s'],scored_hold_exit_precedes_RETURN_request=True,HOLD_start_to_first_reference_ms=(hd[0]['actual_schedule_start_physics_s']-entry['time_s'])*1000,second_HOLD_start_minus_first_nominal_endpoint_ms=(hd[-1]['actual_schedule_start_physics_s']-hd[0]['actual_schedule_start_physics_s']-.5)*1000,last_reference_nominal_endpoint_minus_shared_1s_ms=(nominal_last-entry['time_s']-1)*1000,scored_exit_minus_last_nominal_endpoint_ms=(exit['time_s']-nominal_last)*1000,RETURN_request_to_receipt_write_ms=(activation['apply_ns']-request['request_ns'])/1e6,nonoverlapping_RETURN_intervals=intervals,events=events,source_files={str(p):sha(p) for p in (sp,mp,path)},physics_steps=0,model_API_calls=0)
  allrows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('events','nonoverlapping_RETURN_intervals','source_files')}),flush=True)
 out=dict(status='COMPLETE_WITH_EXPLICIT_HISTORICAL_TIMESTAMP_GAPS',rows=allrows,old_artifacts_read_only=True,physics_steps=0,model_API_calls=0,interpretation='RETURN work follows the already recorded HOLD exit; it cannot cause the scored HOLD excess. Two sequential .5s HOLD references and their request/admission/receipt gaps dominate. Existing traces do not record every dwell/minimum/command-construction subevent; new instrumentation is required for those exact events.',unix=time.time())
 (S/'reports/HOLD_CRITICAL_PATH_EXISTING.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
