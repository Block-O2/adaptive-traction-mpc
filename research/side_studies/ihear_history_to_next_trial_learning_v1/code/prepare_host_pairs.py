from prepare_tasks import *
from prepare_next_versions import frozen_sources
from freeze_version import freeze
def main():
 assert json.loads((STUDY/'versions/E5_NATIVE_WORKER_FULL_NATIVE_EQUIVALENCE_GATE.json').read_text())['status']=='PASS'
 reserve=json.loads((STUDY/'versions/E5_NATIVE_WORKER_DOWNSTREAM_RESERVE.json').read_text());assert reserve['activation_reserve_ms']==36
 sources=frozen_sources()
 for f in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 freeze('E5_HOST_v1')
 save(STUDY/'versions/E5_HOST_v1_CONTRACT.json',dict(parent='E5_NATIVE_WORKER',scientific_full_native_gate='PASS',only_following_source_change='AsyncNativeInterface.method metadata used solely by all-outcome exceptional-result saver; no control computation changed',admission_reserve=reserve,host_mode='whole-session actual wall physics, original request capture, no epoch freezing',cold_pair_order=[['B','baseline','accelerated'],['accelerated','B','baseline'],['baseline','accelerated','B'],['B','accelerated','baseline']],algorithm_sources=sources))
 index=110
 for pair,order in enumerate([['B','baseline','accelerated'],['accelerated','B','baseline'],['baseline','accelerated','B'],['B','accelerated','baseline']]):
  for label in order:
   method='M0' if label=='B' else 'M2';version='E5_HOST_v1' if label=='accelerated' else 'T0'
   enqueue(f'{index:03d}_host_cold_pair{pair+1}_{label}',method=method,original=method=='M0',seed=2026100701+pair,timing_version=version,public_version=None,execution_mode='REALTIME_CHARACTERIZATION',delay_replay=label=='baseline',pipeline_batch=label=='accelerated',activation_reserve_ms=reserve['activation_reserve_ms'] if label=='accelerated' else None,algorithm_sources=sources,host_pair_id=pair+1,cold_start=True,qualification_purpose='4 paired original B vs baseline M2 vs accelerated current-boundary native-worker M2')
   index+=1
 print('FOUR_COLD_PAIRS_12_ATTEMPTS_QUEUED')
if __name__=='__main__':main()
