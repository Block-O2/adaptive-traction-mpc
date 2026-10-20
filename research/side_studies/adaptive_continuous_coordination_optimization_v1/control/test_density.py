from pathlib import Path
import sys,json,pickle
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');sys.path.insert(0,str(P/'tests'))
from fixture import *
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import *
f=fixture();rows=[]
for n in [1,2,3]:
 for sign in [0,1,-1]:
  fractions=np.linspace(0,1,n+2)[1:-1].tolist();spec=dict(fractions=fractions,deltas_deg=[[0.,sign*.01] for _ in fractions]);intent={**f['context'],'perturbation_deg':[0.,sign*.01],'study_spec':spec}
  s=adapt_decision(f['decision'],f['planner'],f['belief'],intent).executed.schedule;assert s.certificate['feasible'];pickle.loads(pickle.dumps(s)).assert_integrity();assert len(s.segments)==n+1, (n,len(s.segments),build_reference.__code__.co_filename)
  for t in [0,s.duration_s]:
   for key in ['q_rad','dq_rad_s','ddq_rad_s2']:assert np.max(abs(getattr(s.sample(t),key)-getattr(s.original.sample(t),key)))<1e-10
  rows.append(dict(n=n,sign=sign,feasible=True,C2_jumps=s.certificate['joint_boundary_jumps'],reference_id=s.sealed_digest))
for bad in [dict(fractions=[.5,.4],deltas_deg=[[0,0],[0,0]]),dict(fractions=[.5],deltas_deg=[[0,.051]]),dict(fractions=[.5],time_fractions=[1.],deltas_deg=[[0,0]])]:
 try:adapt_decision(f['decision'],f['planner'],f['belief'],{**f['context'],'perturbation_deg':[0,0],'study_spec':bad})
 except ValueError:rows.append(dict(invalid=bad,rejected=True))
 else:raise AssertionError('invalid passed')
(P/'DENSITY_MATH_TESTS.json').write_text(json.dumps(dict(status='PASS',rows=rows),indent=2));print('DENSITY_MATH_PASS',len(rows))
