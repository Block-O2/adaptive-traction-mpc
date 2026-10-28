from common import *
import shutil
def run():
 tests=[]
 for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');tests.append(str(p.name))
 old=read('LOCK.json');new={str(p):sha(p) for p in P.glob('*.py')};save('IMPLEMENTATION_REVISION_BEFORE_TRAINING.json',dict(old=old['sources'],new=new,scientific_config_unchanged=sha(L/'PREREGISTRATION.json')==old['config'],changes=['stable RNG tensor digest avoids object-storage pickle identifiers','calibration collection steps moved from evaluation-only ledger to training collection ledger','new mechanical checks']))
 save('LOCK.json',dict(config=old['config'],sources=new))
 torch.manual_seed(192);torch.cuda.manual_seed_all(192);rng=np.random.default_rng(23);e=gym.Env();e.reset(seed=25);before=rngs(rng,e);after=rngs(rng,e);assert digest(before)==digest(after)
 a=actor('cuda');a.log_std.requires_grad_(False)
 with torch.no_grad():a.log_std.weight.zero_();a.log_std.bias.fill_(-8.)
 x=torch.randn(32,55,device='cuda');mean,ls,_=a.get_action_dist_params(x);ac,lp=a.action_log_prob(x);assert torch.isfinite(lp).all();assert torch.allclose(ls,torch.full_like(ls,-8.))
 # Analytical transformed Gaussian density agrees with SB3 including its epsilon Jacobian.
 latent=a.action_dist.gaussian_actions;base=torch.distributions.Normal(mean,ls.exp()).log_prob(latent).sum(1);manual=base-torch.log(1-ac**2+1e-6).sum(1);assert torch.allclose(lp,manual,atol=2e-5)
 b=copy=None
 q=np.load(V/'round_04/evaluation_1/episode_00001/POLICY_TRANSITIONS.npz');d=read('HOLD_DIAGNOSIS.json');obs=q['observations'][q['phase']=='HOLD'];d['first_recorded_policy_dwell_threshold_task_s']=float(obs[np.flatnonzero(obs[:,48]*.5>=.5-1e-6)[0],44]*30);d['hold_target_changes']=int(np.any(np.diff(q['actions'][q['phase']=='HOLD'],axis=0)!=0,axis=1).sum());d['dwell_source']='qualified round4 evaluation1 only';save('HOLD_DIAGNOSIS.json',d)
 for rd in (3,4):
  for j in (1,2,3):
   ep=V/f'round_{rd:02d}/evaluation_{j}/episode_00001';z=np.load(ep/'POLICY_TRANSITIONS.npz');real=np.load(ep/'SAC_ACTOR_ACTIONS.npz');np.testing.assert_array_equal(z['actions'],real['raw_action']);np.testing.assert_array_equal(z['executed_actions'].astype(np.float32),real['executed_action']);assert np.array_equal(z['next_observations'][:-1],z['observations'][1:]);assert (z['terminated']|z['truncated'])[-1]
 save('MECHANICAL_CHECKS.json',dict(status='PASS',compiled=tests,RNG_digest_stable=True,transformed_Gaussian_log_prob_consistent=True,qualified_pure_transitions_verified=True))
 for p in P.glob('*.py'):shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
 print('MECHANICAL_PASS',flush=True)
if __name__=='__main__':run()
