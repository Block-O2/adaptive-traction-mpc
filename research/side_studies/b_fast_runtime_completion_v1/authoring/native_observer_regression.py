from pathlib import Path
import sys,pickle,json,copy,time,dataclasses,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc
from traction_mpc_stage5 import controller_interface as ci
import native_vectors;native_vectors.install(expanded=True)
import native_observer
original,fast=native_observer.install();rows=pickle.loads((S/'inputs/030_N5_V3_A1_C1c_science_nominal_FULL_CONTROLLER_CAUSAL.pkl').read_bytes());rng=np.random.default_rng(2026100717);cases=0;first=None;maxerror=0.;timings={'original':[],'N7':[]}
for index in range(2400):
 runtime,kw,_=pickle.loads(rows[index%len(rows)]['inputs']);measurement=kw['measurement'];observer=runtime['observer'];timestamp=float(measurement.sample_time_s)
 observer.parameters=dataclasses.replace(observer.parameters,observer_fixed_point_iterations=[1,3,6][index%3])
 if index%4==0:observer._last=None
 else:
  last=copy.deepcopy(observer._last);object.__setattr__(last,'sample_timestamp_s',timestamp-[.001,.005,.01,.1][index%4]);observer._last=last
  for name in ('displacement_human_m','rotation_error_human_rad'):getattr(last,name)[:]+=rng.uniform(-1e-3,1e-3,3)
 for name in ('cuff_force_vector_n','cuff_moment_vector_nm','attachment_velocity_m_s','attachment_angular_velocity_rad_s'):
  value=np.asarray(getattr(measurement,name)).copy()+rng.uniform(-.1,.1,3);object.__setattr__(measurement,name,value)
 expected=original(observer,measurement,timestamp);actual=fast(observer,measurement,timestamp)
 for name,value in vars(expected).items():
  got=getattr(actual,name)
  if isinstance(value,np.ndarray) and value.tobytes()!=got.tobytes():
   maxerror=max(maxerror,float(np.max(np.abs(value-got))))
   if first is None:first=dict(index=index,field=name,expected=value.tolist(),actual=got.tolist())
  elif not isinstance(value,np.ndarray):assert value==got
 cases+=1
 if index<600:
  for label,function in (('original',original),('N7',fast)):
   start=time.monotonic_ns();function(observer,measurement,timestamp);timings[label].append((time.monotonic_ns()-start)/1e3)
out=dict(status='PASS' if first is None else 'FAIL',bit_exact=first is None,cases=cases,first_difference=first,max_abs_error=maxerror,timing_us={k:dict(zip(('p50','p95','p99','max'),np.percentile(v,[50,95,99,100]).tolist())) for k,v in timings.items()},native_physics_steps=0,model_API_calls=0,scope='original fixed-point iteration counts, first/prior inversion, perturbed saved causal measurements and old observer state; unchanged SciPy rotation/NumPy matrix products')
sc.save('N7_OBSERVER_LOCAL_REGRESSION.json',out);print(json.dumps(out))
