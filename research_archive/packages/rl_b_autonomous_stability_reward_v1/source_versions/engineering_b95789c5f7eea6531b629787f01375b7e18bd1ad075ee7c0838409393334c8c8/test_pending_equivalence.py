"""Exact continuous30 vs10+20 checkpoint/pending-buffer equivalence test.

Synthetic engineering only: no MuJoCo reset/step. Tests real PPO/Adam/RNG with a
nonempty carry at10, a singleton remainder, and a threshold reached at29.
"""
from pathlib import Path
import os,json
from research_common import ROOT,atomic,now,append
os.environ['IHEAR_RUN_DIR']=str(ROOT/'audit/PENDING_BUFFER_EQUIVALENCE_TEST_v1')
import worker
from worker import torch,np,PPO,RolloutBuffer,configure,load,save,snapshot
import gymnasium as gym

class InterfaceOnly(gym.Env):
    observation_space=gym.spaces.Box(-np.inf,np.inf,shape=(41,),dtype=np.float32)
    action_space=gym.spaces.Box(-1.,1.,shape=(2,),dtype=np.float32)
    def reset(self,*a,**kw):raise RuntimeError('NO_PHYSICS_ALLOWED_IN_ENGINEERING_TEST')
    def step(self,*a,**kw):raise RuntimeError('NO_PHYSICS_ALLOWED_IN_ENGINEERING_TEST')

def main():
    out=ROOT/'audit/PENDING_BUFFER_EQUIVALENCE_TEST_v1';out.mkdir(exist_ok=False)
    cfg=dict(reward='R0',rollout='aggregate64',carry_complete_pending=True,rollout_terminal_episode=30)
    model=PPO('MlpPolicy',InterfaceOnly(),n_steps=128,batch_size=16,n_epochs=4,gamma=1.,gae_lambda=.95,
           learning_rate=.0003,seed=2026102100,device='cpu',policy_kwargs=dict(net_arch=dict(pi=[32,32],vf=[32,32])))
    model._total_timesteps=40000;model._current_progress_remaining=1.
    save(model,out/'initial',dict(state_snapshot=snapshot(model),research_config=cfg,category_note='SYNTHETIC_ENGINEERING_ONLY'))
    worker.append=lambda path,obj:append(out/'SYNTHETIC_UPDATE_LOG.jsonl',obj)
    lengths=[17,16,16,16]+[2]*24+[16,1]
    finals={};details={}
    for mode in ['continuous','segmented']:
        model,meta=load(out/'initial',InterfaceOnly());assert snapshot(model)==meta['state_snapshot']
        model.set_logger(configure(str(out/mode/'logger'),['csv']))
        pending=[];updates=[];carried=0
        for episode,length in enumerate(lengths,1):
            for step in range(length):
                obs=np.zeros(41,np.float32);obs[0]=episode/30.;obs[1]=step/20.
                with torch.no_grad():raw,value,lp=model.policy(torch.tensor(obs.reshape(1,-1)))
                pending.append(dict(obs=obs,raw_action=raw.numpy()[0],reward=float((episode%3)-1) if step==length-1 else 0.,
                     value=float(value),logp=float(lp),episode_start=step==0,terminal=step==length-1))
            model.num_timesteps+=length;model._episode_num+=1
            # Reference is the original single30-job boundary rule.
            ready=((len(pending)>=64 and episode-1!=30-2) or episode-1==30-1) if mode=='continuous' else worker.aggregate_ready(len(pending),episode,30)
            if ready:
                dest=out/mode/f'episode_{episode:03d}';dest.mkdir(parents=True)
                result=worker.update(model,pending,'aggregate64',dest)
                assert result['singleton_minibatches']==0
                updates.append(dict(episode=episode,transitions=len(pending),Adam=result['optimizer_steps']))
                pending=[]
            if mode=='segmented' and episode==10:
                assert len(pending)==12
                before=snapshot(model);base=out/'split10'
                worker.save_pending_generation(model,base,dict(state_snapshot=before,research_config=cfg),pending)
                assert snapshot(model)==before
                model,meta=load(base,InterfaceOnly());assert snapshot(model)==before
                pending=worker.restore_pending(meta,cfg);carried=len(pending)
                model.set_logger(configure(str(out/mode/'resumed_logger'),['csv']))
        assert not pending and [u['episode'] for u in updates]==[4,30]
        assert [u['transitions'] for u in updates]==[65,65]
        finals[mode]=snapshot(model);details[mode]=dict(updates=updates,carried_transitions_at10=carried)
    equality={k:finals['continuous'][k]==v for k,v in finals['segmented'].items()}
    assert all(equality.values()),equality
    steps=sum(u['Adam'] for d in details.values() for u in d['updates'])
    atomic(ROOT/'audit/PENDING_BUFFER_EQUIVALENCE_TEST.json',dict(time_utc=now(),pass_=True,
        category='TEST_ONLY_SYNTHETIC_NO_MUJOCO',details=details,full_state_equality=equality,
        nonempty_pending_restore_at10=12,penultimate_threshold_held=True,singleton_batches=0,
        physical_attempts=0,native_steps=0,actual_MuJoCo_training_Adam_updates=0,
        synthetic_Adam_updates=steps,task_training_ledger_modified_by_test=False))
    print('Continuous30 equals split10+20: full policy/Adam/RNG/counters PASS; synthetic Adam',steps)
if __name__=='__main__':main()
