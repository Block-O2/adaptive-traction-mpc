"""Finite newest-B5 same-parent lifecycle robustness, no new public repair."""
from prepare_tasks import *
from prepare_next_versions import frozen_sources
from freeze_version import freeze
def main():
 gate=json.loads((STUDY/'versions/E7_DEFERRED_FULL_NATIVE_EQUIVALENCE_GATE.json').read_text());assert gate['status']=='PASS'
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[e for e in events if e['event']=='START'];done={e['id'] for e in events if e['event']=='END'};assert all(e['id'] in done for e in starts) and len(starts)+8<=160
 assert time.time()+1200<START+8.25*3600
 freeze('E7_DEFERRED_v1');sources=frozen_sources()
 for f in ('deferred_evaluation.py','lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','consecutive_worker.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 groups=[]
 for base,label,method in ((300,'B','M0'),(310,'accelerated','M2')):
  inner=[]
  for rep in range(4):
   id=f'{base+rep:03d}_E7_DEFERRED_consecutive_{label}_rep{rep+1}'
   inner.append(dict(id=id,kind='physics',budget_attempts=1,mode='select',method=method,original=method=='M0',weights=str(STUDY/'weights/frozen_Q_v1'),weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),seed=2026100851+rep,prefix={},timing_version='E5_DEFERRED_v1',scientific_version='frozen-B-native-Q-v1',source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),public_version=None,execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=method=='M2',research_profile=False,deferred_evaluation=True,delay_replay=False,activation_reserve_ms=36 if method=='M2' else None,algorithm_sources=sources,result_path=str(STUDY/'output'/(id+'_RESULT.json')),repetition_index=rep+1,host_series='E7_deferred_consecutive_'+label))
  groups.append(inner)
 save(STUDY/'versions/E7_DEFERRED_CONSECUTIVE_PROTOCOL.json',dict(groups=groups,attempts=8,attempts_before=len(starts),single_physics_owner=True,quiet=True,source_unchanged_from_E7_gate=True,parent_interpreter_shared=True,fresh_native_worker_and_plant_per_episode=True,scope='Test the newest evaluator-only B5 actor and its monitor/logging lifecycle across four sequential episodes per method. Earlier E5 consecutive tests predate B5 relocation. This is timing/lifecycle robustness, not persistent Human adaptation.',public_B_scheduling_repairs=2,new_public_repair=0,Q_updates=0,no_future_state=True,no_other_offline_CPU_job_during_host_series=True))
 for inner in groups:enqueue(inner[0]['id'],mode='consecutive',consecutive_requests=inner,algorithm_sources=sources,purpose='Newest exact B5 observer relocation: four same-parent finite host episodes, fresh commissioned native plant/worker each, no adaptation claim')
 print(json.dumps(dict(registered_attempts=8,projected_attempts=len(starts)+8,newest_version_same_parent_lifecycle=True)))
if __name__=='__main__':main()
