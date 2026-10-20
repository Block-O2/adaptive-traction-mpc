"""N9 exact original quintic powers, matmul and finite sample semantics."""
from pathlib import Path
import sys,numpy as np,math
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1');INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 sys.path.insert(0,str(S/'build'));import fast_native as n
 from traction_mpc_stage5 import human_waypoint_scheduler as h
 original=h.QuinticHumanWaypointSchedule.sample
 def sample(self,elapsed_s):
  coefficients=self.coefficients
  if type(self.duration_s) is not float or not 1e-150<=self.duration_s<=1e150 or type(coefficients) is not np.ndarray or coefficients.dtype!=np.dtype('float64') or coefficients.shape!=(2,6):return original(self,elapsed_s)
  if not math.isfinite(elapsed_s) or elapsed_s<0:raise ValueError('elapsed_s must be finite and nonnegative')
  q,dq,ddq=n.quintic_sample(coefficients,float(elapsed_s),self.duration_s)
  # C++ already performs the original named finite-two-vector validation.
  # All three arrays are separate new owning buffers, as in original samples.
  out=h.ScheduledHumanReferenceSample.__new__(h.ScheduledHumanReferenceSample)
  for name,value in (('q_rad',q),('dq_rad_s',dq),('ddq_rad_s2',ddq)):object.__setattr__(out,name,value)
  return out
 h.QuinticHumanWaypointSchedule.sample=sample;INSTALLED=True;return original,sample
