"""Documentation-only final telemetry clarification, using verified offline evidence."""
from pathlib import Path
import json,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
audit=json.loads((P/'audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json').read_text())
assert audit['status']=='PASS' and audit['runs']==36 and audit['all_optional_missing_task_rows_are_terminal_only']
p=P/'LEARNING_DATA_SCHEMA.json';old=p.read_bytes();d=json.loads(old)
assert (R/'LEARNING_DATA_SCHEMA.json').read_bytes()==old
d['original_trace']['robot_telemetry_availability']={
 'authority':'audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json',
 'scope':'All 36 retained runs: 34 complete TASK trajectories and two ABORTED observed TASK prefixes (P06_H150, P10_H150). This does not qualify the unexecuted remainder.',
 'actual_command':'cr12_actuator_command_nm and applied_generalized_action_nm are finite on every retained TASK row. Every positive TASK trace interval joins exactly to an applied receipt; actual actuator torque matches its command_torque_nm exactly.',
 'optional_decomposition':'robot_torque_component_{base,position,velocity,allocator,clipping}_nm and allocated_wrench_world are finite on every positive-duration TASK interval. Each has exactly one nonfinite TASK row: the final terminal_boundary_node with no following interval and zero duration. The missing boundary values remain unknown, not zero.',
 'writer_semantics':'The runtime adds realized component/wrench values to the left trace node after executing its interval; the final no-following-interval node has no such realized interval. Archive writer preserves unavailable optional fields as NaN.',
 'whole_session_limit':'Some commissioning/session rows also lack optional decomposition. The TASK interval audit does not establish complete whole-session telemetry.',
 'frozen_summary_nulls':'Original whole-array max/RMS propagate final-boundary NaN and are serialized as JSON null. Preserve those frozen values; the additive receipt-bound interval statistics have a separately named scope and do not overwrite them.',
 'additive_reduction':'Per component, max=max(abs(x_i)); duration-weighted RMS=sqrt(sum(x_i**2 * dt_i)/sum(dt_i)), with dt_i=time_s[i+1]-time_s[i]. Include every positive-duration TASK interval after exact receipt joining; the final boundary has zero weight. Any nonfinite positive interval invalidates both reductions (null), rather than being silently omitted.',
 'available_receipt_payloads':'command_torque_nm, selected_command_force_total_n and selected_command_moment_total_nm are finite in every retained receipt. These are actual command payloads; they do not reconstruct unavailable boundary decomposition.',
 'not_online_truth_permission':'Availability of evaluation trace telemetry does not add these fields to the online feature allowlist.'}
d['OUTCOME']['torque_allocator_reductions']='Frozen whole-array optional component/wrench summary nulls remain unchanged. Additive, fully covered TASK applied-interval max/RMS are in audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json with explicit duration weighting; ABORTED arms describe observed prefixes only.'
d['EXECUTION']['fallback_authority']['observed_example']='P06_H150 and P10_H150 each have FALLBACK_COMMITTED/STOPPED/HOLD once, although every command receipt is TRACK. Preserve both facts; TRACK cannot exclude executed fallback.'
d['schema_audit_authority']['telemetry_availability']='audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json; finite counts, missing indices/times, exact receipt joins, source hashes and positive-interval reductions'
new=(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
for root in [P,R]:
 backup=root/'audit/LEARNING_DATA_SCHEMA_BEFORE_INTERVAL_TELEMETRY_CLARIFICATION.json'
 assert not backup.exists();backup.write_bytes(old)
 (root/'LEARNING_DATA_SCHEMA.json').write_bytes(new)
receipt=dict(status='PASS',old_sha256=hashlib.sha256(old).hexdigest(),new_sha256=hashlib.sha256(new).hexdigest(),
 authority='audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json',raw_execution_modified=False,new_physics_starts=0)
for root in [P,R]:(root/'audit/LEARNING_INTERVAL_TELEMETRY_SCHEMA_CLARIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
