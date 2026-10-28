"""Metadata-only incremental accounting; never infer zero for missing evidence.

Actual increment fields exclude inherited fork prefixes. Persistent boundary
events can own new physics without a DATA file and are counted from END.
"""
from pathlib import Path
import argparse, collections, hashlib, json, time

P = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--require-all-closed', action='store_true')
    args = parser.parse_args()
    target = (P / args.output).resolve()
    assert target.is_relative_to(P) and not target.exists()
    events = []
    for raw in (P / 'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
        row = json.loads(raw)
        if row.get('event') in ('START', 'END'):
            events.append((row, hashlib.sha256(raw).hexdigest()))
    starts, ends = {}, {}
    for row, h in events:
        table = starts if row['event'] == 'START' else ends
        assert row['id'] not in table, 'DUPLICATE_EVENT:' + row['id']
        table[row['id']] = (row, h)
    assert not (set(ends) - set(starts)), 'END_WITHOUT_START'
    open_ids = sorted(set(starts) - set(ends))
    if args.require_all_closed:
        assert not open_ids, 'UNCLOSED_STARTED_ATTEMPTS'
    rows, groups, unresolved = [], {}, []
    for ident, (start, start_sha) in starts.items():
        if ident not in ends:
            continue
        end, end_sha = ends[ident]
        assert end.get('joined') is True, 'END_NOT_JOINED:' + ident
        group = start['group']
        source_counts = []
        for suffix in ('_DATA.json', '_PARTIAL_COMPUTE.json'):
            path = P / 'runtime/output' / (ident + suffix)
            if path.exists():
                data = load(path)
                metric = data.get('metric', data)
                count = metric.get('actual_new_native_physics_steps')
                if integer(count):
                    source_counts.append(dict(path=str(path.relative_to(P)), sha256=sha(path),
                                              field='metric.actual_new_native_physics_steps' if 'metric' in data else 'actual_new_native_physics_steps',
                                              actual_increment=count))
        result_path = P / 'attempts' / (ident + '_RESULT.json')
        result = load(result_path) if result_path.exists() else None
        if result and integer(result.get('actual_new_native_steps')):
            source_counts.append(dict(path=str(result_path.relative_to(P)), sha256=sha(result_path),
                                      field='actual_new_native_steps', actual_increment=result['actual_new_native_steps']))
        for key in ('actual_new_native_steps', 'native_steps'):
            if integer(end.get(key)):
                source_counts.append(dict(path='runtime/ATTEMPTS.jsonl', raw_line_without_newline_sha256=end_sha,
                                          field='END.' + key, actual_increment=end[key]))
        counts = {r['actual_increment'] for r in source_counts}
        if not counts:
            unresolved.append(dict(id=ident, reason='NO_ACTUAL_INCREMENT_EVIDENCE_NOT_IMPUTED_ZERO'))
            count = None
        else:
            assert len(counts) == 1, 'CONFLICTING_ACTUAL_INCREMENTS:' + ident + ':' + str(counts)
            count = counts.pop()
        row = dict(id=ident, group=group, category=start.get('category'), kind=start.get('kind'),
                   original_returncode=end.get('returncode'), joined=end.get('joined'),
                   parent_hash_equal=end.get('parent_hash_equal'),
                   actual_new_native_steps=count, actual_new_simulation_s=count * .00025 if count is not None else None,
                   complete_original_result=result.get('complete') if result else None,
                   original_qualified=result.get('qualified') if result else None,
                   START_raw_line_sha256=start_sha, END_raw_line_sha256=end_sha,
                   evidence=source_counts)
        rows.append(row)
        g = groups.setdefault(group, dict(start_count=0, closed_count=0, actual_new_native_steps=0,
                                         qualified_policy_or_control_results=0, complete_failed_results=0))
        g['closed_count'] += 1
        if count is not None:
            g['actual_new_native_steps'] += count
        g['qualified_policy_or_control_results'] += int(bool(result and result.get('qualified') is True))
        g['complete_failed_results'] += int(bool(result and result.get('complete') is True and result.get('qualified') is False))
    for start, _ in starts.values():
        groups.setdefault(start['group'], dict(start_count=0, closed_count=0, actual_new_native_steps=0,
                                               qualified_policy_or_control_results=0, complete_failed_results=0))['start_count'] += 1
    for group, summary in groups.items():
        path = P / 'owned' / (group + '_SUPERVISOR_END.json')
        if path.exists():
            end = load(path)
            summary['supervisor'] = dict(state=end['state'], worker_exit_code=end['worker_exit_code'],
                                         survivors=end['survivors'], wall_s=end['wall_s'], evidence_sha256=sha(path))
            if args.require_all_closed:
                assert end['state'] == 'STOP' and not end['survivors']
    if args.require_all_closed:
        assert not unresolved, 'UNRESOLVED_NATIVE_INCREMENT_COUNTS'
    total = sum(r['actual_new_native_steps'] for r in rows if r['actual_new_native_steps'] is not None)
    out = dict(schema='v8.actual_physical_increment_snapshot.v1', status='CLOSED_EXACT' if not open_ids and not unresolved else 'IN_PROGRESS_CLOSED_SUBSET',
               created_unix=time.time(), source_sha256=sha(Path(__file__)), activation=load(P / 'ACTIVATION.json')['activation_id'],
               original_start_count=len(starts), original_end_count=len(ends), open_attempt_ids=open_ids,
               unknown_counts_not_imputed_zero=unresolved, actual_new_native_steps_closed=total,
               actual_new_simulation_s_closed=total * .00025, groups=groups, rows=rows,
               accounting_rule='Use original actual_new increment; count each started parent once and each fork child own suffix once. Boundary-only END counts included; inherited absolute native_steps in DATA excluded.',
               reused_historical_native_steps_added=0, new_model_forward=0, new_fit=0, new_physics=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as stream:
        json.dump(out, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k:out[k] for k in ['status', 'original_start_count', 'original_end_count', 'open_attempt_ids', 'actual_new_native_steps_closed', 'unknown_counts_not_imputed_zero']}))

if __name__ == '__main__':
    main()
