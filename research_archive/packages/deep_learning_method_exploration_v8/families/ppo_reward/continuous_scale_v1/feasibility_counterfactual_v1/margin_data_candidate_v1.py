"""SOURCE_ONLY: restore original closed-task margins, never a model or scorer.

GateD requires a later explicit main approval. This file has not been imported
or executed. It rejects partial tasks and reads no mutable Beta run artifact.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import time

GLOBAL_STOP = 1793114740.0
A4_SOURCE = "families/critic_value/coverage_margin_v4/source/audit_component_margin_availability_v1.py"
A4_SHA = "d559baffa113d18ae08076e8878b66824a108f20459d37d7ccba76cebab8f9d9"
HARD = ["force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed",
        "session_clearance", "true_clearance", "measured_sleeve_clearance", "no_shank_table_contact", "no_human_rom_violation"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_frozen(package, ref):
    root = Path(package).resolve()
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root) or "real_runs" in path.relative_to(root).parts:
        raise ValueError("COUNTERFACTUAL_NO_PATH_ESCAPE_OR_ACTUAL_RUN_READ")
    if sha(path) != ref["sha256"]:
        raise ValueError("COUNTERFACTUAL_INPUT_SHA_CHANGED:" + ref["path"])
    return json.loads(path.read_text())


def approved_clock(approval, stage, input_sha256, source_sha256):
    now = time.time()
    if (approval.get("schema") != "v8.beta_feasibility_counterfactual_main_approval.v1" or
            approval.get("status") != "APPROVED_BY_MAIN_FOR_EXACT_INDEPENDENT_OFFLINE_STAGE" or
            approval.get("stage") != stage or approval.get("input_sha256") != input_sha256 or
            approval.get("source_sha256") != source_sha256 or approval.get("single_cpu") is not True or
            approval.get("new_sampling_or_physics") != 0 or approval.get("original_global_stop_unix") != GLOBAL_STOP):
        raise ValueError("COUNTERFACTUAL_EXPLICIT_SEPARATE_STAGE_APPROVAL_REQUIRED")
    start, stop = approval["local_start_unix"], approval["local_stop_unix"]
    cap = 20.0 if stage == "GateD_ORIGINAL_MARGIN_EXTRACTION_ONLY" else 60.0
    if not 0 < stop - start <= cap or not start <= now < min(stop, GLOBAL_STOP):
        raise ValueError("COUNTERFACTUAL_APPROVED_CLOCK_EXPIRED_OR_RESET")


def _a4_components(package):
    path = Path(package) / A4_SOURCE
    if sha(path) != A4_SHA:
        raise ValueError("ORIGINAL_A4_COMPONENT_SOURCE_CHANGED")
    tree = ast.parse(path.read_text())
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ("finite", "components")]
    if {node.name for node in definitions} != {"finite", "components"} or len(definitions) != 2:
        raise ValueError("EXACT_ORIGINAL_A4_TWO_PURE_FUNCTIONS_REQUIRED")
    # Reuse exact original function AST, never import A4 main()/fit code.
    namespace = {"math": math}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["components"]


def extract_closed_batch1(package, inventory_ref, approval):
    """Future approved GateD: exactly four 45-margin extractions, zero model work.

    Call/partial progress is retained on the raised exception. The root runner
    must durably write START/resources before entry, and FAILED before optional
    large diagnostics. No retry is authorized by this function.
    """
    source_sha = sha(__file__)
    approved_clock(approval, "GateD_ORIGINAL_MARGIN_EXTRACTION_ONLY", inventory_ref["sha256"], source_sha)
    inventory = read_frozen(package, inventory_ref)
    if (inventory.get("schema") != "v8.beta_feasibility_counterfactual_source_inventory.v1" or
            inventory["included_jobs"] != ["V8BETA01H", "V8BETA01L"] or
            inventory["number_of_unique_context_action_samples"] != 4 or len(inventory["selected_samples"]) != 4):
        raise ValueError("EXACT_PREDECLARED_FOUR_UNIQUE_FIRST_BATCH_INPUTS_REQUIRED")
    counts = {"components_entered": 0, "components_returned": 0, "margin_values_returned": 0,
              "dense_reward_min_evaluations": 0, "model_import_init_forward_restore_fit_RNG_physics": 0}
    rows = []
    try:
        review = read_frozen(package, inventory["closed_main_review"])
        if (review.get("status") != "READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS" or
                review.get("true_hard_safety_violation") is not False or
                any(review.get(k) is not True for k in ("all_started_children_joined", "all_parent_prefixes_unchanged", "all_started_attempts_hard_safety_reviewed"))):
            raise ValueError("CLOSED_MAIN_FIRST_BATCH_SAFETY_REVIEW_REQUIRED")
        protocol = read_frozen(package, inventory["protocol"])
        if inventory["original_A4_components_source"] != {"path": A4_SOURCE, "sha256": A4_SHA}:
            raise ValueError("REGISTERED_ORIGINAL_A4_COMPONENT_FORMULAS_ONLY")
        components = _a4_components(package)
        baselines = {}
        for item in inventory["baselines"]:
            raw = read_frozen(package, item["result"])
            measured = read_frozen(package, item["measured"])
            replay = read_frozen(package, item["scorer_replay"])
            if raw["complete"] is not True or raw["qualified"] is not True or raw["error"] is not None:
                raise ValueError("SAME_PARENT_B_COMPLETE_ORIGINAL_QUALIFICATION_REQUIRED")
            if replay.get("status") != "SCORER_REPLAY_PASS" or replay.get("original_result_exact_reproduced") is not True or replay.get("qualified_replay") is not True:
                raise ValueError("ORIGINAL_B_SCORER_REPLAY_REQUIRED")
            for ref in (item["result"], item["scorer_replay"]):
                if review["original_evidence_files_sha256"].get(ref["path"]) != ref["sha256"]:
                    raise ValueError("B_INPUT_NOT_EXACT_CLOSED_MAIN_REVIEW_EVIDENCE")
            baselines[item["group"]] = (raw, measured, item)
        for item in inventory["selected_samples"]:
            approved_clock(approval, "GateD_ORIGINAL_MARGIN_EXTRACTION_ONLY", inventory_ref["sha256"], source_sha)
            raw, measured = read_frozen(package, item["result"]), read_frozen(package, item["measured"])
            prediction = read_frozen(package, item["prediction"])
            replay = read_frozen(package, item["scorer_replay"])
            safety = review["started_attempt_safety"][item["id"]]
            if safety.get("true_hard_safety_violation") is True:
                raise ValueError("TRUE_HARD_STOP_BEFORE_ANY_EXCLUSION")
            if safety.get("true_hard_safety_violation") is not False or any(safety["hard_safety_conditions"].get(key) is not True for key in HARD):
                raise ValueError("ORIGINAL_HARD_SAFETY_UNRESOLVED")
            if raw["id"] != item["id"] or raw["complete"] is not True or raw["error"] is not None:
                raise ValueError("PARTIAL_OR_ENGINEERING_ERROR_NEVER_A_MARGIN_TEACHER")
            if (replay.get("status") != "SCORER_REPLAY_PASS" or replay.get("original_result_exact_reproduced") is not True or
                    replay.get("qualified_replay") != raw["qualified"] or replay.get("independent_JF") != raw["JF"] or replay.get("independent_JM") != raw["JM"]):
                raise ValueError("EXACT_ORIGINAL_SAMPLE_SCORER_REPLAY_REQUIRED")
            for ref in (item["result"], item["scorer_replay"]):
                if review["original_evidence_files_sha256"].get(ref["path"]) != ref["sha256"]:
                    raise ValueError("SAMPLE_NOT_EXACT_CLOSED_MAIN_REVIEW_EVIDENCE")
            base, base_measured, base_refs = baselines[item["group"]]
            parent = raw["branch"]["full_hash"]
            if parent != base["branch"]["full_hash"] or parent != measured["branch"]["full_hash"] or parent != base_measured["branch"]["full_hash"] or parent != prediction["parent_hash"]:
                raise ValueError("ORIGINAL_SAME_OUT0_PARENT_BINDING")
            if (raw["metrics_path"] != item["measured"]["path"] or raw["JF"] != measured["J_F_N_s"] or
                    raw["JM"] != measured["moment_integral_Nm_s"] or prediction["selected_lambda"] != item["selected_lambda"]):
                raise ValueError("ORIGINAL_RESULT_MEASUREMENT_OR_LAMBDA_BINDING")
            for replica in item["unique_input_class_physical_replicas"]:
                other = read_frozen(package, replica["prediction"])
                for field in ("selected_lambda", "old_scalar_logdensity", "full_recipe_sha256", "parent_hash"):
                    if other[field] != prediction[field]:
                        raise ValueError("OTHER_ARM_REPLICA_IS_NOT_IDENTICAL_INPUT:" + field)
                known = review["started_attempt_safety"][replica["id"]]
                if known["complete"] is not True or known["true_hard_safety_violation"] is not False:
                    raise ValueError("REPLICA_ORIGINAL_CLOSED_SAFETY_REQUIRED")
            counts["components_entered"] += 1
            values = components(measured, base_measured, protocol["primary"])
            counts["components_returned"] += 1
            counts["margin_values_returned"] += len(values)
            margins = [v["signed_normalized_margin"] for v in values]
            negative = {v["original_failed_requirement_group"] for v in values if v["signed_normalized_margin"] < 0}
            axis_failures = set()
            for axis, name in [("PHYSICAL_TASK_VALID", "physical_task"), ("SCIENTIFIC_EXECUTION_CAUSAL_VALID", "causal_ownership")]:
                if measured["axes"][axis] != "PASS":
                    axis_failures.add(name)
            if negative | axis_failures != set(raw["motion_vs_B"]["failed_requirements"]):
                raise ValueError("EXACT_ORIGINAL_FAILED_GROUP_PARITY_REQUIRED_NO_MARGIN_REDEFINITION")
            accepted = not negative and not axis_failures
            qualified = accepted and measured["axes"]["LEGACY_R2_MATCHED"] == "PASS" and measured["native_physical_audit"]["pass_"]
            if accepted != raw["motion_vs_B"]["acceptance_pass"] or bool(qualified) != raw["qualified"]:
                raise ValueError("MARGIN_SIGN_CANNOT_OVERRIDE_ORIGINAL_QUALIFICATION")
            dense = min(0.0, min(margins))
            counts["dense_reward_min_evaluations"] += 1
            rows.append({"id": item["id"], "group_evaluation_only": item["group"],
                         "lambda_sample": prediction["selected_lambda"], "old_logprob": prediction["old_scalar_logdensity"],
                         "collection_policy_sha256": prediction["collection_policy_sha256"],
                         "full_recipe_sha256": prediction["full_recipe_sha256"],
                         "original_qualified": raw["qualified"], "original_motion_failed_requirements": raw["motion_vs_B"]["failed_requirements"],
                         "original_axes": measured["axes"], "original_45_components": values,
                         "reward_FEASIBILITY_ONLY": dense, "original_force_reward_if_failure": -1.0 if raw["qualified"] is False else None,
                         "JF_and_JM_evaluation_only": {"JF_N_s": raw["JF"], "JM_Nm_s": raw["JM"]},
                         "sources": item, "same_parent_B_sources": base_refs,
                         "commissioned25_from_future_exact_original_proposal_export": None})
        return {"schema": "v8.beta_feasibility_counterfactual_margin_data.v1", "rows": rows, "counts": counts,
                "source_inventory": inventory_ref, "protocol": inventory["protocol"], "A4_original_source": inventory["original_A4_components_source"],
                "data_semantics": "FIXED_BEHAVIOR_REPLAY_NOT_NEW_ON_POLICY", "replay_ready": False,
                "original_qualification_unchanged": True, "JF_JM_costs_not_in_reward": True,
                "unique_context_action_samples": 4, "represented_paid_policy_rollouts": 16}
    except BaseException as error:
        error.counterfactual_paid_work = {"counts": counts, "partial_rows": rows, "no_retry_or_missing_imputation": True}
        raise
