"""Root review of the final exact closed universe; authorizes metadata only.

Does not invoke the aggregator, scorer, model, or physics. Run once after all
scientific jobs and their original evaluation receipts have closed.
"""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
SNAPSHOT = 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'
BASE = 'families/history_conditioned/'
MASTER = 'freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
GLOBAL_STOP = 1793114740.0


def sha(rel):
    path = (P / rel).resolve()
    assert path.is_relative_to(P)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(rel):
    return json.loads((P / rel).read_text())


def ticks(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def main():
    assert time.time() + 90 < GLOBAL_STOP
    snap = read(SNAPSHOT)
    assert snap['status'] == 'CLOSED_EXACT' and not snap['open_attempt_ids']
    assert not snap['unknown_counts_not_imputed_zero']
    authority = read(BASE + 'FINAL_ORIGINAL_REPLAY_COVERAGE_MAIN_APPROVAL_TEMPLATE_REVIEW_ONLY_V2.json')
    original_fixed = {k: v for k, v in authority['inputs_sha256'].items() if v is not None}
    for rel, expected in original_fixed.items():
        assert sha(rel) == expected, rel
    pins = dict(original_fixed)
    pins[SNAPSHOT] = sha(SNAPSHOT)
    pins['runtime/ATTEMPTS.jsonl'] = sha('runtime/ATTEMPTS.jsonl')
    starts, ends = {}, {}
    for raw in (P / 'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
        row = json.loads(raw)
        if row.get('event') in ('START', 'END'):
            table = starts if row['event'] == 'START' else ends
            assert row['id'] not in table
            table[row['id']] = row
    assert starts.keys() == ends.keys() == {x['id'] for x in snap['rows']}
    assert all(x['joined'] is True for x in ends.values())
    for group, summary in snap['groups'].items():
        rel = 'owned/' + group + '_SUPERVISOR_END.json'
        end = read(rel)
        begin = read('owned/' + group + '_SUPERVISOR.json')
        assert end['state'] == 'STOP' and not end['survivors']
        assert sha(rel) == summary['supervisor']['evidence_sha256']
        for identity in [begin['identity'], *end['known_owned'].values()]:
            assert ticks(identity['pid']) != identity['start_ticks']
        pins[rel] = sha(rel)
    assert sha(MASTER) == 'b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
    for rel, expected in read(MASTER)['frozen_artifacts'].items():
        assert sha(rel) == expected, rel
    ordinary = {}
    for path in sorted((P / 'audit/scorer_replay').glob('*.json')):
        ident = path.stem
        assert ident in starts, ident
        rel = str(path.relative_to(P))
        ordinary[rel] = sha(rel)
        pins[rel] = ordinary[rel]
    bindings = []
    for group in ['V8CONVAL01', 'V8CONVAL02']:
        folder = BASE + 'audit/' + group + '_INDEPENDENT_CONTINUOUS_C4_V1/'
        result_rel, end_rel = folder + 'RESULT.json', folder + 'END.json'
        result, end = read(result_rel), read(end_rel)
        assert result['status'] == end['status'] == 'C4_INDEPENDENT_CLOSED_AUDIT_PASS'
        assert not result['errors'] and end['result_sha256'] == sha(result_rel)
        assert result['model_fit_forward_from_audit'] == result['physical_steps_from_audit'] == 0
        pins[result_rel], pins[end_rel] = sha(result_rel), sha(end_rel)
        bindings.append(dict(group=group, result=result_rel, end=end_rel))
    authority.update(status='ROOT_APPROVED_ONE_CLOSED_METADATA_AGGREGATION_V2',
                     main_all_physical_jobs_closed_verified=True,
                     expires_unix=min(time.time() + 180, GLOBAL_STOP),
                     physical_snapshot=dict(path=SNAPSHOT, sha256=sha(SNAPSHOT)),
                     inputs_sha256=pins, scorer_replay_files_sha256=ordinary,
                     c4_results=bindings,
                     source_manifest_sha256=sha(BASE + 'FINAL_ORIGINAL_REPLAY_COVERAGE_SOURCE_MANIFEST_V2.json'),
                     output=BASE + 'audit/coverage_runs/MAIN_FINAL_CLOSED_V2_ONCE',
                     approved_partial_parent_prefix_scope='PARTIAL_PREFIX_NO_FULL_TASK_NO_SCORER_APPLICABLE',
                     approved_partial_parent_prefix_no_TASK_scorer_ids=[
                         'V8FROZENENG01_parent', 'V8OP01H_parent', 'V8BETA02L_parent'],
                     main_review_source=dict(path=str(Path(__file__).relative_to(P)),
                                             sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
                     main_aggregator_source_review=dict(path='audit/FINAL_COVERAGE_AGGREGATOR_MAIN_SOURCE_REVIEW_V2.json',
                                                        sha256=sha('audit/FINAL_COVERAGE_AGGREGATOR_MAIN_SOURCE_REVIEW_V2.json')))
    target = P / 'audit/FINAL_ORIGINAL_REPLAY_COVERAGE_MAIN_APPROVAL_V2.json'
    with target.open('x') as stream:
        json.dump(authority, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=authority['status'], approval_sha256=sha(str(target.relative_to(P))),
                          physical_ids=len(starts), ordinary_receipts=len(ordinary), source_model_pins=2042)))


if __name__ == '__main__':
    main()
