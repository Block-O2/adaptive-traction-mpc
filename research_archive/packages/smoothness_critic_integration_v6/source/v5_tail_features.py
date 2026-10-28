"""Strict causal terminal-state capture for real rolling-tail experiments."""
import numpy as np
def capture(b,study,horizon_s):
 obs=np.asarray(b['observation'].as_array());ref=b['reference'];it=b['interface'];task=b['task_state'];phase=task.phase.value
 schedule=b.get('active_schedule');active_record=schedule.record() if schedule is not None and hasattr(schedule,'record') else {}
 suffix=schedule
 while hasattr(suffix,'suffix'):suffix=suffix.suffix
 record=suffix.record() if suffix is not None and hasattr(suffix,'record') else {}
 belief=b['belief'].value_state_record();runtime=b['runtime'];command=runtime.get('last_command');req=b.get('request')
 names=[];values=[]
 def add(name,x):
  x=np.asarray(x,float).ravel();names.extend([name+'_'+str(i) for i in range(len(x))]);values.extend(x.tolist())
 add('estimated_q_dq',obs);add('reference_q',ref.q_rad);add('reference_dq',ref.dq_rad_s);add('reference_ddq',ref.ddq_rad_s2)
 add('measured_force',it.measured_force_world_n);add('measured_moment',it.measured_moment_world_nm)
 add('phase_onehot',[phase==p for p in ['OUTBOUND','HOLD','RETURN']]);add('phase_elapsed_s',[task.phase_elapsed_s]);add('task_elapsed_s',[b['physical_now']-b['task_start_time']]);add('decision_counts',[study.count.get(p,0) for p in ['OUTBOUND','HOLD','RETURN']]);add('horizon_s',[horizon_s])
 for key,n in [('start_q_rad',2),('start_dq_rad_s',2),('target_q_rad',2),('target_dq_rad_s',2),('duration_s',1)]:
  add('active_schedule_'+key,record.get(key,np.zeros(n)))
 proposal=b.get('progress_proposal') or {}
 add('active_schedule_total_duration_s',[0. if schedule is None else schedule.duration_s])
 add('governor_progress',[proposal.get(k,0.) for k in ['previous_progress_s','desired_progress_s','selected_progress_s','delay_added_s']])
 for key in ['displacement_human_m','velocity_human_m_s','rotation_error_human_rad','angular_velocity_human_rad_s','human_position_world_m','human_rotation_world','human_velocity_world_m_s','human_angular_velocity_world_rad_s']:
  add('causal_interface_'+key,getattr(it,key,np.zeros((3,3)) if key=='human_rotation_world' else np.zeros(3)))
 lifecycle=runtime.get('plan_lifecycle');add('pipeline_has_outstanding_request',[lifecycle is not None and getattr(lifecycle,'_outstanding',None) is not None])
 add('causal_beta',getattr(b['belief'],'beta',np.zeros(11)));add('causal_residual_weights',getattr(b['belief'],'state_residual_weights_nm',np.zeros((2,5))))
 add('previous_executed_delta_q',getattr(b['planner'],'previous_executed_delta_q_rad',np.zeros(2)))
 add('current_applied_robot_torque',np.zeros(6) if command is None else command.joint_torque_command_nm)
 add('source_age_s',[0. if req is None else b['physical_now']-req.source_sample_time_s])
 out=dict(feature_names=names,features=values,phase=phase,physical_s=float(b['physical_now']),horizon_s=horizon_s,active_schedule=active_record,suffix_schedule=record,governor_proposal=proposal,belief_record=belief,observation_role='CAUSAL_MEASURED_ESTIMATED_REFERENCE_EXECUTION',truth_used=False,future_outcome_used=False)
 assert np.all(np.isfinite(values)),'NONFINITE_CAUSAL_TERMINAL_FEATURES'
 return out
