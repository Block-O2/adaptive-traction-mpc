from pathlib import Path
import os,sys,json,time,hashlib,random,pickle,subprocess
import numpy as np
import torch
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc');R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/source');S=R/'stages/stage5_personalized_motion_learning'
P=W/'dagger_anchored_sac_v2';L=P/'output';D=S/'docs/dagger_anchored_sac_v2';O=S/'results/dagger_anchored_sac_v2';V=S/'results/dagger_to_sac_expert_v1'
for folder in (S/'scripts/single_human_sac_expert_v1',S/'scripts/single_human_sac_expert_v1_r2'):sys.path.insert(0,str(folder))
from sac_env import SACExpertEnv,load_case_options,gamma_for,SCALES,feature_spec
import campaign_r2 as r2
from final_qualification import compact_archive
from stable_baselines3.sac.policies import Actor
from stable_baselines3.common.torch_layers import FlattenExtractor
import gymnasium as gym
torch.set_num_threads(1)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,Path):return str(v)
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(name,v):
 for folder in (L,D):
  folder.mkdir(parents=True,exist_ok=True);p=folder/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(clean(v),indent=2,ensure_ascii=False,allow_nan=False)+'\n');t.replace(p)
def read(name):return json.loads((L/name).read_text())
def log(name,v):
 row=dict(unix=time.time(),**v)
 for folder in (L,D):
  folder.mkdir(parents=True,exist_ok=True)
  with (folder/name).open('a') as f:f.write(json.dumps(clean(row),allow_nan=False)+'\n')
def state(status,**kw):
 v=read('STATE.json') if (L/'STATE.json').exists() else {};v.update(status=status,updated_unix=time.time(),**kw);save('STATE.json',v);print(json.dumps(clean(v)),flush=True)
def actor(device='cpu'):
 ob=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32);ac=gym.spaces.Box(-1.,1.,(2,),np.float32)
 return Actor(ob,ac,[256,256],FlattenExtractor(ob),55,torch.nn.ReLU).to(device)
def rngs(sampler=None,env=None):
 return dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [],sampler=None if sampler is None else sampler.bit_generator.state,env=None if env is None else env.np_random.bit_generator.state)
def digest(v):
 def canonical(x):
  if torch.is_tensor(x):return ('tensor',str(x.dtype),tuple(x.shape),x.cpu().numpy().tobytes())
  if isinstance(x,np.ndarray):return ('array',str(x.dtype),x.shape,x.tobytes())
  if isinstance(x,dict):return tuple((k,canonical(x[k])) for k in sorted(x))
  if isinstance(x,(tuple,list)):return tuple(canonical(y) for y in x)
  return x
 return hashlib.sha256(repr(canonical(v)).encode()).hexdigest()
def restore(v,sampler=None,env=None):
 random.setstate(v['python']);np.random.set_state(v['numpy']);torch.set_rng_state(v['torch'])
 if v['cuda']:torch.cuda.set_rng_state_all(v['cuda'])
 if sampler is not None:sampler.bit_generator.state=v['sampler']
 if env is not None:env.np_random.bit_generator.state=v['env']
def resource(tag):
 if (L/'RESOURCE_POLICY_V2.json').exists():
  from resource_policy_v2 import check
  return check(tag)
 sys.path.insert(0,str(W/'single_human_sac_memory'));import memory_test_v1 as m
 proc=m.processes();mem=m.memfile('/proc/meminfo');win=m.windows();swap=mem['SwapTotal']-mem['SwapFree'];base=read('RESOURCE_BASE.json')['swap_bytes'] if (L/'RESOURCE_BASE.json').exists() else swap
 reasons=[]
 if proc['other_heavy_python']:reasons.append('OTHER_HEAVY_PYTHON')
 if win['ExternalVideoRender']:reasons.append('EXTERNAL_VIDEO_RENDER')
 if mem['MemAvailable']<1.5*2**30:reasons.append('LOW_WSL_MEMORY')
 if win['CommitLimit']-win['CommittedBytes']<2*2**30:reasons.append('LOW_COMMIT_HEADROOM')
 if swap-base>128*2**20:reasons.append('NEW_SWAP_OVER_128_MIB')
 gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout.strip()
 row=dict(tag=tag,processes=proc,wsl=mem,windows=win,swap_bytes=swap,gpu=gpu,reasons=reasons)
 if not (L/'RESOURCE_BASE.json').exists():save('RESOURCE_BASE.json',row)
 log('RESOURCES.jsonl',row);assert not reasons,'RESOURCE_GATE:'+','.join(reasons)
def guard():
 if (L/'RESOURCE_PAUSE_FLAG_V2.json').exists():raise AssertionError('RESOURCE_POLICY_V2_ASYNC:'+','.join(read('RESOURCE_PAUSE_FLAG_V2.json')['reasons']))
 authorization=L/'RESUME_36283_AUTHORIZATION.json'
 cutoff=read('RESUME_36283_AUTHORIZATION.json')['operational_cutoff_unix'] if authorization.exists() else read('STATE.json')['hard_cutoff_unix']
 assert time.time()<cutoff,'HARD_WALL_CAP'
 assert sha(L/'PREREGISTRATION.json')==read('LOCK.json')['config']
 for p,h in read('LOCK.json')['sources'].items():assert sha(p)==h,'SOURCE_DRIFT:'+p
def metric(env,name,scope):
 row=r2.metric(env,name,scope);row.pop('raw_actions',None);ts=[x['to'] for x in env.summary['task']['phase_transitions']]
 row.update(gates=dict(settled_OUTBOUND='HOLD' in ts,completed_HOLD='RETURN' in ts,completed_RETURN='COMPLETE' in ts),termination=env.summary.get('abort_reason') or env.summary['status'],safety_mode_counts=env.summary['safety_mode_counts'],reward_total=env.reward_total,reward_totals=env.reward_parts,teacher_queries=0,teacher_execution=0,normalization_updates=0)
 return row
