"""N10 original 21-model-call mechanics loop, complete output semantics."""
from pathlib import Path
import sys,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 sys.path.insert(0,str(S/'build'));import fast_native as n
 from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as p
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule
 C=p.AdaptiveMechanicsScreenV22;original=C.evaluate
 def evaluate(self,belief,candidate,schedule):
  if type(belief) is not p.AdaptiveHumanBeliefV22 or type(schedule) is not QuinticHumanWaypointSchedule:return original(self,belief,candidate,schedule)
  model=belief.human_model()
  peak_force,peak_moment,peak_residual,finite=n.mechanics_loop(model,schedule,np.linspace(0.,schedule.duration_s,self.sample_count),np.linalg.norm)
  feasible=bool(finite and peak_force<=self.force_limit_n+1e-9 and peak_moment<=self.moment_limit_nm+1e-9)
  return dict(evaluated=True,feasible=feasible,rejection_reason=None if feasible else 'adaptive_model_mechanics_limit',belief_sequence=belief.sequence,candidate_label=candidate.label,model='frozen_v2_2_state_residual_human_model',sample_count=self.sample_count,peak_force_n=peak_force,peak_moment_nm=peak_moment,peak_state_residual_nm=peak_residual,force_limit_n=self.force_limit_n,moment_limit_nm=self.moment_limit_nm,deployable_truth_consumed=False)
 C.evaluate=evaluate;INSTALLED=True;return original,evaluate
