"""Exercise the actual inactive campaign controller with fake jobs, zero physics/learning."""
from pathlib import Path
import sys,tempfile,json,importlib.util,types,time
from research_common import ROOT,atomic,read,now
T=ROOT/'unattended/template/scripts';sys.path.insert(0,str(T))
spec=importlib.util.spec_from_file_location('inactive_campaign_under_test',T/'campaign.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
from finite_engine import BranchFailure,GlobalStop
checks={}
for scenario in ['branch_fail','global_stop','full_finite','R4_stochastic_regression']:
 with tempfile.TemporaryDirectory(prefix='std_campaign_test_',dir='/tmp') as tmp:
  root=Path(tmp);(root/'scripts').mkdir();c.ROOT=root;c.RUNTIME=root/'runtime';c.NO_TRAIN=time.time()+21600;c.HARD_STOP=time.time()+28800
  calls=[];evals=[];closed=[]
  atomic(root/'ACTIVATION.json',dict(training_authorized_for_next_stage=True,methods=['CHECKPOINT_STD','STD_INIT_0p2'],checkpoint_pair=[dict(seed=s,checkpoint=f'original_{s}') for s in c.SEEDS],holdout_streams=list(range(2026102301,2026102307)),script_sha256={}))
  def train(label,seed,parent,start,count,reward='R1',initialize_std=None):
   calls.append(dict(label=label,seed=seed,start=start,count=count))
   if label=='CHECKPOINT_STD' and scenario=='branch_fail':raise BranchFailure('safe local branch failure')
   if label=='CHECKPOINT_STD' and scenario=='global_stop':raise GlobalStop('SAMPLING_DENSITY_OWNERSHIP_MISMATCH')
   return f'fake_{label}_{seed}_{start+count}'
  def evaluate(label,seed,parent,endpoint,mode,rng=2026102201,split='development'):
   if label=='LOCKED_FINAL':assert (root/'FINAL_SELECTION_BEFORE_HOLDOUT.json').exists()
   row=dict(seed=seed,policy_mode=mode,success=scenario in ['full_finite','R4_stochastic_regression'] and not (scenario=='R4_stochastic_regression' and label.startswith('REWARD_R4') and mode=='stochastic'),rejections=0,task_s=19.03,JF=100.5 if label.startswith('REWARD_R4') else 100.,JM=9. if label.startswith('REWARD_R4') else 10.)
   evals.append(dict(label=label,rng=rng,split=split));return row
  c.train=train;c.evaluate=evaluate;c.subprocess=types.SimpleNamespace(run=lambda *a,**k:closed.append(True))
  prior=list(sys.argv);sys.argv=['campaign.py','--run-approved-plan']
  try:c.main()
  finally:sys.argv=prior
  end=read(root/'CAMPAIGN_QUEUE_END.json');state=read(root/'RESEARCH_STATE.json')
  if scenario=='branch_fail':
   checks['actual_controller_local_branch_failure_continues_next_method']=any(x['label']=='STD_INIT_0p2' for x in calls) and end['status']=='FINITE_QUEUE_COMPLETE_AWAITING_INDEPENDENT_REVIEW'
   checks['all_scientific_fail_uses_preserved_parents_without_new_search']=read(root/'FINAL_SELECTION_BEFORE_HOLDOUT.json')['method']=='ORIGINAL_R1_60' and len(evals)==16
  elif scenario=='global_stop':checks['actual_controller_global_integrity_stops_before_next_method']=len(calls)==1 and not evals and end['status']=='GLOBAL_STOP'
  else:
   checks['actual_controller_max_training_episodes160']=sum(x['count'] for x in calls)==160
   checks['actual_controller_max_evaluations36']=len(evals)==36
   checks['twelve_holdouts_only_after_candidate_lock']=sum(x['split']=='reserved_action_streams' for x in evals)==12
   checks['R4_predeclared_per_parent_tradeoff_gate_exercised' if scenario=='full_finite' else 'R4_stochastic_regression_prevents_promotion']=read(root/'FINAL_SELECTION_BEFORE_HOLDOUT.json')['reward']==('R4' if scenario=='full_finite' else 'R1')
   checks['normal_close_status_update_no_duplicate_keyword']=state['status']=='FINITE_QUEUE_COMPLETE_AWAITING_INDEPENDENT_REVIEW' and closed==[True]
result=dict(time_utc=now(),checks=checks,pass_=all(checks.values()),new_physics=0,Adam=0,scope='Actual future controller exercised with injected bounded fake train/evaluation/close functions; no end-to-end training claim')
atomic(ROOT/'audit/UNATTENDED_CAMPAIGN_TESTS.json',result);print(json.dumps(result));assert result['pass_']
