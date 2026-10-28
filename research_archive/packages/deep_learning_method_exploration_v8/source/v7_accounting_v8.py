"""Retain recovered physical PASS separately from failed worker/ranking status."""
from pathlib import Path
import hashlib
import json
import runpy
import time

P = Path(__file__).resolve().parents[1]
f = P / 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json'
old = P / 'audit/RESOURCE_ACCOUNTING_PRE_FINAL_V7.json'
if not old.exists():
    old.write_bytes(f.read_bytes())
runpy.run_path(str(P / 'source/v7_accounting_v7.py'), run_name='__main__')
d = json.loads(f.read_text())
q = P / 'analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json'
classification = json.loads(q.read_text())
row = d['candidate_physical_and_worker_status_reconciliation']
row.pop('physical_complete_engineering_unknown_qualification_ids', None)
row.update(path=str(q.relative_to(P)), sha256=hashlib.sha256(q.read_bytes()).hexdigest(),
           counts=classification['candidate_classifications'],
           physical_complete_engineering_failure_ids=['DEVRC01_B', 'HOLDSS01_B'],
           unknown_original_motion_qualification_ids=['HOLDSS01_B'],
           recovered_original_physical_PASS_but_failed_worker_unranked_ids=['DEVRC01_B'])
d['completed_qualified_control_before_failed_job_exit'] = {
    'id': 'DEVRT02_B', 'original_complete_qualified_verdict_preserved': True,
    'later_job_engineering_failure_preserved': True, 'whole_job_success_claimed': False,
    'new_success_or_qualification_promotion': False,
    'original_scorer_replay': 'audit/scorer_replay/DEVRT02_B.json',
}
d['schema'] = 'ihear.resource_attempt_accounting.v8'
d['accounting_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
d['updated_unix'] = time.time()
t = f.with_suffix('.tmp')
t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
t.replace(f)
print('ACCOUNTING_V8', d['physical_START'], d['physical_END'], d['actual_new_native_steps'], 'qualification/ranking distinctions preserved')
