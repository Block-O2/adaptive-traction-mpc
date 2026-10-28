"""SOURCE_ONLY six fixed feasibility means before B; no actor restoration.

Global/LOO RF1/PPO3 must all actually exist and be frozen before either new
condition starts. No missing model is substituted and no result is read to
select, tune or refit a policy. This is separate from the existing12 inventory.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import time

FAMILY = "families/ppo_reward/continuous_scale_v1/"
HERE = FAMILY+"feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/"
A3 = "families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py"
A3_MANIFEST = "families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json"
MODELS = ["FEAS_GLOBAL_RF1", "FEAS_GLOBAL_PPO3", "FEAS_CONTEXT_LOO_RF1", "FEAS_CONTEXT_LOO_PPO3", "FEAS_SPAN_GEOMETRY_RF1", "FEAS_SPAN_GEOMETRY_PPO3"]
GLOBAL_STOP = 1793114740.0


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def path_at(package, relative):
    path = (package/relative).resolve()
    if not path.is_relative_to(package) or "real_runs" in path.relative_to(package).parts:
        raise ValueError("FROZEN_FEASIBILITY_DEPLOYMENT_NO_ACTUAL_RUN_OR_PATH_ESCAPE")
    return path


def read(package, config, ref):
    path = path_at(package, ref["path"])
    if config["frozen_artifacts"].get(ref["path"]) != ref["sha256"] or sha(path) != ref["sha256"]:
        raise ValueError("FEASIBILITY_SOURCE_OR_MODEL_NOT_EXACT_ACTUAL_JOB_FREEZE:"+ref["path"])
    return json.loads(path.read_text())


def before_B(config, study):
    if study.metrics or study.child is not None or study.fork_done is not True or config.get("fork_phase") != "OUTBOUND" or config.get("fork_slot") != 0:
        raise ValueError("ALL_SIX_FEASIBILITY_DECISIONS_REQUIRE_ACTUAL_COLD_OUT0_BEFORE_B")


def predict_before_B(P, config, study):
    counts = {"actual_seven_role_proof_entered": 0, "actual_seven_role_proof_returned": 0,
              "causal_context39_entered": 0, "causal_context39_returned": 0, "commissioned25_projection": 0,
              "logical_policy_copies": 0, "deploy_mean_entered": 0, "deploy_mean_returned": 0,
              "deploy_mean_numerical_rejection": 0, "beta_internal_forward_counter_delta": 0, "fixed_linear_lambda1_map": 0,
              "restore_initialize_fit_gradient_RNG_sampling_physics": 0}
    try:
        return _predict(P, config, study, counts)
    except BaseException as error:
        error.feasibility_mean_consumed_work = counts
        raise


def _predict(P, config, study, counts):
    package = Path(P).resolve(); before_B(config, study)
    spec = config["frozen_feasibility_six_means"]
    if spec.get("schema") != "v8.frozen_feasibility_six_mean_job.v1":
        raise ValueError("SEPARATE_SIX_MEAN_JOB_SCHEMA_REQUIRED")
    auth = read(package, config, spec["deployment_authorization"])
    if (auth.get("schema") != "v8.frozen_feasibility_six_mean_main_approval.v1" or
            auth.get("status") != "APPROVED_BY_MAIN_FOR_SIX_FROZEN_MEANS_ONLY" or
            auth.get("inventory") != spec["inventory"] or config["group"] not in auth["authorized_job_groups"] or
            auth.get("authorized_job_groups") != ["V8FMEAN03", "V8FMEAN04"] or
            auth.get("mean_forward_only") is not True or auth.get("restore_fit_RNG_or_sampling") != 0 or
            not auth["approved_unix"] <= time.time() < min(auth["deployment_deadline_unix"], GLOBAL_STOP)):
        raise ValueError("INDEPENDENT_READ_ONLY_FROZEN_DEPLOYMENT_AUTHORITY_REQUIRED")
    activation = read(package, config, {"path": "ACTIVATION.json", "sha256": auth["activation_sha256"]})
    if activation.get("hard_stop_unix") != GLOBAL_STOP or activation.get("clock_must_not_reset") is not True:
        raise ValueError("ORIGINAL_GLOBAL_CLOCK_MUST_NOT_RESET")
    minimum = {HERE+"mean_adapter_candidate_v1.py", HERE+"mean_sequence_candidate_v1.py", FAMILY+"beta_policy.py", FAMILY+"axis_mapping.py", A3, A3_MANIFEST, "source/v8_worker_v2.py", "source/acl2_shared.py"}
    root_wrapper = auth["root_wrapper"]
    if auth["source_files_sha256"].get(root_wrapper["path"]) != root_wrapper["sha256"]:
        raise ValueError("NEW_ROOT_THIN_WRAPPER_MUST_BE_EXPLICITLY_SOURCE_APPROVED")
    minimum.add(root_wrapper["path"])
    if not minimum <= set(auth["source_files_sha256"]):
        raise ValueError("COMPLETE_NEW_SEQUENCE_ADAPTER_AND_CAUSAL_SOURCE_CLOSURE_REQUIRED")
    for relative, expected in auth["source_files_sha256"].items():
        if config["frozen_artifacts"].get(relative) != expected or sha(path_at(package, relative)) != expected:
            raise ValueError("FROZEN_DEPLOYMENT_DEPENDENCY_CHANGED:"+relative)
    inventory = read(package, config, spec["inventory"])
    if (inventory.get("schema") != "v8.frozen_feasibility_six_mean_inventory.v1" or
            inventory.get("status") != "ALL_SIX_ACTUAL_FIXED_FINAL_ENDPOINTS_FROZEN_NOT_BEST" or
            [item["label"] for item in inventory["models"]] != MODELS):
        raise ValueError("ALL_SIX_ACTUAL_GLOBAL_AND_LOO_MODELS_REQUIRED_NO_DUMMY")
    original_four = read(package, config, inventory["original_four_inventory"])
    if (inventory["original_four_inventory"]!={"path":"freeze/FEASIBILITY_FOUR_MEAN_ACTUAL_INVENTORY_V1.json","sha256":"8cdf0b16ba19b472511a7e2142d4c1fc812e5581e8badfd8f819a677fca8fadf"} or
            inventory["models"][:4]!=original_four["models"] or len(original_four["models"])!=4):
        raise ValueError("ORIGINAL_FOUR_FIXED_ENDPOINTS_MUST_BE_PRESERVED_EXACTLY")
    geometry_manifest=read(package,config,inventory["geometry_source_manifest"])
    geometry_identity=read(package,config,inventory["geometry_actual_identity"])
    if (inventory["geometry_source_manifest"]["sha256"]!="72301018a87d9351a830bd53dd4dcb02a39f62a9970057f6d10a96930985e083" or
            geometry_identity["source_manifest"]!=inventory["geometry_source_manifest"] or
            geometry_identity["stage"]!="GateG_SPAN_GEOMETRY_LOO_FIXED_BEHAVIOR_REPLAY" or
            any(auth["source_files_sha256"].get(p)!=h for p,h in geometry_manifest["source_files_sha256"].items())):
        raise ValueError("ACTUAL_GEOMETRY_FIT_EXACT_SOURCE_IDENTITY_REQUIRED")
    freeze = read(package, config, inventory["main_endpoint_freeze_review"])
    if (freeze.get("schema") != "v8.frozen_feasibility_endpoint_freeze_review.v1" or
            freeze.get("status") != "ALL_SIX_FINAL_MODELS_AND_PROGRAM_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS" or
            freeze.get("new_parameter_parents_not_started_at_freeze") is not True or
            freeze.get("outcome_or_best_endpoint_selection") is not False or
            freeze.get("source_files_sha256") != auth["source_files_sha256"] or
            freeze.get("models_object_sha256") != digest(inventory["models"]) or
            freeze.get("new_parameter_registration") != inventory["new_parameter_registration"]):
        raise ValueError("MAIN_MUST_BIND_ALL_SIX_AND_PROGRAM_BEFORE_ANY_NEW_PARAMETER_PHYSICS")
    registration = read(package, config, inventory["new_parameter_registration"])
    if registration.get("job_groups") != ["V8FMEAN03", "V8FMEAN04"] or registration.get("original_task_and_equations_unchanged") is not True:
        raise ValueError("ROOT_PREREGISTERED_ORIGINAL_TWO_PARAMETER_CONDITIONS_REQUIRED")
    axis = read(package, config, inventory["axis"])
    if digest(axis) != inventory["axis_object_sha256"]:
        raise ValueError("ACTUAL_ORIGINAL_CONTINUOUS_AXIS_CONTENT_REQUIRED")
    for relative, expected in axis["source_files_sha256"].items():
        if config["frozen_artifacts"].get(relative) != expected or sha(path_at(package, relative)) != expected:
            raise ValueError("ORIGINAL_AXIS_RUNTIME_SOURCE_CHANGED:"+relative)
    menu = read(package, config, inventory["original_recipe_menu"])["action_contracts"]
    native = {"B": menu[0], "EARLY_H150": menu[2]}
    for tag, recipe in native.items():
        candidate = copy.deepcopy(config["B"] if tag=="B" else config["H150"])
        candidate.pop("id", None)
        if candidate != recipe["resolved_base_candidate"]:
            raise ValueError("ACTUAL_NATIVE_B_OR_H150_REFERENCE_CHANGED")
    if [item["tag"] for item in config["actions"]] != ["B", "EARLY_H150"] or [item["action"] for item in config["actions"]] != [native[tag]["action"] for tag in ("B", "EARLY_H150")]:
        raise ValueError("NEW_SEQUENCE_NATIVE_REFERENCES_ONLY_NO_UNUSED_FIVE_ACTION_PERMISSION")
    a3_manifest = read(package, config, inventory["A3_adapter_manifest"])
    if inventory["A3_adapter_manifest"]["path"] != A3_MANIFEST or a3_manifest["adapter_sha256"] != auth["source_files_sha256"][A3]:
        raise ValueError("EXACT_REGISTERED_CAUSAL_PROOF_HELPER_REQUIRED")
    for ref in [a3_manifest["bundles"]["A3"], *a3_manifest["api_files"]["A3"].values()]:
        if auth["source_files_sha256"].get(ref["path"]) != ref["sha256"]:
            raise ValueError("A3_CAUSAL_PROOF_DEPENDENCIES_NOT_SEPARATELY_FROZEN")
    loader = importlib.util.spec_from_file_location("_feasibility_mean_A3_proof_"+config["group"], path_at(package, A3))
    a3 = importlib.util.module_from_spec(loader); loader.loader.exec_module(a3)
    bundle = read(package, config, a3_manifest["bundles"]["A3"])
    # Source proof and causal preparation only. A3 menu matcher and all A-model
    # prediction APIs are deliberately absent: the new action domain is 1D.
    counts["actual_seven_role_proof_entered"] += 1
    raw, proof, proof_audit = a3._actual_live_proof(package, config, study, bundle)
    counts["actual_seven_role_proof_returned"] += 1
    files = a3_manifest["api_files"]["A3"]
    causal = a3._private_modules(package, {key:files[key] for key in ("scoped_subset_api", "causal_api")}, "FEASIBILITY_MEAN_CAUSAL")
    counts["causal_context39_entered"] += 1
    full = causal["causal_api"].to_context_full(raw, bundle["input_source_profiles"], proof)
    counts["causal_context39_returned"] += 1
    names = causal["scoped_subset_api"].COMMISSION25
    positions = {name:index for index,name in enumerate(full["feature_names"])}
    context = {"feature_names": list(names), "features": [full["features"][positions[name]] for name in names]}
    counts["commissioned25_projection"] += 1
    apis = a3._private_modules(package, {name:{"path": FAMILY+name+".py", "sha256": auth["source_files_sha256"][FAMILY+name+".py"]} for name in ("axis_mapping", "beta_policy")}, "FEASIBILITY_FROZEN_MEAN")
    beta, mapping = apis["beta_policy"], apis["axis_mapping"]
    mapping.validate_axis(axis, inventory["axis_object_sha256"])
    behavior = read(package, config, inventory["original_behavior_exact_export"])["policy"]
    behavior_density = digest({key:behavior[key] for key in ("schema", "feature_names", "normalization", "weights", "axis_contract", "axis_contract_sha256")})
    if context["feature_names"] != beta.FEATURE_NAMES:
        raise ValueError("ACTUAL_CAUSAL_COMMISSIONED25_WHITELIST")
    records = []
    for item in inventory["models"]:
        result = read(package, config, item["closed_result"])
        done = read(package, config, item["closed_DONE"])
        is_geometry=item["label"].startswith("FEAS_SPAN_GEOMETRY")
        is_loo = item["label"].startswith("FEAS_CONTEXT_LOO") or is_geometry
        schema = "v8.beta_feasibility_span_geometry_private_result.v1" if is_geometry else "v8.beta_feasibility_context_loo_private_result.v1" if is_loo else "v8.beta_feasibility_counterfactual_private_result.v1"
        algorithm = "PPO" if item["label"].endswith("PPO3") else "REINFORCE"
        if (result.get("schema") != schema or result.get("target") != "FEASIBILITY_ONLY" or
                done.get("status") != "COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or done.get("result_sha256") != item["closed_result"]["sha256"] or
                item["policy_json_path"] != ["private_policies", algorithm]):
            raise ValueError("ACTUAL_CLOSED_FIXED_FINAL_RF1_PPO3_ENDPOINTS_REQUIRED")
        if ((not is_loo and item["closed_result"]["sha256"] != "28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044") or
                (is_loo and (result.get("baseline_kind") != "PER_CONTEXT_LEAVE_OTHER_INDEPENDENT_DRAW_REWARD_OUT" or
                            result.get("completed_global_baseline_reference", {}).get("sha256") != "28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044"))):
            raise ValueError("REGISTERED_GLOBAL_AND_CONTEXT_LOO_TARGETS_ONLY_NO_SELECTED_OTHER_FIT")
        if is_geometry and (item["closed_result"]!=inventory["closed_geometry_result"] or
                item["closed_result"]["sha256"]!="c8cfcbd65927717cc94bc91f0d38ad72da579582aada215e806d7dcc0b9b41e4" or
                item["closed_DONE"]["sha256"]!="13e4eea60ce818add0ba01b070949694ca98f5d0a6653ec425177eefd5fcc781" or
                result["input"]!=geometry_identity["input"] or result["input"]["sha256"]!="8598bdf2fd76fbb7212779718d72982b56743c14fb5b57cc9e7b6570aae4b3ed" or
                result.get("geometry_kind")!="Zt_Kinverse_D_contextcoefficients_UNIFIED_TWOHEAD_NORM_RESCALE" or
                result.get("completed_context_loo_reference",{}).get("sha256")!="55369ef436e9b0b54023ee7cdb20e9c520d1933c2ed69f865bc3f7f011129db2" or
                result.get("completed_kernel_diagnostic_reference",{}).get("sha256")!="7c940d3e313379b9f41fd1a2066b624d0c0323998dd5539a675b04c45459cdad" or
                result.get("endpoint_selection")!="BOTH_FIXED_FINAL_RF1_PPO3_NOT_BEST" or
                result.get("original_four_feasibility_mean_inventory_unmodified") is not True):
            raise ValueError("ONLY_ACTUAL_CLOSED_GEOMETRY_TWO_FINAL_ENDPOINTS_NO_SELECTED_NEW_FIT")
        policy = result["private_policies"][algorithm]
        if (policy["normalization"] != behavior["normalization"] or policy["axis_contract"] != axis or
                policy["feature_names"] != context["feature_names"] or len(policy["weights"]) != 2 or any(len(row) != 26 for row in policy["weights"]) or
                policy["axis_contract_sha256"] != inventory["axis_object_sha256"] or
                policy["counters"]["parameter_updates"] != (3 if algorithm=="PPO" else 1) or
                len(result["traces"][algorithm]) != (3 if algorithm=="PPO" else 1) or result["behavior_density_sha256"] != behavior_density or
                beta.policy_sha256(policy) != item["policy_sha256"] or digest(policy["weights"]) != item["weights_sha256"] or
                not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for row in policy["weights"] for v in row)):
            raise ValueError("FIXED_ACTUAL_POLICY_NORMALIZATION_AXIS_OR_WEIGHT_IDENTITY")
        records.append((item, policy))
    if (inventory["models"][0]["closed_result"] != inventory["models"][1]["closed_result"] or
            inventory["models"][2]["closed_result"] != inventory["models"][3]["closed_result"] or
            inventory["models"][0]["closed_result"] != inventory["closed_global_result"] or
            inventory["models"][0]["closed_result"] == inventory["models"][2]["closed_result"] or
            inventory["models"][4]["closed_result"]!=inventory["models"][5]["closed_result"] or
            inventory["models"][4]["closed_result"]!=inventory["closed_geometry_result"] or
            inventory["models"][4]["closed_result"] in [inventory["models"][0]["closed_result"],inventory["models"][2]["closed_result"]]):
        raise ValueError("TWO_COMPLETE_GLOBAL_LOO_RESULTS_ALL_FIXED_ENDPOINTS_REQUIRED")
    decisions = {}
    for item, original in records:
        before_B(config, study)
        if time.time() >= min(auth["deployment_deadline_unix"], GLOBAL_STOP):
            raise ValueError("FROZEN_FEASIBILITY_DEPLOYMENT_DEADLINE")
        policy = copy.deepcopy(original); counts["logical_policy_copies"] += 1
        before_forward = policy["counters"]["forward"]
        counts["deploy_mean_entered"] += 1
        try:
            mapped = beta.deploy_mean(policy, context["feature_names"], context["features"], qa_validated=True, frozen_axis_sha256=inventory["axis_object_sha256"])
        except (ValueError, OverflowError) as error:
            if isinstance(error,ValueError) and str(error) not in ("NUMERICAL_SHAPE_OVERFLOW_NO_ACTION", "NONFINITE_SHAPE_LOGIT"):
                raise
            counts["deploy_mean_numerical_rejection"] += 1
            decisions[item["label"]] = {"status": "NUMERICAL_REJECTION_EXPLICIT_B_ANCHOR", "error_type": type(error).__name__, "error": str(error),
                                        "fallback_core": {"tag":"B", "action":native["B"]["action"]}, "original_qualification_granted":False}
            continue
        finally:
            counts["beta_internal_forward_counter_delta"] += policy["counters"]["forward"]-before_forward
        counts["deploy_mean_returned"] += 1
        if digest(mapped["full_recipe"]) != mapped["full_recipe_sha256"] or digest(mapped["proposal_action"]) != mapped["physical_action_sha256"]:
            raise ValueError("ACTUAL_MEAN_FULL_RECIPE_OR_ACTION_DIGEST")
        decisions[item["label"]] = {"status": "FROZEN_MEAN_NOT_PHYSICALLY_QUALIFIED", "model": item, "prediction": mapped}
    # Three previously fitted same-axis linear controls all select lambda1;
    # reuse that exact choice, do not refit or import a model for these labels.
    global_result = read(package, config, inventory["closed_global_result"])
    rules = global_result["same_axis_lambda_margin_linear_rules"]
    if len(rules) != 3 or any(rule["selected_lambda"] != 1.0 for rule in rules.values()):
        raise ValueError("UNCHANGED_PAID_LINEAR_CONTROLS_MUST_ALL_SELECT_REGISTERED_LAMBDA1")
    counts["fixed_linear_lambda1_map"] += 1
    lambda1 = mapping.map_lambda(axis, 1.0, expected_axis_sha256=inventory["axis_object_sha256"])
    before_B(config, study)
    return {"schema": "v8.frozen_feasibility_six_mean_decisions_before_B.v1", "context25": context,
            "actual_seven_role_proof": proof, "proof_audit": proof_audit, "decisions": decisions,
            "lambda1_same_axis_linear_controls": {"registered_rule_names": list(rules), "mapped": lambda1,
                                                    "required_new_physical_repeat_of": "EARLY_H150"},
            "native_reference_actions": {tag:copy.deepcopy(native[tag]["action"]) for tag in ("B", "EARLY_H150")},
            "native_reference_recipe_sha256": {tag:digest(native[tag]) for tag in ("B", "EARLY_H150")},
            "all_choices_before_B": True, "actual_counts": counts,
            "permission": "ORIGINAL_B_ANCHOR_PLUS_REGISTERED_SCALAR_AXIS_AND_H150_MAPPING_REFERENCE",
            "old_twelve_mean_inventory_modified": False, "new_learner_or_training": False,"original_four_mean_inventory_modified":False}
