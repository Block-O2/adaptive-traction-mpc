"""SOURCE_ONLY independent per-context leave-one-out credit-assignment replay.

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


def context_loo_advantages(rows, counts):
    """Pure arithmetic, suitable for a separately approved synthetic fixture.

    Actual independence and same-context/source proof are checked by replay.
    This helper never predicts, fits, samples, or modifies reward values.
    """
    groups = {row["group_evaluation_only"] for row in rows}
    if len(rows) != 4 or len(groups) != 2 or any(sum(row["group_evaluation_only"] == group for row in rows) != 2 for group in groups):
        raise ValueError("FOUR_ROWS_TWO_CONTEXTS_TWO_DRAWS_REQUIRED")
    peer_baselines = []
    for row in rows:
        peer = next(other for other in rows if other["group_evaluation_only"] == row["group_evaluation_only"] and other["id"] != row["id"])
        peer_baselines.append(peer["reward_FEASIBILITY_ONLY"])
        counts["peer_baseline_formed"] += 1
    advantages = [row["reward_FEASIBILITY_ONLY"]-base for row,base in zip(rows, peer_baselines)]
    half_centered = []
    for value in advantages:
        half_centered.append(.5*value)
        counts["analytic_half_centered_advantage_formed"] += 1
    return peer_baselines, advantages, half_centered


def replay_context_loo(package, input_ref, approval, beta_api):
    """Future GateL: two independent policy copies, RF1/PPO3, same frozen batch.

    The caller must bind the exact common/source closure, use a fresh private
    module namespace, and durably record START/resources before entry. Returned
    artifacts are private counterfactual candidates, never CURRENT generations.
    """
    stage = "GateL_CONTEXT_LOO_FIXED_BEHAVIOR_REPLAY"
    source_sha = sha(__file__)
    approved_clock(approval, stage, input_ref["sha256"], source_sha)
    package = Path(package).resolve()
    if (Path(beta_api.__file__).resolve() != package/BETA_PATH or sha(package/BETA_PATH) != BETA_SHA or
            Path(beta_api.validate_axis.__code__.co_filename).resolve() != package/AXIS_PATH or sha(package/AXIS_PATH) != AXIS_SHA):
        raise ValueError("EXACT_FROZEN_PURE_BETA_AND_AXIS_CODE_REQUIRED")
    registration = read_frozen(package, input_ref)
    if (registration.get("schema") != "v8.beta_feasibility_context_loo_input.v1" or registration.get("target") != "FEASIBILITY_ONLY" or
            registration["base_replay_input"]["sha256"] != "f7596920475e817a45b295b8ff1257e5ac6d28e56b3bf06cda1ccd01dedb6798" or
            registration["completed_global_baseline_result"]["sha256"] != "28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044"):
        raise ValueError("EXACT_SAME_FOUR_ROW_INPUT_AND_CLOSED_GLOBAL_REFERENCE_REQUIRED")
    document = read_frozen(package, registration["base_replay_input"])
    global_result = read_frozen(package, registration["completed_global_baseline_result"])
    if (document.get("schema") != "v8.beta_feasibility_counterfactual_replay_input.v1" or document.get("target") != "FEASIBILITY_ONLY" or
            global_result.get("schema") != "v8.beta_feasibility_counterfactual_private_result.v1" or global_result.get("target") != "FEASIBILITY_ONLY" or
            global_result.get("input") != registration["base_replay_input"]):
        raise ValueError("EXACT_PAID_GLOBAL_BATCHMEAN_RESULT_REUSED_WITHOUT_NEW_FIT")
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
              "new_linear_rule_fit_or_prediction": 0, "peer_baseline_formed": 0,
              "analytic_half_centered_advantage_formed": 0, "initial_gradient_decomposition": 0,
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
        for group in groups:
            pair = [row for row in rows if row["group_evaluation_only"] == group]
            if (pair[0]["id"] == pair[1]["id"] or pair[0]["feature_names"] != pair[1]["feature_names"] or
                    pair[0]["commissioned25"] != pair[1]["commissioned25"] or
                    pair[0]["original_sample"]["rng_after"] != pair[1]["original_sample"]["rng_before"]):
                raise ValueError("PEER_BASELINE_REQUIRES_DISTINCT_DRAWS_FIXED_IDENTICAL_CONTEXT_AND_BEHAVIOR")
        if original_density != global_result["behavior_density_sha256"] or digest(source["weights"]) != global_result["traces"]["REINFORCE"][0]["weights_before_sha256"]:
            raise ValueError("SAME_FROZEN_INITIAL_DENSITY_AND_WEIGHTS_AS_PAID_GLOBAL_RUN_REQUIRED")
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
        if rewards != global_result["rewards"]:
            raise ValueError("DENSE_REWARD_OR_FOUR_ROW_ORDER_CHANGED")
        peer_baselines, advantages, half_centered = context_loo_advantages(rows, counts)
        zero_gradient_reference = None
        initial_gradient_decomposition = None
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
                    old = global_result["traces"]["REINFORCE"][0]["gradient"]
                    within = [[.5*v for v in row] for row in gradient]
                    between = [[a-b for a,b in zip(x,y)] for x,y in zip(old, within)]
                    old_norm = math.sqrt(sum(v*v for row in old for v in row))
                    cosine = sum(a*b for x,y in zip(old,gradient) for a,b in zip(x,y))/max(old_norm*norm,1e-300) if old_norm and norm else None
                    initial_gradient_decomposition = {"closed_global_raw_gradient": old, "new_LOO_raw_gradient": gradient,
                        "centered_raw_gradient_half_LOO_analytic_only": within,
                        "empirical_between_context_offset_component_global_minus_half_LOO": between,
                        "cosine_global_vs_LOO": cosine, "between_context_component_norm": math.sqrt(sum(v*v for row in between for v in row)),
                        "same_initial_score_fields_required": True, "centered_policy_or_endpoint_trained": False,
                        "later_epochs_or_clipping_not_claimed_linear": True}
                    counts["initial_gradient_decomposition"] += 1
        # Reuse the three already paid strong-control rules; zero refits or
        # new rule predictions. Only two LOO policy copies were optimized.
        means = {}
        for algorithm, policy in policies.items():
            means[algorithm] = {}
            for group in groups:
                row = next(row for row in rows if row["group_evaluation_only"] == group)
                counts["deploy_mean_entered"] += 1
                means[algorithm][group] = beta_api.deploy_mean(policy, row["feature_names"], row["commissioned25"], qa_validated=True, frozen_axis_sha256=source["axis_contract_sha256"])
                counts["deploy_mean_returned"] += 1
        approved_clock(approval, stage, input_ref["sha256"], source_sha)
        return {"schema": "v8.beta_feasibility_context_loo_private_result.v1", "target": "FEASIBILITY_ONLY",
                "data_semantics": "FIXED_BEHAVIOR_COUNTERFACTUAL_REPLAY_NOT_NEW_ON_POLICY", "input": input_ref,
                "counts": counts, "behavior_density_sha256": original_density, "rewards": rewards,
                "baseline_kind": "PER_CONTEXT_LEAVE_OTHER_INDEPENDENT_DRAW_REWARD_OUT", "per_row_peer_baselines": peer_baselines,
                "advantages": advantages, "same_context_centered_half_LOO_analytic_only": half_centered,
                "initial_gradient_decomposition": initial_gradient_decomposition,
                "completed_global_baseline_reference": registration["completed_global_baseline_result"],
                "zero_gradient_original_reward_reference": zero_gradient_reference, "private_policies": policies, "traces": traces,
                "endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED": means,
                "same_axis_lambda_margin_linear_rules_REUSED_NO_REFIT": global_result["same_axis_lambda_margin_linear_rules"],
                "new_sampling_or_physics": 0, "original_checkpoint_or_window_modified": False,
                "deployable_or_originally_qualified_claim": False, "JF_JM_improvement_claim": False,
                "original_12mean_inventory_unmodified": True, "future_freeze_API_and_physical_approval_required": True}
    except BaseException as error:
        error.counterfactual_paid_work = {"counts": counts, "private_traces": traces, "completed_input_rows": len(rows),
                                         "private_weights_are_not_published": True, "no_automatic_retry": True}
        raise
