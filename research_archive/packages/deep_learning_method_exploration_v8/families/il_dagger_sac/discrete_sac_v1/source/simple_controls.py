"""相同未来真实replay的常数/if/nearest对照候选；当前未调用fit。"""
import copy
import math
from terminal_discrete_sac import _authorized, _actor_shape, _require, admit_replay, design, digest


def fit(records, manifest, *, common_actor, approved_contract_sha256):
    _authorized(approved_contract_sha256)
    examples = admit_replay(records, manifest, expected_actor=common_actor, approved_contract_sha256=approved_contract_sha256)
    contexts = {}
    for r in examples:
        key = digest(r['features'])
        contexts.setdefault(key, {'features': r['features'], 'rows': []})['rows'].append(r)

    def best_fixed(keys):
        """仅在训练叶每个数值context有实际支持的动作中选均值return。"""
        options = []
        for a in range(5):
            means = []
            for key in keys:
                vals = [r['canonical_terminal_return'] for r in contexts[key]['rows'] if r['action_index'] == a]
                if not vals:
                    break
                means.append(sum(vals) / len(vals))
            if len(means) == len(keys):
                options.append((sum(means) / len(means), -a, a))
        return max(options)[-1] if options else 0

    keys = sorted(contexts)
    fixed = best_fixed(keys)
    candidates = []
    for j in range(25):
        values = sorted({contexts[k]['features'][j] for k in keys})
        for lo, hi in zip(values, values[1:]):
            threshold = (lo + hi) / 2
            left = [k for k in keys if contexts[k]['features'][j] <= threshold]
            right = [k for k in keys if k not in left]
            arms = {True: best_fixed(left), False: best_fixed(right)}
            scored = []
            valid = True
            for k in keys:
                a = arms[contexts[k]['features'][j] <= threshold]
                vals = [r['canonical_terminal_return'] for r in contexts[k]['rows'] if r['action_index'] == a]
                if not vals:
                    valid = False
                    break
                scored.append(sum(vals) / len(vals))
            if valid:
                candidates.append((sum(scored) / len(scored), -j, -threshold, arms[True], arms[False]))
    tree = {'kind': 'CONSTANT', 'action_index': fixed}
    if candidates:
        _, jj, tt, left, right = max(candidates)
        tree = {'kind': 'IF', 'feature_index': -jj, 'threshold': -tt, 'left_action_index': left, 'right_action_index': right}
    return {'schema': 'v8.terminal_replay_simple_controls.v1', 'actor_identity_only': copy.deepcopy(common_actor),
            'best_fixed_action_index': fixed, 'if_stump': tree,
            'contexts': [{'features': contexts[k]['features'], 'normalized_features': design(common_actor, contexts[k]['features'])[1:],
                          'best_observed_action_index': best_fixed([k]), 'numeric_context_sha256': k} for k in keys],
            'training_replay_manifest_sha256': digest(manifest),
            'scope': '同真实replay；缺action×context不补；开发if可能记忆，不能称已泛化'}


def predict(bundle, feature_names, values, *, control, qa_validated):
    actor = bundle['actor_identity_only']
    _actor_shape(actor)
    _require(qa_validated is True and list(feature_names) == actor['feature_names'], 'CAUSAL_CONTEXT_QA')
    x = design(actor, values)
    if control == 'CONSTANT_B':
        action = 0
    elif control == 'BEST_FIXED':
        action = bundle['best_fixed_action_index']
    elif control == 'IF_STUMP':
        tree = bundle['if_stump']
        action = tree['action_index'] if tree['kind'] == 'CONSTANT' else tree['left_action_index'] if values[tree['feature_index']] <= tree['threshold'] else tree['right_action_index']
    elif control == 'NEAREST_CONTEXT':
        nearest = min(bundle['contexts'], key=lambda r: (sum((a - b) ** 2 for a, b in zip(x[1:], r['normalized_features'])), r['numeric_context_sha256']))
        action = nearest['best_observed_action_index']
    else:
        raise ValueError('UNKNOWN_SIMPLE_CONTROL')
    recipe = actor['action_contracts'][action]
    return {'control': control, 'action_index': action, 'full_recipe_sha256': digest(recipe),
            'proposal_action': copy.deepcopy(recipe['action']), 'proposal_full_recipe': copy.deepcopy(recipe),
            'future_qualification_mask_used': False, 'original_qualification_granted': False}
