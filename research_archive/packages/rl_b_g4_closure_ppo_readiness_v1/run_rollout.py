"""Explicit low-budget physics qualification/benchmark; no learning."""
from common import ROOT,put
import os,argparse,time,numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--policy',choices=['hold','maximal','random'],required=True);p.add_argument('--repeats',type=int,default=1);p.add_argument('--out',type=str,required=True);a=p.parse_args()
 if not a.enable:raise RuntimeError('DISABLED_REQUIRE_EXPLICIT_ENABLE')
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_RESOURCE_GUARD_REQUIRED')
 if not 1<=a.repeats<=2:raise ValueError('SHORT_ROLLOUT_ONLY')
 out=ROOT/a.out;out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 from runtime_setup import install
 install()
 from ready_env import ReadyEnv
 env=ReadyEnv(out/'env',retain_trace=True);results=[]
 try:
  for repeat in range(a.repeats):
   obs,info=env.reset(seed=20261021+repeat);initial=obs.copy();rows=[];rng=np.random.default_rng(20261021+repeat)
   for i in range(128):
    action=np.full(2,-1. if a.policy=='hold' else 1.,np.float32) if a.policy!='random' else rng.uniform(-1,1,2).astype(np.float32)
    before=obs.copy();obs,reward,term,trunc,info=env.step(action);rows.append((before,action,reward,obs.copy(),term,trunc))
    print('DECISION',i+1,env.last_task_time,flush=True)
    if term or trunc:break
   metrics=env.metrics();metrics.update(status=info.get('status'),abort_reason=info.get('abort_reason'),success=info.get('success',False),terminated=term,truncated=trunc,seed=20261021+repeat)
   put(out/f'episode_{repeat}.json',metrics);results.append(metrics)
   np.savez_compressed(out/f'transitions_{repeat}.npz',obs=[x[0] for x in rows],actions=[x[1] for x in rows],rewards=[x[2] for x in rows],next_obs=[x[3] for x in rows],terminated=[x[4] for x in rows],truncated=[x[5] for x in rows])
   env.close()
  put(out/'RESULT.json',{'category':'SHORT_REAL_NATIVE_PHYSICS_NO_LEARNING','policy':a.policy,'episodes':results})
 finally:env.close()
if __name__=='__main__':main()
