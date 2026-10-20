"""N5 exact fixed-shape dispatch; scalar/batch edge cases retain originals."""
import sys,numpy as np
from pathlib import Path
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_lowforce_repair_explore_10h_v1')
INSTALLED=set()
def install(*,frames=True,features=True):
 sys.path.insert(0,str(S/'build'));import fast_native as native
 if frames and 'frames' not in INSTALLED:
  from traction_mpc_stage3.frames import RigidTransform
  def post(self):
   rotation=np.asarray(self.rotation,dtype=float);translation=np.asarray(self.translation,dtype=float)
   if rotation.shape!=(3,3) or translation.shape!=(3,):raise ValueError('RigidTransform requires a 3x3 rotation and 3-vector')
   native.validate_rigid(rotation,np.linalg.det)
   object.__setattr__(self,'rotation',rotation.copy());object.__setattr__(self,'translation',translation.copy())
  RigidTransform.__post_init__=post;INSTALLED.add('frames')
 if features and 'features' not in INSTALLED:
  from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as f
  import loaded_context_reuse as reuse
  original=f._state_residual_features
  def feature(state,rom_human=f.HUMAN):
   x=np.asarray(state,dtype=float);lo=np.asarray(rom_human.q_min_rad,dtype=float);hi=np.asarray(rom_human.q_max_rad,dtype=float)
   if x.shape!=(4,) or lo.shape!=(2,) or hi.shape!=(2,):return original(state,rom_human)
   return native.state_features4(x,lo,hi,f.STATE_RESIDUAL_VELOCITY_SCALE_RAD_S)
  reuse.aliases(original,feature);INSTALLED.add('features')
