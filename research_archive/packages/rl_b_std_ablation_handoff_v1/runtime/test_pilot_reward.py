"""Independent no-physics counterexample and corrected-return arithmetic."""
from common import ROOT,put
from pilot_env import PilotEnv
import numpy as np
rows=[]
for phi in [0.,.5,1.,2.,2.9]:
 for jf,v in [(0.,0.),(100.,0.),(3000.,10.),(6000.,30.),(7000.,40.)]:
  env=PilotEnv(ROOT/'test_outputs');env._initialize();env.phi=phi;env.force_integral=jf;env.motion_variation=v;env._reward();env._reward(failure=True)
  cost=.0002*jf+.01*v;actual=sum(env.reward_totals.values());expected=-10-max(1.5,cost)
  assert abs(actual-expected)<1e-10 and env.reward_totals['progress']==0
  rows.append({'phi':phi,'JF':jf,'variation':v,'return':actual,'expected':expected});env.close()
assert all(abs(x['return']+11.5)<1e-10 for x in rows if .0002*x['JF']+.01*x['variation']<=1.5)
put(ROOT/'PILOT_REWARD_TESTS.json',{'category':'TEST_ONLY_NO_PHYSICS','pass':True,'tests':rows,'inherited_v2_counterexample':{'short_failed_return':-10.,'long_failed_return':-11.2,'strict_partial_no_low_JF_advantage':False},'v3_all_safe_failed_costs_at_same_floor':True})
print('PILOT_REWARD_TESTS PASS',len(rows))
