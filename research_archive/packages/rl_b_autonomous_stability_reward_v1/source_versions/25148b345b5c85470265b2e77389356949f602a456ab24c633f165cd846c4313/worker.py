"""One bounded, resumable PPO segment or one frozen physical attempt.

The copied 447-file runtime stays byte-identical. Research reward is computed
outside the original environment, leaving its saved baseline reward auditable.
"""
from pathlib import Path
import argparse, gc, gzip, hashlib, json, math, os, random, shutil, sys, time, traceback
from research_common import (ROOT, RUNTIME, HARD_STOP, NO_TRAIN, atomic, append,
    read, sha, reserve, settle, check_resources, now)
sys.path.insert(0,str(RUNTIME))
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
                  CUDA_VISIBLE_DEVICES='',IHEAR_GUARDED='1')
sys.dont_write_bytecode=True
import common
from runtime_setup import install
install()
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.buffers import RolloutBuffer
from stable_baselines3.common.logger import configure
from stable_baselines3.common.utils import get_schedule_fn
from pilot_env import PilotEnv
from checkpoints import load, save, contract, policy_hash
from functional_smoke import snapshot, state_hash
from resource_guard import Guard
from cloud_case_audit import audit
from force_audit import audit as force_audit
from native_boundary_motion_audit import audit as boundary_audit
from ready_env import completion_evidence
from rewards import transition, measurement, VERSIONS
torch.set_num_threads(1); torch.set_num_interop_threads(1)

def clean(obj): return common.clean(obj)
def write(p,obj): atomic(p,clean(obj))
def compress(run):
    records=[]
    for p in list(run.rglob('*.json'))+list(run.rglob('*.jsonl')):
        if p.stat().st_size<2*1024**2: continue
        h=sha(p); size=p.stat().st_size; dest=Path(str(p)+'.gz'); temp=Path(str(dest)+'.writing')
        with p.open('rb') as src,gzip.open(temp,'wb',compresslevel=1) as target:
            shutil.copyfileobj(src,target,length=1024**2)
        hh=hashlib.sha256()
        with gzip.open(temp,'rb') as f:
            for chunk in iter(lambda:f.read(4*1024**2),b''): hh.update(chunk)
        assert hh.hexdigest()==h,'LOSSLESS_COMPRESSION_MISMATCH'
        os.replace(temp,dest);p.unlink()
        records.append(dict(path=str(p.relative_to(run)),sha256_uncompressed=h,
                            bytes_uncompressed=size,sha256_gzip=sha(dest),roundtrip=True))
    write(run/'LOSSLESS_RAW_COMPRESSION.json',dict(files=records,all_roundtrips=True))

def independent_research_reward(rows, version):
    # Separate arithmetic from rewards.transition; consume only saved measurements.
    if version=='R0': expected=sum(x['baseline_reward'] for x in rows)
    else:
        c=VERSIONS[version]; first=rows[0]['reward_before']; last=rows[-1]['reward_after']
        phi0=first['phi']; phi1=last['phi'] if rows[-1]['success'] else 0.
        if version=='R2': phi0=phi0**2/3.;phi1=phi1**2/3.
        cost=c['force_per_Ns']*last['force']+c['moment_per_Nms']*last['moment']+c['variation']*last['variation']
        expected=c['progress']*(phi1-phi0)+(c['complete']-cost if rows[-1]['success']
                    else c['failure']-max(c['failure_floor'],cost))
    actual=sum(x['reward'] for x in rows)
    checks=dict(sum_matches=abs(actual-expected)<1e-7, finite=math.isfinite(actual),
         only_final_terminal=rows[-1]['terminal'] and not any(x['terminal'] for x in rows[:-1]),
         no_truncation=not any(x['truncated'] for x in rows),
         failed_total_negative=rows[-1]['success'] or actual<0.)
    return dict(pass_=all(checks.values()),checks=checks,expected=expected,actual=actual)

