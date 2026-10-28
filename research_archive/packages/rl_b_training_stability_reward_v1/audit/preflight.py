"""No-native, no-learning admission validation against immutable handoff identities."""
from pathlib import Path
import os,sys,json,hashlib,random,math,datetime,subprocess
O=Path('/home/hank/ihear-lab/rl_b_std_ablation_handoff_v1');S=Path(__file__).resolve().parent
os.environ.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(S/'mpl-cache'),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
sys.dont_write_bytecode=True;sys.path.insert(0,str(O/'runtime'))
import common
os.environ['MPLCONFIGDIR']=str(S/'mpl-cache')
from checkpoints import load,sha,policy_hash
from functional_smoke import snapshot,state_hash
import numpy as np,torch,gymnasium as gym
from stable_baselines3.common.distributions import DiagGaussianDistribution
import importlib.util
sp=importlib.util.spec_from_file_location('tested_rewards',S/'scripts/rewards.py');rw=importlib.util.module_from_spec(sp);sp.loader.exec_module(rw)
torch.set_num_threads(1);torch.set_num_interop_threads(1)
class Interface(gym.Env):
 observation_space=gym.spaces.Box(-np.inf,np.inf,shape=(41,),dtype=np.float32)
 action_space=gym.spaces.Box(-1.,1.,shape=(2,),dtype=np.float32)
 def reset(self,*a,**k):raise RuntimeError('ADMISSION_PREFLIGHT_FORBIDS_PHYSICS')
 def step(self,*a,**k):raise RuntimeError('ADMISSION_PREFLIGHT_FORBIDS_PHYSICS')
plan=json.loads((O/'unattended/NEXT_PLAN.json').read_text());records=[]
allparents=json.loads((O/'NEXT_PARENT_CHECKPOINTS.json').read_text())['checkpoints']
for item in plan['checkpoint_pair']:
 m,meta=load(item['checkpoint'],Interface());actual=snapshot(m)
 assert actual==item['state_snapshot']==meta['state_snapshot'],'FULL_STATE_MISMATCH'
 assert not meta.get('pending_complete_transitions',0) and not meta.get('partial_attempt')
 evidence=next(x for x in allparents if x['seed']==item['seed'] and x['branch']=='RETENTION_R1')
 def subhash(predicate):
  return state_hash({name:value for name,value in m.policy.state_dict().items() if predicate(name)})
 mean0=subhash(lambda n:n!='log_std' and not (n.startswith('value_net') or n.startswith('mlp_extractor.value_net')))
 critic0=subhash(lambda n:n.startswith('value_net') or n.startswith('mlp_extractor.value_net'))
 assert mean0==evidence['actor_mean_parameters_sha256'] and critic0==evidence['critic_parameters_sha256']
 assert m.policy.log_std.requires_grad and any(p is m.policy.log_std for g in m.policy.optimizer.param_groups for p in g['params'])
 assert isinstance(m.policy.action_dist,DiagGaussianDistribution) and not m.use_sde and not m.policy.squash_output
 original=m.policy.log_std.exp().detach().tolist();opt0=state_hash(m.policy.optimizer.state_dict())
 obs=torch.zeros((8,41));raw,values,logp=m.policy(obs)
 oldlp=logp.detach().clone()
 with torch.no_grad():m.policy.log_std.fill_(math.log(.2))
 assert subhash(lambda n:n!='log_std' and not (n.startswith('value_net') or n.startswith('mlp_extractor.value_net')))==mean0
 assert subhash(lambda n:n.startswith('value_net') or n.startswith('mlp_extractor.value_net'))==critic0
 assert state_hash(m.policy.optimizer.state_dict())==opt0
 with torch.no_grad():
  _,stale,_=m.policy.evaluate_actions(obs,raw)
  fresh,_,freshlp=m.policy(obs);_,checked,_=m.policy.evaluate_actions(obs,fresh)
 assert float((checked-freshlp).abs().max())<2e-5
 assert float((stale-oldlp).abs().max())>2e-5,'STALE_DENSITY_TEST_DID_NOT_REJECT'
 records.append(dict(seed=item['seed'],full_state=actual,actor_mean_sha256=mean0,critic_sha256=critic0,actual_parent_std=original,initialized_std=m.policy.log_std.exp().detach().tolist(),log_std_trainable=True,Adam_inherited_including_log_std_moments=True,old_density_rejected=True,new_density_max_error=float((checked-freshlp).abs().max()),policy_distribution='SB3 raw DiagGaussian, clip execution only',pending_empty=True))
