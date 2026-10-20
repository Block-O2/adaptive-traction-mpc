"""Authorized additive schema clarification, with byte-exact original backup."""
from pathlib import Path
import ast
import hashlib
import json
import numpy as np

P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
path=P/'LEARNING_DATA_SCHEMA.json'
original=path.read_bytes();data=json.loads(original)
backup='audit/LEARNING_DATA_SCHEMA_BEFORE_REFERENCE_CLARIFICATION.json'
for root in [P,R]:
    target=root/backup
    assert not target.exists(),'PRESERVE_BACKUP'
    target.write_bytes(original)
fields=data['STATE']['schema_fields']
fields['estimated_q_dq']['description']='Unnormalized ControllerTaskObservation.as_array(): hip q, knee q, hip dq, knee dq, in rad/rad/s. This differs from the normalized legacy 55D observation vector.'
fields['reference_q_dq']['description']='Planner request/handoff reference, ordered hip q, knee q, hip dq, knee dq. With prefetch this can be the planned future handoff endpoint in the physical clock, already causally available at the decision. It is not always the currently emitted reference and contains no future realized motion.'
fields['tracking_q_dq']['description']='Request-reference error: estimated_q_dq minus reference_q_dq. Do not interpret as always the sample-aligned tracking error to the emitted reference. It is not truth tracking.'
data['STATE']['sample_aligned_causal_tracking']={
    'source':'source/results/{run_id}/trace.npz',
    'formula':'estimated_human_state_rad_rad_s - concatenate(reference_q_rad, reference_dq_rad_s) at the same time_s',
    'request_snapshot_authority':'runtime_artifacts.json.gz::causal_tracking_request_snapshots records source state, receipt-owned emitted q_ref/dq_ref, and proposed_schedule_origin separately',
    'derived_audit':'derived/{run_id}_CAUSAL_SCHEMA_VERIFICATION.json::derived_rows',
    'time_join':'Exact physical_s/time_s match within 1e-8 s; audit preserves mismatch rather than fabricating a sample',
    'truth_used':False}
source=P/'source/stages/stage5_personalized_motion_learning/scripts/single_human_sac_expert_v1/sac_env.py'
tree=ast.parse(source.read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='feature_spec')
namespace=dict(np=np,ROM=np.radians(125.),VELOCITY=np.radians([45.,75.]),ACCELERATION=np.radians([300.,600.]))
exec(compile(ast.Module(body=[function],type_ignores=[]),'<offline fixed feature specification only>','exec'),namespace)
features=namespace['feature_spec']()
changes={45:'native_B_nominal_target_hip',46:'native_B_nominal_target_knee',49:'previous_residual_knot_1',50:'previous_residual_knot_2',51:'current_reference_common_progress',52:'native_B_nominal_target_common_progress',53:'unused_zero'}
for i,name in changes.items():features[i]['name']=name
data['STATE']['legacy_normalized55D']={
    'paths':['output/{run_id}_DECISIONS.json::rows[*].observation','source/results/{run_id}/RESIDUAL_DECISIONS.npz::observations'],
    'writer':'deps/coordination_adapter.py::context and code/interfaces.py::terminal_value_context',
    'normalization':'normalized = (raw / fixed_scale).astype(float32); no centering, clipping, or evaluation-derived statistics',
    'inverse':'raw_approx = normalized.astype(float64) * fixed_scale; float32 rounding prevents byte-exact reconstruction of original physical values',
    'preferred_physical_source':'causal_rows or exact causal trace/request payload; inverse-normalized values are approximate',
    'features':features,
    'K3_history_note':'code/interfaces.py explicitly stores richer_previous_residual in context; legacy two history coordinates remain the inherited 55D slots. Do not infer all K3 knots from those two coordinates.',
    'reference_semantics':'Reference slots4:8 use the same request/handoff reference rule above.'}
data['EXECUTION']['fallback_authority']={
    'path':'runtime_artifacts.json.gz::safe_fallback_events',
    'rule':'Count by event type. ESCAPE_ADMITTED records a certified contingency/admission and does not establish executed escape. Join command_receipts.mode and actual native steps to classify actual actuation.',
    'compact_evaluation_caveat':'cross_analysis.py fallbacks reads summary.get(fallback_events,[]), but summary lacks that field in observed completed runs. That compact empty list is not authoritative.'}
data['EXECUTION']['observed_receipt_field_caveat']='The receipt_fields list is a logical desired contract, not proof every listed key is populated. Current observed receipts omit reference_version, plan_request_id and command_kind; use source/validation/reference fields and original lineage artifacts, preserving missing fields explicitly.'
data['schema_audit_authority']={
    'original_backup':backup,'original_sha256':hashlib.sha256(original).hexdigest(),
    'scope':'Documentation-only clarification; raw records, controller, frozen execution manifest, physical data and thresholds unchanged',
    'per_run_schema':'derived/{run_id}_CAUSAL_SCHEMA_VERIFICATION.json',
    'per_run_execution':'audit/{run_id}_LEARNING_EXECUTION_EVIDENCE.json',
    'combined_at_campaign_end':'audit/LEARNING_EXECUTION_FIELD_AUDIT.json',
    'observation_definition':'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/task_observation.py::ControllerTaskObservation.as_array',
    'request_definition':'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py:3238-3256'}
updated=(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
for root in [P,R]:(root/'LEARNING_DATA_SCHEMA.json').write_bytes(updated)
receipt=dict(status='PASS',old_sha256=hashlib.sha256(original).hexdigest(),new_sha256=hashlib.sha256(updated).hexdigest(),backup=backup,raw_execution_modified=False,new_physics_starts=0)
for root in [P,R]:(root/'audit/LEARNING_SCHEMA_CLARIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
