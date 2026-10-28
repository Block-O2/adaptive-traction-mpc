"""A2 pure fit 候选：调用会拟合，未经主 Agent 另行批准禁止运行。"""
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from causal_api import FEATURE_NAMES, to_context25
from predict_api import design, transform

HARD_DEADLINE = 1793114740.
SCALE_FLOOR = [.1] * 5 + [1.] * 2 + [.1] * 4 + [.005] * 4 + [.05] * 10
OBJECTIVES = ['JF_QUALIFIED', 'JM_QUALIFIED', 'STRICT_JM']


def check(deadline):
    if time.time() >= min(deadline, HARD_DEADLINE):
        raise TimeoutError('A2_ORIGINAL_GLOBAL_OR_LOCAL_DEADLINE')


def logistic(A, y, ledger, deadline):
    check(deadline)
    entry = {'kind': 'qualification_risk_logistic', 'rows': len(y), 'dimension': A.shape[1], 'regularization': .3, 'function_evaluations_observed': 0}
    ledger.append(entry)
    def objective(weights):
        check(deadline)
        entry['function_evaluations_observed'] += 1
        z = A @ weights
        return float(np.mean(np.logaddexp(0, z) - y * z) + .15 * weights @ weights), A.T @ (expit(z) - y) / len(y) + .3 * weights
    result = minimize(objective, np.zeros(A.shape[1]), jac=True, method='L-BFGS-B', options={'maxiter': 200, 'ftol': 1e-11})
    entry.update({'success': bool(result.success), 'iterations': int(result.nit), 'nfev': int(result.nfev), 'njev': int(result.njev), 'message': str(result.message)})
    if not result.success and np.linalg.norm(result.jac) >= 1e-4:
        raise RuntimeError('A2_RISK_OPTIMIZATION_FAILED:' + str(result.message))
    return result.x.tolist()


def model(rows, menu, dimensions, ledger, deadline):
    """复用 V1 action×context ridge + 独立 logistic；无PPO/TD/物理。"""
    check(deadline)
    groups = sorted({r['split_parent_group_evaluation_only'] for r in rows})
    contexts = {r['split_parent_group_evaluation_only']: to_context25(r['context']) for r in rows}
    indices = list(range(dimensions))
    X = np.asarray([contexts[g]['features'] for g in groups])[:, indices]
    center = X.mean(0)
    scale = np.maximum(X.std(0), np.asarray(SCALE_FLOOR)[indices])
    spec = {'indices': indices, 'center': center.tolist(), 'scale': scale.tolist(), 'train_parent_groups': groups,
            'cost_heads': {}, 'fit_rows': len(rows), 'risk_rows': len(rows), 'risk_is_calibrated': False}
    zs = {g: transform(spec, c) for g, c in contexts.items()}
    action_index = {m['recipe_sha256']: i for i, m in enumerate(menu)}
    A = np.asarray([design(zs[r['split_parent_group_evaluation_only']], action_index[r['action_recipe_sha256']], len(menu)) for r in rows])
    risk = np.asarray([not r['labels_evaluation_only']['original_qualified'] for r in rows], float)
    spec['risk_weights'] = logistic(A, risk, ledger, deadline)
    spec['support_train_z'] = [[zs[r['split_parent_group_evaluation_only']] for r in rows if action_index[r['action_recipe_sha256']] == i] for i in range(len(menu))]
    for kind in ['ABS', 'DELTA_B']:
        keys = ['JF_N_s', 'JM_Nm_s'] if kind == 'ABS' else ['delta_JF_vs_B_N_s', 'delta_JM_vs_B_Nm_s']
        Y = np.asarray([[r['labels_evaluation_only'][key] for key in keys] for r in rows], float)
        target_center = Y.mean(0)
        target_scale = np.maximum(Y.std(0), [.02, .01])
        norm = (Y - target_center) / target_scale
        weights = []
        for penalty in [.1, 1., 10.]:
            check(deadline)
            ledger.append({'kind': 'independent_JF_JM_ridge_two_RHS', 'target': kind, 'regularization': penalty, 'rows': len(rows), 'dimension': A.shape[1], 'scalar_output_heads': 2})
            weights.append(np.linalg.solve(A.T @ A + penalty * np.eye(A.shape[1]), A.T @ norm).tolist())
        spec['cost_heads'][kind] = {'target_center': target_center.tolist(), 'target_scale': target_scale.tolist(), 'weights': weights}
    return spec


def historical_admissible(row, objective):
    labels = row['labels_evaluation_only']
    return labels['complete'] and labels['original_qualified'] and (objective != 'STRICT_JM' or labels['delta_JM_vs_B_Nm_s'] <= 1e-12)


def component(row, objective):
    return row['labels_evaluation_only']['delta_JM_vs_B_Nm_s' if objective == 'JM_QUALIFIED' else 'delta_JF_vs_B_N_s']


def fixed_best(rows, menu, objective):
    groups = {r['split_parent_group_evaluation_only'] for r in rows}
    options = []
    for item in menu:
        use = [r for r in rows if r['action_recipe_sha256'] == item['recipe_sha256']]
        valid = [r for r in use if historical_admissible(r, objective)]
        options.append((len(groups) - len(valid), float(np.mean([component(r, objective) for r in valid])) if valid else 1e6, item['tag'], item['recipe_sha256']))
    return min(options)[-1]


def stump(rows, menu, objective, deadline):
    contexts = {r['split_parent_group_evaluation_only']: r['context']['features'] for r in rows}
    fixed = fixed_best(rows, menu, objective)
    best = None
    for feature in range(25):
        check(deadline)
        values = sorted({x[feature] for x in contexts.values()})
        for lo, hi in zip(values, values[1:]):
            threshold = (lo + hi) / 2
            left_rows = [r for r in rows if contexts[r['split_parent_group_evaluation_only']][feature] <= threshold]
            right_rows = [r for r in rows if contexts[r['split_parent_group_evaluation_only']][feature] > threshold]
            left, right = fixed_best(left_rows, menu, objective), fixed_best(right_rows, menu, objective)
            failures, cost = 0, []
            for group, x in contexts.items():
                choice = left if x[feature] <= threshold else right
                found = next((r for r in rows if r['split_parent_group_evaluation_only'] == group and r['action_recipe_sha256'] == choice), None)
                if found is None or not historical_admissible(found, objective):
                    failures += 1
                else:
                    cost.append(component(found, objective))
            candidate = ((failures, float(np.mean(cost)) if cost else 1e6), feature, threshold, left, right)
            if best is None or candidate < best:
                best = candidate
    return {'kind': 'constant', 'recipe': fixed} if best is None else {'kind': 'if', 'feature_index': best[1], 'feature_name': FEATURE_NAMES[best[1]], 'threshold': best[2], 'left_recipe': best[3], 'right_recipe': best[4], 'training_loss': best[0]}


def controls(rows, menu, normalizer, deadline):
    out = {}
    for objective in OBJECTIVES:
        check(deadline)
        out[objective] = {'best_fixed': fixed_best(rows, menu, objective), 'if_stump': stump(rows, menu, objective, deadline),
            'past_feedback': [{'recipe_sha256': r['action_recipe_sha256'], 'training_context': r['split_parent_group_evaluation_only'],
                'normalized_context': transform(normalizer, to_context25(r['context'])), 'admissible': historical_admissible(r, objective),
                'component_delta': component(r, objective)} for r in rows]}
    return out
