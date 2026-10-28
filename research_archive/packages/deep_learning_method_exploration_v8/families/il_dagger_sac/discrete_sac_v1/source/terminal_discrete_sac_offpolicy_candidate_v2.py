"""V2未执行：终末一步离散SAC兼容offpolicy replay候选；无I/O、env、进程或import时模型。

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
    return {'schema': 'v8.terminal_discrete_sac.model.v2', 'mechanism': mechanism, 'actor': copy.deepcopy(common_five_actor),
            'common_actor_parent_sha256': digest(common_five_actor), 'seed': seed, 'rng_state': rng.getstate(),
            'q1': small(), 'q2': small(), 'risk': zero(), 'JF': zero(), 'JM': zero(),
            'component_output_units': {'JF': 1500., 'JM': 100.},
            'log_alpha': math.log(.01), 'target_entropy': .5 * math.log(5),
            'source_sha256': module_source_sha256, 'approved_contract_sha256': approved_contract_sha256,
            'replay_manifest_sha256': None, 'support_records': [], 'version': 0,
            'configuration': {'actor_lr': .02, 'critic_lr': .01, 'risk_lr': .01, 'cost_lr': .01, 'alpha_lr': .005,
                              'gradient_norm_limit': 1., 'linear_weight_decay': .001, 'support_radius_RMS': 1., 'support_min_count': 2, 'support_count_unit': 'DISTINCT_TRAINING_CASE_NOT_REPEATED_ROLLOUT',
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
    cases = [set() for _ in range(5)]
    for r in model['support_records']:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(x[1:], r['normalized_features'])) / 25)
        if dist <= cfg['support_radius_RMS']:
            cases[r['action_index']].add(r['case_sha256'])
    return [len(values) for values in cases]


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
    """V2只接root已核原文件的两类offpolicy行；历史行为概率缺失保持None。"""
    _authorized(approved_contract_sha256)
    hashes=_actor_shape(expected_actor)
    _require(manifest.get('schema')=='v8.approved_terminal_sac_offpolicy_manifest.v2','V2_OFFPOLICY_MANIFEST_REQUIRED')
    _require(manifest.get('approved_contract_sha256')==approved_contract_sha256,'EXACT_FIT_APPROVAL_REQUIRED')
    _require(manifest.get('cohort') in ('AGGREGATE64','FRESH16') and manifest.get('split')=='DEVELOPMENT_ONLY','UNAPPROVED_COHORT_OR_SPLIT')
    _require(manifest.get('full_recipe_sha256')==hashes and manifest.get('original_file_builder_verified') is True,'MENU_OR_ORIGINAL_EVIDENCE_NOT_VERIFIED')
    _require(_sha(manifest.get('dataset_file_sha256')) and _sha(manifest.get('builder_manifest_file_sha256')),'MISSING_FROZEN_DATA_IDENTITY')
    whitelist=manifest['records_sha256'];ids=[r['attempt_id'] for r in records]
    _require(len(ids)==len(set(ids)) and set(ids)==set(whitelist) and records,'REAL_ATTEMPT_ACCOUNTING')
    out=[]
    for row in records:
        _require(digest(row)==whitelist[row['attempt_id']],'REPLAY_ROW_HASH_MISMATCH')
        _require(row.get('schema')=='v8.sac_terminal_offpolicy_replay_record.v2' and row.get('data_use_semantics')=='OFFPOLICY_TERMINAL_REPLAY','NO_RELABELED_ONPOLICY_SOURCE')
        origin=row.get('origin')
        _require(origin in ('GENUINE_PG_PHYSICAL_SAMPLE_NOW_REUSED_OFFPOLICY','AUDITED_HISTORICAL_PHYSICAL_TABLE_OFFPOLICY'),'UNKNOWN_SOURCE_COHORT')
        _require(manifest['cohort']!='FRESH16' or origin=='GENUINE_PG_PHYSICAL_SAMPLE_NOW_REUSED_OFFPOLICY','HISTORICAL_ROW_IN_FRESH_DIAGNOSTIC')
        _require(row.get('split')=='DEVELOPMENT_ONLY' and row.get('done') is True and row.get('next_state') is None,'TERMINAL_DEVELOPMENT_ONLY')
        _require(tuple(row['feature_names'])==FEATURE_NAMES and row.get('qa_validated') is True,'ONLY_CAUSAL_COMMISSION25_WITH_QA')
        _vector(row['features'],25)
        csha=digest({'names':row['feature_names'],'values':row['features']})
        _require(csha==row['causal_features_sha256'],'CAUSAL_FEATURE_IDENTITY')
        ai=row['action_index'];_require(type(ai) is int and ai in range(5),'ACTION_INDEX')
        _require(digest(row['full_recipe'])==row['full_recipe_sha256']==hashes[ai],'COMPLETE_RECIPE_IDENTITY')
        _require(_sha(row.get('split_case_sha256_evaluation_only')) and _sha(row.get('parent_fingerprint_evaluation_only')),'MISSING_CASE_PARENT_SPLIT')
        proof=row['original_evidence'];_require(proof['hard_safety'] is False and proof['ownership_PASS'] is True and proof['complete'] is True,'ENGINEERING_PARTIAL_UNKNOWN_HARD_SAFETY_EXCLUDED')
        for key in ('result_source_sha256','measured_source_sha256','actual_binding_sha256','native_ownership_sha256','applied_reference_receipt_stream_sha256','raw_container_sha256'):
            _require(_sha(proof.get(key)),'MISSING_ACTUAL_ORIGINAL_SHA:'+key)
        _require(type(proof.get('actual_new_native_steps')) is int and proof['actual_new_native_steps']>0,'NO_REAL_NATIVE_INCREMENT')
        for kind in ('START','END'):
            ev=proof['events_original_records_and_hash_scopes'][kind]
            _require(digest(ev['record'])==ev['canonical_record_sha256'] and _sha(ev['raw_line_without_newline_sha256']),'ORIGINAL_EVENT_HASH_SCOPE')
            _require(ev['record']['id']==row['attempt_id'] and ev['record']['event']==kind,'INDEPENDENT_EVENT_ID')
        _require(type(row.get('original_qualified')) is bool and row['complete'] is True,'ORIGINAL_COMPLETE_LABEL')
        _require(all(_number(row.get(k)) and row[k]>=0 and row[k]==proof[k] for k in ('JF_N_s','JM_Nm_s')),'FULL_PHYSICAL_COST')
        _require(row['original_qualified']==proof['original_qualified'] and row['failure']==float(not row['original_qualified']),'ORIGINAL_FAILURE_LABEL')
        base=row['baseline'];_require(base['complete'] is True and base['original_qualified'] is True and base['full_recipe_sha256']==hashes[0],'ORIGINAL_FULL_B')
        _require(base['parent_fingerprint']==row['parent_fingerprint_evaluation_only'] and base['causal_features_sha256']==csha and _sha(base['result_source_sha256']),'SAME_PARENT_B_IDENTITY')
        _require(all(_number(base.get(k)) and base[k]>=0 for k in ('JF_N_s','JM_Nm_s')),'BASELINE_FULL_COST')
        if origin=='AUDITED_HISTORICAL_PHYSICAL_TABLE_OFFPOLICY':
            _require(row['behavior'] is None and row['behavior_missing_not_fabricated'] is True,'HISTORICAL_BEHAVIOR_MUST_NOT_BE_INVENTED')
        else:
            behavior=row['behavior'];_require(_sha(behavior['policy_sha256']) and type(behavior['version']) is int and _number(behavior['old_logprob']),'FRESH_BEHAVIOR_PROVENANCE')
            _require(_sha(behavior['proposal_file_sha256']) and _sha(behavior['physical_receipt_file_sha256']),'FRESH_ACTUAL_PROPOSAL_RECEIPT')
        reward=max(-.9,min(.9,(base['JF_N_s']-row['JF_N_s'])/max(base['JF_N_s'],1.))) if row['original_qualified'] else -1.
        _require(reward==row['canonical_terminal_return'],'CANONICAL_GAIN1_REWARD_CHANGED')
        out.append({'attempt_id':row['attempt_id'],'features':list(row['features']),'action_index':ai,'canonical_terminal_return':reward,'failure':row['failure'],
                    'complete':True,'JF':row['JF_N_s'],'JM':row['JM_Nm_s'],'case_sha256':row['split_case_sha256_evaluation_only'],'source_record_sha256':whitelist[row['attempt_id']]})
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
    model['support_records'] = [{'attempt_id': r['attempt_id'], 'normalized_features': design(model['actor'], r['features'])[1:], 'action_index': r['action_index'], 'case_sha256': r['case_sha256']} for r in examples]
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
            'new_physical_attempts_generated': 0, 'data_semantics': 'AUDITED_HISTORICAL_OR_FRESH_SOURCE_USED_OFFPOLICY_TERMINAL',
            'no_future_qualification_mask': True}


def snapshot(model):
    body = copy.deepcopy(model)
    return {'schema': 'v8.terminal_sac.snapshot.v2', 'model': body, 'snapshot_sha256': digest(body),
            'automatic_training_or_physics': False}


def restore(saved, *, expected_source_sha256, expected_contract_sha256, expected_recipe_sha256):
    _require(saved.get('schema') == 'v8.terminal_sac.snapshot.v2' and digest(saved['model']) == saved['snapshot_sha256'], 'SNAPSHOT_CHECKSUM')
    body = saved['model']
    _require(body['source_sha256'] == expected_source_sha256 and body['approved_contract_sha256'] == expected_contract_sha256, 'RESTORE_SOURCE_OR_APPROVAL_CHANGED')
    _require(_actor_shape(body['actor']) == expected_recipe_sha256, 'RESTORE_FULL_RECIPE_CHANGED')
    return copy.deepcopy(body)
