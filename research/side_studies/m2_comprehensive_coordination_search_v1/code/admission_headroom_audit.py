"""Separate conservative research admission from original native deadlines."""
from task_bootstrap import *
import numpy as np
from causal_timing_report import quantile

def main():
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[]
 for run in host['rows']:
  id=run['id'];worker=STUDY/'output'/(id+'_ASYNC_NATIVE_WORKER.json');sels=STUDY/'output'/(id+'_SELECTIONS.json')
  if not worker.exists() or not sels.exists():continue
  proposals={r['request_id']:r for r in json.loads(sels.read_text()).get('rows',[])};timelines={r['request_id']:r for r in run['full_timelines']}
  for record in json.loads(worker.read_text())['rows']:
   selection=proposals.get(record['request_id'])
   if selection is None:continue
   phase=selection['context']['phase'];count=selection['count_before'][phase];plan=np.asarray(selection['candidate_records'][selection['selected_index']]['plan']);action=plan[('OUTBOUND','RETURN').index(phase),count] if count<5 else np.zeros(3);q=timelines.get(record['request_id'],{});admission=record['admission'];age=q.get('activation_age_ms');actual_age=record['source_age_at_worker_return_ms']
   rows.append(dict(id=id,request_id=record['request_id'],phase=phase,count_before=count,selected_source=selection['selected_source'],prospective_selected_current_K3=action.tolist(),prospective_nonzero_current_K3=bool(np.any(np.abs(action)>1e-12)),remaining_future_graph_nonzero=bool(np.any(np.abs(plan)>1e-12)),current_phase_slots_exhausted=count>=5,source_age_before_guard_ms=admission.get('source_age_before_admission_ms'),registered_worker_age_guard_ms=admission.get('worker_return_deadline_age_ms'),registered_downstream_reserve_ms=admission.get('activation_reserve_ms'),late_discard=bool(selection.get('late_discard')),source_age_after_carry_recertification_ms=actual_age,carry_recertification_and_recording_ms=actual_age-admission['source_age_before_admission_ms'],actual_outcome=q.get('outcome'),actual_activation_age_ms=age,observed_return_to_actual_activation_ms=None if age is None else age-actual_age,strict_age_eligible=age is not None and age<55,alternative_learning_activation_not_observed=True))
 out=dict(status='READ_ONLY_ADMISSION_ATTRIBUTION',rows=rows,selection_records=len(rows),late_discard_count=sum(r['late_discard'] for r in rows),prospective_nonzero_current_actions=sum(r['prospective_nonzero_current_K3'] for r in rows),strict_under55_activations=[r for r in rows if r['strict_age_eligible']],pre_guard_source_age_ms=quantile([r['source_age_before_guard_ms'] for r in rows]),carry_recertification_and_recording_ms=quantile([r['carry_recertification_and_recording_ms'] for r in rows]),observed_return_to_actual_activation_ms=quantile([r['observed_return_to_actual_activation_ms'] for r in rows if r['observed_return_to_actual_activation_ms'] is not None]),physics_added=0,controls_modified=False,interpretation='19ms=min(40,55-36) is a conservative, preregistered research proposal-return guard, not an extra native evaluator threshold. Real request source age is immutable. A timely zero carry activation proves neither a learning proposal nor the unobserved latency of an alternative learned command. Terminal current-phase count>=5 maps current action to zero, even if Q selects a future-phase graph. Removing recertification duration from a recorded carry timeline is not a valid counterfactual activation proof.')
 save(STUDY/'reports/ADMISSION_HEADROOM_AUDIT.json',out);print(json.dumps({k:out[k] for k in ('status','selection_records','late_discard_count','prospective_nonzero_current_actions','strict_under55_activations','pre_guard_source_age_ms','carry_recertification_and_recording_ms','observed_return_to_actual_activation_ms')}))
if __name__=='__main__':main()
