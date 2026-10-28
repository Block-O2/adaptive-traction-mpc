"""已批准的小样本 episode Value 机制比较；零新物理，整context开发CV。"""
from pathlib import Path
import hashlib
import itertools
import json
import os
import resource
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from value_api import FEATURE_NAMES, design, predict, to_context25, transform

P = Path(__file__).resolve().parents[1]
DATA_SHA = 'ea35953cf6e8775a7331a80febf1219b2d2d047677fb2cc57db6e8baf0773ed5'
TAGS = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
VARIANTS = {'ABS_25': ('ABS', 25), 'DELTA_25': ('DELTA_B', 25), 'PAIR_25': ('PAIR', 25), 'DELTA_15': ('DELTA_B', 15), 'DELTA_0': ('DELTA_B', 0), 'STRONG_DELTA_25': ('DELTA_STRONG', 25)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(rel, x):
    path = P / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), '禁止覆盖冻结产物：' + str(path)
    path.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def logistic(A, y, reg=.3):
    if len(y) == 0:
        return np.zeros(A.shape[1])
    def objective(w):
        z = A @ w
        return float(np.mean(np.logaddexp(0, z) - y * z) + .5 * reg * w @ w), A.T @ (expit(z) - y) / len(y) + reg * w
    opt = minimize(objective, np.zeros(A.shape[1]), jac=True, method='L-BFGS-B', options={'maxiter': 200, 'ftol': 1e-11})
    assert opt.success or np.linalg.norm(opt.jac) < 1e-4, opt.message
    return opt.x


def model(rows, menu, kind, dimensions):
    groups = sorted({r['group'] for r in rows})
    contexts = {r['group']: to_context25(r['context']) for r in rows}
    indices = list(range(dimensions))
    X = np.array([contexts[g]['features'] for g in groups])[:, indices]
    center = X.mean(0)
    floor = np.array([.1] * 5 + [1.] * 2 + [.1] * 4 + [.005] * 4 + [.05] * 10)[indices]
    scale = np.maximum(X.std(0), floor)
    spec = {'indices': indices, 'center': center.tolist(), 'scale': scale.tolist(), 'target_kind': kind}
    zs = {g: transform(spec, c) for g, c in contexts.items()}
    actions = {a['recipe_sha256']: i for i, a in enumerate(menu)}
    use = [r for r in rows if r['action_recipe_sha256'] in actions]
    dim = len(menu) * (1 + dimensions)
    Aall = np.array([design(zs[r['group']], actions[r['action_recipe_sha256']], len(menu)) for r in use])
    risk_y = np.array([not r['labels_evaluation_only']['original_qualified'] for r in use], float)
    spec['risk_weights'] = logistic(Aall, risk_y).tolist()
    spec['support_train_z'] = [[zs[r['group']].tolist() for r in use if actions[r['action_recipe_sha256']] == i] for i in range(len(menu))]
    by = {(r['group'], menu[actions[r['action_recipe_sha256']]]['tag']): r for r in use}
    valid, targets = [], []
    for r in use:
        lab = r['labels_evaluation_only']
        if not lab['complete'] or lab['JF_N_s'] is None or lab['JM_Nm_s'] is None:
            continue
        y = np.array([lab['JF_N_s'], lab['JM_Nm_s']])
        if kind in ['DELTA_B', 'PAIR', 'DELTA_STRONG']:
            base = by.get((r['group'], 'LATE_H150' if kind == 'DELTA_STRONG' else 'B'))
            if base is None or not base['labels_evaluation_only']['complete']:
                continue
            bl = base['labels_evaluation_only']
            y -= [bl['JF_N_s'], bl['JM_Nm_s']]
        valid.append(design(zs[r['group']], actions[r['action_recipe_sha256']], len(menu)))
        targets.append(y)
    A, Y = np.array(valid), np.array(targets)
    yc, ys = Y.mean(0), np.maximum(Y.std(0), [.02, .01])
    norm_y = (Y - yc) / ys
    spec['target_center'], spec['target_scale'] = yc.tolist(), ys.tolist()
    spec['cost_weights'] = [np.linalg.solve(A.T @ A + lam * np.eye(dim), A.T @ norm_y).tolist() for lam in [.1, 1., 10.]]
    pair_A, yf, ym = [], [], []
    for g in groups:
        rr = [r for r in use if r['group'] == g and r['eligible_for_success_ranking']]
        for a, b in itertools.combinations(rr, 2):
            la, lb = a['labels_evaluation_only'], b['labels_evaluation_only']
            da = design(zs[g], actions[a['action_recipe_sha256']], len(menu))
            db = design(zs[g], actions[b['action_recipe_sha256']], len(menu))
            df, dm = la['JF_N_s'] - lb['JF_N_s'], la['JM_Nm_s'] - lb['JM_Nm_s']
            if abs(df) <= .02:
                continue
            pair_A.append(da - db)
            yf.append(float(df < 0))
            ym.append(float(dm < 0))
    PA = np.array(pair_A).reshape((-1, dim))
    spec['rank_weights_JF'] = logistic(PA, np.array(yf)).tolist()
    spec['rank_weights_JM'] = logistic(PA, np.array(ym)).tolist()
    spec['fit_rows'] = len(Y)
    spec['risk_rows'] = len(use)
    spec['pair_rows_correlated'] = len(yf)
    spec['train_groups'] = groups
    spec['continuation_policy'] = 'FULL_POLICY_COMMITMENT_WITH_FROZEN_SLOT_OVERRIDES'
    return spec


