"""TEST_ONLY synthetic boundary and source regression checks; no physics."""
from common import ROOT,put,load_config
from dataclasses import replace
from types import SimpleNamespace
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import reference_safe_task_transition,SensorSupportedTaskClock,return_finalization_reason
from traction_mpc_stage5.task import TaskPhase,GoalTaskState
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
import json,numpy as np
_,_,spec,_=hidden_plant(load_config()[0]);tests=[]
for phase,next_phase in [(TaskPhase.OUTBOUND,TaskPhase.HOLD),(TaskPhase.HOLD,TaskPhase.RETURN),(TaskPhase.RETURN,TaskPhase.COMPLETE)]:
 for ready in [False,True]:
  before=GoalTaskState(phase,9.999,0.,True,phase is TaskPhase.RETURN)
  proposed=replace(before,phase=next_phase,phase_elapsed_s=0.,outbound_hold_completed=next_phase in (TaskPhase.RETURN,TaskPhase.COMPLETE))
  result=reference_safe_task_transition(spec,before,proposed,.006,ready,continuous_hold=True)
  tests.append({'test':f'late_arrival_cannot_override_{phase.value}_ready_{ready}','pass':result.phase is TaskPhase.ABORTED and result.abort_reason=='TIMEOUT_'+phase.value})
# A sensor stream which never satisfies HOLD must not accumulate dwell.
clock=SensorSupportedTaskClock();state=GoalTaskState(TaskPhase.HOLD,0.,0.,True,False)
for i in range(2001):
 state=clock.transition(spec,state,np.radians([60.,60.]),[0.,0.],.005,sample_time_s=i*.005,ddq_rad_s2=[0.,0.])
 if state.phase is TaskPhase.ABORTED:break
tests.append({'test':'HOLD_unestablished_10s_sensor_clock_timeout','pass':state.abort_reason=='TIMEOUT_HOLD' and state.hold_elapsed_s==0.})
# Duplicate notifications must not create continuous dwell.
clock=SensorSupportedTaskClock();state=GoalTaskState(TaskPhase.HOLD,0.,0.,True,False)
for _ in range(100):state=clock.transition(spec,state,spec.outbound_goal_target_rad,[0.,0.],0.,sample_time_s=1.,ddq_rad_s2=[0.,0.])
tests.append({'test':'zero_time_duplicate_has_zero_HOLD_credit','pass':state.phase is TaskPhase.HOLD and state.hold_elapsed_s==0.})
for kwargs,reason in [({'return_elapsed_s':10.005,'task_elapsed_s':19.03},'TIMEOUT_RETURN'),({'return_elapsed_s':9.,'task_elapsed_s':30.005},'GLOBAL_TASK_TIMEOUT')]:
 value=return_finalization_reason(physical_age=0.,host_age=0.,horizon_s=.01,phase_timeout_s=10.,task_timeout_s=30.,**kwargs)
 tests.append({'test':'causal_commit_'+reason,'pass':value==reason})
put(ROOT/'REPAIR_BOUNDARY_TESTS.json',{'category':'TEST_ONLY_NO_PHYSICS','tests':tests,'pass':all(x['pass'] for x in tests)})
print(tests)
assert all(x['pass'] for x in tests)
