from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 for version in ['E3T','E3T_C2']:assert json.loads((STUDY/'versions'/(version+'_FULL_NATIVE_EQUIVALENCE_GATE.json')).read_text())['status']=='PASS'
 sources=frozen_sources();index=170
 for pair,order in enumerate([['C1_THREAD','C2_THREAD'],['C2_THREAD','C1_THREAD'],['C1_THREAD','C2_THREAD'],['C2_THREAD','C1_THREAD']]):
  for public in order:
   enqueue(f'{index:03d}_public_cold_pair{pair+1}_{public}',method='M0',original=True,seed=2026100741+pair,timing_version='E3T_C2A',public_version=public,execution_mode='REALTIME_CHARACTERIZATION',algorithm_sources=sources,cold_start=True,public_repair_pair=pair+1,public_repair_limit='Only the two already science-equivalent C1_THREAD and C2_THREAD versions; no third scheduling fix.')
   index+=1
 save(STUDY/'versions/PUBLIC_REPAIR_REPEAT_PROTOCOL.json',dict(pairs=4,versions=['C1_THREAD existing native thread option','C2_THREAD same option + exact21point mechanics batch'],existing_process_enable_C1='NOOP_ALREADY_ENABLED; excluded from meaningful repair count',meaningful_public_repair_count=2,no_third_public_scheduling_fix=True,actual_wall=True,algorithm_sources=sources))
 print('TWO_EXISTING_PUBLIC_REPAIRS_FOUR_COLD_PAIRS_QUEUED')
if __name__=='__main__':main()
