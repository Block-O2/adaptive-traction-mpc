from task_bootstrap import *
from causal_timing_report import quantile
def main():
 ids=sys.argv[1:];out=[]
 for id in ids:
  p=STUDY/'output'/(id+'_ASYNC_NATIVE_WORKER.json')
  if not p.exists():continue
  rows=json.loads(p.read_text())['rows'];s=json.loads((STUDY/'output'/(id+'_SELECTIONS.json')).read_text())['rows'];names=set(k for r in rows for k in r['profile'])
  result=dict(id=id,worker_full_ms=quantile([r['worker_elapsed_ms'] for r in rows]),worker_source_age_ms=quantile([r['source_age_at_worker_return_ms'] for r in rows]),nested_profile={k:quantile([r['profile'][k]['sum_ms'] for r in rows if k in r['profile']]) for k in sorted(names)},selection_stages_ms={k:quantile([r[k]*1000 for r in s if k in r]) for k in ('context_s','generation_s','validation_and_S_s','Q_inference_s','submission_s','end_to_end_s','fast_coordinator_s')},admission=[r['admission'] for r in rows],physically_activated=[r['selected_plan_activated'] for r in rows],interpretation='Profile scopes overlap and cannot be summed; learned proposal activation is separately checked against applied_plan and late_discard.')
  out.append(result);print(json.dumps(result))
 save(STUDY/'reports/ASYNC_TIMING_DETAILS.json',dict(rows=out))
if __name__=='__main__':main()
