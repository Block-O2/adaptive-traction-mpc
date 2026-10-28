"""Fresh-process saved-raw audit. Explicitly forbids simulator reset and learning."""
from pathlib import Path
import os,sys,json,math,time,signal,hashlib,gzip,traceback
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R)
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(R/'analysis_tools/mpl-cache'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(R/'scripts'),str(R/'runtime')]
from research_common import atomic,read,sha,now,HARD_STOP,pid_identity,same_pid
import common
os.environ['MPLCONFIGDIR']=str(R/'analysis_tools/mpl-cache')
from cloud_case_audit import audit as original_audit
from force_audit import audit as force_audit
from native_boundary_motion_audit import audit as native_motion_audit
from motion_metrics import metrics
from stream_json import read_evidence
from functional_smoke import snapshot,state_hash
from checkpoints import load,policy_hash,contract
from rewards import VERSIONS
import numpy as np,torch,gymnasium as gym
from pilot_env import PilotEnv

def forbidden(*a,**k):raise RuntimeError('INDEPENDENT_REVIEW_FORBIDS_PHYSICS_AND_LEARNING')
PilotEnv.reset=forbidden;PilotEnv.step=forbidden
from stable_baselines3 import PPO
PPO.train=forbidden;PPO.learn=forbidden;torch.optim.Adam.step=forbidden;torch.Tensor.backward=forbidden
signal.alarm(max(1,int(min(1000,HARD_STOP-time.time()-15))))
torch.set_num_threads(1);torch.set_num_interop_threads(1)
class Interface(gym.Env):
 observation_space=gym.spaces.Box(-np.inf,np.inf,shape=(41,),dtype=np.float32)
 action_space=gym.spaces.Box(-1.,1.,shape=(2,),dtype=np.float32)
 reset=forbidden;step=forbidden

def evidence(path):
 with read_evidence(path,encoding='utf8') as f:return json.load(f)

def reward_audit(rows,version):
 if version=='R0':return dict(pass_=True,version=version,scope='Original reward independently checked by original audit')
 c=VERSIONS[version];first=rows[0]['reward_before'];last=rows[-1]['reward_after'];success=rows[-1]['success']
 cost=c['force_per_Ns']*last['force']+c['moment_per_Nms']*last['moment']+c['variation']*last['variation']
 expected=c['progress']*((last['phi'] if success else 0.)-first['phi'])+(c['complete']-cost if success else c['failure']-max(c['failure_floor'],cost))
 actual=sum(s['reward'] for s in rows)
 checks=dict(finite=math.isfinite(actual),terminal_last=rows[-1]['terminal'] and not any(s['terminal'] for s in rows[:-1]),not_truncated=not any(s['truncated'] for s in rows),sum_matches=abs(expected-actual)<1e-7,failed_negative=success or actual<0.)
 return dict(pass_=all(checks.values()),checks=checks,actual=actual,expected=expected,cost=cost,success=success)

