from pathlib import Path
import sys,json,time,copy,struct,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc,native_intervals
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry as G
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1 as E
from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
original,fast=native_intervals.install();rng=np.random.default_rng(2026100720)
g=G(np.array([0.,0.,.93]),np.array([1.,0.,0.]),np.array([0.,1.,0.]),np.array([0.,0.,1.]),np.array([0.,0.]),.44,np.array([.3,0.]))
def bits(x):
 if isinstance(x,float):return struct.pack('d',x)
 if isinstance(x,dict):return [(k,bits(v)) for k,v in x.items()]
 if isinstance(x,(list,tuple)):return [bits(v) for v in x]
 return x
cases=0;failed=[];timings={'original':[],'N12':[]}
for index in range(5000):
 q0=rng.uniform(0,np.pi,2);delta=rng.uniform(0,np.pi,2)-q0;c=np.outer(delta,[0.,0.,0.,10.,-15.,6.]);c[:,0]=q0
 if index%5==0:c[index%2,index%6]+=rng.choice([-1.,1.])*rng.choice([1e-16,1e-12,1e-10,1e-8])
 if index%7==0:c=rng.uniform(-5,5,(2,6))
 if index==0:c=np.zeros((2,6))
 geometry=copy.deepcopy(g)
 envelope=E(geometry,shank_length_upper_m=float(rng.uniform(.1,1)),existing_shank_margin_m=float(rng.uniform(0,.1)),cuff_reference_translation_world_m=tuple(rng.uniform(-.1,.1,3)))
 for name,fn in (('original',original),('N12',fast)):
  t=time.monotonic_ns();value=fn(envelope,c);timings[name].append((time.monotonic_ns()-t)/1e3)
  if name=='original':want=value
  else:
   if bits(want)!=bits(value):failed.append(dict(index=index,c=c.tolist(),want=want,actual=value))
 cases+=1
for c in (np.full((2,6),1e200),np.ones((3,6)),np.array([[np.nan]*6]*2),np.array([[np.inf]*6]*2)):
 try:want=original(E(g),c)
 except Exception as e:
  try:fast(E(g),c)
  except type(e) as actual:assert str(e)==str(actual)
  else:raise AssertionError('error changed')
 else:assert bits(want)==bits(fast(E(g),c))
 cases+=1
out=dict(status='PASS' if not failed else 'FAIL',bit_exact=not failed,cases=cases,first_failures=failed[:2],timings_us={k:dict(zip(('p50','p95','p99'),np.percentile(v,[50,95,99]).tolist())) for k,v in timings.items()},no_native_physics=True,math='Every original binary64 nextafter/interval operation and original trig/endpoint routines; no new bound or threshold',source_sha256=sc.sha(S/'native/fast_native.cpp'))
sc.save('N12_INTERVAL_LOCAL_REGRESSION.json',out);print(json.dumps(out));assert not failed
