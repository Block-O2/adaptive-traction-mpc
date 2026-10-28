"""One preregistered frozen MuJoCo evaluation; training APIs blocked."""
from pathlib import Path
import os,sys,json,time,traceback,random,hashlib,gzip,shutil
r=Path(__file__).resolve().parents[1];runtime=r/'physical/runtime';sys.path.insert(0,str(runtime));os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
import common
from common import put
from runtime_setup import install
install()
import numpy as np,torch
from stable_baselines3 import PPO
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
def forbidden(*a,**kw):raise RuntimeError('FROZEN_EVALUATION_FORBIDS_GRADIENT_UPDATE')
PPO.train=forbidden;PPO.learn=forbidden;torch.optim.Adam.step=forbidden;torch.Tensor.backward=forbidden;torch.autograd.backward=forbidden
from checkpoints import load,sha,policy_hash,contract
from functional_smoke import state_hash
from resource_guard import Guard
from pilot_env import PilotEnv
from cloud_case_audit import audit
from force_audit import audit as force_audit
from ready_env import completion_evidence
plan=json.loads((r/'physical/EVALUATION_PLAN.json').read_text());case=next(x for x in plan['cases'] if x['id']==sys.argv[1]);out=runtime/'evaluations'/case['id'];out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
assert contract()==plan['source_contract_sha256']
started=time.time();deadline=__import__('datetime').datetime.fromisoformat(json.loads((r/'audit/STUDY_START.json').read_text())['no_new_long_physics_after']).timestamp();assert time.time()<deadline
checkpoint=r.parent/f"rl_b_autonomous_replication_v1/seeds/{case['training_seed']}/stage1/checkpoints/episode_{case['checkpoint_episode']:03d}"
put(out/'START.json',{'unix':started,'pid':os.getpid(),'case':case,'checkpoint':str(checkpoint),'checkpoint_model_sha256':sha(str(checkpoint)+'.zip'),'contract_sha256':contract(),'category':plan['category'],'actual_physics_attempt':False,'gradient_updates_allowed':0,'source_model_config_identity':'exact original frozen executable contract; resource/time budget replaced only in passed runtime guard'})
env=None;guard=None;error=None;result=None;model=None;before=None;resource=None;attempted=False
try:
 budget={'hard_stop_unix':min(started+300,deadline),'no_new_physics_after_unix':deadline,'native_steps':0,'native_steps_hard_cap':165000,'rl_decisions':0,'rl_decisions_hard_cap':128}
 interface=PilotEnv(out/'model_interface/env',budget=budget)
 model,record=load(checkpoint,interface);interface.close();model.policy.set_training_mode(False)
 before={'policy':policy_hash(model),'optimizer':state_hash(model.policy.optimizer.state_dict()),'model_file':sha(str(checkpoint)+'.zip'),'rng_file':sha(str(checkpoint)+'.rng.pt')}
 assert before['policy']==record['policy_sha256']
 rng=case['evaluation_rng_seed'];random.seed(rng);np.random.seed(rng);torch.manual_seed(rng)
 put(out/'EVALUATION_RNG.json',{'seed':rng,'checkpoint_rng_verified_then_explicitly_reseeded':True,'initial_rng_sha256':state_hash({'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state()})})
 guard=Guard(out,seconds=300,min_available_gib=6,min_disk_gib=10,max_output_gib=1.5).start();env=PilotEnv(out/'env',budget=budget,guard=guard,retain_trace=True,category=plan['category'])
 put(out/'PHYSICS_START.json',{'unix':time.time(),'pid':os.getpid(),'case':case,'includes_preparation':True});attempted=True
 obs,info=env.reset(seed=case['environment_seed']);initial_obs=obs.copy();samples=[]
 for i in range(128):
  with torch.no_grad():
   tensor=torch.as_tensor(obs.reshape(1,-1));dist=model.policy.get_distribution(tensor);mean=dist.distribution.mean.numpy()[0].copy();std=dist.distribution.stddev.numpy()[0].copy();raw,value,logp=model.policy(tensor,deterministic=False)
  raw=raw.numpy()[0].copy();action=np.clip(raw,-1,1).astype(np.float32);nextobs,reward,term,trunc,info=env.step(action)
  samples.append({'index':i,'obs':obs.tolist(),'raw_action':raw.tolist(),'deterministic_mean':mean.tolist(),'std':std.tolist(),'bounded_proposal':action.tolist(),'value':float(value.item()),'raw_log_prob':float(logp.item()),'reward':float(reward),'terminated':bool(term),'truncated':bool(trunc),'step_info':common.clean(info)})
  obs=nextobs
  if term or trunc:break
 else:raise RuntimeError('RL_DECISION_CAP')
 native=info['native_steps_total'];native_status=env.summary;complete=completion_evidence(env.summary,env.phases);env.close();env=None
 resource=guard.close();guard=None
 independent=audit(out);force=force_audit(out/'env/episode_0001');assert independent['pass'] and force['pass'],'INDEPENDENT_AUDIT_FAILED'
 after={'policy':policy_hash(model),'optimizer':state_hash(model.policy.optimizer.state_dict()),'model_file':sha(str(checkpoint)+'.zip'),'rng_file':sha(str(checkpoint)+'.rng.pt')};assert before==after,'FROZEN_STATE_MUTATED'
 put(out/'POLICY_SAMPLES.json',{'case':case,'initial_obs_sha256':hashlib.sha256(initial_obs.tobytes()).hexdigest(),'samples':samples})
 result={'case':case,'category':plan['category'],'checkpoint':str(checkpoint),'checkpoint_model_sha256':before['model_file'],'checkpoint_rng_sha256':before['rng_file'],'policy_sha256':before['policy'],'optimizer_sha256':before['optimizer'],'source_contract_sha256':contract(),'success':bool(info['success']),'full_completion_evidence':complete,'status':info['status'],'abort_reason':info['abort_reason'],'task_s':info['task_s'],'native_steps':native,'task_native_steps':info['task_native_steps'],'rl_decisions':len(samples),'reward':sum(x['reward'] for x in samples),'reward_parts':info['reward_totals'],'JF_N_s':info['force_integral_N_s'],'JM_Nm_s':info['moment_integral_Nm_s'],'phases':info['phases'],'accepted':info['accepted'],'rejections':info['rejections'],'fallback_events':len(independent['fallback_events']),'raw_clipping_component_fraction':float(np.mean(np.abs([x['raw_action'] for x in samples])>1)),'initial_obs_sha256':hashlib.sha256(initial_obs.tobytes()).hexdigest(),'independent_audit_pass':independent['pass'],'force_audit_pass':force['pass'],'gradient_updates':0,'frozen_state_unchanged':before==after,'resources':resource,'evidence_scope':'two prespecified samples per checkpoint on known nominal; descriptive, no stability/generalization qualification'}
 put(out/'RESULT.json',result)
except BaseException as exc:
 error={'error':repr(exc),'traceback':traceback.format_exc()};put(out/'FAILURE.json',error)
finally:
 if env is not None:
  try:env.close()
  except BaseException as e:put(out/'CLOSE_FAILURE.json',{'error':repr(e)})
 if guard is not None:resource=guard.close()
 put(out/'END.json',{'unix':time.time(),'pid':os.getpid(),'error':error,'completed':error is None,'physics_attempted':attempted,'gradient_updates':0,'resources':resource,'owner_joined':env is None or env.thread is None})
 if attempted:put(out/'PHYSICS_END.json',{'unix':time.time(),'error':error,'native_steps':None if result is None else result['native_steps'],'owner_joined':env is None or env.thread is None})
if error:raise SystemExit(1)
# Lossless compression after successful raw audits. No native evidence is discarded.
compressed=[]
for p in list(out.rglob('*.json'))+list(out.rglob('*.jsonl')):
 if p.stat().st_size>2*1024**2:
  original_hash=sha(p);original_bytes=p.stat().st_size;target=Path(str(p)+'.gz')
  with p.open('rb') as src,gzip.open(target,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(target,'rb') as f:h=hashlib.sha256(f.read()).hexdigest()
  assert h==original_hash
  compressed.append({'path':str(p.relative_to(out)),'original_sha256':original_hash,'uncompressed_bytes':original_bytes,'gzip_sha256':sha(target),'lossless_roundtrip':True});p.unlink()
put(out/'LOSSLESS_RAW_COMPRESSION.json',{'files':compressed,'all_roundtrips_verified':True})
print(json.dumps(result),flush=True)
