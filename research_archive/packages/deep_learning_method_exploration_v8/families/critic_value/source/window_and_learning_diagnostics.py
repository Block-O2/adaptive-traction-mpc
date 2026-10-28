"""root批准60s、单CPU、0fit/0物理：原始trace窗口与冻结CV目标审计。"""
from pathlib import Path
import hashlib
import itertools
import json
import time
import numpy as np
from short_window_api import select_short

P = Path(__file__).resolve().parents[1]
OLD = P.parents[2] / 'autonomous_learning_smoothness_v7'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(rel, x):
    path = P / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists()
    path.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def integral(t, x, lo, hi):
    return float(np.linalg.norm(x[:-1], axis=1) @ np.maximum(0, np.minimum(t[1:], hi) - np.maximum(t[:-1], lo)))


def main():
    start = time.monotonic()
    data = json.loads((P / 'data/HISTORICAL_RECIPE_DATASET_V2.json').read_text())
    bundle = json.loads((P / 'models/VALUE_FAMILY_V1_FROZEN.json').read_text())
    cv = json.loads((P / 'analysis/OFFLINE_VALUE_CV_V1.json').read_text())
    hashes = {a['recipe_sha256'] for a in bundle['menu']}
    rows = [r for r in data['rows'] if r.get('schema') and r['action_recipe_sha256'] in hashes]
    result, trace_manifest, parent_ids = [], {}, []
    for group in sorted({r['group'] for r in rows}):
        rr = [r for r in rows if r['group'] == group]
        short = {h: [] for h in [.5, 1., 2., 4.]}
        caps, prefixes = set(), set()
        for row in rr:
            cap_path = OLD / 'history' / (row['id'] + '_TAIL_CAUSAL.json')
            cap = json.loads(cap_path.read_text())
            caps.add(cap['fork_parent_hash'])
            trace = OLD / 'runtime/source/results' / row['id'] / 'trace.npz'
            if not trace.exists():
                continue
            trace_manifest[str(trace)] = sha(trace)
            with np.load(trace) as z:
                use = z['stage'] == 'TASK'
                t = z['time_s'][use]
                f = z['physical_cuff_force_world_n'][use]
                m = z['physical_cuff_moment_world_nm'][use]
                before = z['time_s'] <= cap['fork_physical_s'] + 1e-9
                fp = hashlib.sha256()
                for name in ['time_s', 'estimated_human_state_rad_rad_s', 'physical_cuff_force_world_n', 'physical_cuff_moment_world_nm']:
                    fp.update(name.encode())
                    fp.update(z[name][before].tobytes())
                prefixes.add(fp.hexdigest())
            lab = row['labels_evaluation_only']
            if not lab['complete']:
                continue
            fullf, fullm = integral(t, f, t[0], t[-1]), integral(t, m, t[0], t[-1])
            assert abs(fullf - lab['JF_N_s']) < 1e-7 and abs(fullm - lab['JM_Nm_s']) < 1e-7
            fork = cap['fork_physical_s']
            for h in short:
                if t[-1] < fork + h - 1e-9:
                    continue
                short[h].append({'recipe_sha256': row['action_recipe_sha256'], 'parent_hash': cap['fork_parent_hash'],
                                 'horizon_s': h, 'actual_window_complete': True, 'future_outcome_used': False,
                                 'short_JF_N_s': integral(t, f, fork, fork + h), 'short_JM_Nm_s': integral(t, m, fork, fork + h)})
        assert len(caps) == 1, (group, '不同真实父状态不得混菜单')
        assert len(prefixes) == 1, (group, '候选pre-fork物理/observer前缀不同')
        parent_ids.append({'group': group, 'fork_parent_hash': next(iter(caps)), 'observed_measured_prefork_sha256': next(iter(prefixes)), 'context25_sha256': rr[0]['context']['subset_numeric_identity_sha256']})
        qualified = [r for r in rr if r['eligible_for_success_ranking']]
        best = min(qualified, key=lambda r: r['labels_evaluation_only']['JF_N_s'])
        for h, receipts in short.items():
            choice = select_short(receipts, h)
            selected = next(r for r in rr if r['action_recipe_sha256'] == choice['choice_recipe_sha256'])
            lab = selected['labels_evaluation_only']
            result.append({'group': group, 'horizon_s': h, 'short_decision_no_future_mask': choice, 'choice_id': selected['id'],
                           'selected_original_qualified_evaluation_only': lab['original_qualified'], 'selected_full_JF_N_s_evaluation_only': lab['JF_N_s'],
                           'selected_full_JM_Nm_s_evaluation_only': lab['JM_Nm_s'], 'offline_best_qualified_id_evaluation_only': best['id'],
                           'JF_regret_if_qualified_N_s_evaluation_only': lab['JF_N_s'] - best['labels_evaluation_only']['JF_N_s'] if lab['original_qualified'] else None,
                           'menu_missing_partial': [r['id'] for r in rr if not r['labels_evaluation_only']['complete']]})
    put('analysis/SHORT_WINDOW_DIAGNOSTIC_V1.json', {'rows': result, 'parent_identities': parent_ids,
                                                  'distinct_recorded_parent_hashes': len({r['fork_parent_hash'] for r in parent_ids}),
                                                  'distinct_observed_measured_prefixes': len({r['observed_measured_prefork_sha256'] for r in parent_ids}),
                                                  'trace_sha256': trace_manifest, 'short_selector_source_sha256': sha(P / 'source/short_window_api.py'),
                                                  'new_fits': 0, 'new_physics': 0, 'scope': '完整承诺5recipe菜单的历史已暴露开发；未来完整资格仅评价，不参与select_short；此窗口需要真实候选rollout，不称廉价推理或独立部署'} )
    metrics = []
    for method in bundle['methods']:
        abs_err, const_err, centered_err, pair_ok, risk_brier = [], [], [], [], []
        for record in cv['rows']:
            if record['method'] != method + '/JF_QUALIFIED':
                continue
            group = record['heldout_context']
            test = [r for r in rows if r['group'] == group]
            pred = {p['recipe_sha256']: p for p in record['extra']['prediction']['predictions']}
            costs, guesses = [], []
            for r in test:
                p = pred[r['action_recipe_sha256']]
                lab = r['labels_evaluation_only']
                risk_brier.append((p['qualification_failure_score'] - float(not lab['original_qualified'])) ** 2)
                if not lab['complete']:
                    continue
                kind = p['component_semantics']
                if kind == 'ABS':
                    target = [lab['JF_N_s'], lab['JM_Nm_s']]
                else:
                    base_tag = 'LATE_H150' if kind == 'DELTA_STRONG' else 'B'
                    base = next((x for x in test if x['id'].endswith('_' + base_tag)), None)
                    if base is None or not base['labels_evaluation_only']['complete']:
                        continue
                    bl = base['labels_evaluation_only']
                    target = [lab['JF_N_s'] - bl['JF_N_s'], lab['JM_Nm_s'] - bl['JM_Nm_s']]
                guess = [p['predicted_JF_component'], p['predicted_JM_component']]
                abs_err.append((np.asarray(guess) - target) ** 2)
                costs.append(target)
                guesses.append(guess)
                training_same_action = [x for x in rows if x['group'] != group and x['action_recipe_sha256'] == r['action_recipe_sha256'] and x['labels_evaluation_only']['complete']]
                const = []
                for x in training_same_action:
                    xl = x['labels_evaluation_only']
                    if kind == 'ABS':
                        const.append([xl['JF_N_s'], xl['JM_Nm_s']])
                    elif kind != 'DELTA_STRONG':
                        const.append([xl['delta_JF_vs_B_N_s'], xl['delta_JM_vs_B_Nm_s']])
                if const:
                    const_err.append((np.mean(const, axis=0) - target) ** 2)
            if costs:
                e = (np.asarray(guesses) - np.mean(guesses, 0)) - (np.asarray(costs) - np.mean(costs, 0))
                centered_err.extend(e ** 2)
            qq = [r for r in test if r['eligible_for_success_ranking']]
            for a, b in itertools.combinations(qq, 2):
                delta = a['labels_evaluation_only']['JF_N_s'] - b['labels_evaluation_only']['JF_N_s']
                if abs(delta) <= .02:
                    continue
                pa, pb = pred[a['action_recipe_sha256']], pred[b['action_recipe_sha256']]
                pair_ok.append((delta > 0) == (pa['score'] > pb['score']))
        metrics.append({'method': method, 'target_component_RMSE': np.sqrt(np.mean(abs_err, 0)).tolist(),
                        'same_action_constant_target_RMSE': np.sqrt(np.mean(const_err, 0)).tolist() if const_err else None,
                        'within_menu_centered_component_RMSE': np.sqrt(np.mean(centered_err, 0)).tolist(),
                        'qualified_material_JF_pair_accuracy': float(np.mean(pair_ok)) if pair_ok else None,
                        'correlated_qualified_pair_count': len(pair_ok), 'risk_Brier_uncalibrated': float(np.mean(risk_brier))})
    put('analysis/LEARNING_TARGET_DIAGNOSTICS_V1.json', {'methods': metrics, 'wall_s_including_windows': time.monotonic() - start,
                                                       'new_fits': 0, 'new_physics': 0, 'metric_scope': '全部为已暴露开发LOO；PAIR的分量头也是deltaB辅助回归，实际rank用独立utility；不能以误差或pair accuracy代替控制成功。'})
    print(json.dumps({'window_rows': len(result), 'distinct_parent_hashes': len({r['fork_parent_hash'] for r in parent_ids}), 'methods': metrics, 'wall_s': time.monotonic() - start}, ensure_ascii=False))


if __name__ == '__main__':
    main()
