"""Build explicit preseal index and static content manifest; no science runs."""
from pathlib import Path
import ast
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
INDEX = P / 'audit/FINAL_EVIDENCE_INDEX_V2.json'
MANIFEST = P / 'audit/STATIC_PACKAGE_MANIFEST_PRESEAL_V2.json'
assert not INDEX.exists() and not MANIFEST.exists()


def sha(f):
    h = hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def read(relative):
    return json.loads((P / relative).read_text())


def pointer(data, key):
    for k in key.strip('/').split('/') if key.strip('/') else []:
        data = data[int(k)] if isinstance(data, list) else data[k.replace('~1', '/').replace('~0', '~')]
    return data


def ref(relative, requirements):
    data = read(relative)
    assert requirements and all(pointer(data, k) == v for k, v in requirements.items()), 'REFERENCE_ASSERTION:' + relative
    return {'path': relative, 'sha256': sha(P / relative), 'require': requirements}


def put(path, data):
    with path.open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


limits_file = 'audit/FINAL_METADATA_LIMITATIONS_V2.json'
assert (P / limits_file).exists(), 'EXPLICIT_METADATA_LIMITATIONS_REQUIRED'
refs = {
    'historical_content': ref('audit/HISTORY_CONTENT_HASH_FINAL.json', {
        '/status': 'PASS', '/errors': [], '/checked_files': 204641, '/expected_files': 204641, '/bytes_hashed': 93289584051}),
    'protected_inputs': ref('audit/HISTORY_PROTECTION_FINAL.json', {
        '/status': 'PASS', '/checked_files': 204641, '/metadata_changes': [], '/added_historical_files': [], '/critical_hash_mismatches': [], '/late_at_start': []}),
    'journal_prefix': ref('audit/JOURNAL_PREFIX_FINAL.json', {
        '/status': 'PASS', '/original_prefix_preserved': True, '/before_bytes_preserved': True, '/only_append_no_history_overwrite': True}),
    'attempt_accounting': ref('RESOURCE_AND_ATTEMPT_ACCOUNTING.json', {
        '/schema': 'ihear.resource_attempt_accounting.v8', '/physical_START': 170, '/physical_END': 170,
        '/actual_new_native_steps': 12997720, '/active_attempt_ids': [], '/duplicate_START_ids': [], '/duplicate_END_ids': [], '/actual_attempts_saved': 0}),
    'owned_final': ref('audit/OWNED_FINAL_V1.json', {
        '/status': 'PASS_RECORDED_SCOPE_WITH_DOCUMENTED_METADATA_LIMITATIONS', '/known_live_or_zombie': 0,
        '/known_live_descendants': 0, '/checker_exit_proven_by_external_PID_ticks_recheck': True, '/perfect_PID_metadata_compliance_claim': False}),
}
known_limits = []
for ident, category, field, expected, message in [
    ('FOREGROUND_METADATA_PID_GAPS', 'FOREGROUND_STATIC_TOOL_EXIT_ONLY', '/foreground_static_tool_only_gap_present', True,
     'Several foreground static/metadata commands have tool exit receipts without fully persisted PID/start_ticks. No identity reconstructed.'),
    ('ORIGINAL_REVIEW_END_GAPS', 'ORIGINAL_REVIEW_END_OR_MANIFEST_LIMITED', '/original_missing_END_reviews', ['history', 'local_surrogate'],
     'Current main closure receipts and normalized manifests preserve original missing/nonstandard records; no historical END fabricated.'),
    ('ZERO_START_PREIMPORT_IDENTITY', 'ZERO_START_PREIMPORT_SOURCE_IDENTITY_LIMITED', '/zero_START_preimport_manifest_missing', ['DEVPC01', 'HOLDSS01'],
     'Actual zero-START preimport logs/owners/frozen inputs checked; complete loaded-module/interpreter identity not proved.'),
    ('METADATA_REPAIR_BUDGET_OVERRUN', 'BOUNDED_REVIEW_METADATA_SEAL_OVERRUN', '/metadata_seal_budget_compliance_complete', False,
     'One 600s pure repair branch used624.612s including metadata sealing; no extra fit/env/physics, not perfect budget compliance.'),
    ('FAILED_WORKER_JOIN_RECEIPT_LIMITED', 'FAILED_WORKER_NORMAL_JOIN_RECEIPT_MISSING', '/failed_worker_normal_join_receipt_missing_groups', ['DEVRC01', 'DEVRT01', 'DEVRT02', 'HOLDSS02'],
     'Four preserved FAILED_PRESERVED WORKER_DONE receipts lack the normal aggregate join flag. Exact original attempt joins, supervisor STOP/exit1/no survivors and current recorded PID closure are checked separately; no normal receipt reconstructed.'),
    ('CPU_AND_GENERALIZATION_LIMITS', 'TOTAL_COMPUTE_AND_GENERALIZATION_NOT_ESTABLISHED', '/total_host_core_seconds_known', False,
     'Total host core-seconds unknown; model fit times exclude label collection. No patient/hardware or total compute-efficiency claim.'),
]:
    item = ref(limits_file, {field: expected, '/perfect_metadata_PASS_allowed': False})
    item.update(id=ident, category=category, message=message)
    known_limits.append(item)

