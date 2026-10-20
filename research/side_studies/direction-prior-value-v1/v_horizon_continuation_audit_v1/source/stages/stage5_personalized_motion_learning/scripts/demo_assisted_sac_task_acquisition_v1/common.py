"""Versioned orchestration only; the R2 scientific implementation is immutable."""
from pathlib import Path
import sys, os, json, time, hashlib, pickle, random, csv, shutil, subprocess
import numpy as np
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/v_horizon_continuation_audit_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
NAME='demo_assisted_sac_task_acquisition_v1'
D=S/'docs'/NAME; O=S/'results'/NAME; P=S/'scripts'/NAME; L=W/NAME/'output'
OLD=S/'docs/single_human_sac_expert_v1/r2'
DIAG=S/'docs/single_human_sac_seed1_300k_failure_diagnosis_v1'
SEED=20261003; TARGET=50000; BRANCH='codex/demo-assisted-sac-task-acquisition-v1'
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'))
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1_r2'))
sys.path.insert(0,str(W/'single_human_sac_memory'))
import memory_test_v1 as memory
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.buffers import ReplayBuffer
from stable_baselines3.common.type_aliases import ReplayBufferSamples
from sac_env import SACExpertEnv, load_case_options, SCALES, feature_spec
import campaign_r2 as r2
torch.set_num_threads(1)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,Path):return str(x)
    return x
def save(name,x):
    data=json.dumps(clean(x),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n'
    for folder in (D,L):
        tmp=folder/(name+'.tmp');tmp.write_text(data);tmp.replace(folder/name)
def prose(name,text):
    for folder in (D,L):(folder/name).write_text(text,encoding='utf-8')
def append(name,row):
    for folder in (D,L):
        with (folder/name).open('a') as f:f.write(json.dumps(clean(row),allow_nan=False)+'\n')
def table(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    for folder in (D,L):
        with (folder/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,keys);writer.writeheader()
            writer.writerows([{k:json.dumps(clean(v)) if isinstance(v,(dict,list)) else clean(v) for k,v in r.items()} for r in rows])
def rng():return dict(random=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all())
def restore(x):
    random.setstate(x['random']);np.random.set_state(x['numpy']);torch.set_rng_state(x['torch'].cpu());torch.cuda.set_rng_state_all([v.cpu() for v in x['cuda']])
def policy_hash(model):
    h=hashlib.sha256()
    for k,v in model.policy.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()
def check_lock():
    lock=json.loads((D/'SCIENTIFIC_LOCK.json').read_text())
    for p,h in lock['files'].items():assert sha(R/p)==h,'R2 changed: '+p
    return lock
def phase_counts(obs):
    a=np.asarray(obs).reshape(-1,55)[:,41:44]
    assert np.allclose(a.sum(1),1)
    return np.bincount(a.argmax(1),minlength=3).astype(int)
def phases(obs):return dict(zip(('OUTBOUND','HOLD','RETURN'),phase_counts(obs).tolist()))

class ImmutableDemo(ReplayBuffer):
    def freeze(self):
        self.frozen=True
        for k in ('observations','next_observations','actions','rewards','dones','timeouts'):getattr(self,k).flags.writeable=False
    def add(self,*args,**kwargs):
        if getattr(self,'frozen',False):raise RuntimeError('IMMUTABLE_DEMO_ADD_FORBIDDEN')
        return super().add(*args,**kwargs)
    def __setstate__(self,state):
        self.__dict__.update(state)
        if getattr(self,'frozen',False):self.freeze()

class PairedReplay(ReplayBuffer):
    """Independent immutable demo and online storage. Original SB3 SAC.train untouched."""
    def __init__(self,*args,demo_path=None,arm='A',sampler_seed=SEED,**kwargs):
        super().__init__(*args,**kwargs);self.arm=arm
        self.sampler_rng=np.random.default_rng(sampler_seed)
        self.demo=None;self.calls=0;self.demo_sample_counts=np.zeros(3,np.int64);self.online_sample_counts=np.zeros(3,np.int64)
        self.last_batch=None;self.log_path=None;self.online_steps=0
        if demo_path:
            z=np.load(demo_path);self.demo=ImmutableDemo(len(z['rewards']),self.observation_space,self.action_space,device=self.device,handle_timeout_termination=False)
            for i in range(len(z['rewards'])):
                self.demo.add(z['observations'][i:i+1],z['next_observations'][i:i+1],z['actions'][i:i+1],z['rewards'][i:i+1],np.array([z['terminated'][i] or z['truncated'][i]]),[{}])
            self.demo.freeze()
    def add(self,*args,**kwargs):
        super().add(*args,**kwargs);self.online_steps+=1
    def sample(self,batch_size,env=None):
        assert env is None and batch_size==256
        assert self.online_steps>5000,'Learning must use online count, never demos'
        nd=128 if self.demo else 0;no=batch_size-nd
        # A retains SB3's exact original uniform sampler and global RNG semantics.
        oi=np.random.randint(0,self.size(),size=no)
        online=self._get_samples(oi,env=None)
        op=phase_counts(self.observations[oi]);dp=np.zeros(3,np.int64)
        if self.demo:
            di=self.sampler_rng.integers(0,self.demo.size(),size=nd)
            demo=self.demo._get_samples(di,env=None);dp=phase_counts(self.demo.observations[di])
            batch=ReplayBufferSamples(*(torch.cat((d,o),dim=0) for d,o in zip(demo,online)))
        else:batch=online
        self.calls+=1;self.demo_sample_counts+=dp;self.online_sample_counts+=op;self.last_batch=batch
        if self.log_path:
            with Path(self.log_path).open('a',newline='') as f:
                csv.writer(f).writerow([self.calls,self.online_steps,nd,no,nd/batch_size,*dp.tolist(),*op.tolist()])
        return batch
    def __getstate__(self):
        state=self.__dict__.copy();state['last_batch']=None;return state

def make_model(env,arm,config):
    keys=('learning_rate','batch_size','buffer_size','learning_starts','train_freq','gradient_steps','gamma','tau','ent_coef','target_entropy')
    return SAC('MlpPolicy',env,device='cuda',policy_kwargs=dict(net_arch=config['network']),seed=SEED,verbose=0,
        replay_buffer_class=PairedReplay,replay_buffer_kwargs=dict(handle_timeout_termination=False,arm=arm,demo_path=str(O/'NATIVE_DEMO.npz') if arm=='B' else None),**{k:config[k] for k in keys})
