"""Independent density/ownership checks; no environment reset, model mutation, or gradient."""
from pathlib import Path
import json,sys,math
from research_common import ROOT,atomic,now
sys.path.insert(0,str(ROOT/'runtime'))
import numpy as np
import torch
from torch.distributions import Normal
checks={}
x=torch.tensor([[.7,.2],[-.5,.8]],dtype=torch.float32);m=torch.tensor([[.6,.5],[.1,.2]],dtype=torch.float32)
small=Normal(m,torch.full_like(m,.2));original=Normal(m,torch.tensor([.98653877,.98126632]));lp=small.log_prob(x).sum(-1)
checks['same_sampling_and_old_density_ratio_is_one']=bool(torch.equal(torch.exp(lp-lp),torch.ones(2)))
checks['reusing_checkpoint_density_after_std_change_is_not_ratio_one']=bool(torch.max(torch.abs(torch.exp(lp-original.log_prob(x).sum(-1))-1))>.1)
ref=-np.log(.2*math.sqrt(2*math.pi))-((x.numpy()-m.numpy())/.2)**2/2
checks['independent_density_formula_matches']=bool(np.allclose(lp.numpy(),ref.sum(-1),rtol=1e-6))
plan=json.loads((ROOT/'configs/STD_PLAN_v3.json').read_text())
checks['main_streams_new_and_not_historical']=not set(plan['streams'])&{2026102191,2026102192,2026102193,2026102194,2026102101}
checks['attempt_plan_28_with_ceiling32']=len(plan['plans'])==28 and plan['ceiling']==32
for rng in plan['streams']+[plan['pilot_stream']]:
 z=np.load(ROOT/f'noise/z_{rng}.npy');checks[f'noise_{rng}']=z.shape==(128,2) and z.dtype==np.float32 and bool(np.isfinite(z).all())
atomic(ROOT/'audit/FROZEN_MATH_TESTS.json',dict(time_utc=now(),checks=checks,pass_=all(checks.values()),physics=0,Adam=0));assert all(checks.values());print('density and plan checks PASS; no physics or learning')
