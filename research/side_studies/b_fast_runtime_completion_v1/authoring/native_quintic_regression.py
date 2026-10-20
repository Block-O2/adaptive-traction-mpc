from pathlib import Path
import sys,json,time,types,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc,native_quintic
original,fast=native_quintic.install();rng=np.random.default_rng(2026100719);cases=0;first=None;maximum=0.;timings={'original':[],'N9':[]}
for index in range(8000):
 duration=float(rng.uniform(.05,10));c=rng.uniform(-3,3,(2,6));c=np.array(c,order='F' if index%2 else 'C');schedule=types.SimpleNamespace(duration_s=duration,coefficients=c)
 for elapsed in (0.,-0.,duration,2*duration,float(rng.uniform(0,duration))):
  wanted=original(schedule,elapsed);actual=fast(schedule,elapsed)
  for name in vars(wanted):
   v=getattr(wanted,name);a=getattr(actual,name)
   if v.tobytes()!=a.tobytes():
    maximum=max(maximum,float(np.max(np.abs(v-a))))
    if first is None:first=dict(index=index,field=name,duration=duration,elapsed=elapsed,expected=v.tolist(),actual=a.tolist(),coefficients=c.tolist())
  assert not any(np.shares_memory(getattr(actual,a),getattr(actual,b)) for a,b in (('q_rad','dq_rad_s'),('q_rad','ddq_rad_s2'),('dq_rad_s','ddq_rad_s2')))
  assert not np.shares_memory(actual.q_rad,c);cases+=1
 if index<1000:
  for label,function in (('original',original),('N9',fast)):
   start=time.monotonic_ns();function(schedule,duration*.371);timings[label].append((time.monotonic_ns()-start)/1e3)
for elapsed in (-.1,np.nan,np.inf,'invalid'):
 schedule=types.SimpleNamespace(duration_s=.5,coefficients=np.ones((2,6)))
 try:original(schedule,elapsed)
 except Exception as error:
  try:fast(schedule,elapsed)
  except type(error) as actual:assert str(actual)==str(error)
  else:raise AssertionError('invalid elapsed accepted')
 cases+=1
for duration in (1e-300,1e300,np.float64(.5),0.,float('nan')):
 schedule=types.SimpleNamespace(duration_s=duration,coefficients=np.ones((2,6)))
 try:wanted=original(schedule,.1)
 except Exception as error:
  try:fast(schedule,.1)
  except type(error) as actual:assert str(actual)==str(error)
  else:raise AssertionError('invalid mutated duration accepted')
 else:assert all(getattr(wanted,n).tobytes()==getattr(fast(schedule,.1),n).tobytes() for n in vars(wanted))
 cases+=1
out=dict(status='PASS' if first is None else 'FAIL',cases=cases,bit_exact=first is None,max_abs_error=maximum,first_difference=first,timing_us={k:dict(zip(('p50','p95','p99','max'),np.percentile(v,[50,95,99,100]).tolist())) for k,v in timings.items()},model_API_calls=0,native_physics_steps=0,scope='same scalar powers and NumPy matmul, named finite checks, independent fresh outputs; unsupported/extreme cases use original')
sc.save('N9_QUINTIC_LOCAL_REGRESSION.json',out);print(json.dumps(out))
