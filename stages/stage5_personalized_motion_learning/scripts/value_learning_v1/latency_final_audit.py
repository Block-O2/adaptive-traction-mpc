"""Read-only scientific evidence audit. No simulation, controller or learner calls."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
SCRIPTS=STAGE/'scripts/value_learning_v1'
sys.path.insert(0,str(SCRIPTS))
from evidence_io import read_json, file_sha
from latency_report_section import unique_updates
from latency_tools import distribution
RAW=STAGE/'results/value_learning_research_v1'
D=STAGE/'docs/value_learning_research_v1'

def source(path):
    return {'path':str(path.relative_to(ROOT)), 'sha256_original_bytes':file_sha(path)}

def write(name,value):
    path=D/name
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main():
    pilot=read_json(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json')
    updates=read_json(D/'TRAINING_UPDATE_LATENCY.json')
    jobs,pending,failed=unique_updates(updates)
    sessions=[]
    all_processing=[]
    for session in pilot['sessions']:
        mode=session['mode']; rows=session['rows']; valid=[];invalid=[];initials=[];models=[]
        for row in rows:
            rep=row['repetition_index']
            run=RAW/'runs'/row['run_id']
            artifact=read_json(run/'rep_01/runtime_artifacts.json')
            result=read_json(run/'rollout_result.json')
            if row['status']=='VALID':valid.append(rep)
            else:invalid.append({'repetition':rep,'failure':row.get('failure_reason'),
                'planner_decision_count':len(artifact['task_decisions']),
                'trace_phase':[r['task_phase'] for r in artifact['trace']]})
            processing=row.get('scientific_harness_inter_rep_processing_wall_s')
            if processing is not None:all_processing.append(processing)
            wall=artifact['wall_physics']
            if row['status']=='VALID':
                initial=wall['initial_native_boundary_evaluation_only']
                initials.append({'repetition':rep,'time_s':initial['time_s'],
                    'qpos':initial['qpos_evaluation_only'],'qvel':initial['qvel_evaluation_only'],
                    'command_torque_nm':initial['command_torque_nm']})
            models.append({'repetition':rep,'rollout_result_model_fields':{
                k:v for k,v in result.items() if 'model' in k or 'immut' in k},
                'version_used':row.get('model_version_used'),
                'model_path_used':row.get('model_path_used')})
        first=initials[0]
        for initial in initials:
            initial['exact_same_fresh_native_initial_arrays_as_first']=all(
                np.array_equal(initial[k],first[k]) for k in ('qpos','qvel','command_torque_nm'))
        modejobs=[r for r in jobs if r.get('metadata',{}).get('mode')==mode]
        sessions.append({'mode':mode,'attempts':len(rows),'valid_repetitions':valid,
            'invalid_attempts':invalid,'continuous_valid_chain_demonstrated':False,
            'fresh_native_initial_boundary_comparisons':initials,'model_lifecycle':models,
            'unique_online_update_jobs':modejobs,
            'unique_online_update_wall_s':distribution(r['wall_s'] for r in modejobs),
            'prepared_and_promoted_are_same_job':True})
    lifecycle={'schema':'latency_final_pilot_update_audit_v1','publication_status':pilot['status'],
        'sources':[source(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json'),source(D/'TRAINING_UPDATE_LATENCY.json')],
        'unique_online_update_jobs':len(jobs),'unique_online_update_wall_s':distribution(r['wall_s'] for r in jobs),
        'scientific_harness_inter_rep_processing_wall_s':distribution(all_processing),
        'pending_event_count':len(pending),'failed_update_event_count':len(failed),
        'offline_initialization_excluded':True,'sessions':sessions,
        'limitations':['Model generation wall time excludes readiness wait, return extraction, checkpoint, archive and safe settling/bootstrap.',
            'No valid native continuation starts: each mode is four valid fresh development segments plus four invalid attempts, not eight continuous repetitions.',
            'Identical native initial arrays prove only the captured fresh-epoch boundary, not an entire matched counterfactual source trace.']}
    write('LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json',lifecycle)
    previous=read_json(RAW/'runs/pilot_scratch_v1_rep_01/rep_01/runtime_artifacts.json')
    current_path=RAW/'runs/pilot_scratch_v1_rep_02/rep_01/runtime_artifacts.json'
    current=read_json(current_path)
    boundary_path=RAW/'pilot_sessions/scratch_v1/boundary_before_02.json'
    boundary=read_json(boundary_path)
    config_path=STAGE/'configs/high_rom_v1/stage5_goal_task_120_v1.json'
    config=read_json(config_path)
    old=previous['trace'][-1];new=current['trace'][0]
    velocity_tolerance=np.radians(config['joint_velocity_completion_tolerance_deg_s'])
    angle_tolerance=np.radians(config['joint_angle_completion_tolerance_deg'])
    start=np.radians(config['start_return_target_deg'])
    def settled_details(state):
        state=np.asarray(state)
        return {'state_rad_rad_s':state.tolist(),'q_error_deg':np.degrees(state[:2]-start).tolist(),
            'dq_deg_s':np.degrees(state[2:]).tolist(),
            'angle_in_registered_tolerance':(abs(state[:2]-start)<=angle_tolerance).tolist(),
            'velocity_in_registered_tolerance':(abs(state[2:])<=velocity_tolerance).tolist()}
    src=STAGE/'src/traction_mpc_stage5'
    audit={'schema':'latency_boundary_continuity_read_only_audit_v1',
        'classification':'ORIGINAL_CROSS_EPOCH_BOOTSTRAP_SETTLING_INCOMPATIBILITY',
        'no_source_controller_safety_or_harness_edits':True,'no_new_scientific_rollout':True,
        'sources':[source(p) for p in (current_path,RAW/'runs/pilot_scratch_v1_rep_01/rep_01/runtime_artifacts.json',boundary_path,
            config_path,src/'task.py',src/'full3d_adaptive_integration_v1/runtime.py',src/'full3d_adaptive_integration_v1/session_state.py')],
        'registered_angle_tolerance_deg':config['joint_angle_completion_tolerance_deg'],
        'registered_velocity_tolerance_deg_s':config['joint_velocity_completion_tolerance_deg_s'],
        'previous_terminal':{'time_s':old['time_s'],'q_ref_rad':old['q_ref_rad'],
            'estimate':settled_details(old['estimated_state']),'truth_evaluation_only':settled_details(old['truth_state'])},
        'accepted_inter_rep_boundary':boundary,
        'fresh_epoch_origin_physics_s':current['wall_physics']['origin_physics_s'],
        'causal_sensor_estimates':current['wall_physics']['causal_sensor_estimates'],
        'bootstrap_execution_attempts':current['execution_attempts'],
        'failed_start':{'time_s':new['time_s'],'q_ref_rad':new['q_ref_rad'],
            'estimate':settled_details(new['estimated_state']),'truth_evaluation_only':settled_details(new['truth_state']),
            'phase':new['task_phase'],'task_elapsed_s':new['task_elapsed_s'],
            'planner_decision_count':len(current['task_decisions'])},
        'fresh_reference_shift_from_terminal_deg':np.degrees(np.asarray(new['q_ref_rad'])-old['q_ref_rad']).tolist(),
        'bootstrap_physics_duration_s':new['time_s']-boundary['end_time_s'],
        'observer_persistent_source_contract':{'path':str((src/'full3d_adaptive_integration_v1/session_state.py').relative_to(ROOT)),
            'field':'PERSISTENT_RUNTIME_FIELDS includes plant, measurement_layer and observer; runtime carryover reuses them'},
        'findings':['Settled gate and fresh start guard inspect different samples separated by two 5 ms physical intervals.',
            'Fresh bootstrap retains prior command for reseeding, then applies registered start TRACK reference before episode validation.',
            'Original position tolerance remains satisfied; fresh measured/estimated velocities violate original 2 deg/s settled criterion.',
            'Truth hip velocity also violates the original threshold: this is not solely an observer reset or estimation artifact.',
            'Observer and model version 1303 persist; zero task planner decisions precede rejection, so Q/lazy comparator does not trigger it.',
            'Reference jump and increased velocity support a bootstrap discontinuity hypothesis, but no isolating counterfactual was executed.'],
        'publication_limit':'Pilot demonstrates no continuous valid native repetition chain. Later valid fresh segments require exact matched source-initial-trace equivalence for conditional counterfactuals. Failed attempts never supply positive/low-cost returns.'}
    write('LATENCY_BOUNDARY_CONTINUITY_AUDIT.json',audit)
    print(json.dumps({'lifecycle':{k:lifecycle[k] for k in ('unique_online_update_jobs','unique_online_update_wall_s','scientific_harness_inter_rep_processing_wall_s')},
        'per_mode':[{k:s[k] for k in ('mode','valid_repetitions','unique_online_update_wall_s')} for s in sessions],
        'boundary_failure':audit['failed_start']},ensure_ascii=False))

if __name__=='__main__':main()
