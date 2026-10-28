"""Hash the closed research packet and verify required deliverables.

END is written by the root only after this finite process has been joined.
The explicit exclusions avoid recursive manifests and mutable launcher telemetry.
"""
from pathlib import Path
import hashlib
import json
import os
import resource
import signal
import time

P = Path(__file__).resolve().parents[1]
EXCLUDED = {
    'PACKAGE_VERIFICATION.json', 'END.json',
    'audit/PACKAGE_FILE_MANIFEST_V1.json',
    'audit/FINAL_PACKET_EXTERNAL_RESOURCE_V1.txt',
    'audit/FINAL_PACKET_TOOL_JOIN_V1.json',
}
REQUIRED = [
    'REPORT.md', 'EXPERIMENT_CONTRACT.md', 'METHOD_EXPLORATION_MATRIX.md',
    'METHOD_VARIANT_LEDGER.jsonl', 'CRITIC_VALUE_RESULTS.md', 'PPO_REWARD_RESULTS.md',
    'HISTORY_CONDITIONED_RESULTS.md', 'IL_DAGGER_SAC_RESULTS.md',
    'LEARNING_ASSISTED_OPTIMIZATION.md', 'RELATED_WORK.md', 'BASELINE_COMPARISON.md',
    'MOTION_FORCE_MOMENT_TRADEOFF.md', 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json',
    'NEXT_RESEARCH_DECISION.md', 'WORK_STATE.json',
]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            assert time.time() < 1793114740.0
            h.update(block)
    return h.hexdigest()


def read(rel):
    return json.loads((P / rel).read_text())


