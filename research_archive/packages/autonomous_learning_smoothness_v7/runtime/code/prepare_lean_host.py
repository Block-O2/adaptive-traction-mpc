from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 assert json.loads((STUDY/'versions/E6_LEAN_FULL_NATIVE_EQUIVALENCE_GATE.json').read_text())['status']=='PASS'
 jobs=[json.loads(x) for x in (STUDY/'NONPHYSICS_JOBS.jsonl').read_text().splitlines()];assert any(j['id']=='O10r1' and j['returncode']==0 for j in jobs),'QUIET_HOST_WAITS_FOR_OFFLINE_SWEEP_JOIN'
 sources=frozen_sources()
 for f in ('lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 rows=[];index=240
 for pair in range(4):
  for method in (('M0','M2') if pair%2==0 else ('M2','M0')):
   id=f'{index:03d}_E6_LEAN_cold_pair{pair+1}_'+('B' if method=='M0' else 'accelerated');seed=2026100801+pair
   rows.append(dict(id=id,pair=pair+1,method=method,seed=seed))
   enqueue(id,method=method,original=method=='M0',seed=seed,timing_version='E5_LEAN_v1',execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=method=='M2',research_profile=False,activation_reserve_ms=36.,delay_replay=False,algorithm_sources=sources,host_series='E6_lean_quiet_cold',scientific_version='frozen-B-native-Q-v1')
   index+=1
 save(STUDY/'versions/E6_LEAN_HOST_PROTOCOL.json',dict(status='PREREGISTERED',rows=rows,attempts=8,paired_cold4=True,background_study_work='wide offline certificate sweep has joined before dispatch',source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),full_native_SCI_gate='PASS',public_B_scheduling_versions_unchanged=True,main_and_child_research_profile_removed=True,retained='native actual request/activation/receipts/physical traces/timing/physics/API counters/import firewall'))
 print('E6_LEAN_QUIET_FOUR_COLD_PAIRS_QUEUED')
if __name__=='__main__':main()
