from pathlib import Path
import sys,os,pickle,copy,json,time,struct,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1',FAST_NATIVE_GEOMETRY='N6',FAST_NATIVE_VALUE_TREE='N8',FAST_NATIVE_QUINTIC='N9',FAST_NATIVE_INTERVALS='N12',FAST_NATIVE_BOOL_REDUCTIONS='N13')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_task_owner as owner,worker_allocation_reuse as reuse
owner.warm();original,fast=reuse.install()
inputs=pickle.loads((S/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl').read_bytes());planner,args=pickle.loads(next(r['payload'] for r in inputs if r['phase']=='HOLD'));model=args['belief'].human_model()
def exact(want,got):
 assert want.keys()==got.keys()
 for k,v in want.items():
  if isinstance(v,np.ndarray):assert type(got[k]) is type(v) and got[k].dtype==v.dtype and got[k].shape==v.shape and got[k].tobytes()==v.tobytes(),k
  elif isinstance(v,float):assert struct.pack('d',v)==struct.pack('d',got[k]),k
  else:assert v==got[k],k
rng=np.random.default_rng(2026100726);cases=0;scope=dict(cache={},hits=0,misses=0);token=owner.SCOPE.set(scope)
try:
 for _ in range(1000):
  q=rng.uniform(.05,2.3,2);tau=rng.uniform(-100,100,2);want=original(model,tau,q)
  first=fast(model,tau,q);exact(want,first);second=fast(model,tau.copy(),q.copy());exact(want,second)
  assert not np.shares_memory(first['wrench_world'],second['wrench_world'])
  first['wrench_world'][0]+=1.;exact(want,fast(model,tau,q));cases+=3
 # Complete model dependencies must invalidate, including fields not used in allocation.
 for mutation in ('beta','origin_world_m','joint_axis_world','plane_x_world','plane_z_world','hip_plane_m','knee_to_cuff_in_cuff_m','thigh_length_m'):
  other=copy.deepcopy(model)
  if mutation=='beta':other.beta[0]*=1.001
  elif mutation=='thigh_length_m':object.__setattr__(other.geometry,mutation,other.geometry.thigh_length_m*1.001)
  else:getattr(other.geometry,mutation).flat[0]+=1e-5
  q=np.array([.7,.8]);tau=np.array([10.,11.]);before=scope.get('numerical_counts',{}).get('allocation_miss',0)
  exact(original(other,tau,q),fast(other,tau,q));assert scope['numerical_counts']['allocation_miss']==before+1;cases+=1
 for tau,q in ((np.array([np.nan,0.]),np.array([.7,.8])),(np.array([1.,2.,3.]),np.array([.7,.8])),([1.,2.],[.7,.8])):
  try:want=original(model,tau,q)
  except Exception as e:
   try:fast(model,tau,q)
   except type(e) as actual:assert str(e)==str(actual)
   else:raise AssertionError('error changed')
  else:exact(want,fast(model,tau,q))
  cases+=1
finally:owner.SCOPE.reset(token)
assert owner.SCOPE.get() is None;exact(original(model,np.ones(2),np.ones(2)),fast(model,np.ones(2),np.ones(2)))
out=dict(status='PASS',cases=cases+1,bit_exact=True,independent_output_ownership=True,complete_model_key_invalidations=True,no_cross_request_reuse=True,all_original_samples_and_inverse_API_preserved=True,no_physics=True,counts=scope['numerical_counts'])
sc.save('W3_ALLOCATION_LOCAL_REGRESSION.json',out);print(json.dumps(out))
