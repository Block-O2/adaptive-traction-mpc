from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 version='E5_NATIVE_WORKER';save(STUDY/'versions'/(version+'_CONTRACT.json'),dict(version=version,optimization='M2 current-boundary computation inside existing native prewarmed TASK process; main only serializes current causal hints',scientific_version='EXACT_EQUIVALENT_PENDING_GATE',authority='same original native request, snapshot by value, one outstanding worker, same native fallback/activation/current-model validation/expiry',no_future_state=True,no_new_native_decision_boundary=True,no_public_B_scheduling_repair=True,public_B_repairs_still_at_most_two=True,prewarm='Q parameters/imports only, no Human/plant state',pipeline_batch='previously equivalent C2 mechanics math',algorithm_sources=sources,host_gate_pending_registered_downstream_reserve=True))
 for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  enqueue(f'{100+offset:03d}_{version}_science_{label}',method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version=version,public_version=None,execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=True,algorithm_sources=sources)
 print('EXISTING_NATIVE_WORKER_THREE_EQUIVALENCE_REGRESSIONS_QUEUED')
if __name__=='__main__':main()
