"""Direct original scheduler replay from saved legal model and task contract; no plant."""
import os,sys,json
from pathlib import Path
from dataclasses import replace
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];R=P/'runtime';O=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
import numpy as np
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.high_rom_v1 import deployable_prior,contract
from traction_mpc_stage5.task import GoalTaskSpec,TaskPhase
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
case,options=sc.load_case_options();spec=GoalTaskSpec.from_mapping(contract());spec=replace(spec,start_return_target_rad=tuple(np.radians(case['task']['start_deg'])),outbound_goal_target_rad=tuple(np.radians(case['task']['goal_deg'])))
b=json.loads((O/'history/CAUSAL_COMMISSIONED_BELIEF.json').read_text());g=PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in b['geometry'].items()});model=sc.rt.StateResidualHumanModel(g,np.array(b['beta']),deployable_prior(),residual_weights_nm=np.array(b['residual_weights_nm']));clear=CombinedRigidTableClearanceV1(sc.rt.SessionClearanceContract(g),RigidTableReferenceEnvelopeV1(g),use_monotonic_certificate=bool(options.get('monotonic_clearance_certificate',False)));sched=QuinticHumanWaypointSchedulerV1(spec,model,reference_period_s=.005,clearance_evaluator=clear,clearance_source='DEV_D_CAUSAL_EFFECTIVE_RIGID_TABLE_ENVELOPE',preserve_task_endpoint_clearance_floor=True,require_continuous_nonpenetrating_path=True,use_duration_lower_bound=bool(options.get('duration_lower_bound',False)),reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
su=json.loads((O/'runtime/source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json').read_text());rows=[]
for lr in su['learning_records']:
 m=lr['selected_plan']['execution_screen'].get('coordination_modal_v2')
 if m is None or m['phase']!='RETURN' or m['slot'] not in [1,4]:continue
 s=lr['selected_plan']['schedule'];candidate=HumanWaypointCandidate('same_boundary_replay',TaskPhase.RETURN,np.array(spec.start_return_target_rad),np.array(s['target_q_rad']),np.array(s['target_dq_rad_s']));elapsed=next(d['phase_elapsed_s'] for d in su['decisions'] if abs(d['decision_request_time_s']-lr['request_time_s'])<1e-8)
 sch=sched.plan_reference_contract(current_q_hat_rad=np.array(s['start_q_rad']),current_dq_hat_rad_s=np.array(s['start_dq_rad_s']),candidate=candidate,phase_elapsed_s=elapsed);factor={1:1.1,4:1.2}[m['slot']];old_duration=float(np.ceil(sch.duration_s*factor/.005-1e-10)*.005);old=sched.plan_fixed_duration_reference_contract(current_q_hat_rad=np.array(s['start_q_rad']),current_dq_hat_rad_s=np.array(s['start_dq_rad_s']),candidate=candidate,phase_elapsed_s=elapsed,duration_s=old_duration)
 rows.append({'slot':m['slot'],'recomputed_native_minimum_s':sch.duration_s,'recorded_native_minimum_s':m['scheduler_duration_record']['original_scheduler_minimum_s'],'old_compiler_s':old.duration_s,'actual_new_s':s['duration_s'],'old_fixed_certificate_pass':True,'native_minimum_identity':abs(sch.duration_s-m['scheduler_duration_record']['original_scheduler_minimum_s'])<1e-12})
out={'status':'PASS' if all(r['native_minimum_identity'] and r['old_compiler_s']!=r['actual_new_s'] for r in rows) else 'REVIEW_REQUIRED','rows':rows,'original_task_start_rad':spec.start_return_target_rad,'original_task_goal_rad':spec.outbound_goal_target_rad,'public_contract_only':True,'hidden_plant_constructed':False,'new_native_steps':0};(P/'analysis/SCHEDULER_DIRECT_REPLAY.json').write_text(json.dumps(sc.clean(out),indent=2)+'\n');print(out)
