"""Exact state resume; recover already completed protocol evaluations without rerun."""
from common import *
from continue_21283 import ResumeCampaign,replay_digest
import copy,traceback
from stable_baselines3.common.save_util import load_from_zip_file

class PartialCampaign(ResumeCampaign):
 def snapshot(self,name):
  folder=O/'checkpoints'/name
  if name.startswith('candidate_') and folder.exists():
   _,params,variables=load_from_zip_file(folder/'model.zip',device='cuda');actual=self.model.get_parameters();assert all(digest(params[k])==digest(actual[k]) for k in params);assert torch.equal(variables['ent_coef_tensor'],self.model.ent_coef_tensor);log('PENDING_CHECKPOINT_RECOVERY.jsonl',dict(checkpoint=str(folder),total=self.total,exact_learning_components=True,new_updates=False));return folder
  return super().snapshot(name)
 def evaluation(self,name,scope='NATIVE',stochastic=False,actor_state=None):
  cached=L/('EVAL_legacy_predict_revision_'+name.replace('/','_')+'.json')
  if cached.exists() and (name.startswith('checkpoint/') or name.startswith('best_confirmation/')):
   row=json.loads(cached.read_text());req=json.loads((O/'evaluation_requests'/('legacy_predict_revision_'+name.replace('/','_')+'.json')).read_text());saved=torch.load(req['actor'],map_location='cpu',weights_only=False);assert digest(saved)==digest(self.model.actor.state_dict()),'CACHED_EVAL_ACTOR_MISMATCH';assert sha(R/row['trace'])==row['trace_sha256'];assert row['scope']==scope
   if not any(r['name']==row['name'] for r in self.rows):self.rows.append(row);self.eval_steps+=row['steps'];log('EVALUATIONS.jsonl',dict(**row,recovered_existing_completed_child=True))
   return row
  return super().evaluation(name,scope,stochastic,actor_state)

def run():
 campaign=None;monitor=None;folder=Path(sys.argv[1])
 try:
  resource('PRE_RESTORE_IDLE');campaign=PartialCampaign();campaign.restore_interrupted(folder);v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False);assert campaign.total==v['total_consumed_at_snapshot']>=26283;assert sha(v['history_path'])==v['history_sha256'];assert replay_digest(campaign.online)==replay_digest(v['online']);assert digest(campaign.best)==digest(v['best'])
  old=copy.deepcopy(campaign.model.actor);old.load_state_dict(torch.load(folder/'actor.pt',map_location='cuda',weights_only=False));x=torch.as_tensor(campaign.imitation['observations'],device='cuda',dtype=torch.float32)
  with torch.no_grad():assert torch.equal(old(x,True),campaign.model.actor(x,True))
  assert all(digest(v['rng'][k])==digest(rngs(campaign.sampler,None)[k]) for k in ('python','numpy','torch','cuda','sampler'));_,expected,variables=load_from_zip_file(folder/'model.zip',device='cuda');actual=campaign.model.get_parameters();assert all(digest(expected[k])==digest(actual[k]) for k in expected);assert torch.equal(variables['ent_coef_tensor'],campaign.model.ent_coef_tensor)
  save(f'CONTINUATION_RESUME_{campaign.total}_AUDIT.json',dict(status='PASS',checkpoint=str(folder),collection_steps=campaign.total,actor_updates=campaign.actor_updates,critic_updates=campaign.updates,RNG_after_mean_diagnosis_unchanged=True,model_targets_optimizers_alpha_exact=True,replay_history_exact=True,metadata_exact=True,deterministic_means_bitwise_equal_all_13852=True,previous_completed_evaluations_not_rerun=True,budget_not_reset=True));del v,old,x,actual,expected,variables
  monitor=subprocess.Popen([sys.executable,'-u',str(P/'resource_policy_v2.py'),str(os.getpid())],stdout=(L/'RESOURCE_MONITOR_RESUME.log').open('a'),stderr=subprocess.STDOUT);campaign.complete_pending_result();state('RESUMED_VERIFIED',total_online_steps=campaign.total,critic_updates=campaign.updates,actor_updates=campaign.actor_updates,error=None,next_action='complete pending checkpoint from validated cache then continue same total50000 budget',resumable_checkpoint=str(folder));campaign.bounded_training(campaign.formal_origin)
 except BaseException as e:
  if campaign is not None:
   if campaign.env is not None:campaign.env.close()
   try:checkpoint=campaign.snapshot('continuation_paused_exception_'+str(int(time.time())))
   except BaseException:checkpoint=None
  else:checkpoint=None
  save('CONTINUATION_EXCEPTION.json',dict(error=str(e),traceback=traceback.format_exc(),checkpoint=checkpoint));state('CONTINUATION_PAUSED',error=str(e),total_online_steps=campaign.total if campaign else None,resumable_checkpoint=checkpoint);print(traceback.format_exc(),flush=True);raise
 finally:
  if monitor is not None:monitor.terminate();monitor.wait(timeout=15)

if __name__=='__main__':run()
