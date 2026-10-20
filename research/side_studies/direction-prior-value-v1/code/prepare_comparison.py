from freeze import *
import sys
def main():
 version=int(sys.argv[1]);batch=sys.argv[2] if len(sys.argv)>2 else 'core'
 weights=json.loads((STUDY/'LATEST_WEIGHTS.json').read_text());assert weights['version']==version
 group_specs=[('nominal_0',{},2026100610),('nominal_1',{},2026100611),('deviation_0',{'OUTBOUND':[[.05,.05,.05],[-.03,-.03,-.03]]},2026100612),('deviation_1',{'OUTBOUND':[[-.05,-.05,-.05],[.03,.03,.03]]},2026100613)]
 if batch in ('independent','fresh'):
  n=4 if batch=='independent' else 12;group_specs=[]
  for i in range(n):
   prefix={} if i%3==0 else {'OUTBOUND':[[float((1 if i%2 else -1)*(.02+.01*(i%5)))]*3,[float((1 if i%2 else -1)*(-.015-.005*(i%4)))]*3]}
   group_specs.append((batch+'_nominal_'+str(i) if not prefix else batch+'_deviation_'+str(i),prefix,2026100900+(0 if batch=='independent' else 100)+i))
 contract=dict(version=version,batch=batch,weights=weights['weights'],weights_sha256=weights['weights_sha256'],groups=group_specs,paired_conditions='same original physical initialization, commissioning, parameters, legal prefix and search RNG seed; states can diverge after method choices',online_budget=dict(population=8,generations=2,max_G_per_generation=3,full_physics_predictions=0),promotion=dict(material_fraction=.005,all_paired_cases_VALID_MATCHED=True,moment_tradeoffs_reported=True,common_mode_sample_error_max=1e-12),test_isolation='No fitting or tuning with this batch; revisions need new batch/group identifiers')
 contract_path=STUDY/f'COMPARISON_v{version}_{batch}.json';assert not contract_path.exists();save(contract_path,contract)
 algorithm_sources={str(STUDY/'code'/name):sha(STUDY/'code'/name) for name in ('planning.py','interfaces.py','inference.py','known_model.py')};contract['algorithm_sources']=algorithm_sources;save(contract_path,contract)
 for i,(group,prefix,seed) in enumerate(group_specs):
  for j,(short,method) in enumerate([('P','P'),('PG','P+G'),('PV','P+V'),('PGV','P+G+V')]):
   order={'core':30,'final':60,'independent':90,'fresh':100}[batch]
   name=f'{order:03d}_v{version}_{batch}_{i}_{group}_{j}_{short}';p=STUDY/'queue'/(name+'.json');assert not p.exists()
   save(p,dict(id=name,kind='physics',mode='search',method=method,seed=seed+version*100,batch=batch,version=version,group=f'v{version}_{batch}_{group}',split='test',prefix=prefix,weights=weights['weights'] if method!='P' else None,result_path=str(STUDY/'output'/(name+'_RESULT.json')),comparison_contract_sha256=sha(contract_path),algorithm_sources=algorithm_sources))
 print(f'QUEUED_{4*len(group_specs)}_v{version}_{batch}')
if __name__=='__main__':main()