def result(group, method, choice, test_rows, extra=None):
    by = {r['action_recipe_sha256']: r for r in test_rows}
    chosen = by.get(choice)
    b = next(r for r in test_rows if r['action']['family'] == 'B')
    actual = None if chosen is None else chosen['labels_evaluation_only']
    return {'heldout_context': group, 'method': method, 'choice_recipe_sha256': choice,
            'choice_id': None if chosen is None else chosen['id'],
            'actual_available': actual is not None, 'original_qualified': None if actual is None else actual['original_qualified'],
            'JF_N_s': None if actual is None else actual['JF_N_s'], 'JM_Nm_s': None if actual is None else actual['JM_Nm_s'],
            'delta_JF_vs_B_N_s': None if actual is None else actual['delta_JF_vs_B_N_s'],
            'delta_JM_vs_B_Nm_s': None if actual is None else actual['delta_JM_vs_B_Nm_s'],
            'B_recipe_sha256': b['action_recipe_sha256'], 'extra': extra}


def fixed_best(rows, menu):
    groups = sorted({r['group'] for r in rows})
    scores = []
    for a in menu:
        use = [r for r in rows if r['action_recipe_sha256'] == a['recipe_sha256']]
        # 缺少真实反事实视为不支持，不填标签。
        failures = len(groups) - len(use) + sum(not r['eligible_for_success_ranking'] for r in use)
        delta = np.mean([r['labels_evaluation_only']['delta_JF_vs_B_N_s'] for r in use if r['eligible_for_success_ranking']]) if any(r['eligible_for_success_ranking'] for r in use) else 1e6
        scores.append((failures, float(delta), a['tag'], a['recipe_sha256']))
    return min(scores)[-1]


def stump(rows, menu):
    contexts = {r['group']: r['context']['features'] for r in rows}
    best_fixed = fixed_best(rows, menu)
    def loss(f, threshold, left, right):
        fail, costs = 0, []
        for g, x in contexts.items():
            arm = left if x[f] <= threshold else right
            r = next((r for r in rows if r['group'] == g and r['action_recipe_sha256'] == arm), None)
            if r is None or not r['eligible_for_success_ranking']:
                fail += 1
            else:
                costs.append(r['labels_evaluation_only']['delta_JF_vs_B_N_s'])
        return fail, float(np.mean(costs)) if costs else 1e6
    best = None
    for f in range(25):
        values = sorted({x[f] for x in contexts.values()})
        for lo, hi in zip(values, values[1:]):
            threshold = (lo + hi) / 2
            lr = [[r for r in rows if (contexts[r['group']][f] <= threshold) == left] for left in [True, False]]
            left, right = [fixed_best(rs, menu) for rs in lr]
            candidate = (loss(f, threshold, left, right), f, threshold, left, right)
            if best is None or candidate < best:
                best = candidate
    return {'kind': 'constant', 'recipe': best_fixed} if best is None else {'kind': 'if', 'feature_index': best[1], 'feature_name': FEATURE_NAMES[best[1]], 'threshold': best[2], 'left_recipe': best[3], 'right_recipe': best[4], 'training_loss': best[0]}


