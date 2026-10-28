from pathlib import Path
import sys,time,json,dataclasses,numpy as np
S=Path('/home/hank/ihear-lab/learning_guided_motion_improvement_v1/runtime');sys.path.insert(0,str(S/'code'))
def main():
 import study_common as sc,native_interface_adapter as a
 from traction_mpc_stage3.human import soft_limit_torque,HUMAN
 from native_soft_limits import parameter_key
 rng=np.random.default_rng(20261007);cases=[]
 for _ in range(5000):
  h=dataclasses.replace(HUMAN,soft_limit_margin_rad=float(rng.uniform(.001,.2)),soft_limit_boundary_torque_nm=float(rng.uniform(1,100)),soft_limit_damping_nms_rad=float(rng.uniform(0,10)))
  cases.append((h,rng.uniform(-4,4,2),rng.uniform(-10,10,2)))
 h=HUMAN;lower=np.asarray(h.q_min_rad)+h.soft_limit_margin_rad-h.soft_limit_numerical_tolerance_rad;upper=np.asarray(h.q_max_rad)-h.soft_limit_margin_rad+h.soft_limit_numerical_tolerance_rad
 for threshold in (lower,upper):
  for toward in (-np.inf,0,np.inf):
   for velocity in (-1.,-0.,0.,1.):cases.append((h,np.nextafter(threshold,toward),np.full(2,velocity)))
 maxerr=0.;original=[];native=[];failures=[]
 for h,q,dq in cases:
  p=np.asarray(parameter_key(h));t=time.monotonic_ns();x=soft_limit_torque(q,dq,h);original.append(time.monotonic_ns()-t)
  t=time.monotonic_ns();y=a.native.soft_limit_arrays(q,dq,p);native.append(time.monotonic_ns()-t)
  error=float(np.max(np.abs(x-y)));maxerr=max(maxerr,error)
  if not np.array_equal(x,y):failures.append(dict(q=q.tolist(),dq=dq.tolist(),expected=x.tolist(),actual=y.tolist(),error=error))
 out=dict(status='PASS' if not failures else 'FAIL',cases=len(cases),bit_exact=not failures,max_abs_error=maxerr,first_failures=failures[:5],original_median_us=float(np.median(original)/1e3),native_median_us=float(np.median(native)/1e3),source_sha256=sc.sha(S/'native/fast_native.cpp'))
 sc.save('SOFT_LIMIT_N4_LOCAL_REGRESSION.json',out);print(json.dumps(out));assert not failures,out
if __name__=='__main__':main()
