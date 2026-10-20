"""Authorized documentation of observed fallback and incomplete-run semantics."""
from pathlib import Path
import json,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
p=P/'LEARNING_DATA_SCHEMA.json';old=p.read_bytes();d=json.loads(old)
d['EXECUTION']['fallback_authority']['rule']='Count raw safe_fallback_events by event type. ESCAPE_ADMITTED is contingency certification/admission only. FALLBACK_COMMITTED, FALLBACK_STOPPED and FALLBACK_HOLD are explicit execution-state events; join their physical time/reference with applied positive-native-step receipts to inspect realized fallback. TRACK denotes the low-level tracking mode and can track an escape/stop/hold reference; TRACK alone cannot exclude executed fallback.'
d['EXECUTION']['fallback_authority']['observed_example']='P06_H150 has FALLBACK_COMMITTED/STOPPED/HOLD once each, although every command receipt is TRACK. Preserve both facts; do not infer no fallback from receipt mode.'
d['EXECUTION']['fallback_authority']['applied_mode_counts_authority']='audit/{run_id}_RECEIPT_MODE_EVIDENCE.json separates applied/unapplied/positive-step modes and raw fallback event types. Retained native counts include shared prefix and are not new simulated work counts.'
d['EXECUTION']['partial_native_ownership']={
 'authority':'audit/{run_id}_PARTIAL_NATIVE_OWNERSHIP.json',
 'meaning':'PARTIAL_RAW_OWNERSHIP_PASS independently verifies retained native command identity, torque, contiguous receipt intervals and step counts on the observed prefix only.',
 'restriction':'This pass does not imply task completion, full safety or scientific qualification, full force integral, motion acceptance or gain. Original failed-request/scientific status remains unchanged.',
 'failed_requests':'A rejected request can have null activation and trigger missing_version_vector/request_not_activated while already executed commands retain valid ownership. Preserve the request rejection separately; do not automatically call it corruption of actual command execution.'}
d['STATE']['partial_coverage_detection']='Determine task coverage from summary.status, phase transitions and explicit complete_task. A normal-named {run_id}_STATE_ACTION.json can contain an ABORTED observed prefix; the presence or absence of PARTIAL in the filename does not establish completeness.'
d['OUTCOME']['partial_safety_scope']='If complete_task is false, any preserved safety PASS describes the observed prefix only and cannot qualify an unexecuted remainder. Full J_F and full gain remain null.'
d['schema_audit_authority']['partial_native']='audit/{run_id}_PARTIAL_NATIVE_OWNERSHIP.json'
d['schema_audit_authority']['partial_evidence_preservation']='audit/{patient_id}_FAILURE_PRESERVATION_AUDIT.json; evidence bookkeeping pass is not scientific promotion'
new=(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
for root in [P,R]:
    backup=root/'audit/LEARNING_DATA_SCHEMA_BEFORE_PARTIAL_FALLBACK_CLARIFICATION.json'
    assert not backup.exists();backup.write_bytes(old)
    (root/'LEARNING_DATA_SCHEMA.json').write_bytes(new)
receipt=dict(status='PASS',old_sha256=hashlib.sha256(old).hexdigest(),new_sha256=hashlib.sha256(new).hexdigest(),
             authority='P06_H150 preserved runtime fallback/receipt and partial native audit',raw_execution_modified=False)
for root in [P,R]:(root/'audit/LEARNING_PARTIAL_SCHEMA_CLARIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
