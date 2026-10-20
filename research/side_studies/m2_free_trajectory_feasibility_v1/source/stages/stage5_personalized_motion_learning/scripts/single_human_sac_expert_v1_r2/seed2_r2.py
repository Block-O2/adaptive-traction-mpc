"""Optional independent Seed 2, only under the user-authorized time/resource rule.

Primary frozen source/config/weights are never edited. The same R2 scientific
contract and SAC hyperparameters apply; the fresh seed's exact provenance is
frozen before initialization. Eligibility depends on budget/resources only.
"""
from pathlib import Path
import sys,time,json,csv,traceback,math
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1/source/stages/stage5_personalized_motion_learning/scripts/single_human_sac_expert_v1_r2')
sys.path.insert(0,str(P))
import campaign_r2 as c
def run():
 c.configure();import train_campaign_r2 as tc
 tc.metric_record=c.metric;tc.CURRENT_LOCK=json.loads((c.D/'SAC_CONTRACT_LOCK.json').read_text());tc.check_lock()
 config=json.loads((c.D/'SAC_TRAINING_CONFIG.json').read_text());summary=json.loads((c.D/'SAC_SEED_SUMMARY.json').read_text());first=summary['seeds'][0]
 cutoff=config['hard_wall_cutoff_unix'];train_end=cutoff-45*60;seed=20261004;target=50000
 rate=min(first['steps_s'],config['benchmark_rate']);needed=target/rate+20*60
 eligibility=dict(frozen_user_seed_rule='Seed 1 >=300k with real updates and no source/NaN/resource exception; Seed 2 >=50k only when conservative observed throughput +20min evaluation fits before original training cutoff; resource-safe one environment. Never conditioned on superior/inferior SAC J_F.',first_seed=first,seed=seed,target_steps=target,rate_used=rate,required_remaining_s=needed,remaining_s=train_end-time.time(),primary_contract_hash=tc.CURRENT_LOCK['contract_hash'],primary_configuration_hash=tc.CURRENT_LOCK['configuration_hash'],primary_sources_unchanged=True,decision_utc=c.now())
 eligible=first['completed_steps']>=300000 and first['gradient_updates']>0 and not first.get('error') and first['stop_reason'] not in ('RESOURCE_RISK','NAN_OR_NONFINITE_PARAMETERS') and train_end-time.time()>=needed and len(summary['seeds'])==1
 eligibility['eligible_before_resource_check']=eligible
 c.write(c.D/'SEED2_BUDGET_DECISION_R2.json',eligibility)
 if not eligible:print(json.dumps(dict(phase='SEED2_NOT_BUDGET_ELIGIBLE',remaining_h=(train_end-time.time())/3600,required_h=needed/3600)),flush=True);return
 if not c.resource_check('before_optional_seed2'):return
 c.write(c.D/'SEED2_CONFIGURATION_R2.json',{**config,'seeds':[seed],'planned_steps':[target],'seed1_checkpoint_not_used':True,'seed1_replay_not_used':True,'benchmark_data_not_used':True,'stage':'Optional independent Seed 2 under unchanged primary R2 scientific contract','primary_configuration_hash':tc.CURRENT_LOCK['configuration_hash']})
 # Reuse only scalar evidence for joint reporting, never weights or replay.
 tc.EVAL_ROWS[:]=[json.loads(p.read_text()) for p in sorted(c.D.glob('EVALUATION_*.json'))]
 if (c.D/'SAC_LEARNING_CURVE.csv').exists():
  with (c.D/'SAC_LEARNING_CURVE.csv').open() as f:tc.LEARNING_ROWS[:]=list(csv.DictReader(f))
 tc.BEST.update(json.loads((c.D/'SAC_BEST_CANDIDATES.json').read_text()) if (c.D/'SAC_BEST_CANDIDATES.json').exists() else {})
 case,options=c.load_case_options();env=c.SACExpertEnv(c.O/f'seed_{seed}'/'training',case,options,.02,retain_trace=False)
 kwargs={k:config[k] for k in ('learning_rate','batch_size','buffer_size','learning_starts','train_freq','gradient_steps','gamma','tau','ent_coef','target_entropy','replay_buffer_kwargs')}
 model=tc.SAC('MlpPolicy',env,device='cuda',policy_kwargs=dict(net_arch=config['network']),seed=seed,verbose=0,**kwargs)
 callback=tc.CampaignCallback(seed,train_end,config);start=time.monotonic();error=None
 c.q.status('INDEPENDENT_SEED2_START',status='FORMAL_TRAINING',current_seed=seed,current_seed_steps=0,formal_training_started=True)
 try:model.learn(total_timesteps=target,callback=callback)
 except Exception as e:error=dict(error=str(e),traceback=traceback.format_exc());c.write(c.D/f'SEED_{seed}_EXCEPTION.json',error)
 finally:
  checkpoint=c.O/f'seed_{seed}'/f'step_{model.num_timesteps:07d}';checkpoint.parent.mkdir(parents=True,exist_ok=True);model.save(checkpoint);model.save_replay_buffer(c.O/f'seed_{seed}'/'final_replay_buffer.pkl');env.close()
 wall=time.monotonic()-start;row=dict(seed=seed,planned_steps=target,completed_steps=model.num_timesteps,wall_s=wall,steps_s=model.num_timesteps/max(1.,wall),stop_reason=callback.stop_reason or ('EXCEPTION' if error else 'PLANNED_BOUNDED_BUDGET'),gradient_updates=model._n_updates,formal=True,checkpoint=str(checkpoint.relative_to(c.R))+'.zip',error=error,configuration_stage='SEED2_CONFIGURATION_R2.json')
 summary['seeds'].append(row);summary['total_steps']=sum(x['completed_steps'] for x in summary['seeds']);c.write(c.D/'SAC_SEED_SUMMARY.json',summary)
 if error is None and model.num_timesteps!=callback.last_eval and time.time()<cutoff-15*60:
  tc.evaluate(model,seed,model.num_timesteps,'NATIVE','final');tc.evaluate(model,seed,model.num_timesteps,'MATCHED','final')
 if error is None:tc.save_final_profile(model,str(checkpoint.relative_to(c.R))+'.zip')
 confirmations=json.loads((c.D/'SAC_BEST_CONFIRMATION.json').read_text()) if (c.D/'SAC_BEST_CONFIRMATION.json').exists() else {}
 for scope,best in tc.BEST.items():
  if best['seed']!=seed:continue
  model=tc.SAC.load(c.O/f'seed_{seed}'/f'step_{best["training_step"]:07d}.zip',device='cuda')
  if model.replay_buffer is None:
   from stable_baselines3.common.buffers import ReplayBuffer
   model.replay_buffer=ReplayBuffer(1,model.observation_space,model.action_space,device='cuda',handle_timeout_termination=False)
  replays=[]
  for i in range(2):
   if time.time()>=cutoff-5*60:break
   replays.append(tc.evaluate(model,seed,best['training_step'],scope,f'confirmation_{i+1}'))
  confirmations[scope]=dict(pass_=len(replays)==2 and all(r['valid'] and abs(r['J_F']-best['J_F'])<=tc.REPLAY_TOLERANCE for r in replays),selected=best,replays=replays,tolerance_n_s=tc.REPLAY_TOLERANCE)
  c.write(c.D/'SAC_BEST_CONFIRMATION.json',confirmations)
 tc.check_lock();c.q.status('FORMAL_CAMPAIGN_FINISHED_PENDING_REPORT',training_steps=summary['total_steps'],seed_summaries=summary['seeds'],next_action='Closeout scientific interpretation, immutable R1/index verification, individually stage R2 evidence, STOP.')
 print(json.dumps(row),flush=True)
if __name__=='__main__':run()