accounting = read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json')
events = [json.loads(line) for line in (P / 'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
started_groups = {e['group'] for e in events if e['event'] == 'START'}
groups = {}
for row in accounting['physical_supervisor_jobs']:
    g = row['group']
    if row['worker_exit_code']:
        groups[g] = {'physical_START': row['physical_START'], 'worker_exit_code': row['worker_exit_code'],
                     'reason': row['reason'], 'supervisor_END_sha256': sha(P / 'owned' / (g + '_SUPERVISOR_END.json')),
                     'original_failure_not_deleted': True}
eng_path = P / 'audit/ENGINEERING_JOB_CLOSEOUT_INDEX_V2.json'
put(eng_path, {'status': 'ORIGINAL_ENGINEERING_FAILURES_PRESERVED', 'created_unix': time.time(),
               'groups': groups, 'original_records_not_modified': True,
               'DEVRT02_completed_B_verdict_preserved': True, 'DEVRC01_recovered_physical_PASS_still_unranked': True})
engineering = {}
for relative in ['agent_reviews/final_verifier_zero_start_v3/HOLDSS01_INDEX_FRAGMENT_CANDIDATE.json',
                 'agent_reviews/final_verifier_devpc01_v4/DEVPC01_INDEX_FRAGMENT_CANDIDATE.json']:
    engineering.update(read(relative)['engineering_failures'])
for g in ['DEVRT01', 'DEVRT02', 'DEVRC01', 'HOLDSS02']:
    engineering[g] = {'zero_START': False, 'evidence': ref(str(eng_path.relative_to(P)), {
        '/status': 'ORIGINAL_ENGINEERING_FAILURES_PRESERVED', '/groups/' + g + '/worker_exit_code': 1,
        '/groups/' + g + '/original_failure_not_deleted': True})}
for g in ['DEVRT01', 'DEVRT02', 'DEVRC01', 'HOLDSS02']:
    worker_path = 'jobs/' + g + '/WORKER_DONE.json'
    worker = read(worker_path)
    assert 'all_children_joined' not in worker and worker.get('status') == 'FAILED_PRESERVED'
    engineering[g].update(
        failed_join_receipt_schema='ihear.failed_worker_join_receipt.v1',
        normal_worker_join_receipt_missing_acknowledged=True,
        failed_join_receipt_evidence=ref(worker_path, {'/status': 'FAILED_PRESERVED', '/error': worker['error']}),
    )
engineering['DEVRT02'].update(
    preserve_completed_control_ids=['DEVRT02_B'],
    completed_control_result=ref('attempts/DEVRT02_B_RESULT.json', {'/id': 'DEVRT02_B', '/complete': True, '/qualified': True}),
    completed_control_replay=ref('audit/scorer_replay/DEVRT02_B.json', {
        '/status': 'SCORER_REPLAY_PASS', '/qualified_replay': True, '/original_result_exact_reproduced': True}),
)
raw_aliases = {'HOLDSS01_B': {
    'raw_id': 'HOLDSS01_B', 'unranked': True,
    'sha256': {name: sha(P / 'runtime/source/results/HOLDSS01_B' / name) for name in ['trace.npz', 'summary.json', 'runtime_artifacts.json.gz']},
    'evidence': ref('audit/HOLDSS02_ENGINEERING_RAW_PRESERVATION.json', {
        '/status': 'CLOSED_ENGINEERING_FAILURE_RAW_PRESERVED', '/actual_group': 'HOLDSS02', '/rows/0/id': 'HOLDSS01_B'}),
}}

review_index = read('audit/FINAL_REVIEW_INDEX_V2.json')['agent_reviews']
artifacts = {}
for folder in ['models', 'data']:
    for f in (P / folder).rglob('*') if (P / folder).exists() else []:
        if f.is_file():
            artifacts[str(f.relative_to(P))] = sha(f)
for f in (P / 'agent_reviews').rglob('*'):
    if f.is_file() and f.suffix in ['.pt', '.pth', '.pkl', '.ckpt']:
        artifacts[str(f.relative_to(P))] = sha(f)

verifier_source = (P / 'source/v7_verify_final_package_v7.py').read_text()
node = next(n for n in ast.parse(verifier_source).body if isinstance(n, ast.FunctionDef) and n.name == 'identities')
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<original-identities>', 'exec'), namespace)
identities = namespace['identities']
pairs = read('audit/FINAL_OWNED_PAIR_BASE_V2.json')['owned_end_pairs']
for sf in (P / 'owned').glob('*_START.json'):
    ef = sf.with_name(sf.name[:-len('_START.json')] + '_END.json')
    if ef.exists():
        sa, ea = json.loads(sf.read_text()), json.loads(ef.read_text())
        if {(q['pid'], q['start_ticks']) for q in identities(sa)} & {(q['pid'], q['start_ticks']) for q in identities(ea)}:
            pairs.append({'start': str(sf.relative_to(P)), 'end': str(ef.relative_to(P))})
pairs = list({(r['start'], r['end']): r for r in pairs}.values())

excluded = {'END.json', 'PACKAGE_VERIFICATION.json', str(INDEX.relative_to(P)), str(MANIFEST.relative_to(P)),
            'audit/FINAL_INDEX_BUILD_SUMMARY_V2.json'}
files, symlinks, total = {}, {}, 0
for f in sorted(P.rglob('*')):
    rel = str(f.relative_to(P))
    if rel in excluded or rel.startswith('audit/final_verification_v7_preseal_v2/'):
        continue
    if f.is_symlink():
        symlinks[rel] = os.readlink(f)
    elif f.is_file():
        before = f.stat()
        files[rel] = sha(f)
        after = f.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'INPUT_CHANGED_DURING_STATIC_HASH:' + rel
        total += before.st_size
manifest = {'schema': 'ihear.preseal_static_inventory.v1', 'status': 'PASS_HASHED_STATIC_SNAPSHOT',
            'created_unix': time.time(), 'files': files, 'symlinks': symlinks, 'bytes_hashed': total,
            'metadata_limits_present': True, 'contains_scientific_raw': True,
            'exclusions': sorted(excluded),
            'scope': 'Existing static files at freeze; manifest/index themselves and future root seals/verifier/self metadata outputs are separately bound. No universal self-hash claim.'}
put(MANIFEST, manifest)
index = {'final_references': refs,
         'freeze_refs': [ref('freeze/DEVRT03.json', {
             '/group': 'DEVRT03', '/quality_contract/hip_knee_jerk_RMS_ratio_max_vs_V6PHASE': 1.001,
             '/quality_contract/force_norm_rate_RMS_ratio_max_vs_V6PHASE': 1.004}),
                        ref('freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json', {
                            '/status': 'NOT_MET', '/labels/CFACTORH01': 0, '/labels/CFACTORL01': 0, '/threshold_refits': 0})],
         'known_limitations': known_limits, 'artifact_sha256': artifacts, 'owned_end_pairs': pairs,
         'agent_reviews': review_index,
         'config_paths': {j['group']: 'experiments/' + j['group'] + '.json' for j in accounting['physical_supervisor_jobs']},
         'engineering_failures': engineering, 'raw_aliases': raw_aliases,
         'package_manifests': [ref(str(MANIFEST.relative_to(P)), {'/status': 'PASS_HASHED_STATIC_SNAPSHOT', '/metadata_limits_present': True})]}
put(INDEX, index)
put(P / 'audit/FINAL_INDEX_BUILD_SUMMARY_V2.json', {
    'status': 'PRESEAL_INDEX_FROZEN_NOT_VERIFICATION_RESULT', 'created_unix': time.time(),
    'index_path': str(INDEX.relative_to(P)), 'index_sha256': sha(INDEX),
    'manifest_path': str(MANIFEST.relative_to(P)), 'manifest_sha256': sha(MANIFEST),
    'static_files': len(files), 'bytes_hashed': total, 'artifact_files': len(artifacts),
    'review_records': len(review_index), 'explicit_owned_pairs_not_task_count': len(pairs),
    'source_sha256': sha(Path(__file__)), 'new_env_model_fit_physics': 0})
print('FINAL_INDEX_FROZEN', len(files), 'files', len(artifacts), 'model/data artifacts', len(review_index), 'reviews')
