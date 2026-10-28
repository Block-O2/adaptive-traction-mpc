"""TEST_ONLY no-physics original absolute authority with synthetic sensor history."""
from common import ROOT,put,load_config
from types import SimpleNamespace
from traction_mpc_stage5.split_acceleration_monitor import HumanMotionAccelerationAuthorityV1
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import reference_safe_task_transition
from traction_mpc_stage5.task import GoalTaskState,TaskPhase,transition_phase
import numpy as np
_,_,spec,_=hidden_plant(load_config()[0]);authority=HumanMotionAccelerationAuthorityV1(spec.task_joint_acceleration_limit_rad_s2);tests=[]
for scale,expected in [(0.,False),(1.,False),(1.000001,True)]:
 sample=SimpleNamespace(sample_timestamp_s=1.,human_motion_acceleration_rad_s2=np.array(spec.task_joint_acceleration_limit_rad_s2)*scale,human_motion_history_coverage_s=.02,human_motion_history_sample_count=5,human_motion_valid=True)
 verdict=authority.evaluate(sample)
 tests.append({'test':'original_acceleration_threshold_'+str(scale),'pass':verdict.violation==expected,'reason':verdict.abort_reason,'truth_used':verdict.truth_used_online})
 if expected:
  for phase in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN):
   state=GoalTaskState(phase,1.,0.,True,phase is TaskPhase.RETURN)
   proposed=transition_phase(spec,state,np.radians([60.,60.]),[0.,0.],.005,ddq_rad_s2=sample.human_motion_acceleration_rad_s2,abort_reason=verdict.abort_reason)
   final=reference_safe_task_transition(spec,state,proposed,.005,True,continuous_hold=True)
   tests.append({'test':'original_safety_overrides_phase_'+phase.value,'pass':final.phase is TaskPhase.ABORTED and final.abort_reason=='TASK_ACCELERATION_LIMIT'})
put(ROOT/'SAFETY_AUTHORITY_TESTS.json',{'category':'TEST_ONLY_NO_PHYSICS_SYNTHETIC_20MS_HISTORY','tests':tests,'pass':all(x['pass'] for x in tests)})
assert all(x['pass'] for x in tests)
print(tests)
