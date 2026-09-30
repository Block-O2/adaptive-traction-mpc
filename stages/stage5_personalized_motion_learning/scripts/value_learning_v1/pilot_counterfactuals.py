"""Known-benefit comparisons from the SAME pre-repetition immutable state."""
import json
import numpy as np
from research_campaign import D,RAW,RUNS,launch,save
from confirm_references import normalize_descriptor
from evidence_io import read_json

def task_initial_state(run_id):
 trace=np.load(next((RUNS/run_id).glob('rep_*/trace.npz')))
 ix=np.flatnonzero(trace['stage']=='TASK')[0]
 return trace['evaluation_only_human_state_rad_rad_s'][ix].tolist()

def main():
 pilot=json.loads((D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json').read_text())
 table=json.loads((D/'BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 results=[]
 for session in pilot['sessions']:
  ref=next(r for r in table['rows'] if r['condition']==session['condition'])
  for row in session['rows']:
   rep=row['repetition_index']
   if rep not in range(1,9):continue
   if row['status']!='VALID':
    results.append({'session':session['session'],'mode':session['mode'],'repetition':rep,'status':'LEARNED_REPETITION_INVALID','learned_run_id':row['run_id'],'known_benefit_capture':None,'reason':row.get('failure_reason'),'truncated_failure_never_a_good_return':True});continue
   spec={'mode':'PATH','matched_duration_factor':1.3}
   starting_scope='original immutable fresh development condition'
   if rep>1:
    prev=next((r for r in session['rows'] if r['repetition_index']==rep-1),{})
    if not prev.get('end_checkpoint') and row.get('start_native_state_evaluation_only') is not None:
     results.append({'session':session['session'],'repetition':rep,'status':'NO_COMMON_CONTINUOUS_CHECKPOINT'});continue
    if prev.get('end_checkpoint'):
     spec['source_checkpoint']=prev['end_checkpoint'];starting_scope='verified previous-repetition checkpoint + original safe boundary'
    else:starting_scope='fresh development segment after failed native continuation; original immutable condition, not continuous carryover'
   baseline=launch({'condition':session['condition'],'run_id':f'counterfactual_{session["session"]}_rep{rep:02d}_baseline',
    'spec':{**spec,'descriptor':{'parameters':[0.,.5],'horizon':'H4'}}})
   reference=launch({'condition':session['condition'],'run_id':f'counterfactual_{session["session"]}_rep{rep:02d}_reference',
    'spec':{**spec,'descriptor':normalize_descriptor(ref['best_parameters'])}})
   source_equal=(baseline['status']=='VALID' and reference['status']=='VALID' and
    task_initial_state(row['run_id'])==task_initial_state(baseline['run_id'])==task_initial_state(reference['run_id']))
   item={'session':session['session'],'mode':session['mode'],'repetition':rep,'status':'VALID' if source_equal else 'COMPARISON_INVALID',
    'same_native_initial_task_state_evaluation_check':source_equal,'source_checkpoint':spec.get('source_checkpoint'),
    'learned_run_id':row['run_id'],'baseline_run_id':baseline['run_id'],'reference_run_id':reference['run_id'],'starting_state_scope':starting_scope,
    'reference_policy_discovery_run_id':ref['best_run_id'],'comparison':'matched declared-duration paths replayed from same pre-repetition checkpoint; reference transferred to current adaptation state',
    'learned_J_F_n_s':row['J_F_task_n_s'],'baseline_J_F_n_s':baseline.get('J_F_task_n_s'),'reference_J_F_n_s':reference.get('J_F_task_n_s')}
   if source_equal:
    denominator=baseline['J_F_task_n_s']-reference['J_F_task_n_s']
    item['known_benefit_denominator_n_s']=denominator
    item['known_benefit_capture']=None if denominator<=1e-6 else (baseline['J_F_task_n_s']-row['J_F_task_n_s'])/denominator
    item['reference_regret_n_s']=row['J_F_task_n_s']-reference['J_F_task_n_s']
    item['phase_timing_residual_learned_vs_baseline_s']={p:read_json(RUNS/row['run_id']/'rollout_result.json')[p.lower()+'_duration_s']-baseline[p.lower()+'_duration_s'] for p in ('OUTBOUND','RETURN')}
    if row['J_F_task_n_s']<reference['J_F_task_n_s']-1e-6:
     confirmation=launch({'condition':session['condition'],'run_id':f'counterfactual_{session["session"]}_rep{rep:02d}_learned_confirm',
      'spec':{**spec,'descriptor':row['selected_continuation']}})
     confirmed=(confirmation['status']=='VALID' and abs(confirmation['J_F_task_n_s']-row['J_F_task_n_s'])<=1e-6)
     item['learned_better_reference_confirmation']={'run_id':confirmation['run_id'],'confirmed':confirmed,'cost_n_s':confirmation.get('J_F_task_n_s')}
     if confirmed:
      item['updated_state_specific_best_known_J_F_n_s']=confirmation['J_F_task_n_s']
      item['known_benefit_capture_after_confirmed_update']=1.
   results.append(item)
   save(D/'KNOWN_BENEFIT_CAPTURE.json',{'status':'RUNNING','rows':results,'metric':'KNOWN-BENEFIT CAPTURE; not global-optimality percentage'})
   if rep in (1,3,5,8):
    probes=[]
    descriptor=row['selected_continuation'];parameters=list(descriptor['parameters'])
    for index,delta in enumerate((-.03,.03)):
     alternative=parameters.copy();alternative[0]=float(np.clip(alternative[0]+delta,-.2,.2))
     proposal={**descriptor,'parameters':alternative}
     result=launch({'condition':session['condition'],'run_id':f'alternate_probe_{session["session"]}_rep{rep:02d}_P{index}',
      'spec':{**spec,'descriptor':proposal}})
     probes.append({'run_id':result['run_id'],'descriptor':proposal,'status':result['status'],'J_F_n_s':result.get('J_F_task_n_s'),
      'improvement_over_selected_n_s':None if result['status']!='VALID' else row['J_F_task_n_s']-result['J_F_task_n_s'],
      'same_checkpoint':spec.get('source_checkpoint')})
    item['targeted_safe_alternatives']=probes
 save(D/'KNOWN_BENEFIT_CAPTURE.json',{'status':'COMPLETE','rows':results,'metric':'KNOWN-BENEFIT CAPTURE; not global-optimality percentage','same_checkpoint_required':True,'negative_or_zero_denominator_not_reported_as_fraction':True})
if __name__=='__main__':main()
