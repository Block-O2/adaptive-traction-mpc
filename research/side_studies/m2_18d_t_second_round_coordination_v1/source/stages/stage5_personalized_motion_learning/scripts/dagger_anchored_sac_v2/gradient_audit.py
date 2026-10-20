"""Post-run fixed-batch actor gradient evidence, with no physics or updates."""
from common import *
from stable_baselines3 import SAC
from stable_baselines3.common.save_util import load_from_zip_file
class SpacesOnly(gym.Env):
 def __init__(self):self.observation_space=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32);self.action_space=gym.spaces.Box(-1.,1.,(2,),np.float32)
 def reset(self,**kw):raise RuntimeError('NO_PHYSICS_ALLOWED')
def run():
 cfg=read('PREREGISTRATION.json');model=SAC('MlpPolicy',SpacesOnly(),device='cpu',buffer_size=1,ent_coef=cfg['alpha'],policy_kwargs=dict(net_arch=[256,256]));pi0=actor();pi0.load_state_dict(torch.load(V/'qualified_actor.pt',map_location='cpu',weights_only=False)['state_dict']);pi0.requires_grad_(False).eval();im=np.load(O/'IMITATION_ONLY.npz');h=np.load(O/'HISTORY_RL.npz');rows=[]
 candidates=[p for p in (O/'checkpoints').iterdir() if p.is_dir() and (p.name.startswith('candidate_') or p.name.startswith('failed_small') or p.name=='final_attempt_state')]
 for folder in sorted(candidates):
  _,params,_=load_from_zip_file(folder/'model.zip',device='cpu');model.policy.load_state_dict(params['policy']);model.actor.log_std.requires_grad_(False);model.critic.requires_grad_(False);v=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False);rng=np.random.default_rng(7123);torch.manual_seed(7123);hi=rng.integers(len(h['actions']),size=64);oi=rng.integers(len(v['online']),size=192);x=torch.as_tensor(np.concatenate([h['observations'][hi],np.stack([v['online'][i]['observations'] for i in oi])]),dtype=torch.float32);ids=np.concatenate([rng.choice(np.flatnonzero(im['phase']==p),96) for p in ('OUTBOUND','HOLD','RETURN')]);anchor_x=torch.as_tensor(im['observations'][ids],dtype=torch.float32);ac,lp=model.actor.action_log_prob(x);q=torch.min(torch.cat(model.critic(x,ac),1),1).values;sl=(cfg['alpha']*lp-q).mean()
  with torch.no_grad():ref=pi0(anchor_x,True)
  al=torch.mean(torch.sum((model.actor(anchor_x,True)-ref)**2,1));trainable=[p for p in model.actor.parameters() if p.requires_grad];gs=torch.autograd.grad(sl,trainable,retain_graph=True);ga=torch.autograd.grad(v['lam']*al,trainable);ns=float(torch.sqrt(sum((g*g).sum() for g in gs)));na=float(torch.sqrt(sum((g*g).sum() for g in ga)));dot=float(sum((s*a).sum() for s,a in zip(gs,ga)));rows.append(dict(checkpoint=str(folder),SAC_loss=float(sl.detach()),anchor_squared_distance=float(al.detach()),weighted_anchor_loss=float((v['lam']*al).detach()),SAC_gradient_norm=ns,weighted_anchor_gradient_norm=na,gradient_cosine=None if ns*na==0 else dot/(ns*na),weighted_anchor_to_SAC_gradient_ratio=None if ns==0 else na/ns,lambda_=v['lam'],actor_lr=v['actor_lr'],log_std=v['std'],anchor_phase_samples=dict(OUTBOUND=96,HOLD=96,RETURN=96),RL_samples=dict(history=64,online=192),no_updates=True,mean_squared_norm_definition='mean over samples of sum over both action dimensions'))
 save('GRADIENT_SCALE_AUDIT.json',dict(rows=rows,scope='post-run fixed legal batches, CPU numerical gradients; no training RNG, rollout or weights modified; not causal component ablation'))
 print(json.dumps(clean(rows)),flush=True)
if __name__=='__main__':run()
