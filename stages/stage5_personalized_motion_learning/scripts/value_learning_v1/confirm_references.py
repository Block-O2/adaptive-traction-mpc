"""Independent frozen-start re-execution of final best-known references."""
import json
from research_campaign import D,RAW,RUNS,OLD,C,launch,save,sha

def normalize_descriptor(pattern):
 if 'parameters' in pattern:return pattern
 return {'parameters':[pattern.get('lead',0)*pattern.get('amplitude',0),pattern.get('peak',.5)],
  'horizon':pattern.get('horizon','H4'),'return_reverse':pattern.get('return_reverse',False),
  'synchronous':pattern.get('synchronous',False)}

def main():
 table=json.loads((D/'BEST_KNOWN_REFERENCE_TABLE.json').read_text());results=[]
 for row in table['rows']:
  if row['best_source']=='this_search':
   result=launch({'condition':row['condition'],'run_id':'confirm_reference_'+row['condition']+'_v1',
    'spec':{'mode':'PATH','descriptor':normalize_descriptor(row['best_parameters']),'matched_duration_factor':1.3}})
   diff=None if result['status']!='VALID' else result['J_F_task_n_s']-row['best_known_J_F_n_s']
   check={'condition':row['condition'],'discovery_run_id':row['best_run_id'],'confirmation_run_id':result['run_id'],
    'status':result['status'],'J_F_abs_difference_n_s':None if diff is None else abs(diff),
    'independent_confirmation_pass':diff is not None and abs(diff)<=1e-6,
    'meaning':'separate exact frozen-state deterministic rerun; no subject/generalization independence claim'}
   results.append(check)
  else:results.append({'condition':row['condition'],'discovery_run_id':row['best_run_id'],'independent_confirmation_pass':None,'status':'PREVIOUS_REFERENCE_RETAINED'})
  save(D/'BEST_KNOWN_REFERENCE_CONFIRMATION.json',{'status':'RUNNING','rows':results})
 save(D/'BEST_KNOWN_REFERENCE_CONFIRMATION.json',{'status':'PASS' if all(x['independent_confirmation_pass'] is not False for x in results) else 'FAIL','rows':results})
if __name__=='__main__':main()
