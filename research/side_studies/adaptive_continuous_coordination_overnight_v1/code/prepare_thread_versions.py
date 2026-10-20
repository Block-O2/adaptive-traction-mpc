from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ['capture_states.py','certified_snapshot_v2.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 save(STUDY/'reports/WORKER_CONFIGURATION_CORRECTION.json',dict(frozen_original_planner_process_worker=True,previous_C1_process_enable_status='NO_OP_ALREADY_ENABLED_NOT_AN_ENGINEERING_REPAIR',E3_process_cache='Not transported to process worker; zero hits, preserved',actual_public_engineering_versions=['C1_THREAD: existing thread worker, same lifecycle','C2_THREAD: C1_THREAD + structured 21point mechanics batch'],max_two_public_repairs=True))
 for version,pub,base in [('E3T','C1_THREAD',60),('E3T_C2','C2_THREAD',70)]:
  save(STUDY/'versions'/(version+'_CONTRACT.json'),dict(version=version,public_version=pub,optimization='existing thread lifecycle enables same-request exact snapshot reuse; C2 adds complete21point mechanics batch',classification='EXACT_EQUIVALENT_PENDING_GATE',algorithm_sources=sources,all_live_activation_validation_retained=True,public_engineering_fix=1 if pub=='C1_THREAD' else 2))
  for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
   enqueue(f'{base+offset:03d}_{version}_science_{label}',method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version=version,public_version=pub,execution_mode='SCIENTIFIC_SIMULATION',capture_states=method=='M2',certificate_version='v2',algorithm_sources=sources)
 print('TWO_GROUNDED_PUBLIC_REPAIR_REGRESSIONS_QUEUED')
if __name__=='__main__':main()
