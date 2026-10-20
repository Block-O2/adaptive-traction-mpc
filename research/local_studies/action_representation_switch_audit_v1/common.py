from pathlib import Path
import sys, os, json, hashlib, time, subprocess, random
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
S=R/'stages/stage5_personalized_motion_learning'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
NAME='action_representation_switch_audit_v1'
P=W/NAME; O=P/'output'
BC=S/'docs/bc_reproduction_gate_v1'
DEMO=S/'results/demo_assisted_sac_task_acquisition_v1/NATIVE_DEMO.npz'
TEACHER=S/'results/bc_reproduction_gate_v1/teacher_reference/episode_00001'
for p in (S/'scripts/single_human_sac_expert_v1',S/'scripts/single_human_sac_expert_v1_r2'):
    sys.path.insert(0,str(p))
from sac_env import SACExpertEnv, load_case_options, SCALES, feature_spec
import campaign_r2 as r2
import torch
from stable_baselines3.sac.policies import Actor
from stable_baselines3.common.torch_layers import FlattenExtractor
import gymnasium as gym
torch.set_num_threads(1)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,Path):return str(v)
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def save(n,v):
    O.mkdir(exist_ok=True);(O/n).write_text(json.dumps(clean(v),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(n):return json.loads((O/n).read_text())
def actor(seed,device='cpu'):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    ob=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32);ac=gym.spaces.Box(-1.,1.,(2,),np.float32)
    a=Actor(ob,ac,[256,256],FlattenExtractor(ob),55,torch.nn.ReLU).to(device)
    a.log_std.requires_grad_(False);return a
def error(pred,target):
    e=np.asarray(pred,float)-np.asarray(target,float)
    return dict(n=len(e),MAE=np.mean(abs(e)),RMSE=np.sqrt(np.mean(e*e)),max_error=np.max(abs(e)),per_joint_MAE=np.mean(abs(e),axis=0),per_joint_RMSE=np.sqrt(np.mean(e*e,axis=0)))
def lock():
    for p,h in read('SOURCE_LOCK.json').items():assert sha(R/p)==h,'SOURCE_DRIFT:'+p
def resources(tag):
    sys.path.insert(0,str(W/'single_human_sac_memory'))
    import memory_test_v1 as m
    proc=m.processes();mem=m.memfile('/proc/meminfo');win=m.windows()
    safe=not proc['other_heavy_python'] and not win['ExternalVideoRender'] and mem['MemAvailable']>=1.5*2**30 and win['CommitLimit']-win['CommittedBytes']>=2*2**30
    save('RESOURCE_'+tag+'.json',dict(safe=safe,processes=proc,wsl=mem,windows=win));assert safe,'RESOURCE_GATE_FAILED'
def task_trace(path):
    z=np.load(path/'trace.npz');m=z['stage']=='TASK'
    return {k:z[k][m] for k in z.files if z[k].shape[0]==len(m)}
