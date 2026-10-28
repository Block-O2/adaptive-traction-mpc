"""V7 source-only 精确凸终末 Q；NumPy 仅在获批 fit 调用后导入。"""
import copy
import math
from collections import Counter

METHODS = ('EXACT_CRITIC_GAIN1_EMPIRICAL_ROWS', 'EXACT_CRITIC_GAIN20_EMPIRICAL_ROWS', 'EXACT_CRITIC_GAIN1_CASE_ACTION_BALANCED')


def target(row, gain):
    assert gain in (1, 20) and row['complete'] is True and type(row['original_qualified']) is bool
    baseline = row['baseline']['JF_N_s']
    result = max(-.9, min(.9, gain*(baseline-row['JF_N_s'])/max(baseline, 1.))) if row['original_qualified'] else -1.
    if gain == 1: assert result == row['canonical_terminal_return']
    return result


def case_action_weights(rows):
    cases = {r['split_case_sha256_evaluation_only'] for r in rows}
    cells = {(r['split_case_sha256_evaluation_only'], r['action_index']) for r in rows}
    case_cells = Counter(case for case, action in cells)
    repeats = Counter((r['split_case_sha256_evaluation_only'], r['action_index']) for r in rows)
    return [1./len(cases)/case_cells[r['split_case_sha256_evaluation_only']]/repeats[(r['split_case_sha256_evaluation_only'],r['action_index'])] for r in rows]


def fit_three(rows, reference, *, approved_contract_sha256, source_manifest_sha256, counters, bounded):
    """每训练集恰好经验2RHS、balanced1RHS各一次；0actor/温度梯度。"""
    import numpy as np
    assert rows and len({r['attempt_id'] for r in rows}) == len(rows)
    norm = reference['actor']['normalization']; n = len(rows)
    X = np.asarray([[1.]+[(v-m)/s for v,m,s in zip(r['features'],norm['mean'],norm['scale'])] for r in rows], dtype=float)
    A = np.zeros((n,130), dtype=float)
    for i, row in enumerate(rows):
        assert type(row['action_index']) is int and row['action_index'] in range(5)
        A[i,row['action_index']*26:(row['action_index']+1)*26] = X[i]
    Y = np.asarray([[target(r,1),target(r,20)] for r in rows],dtype=float)
    balanced = np.asarray(case_action_weights(rows),dtype=float)
    assert abs(float(balanced.sum())-1.) <= 1e-12 and np.isfinite(A).all() and np.isfinite(Y).all()
    results = {}; diagnostics = []
    jobs = [('EMPIRICAL_ROWS', np.full(n,1./n), Y, METHODS[:2]),
            ('CASE_ACTION_BALANCED', balanced, Y[:,0:1], METHODS[2:])]
    for weighting, weights, y, mechanisms in jobs:
        bounded()
        gram = A.T@(weights[:,None]*A)+.001*np.eye(130)
        rhs = A.T@(weights[:,None]*y)
        counters['solve_attempts'] += 1; counters['scalar_rhs_attempts'] += y.shape[1]
        W = np.linalg.solve(gram,rhs)
        counters['solve_completed'] += 1
        counters['normal_equation_residual_products'] += 1
        residual = gram@W-rhs
        relative = float(np.max(np.abs(residual))/max(1.,float(np.max(np.abs(rhs)))))
        assert np.isfinite(W).all() and relative <= 1e-9, 'NORMAL_EQUATION_RESIDUAL'
        counters['training_matrix_prediction_calls'] += 1
        prediction = A@W
        counters['training_scalar_output_columns'] += y.shape[1]
        for j, mechanism in enumerate(mechanisms):
            w = W[:,j]; errors = prediction[:,j]-y[:,j]
            objective = float(.5*np.sum(weights*errors**2)+.0005*np.sum(w*w))
            model = {'schema':'v8.exact_terminal_critic_model.v7','mechanism':mechanism,
                     'feature_names':copy.deepcopy(reference['actor']['feature_names']),
                     'normalization':copy.deepcopy(norm),'action_contracts':copy.deepcopy(reference['actor']['action_contracts']),
                     'full_recipe_sha256':copy.deepcopy(reference['actor']['action_sha256']),
                     'weights':w.reshape(5,26).tolist(),'alpha':.01,'weight_decay':.001,
                     'terminal_only':True,'future_qualification_mask_used':False,
                     'support_policy':'UNRESTRICTED_SAME_AS_V6_VANILLA_NO_CURRENT_MASK',
                     'support_radius_RMS':1.,'support_count_unit':'DISTINCT_TRAINING_CASE',
                     'support_records':[{'attempt_id':r['attempt_id'],'normalized_features':X[i,1:].tolist(),
                                         'action_index':r['action_index'],'case_sha256':r['split_case_sha256_evaluation_only']} for i,r in enumerate(rows)],
                     'approved_contract_sha256':approved_contract_sha256,'source_manifest_sha256':source_manifest_sha256}
            results[mechanism]=model
            diagnostics.append({'mechanism':mechanism,'weighting':weighting,'train_rows':n,
                                'normal_equation_relative_max_residual':relative,
                                'regularized_train_objective_own_target':objective,
                                'canonical_gain1_empirical_data_MSE':float(np.mean((prediction[:,j]-Y[:,0])**2)),
                                'canonical_gain1_balanced_data_MSE':float(np.sum(balanced*(prediction[:,j]-Y[:,0])**2)),
                                'weight_norm_squared':float(np.sum(w*w)),
                                'empirical_gain1_regularized_objective':float(.5*np.mean((prediction[:,j]-Y[:,0])**2)+.0005*np.sum(w*w)),
                                'solver_is_single_unique_optimum_not_twin_ensemble':True})
        bounded()
    return results,diagnostics


def archived_objectives(rows, archived_case_predictions, reference):
    """只对已归档 Q 数值加减乘除；不调用旧模型 forward。只用于 full。"""
    balanced = case_action_weights(rows); output=[]
    for gain, weighting in ((1,'EMPIRICAL_ROWS'),(20,'EMPIRICAL_ROWS'),(1,'CASE_ACTION_BALANCED')):
        weights = [1./len(rows)]*len(rows) if weighting=='EMPIRICAL_ROWS' else balanced
        for head in ('q1','q2'):
            key='Q1_terminal_return' if head=='q1' else 'Q2_terminal_return'
            errors=[archived_case_predictions[r['split_case_sha256_evaluation_only']][key][r['action_index']]-target(r,gain) for r in rows]
            penalty=.0005*sum(v*v for row in reference[head] for v in row)
            output.append({'old_model':'V6_VANILLA_FIXED_ENTROPY','head':head,'gain':gain,'weighting':weighting,
                           'regularized_full_objective_from_archived_predictions':.5*sum(w*e*e for w,e in zip(weights,errors))+penalty,
                           'regularizer_from_archived_full_weights':penalty,'old_model_new_forward_calls':0,
                           'scope':'FULL_ONLY; old fold train weights/predictions were not archived'})
    return output
