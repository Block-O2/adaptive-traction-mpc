"""Separate deterministic frozen-state confirmations of native new winners."""
import json
from research_campaign import D,launch,save
from confirm_references import normalize_descriptor

def main():
 table=json.loads((D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json').read_text());rows=[]
 for row in table['rows']:
  if row['best_source']=='native_extension':
   result=launch({'condition':row['condition'],'run_id':'confirm_native_reference_'+row['condition']+'_v1',
    'spec':{'mode':'NATIVE_PATH','timing_policy':'NATIVE_SCHEDULER','descriptor':normalize_descriptor(row['best_descriptor']),'matched_duration_factor':0.}})
   difference=None if result['status']!='VALID' else abs(result['J_F_task_n_s']-row['best_known_J_F_n_s'])
   rows.append({'condition':row['condition'],'discovery_run_id':row['best_run_id'],'confirmation_run_id':result['run_id'],
    'status':result['status'],'J_F_abs_difference_n_s':difference,'independent_confirmation_pass':difference is not None and difference<=1e-6,
    'meaning':'separate frozen-state deterministic rerun; no independent Human/generalization claim'})
  else:rows.append({'condition':row['condition'],'status':'PREVIOUS_REFERENCE_RETAINED','independent_confirmation_pass':None})
  save(D/'NATIVE_BEST_KNOWN_REFERENCE_CONFIRMATION.json',{'status':'RUNNING','rows':rows})
 save(D/'NATIVE_BEST_KNOWN_REFERENCE_CONFIRMATION.json',{'status':'PASS' if all(r['independent_confirmation_pass'] is not False for r in rows) else 'FAIL','rows':rows})
if __name__=='__main__':main()
