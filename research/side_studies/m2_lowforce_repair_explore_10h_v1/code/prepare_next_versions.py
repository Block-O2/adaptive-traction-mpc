from prepare_tasks import *
def frozen_sources():
 names=['worker.py','optimized_method.py','optimized_e3.py','shared_nominal.py','certified_snapshot.py','q_first_method.py','native_method.py','native_core.py','native_inference.py','interfaces.py','public_worker.py','batched_mechanics.py','study_common.py','profiling_instrumentation.py']
 return {str(STUDY/'code'/f):sha(STUDY/'code'/f) for f in names}
def main():
 assert json.loads((STUDY/'versions/E2r1_EQUIVALENCE_GATE.json').read_text())['status']=='PASS';sources=frozen_sources()
 enqueue('028_E2r1_wall_M2',timing_version='E2r1',execution_mode='REALTIME_CHARACTERIZATION',delay_replay=True,algorithm_sources=sources)
 for version,pub,base in [('E3',None,30),('E2r1_C1','C1',40),('E3_C2','C2',50)]:
  save(STUDY/'versions'/(version+'_CONTRACT.json'),dict(version=version,public_version=pub,optimization='same-request exact-byte duplicate decision reuse' if version=='E3' else ('existing prewarmed spawn-process planner' if pub=='C1' else 'same21point structured mechanics batch with original thresholds and near-threshold scalar fallback'),classification='EXACT_EQUIVALENT_PENDING_GATE',algorithm_sources=sources,scientific_full_validation_shadow=True,all_live_activation_validation_retained=True))
  for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
   enqueue(f'{base+offset:03d}_{version}_science_{label}',method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version=version,public_version=pub,execution_mode='SCIENTIFIC_SIMULATION',algorithm_sources=sources)
 print('E3_C1_C2_EQUIVALENCE_REGRESSIONS_AND_E2_HOST_QUEUED')
if __name__=='__main__':main()
