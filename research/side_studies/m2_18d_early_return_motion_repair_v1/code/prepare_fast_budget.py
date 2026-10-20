"""Registered compute-performance tradeoff, never an equivalence promotion."""
from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 groups=[('nominal1',{},2026100731),('nominal2',{},2026100732),('deviationA',{'OUTBOUND':[[.15,-.2,.25]]},2026100733),('deviationB',{'OUTBOUND':[[-.2,.15,.1]],'RETURN':[[.1,-.1,.2]]},2026100734)]
 save(STUDY/'versions/FAST_BUDGET_v1_CONTRACT.json',dict(classification='COMPUTE_PERFORMANCE_TRADEOFF_NOT_EXACT_EQUIVALENT',candidate_budgets=[6,4,2],candidate_generation='Original frozen coherent pool, original dedup/mask/RNG, truncate first n; this changes candidate authority available for ranking and can change chosen plans.',groups=groups,weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),no_retraining=True,no_new_objective=True,safety='All finally selected candidates retain unchanged native full certificate/current-model/fallback/activation checks.',timing='SCI full-validation shadow plus separately measured Q-first deployable prefix; fresh host characterization separately',group_interpretation='exposed nominal Human with independent search seeds and preregistered legal prefixes; no new-Human claim',algorithm_sources=sources))
 index=180
 for group,prefix,seed in groups:
  for budget in [0,6,4,2]:
   method='M0' if budget==0 else 'M2';id=f'{index:03d}_FAST_BUDGET_{group}_'+('B' if budget==0 else str(budget))
   enqueue(id,method=method,original=method=='M0' and not prefix,prefix=prefix,seed=seed,timing_version='E5_HOST_v1',public_version=None,execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=method=='M2',candidate_budget=budget or 6,scientific_version='FAST_BUDGET_v1' if budget in (4,2) else 'frozen-B-native-Q-v1',algorithm_sources=sources,tradeoff_group=group,tradeoff_classification='COMPUTE_PERFORMANCE_TRADEOFF' if budget in (4,2) else 'registered reference')
   index+=1
 print('FOUR_GROUPS_16_PHYSICAL_EPISODES_REGISTERED_FAST_BUDGET')
if __name__=='__main__':main()
