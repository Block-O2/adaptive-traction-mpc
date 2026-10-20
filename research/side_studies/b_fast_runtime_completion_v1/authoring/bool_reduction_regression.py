from pathlib import Path
import sys,time,json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc,native_interface_adapter as a,native_bool_reductions as b
b.install()
from traction_mpc_stage5 import loaded_execution as le
rng=np.random.default_rng(2026100722);cases=0
for shape in ((),(0,),(1,),(3,),(6,),(200,),(2048,),(0,3),(3,0),(2,3),(6,6),(8,256)):
 for repeat in range(50):
  x=rng.random(shape)<.5
  if not isinstance(x,np.ndarray):x=np.asarray(x)
  layouts=[x,np.asfortranarray(x)]
  if x.ndim:layouts.append(x[::-1])
  for value in layouts:
   for original,fast in ((np.all,le.np.all),(np.any,le.np.any)):
    expected=original(value);actual=fast(value);assert type(expected) is type(actual) and expected.tobytes()==actual.tobytes() and bool(expected)==bool(actual);cases+=1
for x in (np.ones((2,2,2),dtype=bool),np.ones(2049,dtype=bool),np.array([0.,1.]),[True,False],np.array([1.,np.nan]),np.matrix([[True,False]])):
 for original,fast in ((np.all,le.np.all),(np.any,le.np.any)):
  for kwargs in ({},{'axis':0},{'keepdims':True}):
   try:want=original(x,**kwargs)
   except Exception as e:
    try:fast(x,**kwargs)
    except type(e) as actual:assert str(actual)==str(e)
    else:raise AssertionError('original error changed')
   else:
    actual=fast(x,**kwargs);assert type(want) is type(actual) and np.array_equal(want,actual)
   cases+=1
times={}
for size in (3,6,21,2048):
 x=np.ones(size,dtype=bool)
 for label,fn in (('original',np.all),('N13',le.np.all)):
  samples=[]
  for _ in range(2000):
   t=time.monotonic_ns();fn(x);samples.append((time.monotonic_ns()-t)/1000)
  times[f'{size}_{label}_us']=float(np.median(samples))
out=dict(status='PASS',cases=cases,bit_exact=True,numpy_bool_scalar_type_preserved=True,unsupported_signature_dtype_subclass_fallback=True,scope=list(b.MODULES),timings=times,no_native_physics=True)
sc.save('N13_BOOL_LOCAL_REGRESSION.json',out);print(json.dumps(out))
