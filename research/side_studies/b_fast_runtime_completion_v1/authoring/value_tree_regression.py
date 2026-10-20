from pathlib import Path
import sys,pickle,json,types,time,io,enum,hashlib,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc,loaded_context_reuse as reuse
import native_value_tree
old,fast=native_value_tree.install();slow=types.FunctionType(old.__code__,dict(old.__globals__),old.__name__,old.__defaults__,old.__closure__);slow.__globals__['raw']=slow
def encode(value):
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True;encoder.dump(value);return stream.getvalue()
class E(enum.Enum):a='a';b=7
class L(list):pass
class D(dict):pass
class F(float):pass
class A(np.ndarray):pass
rng=np.random.default_rng(2026100718);cases=[]
manual=[None,False,True,-3,2**100,0.,-0.,float('nan'),float('inf'),F(1),E.a,E.b,np.int64(1),np.float32(1),np.float64(-0.),np.complex128(1+2j),'a',b'x',float,dict,list,(),[],{},L([1,2]),D(x=3),np.dtype('float64'),types.SimpleNamespace(a=np.arange(3),dynamic=17)]
for n in range(1000):
 array=rng.normal(size=(3,4));array[0,0]=-0.
 cases.extend([array,array[:,::-1],np.asfortranarray(array),array.view(A),np.asarray([1,2],dtype='>f8'),dict(values=[manual[n%len(manual)],array],label='x',owner=types.SimpleNamespace(version=n,parameters=(1.,2.)))])
cases+=manual
for row in pickle.loads((S/'inputs/030_N5_V3_A1_C1c_science_nominal_FULL_CONTROLLER_CAUSAL.pkl').read_bytes()):
 runtime,kwargs,public=pickle.loads(row['inputs']);cases.extend((runtime,kwargs,public))
taskrows=pickle.loads((S/'inputs/019_N4_V2_C2_science_deviation_TASK_CAUSAL.pkl').read_bytes())
for row in taskrows:cases.extend((pickle.loads(row['payload']),pickle.loads(row['expected'])))
first=None;timing={'python':[],'N8':[]}
for index,value in enumerate(cases):
 wanted=slow(value);actual=fast(value)
 if encode(wanted)!=encode(actual):
  first=dict(index=index,type=str(type(value)),expected_sha=hashlib.sha256(encode(wanted)).hexdigest(),actual_sha=hashlib.sha256(encode(actual)).hexdigest());break
 if index>=len(cases)-42:
  for label,function in (('python',slow),('N8',fast)):
   for repeat in range(20):
    start=time.monotonic_ns();function(value);timing[label].append((time.monotonic_ns()-start)/1e3)
out=dict(status='PASS' if first is None else 'FAIL',cases=len(cases),exact_complete_tree_and_memo_free_bytes=first is None,first_difference=first,timing_us={k:dict(zip(('p50','p95','p99','max'),np.percentile(v,[50,95,99,100]).tolist())) for k,v in timing.items() if v},native_physics_steps=0,model_API_calls=0,scope='all raw fields retained; ndarray layout/dtype/bytes, float bits, enums, subclass and unknown-object fallback, complete saved controller and TASK graphs')
sc.save('N8_VALUE_TREE_LOCAL_REGRESSION.json',out);print(json.dumps(out))