# Reward math and saved-raw replay; no simulator, gradient or optimizer entrypoint.
paths=[]
for line in (O/'ALL_ATTEMPTS.jsonl').read_text().splitlines():
 row=json.loads(line);p=Path(row['run'])/'RESEARCH_TRANSITIONS.json'
 if p.exists():paths.append(p)
replays=[]
for p in paths:
 rows=json.loads(p.read_text())
 for version in ['R1','R4']:
  c=rw.VERSIONS[version];actual=sum(rw.transition(version,s['reward_before'],s['reward_after'],s['terminal'] or s['truncated'],s['success'],s['baseline_reward'])[0] for s in rows)
  b=rows[0]['reward_before'];a=rows[-1]['reward_after'];ok=rows[-1]['success'];cost=c['force_per_Ns']*a['force']+c['moment_per_Nms']*a['moment']+c['variation']*a['variation']
  expected=c['progress']*((a['phi'] if ok else 0)-b['phi'])+(c['complete']-cost if ok else c['failure']-max(c['failure_floor'],cost))
  assert abs(actual-expected)<1e-7 and (ok or actual<0)
  replays.append(dict(path=str(p),version=version,expected=expected,actual=actual,success=ok))
for version in ['R1','R4']:
 z=dict(phi=0.,force=0.,moment=0.,variation=0.);a={**z,'phi':1.};b={**z,'phi':2.}
 assert abs(sum(rw.transition(version,x,y,False,False,0)[0] for x,y in [(z,a),(a,b),(b,z)]))<1e-12
 assert rw.transition(version,z,z,True,False,0)[0]==-30.
assert {k:v for k,v in rw.VERSIONS['R1'].items() if k not in ['version','rationale','moment_per_Nms']}=={k:v for k,v in rw.VERSIONS['R4'].items() if k not in ['version','rationale','moment_per_Nms']}
assert rw.VERSIONS['R1']['moment_per_Nms']==.005 and rw.VERSIONS['R4']['moment_per_Nms']==.020
# No execution of the reserved streams; inspect only existing configuration and attempt IDs.
streams=set(plan['holdout_streams']);hits=[];checked=0
for package in O.parent.glob('rl_b_*'):
 for folder in [package/'configs',package/'runtime/configs']:
  if folder.is_dir():
   for p in folder.glob('*.json'):
    x=json.loads(p.read_text());checked+=1
    if x.get('evaluation_rng') in streams:hits.append(str(p))
 p=package/'ALL_ATTEMPTS.jsonl'
 if p.exists():
  for line in p.open():
   x=json.loads(line);checked+=1
   if x.get('evaluation_rng') in streams:hits.append(str(p)+':'+str(x.get('job_id')))
assert not hits,'RESERVED_STREAM_ALREADY_EXECUTED'
manifest=json.loads((O/'OUTPUT_MANIFEST.json').read_text());mismatches=[]
for entry in manifest['files']:
 p=O/entry['path']
 if not p.exists() or sha(p)!=entry['sha256']:mismatches.append(entry['path'])
assert not mismatches,'ORIGIN_PACKAGE_CHANGED'
git=O.parent/'rl_b_matched_recovery_stability_v1/github'
git_state={name:subprocess.check_output(['git','-C',str(git),*args],text=True) for name,args in [('HEAD',['rev-parse','HEAD']),('branch',['symbolic-ref','--short','-q','HEAD'])] if name!='branch'}
git_state['status']=subprocess.check_output(['git','-C',str(git),'status','--porcelain=v1','--untracked-files=all'],text=True)
report=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pass_=True,native_steps=0,optimizer_updates=0,parents=records,reward_saved_raw_replays=replays,reward_units='observed 5ms left-integrated JF N*s; JM Nm*s; gamma=1; complete/partial separate',reserved_streams=dict(streams=sorted(streams),checked_records=checked,hits=hits),origin_manifest=dict(entries=len(manifest['files']),sha256=sha(O/'OUTPUT_MANIFEST.json'),mismatches=mismatches),git=git_state)
(S/'audit/PREFLIGHT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(pass_=True,parents=len(records),saved_reward_replays=len(replays),origin_files_verified=len(manifest['files']),reserved_streams_unused=True)))
