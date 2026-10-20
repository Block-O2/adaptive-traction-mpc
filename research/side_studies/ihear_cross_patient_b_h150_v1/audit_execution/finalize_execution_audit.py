"""Final offline document sync and closeout evidence; no simulation imports."""
from pathlib import Path
import json,hashlib,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names=['independent_batch.py','audit_learning_evidence.py']
owned=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 # Ignore shell command text and check actual python argv only.
 if cmd.split(' ',1)[0].endswith('python') and any(n in cmd for n in names):owned.append(dict(pid=int(proc.name),command=cmd))
assert not owned,owned
assert read(P/'SERIAL_CAMPAIGN_DONE.json')['owned_children_joined']
audit=read(P/'audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json')
assert audit['status']=='PASS' and len(audit['rows'])==36
learning=read(P/'audit/LEARNING_EXECUTION_FIELD_AUDIT.json')
assert len(learning['rows'])==36
patients=read(P/'VIRTUAL_PATIENT_COHORT.json')['order']
statuses={pid:read(P/'audit'/('INDEPENDENT_COMPLETE_'+pid+'.json'))['status'] for pid in patients}
preservation={pid:read(P/'audit'/(pid+'_FAILURE_PRESERVATION_AUDIT.json'))['status'] for pid in patients}
assert all(s=='EVIDENCE_PRESERVATION_PASS' for s in preservation.values())
for name in ['LEARNING_DATA_SCHEMA.json','audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json','audit/LEARNING_EXECUTION_FIELD_AUDIT.json']:
 assert sha(P/name)==sha(R/name),name
memo=(R/'audit_execution/LEARNING_EXECUTION_AUDIT.md').read_bytes()
(P/'audit/LEARNING_EXECUTION_AUDIT.md').write_bytes(memo)
(R/'audit/LEARNING_EXECUTION_AUDIT.md').write_bytes(memo)
record=dict(status='PASS',timestamp_unix=time.time(),new_physics_starts=0,raw_or_frozen_files_modified=False,
 owned_watchers_live=owned,
 joined_tool_sessions=[dict(session_id=43631,linux_pid=689,role='independent arithmetic watcher',exit_code=0),
  dict(session_id=43907,linux_pid=3371,role='final Learning watcher',exit_code=0),
  dict(session_id=93591,role='36-run interval telemetry sweep',exit_code=0)],
 earlier_watcher_reload=dict(session_id=15403,linux_pid=1275,exit_code=1,reason='Intentional SIGTERM and join before replacement watcher; offline inventory extension for partial arms, no physics'),
 independent_patient_statuses=statuses,failure_preservation_statuses=preservation,
 complete_raw_runs=34,preserved_partial_raw_runs=['P06_H150','P10_H150'],
 learning_evidence_runs=len(learning['rows']),telemetry_evidence_runs=len(audit['rows']),
 no_partial_promotion=True,
 artifact_hashes={n:sha(P/n) for n in ['LEARNING_DATA_SCHEMA.json','audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json','audit/LEARNING_EXECUTION_FIELD_AUDIT.json','audit/LEARNING_EXECUTION_AUDIT.md']},
 scope='This subagent owned helper lifecycle only; global process and physical accounting authority remain root closeout audit.')
for root in [P,R]:
 dest=root/'audit/OFFLINE_EXECUTION_AUDIT_CLOSED.json';assert not dest.exists();dest.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
