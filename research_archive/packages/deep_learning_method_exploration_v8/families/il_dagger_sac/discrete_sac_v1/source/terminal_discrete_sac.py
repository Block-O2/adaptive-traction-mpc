"""未执行的终末一步离散SAC纯候选；无I/O、env、进程或import时模型。

只有主Agent批准具体数据/source/共同父合同后，才可调用初始化、predict或step。
Q target严格是完整单任务canonical return；没有next-state bootstrap。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import time
from datetime import datetime

HARD_DEADLINE_UNIX = datetime.fromisoformat('2026-10-27T15:25:40+00:00').timestamp()
MECHANISMS = ('VANILLA_FIXED_ENTROPY', 'ADAPTIVE_TEMPERATURE', 'CONSERVATIVE_SUPPORT')
BETA = ('a_inertia_combination', 'b_distal_inertia_combination', 'd_mass_length_com_combination', 'g1_proximal_gravity_combination', 'g2_distal_gravity_combination', 'k1_passive_stiffness', 'k2_passive_stiffness', 'rho1_stiffness_rest_combination', 'rho2_stiffness_rest_combination', 'bv1_viscous_damping', 'bv2_viscous_damping')
FEATURE_NAMES = tuple('estimated_beta_' + n for n in BETA) + tuple('estimated_geometry_' + n for n in ('hip_plane_x', 'hip_plane_z', 'thigh_length', 'knee_to_cuff_distance')) + tuple('residual_weight_' + j + '_' + n for j in ('hip', 'knee') for n in ('constant', 'q_hip_normalized', 'q_knee_normalized', 'dq_hip_bounded', 'dq_knee_bounded'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _require(test, reason):
    if not test:
        raise ValueError(reason)


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vector(values, size):
    _require(isinstance(values, (list, tuple)) and len(values) == size and all(_number(v) for v in values), 'NONFINITE_OR_WRONG_VECTOR')


def _authorized(approval_sha256):
    _require(_sha(approval_sha256), 'EXPLICIT_MAIN_APPROVED_CONTRACT_SHA_REQUIRED')
    _require(time.time() < HARD_DEADLINE_UNIX, 'ORIGINAL_GLOBAL_HARD_DEADLINE_REACHED')


def _recipes(policy):
    recipes = policy['action_contracts']
    hashes = [digest(a) for a in recipes]
    _require(len(recipes) == 5 and len(set(hashes)) == 5, 'EXACT_FIVE_UNIQUE_FULL_RECIPES_REQUIRED')
    _require(hashes == policy['action_sha256'], 'ACTUAL_RECIPE_BODY_VS_METADATA_MISMATCH')
    _require(recipes[0].get('action', {}).get('family') == 'B', 'FIRST_RECIPE_MUST_BE_ORIGINAL_B')
    return hashes


def _actor_shape(actor):
    _require(tuple(actor['feature_names']) == FEATURE_NAMES, 'ONLY_SCOPED_COMMISSIONING25')
    _vector(actor['normalization']['mean'], 25)
    _vector(actor['normalization']['scale'], 25)
    _require(all(v > 0 for v in actor['normalization']['scale']), 'NORMALIZATION_SCALE_NOT_POSITIVE')
    _require(len(actor['weights']) == 5, 'ACTOR_ACTION_COUNT')
    for row in actor['weights']:
        _vector(row, 26)
    return _recipes(actor)


def lift_bc_three_to_five(parent3, recipes5, *, approved_contract_sha256):
    """纯确定性共同父准备；调用仍需批准，当前未执行。"""
    _authorized(approved_contract_sha256)
    _require(tuple(parent3['feature_names']) == FEATURE_NAMES and len(parent3['weights']) == 3, 'BC3_PARENT_SCHEMA')
    _require(len(recipes5) == 5, 'FIVE_RECIPE_MENU_REQUIRED')
    parent_hashes = [digest(a) for a in parent3['action_contracts']]
    _require(parent_hashes == parent3['action_sha256'] == [digest(a) for a in recipes5[:3]], 'BC3_ACTUAL_RECIPE_IDENTITY')
    for row in parent3['weights']:
        _vector(row, 26)
    actor = {'feature_names': list(FEATURE_NAMES), 'normalization': copy.deepcopy(parent3['normalization']),
             'weights': copy.deepcopy(parent3['weights']), 'action_contracts': copy.deepcopy(recipes5),
             'action_sha256': [digest(a) for a in recipes5], 'version': 0,
             'initialization': {'kind': 'BC3_TO5_EXACT_LOGIT_LIFT', 'parent3_full_snapshot_sha256': digest(parent3),
                                'first_three_logits_unchanged': True, 'first_three_total_probabilities_unchanged': False}}
    average = [(a + b) / 2 for a, b in zip(parent3['weights'][1], parent3['weights'][2])]
    actor['weights'].extend([average.copy(), average.copy()])
    _actor_shape(actor)
    return actor


def initialize(common_five_actor, *, mechanism, seed, approved_contract_sha256, module_source_sha256):
    """定义将来的显式初始化入口；不从文件读取父模型或数据。"""
    _authorized(approved_contract_sha256)
    _require(mechanism in MECHANISMS and _sha(module_source_sha256), 'UNREGISTERED_MECHANISM_OR_SOURCE')
    _actor_shape(common_five_actor)
    rng = random.Random(seed)
    small = lambda: [[rng.uniform(-.001, .001) for _ in range(26)] for _ in range(5)]
    zero = lambda: [[0.] * 26 for _ in range(5)]
    return {'schema': 'v8.terminal_discrete_sac.model.v1', 'mechanism': mechanism, 'actor': copy.deepcopy(common_five_actor),
            'common_actor_parent_sha256': digest(common_five_actor), 'seed': seed, 'rng_state': rng.getstate(),
            'q1': small(), 'q2': small(), 'risk': zero(), 'JF': zero(), 'JM': zero(),
            'component_output_units': {'JF': 1500., 'JM': 100.},
            'log_alpha': math.log(.01), 'target_entropy': .5 * math.log(5),
            'source_sha256': module_source_sha256, 'approved_contract_sha256': approved_contract_sha256,
            'replay_manifest_sha256': None, 'support_records': [], 'version': 0,
            'configuration': {'actor_lr': .02, 'critic_lr': .01, 'risk_lr': .01, 'cost_lr': .01, 'alpha_lr': .005,
                              'gradient_norm_limit': 1., 'linear_weight_decay': .001, 'support_radius_RMS': 1., 'support_min_count': 2,
                              'alpha_min': 1e-4, 'alpha_max': 1., 'gamma': 1., 'terminal_only': True},
            'counters': {'parameter_steps': 0, 'q_gradient_examples': 0, 'risk_gradient_examples': 0, 'cost_gradient_examples': 0,
                         'actor_gradient_states': 0, 'alpha_gradient_steps': 0},
            'scope': 'ONE_TERMINAL_RECIPE_CONTEXTUAL_BANDIT; NOT old continuous SAC/DAgger or multi-step credit'}


def design(actor, values):
    _vector(values, 25)
    return [1.] + [(v - m) / s for v, m, s in zip(values, actor['normalization']['mean'], actor['normalization']['scale'])]


def linear(weights, x):
    return [sum(w * v for w, v in zip(row, x)) for row in weights]


def softmax(logits, allowed=None):
    allowed = list(range(len(logits))) if allowed is None else list(allowed)
    _require(allowed, 'NO_SUPPORTED_ACTION')
    maximum = max(logits[i] for i in allowed)
    exp = {i: math.exp(logits[i] - maximum) for i in allowed}
    total = sum(exp.values())
    return [exp.get(i, 0.) / total for i in range(len(logits))]


def entropy(probabilities):
    return -sum(p * math.log(p) for p in probabilities if p > 0)


def _sigmoid(value):
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


def support_counts(model, x):
    cfg = model['configuration']
    counts = [0] * 5
    for r in model['support_records']:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(x[1:], r['normalized_features'])) / 25)
        if dist <= cfg['support_radius_RMS']:
            counts[r['action_index']] += 1
    return counts


def _allowed(model, x):
    counts = support_counts(model, x)
    if model['mechanism'] == 'CONSERVATIVE_SUPPORT':
        return [i for i, c in enumerate(counts) if c >= model['configuration']['support_min_count']], counts
    return list(range(5)), counts


def predict(model, feature_names, commissioned25, *, qa_validated):
    """无当前结果输入的只读预测；risk只报告，不授予原资格。"""
    _actor_shape(model['actor'])
    _require(qa_validated is True and tuple(feature_names) == FEATURE_NAMES, 'CAUSAL_OUT0_QA_REQUIRED')
    x = design(model['actor'], commissioned25)
    q1, q2 = linear(model['q1'], x), linear(model['q2'], x)
    q = [min(a, b) for a, b in zip(q1, q2)]
    allowed, counts = _allowed(model, x)
    alpha = math.exp(model['log_alpha'])
    actor_logits = linear(model['actor']['weights'], x)
    raw_actor = softmax(actor_logits)
    actor = softmax(actor_logits, allowed) if allowed else [0.] * 5
    ideal_soft_q = softmax([v / alpha for v in q], allowed) if allowed else [0.] * 5
    choose = lambda a: max(allowed, key=lambda i: (a[i], -i)) if allowed else None
    index, greedy = choose(actor), choose(q)
    recipes = model['actor']['action_contracts']
    return {'schema': 'v8.terminal_sac_prediction.v1', 'mechanism': model['mechanism'], 'model_version': model['version'],
            'action_index': index, 'full_recipe_sha256': None if index is None else model['actor']['action_sha256'][index],
            'proposal_action': None if index is None else copy.deepcopy(recipes[index]['action']),
            'proposal_full_recipe': None if index is None else copy.deepcopy(recipes[index]),
            'actor_probabilities': actor, 'unrestricted_actor_probabilities': raw_actor,
            'direct_softmax_Q_probabilities': ideal_soft_q, 'direct_Q_greedy_index': greedy,
            'actor_vs_ideal_softQ_KL': sum(p * math.log(p / max(s, 1e-300)) for p, s in zip(actor, ideal_soft_q) if p > 0),
            'Q1_terminal_return': q1, 'Q2_terminal_return': q2, 'alpha': alpha,
            'risk_failure_scores_uncalibrated': [_sigmoid(v) for v in linear(model['risk'], x)],
            'JF_N_s_predictions': [v * model['component_output_units']['JF'] for v in linear(model['JF'], x)],
            'JM_Nm_s_predictions': [v * model['component_output_units']['JM'] for v in linear(model['JM'], x)],
            'support_counts': counts, 'allowed_from_past_replay_only': allowed,
            'reason': 'FROZEN_ACTOR_ARGMAX' if index is not None else 'ABSTAIN_NO_PAST_REPLAY_SUPPORT',
            'future_qualification_mask_used': False, 'original_qualification_granted': False,
            'operation_counts': {'actor_forward': 1, 'Q_forward': 2, 'risk_forward': 1, 'cost_forward': 2}}


def admit_replay(records, manifest, *, expected_actor, approved_contract_sha256):
    """主owner先核真实原始文件；此处再验冻结行白名单，不读取任何路径。"""
    _authorized(approved_contract_sha256)
    action_hashes = _actor_shape(expected_actor)
    _require(manifest.get('schema') == 'v8.main_owner_terminal_sac_replay_manifest.v1', 'WRONG_REPLAY_MANIFEST')
    _require(manifest.get('approved_contract_sha256') == approved_contract_sha256, 'REPLAY_APPROVAL_IDENTITY')
    _require(manifest.get('producer') == 'MAIN_AGENT_PHYSICS_OWNER' and manifest.get('source_experiment') == 'B_ONPOLICY_V1', 'ONLY_NEW_COMPATIBLE_MAIN_OWNER_REPLAY')
    _require(manifest.get('split') == 'DEVELOPMENT_ONLY' and manifest.get('raw_receipt_adapter_verified') is True, 'DEVELOPMENT_AND_RAW_ADAPTER_PROOF_REQUIRED')
    _require(manifest.get('recipe_sha256') == action_hashes, 'REPLAY_FIVE_RECIPE_IDENTITY')
    whitelist = manifest['records_sha256']
    ids = [r['attempt_id'] for r in records]
    _require(len(ids) == len(set(ids)) and set(ids) == set(whitelist), 'DUPLICATE_OR_MISSING_REAL_ATTEMPT')
    excluded = manifest.get('excluded_attempts')
    _require(isinstance(excluded, list) and all(r.get('reason') for r in excluded), 'EXPLICIT_ENGINEERING_EXCLUSION_LEDGER_REQUIRED')
    excluded_ids = [r['attempt_id'] for r in excluded]
    _require(not set(ids) & set(excluded_ids) and len(excluded_ids) == len(set(excluded_ids)), 'ADMITTED_EXCLUDED_OVERLAP')
    _require(set(manifest['source_attempt_ids']) == set(ids) | set(excluded_ids), 'SOURCE_ATTEMPT_ACCOUNTING_NOT_CLOSED')
    out = []
    for row in records:
        _require(digest(row) == whitelist[row['attempt_id']], 'REPLAY_ROW_HASH_MISMATCH')
        _require(row.get('schema') == 'v8.sac_terminal_replay_record.v1' and row.get('source_data_semantics') == 'FRESH_ON_POLICY_PHYSICAL_ROLLOUT', 'OLD_OR_INCOMPATIBLE_SOURCE_DATA')
        _require(row.get('split') == 'DEVELOPMENT_ONLY' and row.get('source_experiment') == 'B_ONPOLICY_V1', 'HELDOUT_OR_UNKNOWN_REPLAY_SOURCE')
        _require(row.get('done') is True and row.get('next_state') is None, 'ONLY_GENUINE_TERMINAL_ONE_STEP_DATA')
        _require(tuple(row['feature_names']) == FEATURE_NAMES, 'REPLAY_CONTEXT_SCHEMA')
        _vector(row['features'], 25)
        context_sha = digest({'names': row['feature_names'], 'values': row['features']})
        _require(context_sha == row['causal_features_sha256'] and row.get('qa_validated') is True, 'REPLAY_CAUSAL_CONTEXT_IDENTITY')
        action = row['action_index']
        _require(isinstance(action, int) and not isinstance(action, bool) and 0 <= action < 5, 'REPLAY_ACTION_INDEX')
        _require(digest(row['full_recipe']) == row['full_recipe_sha256'] == action_hashes[action], 'REPLAY_ACTUAL_RECIPE_BODY_IDENTITY')
        _require(_sha(row.get('behavior_policy_sha256')) and isinstance(row.get('behavior_policy_version'), int) and _number(row.get('old_logprob')), 'BEHAVIOR_PROVENANCE_MISSING')
        receipt = row['physical_receipt']
        _require(receipt.get('true_hard_safety_violation') is not True, 'HARD_SAFETY_STOP')
        _require(receipt.get('true_hard_safety_violation') is False, 'SAFETY_EVIDENCE_MISSING')
        _require(receipt.get('genuine_new_physical_attempt') is True and receipt.get('historical_or_cached_outcome') is False, 'NOT_NEW_PHYSICAL_REPLAY')
        _require(receipt.get('engineering_complete') is True and receipt.get('ownership_and_causality_audit_pass') is True, 'ENGINEERING_FAILURE_MUST_BE_EXCLUDED_NOT_REWARDED')
        steps = receipt.get('actual_new_native_steps')
        _require(isinstance(steps, int) and not isinstance(steps, bool) and steps > 0, 'NO_REAL_NEW_NATIVE_STEPS')
        for key in ('attempt_start_sha256', 'attempt_end_sha256', 'result_source_sha256', 'native_ownership_sha256', 'applied_reference_receipt_stream_sha256'):
            _require(_sha(receipt.get(key)), 'MISSING_RAW_PHYSICAL_IDENTITY:' + key)
        _require(isinstance(receipt.get('complete'), bool) and isinstance(receipt.get('original_qualified'), bool), 'ORIGINAL_QUALIFICATION_MISSING')
        _require(receipt['complete'] or receipt.get('protected_task_failure') is True, 'PARTIAL_IS_NOT_PROTECTED_TASK_FAILURE')
        _require(receipt['complete'] or not receipt['original_qualified'], 'INCOMPLETE_CANNOT_BE_ORIGINALLY_QUALIFIED')
        base = row['baseline']
        _require(base.get('complete') is True and base.get('original_qualified') is True and _sha(base.get('result_source_sha256')), 'FULL_QUALIFIED_REAL_B_REQUIRED')
        _require(base.get('full_recipe_sha256') == action_hashes[0], 'BASELINE_NOT_EXACT_ORIGINAL_B_RECIPE')
        _require(base.get('causal_features_sha256') == context_sha and base.get('parent_fingerprint') == row.get('parent_fingerprint') and _sha(row.get('parent_fingerprint')), 'BASELINE_NOT_SAME_ACTUAL_CONTEXT_PARENT')
        _require(all(_number(base.get(k)) and base[k] >= 0 for k in ('JF_N_s', 'JM_Nm_s')), 'BAD_BASELINE_PHYSICAL_COST')
        if receipt['complete']:
            _require(all(_number(receipt.get(k)) and receipt[k] >= 0 for k in ('JF_N_s', 'JM_Nm_s')), 'BAD_COMPLETE_PHYSICAL_COST')
        reward = max(-.9, min(.9, (base['JF_N_s'] - receipt['JF_N_s']) / max(base['JF_N_s'], 1.))) if receipt['complete'] and receipt['original_qualified'] else -1.
        out.append({'attempt_id': row['attempt_id'], 'features': list(row['features']), 'action_index': action,
                    'canonical_terminal_return': reward, 'failure': float(not receipt['original_qualified']),
                    'complete': receipt['complete'], 'JF': receipt.get('JF_N_s') if receipt['complete'] else None,
                    'JM': receipt.get('JM_Nm_s') if receipt['complete'] else None, 'source_record_sha256': whitelist[row['attempt_id']]})
    _require(out, 'EMPTY_REAL_REPLAY')
    return out


def _apply(weights, gradient, *, lr, limit, decay):
    combined = [[g + decay * w for g, w in zip(gr, wr)] for gr, wr in zip(gradient, weights)]
    norm = math.sqrt(sum(v * v for row in combined for v in row))
    _require(math.isfinite(norm), 'NONFINITE_GRADIENT_ABORT_WITHOUT_COMMIT')
    scale = min(1., limit / max(norm, 1e-300))
    for i, row in enumerate(combined):
        for j, value in enumerate(row):
            weights[i][j] -= lr * scale * value
    return {'gradient_norm': norm, 'gradient_scale': scale}


def step(model, records, manifest, *, approved_contract_sha256):
    """一次全replay梯度步，不能自动调度；当前未执行。"""
    _authorized(approved_contract_sha256)
    _require(model['approved_contract_sha256'] == approved_contract_sha256, 'MODEL_TRAINING_APPROVAL_MISMATCH')
    original_model, model = model, copy.deepcopy(model)  # 全部数值成功后才提交。
    examples = admit_replay(records, manifest, expected_actor=model['actor'], approved_contract_sha256=approved_contract_sha256)
    manifest_sha = digest(manifest)
    _require(model['replay_manifest_sha256'] in (None, manifest_sha), 'NEW_REPLAY_REQUIRES_NEW_EXPLICIT_CONTRACT')
    model['replay_manifest_sha256'] = manifest_sha
    model['support_records'] = [{'attempt_id': r['attempt_id'], 'normalized_features': design(model['actor'], r['features'])[1:], 'action_index': r['action_index']} for r in examples]
    zero = lambda: [[0.] * 26 for _ in range(5)]
    gradients = {k: zero() for k in ('q1', 'q2', 'risk', 'JF', 'JM', 'actor')}
    losses = {k: 0. for k in ('q1', 'q2', 'risk', 'JF', 'JM', 'actor')}
    n = len(examples)
    full_count = sum(r['complete'] for r in examples)
    actor_states, entropies = 0, []
    alpha = math.exp(model['log_alpha'])
    for row in examples:
        x, action = design(model['actor'], row['features']), row['action_index']
        q1, q2 = linear(model['q1'], x), linear(model['q2'], x)
        target = row['canonical_terminal_return']  # done=True: y=r，无bootstrap或额外终末熵。
        for head, q in (('q1', q1), ('q2', q2)):
            error = q[action] - target
            losses[head] += .5 * error ** 2 / n
            for j, value in enumerate(x): gradients[head][action][j] += error * value / n
        risk_logit = linear(model['risk'], x)[action]
        risk = _sigmoid(risk_logit)
        losses['risk'] += (max(risk_logit, 0.) + math.log1p(math.exp(-abs(risk_logit))) - row['failure'] * risk_logit) / n
        for j, value in enumerate(x): gradients['risk'][action][j] += (risk - row['failure']) * value / n
        if row['complete']:
            for head in ('JF', 'JM'):
                # 固定量纲缩放只影响数值优化，不混合两个物理目标。
                units = model['component_output_units'][head]
                error = linear(model[head], x)[action] - row[head] / units
                losses[head] += .5 * error ** 2 / max(full_count, 1)
                for j, value in enumerate(x): gradients[head][action][j] += error * value / max(full_count, 1)
        allowed, _ = _allowed(model, x)
        if not allowed:
            continue
        actor_states += 1
        pi = softmax(linear(model['actor']['weights'], x), allowed)
        inside = [alpha * math.log(max(pi[i], 1e-300)) - min(q1[i], q2[i]) for i in range(5)]
        mean_inside = sum(pi[i] * inside[i] for i in range(5))
        losses['actor'] += mean_inside
        entropies.append(entropy(pi))
        # 精确categorical梯度，Q/alpha stop-gradient；unsupported pi=0不参与。
        for i in allowed:
            coefficient = pi[i] * (inside[i] - mean_inside)
            for j, value in enumerate(x): gradients['actor'][i][j] += coefficient * value
    cfg = model['configuration']
    for row in gradients['actor']:
        for j in range(26): row[j] /= max(actor_states, 1)
    losses['actor'] /= max(actor_states, 1)
    metrics = {}
    for head in ('q1', 'q2', 'risk', 'JF', 'JM', 'actor'):
        if head in ('JF', 'JM') and full_count == 0 or head == 'actor' and actor_states == 0:
            metrics[head] = {'skipped_no_valid_examples': True}
            continue
        weights = model['actor']['weights'] if head == 'actor' else model[head]
        lr = cfg['actor_lr'] if head == 'actor' else cfg['risk_lr'] if head == 'risk' else cfg['cost_lr'] if head in ('JF', 'JM') else cfg['critic_lr']
        metrics[head] = _apply(weights, gradients[head], lr=lr, limit=cfg['gradient_norm_limit'], decay=0. if head == 'actor' else cfg['linear_weight_decay'])
    alpha_gradient = None
    if model['mechanism'] == 'ADAPTIVE_TEMPERATURE' and entropies:
        # J(alpha)=alpha*(H(pi)-Htarget)，对log-alpha求导；低熵增加alpha。
        alpha_gradient = alpha * (sum(entropies) / len(entropies) - model['target_entropy'])
        model['log_alpha'] = max(math.log(cfg['alpha_min']), min(math.log(cfg['alpha_max']), model['log_alpha'] - cfg['alpha_lr'] * alpha_gradient))
        model['counters']['alpha_gradient_steps'] += 1
    model['version'] += 1
    model['actor']['version'] += 1
    model['counters']['parameter_steps'] += 1
    model['counters']['q_gradient_examples'] += 2 * n
    model['counters']['risk_gradient_examples'] += n
    model['counters']['cost_gradient_examples'] += 2 * full_count
    model['counters']['actor_gradient_states'] += actor_states
    _authorized(approved_contract_sha256)
    original_model.clear()
    original_model.update(model)
    return {'version': model['version'], 'terminal_targets': [r['canonical_terminal_return'] for r in examples],
            'losses': losses, 'gradient_metrics': metrics, 'actor_states': actor_states,
            'mean_entropy': sum(entropies) / len(entropies) if entropies else None,
            'alpha_before': alpha, 'alpha_after': math.exp(model['log_alpha']), 'log_alpha_gradient': alpha_gradient,
            'replay_manifest_sha256': manifest_sha, 'counters': copy.deepcopy(model['counters']),
            'new_physical_attempts_generated': 0, 'data_semantics': 'GENUINE_NEW_PHYSICAL_OFFPOLICY_REPLAY_TERMINAL',
            'no_future_qualification_mask': True}


def snapshot(model):
    body = copy.deepcopy(model)
    return {'schema': 'v8.terminal_sac.snapshot.v1', 'model': body, 'snapshot_sha256': digest(body),
            'automatic_training_or_physics': False}


def restore(saved, *, expected_source_sha256, expected_contract_sha256, expected_recipe_sha256):
    _require(saved.get('schema') == 'v8.terminal_sac.snapshot.v1' and digest(saved['model']) == saved['snapshot_sha256'], 'SNAPSHOT_CHECKSUM')
    body = saved['model']
    _require(body['source_sha256'] == expected_source_sha256 and body['approved_contract_sha256'] == expected_contract_sha256, 'RESTORE_SOURCE_OR_APPROVAL_CHANGED')
    _require(_actor_shape(body['actor']) == expected_recipe_sha256, 'RESTORE_FULL_RECIPE_CHANGED')
    return copy.deepcopy(body)
