"""SOURCE_ONLY independent FEASIBILITY_ONLY fixed-behavior replay candidate.

No BetaArm, RNG, new environment, genuine-on-policy update or publication API.
Future GateC main approval and exact exported closed artifacts are required.
"""
import copy
import math
from pathlib import Path

from margin_data_candidate_v1 import approved_clock, digest, read_frozen, sha

BETA_PATH = "families/ppo_reward/continuous_scale_v1/beta_policy.py"
BETA_SHA = "4716950923aded5a0daffb0230fbcea39d687a3cddba7bca85bb9ba4231b0c95"
AXIS_PATH = "families/ppo_reward/continuous_scale_v1/axis_mapping.py"
AXIS_SHA = "60e7a8eeaa524c69da6e7b932e7a3b696c7b163d10a500a86d64042a996fa264"
GRID = [0.0, .25, .5, .75, 1.0]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def behavior_density_digest(policy):
    # Version/arm/gain/counters need not match across genuine arms, but these
    # exact fields determine the entire collection density for every raw25.
    return digest({key: policy[key] for key in ("schema", "feature_names", "normalization", "weights", "axis_contract", "axis_contract_sha256")})


def _linear_rule(training_rows, counts):
    """One scalar OLS rule; no case ID or native truth used at prediction."""
    counts["linear_rule_fit_entered"] += 1
    xbar = sum(row["lambda_sample"] for row in training_rows) / len(training_rows)
    ybar = sum(row["reward_FEASIBILITY_ONLY"] for row in training_rows) / len(training_rows)
    denominator = sum((row["lambda_sample"] - xbar)**2 for row in training_rows)
    slope = (sum((row["lambda_sample"] - xbar) * (row["reward_FEASIBILITY_ONLY"] - ybar) for row in training_rows) / denominator
             if denominator > 1e-24 else 0.0)
    intercept = ybar - slope*xbar
    predictions = []
    for lam in GRID:
        counts["linear_rule_grid_scalar_prediction"] += 1
        predictions.append({"lambda": lam, "predicted_FEASIBILITY_ONLY": intercept + slope*lam})
    best = max(p["predicted_FEASIBILITY_ONLY"] for p in predictions)
    # A flat line chooses .5; otherwise equal maxima choose closest to .5,
    # then smaller lambda. No observed result or B is consulted at deployment.
    chosen = min((p for p in predictions if p["predicted_FEASIBILITY_ONLY"] == best), key=lambda p: (abs(p["lambda"]-.5), p["lambda"]))
    counts["linear_rule_fit_returned"] += 1
    return {"intercept": intercept, "slope": slope, "grid_predictions": predictions,
            "selected_lambda": chosen["lambda"], "original_qualification_granted": False,
            "constant_action_rule_has_same_full_axis_permission": True,
            "grid_endpoints_may_be_unobserved_and_require_future_physical_evaluation": True}


