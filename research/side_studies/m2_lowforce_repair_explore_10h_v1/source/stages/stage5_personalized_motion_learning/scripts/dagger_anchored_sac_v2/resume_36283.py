"""Same learning campaign, exact36,283 restore; serial evaluation lifecycle only."""
from common import *
from continue_partial_checkpoint import PartialCampaign
from operational_memory_v3 import phase,evidence,descendants
import gc,copy,traceback
from stable_baselines3.common.save_util import load_from_zip_file
class OperationalCampaign(PartialCampaign):
 def collect(self,count,allow_actor=True):
  phase('TRAINING_ACTIVE');evidence('TRAINING_START',total=self.total)
  try:return super().collect(count,allow_actor)
  finally:
   if self.env is not None:
    self.env.close();assert self.env.thread is None
   gc.collect();phase('TRAINING_JOINED');evidence('TRAINING_JOINED',total=self.total,descendants=descendants(os.getpid()))
 def evaluation(self,name,scope='NATIVE',stochastic=False,actor_state=None):
  cached=L/('EVAL_legacy_predict_revision_'+name.replace('/','_')+'.json')
  if cached.exists() and (name.startswith('checkpoint/') or name.startswith('best_confirmation/')):return super().evaluation(name,scope,stochastic,actor_state)
  guard()
  if self.env is not None:self.env.close();assert self.env.thread is None
  before=rngs(self.sampler,self.env);oldchildren=descendants(os.getpid());assert not any('multiprocessing.spawn' in x['cmd'] for x in oldchildren),'PLANNER_NOT_RELEASED'
  fullname='legacy_predict_revision/'+name;p=O/'evaluation_requests';p.mkdir(exist_ok=True);ap=p/(fullname.replace('/','_')+'.pt');torch.save(actor_state or {k:v.detach().cpu() for k,v in self.model.actor.state_dict().items()},ap)
  req=dict(name=fullname,scope=scope,stochastic=stochastic,actor=str(ap),seed=self.cfg['seed']+7919*(len(self.rows)+1),initial_condition_seed=self.cfg['initial_condition_seed'],result='EVAL_'+fullname.replace('/','_')+'.json');rp=p/(fullname.replace('/','_')+'.json');rp.write_text(json.dumps(req))
  phase('EVALUATION_START');evidence('BEFORE_CHILD',name=fullname,total=self.total)
  child=subprocess.Popen([sys.executable,str(P/'evaluate_operational_v3.py'),str(rp)],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  rc=child.wait();assert rc==0,f'EVALUATION_CHILD_EXIT_{rc}'
  assert not Path(f'/proc/{child.pid}').exists(),'EVALUATION_CHILD_NOT_REAPED';remaining=descendants(os.getpid());assert not any('multiprocessing.spawn' in x['cmd'] for x in remaining),'EVALUATION_PLANNER_NOT_RELEASED'
  gc.collect();phase('POST_EVALUATION_RELEASE');evidence('AFTER_CHILD_RELEASE',name=fullname,child_pid=child.pid,child_reaped=True,descendants=remaining,total=self.total)
  assert digest(before)==digest(rngs(self.sampler,self.env)),'EVALUATION_MUTATED_TRAINING_RNG'
  row=read(req['result']);self.eval_steps+=row['steps'];self.rows.append(row);log('EVALUATIONS.jsonl',row);return row
def run():
 c=None;monitor=None;folder=Path(sys.argv[1])
 try:
  from sac_env import rt
  from operational_memory_v3 import install
  phase('RESTORED_IDLE');install(rt);resource('RESUME_36283_PREFLIGHT');c=OperationalCampaign();c.restore_interrupted(folder);v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False)
  assert c.total==36283 and c.updates==45010 and c.actor_updates==2510
  from continue_21283 import replay_digest
  assert replay_digest(c.online)==replay_digest(v['online']);assert sha(v['history_path'])==v['history_sha256'];assert digest(c.best)==digest(v['best']);assert str(c.last_good)==v['last_good']
  old=copy.deepcopy(c.model.actor);old.load_state_dict(torch.load(folder/'actor.pt',map_location='cuda',weights_only=False));x=torch.as_tensor(c.imitation['observations'],device='cuda',dtype=torch.float32)
  with torch.no_grad():assert torch.equal(old(x,True),c.model.actor(x,True))
  assert all(digest(v['rng'][k])==digest(rngs(c.sampler,None)[k]) for k in ('python','numpy','torch','cuda','sampler'))
  _,params,variables=load_from_zip_file(folder/'model.zip',device='cuda');actual=c.model.get_parameters();assert all(digest(params[k])==digest(actual[k]) for k in params);assert torch.equal(variables['ent_coef_tensor'],c.model.ent_coef_tensor)
  save('RESUME_36283_AUDIT.json',dict(status='PASS',collection_steps=c.total,critic_updates=c.updates,actor_updates=c.actor_updates,full_components_exact=True,mean_bitwise_equal_all_13852=True,global_sampler_env_RNG_restored=True,replay_history_best_lastgood_exact=True,lambda_=c.lam,log_std=c.std,alpha=float(c.model.ent_coef_tensor),spent_budget_not_reset=True))
  del v,old,x,params,variables,actual;gc.collect();evidence('RESTORE_TEMPORARIES_RELEASED',total=c.total)
  monitor=subprocess.Popen([sys.executable,'-u',str(P/'resource_policy_v2.py'),str(os.getpid())],stdout=(L/'RESOURCE_MONITOR_36283.log').open('a'),stderr=subprocess.STDOUT)
  state('RESUMED_36283_VERIFIED',total_online_steps=c.total,error=None,resumable_checkpoint=str(folder))
  c.bounded_training(c.formal_origin)
 except BaseException as e:
  ck=None
  if c is not None:
   if c.env is not None:c.env.close()
   try:ck=c.snapshot('resume36283_paused_'+str(int(time.time())))
   except BaseException:pass
  save('EXCEPTION_36283.json',dict(error=str(e),traceback=traceback.format_exc(),checkpoint=ck));state('PAUSED_REAL_BLOCKER',error=str(e),total_online_steps=c.total if c else 36283,resumable_checkpoint=ck);raise
 finally:
  if monitor is not None:monitor.terminate();monitor.wait(timeout=15)
  phase('CAMPAIGN_EXIT');evidence('CAMPAIGN_EXIT',total=c.total if c else 36283)
if __name__=='__main__':run()
