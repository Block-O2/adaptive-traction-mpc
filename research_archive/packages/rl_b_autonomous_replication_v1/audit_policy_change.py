"""Same causal observations, different checkpoints; no new physical attempts."""
from common import ROOT,put
from pathlib import Path
import json,hashlib
import numpy as np

def main():
 import torch
 from stable_baselines3 import PPO
 from checkpoints import policy_hash
 torch.set_num_threads(1)
 cfg=json.loads((ROOT/'PPO_TRAINING_CONFIG.json').read_text());rows=[]
 for n in ['ALL_TRAINING_LOG.jsonl','ALL_EVALUATION_LOG.jsonl']:
  if (ROOT/n).exists():rows.extend(json.loads(s) for s in (ROOT/n).read_text().splitlines())
 result=[]
 for seed in cfg['seeds']:
  seedroot=ROOT/'seeds'/str(seed)/'stage1';progress=json.loads((seedroot/'PROGRESS.json').read_text());before=PPO.load(seedroot/'checkpoints/initial.zip',device='cpu');after=PPO.load(str(ROOT/progress['checkpoint'])+'.zip',device='cpu');selected=[r for r in rows if r['training_seed']==seed and r['stage']=='stage1'];obs=np.concatenate([np.load(ROOT/r['run']/'transitions_0.npz')['obs'] for r in selected],axis=0).astype(np.float32)
  a,_=before.predict(obs,deterministic=True);b,_=after.predict(obs,deterministic=True);d=np.abs(a-b)
  ev=[r for r in selected if r['mode']=='evaluate'];first=[np.load(ROOT/r['run']/'transitions_0.npz')['obs'][0] for r in ev];same_initial=max(float(np.max(np.abs(x-first[0]))) for x in first)
  result.append({'seed':seed,'initial_policy_sha256':policy_hash(before),'final_policy_sha256':policy_hash(after),'common_causal_observation_count':len(obs),'observation_sha256':hashlib.sha256(obs.tobytes()).hexdigest(),'initial_action_mean_on_common_observations':a.mean(0).tolist(),'final_action_mean_on_common_observations':b.mean(0).tolist(),'mean_absolute_action_change':d.mean(0).tolist(),'maximum_absolute_action_change':d.max(0).tolist(),'fraction_observations_changed_gt1e_6':float(np.mean(np.any(d>1e-6,axis=1))),'first_causal_observation_maxdiff_across_evaluations':same_initial,'actual_initial_eval_proposals':np.load(ROOT/next(r['run'] for r in ev if r['kind']=='initial_deterministic')/'transitions_0.npz')['actions'].tolist(),'final_checkpoint':progress['checkpoint'],'initial_log_std':before.policy.log_std.detach().cpu().numpy().tolist(),'final_log_std':after.policy.log_std.detach().cpu().numpy().tolist(),'pass':bool(policy_hash(before)!=policy_hash(after) and d.max()>1e-6 and same_initial<1e-7)})
 put(ROOT/'audit/POLICY_ACTION_CHANGE.json',{'seeds':result,'all_pass':all(x['pass'] for x in result),'actual_proposals_are_not_applied_torques':'Actual applied robot torque evidenced separately in native command receipts; policy weight change alone is not execution evidence.'})
 print(json.dumps({'all_pass':all(x['pass'] for x in result),'mean_action_change_by_seed':[{'seed':x['seed'],'change':x['mean_absolute_action_change']} for x in result]}))
if __name__=='__main__':main()
