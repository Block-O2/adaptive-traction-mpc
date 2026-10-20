from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 rows=[];sources=frozen_sources()
 for name in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py']:sources[str(STUDY/'code'/name)]=sha(STUDY/'code'/name)
 for offset,(seed,budget) in enumerate([(2026100781,6),(2026100781,4),(2026100781,2),(2026100782,2),(2026100782,4),(2026100782,6)]):
  id=f'{200+offset:03d}_FAST_BUDGET_actual_{budget}_seed{seed}';rows.append(dict(id=id,seed=seed,candidate_budget=budget))
  enqueue(id,seed=seed,timing_version='E5_HOST_FAST_BUDGET_v1',execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=True,candidate_budget=budget,activation_reserve_ms=36.,algorithm_sources=sources,delay_replay=False,classification='COMPUTE_PERFORMANCE_TRADEOFF_NOT_EXACT_EQUIVALENT')
 save(STUDY/'versions/FAST_BUDGET_HOST_PROTOCOL.json',dict(status='PREREGISTERED',rows=rows,changed_only='candidate pool truncation 6/4/2; same frozen Q/current native safety; actual physics wall time',learning_qualification='only complete valid timely actually executed learned action qualifies',engineering_versions_unchanged=True))
 print('FAST_BUDGET_ACTUAL_SIX_ATTEMPTS_QUEUED')
if __name__=='__main__':main()
