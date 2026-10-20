from pathlib import Path
import sys,json,time,inspect,gzip,hashlib,shutil
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1/source');S=R/'stages/stage5_personalized_motion_learning';P=S/'scripts/single_human_sac_expert_v1';D=S/'docs/single_human_sac_expert_v1';O=S/'results/single_human_sac_expert_v1_r2'
sys.path.insert(0,str(P))
import final_qualification as f
from sac_env import SACExpertEnv,load_case_options,rt,TaskPhase
original=rt.reference_safe_task_transition;records=[]
def observed(spec,previous,proposed,physical_dt,reference_ready,**kwargs):
 result=original(spec,previous,proposed,physical_dt,reference_ready,**kwargs)
 if previous.phase is TaskPhase.HOLD:
  loc=inspect.currentframe().f_back.f_locals;schedule=loc.get('active_schedule')
  records.append(dict(physical_now=loc['physical_now'],truth_time_s=loc['truth'].time_s,phase_elapsed_s=previous.phase_elapsed_s,physical_dt=physical_dt,hold_elapsed_s=previous.hold_elapsed_s,proposed=proposed.phase.value,result=result.phase.value,reference_ready=reference_ready,active_segment_complete=loc.get('active_segment_complete'),schedule_start=loc.get('schedule_start_time'),schedule_duration=None if schedule is None else schedule.duration_s,reference_q=loc['reference_state'][:2].tolist(),reference_dq=loc['reference_state'][2:].tolist(),reference_ddq=loc['reference_acceleration'].tolist(),active_candidate=None if schedule is None else schedule.candidate.label))
 return result
if __name__=='__main__':
 rt.reference_safe_task_transition=observed
 case,options=load_case_options();out=O/'diagnosis_old_MATCHED_attempt2';out.mkdir(parents=True,exist_ok=False);env=SACExpertEnv(out,case,options,.02,'MATCHED',True);env.episode_dir=out;env.host_start=time.monotonic()
 try:
  env.summary=rt.run_executed_case(out,qualification_case=case,qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=env.capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},sac_hooks=env)
  record=f.metric_record(env,'old_nominal_diagnosis','MATCHED');record['classification']='diagnostic transparent wrapper, not changed control'
  (D/'SAC_HOLD_PROBE_R2.json').write_text(json.dumps(dict(record=record,transition_calls=records),indent=2)+'\n')
  f.compact_archive(env)
  print(json.dumps(dict(phase_durations=record['phase_durations'],last_calls=records[-7:],around_first_endpoint=[x for x in records if .495<=x['phase_elapsed_s']<=.525])),flush=True)
 finally:env.close();rt.reference_safe_task_transition=original
 
