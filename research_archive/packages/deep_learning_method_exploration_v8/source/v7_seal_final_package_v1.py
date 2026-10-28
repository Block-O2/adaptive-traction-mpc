"""Seal the concrete v7 package after strict preseal success. No science work."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import time
from datetime import datetime, timezone

P = Path(__file__).resolve().parents[1]
NOW = time.time()
SELF = {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def read(rel):
    return json.loads((P / rel).read_text())


def put(rel, data):
    path = P / rel
    assert not path.exists(), 'NO_OVERWRITE:' + rel
    temp = path.with_name('.' + path.name + '.' + str(os.getpid()) + '.tmp')
    with temp.open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.link(temp, path)
    temp.unlink()


def evidence(rel):
    return {'path': rel, 'sha256': sha(P / rel)}


activation = read('ACTIVATION.json')
assert NOW < activation['deadline_unix']
assert not any((P / name).exists() for name in ['PACKAGE_VERIFICATION.json', 'END.json', 'FINAL_MANIFEST.json'])
pre_dir = 'audit/final_verification_v7_preseal_v2'
pre = read(pre_dir + '/VERIFICATION.json')
assert pre['status'] == 'COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS' and not pre['issues']
assert pre['observations']['physical_START'] == pre['observations']['physical_END'] == 170
assert set(pre['observations']['preseal_pending']) == {'PACKAGE_VERIFICATION.json', 'END.json'}
spec = importlib.util.spec_from_file_location('genuine_ownership_checker', P / 'agent_reviews/final_metadata_inventory/final_ownership_checker.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
pre_identity = read(pre_dir + '/END.json')['process']
proc, proc_errors = checker.proc_snapshot()
assert not proc_errors
assert pre_identity['pid'] not in proc or proc[pre_identity['pid']]['start_ticks'] != pre_identity['start_ticks'], 'PRESEAL_PROCESS_STILL_PRESENT'
inventory = copy.deepcopy(read('audit/ACTUAL_FINAL_OWNERSHIP_INVENTORY_V2.json'))
files = {row['path']: row for row in inventory['metadata_files']}
for f in (P / 'owned').glob('*.json'):
    files.setdefault(str(f.relative_to(P)), {'path': str(f.relative_to(P)), 'origin': 'ROOT_OWNED_FRESH', 'selectors': 'canonical_genuine_metadata'})
for folder in (P / 'audit').glob('final_verification_*'):
    if folder.is_dir():
        for name in ['START.json', 'END.json']:
            f = folder / name
            if f.is_file():
                rel = str(f.relative_to(P))
                files[rel] = {'path': rel, 'sha256': sha(f), 'origin': 'ACTUAL_MAIN_VERIFIER_BOUNDARY', 'selectors': 'canonical_genuine_metadata'}
records = []
for rel, item in files.items():
    f = P / rel
    assert f.is_file(), 'MISSING_METADATA:' + rel
    if item.get('sha256'):
        assert sha(f) == item['sha256'], 'METADATA_CHANGED:' + rel
    obj = read(rel)
    if item.get('selectors') == 'canonical_genuine_metadata':
        items = list(checker.extract(obj))
    else:
        items = []
        for selector in item.get('selectors', []):
            d = checker.pointer(obj, selector['pointer'])
            items.append({'pid': checker.canonical_int(d[selector['pid_key']]), 'start_ticks': checker.canonical_int(d[selector['ticks_key']]), **selector})
    records += [{**q, 'source': rel} for q in items]
closure = checker.evaluate(records, proc, SELF)
assert closure['all_OTHER_recorded_processes_ended_or_reused']
put('audit/SEAL_PRECEDING_PROCESS_CLOSURE_V1.json', {
    'status': 'NO_OTHER_LIVE_RECORDED_OWNED_SELF_PENDING_TOOL_RETURN', 'created_unix': NOW, 'process': SELF,
    'preseal_verifier_tool_exit_code_observed': 0, 'preseal_verifier_identity': pre_identity,
    'preseal_verifier_PID_ticks_absent_after_tool_return': True,
    'unique_preceding_recorded_identities': len({(q['pid'], q['start_ticks']) for q in records}),
    'live_or_zombie_known': closure['live_or_zombie_known'], 'live_known_descendants': closure['live_known_descendants'],
    'inventory_base': evidence('audit/ACTUAL_FINAL_OWNERSHIP_INVENTORY_V2.json'),
    'self_exit_proven': False, 'next_external_check': 'audit/ownership_final_v2/OWNERSHIP_RESULT.json',
    'unrecorded_reparented_orphans_universally_proven_absent': False, 'new_env_model_fit_physics': 0})
integral = read('agent_reviews/integral_audit/incremental_final_lstf_v3/THREE_SNAPSHOT_170_CLOSURE.json')
assert integral['status'] == 'PASS' and integral['union_count'] == 170 and integral['pairwise_disjoint'] and integral['all_three_audits_PASS']
accounting = read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json')
assert accounting['physical_START'] == accounting['physical_END'] == 170 and accounting['actual_new_native_steps'] == 12997720
journal = read('audit/JOURNAL_PREFIX_FINAL.json')
assert sha(Path(journal['journal_path'])) == journal['after_sha256'] and journal['original_prefix_preserved'] and journal['only_append_no_history_overwrite']
index = read('audit/FINAL_EVIDENCE_INDEX_V2.json')
for rel, digest in index['artifact_sha256'].items():
    assert sha(P / rel) == digest, 'MODEL_DATA_CHANGED:' + rel
required = ['REPORT.md', 'EXPERIMENT_CONTRACT.md', 'BASELINE_AND_PAIRED_OPTIMIZATION.md', 'LEARNING_METHODS_AUDIT.md', 'CRITIC_AND_VALUE_RESULTS.md', 'RL_AND_REWARD_RESULTS.md', 'HISTORY_CONDITIONED_LEARNING.md', 'MOTION_FORCE_MOMENT_TRADEOFF.md', 'RELATED_WORK.md', 'LEARNING_CONTROL_INTERFACE_GUIDE.md', 'RESEARCH_DECISIONS.jsonl', 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json', 'PACKAGE_VERIFICATION.json', 'NEXT_RESEARCH_DECISION.md', 'END.json']
for name in required:
    if name not in ['PACKAGE_VERIFICATION.json', 'END.json']:
        assert (P / name).is_file()
scientific_end = 1793055095.4496493
sealed_check = 'audit/final_verification_v7_sealed_v3/VERIFICATION.json'
terminal_receipt = 'audit/FINAL_COMPLETION_RECEIPT_V1.json'
verification = {
    'schema': 'ihear.package_verification.v7.final', 'status': 'COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS',
    'created_unix': NOW, 'verification_stage_at_record_seal': 'STRICT_PRESEAL_COMPLETED',
    'activation_id': activation['activation_id'], 'required_deliverables': required,
    'strict_preseal': evidence(pre_dir + '/VERIFICATION.json'), 'strict_preseal_END': evidence(pre_dir + '/END.json'),
    'strict_preseal_issues': [], 'known_limitations': pre['known_limitations'],
    'metadata_limitations': evidence('audit/FINAL_METADATA_LIMITATIONS_V2.json'), 'perfect_metadata_PASS_allowed': False,
    'final_manifest': 'FINAL_MANIFEST.json',
    'terminal_checks': {'sealed_verification': sealed_check, 'ownership': 'audit/ownership_final_v2/OWNERSHIP_RESULT.json',
                        'completion_receipt': terminal_receipt, 'hash_addendum': 'audit/FINAL_METADATA_ADDENDUM_V1.json',
                        'must_pass_before_user_delivery': True, 'pending_at_this_immutable_record_creation': True,
                        'scope': 'Only read-only verification and its own closure metadata; no new scientific computation'},
    'raw_and_original_scorer': {
        'status': 'CONFIRMED_IN_REGISTERED_SCOPE', 'three_disjoint_integral_audits': [59, 104, 7],
        'closure': evidence('agent_reviews/integral_audit/incremental_final_lstf_v3/THREE_SNAPSHOT_170_CLOSURE.json'),
        'original_scorer_replay_directory': 'audit/scorer_replay', 'raw_hashes_bound_by_index_and_manifest': True,
        'failed_partial_and_engineering_raw_preserved': True, 'partial_or_unqualified_formal_cost_ranking_allowed': False,
        'DEVRC01_B': 'Recovered original physical PASS; original worker failure retained; engineering unranked',
        'DEVRT02_B': 'Original complete qualified B preserved despite later job path-check failure',
        'HOLDSS01_B': 'Actual START group HOLDSS02; complete raw, no original motion verdict; engineering unranked'},
    'accounting': evidence('RESOURCE_AND_ATTEMPT_ACCOUNTING.json'),
    'model_and_data_sha256': index['artifact_sha256'],
    'historical_content': evidence('audit/HISTORY_CONTENT_HASH_FINAL.json'),
    'historical_metadata_and_critical_sources': evidence('audit/HISTORY_PROTECTION_FINAL.json'),
    'historical_full_hash_exact_T0': False,
    'journal': {**evidence('audit/JOURNAL_PREFIX_FINAL.json'), 'original_prefix_bytes': 24862, 'original_prefix_sha256': journal['original_prefix_sha256'], 'final_journal_sha256': journal['after_sha256'], 'prefix_unchanged_append_only': True},
    'preceding_process_closure': evidence('audit/SEAL_PRECEDING_PROCESS_CLOSURE_V1.json'),
    'review_index': evidence('audit/FINAL_REVIEW_INDEX_V2.json'), 'review_records': 40, 'top_level_review_directories': 38,
    'scientific_contract_unchanged': True, 'original_physics_sources_checkpoints_and_raw_modified': False,
    'new_env_model_fit_physics_during_seal': 0,
    'not_equivalent_conclusions': {
        'method_effective': 'CONFIRMED only in specified finite conditions; traditional positives and scientific negatives separately retained',
        'learning_independent_increment_over_strongest_traditional': 'NOT_DEMONSTRATED',
        'total_compute_or_actual_attempt_efficiency_advantage': 'NOT_DEMONSTRATED; actual simulator attempts saved0, hardware0',
        'independent_generalization': 'LIMITED_FIXED_PREFIX_EVIDENCE_WITH_SS_NEGATIVE; no patient/hardware validation'},
    'no_automatic_next_round': True,
}
put('PACKAGE_VERIFICATION.json', verification)
seal_time = time.time()
put('END.json', {
    'schema': 'ihear.autonomous_research_end.v7', 'status': 'STOP_SCIENTIFIC_RUN_SEALED_WITH_DOCUMENTED_METADATA_LIMITATIONS',
    'activation_id': activation['activation_id'], 'T0_unix': activation['T0_unix'], 'T0_UTC': activation['T0_UTC'],
    'deadline_unix': activation['deadline_unix'], 'deadline_UTC': activation['deadline_UTC'], 'clock_reset': False,
    'scientific_physical_end_unix': scientific_end,
    'scientific_physical_elapsed_seconds': scientific_end - activation['T0_unix'],
    'record_sealed_unix': seal_time, 'record_sealed_UTC': datetime.fromtimestamp(seal_time, timezone.utc).isoformat(),
    'elapsed_seconds': seal_time - activation['T0_unix'], 'elapsed_scope': 'Activation through immutable root END record seal. Later read-only terminal verification overhead is separately measured by completion_receipt.',
    'deadline_exceeded_at_seal': seal_time >= activation['deadline_unix'],
    'stop_class': 'SCIENTIFIC_FINITE_SCOPE_SUPPORTED',
    'stop_reason': 'Discriminating finite revisions and independent scientific review completed. Current models show no independent increment; future work requires a new benefit-ranking or fair-interface premise. No first-queue/quota/fixed-trial/time-fill stop.',
    'physical_START': 170, 'physical_END': 170, 'cold_parents': 26, 'fork_candidates': 144,
    'actual_new_native_steps': 12997720, 'candidate_classes': {'complete_original_qualified': 78, 'complete_original_unqualified': 51, 'physically_partial_unranked': 13, 'complete_engineering_unranked': 2},
    'hardware_attempts': 0, 'clinical_patients': 0, 'actual_simulator_attempts_saved': 0,
    'outcomes': {'traditional': 'Finite nominal/prefix microgain; SS negative. Heavy earlyH150 smoothness gain with JM tradeoff, light failures.',
                 'learning': 'No demonstrated independent increment over strongest traditional/simple equivalent; GP/quad same action, JM sign wrong; stumps gate NOT_MET.',
                 'fresh_RL_and_long_Q_Value_WM': 'NOT_RUN; offline diagnostics and historical evidence are separately identified'},
    'all_scientific_supervisors_stopped': True, 'physical_START_END_exact_closed': True,
    'normal_failed_worker_join_receipt_gaps': ['DEVRC01', 'DEVRT01', 'DEVRT02', 'HOLDSS02'],
    'all_prior_recorded_processes_ended_in_checked_scope': True, 'sealing_process': SELF,
    'sealing_process_self_exit_proven_at_record_creation': False,
    'remaining_permitted_actions': 'Only declared read-only sealed verification, ownership scan and terminal metadata receipt; no new fit, simulation, experiment or queue.',
    'completion_receipt': terminal_receipt, 'completion_receipt_required_before_delivery': True,
    'package_verification': evidence('PACKAGE_VERIFICATION.json'), 'final_manifest_path': 'FINAL_MANIFEST.json',
    'metadata_limitations': evidence('audit/FINAL_METADATA_LIMITATIONS_V2.json'), 'perfect_PID_or_metadata_compliance_claim': False,
    'historical_sources_checkpoints_raw_unchanged_in_checked_scope': True, 'journal_prefix_preserved': True,
    'git_write_operations': 0, 'Stage2_final_Campaign_hardware_launched': False,
    'next_research_decision': evidence('NEXT_RESEARCH_DECISION.md'), 'no_automatic_next_round': True,
    'initial_ACTIVATION_state_is_historical_identity_not_current_status': True,
})

# These exact future metadata files are bound in the terminal addendum instead
# of creating cyclic self-hashes. Scientific files and all15 root deliverables
# are already present and included in the final manifest.
future_files = {'FINAL_MANIFEST.json', 'audit/FINAL_EVIDENCE_INDEX_V3_SEALED.json',
                'audit/FINAL_OWNERSHIP_INVENTORY_V3.json', 'audit/FINAL_SEAL_BUILD_RECEIPT_V1.json',
                'audit/FINAL_METADATA_ADDENDUM_V1.json', 'audit/FINAL_COMPLETION_RECEIPT_V1.json',
                'audit/FINAL_TERMINAL_START_V1.json', 'audit/FINAL_TERMINAL_END_V1.json'}
future_prefixes = ['audit/final_verification_v7_sealed_v3/', 'audit/ownership_final_v2/']
for f in (P / 'owned').glob('*_START.json'):
    d = json.loads(f.read_text())
    if d.get('pid') == SELF['pid'] and int(d.get('start_ticks', -1)) == SELF['start_ticks']:
        future_files.add(str(f.with_name(f.name[:-len('_START.json')] + '_END.json').relative_to(P)))
manifest_files, symlinks, total = {}, {}, 0
for f in sorted(P.rglob('*')):
    rel = str(f.relative_to(P))
    if rel in future_files or any(rel.startswith(prefix) for prefix in future_prefixes):
        continue
    if f.is_symlink():
        symlinks[rel] = os.readlink(f)
    elif f.is_file():
        before = f.stat()
        manifest_files[rel] = sha(f)
        after = f.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'CHANGED_DURING_FINAL_HASH:' + rel
        total += before.st_size
assert set(required) <= manifest_files.keys()
put('FINAL_MANIFEST.json', {'schema': 'ihear.final_content_manifest.v7', 'status': 'PASS_HASHED_FINAL_STATIC_PACKAGE',
                           'created_unix': time.time(), 'files': manifest_files, 'symlinks': symlinks, 'bytes_hashed': total,
                           'required_deliverables_count': 15, 'all15_deliverables_content_hashed': True,
                           'includes_original_failure_and_partial_evidence': True, 'metadata_limits_present': True,
                           'exact_future_metadata_exclusions': sorted(future_files), 'future_metadata_prefix_exclusions': future_prefixes,
                           'future_metadata_binding': 'audit/FINAL_METADATA_ADDENDUM_V1.json; self-hash excluded, external completion receipt binds it',
                           'self_sha256_claimed': False})
sealed_index = copy.deepcopy(index)
sealed_index['package_manifests'].append({'path': 'FINAL_MANIFEST.json', 'sha256': sha(P / 'FINAL_MANIFEST.json'),
                                         'require': {'/status': 'PASS_HASHED_FINAL_STATIC_PACKAGE', '/all15_deliverables_content_hashed': True, '/required_deliverables_count': 15}})
sealed_index['final_references']['root_package_verification'] = {'path': 'PACKAGE_VERIFICATION.json', 'sha256': sha(P / 'PACKAGE_VERIFICATION.json'), 'require': {'/status': verification['status']}}
put('audit/FINAL_EVIDENCE_INDEX_V3_SEALED.json', sealed_index)
# Add only real main verifier/sealer boundaries. Root-owned files are also
# freshly scanned by the checker; no synthetic recursive fixture discovery.
for rel in ['END.json', 'audit/SEAL_PRECEDING_PROCESS_CLOSURE_V1.json']:
    files[rel] = {'path': rel, 'sha256': sha(P / rel), 'origin': 'ACTUAL_MAIN_FINAL_SEAL_BOUNDARY', 'selectors': 'canonical_genuine_metadata'}
for rel in ['audit/final_verification_v7_sealed_v3/START.json', 'audit/final_verification_v7_sealed_v3/END.json']:
    files[rel] = {'path': rel, 'origin': 'ACTUAL_MAIN_SEALED_VERIFIER_BOUNDARY_FUTURE_REQUIRED', 'selectors': 'canonical_genuine_metadata'}
inventory.update(metadata_files=list(files.values()), created_unix=time.time(), source_sha256=sha(Path(__file__)), pending_review=[],
                 main_final_refresh='Only new genuine main process boundaries; all original selectors/hashes retained')
put('audit/FINAL_OWNERSHIP_INVENTORY_V3.json', inventory)
put('audit/FINAL_SEAL_BUILD_RECEIPT_V1.json', {
    'status': 'FINAL_STATIC_PACKAGE_SEALED_PENDING_DECLARED_TERMINAL_READONLY_CHECKS', 'created_unix': time.time(), 'process': SELF,
    'files': len(manifest_files), 'bytes_hashed': total, 'all15_deliverables_content_hashed': True,
    'manifest': evidence('FINAL_MANIFEST.json'), 'index': evidence('audit/FINAL_EVIDENCE_INDEX_V3_SEALED.json'),
    'ownership_inventory': evidence('audit/FINAL_OWNERSHIP_INVENTORY_V3.json'), 'source_sha256': sha(Path(__file__)),
    'self_exit_proven': False, 'new_env_model_fit_physics': 0})
print('FINAL_STATIC_PACKAGE_SEALED', len(manifest_files), 'files; all15 hashed; terminal read-only checks remain')
