"""Separate frozen deterministic evaluation; never updates the optimizer."""
from common import ROOT,put
import argparse,os,time,numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--checkpoint',required=True);p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=20262021);a=p.parse_args()
 if not a.enable:raise RuntimeError('DISABLED_REQUIRE_EXPLICIT_ENABLE')
 if os.environ.get('IHEAR_GUARDED')!='1':raise RuntimeError('OUTER_RESOURCE_GUARD_REQUIRED')
 out=ROOT/a.out;out.mkdir(parents=True,exist_ok=False);os.environ['IHEAR_RUN_DIR']=str(out)
 from runtime_setup import install
 install()
 import torch
 from ready_env import ReadyEnv
 from checkpoints import load,policy_hash
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 env=ReadyEnv(out/'env',retain_trace=True);rows=[]
 try:
  model,metadata=load(ROOT/a.checkpoint,env);before=policy_hash(model);updates=model._n_updates;obs,info=env.reset(seed=a.seed)
  for i in range(128):
   action,_=model.predict(obs,deterministic=True);obs,reward,term,trunc,info=env.step(action);rows.append({'reward':reward,'done':term or trunc})
   if term or trunc:break
  put(out/'RESULT.json',{'category':'FROZEN_DEVELOPMENT_EVALUATION','seed':a.seed,'status':info.get('status'),'success':info.get('success',False),'decisions':len(rows),'return':sum(x['reward'] for x in rows),'no_weight_change':before==policy_hash(model),'no_updates':updates==model._n_updates,'metrics':env.metrics(),'heldout_or_patient_generalization':False})
 finally:env.close()
if __name__=='__main__':main()