def replay(package, input_ref, approval, beta_api):
    """Future GateC: two independent policy copies, RF1/PPO3, one frozen batch.

    The caller must bind the exact common/source closure, use a fresh private
    module namespace, and durably record START/resources before entry. Returned
    artifacts are private counterfactual candidates, never CURRENT generations.
    """
    stage = "GateC_FEASIBILITY_ONLY_FIXED_BEHAVIOR_REPLAY"
    source_sha = sha(__file__)
    approved_clock(approval, stage, input_ref["sha256"], source_sha)
    package = Path(package).resolve()
    if (Path(beta_api.__file__).resolve() != package/BETA_PATH or sha(package/BETA_PATH) != BETA_SHA or
            Path(beta_api.validate_axis.__code__.co_filename).resolve() != package/AXIS_PATH or sha(package/AXIS_PATH) != AXIS_SHA):
        raise ValueError("EXACT_FROZEN_PURE_BETA_AND_AXIS_CODE_REQUIRED")
    document = read_frozen(package, input_ref)
    if document.get("schema") != "v8.beta_feasibility_counterfactual_replay_input.v1" or document.get("target") != "FEASIBILITY_ONLY":
        raise ValueError("INDEPENDENT_FEASIBILITY_REPLAY_INPUT_REQUIRED")
    data = read_frozen(package, document["margin_data"])
    inventory = read_frozen(package, data["source_inventory"])
    checkpoint = read_frozen(package, document["behavior_checkpoint_exact_export"])
    if (checkpoint.get("schema") != "v8.continuous_beta_arm_checkpoint.v2" or checkpoint.get("execution_mode") != "GENUINE_ON_POLICY" or
            checkpoint.get("pending") or data.get("unique_context_action_samples") != 4 or len(data["rows"]) != 4 or
            data.get("original_qualification_unchanged") is not True or data.get("JF_JM_costs_not_in_reward") is not True):
        raise ValueError("EXACT_GENUINE_BEHAVIOR_EXPORT_AND_FOUR_UNIQUE_MARGIN_ROWS_REQUIRED")
    counts = {"logical_policy_copies_entered": 0, "logical_policy_copies_returned": 0,
              "old_density_forward_entered": 0, "old_density_forward_returned": 0,
              "score_entered": 0, "score_returned": 0, "surrogate_entered": 0, "surrogate_returned": 0,
              "parameter_step_entered": 0, "parameter_step_returned": 0,
              "deploy_mean_entered": 0, "deploy_mean_returned": 0,
              "proposal_map_entered": 0, "proposal_map_returned": 0,
              "linear_rule_fit_entered": 0, "linear_rule_fit_returned": 0, "linear_rule_grid_scalar_prediction": 0,
              "BetaArm_constructor_restore_initialize_RNG_new_sampling_physics": 0}
    traces, rows, policies = {}, [], {}
    try:
        source = checkpoint["policy"]
        source_sha_policy = beta_api.policy_sha256(source)
        original_density = behavior_density_digest(source)
        exports = document["original_closed_proposal_exact_exports_by_id"]
        if set(exports) != {item["id"] for item in inventory["selected_samples"]}:
            raise ValueError("ONLY_THE_EXACT_FOUR_REGISTERED_CLOSED_PROPOSALS")
        for data_row, item in zip(data["rows"], inventory["selected_samples"]):
            if data_row["id"] != item["id"] or exports[item["id"]]["sha256"] != item["closed_proposal_original_ref_referenced_but_not_opened"]["sha256"]:
                raise ValueError("EXPORTED_PROPOSAL_MUST_PRESERVE_ORIGINAL_FILE_BYTES")
            proposal = read_frozen(package, exports[item["id"]])
            identity = dict(proposal); expected_identity = identity.pop("proposal_identity_sha256")
            if digest(identity) != expected_identity or proposal["attempt_id"] != item["id"] or proposal["physical_receipt"] is not None:
                raise ValueError("EXACT_ORIGINAL_BEFORE_PHYSICS_PROPOSAL_IDENTITY")
            sample = proposal["sample"]
            if (sample["policy_sha256"] != source_sha_policy or proposal["qa_validated"] is not True or
                    proposal["feature_names"] != beta_api.FEATURE_NAMES or len(proposal["commissioned25"]) != 25 or
                    sample["old_logprob"] != item["old_scalar_logdensity"] or sample["lambda_sample"] != item["selected_lambda"] or
                    sample["full_recipe_sha256"] != item["full_recipe_sha256"] or sample["physical_action_sha256"] != item["physical_action_sha256"] or
                    sample.get("post_sampling_clip") is not False or sample.get("deterministic_mean_deployment") is not False or
                    digest({"names": proposal["feature_names"], "values": proposal["commissioned25"]}) != proposal["causal_features_sha256"]):
                raise ValueError("ORIGINAL_CAUSAL_QA_DENSITY_LAMBDA_ACTUAL_RECIPE_BINDING")
            counts["proposal_map_entered"] += 1
            mapped = beta_api.map_lambda(source["axis_contract"], sample["lambda_sample"], expected_axis_sha256=source["axis_contract_sha256"])
            counts["proposal_map_returned"] += 1
            if mapped["full_recipe"] != sample["full_recipe"] or mapped["full_recipe_sha256"] != sample["full_recipe_sha256"]:
                raise ValueError("ORIGINAL_PHYSICAL_ACTION_OR_FULL_AXIS_RECIPE_CHANGED")
            reward = min(0.0, min(v["signed_normalized_margin"] for v in data_row["original_45_components"]))
            if not finite(reward) or reward != data_row["reward_FEASIBILITY_ONLY"] or data_row["original_qualified"] is not False:
                raise ValueError("EXACT_FIRST_BATCH_FAILED_TASK_MARGIN_TARGET_REQUIRED")
            rows.append({**data_row, "feature_names": proposal["feature_names"], "commissioned25": proposal["commissioned25"],
                         "original_sample": sample, "original_proposal_identity_sha256": expected_identity})
        groups = sorted({row["group_evaluation_only"] for row in rows})
        if len(groups) != 2 or any(sum(row["group_evaluation_only"] == g for row in rows) != 2 for g in groups):
            raise ValueError("EXACT_BALANCED_TWO_CONTEXT_TWO_DRAW_REPLAY_REQUIRED")
        for algorithm in ("REINFORCE", "PPO"):
            counts["logical_policy_copies_entered"] += 1
            policies[algorithm] = copy.deepcopy(source)
            counts["logical_policy_copies_returned"] += 1
        if behavior_density_digest(policies["REINFORCE"]) != original_density or behavior_density_digest(policies["PPO"]) != original_density:
            raise ValueError("BOTH_PRIVATE_POLICIES_MUST_HAVE_IDENTICAL_FROZEN_BEHAVIOR_PARAMETERS")
        # Validate collection density once per unique row using the RF copy.
        for row in rows:
            counts["old_density_forward_entered"] += 1
            _, _, alpha, beta_shape = beta_api._forward(policies["REINFORCE"], row["feature_names"], row["commissioned25"], qa_validated=True, frozen_axis_sha256=source["axis_contract_sha256"])
            counts["old_density_forward_returned"] += 1
            sample = row["original_sample"]
            if (abs(beta_api.log_density(row["lambda_sample"], alpha, beta_shape) - row["old_logprob"]) > 1e-10 or
                    abs(alpha-sample["alpha"]) > 1e-12 or abs(beta_shape-sample["beta"]) > 1e-12):
                raise ValueError("FROZEN_BEHAVIOR_SCALAR_DENSITY_NOT_ORIGINAL_COLLECTION")
        rewards = [row["reward_FEASIBILITY_ONLY"] for row in rows]
        baseline = sum(rewards)/len(rows)
        advantages = [reward-baseline for reward in rewards]
        zero_gradient_reference = None
        for algorithm, epochs in (("REINFORCE", 1), ("PPO", 3)):
            working = policies[algorithm]; traces[algorithm] = []
            for epoch in range(epochs):
                approved_clock(approval, stage, input_ref["sha256"], source_sha)
                gradient = [[0.0]*26 for _ in range(2)]
                zero_gradient = [[0.0]*26 for _ in range(2)]
                details = []
                for row, advantage in zip(rows, advantages):
                    counts["score_entered"] += 1
                    score = beta_api.score_for_weights(working, row["feature_names"], row["commissioned25"], row["lambda_sample"], qa_validated=True, frozen_axis_sha256=source["axis_contract_sha256"])
                    counts["score_returned"] += 1
                    counts["surrogate_entered"] += 1
                    coeff = beta_api.surrogate_coefficient(algorithm=algorithm, new_logprob=score["logprob"], old_logprob=row["old_logprob"], advantage=advantage, clip_range=.2)
                    counts["surrogate_returned"] += 1
                    for h in range(2):
                        for j in range(26):
                            gradient[h][j] += coeff["score_coefficient"]*score["score_gradient"][h][j]/len(rows)
                            # Original floor(-1)-mean(-1)=0, using these same
                            # finite scores; no third policy/hidden forward.
                            zero_gradient[h][j] += 0.0*score["score_gradient"][h][j]/len(rows)
                    ratio = math.exp(score["logprob"]-row["old_logprob"])
                    details.append({"id": row["id"], "lambda_sample": row["lambda_sample"], "advantage": advantage,
                                    "old_logprob": row["old_logprob"], "new_logprob": score["logprob"], "ratio": ratio,
                                    "outside_ratio_clip_range": abs(ratio-1.0)>.2,
                                    "surrogate_gradient_suppressed": algorithm=="PPO" and ((advantage>=0 and ratio>1.2) or (advantage<0 and ratio<.8))})
                norm = math.sqrt(sum(v*v for r in gradient for v in r))
                if not finite(norm) or not all(finite(v) for r in gradient for v in r):
                    raise ValueError("NONFINITE_PRIVATE_REPLAY_GRADIENT")
                scale = min(1.0, 1.0/max(norm, 1e-300))
                counts["parameter_step_entered"] += 1
                weights = [[w+.15*scale*g for w,g in zip(wr,gr)] for wr,gr in zip(working["weights"],gradient)]
                if not all(finite(v) for r in weights for v in r):
                    raise ValueError("NONFINITE_PRIVATE_REPLAY_STEP_NO_PUBLICATION")
                approved_clock(approval, stage, input_ref["sha256"], source_sha)
                delta = math.sqrt(sum((a-b)**2 for r,s in zip(weights,working["weights"]) for a,b in zip(r,s)))
                before_sha = digest(working["weights"])
                # Private local reference replacement, never clear/update a
                # shared actor and never publish a genuine training generation.
                working = {**working, "weights": weights, "counters": {**working["counters"], "parameter_updates": working["counters"]["parameter_updates"]+1}}
                policies[algorithm] = working
                counts["parameter_step_returned"] += 1
                traces[algorithm].append({"epoch": epoch, "gradient": gradient, "raw_gradient_norm": norm, "gradient_clip_scale": scale,
                                          "weight_delta_norm": delta, "weights_before_sha256": before_sha, "weights_after_sha256": digest(weights), "rows": details})
                if algorithm=="REINFORCE" and epoch==0:
                    zero_gradient_reference = {"original_rewards": [-1.0]*4, "original_meanbaseline": -1.0, "original_advantages": [0.0]*4,
                                               "exact_same_score_zero_gradient": zero_gradient, "extra_forward_or_policy_copy": 0}
        rules = {"ALL_EXPOSED_DEVELOPMENT": _linear_rule(rows, counts)}
        for held in groups:
            rules["LEAVE_ONE_EXPOSED_CONTEXT_OUT_"+held] = _linear_rule([row for row in rows if row["group_evaluation_only"] != held], counts)
        means = {}
        for algorithm, policy in policies.items():
            means[algorithm] = {}
            for group in groups:
                row = next(row for row in rows if row["group_evaluation_only"] == group)
                counts["deploy_mean_entered"] += 1
                means[algorithm][group] = beta_api.deploy_mean(policy, row["feature_names"], row["commissioned25"], qa_validated=True, frozen_axis_sha256=source["axis_contract_sha256"])
                counts["deploy_mean_returned"] += 1
        approved_clock(approval, stage, input_ref["sha256"], source_sha)
        return {"schema": "v8.beta_feasibility_counterfactual_private_result.v1", "target": "FEASIBILITY_ONLY",
                "data_semantics": "FIXED_BEHAVIOR_COUNTERFACTUAL_REPLAY_NOT_NEW_ON_POLICY", "input": input_ref,
                "counts": counts, "behavior_density_sha256": original_density, "rewards": rewards, "meanbaseline": baseline, "advantages": advantages,
                "zero_gradient_original_reward_reference": zero_gradient_reference, "private_policies": policies, "traces": traces,
                "endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED": means, "same_axis_lambda_margin_linear_rules": rules,
                "new_sampling_or_physics": 0, "original_checkpoint_or_window_modified": False,
                "deployable_or_originally_qualified_claim": False, "JF_JM_improvement_claim": False,
                "original_12mean_inventory_unmodified": True, "future_freeze_API_and_physical_approval_required": True}
    except BaseException as error:
        error.counterfactual_paid_work = {"counts": counts, "private_traces": traces, "completed_input_rows": len(rows),
                                         "private_weights_are_not_published": True, "no_automatic_retry": True}
        raise
