"""No physics. Frozen objective gate and reward arithmetic before any Stage2."""
from pathlib import Path
import json,time,hashlib
from common import ROOT,put

def main():
 from replication_analysis import summarize
 result=summarize();cfg=json.loads((ROOT/'PPO_TRAINING_CONFIG.json').read_text());ledger=json.loads((ROOT/'LEDGER.json').read_text());seeds=result['seeds'];seed=min(cfg['seeds']);parent=next(x for x in seeds if x['seed']==seed)
 checks={'Stage1_complete':(ROOT/'STAGE1_COMPLETE.json').exists(),'three_of_three_replication':result['three_seed_replication_pass'],'parent_repeated_runtime_2_of_2':parent['final_evaluation_attempts']==2 and parent['final_evaluation_successes']==2,'all_observed_training_audits_pass':all(x['all_episode_audits_pass'] for x in seeds),'all_independent_integral_metrics_pass':result['all_integral_tracking_recomputations_pass'],'no_resource_or_safety_stop':not (ROOT/'RESOURCE_STOP').exists(),'at_least_60min_before_no_new_physics':time.time()<cfg['no_new_physics_after_unix']-3600,'native_budget_for_30train_and2eval':cfg['native_steps_hard_cap']-ledger['native_steps']>=32*165000,'evaluation_budget_for_2':ledger['evaluation_attempts']+2<=24}
 gate=all(checks.values());decision={'unix':time.time(),'gate_pass':gate,'checks':checks,'seed':seed,'parent_checkpoint':parent['final_checkpoint'],'parent_policy_sha256':json.loads((ROOT/parent['final_checkpoint']).with_suffix('.json').read_text())['policy_sha256'] if parent['final_checkpoint'] else None,'mode':'DEVELOPMENT_ONLY_NO_FORMAL_PROMOTION','selection_rule':'smallest numerical seed, final preregistered checkpoint; never best JF/motion','scorer_readiness':'NOT_READY_ORIGINAL_B_H150_SCORER_MISSING','final_campaign_authorized':False}
 put(ROOT/'STAGE2_GATE_DECISION.json',decision)
 if not gate:
  reasons=[k for k,v in checks.items() if not v]
  put(ROOT/'STAGE2_RESULTS.json',{'status':'NOT_RUN','reason':'Frozen gate failed: '+', '.join(reasons),'gate':decision,'training_episodes':0,'gradient_updates':0,'native_steps':0,'paired_performance':'NOT_EVALUABLE_NO_STAGE2','task_completion_sacrificed':'NOT_APPLICABLE_NOT_RUN'})
  (ROOT/'STAGE2_PERFORMANCE_STUDY.md').write_text('# Stage2性能研究\n\n**NOT_RUN**。'+', '.join(reasons)+'。\n\n未满足预注册启动条件，不强行训练。不存在Stage2性能改进或任务牺牲的结果；所有Stage1父权重保留。原reward为pilot_v3_failure_cost_floor。没有把未运行的候选reward称为已训练版本，也没有自动启动最终campaign。\n')
  print(json.dumps({'gate_pass':False,'reasons':reasons}));return
 reward={'version':'stage2_task_pretrained_force_motion_v1','gamma':1.,'progress_weight':5.,'completion_bonus':20.,'failure_base_penalty':-10.,'force_weight':1.,'force_normalization_Ns':100.,'variation_weight':.05,'acceleration_normalization_deg_s2':[300.,600.],'failure_cost_floor':61.5,'bound':'200N*30s/100=60, plus .05*30=1.5 normalized squared acceleration integral; failure telescopes progress to0 and return=-10-max(61.5,observed force+variation cost)-5*initial potential. Hard safety independent.','moment_weight':0.,'terminal_extra_weight':0.}
 decision.update(reward=reward,planned_training_episodes=30,checkpoints=[10,20,30],parent_training_success_rate_last20=None,stage2_identity='TASK_PRETRAINED_PPO_FINETUNING',reward_revision_branches=0,paired_force_attribution_rule='Both full runtime tasks and equal mean TASK duration within1e-6 numerical seconds; unequal duration gets descriptive integrals only, never force-improvement attribution. Original19.030 necessary timing is checked separately, never a full scorer substitute.',stop_rule='Stop for any safety/reward/ownership/resource error; after every10 stop if training completion rate below parent last20 (stricter than pre-protocol >20pp stop); never retune on frozen final evaluation. Final task failure, duration mismatch, moment/jerk degradation cannot be called qualified improvement.')
 rows=[json.loads(s) for s in (ROOT/'ALL_TRAINING_LOG.jsonl').read_text().splitlines()];pr=[x for x in rows if x['training_seed']==seed and x['stage']=='stage1'][-20:];decision['parent_training_success_rate_last20']=sum(x['success'] for x in pr)/len(pr)
 # Arithmetic test is independent of physics and checks the inherited failure
 # loophole remains closed when force weight increases 50x.
 from stage2_env import Stage2Env
 tests=[]
 for phi in [0.,.5,1.,2.,2.9]:
  for jf,var in [(0.,0.),(100.,0.),(1450.,1.),(6000.,30.),(7000.,40.)]:
   e=Stage2Env.__new__(Stage2Env);e.stage2_config={'reward':reward};e.phi=phi;e.last_phi=0.;e.force_integral=jf;e.last_force=0.;e.motion_variation=var;e.last_variation=0.;e.reward_totals={'progress':0.,'completion':0.,'force':0.,'variation':0.}
   e._reward();e._reward(failure=True);actual=sum(e.reward_totals.values());expected=-10-max(61.5,jf/100.+.05*var);tests.append({'phi':phi,'JF':jf,'variation':var,'actual':actual,'expected':expected,'pass':abs(actual-expected)<1e-10 and abs(e.reward_totals['progress'])<1e-10})
 put(ROOT/'STAGE2_REWARD_AUDIT.json',{'category':'NO_PHYSICS_REWARD_ARITHMETIC','tests':tests,'pass':all(x['pass'] for x in tests),'no_final_evaluation_tuning':True})
 assert all(x['pass'] for x in tests)
 put(ROOT/'STAGE2_FROZEN.json',decision);digest=hashlib.sha256((ROOT/'STAGE2_FROZEN.json').read_bytes()).hexdigest();put(ROOT/'STAGE2_FROZEN_IDENTITY.json',{'sha256':digest,'unix':time.time(),'parent_checkpoint':decision['parent_checkpoint'],'gate_pass':True})
 print(json.dumps({'gate_pass':True,'frozen_sha256':digest,'seed':seed,'parent':decision['parent_checkpoint']}))
if __name__=='__main__':main()
