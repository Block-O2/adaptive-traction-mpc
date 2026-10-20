from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 assert json.loads((STUDY/'versions/CONSECUTIVE_r1_FULL_NATIVE_EQUIVALENCE_GATE.json').read_text())['status']=='PASS'
 sources=frozen_sources()
 for f in ['async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py','consecutive_worker.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 for base,label,method,version in [(140,'B','M0','T0'),(150,'baseline','M2','T0'),(160,'accelerated','M2','E5_HOST_v1')]:
  inner=[]
  for rep in range(4):
   id=f'{base+rep:03d}_host_consecutive_{label}_rep{rep+1}';req=dict(id=id,kind='physics',budget_attempts=1,mode='select',method=method,original=method=='M0',weights=str(STUDY/'weights/frozen_Q_v1'),weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),seed=2026100761+rep,prefix={},timing_version=version,scientific_version='frozen-B-native-Q-v1',source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),public_version=None,execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=label=='accelerated',delay_replay=label=='baseline',activation_reserve_ms=36 if label=='accelerated' else None,algorithm_sources=sources,result_path=str(STUDY/'output'/(id+'_RESULT.json')),repetition_index=rep+1,host_series='consecutive_'+label)
   inner.append(req)
  enqueue(inner[0]['id'],mode='consecutive',consecutive_requests=inner,algorithm_sources=sources,purpose='4 complete attempted host episodes in one parent interpreter; each fresh native worker closes/joins, no persistent Human/plant-state claim')
 save(STUDY/'versions/HOST_CONSECUTIVE_PROTOCOL.json',dict(methods=['M0 original','M2 baseline','M2 existing-native-worker accelerated'],repetitions_each=4,physical_attempts=12,single_physics_owner=True,fresh_commissioning_each=True,parent_interpreter_shared=True,native_worker_reinitialized_each=True,SCI_plumbing_full_native_gate='PASS',actual_wall=True,epoch_frozen=False,adaptation_pilot=False,algorithm_sources=sources))
 print('THREE_METHODS_FOUR_CONSECUTIVE_HOST_EPISODES_EACH_QUEUED')
if __name__=='__main__':main()
