"""Versioned causal imitation-to-RL campaign; frozen physics and R2 evaluator."""
from pathlib import Path
import sys, os, json, time, hashlib, subprocess, random, shutil, traceback
import numpy as np
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
NAME='dagger_to_sac_expert_v1'
P=W/NAME; L=P/'output'; D=S/'docs'/NAME; O=S/'results'/NAME
for folder in (S/'scripts/single_human_sac_expert_v1',S/'scripts/single_human_sac_expert_v1_r2'):
    sys.path.insert(0,str(folder))
from sac_env import SACExpertEnv, load_case_options, SCALES, feature_spec, target_to_action, gamma_for
import campaign_r2 as r2
from final_qualification import compact_archive
import torch
from stable_baselines3.sac.policies import Actor
from stable_baselines3.common.torch_layers import FlattenExtractor
import gymnasium as gym
torch.set_num_threads(1)
DEMO=S/'results/demo_assisted_sac_task_acquisition_v1/NATIVE_DEMO.npz'
BC=W/'action_representation_switch_audit_v1/output'
BRANCH='codex/dagger-to-sac-expert-v1'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,Path):return str(v)
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def save(name,value):
    text=json.dumps(clean(value),indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    for folder in (D,L):
        folder.mkdir(parents=True,exist_ok=True)
        tmp=folder/(name+'.tmp');tmp.write_text(text);tmp.replace(folder/name)
def read(name):return json.loads((D/name).read_text())
def state(status,**kw):
    row=read('STATE.json') if (D/'STATE.json').exists() else {}
    row.update(status=status,updated_unix=time.time(),**kw);save('STATE.json',row)
    print(json.dumps(clean(row)),flush=True)
def resource(tag):
    sys.path.insert(0,str(W/'single_human_sac_memory'))
    import memory_test_v1 as m
    proc=m.processes();mem=m.memfile('/proc/meminfo');win=m.windows()
    swap=mem['SwapTotal']-mem['SwapFree']
    base=read('RESOURCE_PREFLIGHT.json')['swap_bytes'] if (D/'RESOURCE_PREFLIGHT.json').exists() else swap
    reasons=[]
    if proc['other_heavy_python']:reasons.append('OTHER_HEAVY_PYTHON')
    if win['ExternalVideoRender']:reasons.append('EXTERNAL_VIDEO_RENDER')
    if mem['MemAvailable']<1.5*2**30:reasons.append('LOW_WSL_MEMORY')
    if win['CommitLimit']-win['CommittedBytes']<2*2**30:reasons.append('LOW_COMMIT_HEADROOM')
    if swap-base>128*2**20:reasons.append('NEW_SWAP_OVER_128_MIB')
    row=dict(tag=tag,unix=time.time(),safe=not reasons,reasons=reasons,processes=proc,wsl=mem,windows=win,swap_bytes=swap)
    save('RESOURCE_'+tag+'.json',row);assert not reasons,'RESOURCE_GATE:'+','.join(reasons)
    return row
def check():
    for path,h in read('SCIENTIFIC_LOCK.json')['files'].items():assert sha(R/path)==h,'SCIENCE_DRIFT:'+path
    assert sha(D/'PREREGISTRATION.json')==read('PREREGISTRATION_SHA256.json')['sha256']
    for path,h in read('EXPERIMENT_SOURCE_LOCK.json').items():assert sha(P/path)==h,'SOURCE_DRIFT:'+path
    assert time.time()<read('STATE.json')['hard_cutoff_unix'],'HARD_WALL_CAP'
def actor(seed,device='cpu'):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    ob=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32);ac=gym.spaces.Box(-1.,1.,(2,),np.float32)
    a=Actor(ob,ac,[256,256],FlattenExtractor(ob),55,torch.nn.ReLU).to(device)
    a.log_std.requires_grad_(False);return a
def metric(env,name,scope):
    row=r2.metric(env,name,scope);row.pop('raw_actions',None)
    transitions=[r['to'] for r in env.summary['task']['phase_transitions']]
    row['gates']=dict(settled_OUTBOUND='HOLD' in transitions,completed_HOLD='RETURN' in transitions,
                      RETURN_entered='RETURN' in transitions,completed_RETURN='COMPLETE' in transitions,
                      independent_VALID=row['valid'])
    return row
def checkpoint(a,opt,rng,path,**kw):
    torch.save(dict(state_dict=a.state_dict(),optimizer=opt.state_dict(),numpy_rng=rng.bit_generator.state,
                    torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),python_rng=random.getstate(),**kw),path)
