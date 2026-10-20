from task_bootstrap import *
from prepare import enqueue
def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1';weights=json.loads((STUDY/'LATEST_WEIGHTS.json').read_text())['path']
 contract=json.loads((STUDY/'PROTOCOL.json').read_text());assert contract['version']==1
 algorithm={str(p):sha(p) for folder in ('code','deps') for p in (STUDY/folder).glob('*.py') if p.name in ('native_method.py','native_core.py','native_inference.py','interfaces.py','coordination_adapter.py','representation.py')}
 groups=[('nominal_a',{},2026100621),('nominal_b',{},2026100622),('deviation_positive',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623),('deviation_negative',{'OUTBOUND':[[-.2,-.1,.1],[-.05,-.15,-.25]]},2026100624)]
 save(STUDY/('MATRIX_CONTRACT_'+version+'.json'),dict(version=version,frozen_unix=time.time(),weights=weights,weights_sha256=sha(Path(weights)/'weights.npz'),algorithms=algorithm,groups=groups,methods=['M0','M1','M2','M3','M4'],same_human=True,nominal_duplicates='two search seeds are deterministic same-physical-state replication, not two independent humans',prefix='executed lawful shared intervention before method selection; no q/dq snapshot fabrication',information='estimated commissioned B only',test_tuning=False,physical_task_and_R2_unchanged=True))
 for idx,(group,prefix,seed) in enumerate(groups):
  for method in ('M0','M1','M2','M3','M4'):
   enqueue(f'040_{version}_{idx}_{group}_{method}',mode='select',group=version+'_'+group,method=method,weights=weights,weights_sha256=sha(Path(weights)/'weights.npz'),seed=seed,prefix=prefix,algorithm_sources=algorithm,original=(method=='M0' and not prefix))
 save(STUDY/'CHECKPOINT.json',dict(phase='FIRST_COMPLETE_MATRIX',next='20 paired full runs; then paired validity/cost/latency and one bounded attribution correction if warranted',start_unix=json.loads((STUDY/'RUN_PLAN.json').read_text())['start_unix'],weights=weights))
 print('MATRIX_PREREGISTERED',version,20)
if __name__=='__main__':main()
