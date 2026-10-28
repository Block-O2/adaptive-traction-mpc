"""Synthetic engineering test: boundaries, no sample loss, no singleton batches.

No physical environment is reset; synthetic Adam updates are labelled separately
and never presented as MuJoCo training or task-success evidence.
"""
from pathlib import Path
import os,sys,json
from research_common import ROOT,atomic,now
os.environ['IHEAR_RUN_DIR']=str(ROOT/'audit/H2_SYNTHETIC_TEST')
import worker
import numpy as np,torch,gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.buffers import RolloutBuffer
from stable_baselines3.common.logger import configure

class InterfaceOnly(gym.Env):
    observation_space=gym.spaces.Box(-np.inf,np.inf,shape=(41,),dtype=np.float32)
    action_space=gym.spaces.Box(-1.,1.,shape=(2,),dtype=np.float32)
    def reset(self,*a,**kw):raise RuntimeError('SYNTHETIC_TEST_FORBIDS_ENVIRONMENT_RESET')
    def step(self,*a,**kw):raise RuntimeError('SYNTHETIC_TEST_FORBIDS_ENVIRONMENT_STEP')

def main():
    out=ROOT/'audit/H2_SYNTHETIC_TEST';out.mkdir(exist_ok=False)
    model=PPO('MlpPolicy',InterfaceOnly(),n_steps=128,batch_size=16,n_epochs=4,gamma=1.,
          gae_lambda=.95,learning_rate=.0003,device='cpu',seed=2026102100,
          policy_kwargs=dict(net_arch=dict(pi=[32,32],vf=[32,32])))
    model._total_timesteps=40000;model.set_logger(configure(str(out/'logger'),['csv']))
    samples=[];lengths=[1,16,48];start=0
    for length in lengths:
        for i in range(length):
            idx=len(samples);obs=np.zeros(41,np.float32);obs[0]=idx/100.
            with torch.no_grad():raw,val,lp=model.policy(torch.tensor(obs.reshape(1,-1)))
            samples.append(dict(obs=obs,raw_action=raw.numpy()[0],reward=float((idx%3)-1),
                      value=float(val),logp=float(lp),episode_start=i==0))
        start+=length
    captured=[];orig=RolloutBuffer._get_samples
    def capture(self,indices,*args,**kwargs):
        captured.append(np.asarray(indices).copy());return orig(self,indices,*args,**kwargs)
    RolloutBuffer._get_samples=capture
    worker.append=lambda path,obj: atomic(out/'TEST_ONLY_UPDATE.json',obj)
    try:result=worker.update(model,samples,'aggregate64',out)
    finally:RolloutBuffer._get_samples=orig
    z=np.load(out/'ppo_rollout.npz');expected=np.zeros(65);cursor=0
    for length in lengths:
        gae=0.
        for i in range(cursor+length-1,cursor-1,-1):
            next_value=0. if i==cursor+length-1 else samples[i+1]['value']
            delta=samples[i]['reward']+next_value-samples[i]['value']
            gae=delta+.95*gae;expected[i]=gae
        cursor+=length
    assert np.max(np.abs(z['advantages'][:,0]-expected))<2e-6
    assert len(captured)==16
    for epoch in range(4):
        seen=np.concatenate(captured[epoch*4:(epoch+1)*4])
        assert np.array_equal(np.sort(seen),np.arange(65))
    assert all(len(ids)>1 for ids in captured)
    assert sorted(map(len,captured))==[16]*12+[17]*4
    assert result['singleton_minibatches']==0 and result['transitions']==65
    assert all(x['weights_changed'] and np.isfinite(x['postclip_gradient_l2']) for x in result['gradients'])
    atomic(ROOT/'audit/H2_AGGREGATION_ENGINEERING_TEST.json',dict(time_utc=now(),pass_=True,
        category='TEST_ONLY_SYNTHETIC_NO_PHYSICS',physical_attempts=0,native_steps=0,
        synthetic_Adam_updates=result['optimizer_steps'],actual_MuJoCo_training_Adam_updates=0,
        episodes_lengths=lengths,every_transition_once_per_epoch=True,episode_terminal_GAE_independent=True,
        no_singleton_minibatches=True,all_epochs_four=True,finite_nonzero_updates=True,
        scope='Engineering buffer test only; no scientific task success or safety qualification'))
    print('H2 engineering PASS: 65 samples, 3 complete-episode boundaries, 4 epochs, no missing/singleton samples; synthetic Adam updates',result['optimizer_steps'])
if __name__=='__main__':main()
