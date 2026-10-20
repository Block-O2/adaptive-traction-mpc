from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ('continuous_worker.py','consecutive_worker.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 # Paired Rep1 B creates the same commissioned session. Both arms retain all
 # native boundary mechanics; frozen-Q arm uses unchanged six-candidate M2.
 protocols=[]
 for base,label,methods in [(210,'B',['M0']*5),(220,'frozen_Q',['M0']+['M2']*4)]:
  inner=[]
  for rep,method in enumerate(methods):
   id=f'{base+rep:03d}_continuous_SCI_{label}_rep{rep+1}'
   req=dict(id=id,mode='select',kind='physics',budget_attempts=1,method=method,original=False,execution_mode='SCIENTIFIC_SIMULATION',timing_version='T0' if method=='M0' else 'E5_HOST_v1',pipeline_batch=method=='M2',weights=str(STUDY/'weights/frozen_Q_v1'),weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),seed=2026100785+rep,prefix={},candidate_budget=6,delay_replay=False,algorithm_sources=sources,result_path=str(STUDY/'output'/(id+'_RESULT.json')),source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),scientific_version='NATIVE_CONTINUOUS_FROZEN_STABILITY_v1')
   inner.append(req)
  enqueue(inner[0]['id'],mode='consecutive',continuous_session=True,consecutive_requests=inner,algorithm_sources=sources,purpose='SCI frozen-Q stability using original native continuous session; no adaptation or actual-clock qualification')
  protocols.append(dict(label=label,ids=[r['id'] for r in inner],methods=methods))
 save(STUDY/'versions/CONTINUOUS_FROZEN_STABILITY_PROTOCOL.json',dict(status='PREREGISTERED',groups=protocols,attempt_budget=10,scope='exposed nominal Human only',Q_update=False,actual_clock=False,native_api='session_context + advance_inter_rep_boundary; original native transient-state carryover contract',condition='Host gate false; adaptation pilot not started. This is additional frozen scientific stability evidence.',resource_and_physics_owner='same durable runner single owner',cost='within repetition remaining cost; explicit inter-repetition settle/hold separately recorded',first_repetition_reference='Compare zero/B first full trajectory against prior SCI original B; subsequent reps are continuous states, not repeats of an independent identical initial trajectory.'))
 print('TEN_NATIVE_CONTINUOUS_FROZEN_SCI_REPETITIONS_QUEUED')
if __name__=='__main__':main()
