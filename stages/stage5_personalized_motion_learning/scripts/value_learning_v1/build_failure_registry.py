"""Keep screened rejections distinct from post-screen failed transitions."""
import json
from value_dataset import D,RAW,OLD,OD,save,sha
from evidence_io import read_json

def main():
 rows=[]
 old=json.loads((OD/'ALL_COORDINATION_ROLLOUTS.json').read_text())
 paths=[OLD/r['run_id'] for r in old if r['status']!='VALID']
 paths += [p.parent for p in (RAW/'runs').glob('*/rollout_result.json')]
 for folder in paths:
  result=read_json(folder/'rollout_result.json')
  if result['status'] in ('VALID','RUNNING'):continue
  reason=result.get('failure_reason','') or ''
  kind=('infrastructure_interruption' if result['status']=='INTERRUPTED_HOST_RESOURCE' else
   'pre_execution_screen_rejection' if result['status']=='INFEASIBLE' or 'NO_FEASIBLE_WAYPOINT' in reason else 'post_screen_task_or_scientific_failure')
  item={'run_id':result['run_id'],'condition_id':result['condition_id'],'status':result['status'],'failure_class':kind,
   'reason':reason,'result_sha256':sha(folder/'rollout_result.json'),'never_a_regression_target':True,
   'truncated_force_integral_never_an_attractive_action_label':True,'last_activated_action_not_automatically_causal':True}
  reps=list(folder.glob('rep_*'))
  if reps:
   try:
    summary=read_json(reps[0]/'summary.json')
    active=[d for d in summary.get('decisions',[]) if d.get('plan_activated') and 'evaluations' in d]
    if active:
     last=active[-1];chosen=next(e for e in last['evaluations'] if e['label']==last['executed_label'])
     item['last_activated_transition_evidence']={'phase':last['phase'],'estimated_state':last.get('deployable_state_rad_rad_s',last.get('deployable_state')),
      'reference_state':last.get('reference_state_rad_rad_s'),'activation_time_s':last.get('activation_timestamp_s'),
      'action':chosen,'continuation_context':chosen.get('execution_screen',{}).get('research_context'),
      'failure_after_screening':kind=='post_screen_task_or_scientific_failure','return_target':None}
    item['logged_rejected_candidates']=[{'phase':d['phase'],'label':e['label'],'target':e.get('target_q_rad'),'reason':e.get('rejection_reason')} for d in summary.get('decisions',[]) for e in d.get('evaluations',[]) if not e.get('feasible')]
   except (FileNotFoundError,StopIteration,json.JSONDecodeError) as error:
    item['partial_summary_unavailable']=str(error)
    item['partial_artifact_preserved_not_dropped']=True
  rows.append(item)
 save(D/'FAILURE_TRANSITIONS_REGISTRY.json',{'schema':'separate_failure_transitions_v1','rows':rows,
  'counts':{k:sum(r['failure_class']==k for r in rows) for k in ('pre_execution_screen_rejection','post_screen_task_or_scientific_failure','infrastructure_interruption')},
  'all_failed_and_truncated_runs_excluded_from_value_regression':True})
if __name__=='__main__':main()
