"""Isolated actor-only BC diagnostic; frozen R2 production sources are read-only."""
from pathlib import Path
import os, sys, json, time, hashlib, subprocess, random, shutil
import numpy as np
W = Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
R = Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1/source')
S = R/'stages/stage5_personalized_motion_learning'
NAME = 'bc_reproduction_gate_v1'
P = S/'scripts'/NAME; D = S/'docs'/NAME; O = S/'results'/NAME; L = W/NAME/'output'
PREVIOUS = S/'docs/demo_assisted_sac_task_acquisition_v1'
DEMO = S/'results/demo_assisted_sac_task_acquisition_v1/NATIVE_DEMO.npz'
OLD = S/'docs/single_human_sac_expert_v1/r2'
BRANCH = 'codex/bc-reproduction-gate-v1'
for folder in (S/'scripts/single_human_sac_expert_v1', S/'scripts/single_human_sac_expert_v1_r2'):
    sys.path.insert(0, str(folder))
from sac_env import SACExpertEnv, load_case_options, SCALES, feature_spec
import campaign_r2 as r2
from final_qualification import compact_archive
import torch
from stable_baselines3.sac.policies import Actor
from stable_baselines3.common.torch_layers import FlattenExtractor
torch.set_num_threads(1)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for b in iter(lambda:stream.read(2**20), b''): h.update(b)
    return h.hexdigest()

def clean(v):
    if isinstance(v, dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [clean(x) for x in v]
    if isinstance(v,np.ndarray): return clean(v.tolist())
    if isinstance(v,np.generic): return clean(v.item())
    if isinstance(v,Path): return str(v)
    if isinstance(v,float) and not np.isfinite(v): return None
    return v

def save(name, value):
    text=json.dumps(clean(value),indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n'
    for folder in (D,L):
        folder.mkdir(parents=True,exist_ok=True)
        tmp=folder/(name+'.tmp'); tmp.write_text(text); tmp.replace(folder/name)

def prose(name, text):
    for folder in (D,L): (folder/name).write_text(text,encoding='utf-8')

def read(name): return json.loads((D/name).read_text())
def state(status, **kw):
    row=dict(status=status,updated_unix=time.time(),**kw); save('STATE.json',row)
    print(json.dumps(clean(row)),flush=True)

def check_lock():
    lock=read('SCIENTIFIC_LOCK.json')
    for path,h in lock['files'].items(): assert sha(R/path)==h, 'R2_SOURCE_DRIFT:'+path
    assert sha(D/'PREREGISTRATION.json')==read('PREREGISTRATION_SHA256.json')['sha256']
    for path,h in read('EXPERIMENT_SOURCE_LOCK.json').items(): assert sha(R/path)==h, 'BC_SOURCE_DRIFT:'+path
    return lock

def make_actor(seed, device='cpu'):
    import gymnasium as gym
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    observation=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32)
    action=gym.spaces.Box(-1.,1.,(2,),np.float32)
    actor=Actor(observation,action,[256,256],FlattenExtractor(observation),55,torch.nn.ReLU).to(device)
    actor.log_std.requires_grad_(False) # Native Gaussian head exists, deterministic mean only is trained.
    assert not hasattr(actor,'critic')
    return actor

def metrics(pred, target, phases):
    error=np.asarray(pred,dtype=float)-np.asarray(target,dtype=float)
    def row(e):
        return dict(n=len(e),MAE=float(np.mean(np.abs(e))),RMSE=float(np.sqrt(np.mean(e*e))),
                    hip_MAE=float(np.mean(np.abs(e[:,0]))),hip_RMSE=float(np.sqrt(np.mean(e[:,0]**2))),
                    knee_MAE=float(np.mean(np.abs(e[:,1]))),knee_RMSE=float(np.sqrt(np.mean(e[:,1]**2))),
                    max_error=float(np.max(np.abs(e))))
    return {**row(error),'per_phase':{p:row(error[phases==p]) for p in ('OUTBOUND','HOLD','RETURN')},
            'actor_near_bound_coordinate_rate':float(np.mean(np.abs(pred)>=.95)),
            'teacher_near_bound_coordinate_rate':float(np.mean(np.abs(target)>=.95)),
            'degree_conversion_per_action_unit':62.5}

def resource(tag):
    sys.path.insert(0,str(W/'single_human_sac_memory'))
    import memory_test_v1 as memory
    proc=memory.processes(); mem=memory.memfile('/proc/meminfo'); win=memory.windows()
    row=dict(tag=tag,unix=time.time(),processes=proc,wsl=mem,windows=win)
    row['safe']=(not proc['other_heavy_python'] and not win['ExternalVideoRender'] and
                 mem['MemAvailable']>=1.5*2**30 and win['CommitLimit']-win['CommittedBytes']>=2*2**30)
    save('RESOURCE_'+tag+'.json',row)
    assert row['safe'], 'RESOURCE_GATE_FAILED'
    return row
