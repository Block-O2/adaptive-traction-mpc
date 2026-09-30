"""Audit ALL prior valid references without filtering for timing isolation."""
import json
from research_campaign import D,OD,C,save

def main():
 prior=json.loads((OD/'ALL_COORDINATION_ROLLOUTS.json').read_text());rows=[]
 for condition in C['reference_search']['conditions']:
  selected=[r for r in prior if r['condition_id']==condition and r['status']=='VALID']
  row={'condition':condition}
  for arm in ('NATIVE','MATCHED'):
   best=min([r for r in selected if r['arm']==arm],key=lambda r:r['J_F_task_n_s'])
   row[arm]={'run_id':best['run_id'],'J_F_task_n_s':best['J_F_task_n_s'],
    'pattern':best['pattern'],'timing_isolated':best.get('timing_isolated',False)}
  rows.append(row)
 save(D/'ALL_PRIOR_VALID_REFERENCE_AUDIT.json',{'status':'PASS','rows':rows,
  'all_valid_prior_patterns_included':True,'no_timing_isolation_filter_for_absolute_cost_reference':True})
 print(json.dumps(rows,indent=2),flush=True)
if __name__=='__main__':main()
