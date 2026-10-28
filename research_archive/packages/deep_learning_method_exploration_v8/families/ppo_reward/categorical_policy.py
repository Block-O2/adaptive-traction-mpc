"""One-decision recipe policy. Pure Python; importing this file never trains.

The runner owns physical dispatch and source/RNG/attempt ledgers. Historical
full-menu optimization MUST use OFFLINE_TABLE_POLICY_OPTIMIZATION. Genuine new
on-policy records use FRESH_ON_POLICY_PHYSICAL_ROLLOUT and bind policy_sha256.
This is a new episode-level policy representation, not the old 41D actor.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random


OFFLINE = "OFFLINE_TABLE_POLICY_OPTIMIZATION"
ON_POLICY = "FRESH_ON_POLICY_PHYSICAL_ROLLOUT"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _finite_vector(values, size):
    if len(values) != size or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in values):
        raise ValueError("FEATURE_SHAPE_OR_NONFINITE")


def initialize(action_contracts, feature_names, *, seed=0, normalization=None):
    """Create a uniform policy without fitting or reading any data.

    Normalization is externally frozen from training contexts only. No case IDs,
    future labels, parent IDs or paths may be included in feature_names.
    """
    if len(action_contracts) < 2 or len(set(feature_names)) != len(feature_names):
        raise ValueError("INVALID_ACTION_OR_FEATURE_SCHEMA")
    forbidden = ("case_id", "case_key", "case_path", "truth", "future", "outcome", "pass_fail", "path", "hash", "parent", "final_jf", "final_jm")
    if any(any(s in name.lower() for s in forbidden) for name in feature_names):
        raise ValueError("FORBIDDEN_ACTOR_FEATURE_NAME")
    dim = len(feature_names)
    if normalization is None:
        normalization = {"mean": [0.0] * dim, "scale": [1.0] * dim, "fit_scope": "NO_FIT_IDENTITY"}
    _finite_vector(normalization["mean"], dim)
    _finite_vector(normalization["scale"], dim)
    if not all(s > 0 for s in normalization["scale"]):
        raise ValueError("NONPOSITIVE_NORMALIZATION_SCALE")
    return {"schema": "ihear.episode_categorical.v1", "seed": seed, "version": 0,
            "action_contracts": copy.deepcopy(action_contracts),
            "action_sha256": [digest(a) for a in action_contracts],
            "feature_names": list(feature_names), "normalization": copy.deepcopy(normalization),
            "weights": [[0.0] * (dim + 1) for _ in action_contracts],
            "counters": {"forward": 0, "backward_equivalent": 0, "parameter_updates": 0},
            "training_data_semantics": "UNTRAINED_UNIFORM"}


def policy_sha256(policy):
    # Inference counters and run metadata do not change the behavior identity.
    fields = ("schema", "seed", "version", "action_sha256", "feature_names", "normalization", "weights")
    return digest({**{k: policy[k] for k in fields}, "representation": policy.get("representation", "linear_commissioned25")})


def design(policy, features):
    _finite_vector(features, len(policy["feature_names"]))
    if policy.get("representation") == "constant":
        return [1.0] + [0.0] * len(features)
    n = policy["normalization"]
    return [1.0] + [(v - m) / s for v, m, s in zip(features, n["mean"], n["scale"])]


def probabilities(policy, features):
    x = design(policy, features)
    logits = [sum(w * v for w, v in zip(row, x)) for row in policy["weights"]]
    maximum = max(logits)
    e = [math.exp(v - maximum) for v in logits]
    denom = sum(e)
    policy["counters"]["forward"] += 1
    return [v / denom for v in e]


def choose(policy, features, *, deterministic=True, rng=None, behavior_sha256=None):
    p = probabilities(policy, features)
    if deterministic:
        idx = max(range(len(p)), key=lambda i: (p[i], -i))
    else:
        if rng is None:
            raise ValueError("EXPLICIT_SAMPLING_RNG_REQUIRED")
        u = rng.random()
        idx = len(p) - 1
        for i, prob in enumerate(p):
            u -= prob
            if u <= 0:
                idx = i
                break
    return {"action_index": idx, "action_sha256": policy["action_sha256"][idx],
            "action": copy.deepcopy(policy["action_contracts"][idx]),
            "probabilities": p, "logprob": math.log(max(p[idx], 1e-300)),
            "policy_sha256": behavior_sha256 or policy_sha256(policy), "deterministic": deterministic}


def select_out0(policy, feature_names, commissioned_values, *, qa_validated):
    """Frozen deployment API; no paths, case IDs or outcomes are accepted.

    The runner supplies the unchanged scoped availability proof, then executes
    proposal_action via the original planner/scorer. This API never authorizes
    a physical run and never declares original qualification.
    """
    if qa_validated is not True or list(feature_names) != policy["feature_names"]:
        raise ValueError("OUT0_QA_OR_SCHEMA_INVALID")
    result = choose(policy, commissioned_values, deterministic=True)
    recipe = result["action"]
    return {**result, "proposal_action": copy.deepcopy(recipe["action"]),
            "full_recipe_sha256": digest(recipe),
            "resolved_base_candidate": copy.deepcopy(recipe["resolved_base_candidate"]),
            "original_qualification_granted": False}


def feedback(result, baseline, *, objective="JF", constraint_other_nonincrease=True):
    """Observed full-task feedback; never use this function before task completion.

    Values are bounded feasibility-gated relative improvement, not formal metrics.
    No weighted combination of physical objectives. qualification and motion must
    be original evaluator results; missing data remains missing and is rejected.
    Parent/runner must report all components independently even if reward=-1.
    """
    if objective not in ("JF", "JM"):
        raise ValueError("UNKNOWN_SINGLE_COMPONENT_OBJECTIVE")
    if baseline.get("qualified") is not True or baseline.get("complete") is not True:
        raise ValueError("BASELINE_NOT_ORIGINALLY_QUALIFIED")
    if result.get("complete") is not True or result.get("qualified") is not True:
        return {"reward": -1.0, "feasible": False, "reason": "INCOMPLETE_OR_ORIGINAL_QUALIFICATION_FAILURE", "partial_cost_not_ranked": True}
    other = "JM" if objective == "JF" else "JF"
    for row in (result, baseline):
        if any(k not in row or not math.isfinite(float(row[k])) for k in ("JF", "JM")):
            raise ValueError("MISSING_OR_NONFINITE_FULL_COST")
    feasible = not constraint_other_nonincrease or result[other] <= baseline[other]
    reward = max(-1.0, min(1.0, (baseline[objective] - result[objective]) / max(abs(baseline[objective]), 1.0))) if feasible else -1.0
    return {"reward": reward, "feasible": feasible, "reason": "COMPLETE_QUALIFIED" if feasible else "OTHER_COMPONENT_CONSTRAINT", "objective": objective,
            "JF": result["JF"], "JM": result["JM"], "JF_baseline": baseline["JF"], "JM_baseline": baseline["JM"], "partial_cost_not_ranked": False}


def update(policy, records, *, algorithm, data_semantics, learning_rate=0.1,
           epochs=1, clip_range=0.2, advantage_baseline=0.0, max_gradient_norm=1.0,
           allow_offline_table=False):
    """Manual exact softmax gradients; runner authorization is required to call.

    BC records have teacher_action_index. RF/PPO records have sampled
    action_index, old_logprob, reward and collection_policy_sha256. A rollout
    batch must be collected from the exact initial policy. In offline mode the
    caller explicitly acknowledges that no new physical on-policy data exists.
    This pure linear model has no critic; it cannot diagnose the old joint-clip
    actor/value mechanism. Counters label gradients as manual equivalents.
    """
    if algorithm not in ("BC", "REINFORCE", "PPO") or not records:
        raise ValueError("INVALID_ALGORITHM_OR_EMPTY_BATCH")
    if data_semantics not in (OFFLINE, ON_POLICY):
        raise ValueError("UNDECLARED_DATA_SEMANTICS")
    if data_semantics == OFFLINE and not allow_offline_table:
        raise ValueError("OFFLINE_TABLE_REQUIRES_EXPLICIT_ACKNOWLEDGEMENT")
    if epochs < 1 or epochs > 10000 or not 0 < learning_rate <= 1 or not 0 < max_gradient_norm <= 100:
        raise ValueError("INVALID_OPTIMIZER_BOUND")
    if algorithm == "PPO" and not 0 < clip_range < 1:
        raise ValueError("INVALID_PPO_CLIP_RANGE")
    if algorithm == "REINFORCE" and epochs != 1:
        raise ValueError("REINFORCE_SINGLE_EPOCH_ONLY")
    origin = policy_sha256(policy)
    if algorithm == "BC" and any(r.get("teacher_complete_and_qualified") is not True for r in records):
        raise ValueError("TEACHER_NOT_COMPLETE_AND_ORIGINALLY_QUALIFIED")
    if data_semantics == ON_POLICY and algorithm != "BC":
        if any(r.get("collection_policy_sha256") != origin for r in records):
            raise ValueError("STALE_OR_MIXED_ON_POLICY_BATCH")
        if len({r["physical_attempt_id"] for r in records}) != len(records):
            raise ValueError("DUPLICATE_PHYSICAL_ATTEMPT")
    steps = []
    for epoch in range(epochs):
        gradient = [[0.0] * len(policy["weights"][0]) for _ in policy["weights"]]
        loss = 0.0
        for record in records:
            x = design(policy, record["features"])
            probs = probabilities(policy, record["features"])
            action = record["teacher_action_index"] if algorithm == "BC" else record["action_index"]
            if not isinstance(action, int) or not 0 <= action < len(probs):
                raise ValueError("INVALID_ACTION_INDEX")
            if algorithm == "BC":
                coefficient = 1.0
                loss -= math.log(max(probs[action], 1e-300))
            else:
                advantage = float(record["reward"]) - float(advantage_baseline)
                if not math.isfinite(advantage):
                    raise ValueError("NONFINITE_ADVANTAGE")
                ratio = math.exp(math.log(max(probs[action], 1e-300)) - record["old_logprob"])
                if algorithm == "PPO":
                    clipped = max(1.0 - clip_range, min(1.0 + clip_range, ratio))
                    loss -= min(ratio * advantage, clipped * advantage)
                    active = (advantage >= 0 and ratio <= 1 + clip_range) or (advantage < 0 and ratio >= 1 - clip_range)
                    coefficient = advantage * ratio if active else 0.0
                else:
                    coefficient = advantage
                    loss -= advantage * math.log(max(probs[action], 1e-300))
            for i in range(len(probs)):
                g = coefficient * ((1.0 if i == action else 0.0) - probs[i]) / len(records)
                for j, value in enumerate(x):
                    gradient[i][j] += g * value
            policy["counters"]["backward_equivalent"] += 1
        norm = math.sqrt(sum(v * v for row in gradient for v in row))
        scale = min(1.0, max_gradient_norm / max(norm, 1e-300))
        for i in range(len(gradient)):
            for j in range(len(gradient[i])):
                policy["weights"][i][j] += learning_rate * scale * gradient[i][j]
        policy["counters"]["parameter_updates"] += 1
        steps.append({"epoch": epoch, "loss": loss / len(records), "gradient_norm": norm, "gradient_scale": scale})
    policy["version"] += 1
    policy["training_data_semantics"] = data_semantics
    return {"algorithm": algorithm, "data_semantics": data_semantics, "source_policy_sha256": origin,
            "result_policy_sha256": policy_sha256(policy), "records": len(records), "steps": steps,
            "new_physical_attempts_generated_by_this_function": 0,
            "counters": copy.deepcopy(policy["counters"])}
