"""Resume orchestration only; frozen Campaign training implementation is unchanged."""
from common import *
from train import Campaign
from stable_baselines3.common.save_util import load_from_zip_file
import traceback,copy

class ResumeCampaign(Campaign):
 def evaluation(self,name,scope='NATIVE',stochastic=False,actor_state=None):
  cached=L/'EVAL_legacy_predict_revision_best_confirmation_a1_p10000_NATIVE.json'
  if name=='best_confirmation/a1_p10000_NATIVE' and cached.exists():
   row=json.loads(cached.read_text());request=O/'evaluation_requests/legacy_predict_revision_best_confirmation_a1_p10000_NATIVE.json';req=json.loads(request.read_text());saved=torch.load(req['actor'],map_location='cpu',weights_only=False)
   assert digest(saved)==digest(self.model.actor.state_dict()),'CACHED_CONFIRMATION_ACTOR_MISMATCH';assert sha(R/row['trace'])==row['trace_sha256'];assert row['valid']
   if not any(r['name']==row['name'] for r in self.rows):self.rows.append(row);self.eval_steps+=row['steps'];log('EVALUATIONS.jsonl',dict(**row,recovered_completed_confirmation_before_rng_diagnostic_repair=True))
   return row
  return super().evaluation(name,scope,stochastic,actor_state)

def replay_digest(rows):
 h=hashlib.sha256()
 for r in rows:h.update(digest(r).encode())
 return h.hexdigest()

def run():
 campaign=None;monitor=None
 try:
  resource('CONTINUATION_PRECONSTRUCTION');campaign=ResumeCampaign();folder=Path(read('RESOURCE_PAUSE_CLOSEOUT.json')['resumable_checkpoint']);campaign.restore_interrupted(folder);v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False)
  assert campaign.total==21283 and campaign.updates==30010 and campaign.actor_updates==1010
  assert sha(v['history_path'])==v['history_sha256'];assert replay_digest(campaign.online)==replay_digest(v['online']);assert digest(campaign.best)==digest(v['best']) and str(campaign.last_good)==v['last_good']
  _,params,variables=load_from_zip_file(folder/'model.zip',device='cuda');actual=campaign.model.get_parameters();assert all(digest(params[k])==digest(actual[k]) for k in params);assert torch.equal(variables['ent_coef_tensor'],campaign.model.ent_coef_tensor)
  paused_actor=copy.deepcopy(campaign.model.actor);paused_actor.load_state_dict(torch.load(folder/'actor.pt',map_location='cuda',weights_only=False));x=torch.as_tensor(campaign.imitation['observations'],device='cuda',dtype=torch.float32)
  before=rngs(campaign.sampler,None)
  with torch.no_grad():old=paused_actor(x,True);current=campaign.model.actor(x,True)
  assert torch.equal(old,current),'RESTORED_MEAN_CHANGED';assert digest(before)==digest(rngs(campaign.sampler,None));assert all(digest(v['rng'][k])==digest(rngs(campaign.sampler,None)[k]) for k in ('python','numpy','torch','cuda','sampler')),'DIAGNOSTIC_CHANGED_RESTORED_RNG';del paused_actor,old,current,x
  audit=dict(status='PASS',restored_from_step=21283,checkpoint=str(folder),critic_updates=campaign.updates,actor_updates=campaign.actor_updates,deterministic_mean_bitwise_equal_all_13852=True,network_target_optimizer_digests={k:dict(expected=digest(params[k]),actual=digest(actual[k])) for k in params},fixed_alpha=float(campaign.model.ent_coef_tensor),replay_steps=len(campaign.online),replay_sha256=replay_digest(campaign.online),history_sha256=v['history_sha256'],rng_hashes={k:digest(y) for k,y in v['rng'].items()},sampler_global_env_rng_verified_by_existing_restore=True,metadata_restored=True,lambda_=campaign.lam,log_std=campaign.std,actor_lr=campaign.model.actor.optimizer.param_groups[0]['lr'],spent_budget_not_reset=True)
  save('CONTINUATION_RESUME_AUDIT.json',audit);del params,actual,v
  monitor=subprocess.Popen([sys.executable,'-u',str(P/'resource_policy_v2.py'),str(os.getpid())],stdout=(L/'RESOURCE_MONITOR_RESUME.log').open('a'),stderr=subprocess.STDOUT)
  # Recover completed 10k evaluations; do not rerun/recount these interactions.
  prefix='legacy_predict_revision/checkpoint/a1_p10000_';native=[r for r in campaign.rows if r['name'].startswith(prefix+'NATIVE_')];matched=[r for r in campaign.rows if r['name'].startswith(prefix+'MATCHED_')];stoch=next(r for r in campaign.rows if r['name']==prefix+'STOCHASTIC');assert len(native)==len(matched)==2
  candidate=Path(read('RESOURCE_PAUSE_CLOSEOUT.json')['latest_native_good_checkpoint']);capable=all(r['valid'] for r in native);assert capable
  with torch.no_grad():
   x=torch.as_tensor(campaign.imitation['observations'],device='cuda',dtype=torch.float32);drift=campaign.model.actor(x,True)-campaign.pi0(x,True)
  rec=dict(attempt=1,point=10000,total_online_steps=21283,native_valid=2,matched_valid=sum(r['valid'] for r in matched),stochastic_valid=stoch['valid'],mean_drift_RMSE=float(torch.sqrt(torch.mean(drift**2))),mean_drift_peak=float(drift.abs().max()),checkpoint=str(candidate),lambda_=campaign.lam,std=campaign.std)
  assert not any(r['point']==10000 for r in campaign.checkpoints);campaign.checkpoints.append(rec);campaign.consecutive+=1;campaign.last_good=candidate;log('CAPABILITY.jsonl',dict(**rec,recovered_pending_after_resource_resume=True));del x,drift
  before=rngs(campaign.sampler,None);updates=(campaign.updates,campaign.actor_updates);resource('BEFORE_PENDING_10K_CONFIRMATION');campaign.record_best_and_results(10000,candidate,native,matched,stoch,rec);resource('AFTER_PENDING_10K_CONFIRMATION');assert updates==(campaign.updates,campaign.actor_updates) and digest(before)==digest(rngs(campaign.sampler,None))
  save('PENDING_10K_CONFIRMATION.json',dict(status='PASS',native=campaign.best['NATIVE'],collection_steps_unchanged=campaign.total,actor_updates_before_and_after=campaign.actor_updates,critic_updates_before_and_after=campaign.updates,parent_RNG_unchanged=True,no_training_updates_before_confirmation=True));campaign.snapshot('resumed_verified_21283_after_pending_10k');state('RESUMED_VERIFIED',total_online_steps=21283,critic_updates=campaign.updates,actor_updates=campaign.actor_updates,error=None,pending_10k_confirmation='PASS')
  campaign.bounded_training(campaign.formal_origin)
 except BaseException as e:
  if campaign is not None:
   if campaign.env is not None:campaign.env.close()
   try:checkpoint=campaign.snapshot('continuation_paused_exception_'+str(int(time.time())))
   except BaseException:checkpoint=None
  else:checkpoint=None
  save('CONTINUATION_EXCEPTION.json',dict(error=str(e),traceback=traceback.format_exc(),checkpoint=checkpoint));state('CONTINUATION_PAUSED',error=str(e),total_online_steps=campaign.total if campaign else 21283,resumable_checkpoint=checkpoint);print(traceback.format_exc(),flush=True);raise
 finally:
  if monitor is not None:monitor.terminate();monitor.wait(timeout=15)

if __name__=='__main__':run()
