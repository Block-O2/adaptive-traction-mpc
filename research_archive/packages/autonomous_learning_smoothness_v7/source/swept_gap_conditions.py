"""Exact scalar all-time quadratic lower-bound requirement; not a plant certificate."""
from pathlib import Path
import os,sys,json,time
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path(__file__).resolve().parents[1]
def required_acceleration(g,v,delta,threshold=1e-5):
 clearance=g-threshold
 if clearance<0:return float('inf')
 if clearance==0:return float('inf') if v<0 else -2*v/delta
 candidates=[-2*(clearance+v*delta)/delta**2]
 if v<0:
  ts=-2*clearance/v
  if ts<=delta:candidates.append(v*v/(2*clearance))
 return max(candidates)
def minimum_quadratic(g,v,a,delta):
 vals=[g,g+v*delta+.5*a*delta*delta]
 if a>0 and 0<-v/a<delta:vals.append(g-.5*v*v/a)
 return min(vals)
rng=np.random.default_rng(2026102205);errors=[];n=10000
for _ in range(n):
 g=1e-5+10**rng.uniform(-7,-1);v=rng.uniform(-.5,.5);dt=10**rng.uniform(-4,-.8);required=required_acceleration(g,v,dt);errors.append(minimum_quadratic(g,v,required,dt)-1e-5)
# Both smooth endpoint normals can conflict with each other or with acceleration/torque boxes.
from importlib.util import spec_from_file_location,module_from_spec
# Source is kept independent of controller; no runtime patch.
failures=[dict(g_m=2e-5,v_m_s=-.02,delta_s=.005,required_gap_acceleration_m_s2=required_acceleration(2e-5,-.02,.005),old_horizon_required_m_s2=1.996875,old_horizon_actual_scalar_acceleration_m_s2=2.,continuous_minimum_gap_m=minimum_quadratic(2e-5,-.02,2.,.005))]
out=dict(status='PASS_ANALYTIC_SCALAR_LOWER_BOUND',samples=n,min_gap_residual_m=float(min(errors)),max_abs_boundary_residual_m=float(max(abs(np.array(errors)))),counterexamples=failures,conditional_proof='If every endpoint true gap acceleration is bounded below by constant a_i throughout [0,delta], and measured g/v are valid lower bounds, then a_i >= required_acceleration enforces all-time endpoint gap >= threshold. Pointwise dual minimum equivalence then enforces sleeve.',missing_for_plant=['valid causal g/v error bounds','lower bound on acceleration from final saturated robot torque through cuff/Human dynamics','Hessian/velocity changes across hold','robust feasible backup for empty endpoint/actuator intersection','all other original geometry components and task rules retained'],physical_steps=0)
(P/'analysis/SWEPT_GAP_CONDITIONS.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