def update(model, samples, mode, out):
    n=len(samples)
    buf=RolloutBuffer(n,model.observation_space,model.action_space,device='cpu',
                      gamma=1.,gae_lambda=.95,n_envs=1)
    for s in samples:
        buf.add(s['obs'].reshape(1,-1),s['raw_action'].reshape(1,-1),np.array([s['reward']]),
                np.array([s['episode_start']]),torch.tensor([s['value']]),torch.tensor([s['logp']]))
    buf.compute_returns_and_advantage(last_values=torch.zeros(1),dones=np.array([True]))
    np.savez_compressed(out/'ppo_rollout.npz',obs=buf.observations,raw_actions=buf.actions,
         rewards=buf.rewards,values=buf.values,log_probs=buf.log_probs,advantages=buf.advantages,
         returns=buf.returns,episode_starts=buf.episode_starts)
    singleton=0
    if mode=='aggregate64':
        # Shuffle every epoch as SB3 does; merge a final singleton with its predecessor.
        def batches(batch_size=None):
            nonlocal singleton
            if not buf.generator_ready:
                for tensor in ['observations','actions','values','log_probs','advantages','returns']:
                    buf.__dict__[tensor]=buf.swap_and_flatten(buf.__dict__[tensor])
                buf.generator_ready=True
            indices=np.random.permutation(n)
            groups=[indices[i:i+16] for i in range(0,n,16)]
            if len(groups)>1 and len(groups[-1])==1:
                groups[-2]=np.concatenate([groups[-2],groups[-1]]);groups.pop()
            for ids in groups:
                singleton+=int(len(ids)==1)
                yield buf._get_samples(ids)
        buf.get=batches
    model.rollout_buffer=buf;model._current_progress_remaining=1.
    original=model.policy.optimizer.step;steps=[]
    def step(*args,**kw):
        gs=[p.grad.detach() for p in model.policy.parameters() if p.grad is not None]
        norm=float(torch.sqrt(sum((g*g).sum() for g in gs)))
        if not all(bool(torch.isfinite(g).all()) for g in gs): raise RuntimeError('NONFINITE_GRADIENT')
        before=policy_hash(model);answer=original(*args,**kw)
        steps.append(dict(postclip_gradient_l2=norm,weights_changed=before!=policy_hash(model)))
        return answer
    model.policy.optimizer.step=step
    try: model.train()
    except BaseException:
        write(out/'PARTIAL_UPDATE.json',dict(optimizer_steps=len(steps),gradients=steps,
              partial_update_not_promoted=True,restore='before_update_checkpoint plus COMPLETE_UPDATE_INPUT.json'))
        raise
    finally: model.policy.optimizer.step=original
    losses={k:float(v) for k,v in model.logger.name_to_value.items()
            if k.startswith('train/') and isinstance(v,(int,float,np.number)) and np.isfinite(v)}
    model.logger.dump(model.num_timesteps)
    if mode=='episode': singleton=4*int(n%16==1)
    result=dict(transitions=n,complete_episodes=sum(x['episode_start'] for x in samples),
                optimizer_steps=len(steps),singleton_minibatches=singleton,
                gradients=steps,losses=losses,rollout=mode,epochs=model.n_epochs)
    write(out/'UPDATE.json',result)
    append(ROOT/'UPDATE_LOG.jsonl',dict(time_utc=now(),run=str(out),**result))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    args=parser.parse_args();path=Path(args.config);cfg=read(path)
    out=RUNTIME/'jobs'/cfg['job_id'];out.mkdir(parents=True,exist_ok=False)
    os.environ['IHEAR_RUN_DIR']=str(out)
    write(out/'START.json',dict(time_utc=now(),pid=os.getpid(),config=cfg,config_sha256=sha(path),base_contract=contract()))
    model=env=guard=None; active=None;error=None;pending=[];rows=[];latest=None
    try:
        check_resources()
        interface=PilotEnv(out/'interface/env')
        model,record=load(cfg['parent_checkpoint'],interface);interface.close()
        restored=snapshot(model);checks={k:restored[k]==v for k,v in record['state_snapshot'].items()}
        write(out/'RESUME_AUDIT.json',dict(parent=cfg['parent_checkpoint'],checks=checks,
             expected=record['state_snapshot'],actual=restored,pass_=all(checks.values())))
        assert all(checks.values()),'RESTORE_POLICY_ADAM_RNG_COUNTER_MISMATCH'
        # Loading verifies the full parent state before the sole intended config edit.
        if cfg['mode']=='training':
            model.learning_rate=cfg['learning_rate'];model.lr_schedule=get_schedule_fn(cfg['learning_rate'])
            model.target_kl=cfg.get('target_kl')
        else:
            def forbidden(*a,**kw):raise RuntimeError('FROZEN_EVALUATION_FORBIDS_UPDATE')
            PPO.train=forbidden;PPO.learn=forbidden;torch.optim.Adam.step=forbidden
            torch.Tensor.backward=forbidden;torch.autograd.backward=forbidden
            torch.set_grad_enabled(False);model.policy.set_training_mode(False)
            random.seed(cfg['evaluation_rng']);np.random.seed(cfg['evaluation_rng']);torch.manual_seed(cfg['evaluation_rng'])
        model.set_logger(configure(str(out/'ppo_logs'),['csv']))
        count=cfg['episodes'] if cfg['mode']=='training' else 1
        for offset in range(count):
            index=cfg.get('start_episode',0)+offset+1
            run=out/f'episode_{index:03d}';run.mkdir();os.environ['IHEAR_RUN_DIR']=str(run)
            identity,native_before=reserve(cfg['mode'],cfg['job_id'],run,index)
            active=dict(id=identity,run=run,native=0,decisions=0,optimizer=0)
            before=snapshot(model)
            write(run/'START.json',dict(time_utc=now(),pid=os.getpid(),mode=cfg['mode'],index=index,
                   policy=before['policy'],parent=cfg['parent_checkpoint'],category='DEVELOPMENT_NOMINAL'))
            deadline=min(time.time()+300,HARD_STOP-30)
            budget=dict(hard_stop_unix=deadline,no_new_physics_after_unix=HARD_STOP-300,
                        native_steps=native_before,native_steps_hard_cap=min(50000000,native_before+165000),
                        rl_decisions=0,rl_decisions_hard_cap=128)
            guard=Guard(run,seconds=300,min_available_gib=6,min_disk_gib=10,max_output_gib=1.5).start()
            env=PilotEnv(run/'env',budget=budget,guard=guard,retain_trace=True,
                         category='DEVELOPMENT_TRAINING' if cfg['mode']=='training' else 'FROZEN_DEVELOPMENT_NOMINAL')
            environment_seed=20261020+50+index if cfg['mode']=='training' else 20261020
            obs,info=env.reset(seed=environment_seed);samples=[];initial=obs.copy()
            for step_index in range(128):
                with torch.no_grad():
                    tensor=torch.as_tensor(obs.reshape(1,-1));dist=model.policy.get_distribution(tensor)
                    mean=dist.distribution.mean.numpy()[0].copy();std=dist.distribution.stddev.numpy()[0].copy()
                    entropy=float(dist.entropy().sum());raw,value,logp=model.policy(tensor,
                              deterministic=cfg['mode']!='training' and cfg['policy_mode']=='deterministic')
                raw=raw.numpy()[0].copy();action=np.clip(raw,-1,1).astype(np.float32)
                previous=measurement(env);nxt,baseline_reward,term,trunc,info=env.step(action);after=measurement(env)
                reward,parts=transition(cfg['reward'],previous,after,term or trunc,
                                       bool(info.get('success',False)),baseline_reward)
                samples.append(dict(obs=obs.copy(),next_obs=nxt.copy(),raw_action=raw,action=action,
                    reward=float(reward),baseline_reward=float(baseline_reward),reward_parts=parts,
                    reward_before=previous,reward_after=after,value=float(value.item()),logp=float(logp.item()),
                    episode_start=step_index==0,terminal=bool(term),truncated=bool(trunc),
                    success=bool(info.get('success',False)),mean=mean,std=std,entropy=entropy))
                obs=nxt;active['decisions']=len(samples)
                if term or trunc:break
            else: raise RuntimeError('RL_DECISION_CAP')
            active['native']=int(info['native_steps_total'])
            complete=completion_evidence(env.summary,env.phases);env.close();env=None
            resource=guard.close();guard=None
            independent=audit(run);force=force_audit(run/'env/episode_0001');motion=boundary_audit(run)
            custom=independent_research_reward(samples,cfg['reward'])
            write(run/'RESEARCH_REWARD_AUDIT.json',custom)
            write(run/'RESEARCH_TRANSITIONS.json',samples)
            assert independent['pass'] and force['pass'] and motion['pass'] and custom['pass_'],'INDEPENDENT_AUDIT_FAILED'
            if info['success']!=complete:raise RuntimeError('SUCCESS_EVIDENCE_MISMATCH')
            model.num_timesteps+=len(samples) if cfg['mode']=='training' else 0
            model._episode_num+=int(cfg['mode']=='training')
            model._last_obs=obs.reshape(1,-1);model._last_episode_starts=np.array([True])
            pending.extend(samples) if cfg['mode']=='training' else None
            update_result=None
            # Keep at least two whole episodes in the terminal residual. Never
            # create a one-transition final aggregate by updating penultimately.
            aggregate_ready=(len(pending)>=64 and offset!=count-2) or offset==count-1
            if cfg['mode']=='training' and (cfg['rollout']=='episode' or aggregate_ready):
                # A recoverable generation before the first Adam step makes an
                # interrupted multi-episode update replayable without physics.
                write(run/'COMPLETE_UPDATE_INPUT.json',pending)
                old_snapshot=snapshot(model)
                save(model,run/'before_update_checkpoint',dict(seed=cfg['seed'],branch=cfg['branch'],
                     continuation_episodes=index,research_config=cfg,state_snapshot=old_snapshot,
                     phase='COMPLETE_ROLLOUT_BEFORE_ADAM',pending_complete_episodes=sum(s['episode_start'] for s in pending),
                     input_sha256=sha(run/'COMPLETE_UPDATE_INPUT.json'),parent=cfg['parent_checkpoint']))
                assert snapshot(model)==old_snapshot,'CHECKPOINT_SAVE_CHANGED_RNG_OR_MODEL'
                update_result=update(model,pending,cfg['rollout'],run)
                active['optimizer']=update_result['optimizer_steps'];pending=[]
            if cfg['mode']=='evaluation':
                after_frozen=snapshot(model)
                assert before['policy']==after_frozen['policy'] and before['optimizer']==after_frozen['optimizer'],'FROZEN_POLICY_MUTATED'
            row=dict(time_utc=now(),job_id=cfg['job_id'],branch=cfg['branch'],seed=cfg['seed'],
                index=index,mode=cfg['mode'],policy_mode=cfg.get('policy_mode','stochastic_training'),
                reward_version=cfg['reward'],run=str(run),parent=cfg['parent_checkpoint'],
                success=bool(info['success']),complete_evidence=complete,status=info['status'],
                abort_reason=info['abort_reason'],task_s=info['task_s'],native_steps=active['native'],
                task_native_steps=info['task_native_steps'],rl_decisions=len(samples),
                training_reward=sum(s['reward'] for s in samples),baseline_reward=sum(s['baseline_reward'] for s in samples),
                JF=info['force_integral_N_s'],JM=info['moment_integral_Nm_s'],
                integral_scope='COMPLETE_TASK' if complete else 'FAILED_PARTIAL_TASK',
                accepted=info['accepted'],rejections=info['rejections'],phases=info['phases'],
                fallback_events=independent['fallback_events'],native_actions=independent['native_actions'],
                actual_human_motion=independent['motion'],boundary_motion=motion,
                resources=resource,independent_audit_pass=True,
                initial_obs=initial.tolist(),policy_before=before['policy'],policy_after=policy_hash(model),
                entropy_mean=float(np.mean([s['entropy'] for s in samples])),
                mean_initial=samples[0]['mean'].tolist(),std_initial=samples[0]['std'].tolist(),
                raw_clipped_fraction=float(np.mean(np.abs([s['raw_action'] for s in samples])>1)),
                update=update_result,gradient_updates=active['optimizer'])
            rows.append(row)
            # Full generation after every episode; aggregate rollouts checkpoint only after update.
            if cfg['mode']=='training' and not pending:
                latest=out/'checkpoints'/f'episode_{index:03d}'
                meta=dict(seed=cfg['seed'],branch=cfg['branch'],training_episodes=50+index,
                    continuation_episodes=index,parent=cfg['parent_checkpoint'],research_config=cfg,
                    research_config_sha256=sha(path),research_source_sha256=sha(Path(__file__)),
                    reward_source_sha256=sha(Path(__file__).with_name('rewards.py')),
                    state_snapshot=snapshot(model),optimizer_step_calls=sum(x['gradient_updates'] for x in rows))
                save(model,latest,meta);row['checkpoint_after']=str(latest)
                write(out/'PROGRESS.json',dict(completed=index,checkpoint=str(latest),rows=len(rows)))
            write(run/'RESULT.json',row);append(ROOT/'ALL_ATTEMPTS.jsonl',row)
            settle(identity,active['native'],active['decisions'],active['optimizer'],row['status'])
            write(run/'END.json',dict(time_utc=now(),status='COMPLETE_ATTEMPT',runtime_status=row['status'],owner_joined=True))
            active=None
            compress(run);gc.collect()
            print(json.dumps(dict(job=cfg['job_id'],episode=index,success=row['success'],
                   task_s=row['task_s'],native=row['native_steps'],updates=row['gradient_updates'])),flush=True)
        write(out/'RESULT.json',dict(completed=True,config=cfg,episodes=len(rows),
              successes=sum(x['success'] for x in rows),checkpoint=str(latest) if latest else None,rows=rows))
    except BaseException as exc:
        error=dict(error=repr(exc),traceback=traceback.format_exc())
        write(out/'FAILURE.json',error)
        if active:
            partial=read(active['run']/'PARTIAL_UPDATE.json',{})
            active['optimizer']=max(active['optimizer'],partial.get('optimizer_steps',0))
            if env is not None:
                try:active['native']=max(active['native'],int(env.metrics()['native_steps_total']))
                except BaseException:pass
            try:settle(active['id'],active['native'],active['decisions'],active['optimizer'],'INFRASTRUCTURE_OR_AUDIT_FAILURE')
            except BaseException as exc2:write(out/'SETTLE_FAILURE.json',dict(error=repr(exc2)))
        if model is not None:
            try:
                write(out/'PENDING_COMPLETE_ROLLOUT.json',pending)
                save(model,out/'emergency_checkpoint',dict(state_snapshot=snapshot(model),research_config=cfg,
                    partial_attempt=True,partial_physical_transition_discarded=True,
                    pending_complete_transitions_preserved=len(pending),
                    completed_continuation_episode=rows[-1]['index'] if rows else cfg.get('start_episode',0),
                    resume_requires_explicit_offline_pending_recovery=bool(pending),parent=cfg['parent_checkpoint']))
            except BaseException as exc2:write(out/'CHECKPOINT_FAILURE.json',dict(error=repr(exc2)))
    finally:
        if env is not None:
            try:env.close()
            except BaseException as exc:write(out/'CLOSE_FAILURE.json',dict(error=repr(exc)))
        if guard is not None:guard.close()
        if active:write(active['run']/'END.json',dict(time_utc=now(),error=error,status='FAILED_ATTEMPT',owner_joined=env is None or env.thread is None))
        write(out/'END.json',dict(time_utc=now(),pid=os.getpid(),error=error,completed=error is None,
             latest_checkpoint=str(latest) if latest else None,owner_joined=env is None or env.thread is None))
    if error:raise SystemExit(1)

if __name__=='__main__':main()
