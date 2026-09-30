"""Absolute primary-objective anchors, separate from conditional matched capture."""
import json
from research_campaign import D,launch,save
from pilot_counterfactuals import task_initial_state
from confirm_references import normalize_descriptor

def main():
 pilot=json.loads((D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json').read_text())
 table=json.loads((D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 results=[]
 for session in pilot['sessions']:
  ref=next(r for r in table['rows'] if r['condition']==session['condition'])
  for row in session['rows']:
   rep=row['repetition_index']
   if rep not in (1,3,5,8):continue
   if row['status']!='VALID':
    results.append({'session':session['session'],'mode':session['mode'],'repetition':rep,'status':'LEARNED_REPETITION_INVALID','learned_run_id':row['run_id'],'known_benefit_capture':None,'reason':row.get('failure_reason'),'truncated_failure_never_a_good_return':True});continue
   spec={'timing_policy':'NATIVE_SCHEDULER','matched_duration_factor':0.}
   starting_scope='original immutable fresh development condition'
   if rep>1:
    prev=next((r for r in session['rows'] if r['repetition_index']==rep-1),{})
    if not prev.get('end_checkpoint') and row.get('start_native_state_evaluation_only') is not None:
     results.append({'session':session['session'],'repetition':rep,'status':'NO_COMMON_CONTINUOUS_CHECKPOINT'});continue
    if prev.get('end_checkpoint'):
     spec['source_checkpoint']=prev['end_checkpoint'];starting_scope='verified previous-repetition checkpoint + original safe boundary'
    else:starting_scope='fresh development segment after failed native continuation; original immutable condition, not continuous carryover'
   baseline=launch({'condition':session['condition'],'run_id':f'absolute_counterfactual_{session["session"]}_rep{rep:02d}_baseline',
    'spec':{**spec,'mode':'NATIVE_BASELINE','descriptor':{'parameters':[0.,.5],'horizon':'H4'}}})
   reference=launch({'condition':session['condition'],'run_id':f'absolute_counterfactual_{session["session"]}_rep{rep:02d}_reference',
    'spec':{**spec,'mode':'NATIVE_PATH','descriptor':normalize_descriptor(ref['best_descriptor'])}})
   equal=(baseline['status']=='VALID' and reference['status']=='VALID' and
    task_initial_state(row['run_id'])==task_initial_state(baseline['run_id'])==task_initial_state(reference['run_id']))
   item={'session':session['session'],'mode':session['mode'],'repetition':rep,'status':'VALID' if equal else 'COMPARISON_INVALID',
    'same_native_initial_task_state_evaluation_check':equal,'source_checkpoint':spec.get('source_checkpoint'),
    'learned_run_id':row['run_id'],'baseline_run_id':baseline['run_id'],'reference_run_id':reference['run_id'],'starting_state_scope':starting_scope,
    'reference_discovery_run_id':ref['best_run_id'],'comparison':'absolute primary objective; matched learner versus native baseline/reference from identical pre-repetition state; timing may differ',
    'learned_J_F_n_s':row['J_F_task_n_s'],'baseline_J_F_n_s':baseline.get('J_F_task_n_s'),'reference_J_F_n_s':reference.get('J_F_task_n_s')}
   if equal:
    denominator=baseline['J_F_task_n_s']-reference['J_F_task_n_s']
    item.update(known_benefit_denominator_n_s=denominator,
     known_benefit_capture=None if denominator<=1e-6 else (baseline['J_F_task_n_s']-row['J_F_task_n_s'])/denominator,
     reference_regret_n_s=row['J_F_task_n_s']-reference['J_F_task_n_s'])
   results.append(item)
   save(D/'PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json',{'status':'RUNNING','rows':results,'metric':'KNOWN-BENEFIT CAPTURE; negative values retained; no global optimality'})
 save(D/'PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json',{'status':'COMPLETE','rows':results,'metric':'KNOWN-BENEFIT CAPTURE; negative values retained; no global optimality','same_checkpoint_required':True})
if __name__=='__main__':main()
