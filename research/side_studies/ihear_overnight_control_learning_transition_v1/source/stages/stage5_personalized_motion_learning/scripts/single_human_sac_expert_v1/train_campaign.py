"""Bounded, frozen-contract SB3 SAC CUDA campaign; evaluations never update learning."""
import sys,time,json,math,hashlib,subprocess,traceback,resource,copy,datetime,csv,gzip,shutil
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from qualify import *
from final_qualification import metric_record,compact_archive
from throughput import distribution
torch.set_num_threads(1)
REPLAY_TOLERANCE=1e-6
EVAL_ROWS=[];LEARNING_ROWS=[];BEST={};CURRENT_LOCK=None
def check_lock():
    for name,h in CURRENT_LOCK['files'].items():
        if sha(R/name)!=h:raise RuntimeError('CONTRACT_OR_SOURCE_CORRUPTION:'+name)
def lock_and_budget():
    assert json.loads((D/'STATE.json').read_text())['phase']=='ALL_QUALIFICATION_GATES_PASS'
    assert json.loads((D/'SAC_REWARD_AUDIT.json').read_text())['status']=='PASS'
    assert json.loads((D/'SAC_RESET_STRESS.json').read_text())['status']=='PASS'
    assert json.loads((D/'SAC_COMPARATOR_TABLE.json').read_text())['status']=='PASS'
    throughput=json.loads((D/'SAC_THROUGHPUT.json').read_text());assert throughput['status']=='PASS'
    rate=throughput['sac']['agent_steps_s']
    cutoff=datetime.datetime.fromisoformat('2026-10-03T03:55:00+00:00').timestamp();train_end=cutoff-45*60
    available=max(0.,train_end-time.time());feasible=math.floor(rate*available)
    eval_s=max(120.,2*throughput['deterministic_evaluation']['wall_s'])
    for _ in range(3):feasible=max(0,math.floor(rate*(available-math.ceil(feasible/25000)*eval_s)))
    if feasible>=1000000:targets=[500000,500000]
    elif feasible>=600000:targets=[500000,100000]
    elif feasible>=350000:
        second=max(50000,math.floor(.2*feasible));targets=[min(500000,feasible-second),second]
    else:
        second=min(50000,max(10000,math.floor(.2*feasible)));targets=[max(0,feasible-second),second]
    if targets[0]<10000:raise RuntimeError('INSUFFICIENT_WALL_BUDGET_AFTER_QUALIFICATION')
    config=json.loads((D/'SAC_TRAINING_CONFIG.json').read_text());config.update(status='FROZEN_FORMAL',gamma=gamma_for(.02),policy_period_s=.02,version='sb3_2.6.0_final_v1',planned_steps=targets,hard_wall_cutoff_utc='2026-10-03T03:55:00Z',training_cutoff_utc=datetime.datetime.fromtimestamp(train_end,datetime.timezone.utc).isoformat(),seed2_reserved_wall_s=targets[1]/rate,benchmark_rate=rate)
    save('SAC_TRAINING_CONFIG.json',config)
    contract=json.loads((D/'SAC_EXPERT_V1_CONTRACT.json').read_text());contract.update(status='FROZEN_FORMAL',formal_frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),training=config)
    reference=json.loads((D/'RUN_reference_20ms_NATIVE.json').read_text());matched_reference=json.loads((D/'RUN_final_reference_20ms_MATCHED.json').read_text())
    contract['discount'].update(native_reference_decisions=reference['steps'],matched_reference_decisions=matched_reference['steps'],nominal_matched_decisions=950,max_decisions_conservative=1506,candidate_complete_task_weights={str(g):dict(native=float(g**reference['steps']),matched=float(g**matched_reference['steps'])) for g in (.99,.995,.999,.9995,.9999,gamma_for(.02))},selected_complete_task_weights=dict(native=float(gamma_for(.02)**reference['steps']),matched=float(gamma_for(.02)**matched_reference['steps'])))
    contract['budget'].update(planned_seed_steps=targets,rate_used=rate,phase_policy='Fresh initialization of each seed, no curriculum. Wall cap/NaN/resource/source-corruption stop. Seed 1 reserves Seed 2 observed ETA; after >=300k, stop on four valid native evaluations with <1 N s improvement. No undocumented tuning or mixed contract versions.',selected_feasible_steps=feasible,checkpoint_interval_steps=25000,independent_confirmation_J_F_tolerance_n_s=REPLAY_TOLERANCE)
    save('SAC_EXPERT_V1_CONTRACT.json',contract)
    protected=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text())
    files={**protected['protected_files'],**protected['historical_docs'],**protected['dirty_source']}
    for p in (P/'sac_env.py',P/'qualify.py',P/'final_qualification.py',P/'train_campaign.py',S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py',D/'SAC_EXPERT_V1_CONTRACT.json',D/'SAC_TRAINING_CONFIG.json',D/'SAC_OBSERVATION_NORMALIZATION.json'):files[str(p.relative_to(R))]=sha(p)
    ref=json.loads((D/'RUN_reference_20ms_NATIVE.json').read_text())
    lock=dict(files=files,contract_hash=sha(D/'SAC_EXPERT_V1_CONTRACT.json'),configuration_hash=sha(D/'SAC_TRAINING_CONFIG.json'),frozen_model_hash=ref['model_hash'],frozen_model=ref['frozen_model'],task_hash=sha(S/'configs/high_rom_v1/stage5_goal_task_120_v1.json'),condition_hash=sha(S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'),normalization_hash=sha(D/'SAC_OBSERVATION_NORMALIZATION.json'),user_request_hash=sha(D/'USER_REQUEST.txt'),source_head=json.loads((D/'GIT_PREFLIGHT.json').read_text())['head'],branch='codex/single-human-sac-expert-v1')
    save('SAC_CONTRACT_LOCK.json',lock)
    return config,lock,train_end
def evaluate(model,seed,step,scope,tag='periodic'):
    check_lock();case,options=load_case_options();out=O/'evaluation'/f'seed_{seed}_step_{step:07d}_{scope}_{tag}'
    env=SACExpertEnv(out,case,options,.02,scope,True);was_training=model.policy.training;model.policy.set_training_mode(False)
    replay_size=model.replay_buffer.size();updates=model._n_updates
    try:
        obs,info=env.reset(seed=20261003);assert env.model_hash==CURRENT_LOCK['frozen_model_hash']
        inference=[]
        for k in range(1600):
            started=time.perf_counter_ns()
            with torch.no_grad():action,_=model.predict(obs,deterministic=True)
            inference.append((time.perf_counter_ns()-started)/1e6)
            obs,reward,terminated,truncated,info=env.step(action)
            if terminated or truncated:break
        if env.summary is None:raise RuntimeError('EVALUATION_NO_COMPLETE_TERMINAL_RESULT')
        record=metric_record(env,'SAC',scope)
        record.update(seed=seed,training_step=step,tag=tag,checkpoint=f'seed_{seed}/step_{step:07d}.zip',learning_frozen=True,exploration=False,replay_unchanged=model.replay_buffer.size()==replay_size,gradient_updates_unchanged=model._n_updates==updates,normalization_updates=False,contract_hash=CURRENT_LOCK['contract_hash'],model_hash=env.model_hash,task_hash=CURRENT_LOCK['task_hash'],normalization_hash=CURRENT_LOCK['normalization_hash'],actor_inference_ms=distribution(inference),full_chain_ms=distribution([r['full_chain_ms'] for r in env.action_records]),reference_ready_validation_ms=distribution([r['realization_validation_ms'] for r in env.action_records]))
        np.testing.assert_allclose(record['model_beta'],CURRENT_LOCK['frozen_model']['beta'],atol=1e-12,rtol=0)
        assert record['replay_unchanged'] and record['gradient_updates_unchanged']
        save(f'EVALUATION_seed_{seed}_step_{step:07d}_{scope}_{tag}.json',record)
        EVAL_ROWS.append(record);table('SAC_CHECKPOINT_EVALUATION.csv',[{k:r.get(k) for k in ('seed','training_step','scope','tag','status','valid','matched_timing_valid','J_F','force_mean','force_rms','force_peak','moment_integral','moment_peak','duration_s','clearance','physical_clearance','rejections','modification_fraction','trace','trace_sha256','checkpoint','contract_hash','model_hash','task_hash')} for r in EVAL_ROWS])
        if record['valid'] and (scope not in BEST or record['J_F']<BEST[scope]['J_F']):BEST[scope]=record
        save('SAC_BEST_CANDIDATES.json',BEST)
        print(json.dumps({k:record.get(k) for k in ('seed','training_step','scope','status','valid','J_F','force_peak','moment_peak','duration_s','rejections')}),flush=True)
        return record
    finally:
        compact_archive(env);env.close();model.policy.set_training_mode(was_training)
class CampaignCallback(BaseCallback):
    def __init__(self,seed,end_unix,config):
        super().__init__();self.seed=seed;self.end_unix=end_unix;self.config=config;self.begin=time.monotonic();self.last_state=0;self.last_eval=0;self.stop_reason=None;self.native_history=[];self.episodes=0
    def _on_step(self):
        info=self.locals['infos'][0];step=self.model.num_timesteps
        if info.get('model_hash')!=CURRENT_LOCK['frozen_model_hash']:raise RuntimeError('FROZEN_MODEL_RESET_MISMATCH')
        if self.locals['dones'][0]:
            self.episodes+=1
            row=dict(seed=self.seed,training_step=step,episode=self.episodes,causal_task_complete=info.get('success'),status=info.get('status'),abort_reason=info.get('abort_reason'),J_F_unranked=info.get('J_F'),episode_return=info.get('reward_total'),force_peak=info.get('force_peak'),moment_peak=info.get('moment_peak'),duration_s=info.get('duration_s'),rejections=info.get('rejections'),steps=info.get('steps'),episode_host_s=info.get('host_s'),wall_s=time.monotonic()-self.begin,steps_s=step/max(1e-12,time.monotonic()-self.begin),independent_physical_rank=False)
            row.update(minimum_clearance_m=info.get('minimum_clearance_m'),physical_rom_violation_steps_evaluation_only=info.get('physical_rom_violation_steps_evaluation_only'),physical_contact_steps_evaluation_only=info.get('physical_contact_steps_evaluation_only'),fallbacks=info.get('fallbacks'),action_evidence=info.get('action_evidence'),reward_decomposition=info.get('reward_totals'),physical_success_rank=info.get('physical_success_rank'))
            LEARNING_ROWS.append(row);table('SAC_LEARNING_CURVE.csv',LEARNING_ROWS)
        if step-self.last_state>=250:
            self.last_state=step;check_lock();rss=Process().memory_info().rss
            memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines());available=int(memory['MemAvailable'].split()[0])*1024;total=int(memory['MemTotal'].split()[0])*1024
            losses={k:float(v) for k,v in self.model.logger.name_to_value.items() if k.startswith('train/') and np.isscalar(v)}
            if any(not np.isfinite(v) for v in losses.values()) or any(not bool(torch.isfinite(p).all().item()) for p in self.model.policy.parameters()):self.stop_reason='NAN_OR_NONFINITE_PARAMETERS';return False
            if rss>.70*total or available<1024**3:self.stop_reason='RESOURCE_RISK';return False
            status('FORMAL_TRAINING',status='FORMAL_TRAINING',formal_training_started=True,current_seed=self.seed,training_steps=sum(r.get('completed_steps',0) for r in json.loads((D/'SAC_SEED_SUMMARY.json').read_text()).get('seeds',[])) +step if (D/'SAC_SEED_SUMMARY.json').exists() else step,current_seed_steps=step,current_seed_wall_s=time.monotonic()-self.begin,observed_steps_s=step/(time.monotonic()-self.begin),rss_bytes=rss,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,losses=losses,next_action='Continue frozen-contract SAC until planned budget, convergence rule or wall/resource stop; independent deterministic evaluation every 25k.')
            print(json.dumps(dict(seed=self.seed,steps=step,steps_s=round(step/(time.monotonic()-self.begin),3),rss_mb=round(rss/2**20,1),episodes=self.episodes)),flush=True)
        if time.time()>=self.end_unix:self.stop_reason='BOUNDED_WALL_BUDGET';return False
        if step-self.last_eval>=25000:
            self.last_eval=step;checkpoint=O/f'seed_{self.seed}'/f'step_{step:07d}';checkpoint.parent.mkdir(parents=True,exist_ok=True);self.model.save(checkpoint)
            status('INDEPENDENT_CHECKPOINT_EVALUATION',current_seed=self.seed,current_seed_steps=step,next_action='Freeze learning and independently evaluate native and matched complete-task performance.')
            native=evaluate(self.model,self.seed,step,'NATIVE');evaluate(self.model,self.seed,step,'MATCHED');self.native_history.append(native)
            if step>=300000 and len(self.native_history)>=4:
                last=self.native_history[-4:]
                if all(r['valid'] for r in last) and max(r['J_F'] for r in last)-min(r['J_F'] for r in last)<1.:self.stop_reason='VALID_EVALUATION_PLATEAU';return False
        return True
def save_final_profile(model,checkpoint):
    profile=json.loads((D/'SAC_RUNTIME_PROFILE.json').read_text());raw=torch.zeros((1,55),device=model.device);actors=[('cuda',model.actor,raw),('cpu',copy.deepcopy(model.actor).to('cpu'),raw.cpu())]
    result=dict(checkpoint=checkpoint,scope='Final saved formal policy; hardware realtime not qualified')
    for device,actor,tensor in actors:
        values=[]
        with torch.no_grad():
            for i in range(1100):
                if device=='cuda':torch.cuda.synchronize()
                start=time.perf_counter_ns();actor(tensor,deterministic=True)
                if device=='cuda':torch.cuda.synchronize()
                if i>=100:values.append((time.perf_counter_ns()-start)/1e6)
        result[f'actor_{device}_ms']=distribution(values)
    profile['formal_final_policy']=result;save('SAC_RUNTIME_PROFILE.json',profile)
def run():
    global CURRENT_LOCK
    config,CURRENT_LOCK,train_end=lock_and_budget();check_lock();assert torch.cuda.is_available()
    summaries=[];models={}
    status('FORMAL_TRAINING_START',status='FORMAL_TRAINING',formal_training_started=True,training_steps=0,contract_hash=CURRENT_LOCK['contract_hash'])
    for index,(seed,target) in enumerate(zip(config['seeds'],config['planned_steps'])):
        check_lock();case,options=load_case_options();env=SACExpertEnv(O/f'seed_{seed}'/'training',case,options,.02,retain_trace=False)
        kwargs={k:config[k] for k in ('learning_rate','batch_size','buffer_size','learning_starts','train_freq','gradient_steps','gamma','tau','ent_coef','target_entropy','replay_buffer_kwargs')}
        model=SAC('MlpPolicy',env,device='cuda',policy_kwargs=dict(net_arch=config['network']),seed=seed,verbose=0,**kwargs);assert model.device.type=='cuda'
        reserve=config['seed2_reserved_wall_s'] if index==0 else 0.
        end_unix=train_end-reserve;callback=CampaignCallback(seed,end_unix,config);start=time.monotonic();error=None
        try:model.learn(total_timesteps=target,callback=callback)
        except Exception as ex:
            error=dict(error=str(ex),traceback=traceback.format_exc());save(f'SEED_{seed}_EXCEPTION.json',error)
        finally:
            checkpoint=O/f'seed_{seed}'/f'step_{model.num_timesteps:07d}';checkpoint.parent.mkdir(parents=True,exist_ok=True);model.save(checkpoint);model.save_replay_buffer(O/f'seed_{seed}'/'final_replay_buffer.pkl');env.close()
        wall=time.monotonic()-start;summary=dict(seed=seed,planned_steps=target,completed_steps=model.num_timesteps,wall_s=wall,steps_s=model.num_timesteps/max(1.,wall),stop_reason=callback.stop_reason or ('EXCEPTION' if error else 'PLANNED_BOUNDED_BUDGET'),gradient_updates=model._n_updates,formal=True,checkpoint=str(checkpoint.relative_to(R))+'.zip',error=error)
        summaries.append(summary);save('SAC_SEED_SUMMARY.json',dict(seeds=summaries,planned=config['planned_steps'],total_steps=sum(x['completed_steps'] for x in summaries)))
        # A final independent evaluation is required even for a partial seed.
        if time.time()<train_end+20*60 and error is None and model.num_timesteps!=callback.last_eval:
            evaluate(model,seed,model.num_timesteps,'NATIVE','final');evaluate(model,seed,model.num_timesteps,'MATCHED','final')
        if error is None:save_final_profile(model,str(checkpoint.relative_to(R))+'.zip')
        models[seed]=(checkpoint,model.num_timesteps)
        if error is not None or callback.stop_reason in ('NAN_OR_NONFINITE_PARAMETERS','RESOURCE_RISK'):break
        del model
        if time.time()>=train_end:break
    status('BEST_CHECKPOINT_CONFIRMATION',next_action='Independently reload and replay best valid policy from the same frozen initial condition; preserve failed confirmations.')
    confirmations={}
    for scope,best in list(BEST.items()):
        seed=best['seed'];step=best['training_step'];path=O/f'seed_{seed}'/f'step_{step:07d}.zip';model=SAC.load(path,device='cuda')
        # Loaded model's empty replay storage is never updated during evaluation.
        if model.replay_buffer is None:
            from stable_baselines3.common.buffers import ReplayBuffer
            model.replay_buffer=ReplayBuffer(1,model.observation_space,model.action_space,device='cuda',handle_timeout_termination=False)
        records=[]
        for i in range(2):
            if time.time()>=datetime.datetime.fromisoformat('2026-10-03T03:50:00+00:00').timestamp():break
            records.append(evaluate(model,seed,step,scope,f'confirmation_{i+1}'))
        passed=len(records)==2 and all(r['valid'] and abs(r['J_F']-best['J_F'])<=REPLAY_TOLERANCE for r in records)
        confirmations[scope]=dict(pass_=passed,selected=best,replays=records,tolerance_n_s=REPLAY_TOLERANCE)
        save('SAC_BEST_CONFIRMATION.json',confirmations);save_final_profile(model,str(path.relative_to(R)))
        del model
    check_lock();status('FORMAL_CAMPAIGN_FINISHED_PENDING_REPORT',training_steps=sum(x['completed_steps'] for x in summaries),seed_summaries=summaries,next_action='Scientific interpretation, comparator table and provenance verification; individually stage new compact evidence; STOP.')
if __name__=='__main__':
    try:run()
    except Exception as error:
        save('FORMAL_CAMPAIGN_EXCEPTION.json',dict(error=str(error),traceback=traceback.format_exc()))
        status('CAMPAIGN_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_PARTIAL',blocker=str(error),next_action='Preserve checkpoints and learning/evaluation evidence; close out scientific report. No further algorithms.')
        print(traceback.format_exc(),flush=True)
