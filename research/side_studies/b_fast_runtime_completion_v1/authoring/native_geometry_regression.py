from pathlib import Path
import sys,json,time,copy,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry as G
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1 as E
import native_vectors;native_vectors.install(expanded=True)
import native_geometry
original,fast,original_j,fast_j,original_reg,fast_reg=native_geometry.install();rng=np.random.default_rng(2026100716);cases=0;maximum=0.;first=None
g=G(np.array([0.,0.,.93]),np.array([1.,0.,0.]),np.array([0.,1.,0.]),np.array([0.,0.,1.]),np.array([0.,0.]),.44,np.array([.3,0.]))
for index in range(2400):
 geometry=copy.deepcopy(g)
 if index%3==0:
  for field in ('origin_world_m','plane_x_world','plane_z_world','hip_plane_m','knee_to_cuff_in_cuff_m'):
   object.__setattr__(geometry,field,rng.uniform(-2,2,getattr(geometry,field).shape))
 elif index%3==1:geometry.plane_x_world[2]=[0.,1e-9,-1e-9,1e-9-1e-15,-1e-9+1e-15][index%5]
 envelope=E(geometry,shank_length_upper_m=float(rng.uniform(.1,1)),existing_shank_margin_m=float(rng.uniform(-.1,.1)),cuff_reference_translation_world_m=tuple(rng.uniform(-.1,.1,3)))
 count=[1,2,21,1201][index%4];q=rng.uniform(-4,4,(count,2))
 if index%4==1:q=np.array([[-0.,0.],[np.pi,np.pi]])
 for layout in (q,np.asfortranarray(q),q[0] if count==1 else q[::-1]):
  wanted=original(envelope,layout);actual=fast(envelope,layout)
  for name in wanted:
   if wanted[name].tobytes()!=actual[name].tobytes():
    err=float(np.max(np.abs(wanted[name]-actual[name])));maximum=max(maximum,err)
    if first is None:first=dict(index=index,name=name,q=layout.tolist(),wanted=wanted[name].tolist()[:8],actual=actual[name].tolist()[:8],geometry=sc.clean(geometry))
  cases+=1
for index in range(10000):
 q=rng.uniform(-4,4,2);v=rng.uniform(-10,10,2);a=rng.uniform(-10,10,2)
 if index==0:q*=0;v*=0;a*=0
 wanted=original_j(g,q);actual=fast_j(g,q)
 if wanted.tobytes()!=actual.tobytes():
  if first is None:first=dict(kernel='J',q=q.tolist(),expected=wanted.tolist(),actual=actual.tolist())
  maximum=max(maximum,float(np.max(np.abs(wanted-actual))))
 wanted=original_reg(q,v,a);actual=fast_reg(q,v,a)
 if wanted.tobytes()!=actual.tobytes():
  if first is None:first=dict(kernel='REGRESSOR',q=q.tolist(),v=v.tolist(),a=a.tolist(),expected=wanted.tolist(),actual=actual.tolist())
  maximum=max(maximum,float(np.max(np.abs(wanted-actual))))
 cases+=2
for q in (np.empty((0,2)),np.array([np.nan,0]),np.array([np.inf,0]),np.zeros(3),np.ones((3,3))):
 try:wanted=original(E(g),q)
 except Exception as e:
  try:fast(E(g),q)
  except type(e) as actual:assert str(actual)==str(e)
  else:raise AssertionError('rejection changed')
 else:assert all(wanted[k].tobytes()==fast(E(g),q)[k].tobytes() for k in wanted)
 cases+=1
timings={}
for count in (1,21,1201):
 q=rng.uniform(0,2,(count,2));envelope=E(g)
 for label,function in (('original',original),('N6',fast)):
  values=[]
  for repeat in range(300):
   start=time.monotonic_ns();function(envelope,q);values.append((time.monotonic_ns()-start)/1e3)
  timings[str(count)+'_'+label+'_us']=dict(zip(('p50','p95'),[float(v) for v in np.percentile(values,[50,95])]))
out=dict(status='PASS' if first is None else 'FAIL',cases=cases,bit_exact=first is None,max_abs_error=maximum,first_difference=first,timings=timings,native_physics_steps=0,model_API_calls=0)
sc.save('N6_GEOMETRY_LOCAL_REGRESSION.json',out);print(json.dumps(out))
