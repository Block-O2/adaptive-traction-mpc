"""Pure complete-input geometry reuse and immutable original TASK regressions."""
from pathlib import Path
import sys,pickle,copy,time,json,os,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
os.environ.update(FAST_NATIVE_SMALL_KERNELS='N5',FAST_ADMISSION_KEY='RAW_A1')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,fast_task_owner,admission_certificates
from traction_mpc_stage5.full3d_adaptive_integration_v1 import rigid_table_reference as r,monotonic_clearance as m
from loaded_context_reuse import raw,aliases
from traction_mpc_stage4 import estimator_v2 as ma
import geometry_transaction_reuse as g
ident=sys.argv[1];rows=[v for v in pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes()) if 'expected' in v]
fast_task_owner.warm();captured=[];originals={name:getattr(r.RigidTableReferenceEnvelopeV1,name) for name in ('margins','cuff_centers','check_quintic')};originals['monotonic_certificate']=m.monotonic_certificate
def capture(original):
 def call(*a,**k):
  out=original(*a,**k)
  if len(captured)<140:captured.append((original,pickle.dumps((a,k),protocol=5),pickle.dumps(out,protocol=5)))
  return out
 return call
for name,function in originals.items():
 if name=='monotonic_certificate':aliases(function,capture(function))
 else:setattr(r.RigidTableReferenceEnvelopeV1,name,capture(function))
baseline=[];before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
for row in rows:
 start=time.monotonic_ns();value=fast_task_owner.task_with_certificates(row['payload']);baseline.append((time.monotonic_ns()-start)/1e6)
 assert {k:v for k,v in sc.clean(value['value']).items() if k!='runtime_ms'}=={k:v for k,v in sc.clean(pickle.loads(row['expected'])).items() if k!='runtime_ms'}
for name,function in originals.items():
 if name=='monotonic_certificate':
  current=m.monotonic_certificate;aliases(current,function)
 else:setattr(r.RigidTableReferenceEnvelopeV1,name,function)
g.install();cases=0;mutations=0
for original,payload,expected in captured:
 a,k=pickle.loads(payload);wanted=pickle.loads(expected);wrapped=g.wrap(original);token=g.SCOPE.set({})
 try:
  assert raw(wrapped(*a,**k))==raw(wanted)
  returned=wrapped(*a,**k);assert raw(returned)==raw(wanted)
  if isinstance(returned,dict):returned.clear()
  elif isinstance(returned,np.ndarray):returned[...] = 99
  assert raw(wrapped(*a,**k))==raw(wanted);cases+=1
  # Every raw field change, including otherwise-unused dynamic attributes,
  # invalidates. Original operation still determines its value or rejection.
  envelope=a[0]
  variants=[]
  for owner_name,owner in (('envelope',envelope),('geometry',envelope.geometry)):
   for field,value in vars(owner).items():
    if isinstance(value,(float,int)) and not isinstance(value,bool):
     changed=copy.deepcopy(a);obj=changed[0] if owner_name=='envelope' else changed[0].geometry
     object.__setattr__(obj,field,value+1e-7 if isinstance(value,float) else value+1);variants.append(changed)
    elif isinstance(value,np.ndarray) and value.size:
     changed=copy.deepcopy(a);obj=changed[0] if owner_name=='envelope' else changed[0].geometry
     getattr(obj,field).flat[0]+=1e-7;variants.append(changed)
  changed=copy.deepcopy(a);object.__setattr__(changed[0],'extra_dependency_test',17);variants.append(changed)
  for changed in variants:
   count=len(g.SCOPE.get())
   try:want=original(*changed,**k)
   except (ValueError,ArithmeticError) as error:
    try:wrapped(*changed,**k)
    except type(error) as actual:assert str(actual)==str(error)
    else:raise AssertionError('rejection changed')
   else:
    assert raw(wrapped(*changed,**k))==raw(want);assert len(g.SCOPE.get())>count
   mutations+=1
 finally:g.SCOPE.reset(token)
os.environ['FAST_GEOMETRY_TRANSACTION']='GEO1';g.ROWS.clear();timings=[]
for row in rows:
 times=[]
 for repeat in range(5):
  start=time.monotonic_ns();value=fast_task_owner.task_with_certificates(row['payload']);times.append((time.monotonic_ns()-start)/1e6)
  expected=pickle.loads(row['expected'])
  assert {k:v for k,v in sc.clean(value['value']).items() if k!='runtime_ms'}=={k:v for k,v in sc.clean(expected).items() if k!='runtime_ms'}
  assert admission_certificates.prepare(row['payload'],expected)['proofs']==value['multirate_mechanics_certificates']['proofs']
 timings.append(dict(phase=row['phase'],request_id=row['request_id'],baseline_first_ms=baseline[len(timings)],geo1_p50_ms=float(np.median(times)),geo1_max_ms=max(times)))
out=dict(status='PASS',captured_original_calls=cases,dependency_mutations=mutations,worker_timings=timings,reuse_counts=g.ROWS,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,native_physics_steps=0,bit_exact=True,scope='all original argument/envelope fields rekeyed per call; caller output mutation cannot modify cached bytes; one request/control transaction only')
sc.save(ident+'_GEO1_LOCAL_REGRESSION.json',out);print(json.dumps(out))
