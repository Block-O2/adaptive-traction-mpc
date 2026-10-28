"""Collect closed optional-development results; no evaluator/model/physics calls."""
from pathlib import Path
import hashlib
import json
import os
import resource
import time

P = Path(__file__).resolve().parents[1]
GROUPS = ['V8POSTAPP01', 'V8DEVCAP01H', 'V8DEVCAP01L', 'V8POSTAPP02']


def main():
    started, cpu = time.perf_counter(), time.process_time()
    refs = {}

    def read(rel):
        raw = (P / rel).read_bytes()
        refs[rel] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    sr = 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'
    snapshot = read(sr)
    assert snapshot['status'] == 'CLOSED_EXACT' and not snapshot['open_attempt_ids']
    groups = []
    for group in GROUPS:
        config = read('experiments/' + group + '.json')
        supervisor = read('owned/' + group + '_SUPERVISOR_END.json')
        assert supervisor['state'] == 'STOP' and not supervisor['survivors']
        is_app = group.startswith('V8POSTAPP')
        final = read('analysis/' + group + ('_POSTAPP_FINAL.json' if is_app else '_DEV_CAPACITY_FINAL.json'))
        rows = []
        for physical in snapshot['rows']:
            if physical['group'] != group:
                continue
            ident = physical['id']
            replay = read('audit/scorer_replay/' + ident + '.json')
            assert replay['original_result_exact_reproduced'] is True and not replay['errors']
            if ident == group + '_parent':
                continue
            row = read('attempts/' + ident + '_RESULT.json')
            assert row['complete'] is (replay['independent_JF'] is not None)
            assert row['qualified'] is replay['qualified_replay']
            if row['complete']:
                assert row['JF'] == replay['independent_JF'] and row['JM'] == replay['independent_JM']
            rows.append(dict(id=ident, action=row['action'], complete=row['complete'], qualified=row['qualified'],
                             JF=row.get('JF') if row['complete'] else None, JM=row.get('JM') if row['complete'] else None,
                             failed_requirements=(row.get('motion_vs_B') or {}).get('failed_requirements'),
                             error=row.get('error'), actual_new_native_steps=physical['actual_new_native_steps'],
                             formal_qualified_cost_rank_allowed=row['qualified'] is True,
                             original_execution_records_preserved_at='attempts/' + ident + '_RESULT.json'))
        if is_app:
            gate = read('analysis/' + group + '_POSTAPP_B_RAW_GATE.json')
            assert gate['original_compare_result']['status'] == 'PASS'
            raw_gate_scope = 'Original B cross-job full-raw comparison only; no H/phase equivalence claimed.'
        else:
            gate = read('audit/' + group + '_AXIS_L1_REPEAT_REPEAT_GATE.json')
            assert gate['status'] == 'PASS'
            raw_gate_scope = 'Paid lambda1 repeat full-raw equality to this job original H; lambda0 is not B.'
        groups.append(dict(group=group, branch=config['scientific_branch'],
                           case_sha256=config['case_sha256'], seed=config['condition']['seed'],
                           prefix=config['condition']['prefix'], physical_accounting=snapshot['groups'][group],
                           actual_children=len(rows), complete_children=sum(r['complete'] for r in rows),
                           qualified_children=sum(r['qualified'] for r in rows),
                           partial_children=sum(r['complete'] is False for r in rows),
                           original_sequence_counts=final['counts'], NOT_RUN=final['NOT_RUN'], stop=final['stop'],
                           raw_gate='PASS', raw_gate_scope=raw_gate_scope, rows=rows))
    result = dict(schema='v8.closed_optional_development_collection.v1',
                  status='CLOSED_EXPOSED_DEVELOPMENT_NOT_NEW_GENERALIZATION', created_unix=time.time(),
                  groups=groups, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), inputs_sha256=refs,
                  original_independent_validation_conditions_added=0,
                  old_models_labels_or_decisions_transferred_to_new_recipes=False,
                  scope='Copies existing actual complete/partial/qualification/cost and exact increment evidence. All unqualified costs descriptive, partial costs omitted from full-task ranking. No new evaluation.',
                  resource=dict(wall_s=time.perf_counter()-started, CPU_s=time.process_time()-cpu,
                                RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                scope='metadata collector core, not global/incremental process memory'),
                  new_model_scorer_fit_RNG_physics_calls=0)
    with (P / 'analysis/OPTIONAL_EXPOSED_DEVELOPMENT_FINAL_V1.json').open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    audit = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                 ended_unix=time.time(), status=result['status'], result_sha256=hashlib.sha256((P / 'analysis/OPTIONAL_EXPOSED_DEVELOPMENT_FINAL_V1.json').read_bytes()).hexdigest(),
                 resource=result['resource'], new_model_scorer_fit_RNG_physics_calls=0)
    with (P / 'audit/OPTIONAL_DEVELOPMENT_COLLECTION_EXECUTION_V1.json').open('x') as stream:
        json.dump(audit, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], groups=[{k:g[k] for k in ['group','actual_children','complete_children','qualified_children','partial_children']} for g in groups])))


if __name__ == '__main__':
    main()
