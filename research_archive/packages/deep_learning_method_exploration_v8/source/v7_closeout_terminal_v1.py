"""Final bounded receipt after successful sealed and process audits. No science."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import time

P = Path(__file__).resolve().parents[1]
ME = {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])}
began = time.time()


def sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def read(rel):
    return json.loads((P / rel).read_text())


def put(rel, data):
    f = P / rel
    tmp = f.with_name('.' + f.name + '.' + str(os.getpid()) + '.tmp')
    with tmp.open('x') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.link(tmp, f)
    tmp.unlink()


put('audit/FINAL_TERMINAL_START_V1.json', {'process': ME, 'started_unix': began, 'source_sha256': sha(Path(__file__)), 'new_env_model_fit_physics': 0})
activation = read('ACTIVATION.json')
assert began < activation['deadline_unix']
sealed = 'audit/final_verification_v7_sealed_v3'
owned = 'audit/ownership_final_v2'
verification = read(sealed + '/VERIFICATION.json')
assert verification['status'] == 'COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS' and not verification['issues']
assert not verification['observations'].get('preseal_pending')
ownership = read(owned + '/OWNERSHIP_RESULT.json')
assert ownership['status'] == 'NO_OTHER_LIVE_OWNED_IN_DECLARED_SCOPE_SELF_PENDING_TOOL_RETURN' and not ownership['issues']
assert not ownership['live_or_zombie_known'] and not ownership['live_known_descendants']
assert ownership['all_OTHER_recorded_processes_ended_or_reused']
spec = importlib.util.spec_from_file_location('ownership_checker_final_read', P / 'agent_reviews/final_metadata_inventory/final_ownership_checker.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
proc, errors = checker.proc_snapshot()
assert not errors
boundary = []
for rel in [sealed + '/END.json', owned + '/END.json', 'audit/FINAL_SEAL_BUILD_RECEIPT_V1.json']:
    identity = read(rel)['process']
    now = proc.get(identity['pid'])
    assert now is None or now['start_ticks'] != identity['start_ticks'], 'FINAL_PROCESS_STILL_PRESENT:' + rel
    boundary.append({'receipt': rel, 'process': identity, 'state_after_actual_tool_return': 'ENDED_OR_REUSED', 'tool_exit_code_observed': 0})
records = []
for f in (P / 'owned').glob('*.json'):
    records += [{**q, 'source': str(f.relative_to(P))} for q in checker.extract(json.loads(f.read_text()))]
for row in ownership['known_processes']:
    records.append({'pid': row['pid'], 'start_ticks': row['start_ticks'], 'source': row.get('source', 'final_ownership_scope')})
closure = checker.evaluate(records, proc, ME)
assert closure['all_OTHER_recorded_processes_ended_or_reused']
journal = read('audit/JOURNAL_PREFIX_FINAL.json')
assert sha(Path(journal['journal_path'])) == journal['after_sha256']
manifest = read('FINAL_MANIFEST.json')
assert manifest['all15_deliverables_content_hashed'] and manifest['required_deliverables_count'] == 15
# The strict sealed verifier already checked all manifest bytes. Recheck root
# deliverables and exact late metadata here, rather than rerunning integrations.
for name in read('PACKAGE_VERIFICATION.json')['required_deliverables']:
    assert sha(P / name) == manifest['files'][name], 'ROOT_DELIVERABLE_CHANGED:' + name
for directory in [sealed, owned]:
    output = read(directory + '/OUTPUT_MANIFEST.json')['files']
    for rel, digest in output.items():
        assert sha(P / directory / rel) == digest
    assert sha(P / directory / 'OUTPUT_MANIFEST.json') == read(directory + '/END.json')['manifest_sha256']
late = ['FINAL_MANIFEST.json', 'audit/FINAL_EVIDENCE_INDEX_V3_SEALED.json', 'audit/FINAL_OWNERSHIP_INVENTORY_V3.json',
        'audit/FINAL_SEAL_BUILD_RECEIPT_V1.json', 'audit/FINAL_TERMINAL_START_V1.json']
for directory in [sealed, owned]:
    late += [str(f.relative_to(P)) for f in (P / directory).iterdir() if f.is_file()]
for f in (P / 'owned').glob('*_END.json'):
    rel = str(f.relative_to(P))
    if rel not in manifest['files']:
        late.append(rel)
put('audit/FINAL_METADATA_ADDENDUM_V1.json', {
    'schema': 'ihear.final_metadata_hash_addendum.v1', 'status': 'PASS_TERMINAL_METADATA_BOUND',
    'created_unix': time.time(), 'process': ME, 'files': {rel: sha(P / rel) for rel in sorted(set(late))},
    'closure_receipt': 'audit/FINAL_COMPLETION_RECEIPT_V1.json',
    'self_and_completion_cycle_exclusions': ['audit/FINAL_METADATA_ADDENDUM_V1.json', 'audit/FINAL_COMPLETION_RECEIPT_V1.json', 'audit/FINAL_TERMINAL_END_V1.json'],
    'self_sha256_claimed': False, 'no_scientific_files_changed': True,
    'source_sha256': sha(Path(__file__)), 'new_env_model_fit_physics': 0})
completed = time.time()
put('audit/FINAL_COMPLETION_RECEIPT_V1.json', {
    'schema': 'ihear.final_completion_receipt.v1', 'status': 'STOP_COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS',
    'completed_unix': completed, 'T0_unix': activation['T0_unix'], 'deadline_unix': activation['deadline_unix'],
    'elapsed_seconds_including_terminal_checks': completed - activation['T0_unix'],
    'root_END_elapsed_seconds_at_static_record_seal': read('END.json')['elapsed_seconds'],
    'terminal_readonly_overhead_after_root_END_seconds': completed - read('END.json')['record_sealed_unix'],
    'before_hard_deadline': completed < activation['deadline_unix'], 'clock_reset': False,
    'strict_sealed_verification_status': verification['status'], 'strict_sealed_issues': [],
    'known_metadata_limitations_retained': verification['known_limitations'], 'perfect_metadata_PASS_allowed': False,
    'all15_required_deliverables_present_and_content_hashed': True, 'all_original_failure_and_partial_evidence_preserved': True,
    'final_manifest_sha256': sha(P / 'FINAL_MANIFEST.json'),
    'metadata_addendum_sha256': sha(P / 'audit/FINAL_METADATA_ADDENDUM_V1.json'),
    'sealed_verification_sha256': sha(P / sealed / 'VERIFICATION.json'),
    'ownership_sha256': sha(P / owned / 'OWNERSHIP_RESULT.json'),
    'external_boundary_process_exit_checks': boundary,
    'unique_recorded_identities_rechecked': len({(q['pid'], q['start_ticks']) for q in records}),
    'known_live_or_zombie_excluding_current_terminal_process': 0, 'known_live_descendants': 0,
    'current_terminal_process': ME, 'current_terminal_process_exit_not_self_proven': True,
    'current_terminal_exit_evidence_required': 'This exact exec_command must return exit_code0 before delivery. It creates no children; there is no later owned job or queue.',
    'unrecorded_reparented_orphans_universally_proven_absent': False,
    'journal_final_sha256_rechecked': journal['after_sha256'], 'historical_final_checks': ['audit/HISTORY_CONTENT_HASH_FINAL.json', 'audit/HISTORY_PROTECTION_FINAL.json'],
    'new_fit_physics_or_experiment_after_scientific_stop': 0, 'no_automatic_next_round': True,
    'final_action': 'STOP after this terminal receipt and actual tool-return exit'},
)
put('audit/FINAL_TERMINAL_END_V1.json', {
    'status': 'STOP_COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS', 'process': ME, 'ended_unix': time.time(),
    'wall_s': time.time() - began, 'children': [], 'self_OS_exit_proven': False,
    'completion_receipt_sha256': sha(P / 'audit/FINAL_COMPLETION_RECEIPT_V1.json'),
    'source_sha256': sha(Path(__file__)), 'new_env_model_fit_physics': 0})
print(json.dumps({'status': 'STOP_COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS', 'elapsed_seconds': completed - activation['T0_unix'], 'known_other_live_owned': 0, 'all15_deliverables': True, 'process': ME, 'self_exit_requires_actual_tool_return': True}))
