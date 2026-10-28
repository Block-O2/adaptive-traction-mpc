"""Atomic generation checkpoint: metadata is the commit marker; no executable secrets."""
from common import put
from pathlib import Path
import hashlib,json,os,random
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def policy_hash(model):
 h=hashlib.sha256()
 for n,t in model.policy.state_dict().items():h.update(n.encode());h.update(t.detach().cpu().numpy().tobytes())
 return h.hexdigest()
def contract():
 from common import ROOT
 # Freeze executable/config identity only; generated reports must not alter it.
 manifest=json.loads((ROOT/'FROZEN_CONTRACT_MANIFEST.json').read_text())['files']
 names={n:sha(ROOT/n) for n in sorted(manifest)}
 if names!=manifest:raise ValueError('FROZEN_EXECUTABLE_CONTRACT_CHANGED')
 return hashlib.sha256(json.dumps(names,sort_keys=True).encode()).hexdigest()

def save(model,base,metadata):
 import torch,numpy as np
 base=Path(base);base.parent.mkdir(exist_ok=True,parents=True)
 if base.with_suffix('.json').exists():raise ValueError('CHECKPOINT_GENERATION_EXISTS')
 model.save(base.with_suffix('.writing.zip'),exclude=['train']);os.replace(base.with_suffix('.writing.zip'),base.with_suffix('.zip'))
 rng={'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state()}
 torch.save(rng,base.with_suffix('.writing.pt'));os.replace(base.with_suffix('.writing.pt'),base.with_suffix('.rng.pt'))
 record={**metadata,'category':'REAL_PPO_CHECKPOINT','decisions':model.num_timesteps,'updates':model._n_updates,'policy_sha256':policy_hash(model),'model_sha256':sha(base.with_suffix('.zip')),'rng_sha256':sha(base.with_suffix('.rng.pt')),'contract_sha256':contract(),'resume_semantics':'fresh physical episode; partial rollout discarded'}
 put(base.with_suffix('.writing.json'),record);os.replace(base.with_suffix('.writing.json'),base.with_suffix('.json'));return record
def load(base,env):
 import torch,numpy as np
 from stable_baselines3 import PPO
 base=Path(base);record=json.loads(base.with_suffix('.json').read_text())
 if record['contract_sha256']!=contract():raise ValueError('CHECKPOINT_CONTRACT_MISMATCH')
 if sha(base.with_suffix('.zip'))!=record['model_sha256'] or sha(base.with_suffix('.rng.pt'))!=record['rng_sha256']:raise ValueError('CHECKPOINT_HASH_MISMATCH')
 model=PPO.load(base.with_suffix('.zip'),env=env,device='cpu',force_reset=True)
 if policy_hash(model)!=record['policy_sha256'] or model.num_timesteps!=record['decisions'] or model._n_updates!=record['updates']:raise ValueError('CHECKPOINT_COUNTER_OR_WEIGHTS_MISMATCH')
 rng=torch.load(base.with_suffix('.rng.pt'),weights_only=False);random.setstate(rng['python']);np.random.set_state(rng['numpy']);torch.set_rng_state(rng['torch'])
 return model,record
