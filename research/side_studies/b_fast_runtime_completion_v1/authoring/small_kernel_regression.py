from pathlib import Path
import sys,json,numpy as np,copy,types,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
from traction_mpc_stage3.frames import RigidTransform as RT
from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as f
from scipy.spatial.transform import Rotation
ORIGINAL=(RT.__post_init__,f._state_residual_features)
import native_small_kernels as small
small.install();rng=np.random.default_rng(20261007);features=0;matrices=0
states=list(rng.uniform(-100,100,(5000,4)))+[np.zeros(4),np.array([-0.,0.,-0.,0.]),np.array([np.nan,0,0,0]),np.array([np.inf,0,0,0]),np.zeros((3,4)),np.zeros(3)]
for state in states:
 for rom in (f.HUMAN,types.SimpleNamespace(q_min_rad=np.array([-.3,-.2]),q_max_rad=np.array([2.5,2.8]))):
  try:expected=ORIGINAL[1](state,rom)
  except ValueError as e:
   try:f._state_residual_features(state,rom)
   except ValueError as actual:assert str(actual)==str(e)
   else:raise AssertionError('INVALID_STATE_ACCEPTED')
  else:
   actual=f._state_residual_features(state,rom);assert expected.shape==actual.shape and expected.tobytes()==actual.tobytes(),(state,expected,actual)
  features+=1
rotations=list(Rotation.random(3000,random_state=rng).as_matrix())
for amount in (0.,-1e-12,1e-12,-1e-5,1e-5,-5e-6,5e-6):
 for i in range(3):
  for j in range(3):
   m=np.eye(3);m[i,j]+=amount;rotations.append(m)
rotations += [np.diag([-1.,1.,1.]),np.full((3,3),np.nan),np.full((3,3),np.inf),np.zeros((3,3)),np.ones((2,2))]
for rotation in rotations:
 for layout in (np.array(rotation,order='C'),np.array(rotation,order='F')):
  obj=RT.__new__(RT);object.__setattr__(obj,'rotation',layout);object.__setattr__(obj,'translation',np.array([np.nan,-0.,1.]))
  try:ORIGINAL[0](obj)
  except ValueError as error:
   try:RT(layout,np.array([np.nan,-0.,1.]))
   except ValueError as actual:assert str(actual)==str(error)
   else:raise AssertionError('INVALID_ROTATION_ACCEPTED')
  else:
   actual=RT(layout,np.array([np.nan,-0.,1.]));assert obj.rotation.tobytes()==actual.rotation.tobytes() and obj.translation.tobytes()==actual.translation.tobytes()
  matrices+=1
out=dict(status='PASS',feature_cases=features,rotation_cases=matrices,bit_exact=True,original_accept_reject_and_error=True,model_API_calls=0,native_physics_steps=0,
 notes='Same NumPy Gram product and determinant; exact original allclose rtol=1e-5/atol=1e-12. Native scalar features retain batch fallback, dtype and operation order.')
(S/'output/N5_SMALL_KERNEL_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