def main():
 started=time.time();rows=[json.loads(s) for s in (R/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (R/'ALL_ATTEMPTS.jsonl').exists() else [];records=[]
 for i,row in enumerate(rows):
  run=Path(row['run']);target=R/'audit/independent_all_attempts'/row['job_id']/run.name;target.mkdir(parents=True,exist_ok=True)
  # Original auditors recompute native owner/receipts, force/moment and motion from retained raw.
  a=original_audit(run);f=force_audit(run/'env/episode_0001');n=native_motion_audit(run);m=metrics(run,target)
  samples=evidence(run/'RESEARCH_TRANSITIONS.json');reward=reward_audit(samples,row['reward_version'])
  raw=np.asarray([s['raw_action'] for s in samples]);clipped=np.asarray([s['action'] for s in samples]);mapping=bool(np.allclose(np.clip(raw,-1,1),clipped,rtol=0,atol=1e-7))
  independent_JF=f['independent_J_F_N_s'];independent_JM=f['independent_J_M_Nm_s']
  checks=dict(original_native=a['pass'],force=f['pass'],motion=n['pass'],reward=reward['pass_'],raw_clip_mapping=mapping,JF_match=abs(independent_JF-row['JF'])<1e-7,JM_match=abs(independent_JM-row['JM'])<1e-7,task_identity=m['success']==row['success'],native_steps=a['ownership']['native_steps_all']==row['native_steps'] and a['ownership']['native_task_steps']==row['task_native_steps'])
  checks['native_steps']=bool(checks['native_steps'])
  item=dict(run=str(run),source_row_sha256=sha(run/'RESULT.json'),pass_=all(checks.values()),checks=checks,JF=independent_JF,JM=independent_JM,integral_scope=row['integral_scope'],reward=reward,motion_metrics=str(target/'COMMON_MOTION_METRICS.json'),original_checks=a['checks'],native_motion_checks=n['checks'])
  atomic(target/'AUDIT.json',item);records.append(item)
  atomic(R/'audit/INDEPENDENT_ALL_ATTEMPTS_PROGRESS.json',dict(completed=i+1,total=len(rows),all_pass=all(x['pass_'] for x in records)))
  assert item['pass_'],str(item)
 cp_records=[]
 for p in sorted(list((R/'runtime/jobs').glob('*/checkpoints/*.json'))+list((R/'runtime/jobs').glob('*/episode_*/before_update_checkpoint.json'))):
  if p.name.endswith('.pending.json'):continue
  meta=read(p)
  if meta.get('category')!='REAL_PPO_CHECKPOINT':continue
  model,loaded=load(p.with_suffix(''),Interface());actual=snapshot(model);checks={k:actual[k]==v for k,v in meta['state_snapshot'].items()}
  pend=meta.get('pending_complete_transitions',0);density=None
  if pend:
   q=Path(meta['pending_complete_rollout_path']);assert sha(q)==meta['pending_complete_rollout_sha256']
   samples=read(q);assert len(samples)==pend and samples[0]['episode_start'] and samples[-1]['terminal']
   with torch.no_grad():
    obs=torch.as_tensor(np.asarray([s['obs'] for s in samples],np.float32));acts=torch.as_tensor(np.asarray([s['raw_action'] for s in samples],np.float32));_,lp,_=model.policy.evaluate_actions(obs,acts)
    density=float((lp-torch.as_tensor([s['logp'] for s in samples],dtype=torch.float32)).abs().max())
   checks['pending_density']=density<2e-5
  if meta.get('phase')=='COMPLETE_ROLLOUT_BEFORE_ADAM':
   input_path=p.parent/'COMPLETE_UPDATE_INPUT.json'
   assert sha(input_path)==meta['input_sha256']
   samples=evidence(input_path)
   with torch.no_grad():
    obs=torch.as_tensor(np.asarray([s['obs'] for s in samples],np.float32));acts=torch.as_tensor(np.asarray([s['raw_action'] for s in samples],np.float32));_,lp,_=model.policy.evaluate_actions(obs,acts)
    density=float((lp-torch.as_tensor([s['logp'] for s in samples],dtype=torch.float32)).abs().max())
   checks['full_update_density']=density<2e-5
  cp_records.append(dict(checkpoint=str(p.with_suffix('')),files={s:sha(p.with_suffix(s)) for s in ['.zip','.rng.pt','.json']},state_snapshot=actual,pending_transitions=pend,pending_density_max_error=density,std=model.policy.log_std.detach().exp().tolist(),checks=checks,pass_=all(checks.values())))
  del model
 assert all(x['pass_'] for x in cp_records)
 ledger=read(R/'LEDGER.json',{});activation=read(R/'ACTIVATION.json');origin=Path(read(R/'START.json')['origin_package']);origin_manifest=read(origin/'OUTPUT_MANIFEST.json');origin_mismatch=[]
 for item in origin_manifest['files']:
  p=origin/item['path']
  if not p.exists() or sha(p)!=item['sha256']:origin_mismatch.append(item['path'])
 parent_mismatch=[]
 for item in activation['checkpoint_pair']:
  for name,h in item['files'].items():
   if sha(origin.parent/'rl_b_autonomous_stability_reward_v1'/name)!=h:parent_mismatch.append(name)
 source_bindings=[]
 for q in (R/'jobs').glob('*/SOURCE_IDENTITY.json'):
  identity=read(q);cfg_path=R/'configs'/f'{q.parent.name}.json';cfg=read(cfg_path)
  source_ok=all(sha(Path(identity['path'])/name)==h for name,h in identity['files'].items())
  source_ok &= all(activation['script_sha256'][name]==h for name,h in identity['files'].items())
  effective=R/'runtime/jobs'/q.parent.name/'EFFECTIVE_CONFIG.json'
  source_ok &= read(effective)==cfg
  source_bindings.append(dict(job=q.parent.name,source_bundle=identity['bundle_sha256'],config_sha256=sha(cfg_path),pass_=bool(source_ok)))
 assert all(x['pass_'] for x in source_bindings),'SOURCE_CONFIG_OWNERSHIP_MISMATCH'
 identities=[]
 for p in (R/'jobs').glob('*/END.json'):
  x=read(p);identities.append(dict(job=p.parent.name,START=(p.parent/'START.json').exists(),END=True,child_joined=x.get('child_joined'),worker_owner_joined=(x.get('worker_end') or {}).get('owner_joined')))
 train_count=sum(x['mode']=='training' for x in rows);dev_count=sum(x['mode']=='evaluation' and x.get('evaluation_split')!='reserved_action_streams' for x in rows);final_count=sum(x['mode']=='evaluation' and x.get('evaluation_split')=='reserved_action_streams' for x in rows)
 std_count=sum(x['mode']=='training' and x['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2'] for x in rows)
 native_sum=sum(x.get('native_steps',0) for x in ledger.get('attempts',[]));row_native=sum(x['native_steps'] for x in rows);optim=sum(x['gradient_updates'] for x in rows)
 checks=dict(source_and_config_ownership=all(x['pass_'] for x in source_bindings),all_saved_raw_pass=all(x['pass_'] for x in records),all_checkpoints_pass=all(x['pass_'] for x in cp_records),contract_unchanged=contract()==activation['contract_sha256'],origin_files_unchanged=not origin_mismatch,parent_files_unchanged=not parent_mismatch,all_attempts_settled=all(x['settled'] for x in ledger.get('attempts',[])),ledger_native_sum=native_sum==ledger.get('native_steps',0),row_native_sum=row_native==native_sum,optimizer_sum=optim==ledger.get('optimizer_steps',0),STD_cap=std_count<=80,training_cap=train_count<=160,development_cap=dev_count<=24,final_cap=final_count<=12,total_evaluation_cap=dev_count+final_count<=36,native_cap=native_sum<=33000000,all_job_START_END=all(x['START'] and x['END'] and x['child_joined'] and x['worker_owner_joined'] for x in identities))
 result=dict(time_utc=now(),source_sha256=sha(Path(__file__)),checks=checks,pass_=all(checks.values()),attempts=records,checkpoints=cp_records,source_bindings=source_bindings,jobs=identities,origin_manifest_entries=len(origin_manifest['files']),origin_mismatches=origin_mismatch,parent_mismatches=parent_mismatch,wall_s=time.time()-started,counts=dict(training=train_count,STD=std_count,development=dev_count,final=final_count,native=native_sum,optimizer=optim),new_physics=0,new_optimizer_updates=0)
 atomic(R/'audit/INDEPENDENT_FULL_AUDIT.json',result);print(json.dumps({'pass_':result['pass_'],'checks':checks,'wall_s':result['wall_s']}),flush=True)
 assert result['pass_']
if __name__=='__main__':main()