def aggregate(rows):
    out = {}
    for method in sorted({r['method'] for r in rows}):
        rr = [r for r in rows if r['method'] == method]
        good = [r for r in rr if r['original_qualified']]
        out[method] = {'contexts': len(rr), 'known_choices': sum(r['actual_available'] for r in rr),
                       'qualified': len(good), 'failed': sum(r['original_qualified'] is False for r in rr),
                       'unknown': sum(r['original_qualified'] is None for r in rr),
                       'mean_delta_JF_qualified_N_s': float(np.mean([r['delta_JF_vs_B_N_s'] for r in good])) if good else None,
                       'mean_delta_JM_qualified_Nm_s': float(np.mean([r['delta_JM_vs_B_Nm_s'] for r in good])) if good else None,
                       'choices_vs_B': sum(r['choice_recipe_sha256'] != r['B_recipe_sha256'] for r in rr)}
    return out


def main():
    begin = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    data_path = P / 'data/HISTORICAL_RECIPE_DATASET_V2.json'
    assert sha(data_path) == DATA_SHA
    data = json.loads(data_path.read_text())
    source_rows = [r for r in data['rows'] if r.get('schema')]
    anchor = {r['id'].split('CFACTORH01_', 1)[1]: r for r in source_rows if r['group'] == 'CFACTORH01'}
    menu = [{'tag': tag, 'recipe_sha256': anchor[tag]['action_recipe_sha256'], 'action': anchor[tag]['action'], 'action_recipe': anchor[tag]['action_recipe']} for tag in TAGS]
    rows = [r for r in source_rows if r['action_recipe_sha256'] in {a['recipe_sha256'] for a in menu}]
    groups = sorted({r['group'] for r in rows})
    cv = []
    for heldout in groups:
        train = [r for r in rows if r['group'] != heldout]
        test = [r for r in rows if r['group'] == heldout]
        ctx = test[0]['context']
        b = next(r for r in test if r['action']['family'] == 'B')
        for name, (kind, dims) in VARIANTS.items():
            bundle = {'menu': menu, 'methods': {name: model(train, menu, kind, dims)}, 'primary_method': name, 'distance_limit': 3.}
            for objective in ['JF_QUALIFIED', 'STRICT_JM']:
                prediction = predict(bundle, ctx, name, objective)
                choice = prediction['choice_recipe_sha256'] or b['action_recipe_sha256']
                cv.append(result(heldout, name + '/' + objective, choice, test, {'prediction': prediction, 'B_fallback_after_abstain': prediction['choice_recipe_sha256'] is None}))
        cv.append(result(heldout, 'CONSTANT_B', b['action_recipe_sha256'], test))
        cv.append(result(heldout, 'BEST_FIXED_TRAIN', fixed_best(train, menu), test))
        tree = stump(train, menu)
        choice = tree['recipe'] if tree['kind'] == 'constant' else tree['left_recipe'] if ctx['features'][tree['feature_index']] <= tree['threshold'] else tree['right_recipe']
        cv.append(result(heldout, 'IF_STUMP_TRAIN', choice, test, tree))
        # 每动作取最近训练context；只使用训练结束后的真实反馈。
        normalizer = model(train, menu, 'DELTA_B', 25)
        z = transform(normalizer, to_context25(ctx))
        nearest = []
        for item in menu:
            tr = [r for r in train if r['action_recipe_sha256'] == item['recipe_sha256']]
            if not tr:
                continue
            n = min(tr, key=lambda r: float(np.mean((transform(normalizer, to_context25(r['context'])) - z) ** 2)))
            if n['eligible_for_success_ranking']:
                nearest.append((n['labels_evaluation_only']['delta_JF_vs_B_N_s'], item['tag'], item['recipe_sha256']))
        choice = min(nearest)[-1] if nearest else b['action_recipe_sha256']
        cv.append(result(heldout, 'NEAREST_CONTEXT', choice, test))
    ag = aggregate(cv)
    eligible = [n for n in ['ABS_25', 'DELTA_25', 'PAIR_25', 'STRONG_DELTA_25']]
    primary = min(eligible, key=lambda n: (ag[n + '/JF_QUALIFIED']['failed'] + ag[n + '/JF_QUALIFIED']['unknown'], ag[n + '/JF_QUALIFIED']['mean_delta_JF_qualified_N_s'] if ag[n + '/JF_QUALIFIED']['mean_delta_JF_qualified_N_s'] is not None else 1e6, eligible.index(n)))
    frozen = {'schema': 'v8.value_family_frozen.v1', 'frozen_unix': time.time(), 'data_sha256': DATA_SHA,
              'menu': menu, 'primary_method': primary, 'distance_limit': 3., 'methods': {name: model(rows, menu, kind, dims) for name, (kind, dims) in VARIANTS.items()},
              'strong_controls': {'best_fixed': fixed_best(rows, menu), 'if_stump': stump(rows, menu)},
              'train_contexts': groups, 'selection_rule': '开发整context失败/未知数最少，再比较合格均值JF；所有方法保留',
              'primary_objective': '原完整资格约束下JF；JM代价独立列出', 'strict_JM_separate': True,
              'test_outcomes_opened': False, 'new_physics': 0, 'physical_attempt_savings': 0,
              'risk_is_original_gate_or_calibrated_probability': False,
              'source_sha256': {n: sha(P / 'source' / n) for n in ['value_api.py', 'train_value_models.py']}}
    put('models/VALUE_FAMILY_V1_FROZEN.json', frozen)
    put('freeze/FIVE_ACTION_MENU_V1.json', {'schema': 'v8.value_five_action_menu.v1', 'menu': menu, 'anchor': 'CFACTORH01精确recipe；同tag异recipe不混用', 'source_data_sha256': DATA_SHA})
    put('analysis/OFFLINE_VALUE_CV_V1.json', {'schema': 'v8.offline_value_development_cv.v1', 'rows': cv, 'aggregate': ag, 'primary_method': primary, 'context_count': len(groups), 'training_rows': len(rows), 'train_groups': groups, 'independent_test': False, 'new_physics': 0, 'limitation': '全部历史暴露开发；6context无法支持广域个体化或概率校准；缺反事实不补；原资格只作训练标签和评价，不进入本次predict。'})
    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    put('analysis/TRAINING_RESOURCE_V1.json', {'wall_s': time.monotonic() - begin, 'cpu_user_s': end_usage.ru_utime - usage.ru_utime, 'cpu_system_s': end_usage.ru_stime - usage.ru_stime, 'peak_RSS_KiB': end_usage.ru_maxrss, 'single_thread_environment': {n: os.environ.get(n) for n in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'PYTHONDONTWRITEBYTECODE']}, 'python': os.sys.executable, 'numpy': np.__version__, 'new_physics': 0, 'new_native_steps': 0, 'full_bundle_sha256': sha(P / 'models/VALUE_FAMILY_V1_FROZEN.json'), 'fit_call_count': len(VARIANTS) * (len(groups) + 1) + len(groups), 'scope': '每fit含3个ridge矩阵求解、1个risk优化与2个pair优化；未称fresh rollout/TD/PPO。'})
    print(json.dumps({'primary': primary, 'aggregate': ag, 'bundle_sha256': sha(P / 'models/VALUE_FAMILY_V1_FROZEN.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
