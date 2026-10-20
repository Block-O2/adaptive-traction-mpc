"""New paired groups following an independent fit initialization."""
from task_bootstrap import *
from prepare import enqueue

def main():
 version=sys.argv[1];base=sys.argv[2] if len(sys.argv)>2 else 'v1';latest=json.loads((STUDY/'LATEST_WEIGHTS.json').read_text());assert latest['version']==version
 original=json.loads((STUDY/('MATRIX_CONTRACT_'+base+'.json')).read_text());analysis=json.loads((STUDY/('ANALYSIS_'+base+'.json')).read_text());assert any(analysis['summary'][m]['quality_engineering_gate'] for m in ('M2','M3','M4')),'REPEATABLE_LEARNING_BENEFIT_FIRST'
 groups=[('nominal_c',{},2026100681),('nominal_d',{},2026100682),('deviation_c',{'OUTBOUND':[[.18,-.05,.22],[.1,.2,-.12]]},2026100683),('deviation_d',{'OUTBOUND':[[-.18,.05,-.22],[-.1,-.2,.12]]},2026100684)]
 algorithms=original['algorithms'];assert all(sha(Path(p))==h for p,h in algorithms.items())
 weights=latest['path'];contract=dict(original,version=version,frozen_unix=time.time(),weights=weights,weights_sha256=latest['sha256'],groups=groups,independent_fit_seed=latest['seed'],same_training_data=True,new_test_groups=True,parent_matrix=base,nominal_duplicates='additional same-physical-trajectory replication; independent search seeds are not new Humans',Q_seed_caveat='if linear again wins dev, its fit is deterministic; independent initialization tests G/MLP and does not fabricate a second distinct linear learner')
 save(STUDY/('MATRIX_CONTRACT_'+version+'.json'),contract)
 for i,(group,prefix,seed) in enumerate(groups):
  for method in ('M0','M1','M2','M3','M4'):
   enqueue(f'080_{version}_{i}_{group}_{method}',mode='select',group=version+'_'+group,method=method,weights=weights,weights_sha256=latest['sha256'],seed=seed,prefix=prefix,algorithm_sources=algorithms,original=method=='M0' and not prefix)
 print('NEW_PAIRED_GROUPS_QUEUED',version,20)
if __name__=='__main__':main()
