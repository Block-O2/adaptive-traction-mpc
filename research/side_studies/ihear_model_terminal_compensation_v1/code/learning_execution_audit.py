"""Separate a learning proposal, carry, native activation, and real command steps."""
from task_bootstrap import *
from stream_runtime_evidence import array_items
from analyze_timing import header_requests
import numpy as np
def audit(id):
 result=json.loads((STUDY/'output'/(id+'_RESULT.json')).read_text());folder=STUDY/'source/results'/id;p=folder/'summary.json';summary=json.loads(p.read_text()) if p.exists() else {};artifact=folder/'runtime_artifacts.json.gz';sels_path=STUDY/'output'/(id+'_SELECTIONS.json');sels=json.loads(sels_path.read_text()).get('rows',[]) if sels_path.exists() else [];requests=summary.get('timing',{}).get('requests',[]) or (header_requests(artifact) if artifact.exists() else []);task={q['request_id']:q for q in requests if q.get('stage')=='TASK'}
 receipts={};activation_owners={q.get('conservative_activation_ns',q.get('activation_ns')):owner for owner,q in task.items() if q.get('outcome')=='ACTIVATED'};intervals=[]
 for record in summary.get('learning_records',[]):
  index=record.get('decision_index');decisions=summary.get('decisions',[])
  if index is not None and index<len(decisions) and record.get('selected_plan_activated'):
   owner=decisions[index].get('timing_request_id')
   if owner in task:intervals.append((float(record['start_time_s']),float(record['end_time_s']),owner))
 if artifact.exists():
  for r in array_items(artifact,'command_receipts'):
   owner=r.get('plan_request_id',r.get('request_id'));authority='explicit_receipt_owner'
   if owner not in task:
    owner=activation_owners.get(r.get('conservative_activation_ns'));authority='exact_original_actual_activation_timestamp_join'
   if owner not in task and r.get('start_physics_s') is not None:
    matches=[o for begin,end,o in intervals if begin<=r['start_physics_s']<end]
    if len(matches)==1:owner=matches[0];authority='original_native_learning_record_half_open_active_segment_and_decision_request_id'
   if owner in task and r.get('applied') and r.get('native_steps',0)>0:receipts.setdefault(owner,[]).append({k:r.get(k) for k in ('receipt_index','source_capture_ns','start_physics_s','end_physics_s','native_steps','request_id','plan_request_id','command_kind','reference_source','sensor_age_at_apply_ms','conservative_activation_ns')}|dict(owner_join_authority=authority))
 rows=[]
 for s in sels:
  owner=s['request_id'];q=task.get(owner,{});phase=s['context']['phase'];count=s['count_before'][phase];used=np.asarray(s['applied_plan']);a=used[('OUTBOUND','RETURN').index(phase),count] if count<5 else np.zeros(3);late=bool(s.get('late_discard'));activated=q.get('outcome')=='ACTIVATED';nsteps=sum(r.get('native_steps',0) for r in receipts.get(owner,[]));nonzero=bool(np.any(np.abs(a)>1e-12));age=q.get('activation_age_ms');timely=age is not None and age<55.
  # This is a conservative positive proof: the original native lifecycle must
  # activate this owner, actual command receipts must integrate native steps,
  # and a nonzero selected graph must have survived the late-admission guard.
  rows.append(dict(request_id=owner,selected_index=s['selected_index'],selected_source=s['selected_source'],applied_current_K3_action=a.tolist(),nonzero_current_action=nonzero,late_discard=late,plan_changed=s.get('plan_changed'),native_outcome=q.get('outcome'),native_reason=q.get('reason'),actual_activation_age_ms=age,actual_command_receipts=receipts.get(owner,[]),actual_native_steps=nsteps,learning_action_execution_proven=bool(not late and nonzero and activated and nsteps>0),timely_learning_execution_proven=bool(not late and nonzero and activated and nsteps>0 and timely),discarded_proposal_never_counted_as_executed=True))
 out=dict(id=id,execution_mode=result['inputs'].get('execution_mode'),full_task_VALID=result.get('metric',{}).get('valid',False),worker_status=result['status'],error=result.get('error'),abort_reason=summary.get('abort_reason'),task_request_count=len(task),selection_count=len(sels),late_discard_count=sum(r['late_discard'] for r in rows),actual_learning_execution_proven_count=sum(r['learning_action_execution_proven'] for r in rows),timely_learning_execution_proven_count=sum(r['timely_learning_execution_proven'] for r in rows),over55_activated=sum(q.get('activation_age_ms',0)>=55 for q in task.values() if q.get('outcome')=='ACTIVATED'),task_activated_count=sum(q.get('outcome')=='ACTIVATED' for q in task.values()),rows=rows,qualification='PASS' if result['inputs'].get('execution_mode')=='REALTIME_CHARACTERIZATION' and result.get('metric',{}).get('valid',False) and any(r['timely_learning_execution_proven'] for r in rows) and all(q.get('activation_age_ms',101)<55 for q in task.values() if q.get('outcome')=='ACTIVATED') else 'NOT_QUALIFIED',activation_evidence='Original lifecycle conservative actual activation + exact raw receipt stamp or native decision/half-open segment owner + nonzero applied K3 + actual integrated native steps; unchanged evaluator requires strictly<55ms; SCI evidence cannot count as actual wall qualification.')
 save(STUDY/'reports'/(id+'_LEARNING_EXECUTION_AUDIT.json'),out);return out
def main():
 for id in sys.argv[1:]:
  r=audit(id);print(json.dumps({k:r[k] for k in ('id','execution_mode','full_task_VALID','task_request_count','selection_count','late_discard_count','actual_learning_execution_proven_count','timely_learning_execution_proven_count','over55_activated','qualification')}))
if __name__=='__main__':main()
