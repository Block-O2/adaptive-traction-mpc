"""Preregister downstream reserve from existing native host activations."""
from task_bootstrap import *
from analyze_timing import header_requests
import math,numpy as np
def main():
 ids=sys.argv[1:] or ['000_T0_wall_B'];rows=[]
 for id in ids:
  p=STUDY/'source/results'/id/'runtime_artifacts.json.gz'
  if not p.exists():continue
  for q in header_requests(p):
   if q.get('stage')!='TASK' or q.get('outcome')!='ACTIVATED':continue
   finish=q.get('compute_finish_ns');activate=q.get('conservative_activation_ns',q.get('activation_ns'))
   if finish is None or activate is None:continue
   rows.append(dict(id=id,request_id=q['request_id'],worker_finish_to_actual_activation_ms=(activate-finish)/1e6,activation_age_ms=q.get('activation_age_ms'),validation_and_command_construction_ms=q.get('validation_and_command_construction_ms'),worker_to_main_scheduling_ms=q.get('worker_to_main_scheduling_ms')))
 assert rows,'NO_ACTUAL_TASK_ACTIVATIONS_FOR_RESERVE'
 reserve=math.ceil(max(r['worker_finish_to_actual_activation_ms'] for r in rows))+5
 out=dict(status='REGISTERED_FROM_PRIOR_ACTUAL_NATIVE_EXECUTION',source_ids=ids,rows=rows,activation_reserve_ms=reserve,guard_margin_ms=5,worker_return_deadline_age_ms=min(40,55-reserve),bridge_ms=40,evaluator_activation_ms=55,generic_expiry_ms=100,warning='Reserve is an admission guard, not proof of timely activation; fresh complete actual-clock runs must independently qualify.',timestamps='original immutable sensor capture and conservative actual activation',created_unix=time.time())
 save(STUDY/'versions/E5_NATIVE_WORKER_DOWNSTREAM_RESERVE.json',out);print(json.dumps(out))
if __name__=='__main__':main()
