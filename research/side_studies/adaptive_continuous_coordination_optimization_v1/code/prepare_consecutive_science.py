from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py','consecutive_worker.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 inner=[]
 for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  id=f'{135+offset:03d}_consecutive_r1_science_{label}'
  req=dict(id=id,kind='physics',budget_attempts=1,mode='select',method=method,original=method=='M0',weights=str(STUDY/'weights/frozen_Q_v1'),weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),seed=seed,prefix=prefix,timing_version='E5_HOST_v1',scientific_version='frozen-B-native-Q-v1',source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),public_version=None,execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=method=='M2',algorithm_sources=sources,result_path=str(STUDY/'output'/(id+'_RESULT.json')))
  inner.append(req)
 save(STUDY/'versions/CONSECUTIVE_r1_CONTRACT.json',dict(scope='metadata/audit lifecycle only',previous_failed_ids=['131_consecutive_science_M2','132_consecutive_science_deviation'],repair='Install dynamically compiled execution-mode metadata writer once per interpreter; it consumes each current env summary and retains unchanged independent audit. No physics/control/model timing change.',algorithm_sources=sources))
 enqueue(inner[0]['id'],mode='consecutive',consecutive_requests=inner,algorithm_sources=sources,purpose='same-interpreter plumbing equivalence on B/M2/legal-deviation after idempotent metadata audit repair')
 print('THREE_COUNTED_CONSECUTIVE_SCIENCE_EPISODES_QUEUED')
if __name__=='__main__':main()
