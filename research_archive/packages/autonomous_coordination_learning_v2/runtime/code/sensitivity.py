"""Non-actuating timing headroom analysis of original host records."""
from pathlib import Path
import json,sys,collections
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
sys.path.insert(0,str(S/'code'))
from audit import quantile
def main():
 host=json.loads((S/'reports/HOST_QUALIFICATION.json').read_text());rows=[]
 for run in host['rows']:
  ev=json.loads((S/'output'/(run['id']+'_MULTIRATE.json')).read_text())
  for q in ev['native_requests']:
   if q['stage']!='TASK' or q['outcome']!='ACTIVATED':continue
   source=q['sensor_capture_ns'];ready=q.get('compute_finish_ns');age=q['activation_age_ms'];collection=q.get('worker_to_main_scheduling_ms');construction=q.get('validation_and_command_construction_ms')
   rows.append(dict(id=run['id'],series=run['series'],revision=run['revision'],request_id=q['request_id'],age_ms=age,ready_age_ms=None if ready is None else (ready-source)/1e6,ready_headroom_to55_ms=None if ready is None else 55-(ready-source)/1e6,required_age_reduction_to_strict55_ms=max(0.,age-55+1e-6),ideal_zero_result_collection_bound_age_ms=None if collection is None else age-collection,ideal_zero_admission_and_command_bound_age_ms=None if construction is None else age-construction))
 selected=[r for r in rows if r['revision']=='R3' and r['series'] in ('cold','same_interpreter')]
 meaningful={(r['id'],q['request_id']) for r in host['rows'] for q in r['meaningful_plans'] if q['receipt_native_steps']>0}
 selected_meaningful=[r for r in selected if (r['id'],r['request_id']) in meaningful]
 def stats(rs):return dict(n=len(rs),ready_age_ms=quantile([r['ready_age_ms'] for r in rs]),ready_headroom_to55_ms=quantile([r['ready_headroom_to55_ms'] for r in rs]),required_age_reduction_to_strict55_ms=quantile([r['required_age_reduction_to_strict55_ms'] for r in rs]),already_exhausted_at_proposal_ready=sum(r['ready_age_ms']>=55 for r in rs),still_not_lt55_with_ideal_zero_result_collection=sum(r['ideal_zero_result_collection_bound_age_ms']>=55 for r in rs),still_not_lt55_with_ideal_zero_admission_and_command=sum(r['ideal_zero_admission_and_command_bound_age_ms']>=55 for r in rs))
 out=dict(scope='Read-only algebraic timing bounds, no physical replay or altered timestamps. Removing a whole measured interval is optimistic and ignores feedback/state/window changes; no counterfactual PASS claim.',rows=rows,R3_ladder=stats(selected),R3_ladder_meaningful_only=stats(selected_meaningful))
 (S/'reports/TIMING_SENSITIVITY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['R3_ladder']))
if __name__=='__main__':main()
