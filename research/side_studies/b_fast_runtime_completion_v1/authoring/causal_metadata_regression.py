from pathlib import Path
import sys,json,types,copy,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import causal_metadata as m
pose=types.SimpleNamespace(rotation=np.eye(3),translation=np.array([.1,.2,.3]));source=1000;write=2000
row=dict(validation_model_version='population_prior_v1',model_version=None,source_capture_ns=source,apply_ns=write,applied=True,supervisor_mode='TRACK',validation_reference_q_rad=np.array([.1,.2]),validation_reference_dq_rad_s=np.zeros(2),command_torque_nm=np.arange(6,dtype=float))
owner=types.SimpleNamespace(runtime=dict(emitted_robot_reference_history=[dict(pose=pose,twist=np.zeros(6),apply_ns=write)]))
original=copy.deepcopy(row);m.enrich(owner,row)
assert row['source_capture_ns']==source and row['apply_ns']==write and row['actual_written_source_age_ns']==write-source
assert row['model_version']=='population_prior_v1' and row['runtime_model_sequence'] is None
assert np.array_equal(row['command_torque_nm'],original['command_torque_nm'])
version=row['reference_version'];changed=copy.deepcopy(original);pose.translation[0]+=1e-7;m.enrich(owner,changed);assert changed['reference_version']!=version
assert row['actual_robot_reference_translation'][0]==.1
brake=original|dict(supervisor_mode='BRAKE',selected_command_force_total_n=np.zeros(3),selected_command_moment_total_nm=np.zeros(3));m.enrich(owner,brake);assert brake['actual_reference_kind']=='SELECTED_EXECUTABLE_COMMAND' and 'actual_robot_reference_rotation' not in brake
out=dict(status='PASS',native_physics_steps=0,model_API_calls=0,actual_source_write_preserved=True,original_validation_model_authority=True,reference_pose_mutation_changes_version=True,arrays_copied=True,brake_not_mislabeled_as_track=True)
(S/'output/CAUSAL_METADATA_C1c_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
