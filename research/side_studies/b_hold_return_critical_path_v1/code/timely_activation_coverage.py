"""Read-only classification of every TASK activation satisfying source age <55."""
from task_bootstrap import *
import numpy as np
def main():
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[]
 for run in host['rows']:
  folder=STUDY/'source/results'/run['id'];p=folder/'summary.json';summary=json.loads(p.read_text()) if p.exists() else {};selections=STUDY/'output'/(run['id']+'_SELECTIONS.json');sels=json.loads(selections.read_text()).get('rows',[]) if selections.exists() else []
  for q in run['full_timelines']:
   if q['stage']!='TASK' or q.get('outcome')!='ACTIVATED' or q.get('activation_age_ms',100)>=55:continue
   matches=[s for s in sels if s['request_id']==q['request_id']];records=[]
   for record in summary.get('learning_records',[]):
    di=record.get('decision_index');decisions=summary.get('decisions',[])
    if di is None or di>=len(decisions) or decisions[di].get('timing_request_id')!=q['request_id']:continue
    selected=record.get('selected_plan',{});screen=selected.get('execution_screen',{});worker=screen.get('_E5_worker_evidence',{})
    records.append(dict(decision_index=di,decision_phase=decisions[di].get('phase'),record_stage=record.get('stage'),selected_plan_activated=record.get('selected_plan_activated'),start_time_s=record.get('start_time_s'),end_time_s=record.get('end_time_s'),selected_plan_keys=list(selected),execution_screen_keys=list(screen),coordination_residual_v2=screen.get('coordination_residual_v2'),worker_selection_present=worker.get('selection_row') is not None,worker_evidence_present=bool(worker),worker_admission=worker.get('admission'),worker_Q_calls_cumulative=worker.get('Q_calls')))
   details=[]
   for s in matches:
    phase=s['context']['phase'];count=s['count_before'][phase];plan=np.asarray(s['applied_plan']);action=plan[('OUTBOUND','RETURN').index(phase),count] if count<5 else np.zeros(3)
    details.append(dict(phase=phase,count_before=count,late_discard=s.get('late_discard'),applied_current_K3=action.tolist(),nonzero_current_K3=bool(np.any(np.abs(action)>1e-12))))
   rows.append(dict(id=run['id'],method=run['method'],request_id=q['request_id'],activation_age_ms=q['activation_age_ms'],selection_rows=len(matches),selection_details=details,original_native_records=records,does_not_prove_full_task_qualification=True))
 out=dict(status='ALL_STRICT_AGE_ELIGIBLE_TASK_ACTIVATIONS_CATALOGUED',rows=rows,count=len(rows),M2_count=sum(r['method']=='M2' for r in rows),physics_added=0,new_model_predictions=0,interpretation='Source-age eligibility alone is necessary, not sufficient. A native plan with no Q selection is not learned execution. Original records and selected execution metadata are retained for each eligible request; no candidate slot or stage is inferred solely from elapsed time.')
 save(STUDY/'reports/TIMELY_ACTIVATION_COVERAGE.json',out);print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