def save(rel, value):
    with (P / rel).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    started, cpu = time.time(), time.process_time()
    assert started + 330 < 1793114740.0
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('FINITE_FINAL_PACKET_300S_CAP')))
    signal.alarm(300)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    assert not (P / 'PACKAGE_VERIFICATION.json').exists() and not (P / 'END.json').exists()
    identity = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]))
    save('audit/FINAL_PACKET_PROCESS_START_V1.json', dict(**identity, started_unix=started,
                                                       source_sha256=digest(Path(__file__))))
    for rel in REQUIRED:
        assert (P / rel).is_file() and (P / rel).stat().st_size > 0, rel
    assert read('WORK_STATE.json')['status'] == 'STOP'
    snapshot = read('audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json')
    assert snapshot['status'] == 'CLOSED_EXACT' and not snapshot['open_attempt_ids']
    assert snapshot['original_start_count'] == snapshot['original_end_count']
    coverage_rel = 'families/history_conditioned/audit/coverage_runs/MAIN_FINAL_CLOSED_V2_ONCE/RESULT.json'
    coverage = read(coverage_rel)
    assert coverage['status'] == 'COMPLETE_SCOPE_APPROPRIATE_METADATA_COVERAGE' and not coverage['gaps']
    assert coverage['physical_id_count'] == snapshot['original_start_count']
    snapshot_sha = digest(P / 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json')
    assert coverage['physical_snapshot']['path'] == 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'
    assert coverage['physical_snapshot']['sha256'] == snapshot_sha
    assert read(str(Path(coverage_rel).with_name('END.json')))['result_sha256'] == digest(P / coverage_rel)
    assert read('audit/HISTORY_PROTECTION_FINAL.json')['status'] == 'PASS'
    pins = read('audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json')
    assert pins['status'] == 'PASS' and pins['references']['audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'] == snapshot_sha
    accounting = read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json')
    assert accounting['actual_physical']['source']['sha256'] == snapshot_sha
    assert accounting['evaluator_coverage']['source']['sha256'] == digest(P / coverage_rel)
    owned = read('audit/FINAL_OWNED_PROCESS_AUDIT_V1.json')
    assert owned['status'] == 'NO_KNOWN_OR_PACKAGE_RESEARCH_PROCESS_LIVE'
    assert not owned['live_original_identities'] and not owned['parse_errors']
    journal = P.parent / 'RESEARCH_DECISION_JOURNAL.md'
    initial = (P / 'audit/JOURNAL_INITIAL.md').read_bytes()
    current = journal.read_bytes()
    assert current.startswith(initial)
    final_journal = read('audit/JOURNAL_FINAL_PREFIX_VERIFICATION_V1.json')
    assert final_journal['after_sha256'] == hashlib.sha256(current).hexdigest()
    rows, symlinks, hashed_bytes = [], [], 0
    for path in sorted(P.rglob('*')):
        assert time.time() < 1793114740.0
        rel = str(path.relative_to(P))
        if rel in EXCLUDED:
            continue
        if path.is_symlink():
            symlinks.append(dict(path=rel, literal_target=os.readlink(path), scope='literal symlink identity; target bytes not added as another package file'))
            continue
        if not path.is_file():
            continue
        before = path.stat()
        h = digest(path)
        after = path.stat()
        assert (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), 'PACKAGE_FILE_CHANGED_DURING_FINAL_HASH:' + rel
        rows.append(dict(path=rel, sha256=h, bytes=after.st_size))
        hashed_bytes += after.st_size
    manifest_rel = 'audit/PACKAGE_FILE_MANIFEST_V1.json'
    manifest = dict(schema='v8.full_local_packet_file_manifest.v1', status='PASS',
                    created_unix=time.time(), files=rows, symlinks=symlinks,
                    local_regular_file_count=len(rows), bytes_hashed=hashed_bytes,
                    explicit_exclusions=sorted(EXCLUDED),
                    scope='All local regular package files present in the closed snapshot, plus literal symlinks; self/END and exact post-join launcher telemetry excluded to avoid cycles.')
    save(manifest_rel, manifest)
    index = {r['path']:r for r in rows}
    assert all(rel in index for rel in REQUIRED)
    result = dict(schema='v8.final_packet_verification.v1', status='PASS_FOR_RECORDED_RESEARCH_SCOPE',
                  created_unix=time.time(), activation=read('ACTIVATION.json')['activation_id'],
                  original_global_stop_unix=1793114740.0,
                  required_deliverables={rel:index[rel] for rel in REQUIRED},
                  END_scope='Created last by root after this verifier tool exits and its original PID/starttick is absent; root END excluded from recursive hash.',
                  full_packet_manifest=dict(path=manifest_rel, sha256=digest(P / manifest_rel),
                                            local_regular_files=len(rows), bytes_hashed=hashed_bytes),
                  excluded_final_files=sorted(EXCLUDED),
                  exact_physical_ids=snapshot['original_start_count'],
                  exact_new_native_steps=snapshot['actual_new_native_steps_closed'],
                  coverage=dict(path=coverage_rel, sha256=digest(P / coverage_rel), counts=coverage['counts']),
                  historical_protection=dict(path='audit/HISTORY_PROTECTION_FINAL.json', sha256=digest(P / 'audit/HISTORY_PROTECTION_FINAL.json'), status='PASS'),
                  pinned_sources_models=dict(path='audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json', sha256=digest(P / 'audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json'), status='PASS'),
                  owned_processes=dict(path='audit/FINAL_OWNED_PROCESS_AUDIT_V1.json', sha256=digest(P / 'audit/FINAL_OWNED_PROCESS_AUDIT_V1.json'),
                                       status=owned['status'], known_identity_count=owned['known_unique_PID_starttick_count'],
                                       missing_original_startticks_remain_UNKNOWN=len(owned['unrecorded_starttick_metadata_not_fabricated'])),
                  journal=dict(path='../RESEARCH_DECISION_JOURNAL.md', bytes=len(current), sha256=hashlib.sha256(current).hexdigest(), initial_prefix_preserved=True),
                  scientific_scope='Verification PASS is provenance/process/data integrity, not proof of TASK qualification, strong-baseline increment, broad generalization or efficiency.',
                  finite_packaging_process=identity,
                  resources=dict(wall_s=time.time()-started, CPU_s=time.process_time()-cpu,
                                 RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                 local_wall_cap_s=300, CPU_threads=1,
                                 external_resource_receipt='audit/FINAL_PACKET_EXTERNAL_RESOURCE_V1.txt',
                                 external_receipt_written_after_process_exit_and_excluded_from_recursive_hash=True),
                  new_model_scorer_fit_physics_calls=0)
    save('PACKAGE_VERIFICATION.json', result)
    print(json.dumps(dict(status=result['status'], files=len(rows), bytes_hashed=hashed_bytes,
                          PACKAGE_VERIFICATION_sha256=digest(P / 'PACKAGE_VERIFICATION.json'), process=identity)))
    signal.alarm(0)


if __name__ == '__main__':
    main()
