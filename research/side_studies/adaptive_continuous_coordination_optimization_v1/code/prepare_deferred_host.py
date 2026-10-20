from prepare_tasks import *
from prepare_next_versions import frozen_sources
from freeze_version import freeze
def main():
 gate=json.loads((STUDY/'versions/E7_DEFERRED_FULL_NATIVE_EQUIVALENCE_GATE.json').read_text());assert gate['status']=='PASS' and all(r['original_true_physics_record_exact'] and r['all_samples_flushed'] for r in gate['rows'])
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[x for x in events if x['event']=='START'];ended={x['id'] for x in events if x['event']=='END'};assert all(x['id'] in ended for x in starts),'QUIET_HOST_REQUIRES_NO_OTHER_PHYSICS'
 assert len(starts)+8<=160 and time.time()+600<START+8.25*3600
 frozen=freeze('E7_DEFERRED_v1');sources=frozen_sources()
 for f in ('deferred_evaluation.py','lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 rows=[];index=290
 for pair in range(4):
  for method in (('M0','M2') if pair%2==0 else ('M2','M0')):
   id=f'{index:03d}_E7_DEFERRED_cold_pair{pair+1}_'+('B' if method=='M0' else 'accelerated');seed=2026100841+pair;rows.append(dict(id=id,method=method,seed=seed,pair=pair+1));index+=1
 save(STUDY/'versions/E7_DEFERRED_HOST_PROTOCOL.json',dict(rows=rows,attempts=8,paired_cold4=True,background_study_work='No other offline CPU benchmark or physics owner during host series.',full_native_and_observer_equivalence_gate='PASS',public_B_scheduling_repairs=2,new_scheduling_repair=0,change='Only evaluator-only native-node aggregation deferred; all original raw samples retained until original formula record, no controller input or safety predicate removed.',actor_manifest_sha256=sha(STUDY/'versions/E7_DEFERRED_v1_FROZEN_MANIFEST.json'),algorithm_sources=sources))
 for r in rows:enqueue(r['id'],method=r['method'],original=r['method']=='M0',seed=r['seed'],timing_version='E5_DEFERRED_v1',execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=r['method']=='M2',research_profile=False,deferred_evaluation=True,activation_reserve_ms=36.,delay_replay=False,algorithm_sources=sources,host_series='E7_deferred_quiet_cold')
 print('E7_B5_DEFERRED_QUIET_FOUR_COLD_PAIRS_QUEUED')
if __name__=='__main__':main()
