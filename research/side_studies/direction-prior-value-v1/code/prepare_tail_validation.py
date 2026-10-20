"""Up to two untouched groups, using only actual spare slots after all stages."""
from freeze import *
import sys
sys.path.insert(0,str(STUDY/'code'))
from accounting import attempts
def main():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());pilot=json.loads((STUDY/'PILOT_STATE.json').read_text())
 assert pilot['status'] in ('NOT_STARTED','FROZEN_DIRECTION_VALIDATION_COMPLETE')
 assert (STUDY/'ANALYSIS_v2_extra.json').exists(),'REGISTERED_EXTRA_TESTS_FIRST'
 n=min(2,(300-attempts())//4)
 if not n or time.time()+3600>=cfg['dispatch_cutoff_unix']:print('NO_TAIL_BUDGET');return
 prior=json.loads((STUDY/'COMPARISON_v2_fresh.json').read_text());assert all(sha(Path(p))==h for p,h in prior['algorithm_sources'].items());assert sha(Path(prior['weights']))==prior['weights_sha256']
 specs=[dict(group='v2_tail_nominal_0',seed=2026112200,prefix={}),dict(group='v2_tail_deviation_1',seed=2026112201,prefix={'OUTBOUND':[[.055,-.045,.025],[-.030,.060,-.020]]})][:n]
 contract=dict(version=2,batch='tail',groups=specs,weights=prior['weights'],weights_sha256=prior['weights_sha256'],algorithm_sources=prior['algorithm_sources'],registered_rule='PLAN_AMENDMENT_14_UNUSED_TAIL_VALIDATION.json',no_fit_or_tuning=True,no_retroactive_pilot_promotion=True,information_condition='KNOWN_MODEL',actual_attempts_before=attempts(),maximum_new_attempts=4*n)
 path=STUDY/'COMPARISON_v2_tail.json';assert not path.exists();save(path,contract)
 for i,spec in enumerate(specs):
  for j,(short,method) in enumerate((('P','P'),('PG','P+G'),('PV','P+V'),('PGV','P+G+V'))):
   name=f'140_v2_tail_{i}_{j}_{short}';p=STUDY/'queue'/(name+'.json');assert not p.exists();save(p,dict(id=name,kind='physics',mode='search',version=2,batch='tail',group=spec['group'],method=method,seed=spec['seed'],prefix=spec['prefix'],weights=prior['weights'] if method!='P' else None,algorithm_sources=prior['algorithm_sources'],comparison_contract_sha256=sha(path),split='test',result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 print(f'UNTOUCHED_TAIL_{4*n}_QUEUED')
if __name__=='__main__':main()
