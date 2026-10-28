"""A5 SOURCE_ONLY：只有批准runner可调用；11个logistic，0成本/margin拟合。"""
import copy
import time
from predict_api_v1 import transform, design

STOP = 1793114740.
SCALE_FLOOR = [.1] * 5 + [1.] * 2 + [.1] * 4 + [.005] * 4 + [.05] * 10 + [.005] * 8 + [1.] * 3 + [.1] * 3


def check(deadline):
    if time.time() >= min(deadline, STOP):
        raise TimeoutError('A5_ORIGINAL_GLOBAL_OR_LOCAL_STOP')


def normalization(old_train_rows, context_by_id, frozen_full_spec=None):
    """按旧A3 sorted parent/unique context统计；新2标签不改变任何norm。"""
    if frozen_full_spec is not None:
        return {k: copy.deepcopy(frozen_full_spec[k]) for k in ('indices', 'center', 'scale', 'numeric_constant_positions', 'numeric_zero_std_rule')}
    import numpy as np
    parents = sorted({r['old_parent_split_evaluation_only'] for r in old_train_rows})
    context_by_parent = {r['old_parent_split_evaluation_only']: context_by_id[r['id_evaluation_only']] for r in old_train_rows}
    # 与旧A3的fancy-index memory layout也一致，避免负对照受reduction次序干扰。
    X = np.asarray([context_by_parent[p]['features'] for p in parents])[:, list(range(39))]
    std = X.std(0)
    return {'indices': list(range(39)), 'center': X.mean(0).tolist(),
        'scale': np.maximum(std, SCALE_FLOOR).tolist(), 'numeric_constant_positions': np.flatnonzero(std <= 1e-12).tolist(),
        'numeric_zero_std_rule': 1e-12}


def fit_one(rows, menu, norm, context_by_id, ledger, deadline, scope):
    check(deadline)
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit
    indices = {m['recipe_sha256']: i for i, m in enumerate(menu)}
    history = [{'recipe_sha256': r['recipe_sha256'], 'z39': transform(norm, context_by_id[r['id_evaluation_only']]),
                'operational_qualified': r['operational_qualified_target_only'], 'old48': r['origin_evaluation_only'] == 'OLD48_FULL_TASK'} for r in rows]
    A = np.asarray([design(h['z39'], indices[h['recipe_sha256']], 5) for h in history], float)
    y = np.asarray([not h['operational_qualified'] for h in history], float)
    assert A.shape == (len(rows), 200) and np.isfinite(A).all() and np.isfinite(y).all()
    entry = {'kind': 'risk50_logistic_same_A3_objective', 'scope_evaluation_only': scope, 'rows': len(rows),
        'dimension': 200, 'regularization': .3, 'function_evaluations_observed': 0, 'completed': False,
        'objective_evaluations_completed': 0, 'logit_matvec_entry': 0, 'logit_matvec_completed': 0,
        'gradient_matvec_entry': 0, 'gradient_matvec_completed': 0,
        'initialization': 'EXACT_ZERO_200_NO_RNG', 'started_unix': time.time(), 'training_design_rows': len(rows)}
    ledger.append(entry)
    def objective(weights):
        check(deadline)
        if entry['function_evaluations_observed'] >= 1000:
            raise RuntimeError('A5_EXACT_FUNCTION_EVALUATION_BUDGET_EXHAUSTED_NO_RETRY')
        entry['function_evaluations_observed'] += 1
        entry['logit_matvec_entry'] += 1
        z = A @ weights
        entry['logit_matvec_completed'] += 1
        loss = float(np.mean(np.logaddexp(0, z) - y * z) + .15 * weights @ weights)
        entry['gradient_matvec_entry'] += 1
        gradient = A.T @ (expit(z) - y) / len(y) + .3 * weights
        entry['gradient_matvec_completed'] += 1
        entry['objective_evaluations_completed'] += 1
        return loss, gradient
    result = minimize(objective, np.zeros(200), jac=True, method='L-BFGS-B', options={'maxiter': 200, 'ftol': 1e-11})
    entry.update(success=bool(result.success), iterations=int(result.nit), nfev=int(result.nfev), njev=int(result.njev),
                 message=str(result.message), ended_unix=time.time())
    if not result.success and np.linalg.norm(result.jac) >= 1e-4:
        raise RuntimeError('A5_RISK50_OPTIMIZATION_FAILED_NO_RETRY:' + str(result.message))
    check(deadline)
    assert entry['objective_evaluations_completed'] == entry['function_evaluations_observed'] == int(result.nfev)
    entry['completed'] = True
    value = copy.deepcopy(norm)
    value.update(weights=result.x.tolist(), history50=[{k: v for k, v in h.items() if k != 'old48'} for h in history],
                 history48=[{k: v for k, v in h.items() if k != 'old48'} for h in history if h['old48']],
                 label_semantics='OPERATIONAL_COMPLETE_AND_ORIGINAL_QUALIFIED', calibrated=False)
    return value
