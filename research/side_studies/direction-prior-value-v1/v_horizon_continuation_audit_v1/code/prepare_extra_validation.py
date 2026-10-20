from freeze import *
import sys
sys.path.insert(0,str(STUDY/'code'))
from accounting import attempts
def main():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());pilot=json.loads((STUDY/'PILOT_STATE.json').read_text());assert pilot['status'] in ('NOT_STARTED','FROZEN_DIRECTION_VALIDATION_COMPLETE'),'PILOT_HAS_PRIORITY'
 assert attempts()+16<=300 and time.time()+3600<cfg['dispatch_cutoff_unix'],'INSUFFICIENT_EXTRA_VALIDATION_BUDGET'
 weights=json.loads((STUDY/'COMPARISON_v2_fresh.json').read_text());algorithm_sources=weights['algorithm_sources'];assert all(sha(Path(p))==h for p,h in algorithm_sources.items());assert sha(Path(weights['weights']))==weights['weights_sha256']
 contract=dict(version=2,batch='extra',weights=weights['weights'],weights_sha256=weights['weights_sha256'],algorithm_sources=algorithm_sources,reason='All required comparison/audit/independent stages completed; pilot did not promote; use remaining physical budget only for untouched paired tests',no_training_or_tuning=True,information_condition='KNOWN_MODEL',exposed_nominal_Human=True,online_budget=dict(population=8,generations=2,G_max_per_generation=3,full_physics_predictions=0),groups=[])
 for i in range(4):
  prefix={} if i==0 else {'OUTBOUND':[[float((1 if i%2 else -1)*(.024+.009*i))]*3,[float((1 if i%2 else -1)*(-.011-.006*i))]*3]};group=f'v2_extra_{"nominal" if not prefix else "deviation"}_{i}';seed=2026111200+i;contract['groups'].append(dict(group=group,prefix=prefix,seed=seed))
 path=STUDY/'COMPARISON_v2_extra.json';assert not path.exists();save(path,contract)
 for i,spec in enumerate(contract['groups']):
  for j,(short,method) in enumerate((('P','P'),('PG','P+G'),('PV','P+V'),('PGV','P+G+V'))):
   name=f'130_v2_extra_{i}_{j}_{short}';path=STUDY/'queue'/(name+'.json');assert not path.exists();save(path,dict(id=name,kind='physics',mode='search',version=2,batch='extra',group=spec['group'],method=method,seed=spec['seed'],prefix=spec['prefix'],weights=contract['weights'] if method!='P' else None,algorithm_sources=algorithm_sources,comparison_contract_sha256=sha(STUDY/'COMPARISON_v2_extra.json'),split='test',result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 print('UNTOUCHED_EXTRA_16_QUEUED')
if __name__=='__main__':main()
