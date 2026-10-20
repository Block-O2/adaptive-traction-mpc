"""Read actual trained checkpoint+restore evidence; no rollout and no update."""
from common import ROOT,put
import argparse,json,random,numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 import torch
 from checkpoints import load,policy_hash
 from ready_env import ReadyEnv
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 env=ReadyEnv(ROOT/'runs/never_reset_checkpoint_audit')
 try:
  before,record=load(ROOT/a.checkpoint,env);obs=np.linspace(-.2,.2,41,dtype=np.float32)
  expected=before.predict(obs,deterministic=False)[0];py_expected=random.random();np_expected=np.random.random();torch_expected=torch.rand(3)
  after,restored=load(ROOT/a.checkpoint,env);actual=after.predict(obs,deterministic=False)[0]
  def equal(x,y):
   if isinstance(x,dict):return x.keys()==y.keys() and all(equal(x[k],y[k]) for k in x)
   if isinstance(x,(list,tuple)):return len(x)==len(y) and all(equal(a,b) for a,b in zip(x,y))
   if isinstance(x,torch.Tensor):return torch.equal(x,y)
   return x==y
  steps=[float(v['step']) for v in before.policy.optimizer.state_dict()['state'].values() if 'step' in v]
  checks={'trained_update_exists':record['updates']>0,'actual_Adam_steps_exist':bool(steps) and min(steps)>0,'policy_exact':policy_hash(before)==policy_hash(after),'optimizer_exact':equal(before.policy.optimizer.state_dict(),after.policy.optimizer.state_dict()),'stochastic_action_exact':np.array_equal(expected,actual),'python_rng_exact':random.random()==py_expected,'numpy_rng_exact':np.random.random()==np_expected,'torch_rng_exact':torch.equal(torch.rand(3),torch_expected),'counters_exact':before.num_timesteps==after.num_timesteps and before._n_updates==after._n_updates}
  put(ROOT/a.out,{'category':'TRAINED_CHECKPOINT_RELOAD_NO_PHYSICS_NO_NEW_UPDATES','pass':all(checks.values()),'checks':checks,'checkpoint':a.checkpoint,'updates':record['updates'],'decisions':record['decisions']})
  if not all(checks.values()):raise RuntimeError('CHECKPOINT_RECOVERY_ASSERTIONS_FAILED')
 finally:env.close()
if __name__=='__main__':main()
