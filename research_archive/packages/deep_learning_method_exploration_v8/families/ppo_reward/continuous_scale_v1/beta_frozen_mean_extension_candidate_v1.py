"""UNRUN source-only continuous extras for a future root composer.

predict_before_B does 12 frozen Beta mean forwards plus five fixed mappings.
No optimizer/Arm/restore/RNG, no old training-clock extension, no I/O writes or
physics. Actual model inventory/authorization must be supplied by main later.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import time

FAMILY = "families/ppo_reward/continuous_scale_v1/"
ARM_IDS = ["BETA_RF_RAW", "BETA_PPO_RAW", "BETA_RF_SCALED", "BETA_PPO_SCALED"]
ROLES = ["PARENT", "FIRST_COMPLETED", "LAST_COMPLETED"]
GRID = [0., .25, .5, .75, 1.]
GLOBAL_STOP = 1793114740.0
A3_ADAPTER = "families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py"
A3_MANIFEST = "families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(package, relative):
    path = (package/relative).resolve()
    if not path.is_relative_to(package):
        raise ValueError("BETA_DEPLOYMENT_PATH_ESCAPES_PACKAGE")
    return path


def verified(package, ref):
    path = bounded(package, ref["path"])
    if sha(path) != ref["sha256"]:
        raise ValueError("FROZEN_BETA_DEPLOYMENT_ARTIFACT_CHANGED:"+ref["path"])
    return json.loads(path.read_text())


def _before_B(config, study):
    if (study.child is not None or study.fork_done is not True or study.metrics or
            config.get("fork_phase") != "OUTBOUND" or config.get("fork_slot") != 0):
        raise ValueError("BETA_ALL_CHOICES_REQUIRE_ACTUAL_COLD_OUT0_BEFORE_ANY_B_RESULT")


def _authorization(package, config, spec):
    auth = verified(package, spec["deployment_authorization"])
    if (auth.get("schema") != "v8.beta_frozen_mean_deployment_authorization.v1" or
            auth.get("status") != "APPROVED_BY_MAIN_READ_ONLY_FROZEN_DEPLOYMENT" or
            auth.get("inventory") != spec["inventory"] or config["group"] not in auth["authorized_job_groups"] or
            auth.get("mean_policy_forward_only") is not True or auth.get("new_training_or_restore_authorized") is not False or
            not auth["approved_unix"] <= time.time() < min(auth["deployment_deadline_unix"], GLOBAL_STOP)):
        raise ValueError("SEPARATE_FROZEN_DEPLOYMENT_MAIN_APPROVAL_REQUIRED")
    activation = verified(package, {"path":"ACTIVATION.json", "sha256":auth["activation_sha256"]})
    if activation["hard_stop_unix"] != GLOBAL_STOP or activation.get("clock_must_not_reset") is not True:
        raise ValueError("ORIGINAL_GLOBAL_ACTIVATION_DEADLINE_MUST_NOT_RESET")
    required = {FAMILY+"beta_frozen_mean_extension_candidate_v1.py", FAMILY+"beta_policy.py", FAMILY+"axis_mapping.py", A3_ADAPTER, A3_MANIFEST}
    if not required <= set(auth["source_files_sha256"]):
        raise ValueError("COMPLETE_MEAN_EXTENSION_AND_PROOF_SOURCE_CLOSURE_REQUIRED")
    for relative, expected in auth["source_files_sha256"].items():
        if sha(bounded(package,relative)) != expected or config["frozen_artifacts"].get(relative) != expected:
            raise ValueError("DEPLOYMENT_SOURCE_NOT_ACTUAL_JOB_FREEZE:"+relative)
    for ref in (spec["inventory"], spec["deployment_authorization"]):
        if config["frozen_artifacts"].get(ref["path"]) != ref["sha256"]:
            raise ValueError("ACTUAL_INVENTORY_AND_DEPLOYMENT_AUTH_NOT_JOB_FROZEN")
    return auth


def _inventory(package, config, spec):
    inventory = verified(package,spec["inventory"])
    if (inventory.get("schema") != "v8.beta_frozen_mean_deployment_inventory.v1" or
            inventory.get("status") != "FROZEN_ACTUAL_PARENT_FIRST_LAST_NOT_BEST" or
            [item["role"] for item in inventory["roles"]] != ROLES or inventory["arm_ids"] != ARM_IDS or
            inventory.get("policy_location") != ["policy"]):
        raise ValueError("ACTUAL_FROZEN_TWELVE_ROLE_ARM_CHECKPOINTS_REQUIRED")
    review = verified(package,inventory["root_endpoint_review"])
    if (review.get("schema") != "v8.beta_frozen_mean_endpoint_review.v1" or
            review.get("status") != "CLOSED_ACTUAL_ENDPOINTS_PARENT_FIRST_LAST_REVIEWED" or
            review.get("true_hard_safety_violation") is not False or
            review.get("all_training_physical_owners_closed") is not True or
            review.get("endpoint_selected_by_outcome_or_best_seed") is not False or
            not review.get("original_evidence_files_sha256")):
        raise ValueError("ORIGINAL_CLOSED_ENDPOINT_FREEZE_REVIEW_REQUIRED")
    for relative,expected in review["original_evidence_files_sha256"].items():
        if sha(bounded(package,relative)) != expected:
            raise ValueError("ENDPOINT_FREEZE_ORIGINAL_EVIDENCE_CHANGED")
    transactions = {}
    for item in inventory["complete_generation_transaction_inventory"]:
        transaction = verified(package,item["transaction"])
        index = item["generation_index"]
        if (transaction["generation_index"] != index or index in transactions or
                transaction.get("all_four_published_together") is not True or
                set(transaction["checkpoints"]) != set(ARM_IDS)):
            raise ValueError("ACTUAL_ATOMIC_FOUR_ARM_GENERATION_CHAIN_REQUIRED")
        transactions[index] = transaction
    if sorted(transactions) != list(range(len(transactions))) or transactions[0]["status"] != "READY_ALL_FOUR_INITIALIZED":
        raise ValueError("CONTIGUOUS_ACTUAL_GENERATION_INVENTORY_FROM_PARENT_REQUIRED")
    if (review.get("generation_inventory_object_sha256") != digest(inventory["complete_generation_transaction_inventory"]) or
            review.get("latest_published_generation_index") != max(transactions)):
        raise ValueError("MAIN_REVIEW_MUST_BIND_WHOLE_ACTUAL_FROZEN_RUN_TIP_NOT_SELECTED_PREFIX")
    completed = sorted(i for i,t in transactions.items() if t["status"] == "READY_ALL_FOUR_UPDATED")
    if not completed:
        raise ValueError("NO_FIRST_COMPLETED_REAL_UPDATE_MODELS_CANNOT_BE_FABRICATED")
    expected = {"PARENT":0, "FIRST_COMPLETED":completed[0], "LAST_COMPLETED":completed[-1]}
    if review.get("role_generation_indices") != expected:
        raise ValueError("ROOT_REVIEW_MUST_BIND_ACTUAL_FIRST_AND_LAST_NOT_BEST")
    axis = verified(package,inventory["axis"])
    if (digest(axis) != inventory["axis_object_sha256"] or
            config["frozen_artifacts"].get(inventory["axis"]["path"]) != inventory["axis"]["sha256"]):
        raise ValueError("ACTUAL_FROZEN_CONTINUOUS_AXIS_REQUIRED")
    for relative,expected_sha in axis["source_files_sha256"].items():
        if sha(bounded(package,relative)) != expected_sha or config["frozen_artifacts"].get(relative) != expected_sha:
            raise ValueError("LIVE_AXIS_SOURCE_NOT_ORIGINAL_FREEZE")
    if inventory["normalization_source"]["path"] != "families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json":
        raise ValueError("ORIGINAL_FROZEN_G0_NORMALIZATION_PROVENANCE_REQUIRED")
    normalized = verified(package,inventory["normalization_source"])["policy"]["normalization"]
    records = []
    for role in inventory["roles"]:
        if role["generation_index"] != expected[role["role"]] or [item["arm_id"] for item in role["checkpoints"]] != ARM_IDS:
            raise ValueError("EXACT_PARENT_FIRST_LAST_AND_FOUR_ARM_ORDER")
        transaction = transactions[role["generation_index"]]
        for item in role["checkpoints"]:
            ref = {"path":item["path"], "sha256":item["sha256"]}
            actual_ref = transaction["checkpoints"][item["arm_id"]]
            if any(ref[key] != actual_ref[key] for key in ref) or config["frozen_artifacts"].get(ref["path"]) != ref["sha256"]:
                raise ValueError("MODEL_NOT_THIS_ACTUAL_CLOSED_GENERATION_AND_JOB_FREEZE")
            checkpoint = verified(package,ref)
            expected_algorithm = "PPO" if item["arm_id"].startswith("BETA_PPO") else "REINFORCE"
            expected_gain = 20. if item["arm_id"].endswith("SCALED") else 1.
            if (checkpoint.get("schema") != "v8.continuous_beta_arm_checkpoint.v2" or
                    checkpoint.get("execution_mode") != "GENUINE_ON_POLICY" or checkpoint.get("pending") or
                    checkpoint.get("math_fixture_contract_sha256") is not None or checkpoint.get("algorithm") != expected_algorithm or
                    checkpoint["policy"].get("schema") != "v8.scalar_beta_linear25.v1" or checkpoint["policy"].get("gain") != expected_gain or
                    checkpoint["policy"]["arm_id"] != item["arm_id"] or checkpoint["policy"]["normalization"] != normalized or
                    checkpoint["frozen_axis_sha256"] != inventory["axis_object_sha256"] or
                    checkpoint["policy"]["axis_contract"] != axis or
                    checkpoint["policy_behavior_sha256"] != item["policy_behavior_sha256"]):
                raise ValueError("REAL_FINISHED_BETA_POLICY_CONTENT_IDENTITY")
            if role["role"] == "PARENT" and (checkpoint["policy"]["version"] != 0 or checkpoint["policy"]["counters"]["parameter_updates"] != 0):
                raise ValueError("PARENT_MUST_BE_ACTUAL_UNTRAINED_INITIALIZED_ENDPOINT")
            records.append({"role":role["role"],"generation_index":role["generation_index"],"item":item,"checkpoint":checkpoint})
    return inventory,axis,records


def _predict_before_B(P,config,study,counts):
    package = Path(P).resolve(); _before_B(config,study)
    spec = config["beta_mean_extension"]
    if spec.get("schema") != "v8.beta_frozen_mean_extension_job.v1":
        raise ValueError("SEPARATE_CONTINUOUS_EXTRAS_CONFIG_SCHEMA_REQUIRED")
    auth = _authorization(package,config,spec)
    inventory,axis,records = _inventory(package,config,spec)
    a3_manifest = verified(package,inventory["A3_adapter_manifest"])
    if inventory["A3_adapter_manifest"]["path"] != A3_MANIFEST or a3_manifest["adapter_sha256"] != auth["source_files_sha256"][A3_ADAPTER]:
        raise ValueError("ACTUAL_REGISTERED_A3_PROOF_HELPER_REQUIRED")
    a3_proof_dependencies = [a3_manifest["bundles"]["A3"]]+list(a3_manifest["api_files"]["A3"].values())
    for ref in a3_proof_dependencies:
        if (auth["source_files_sha256"].get(ref["path"]) != ref["sha256"] or
                config["frozen_artifacts"].get(ref["path"]) != ref["sha256"]):
            raise ValueError("A3_PROOF_PREPARATION_BUNDLE_AND_APIS_MUST_BE_DEPLOYMENT_AND_JOB_FROZEN")
    loader = importlib.util.spec_from_file_location("_v8_beta_mean_frozen_A3_proof",bounded(package,A3_ADAPTER))
    a3 = importlib.util.module_from_spec(loader); loader.loader.exec_module(a3)
    bundle = verified(package,a3_manifest["bundles"]["A3"])
    # Only original source attestation and context preparation; no A1/A2/A3
    # prediction APIs are called by this extension.
    a3._menu_matches(package,config,bundle["menu"])
    counts["A3_actual_live_seven_role_proof_entry"] += 1
    raw,source_proof,proof_audit = a3._actual_live_proof(package,config,study,bundle)
    counts["A3_actual_live_seven_role_proof_completed"] += 1
    files = a3_manifest["api_files"]["A3"]
    private_a3 = a3._private_modules(package,{k:files[k] for k in ("scoped_subset_api","causal_api")},"BETA_MEAN_CAUSAL")
    counts["A3_scoped_context39_preparation_entry"] += 1
    full_context = private_a3["causal_api"].to_context_full(raw,bundle["input_source_profiles"],source_proof)
    counts["A3_scoped_context39_preparation_completed"] += 1
    names = private_a3["scoped_subset_api"].COMMISSION25
    position = {name:i for i,name in enumerate(full_context["feature_names"])}
    context = {"feature_names":list(names),"features":[full_context["features"][position[name]] for name in names]}
    counts["commissioned25_projection"] += 1
    api_files = {"axis_mapping":{"path":FAMILY+"axis_mapping.py","sha256":auth["source_files_sha256"][FAMILY+"axis_mapping.py"]},
        "beta_policy":{"path":FAMILY+"beta_policy.py","sha256":auth["source_files_sha256"][FAMILY+"beta_policy.py"]}}
    apis = a3._private_modules(package,api_files,"BETA_FROZEN_MEAN")
    beta = apis["beta_policy"]; mapping = apis["axis_mapping"]
    if context["feature_names"] != beta.FEATURE_NAMES:
        raise ValueError("EXACT_CAUSAL_COMMISSIONED25_WHITELIST_REQUIRED")
    # Validate every model before the first forward, even if role refs alias.
    for record in records:
        if beta.policy_sha256(record["checkpoint"]["policy"]) != record["item"]["policy_behavior_sha256"]:
            raise ValueError("ACTUAL_BETA_POLICY_BEHAVIOR_IDENTITY")
    decisions = {}; fixed = {}; catalog = {}
    def add_catalog(name,mapped):
        recipe_sha = mapped["full_recipe_sha256"]
        if digest(mapped["full_recipe"]) != recipe_sha or digest(mapped["proposal_action"]) != mapped["physical_action_sha256"]:
            raise ValueError("ACTUAL_CONTINUOUS_FULLRECIPE_ACTION_IDENTITY")
        if recipe_sha in catalog:
            if catalog[recipe_sha]["full_recipe"] != mapped["full_recipe"] or catalog[recipe_sha]["actual_action"] != mapped["proposal_action"]:
                raise ValueError("SAME_RECIPE_SHA_DIFFERENT_ACTION")
            catalog[recipe_sha]["selected_by"].append(name)
        else:
            catalog[recipe_sha] = {"full_recipe":copy.deepcopy(mapped["full_recipe"]),"actual_action":copy.deepcopy(mapped["proposal_action"]),
                "physical_action_sha256":mapped["physical_action_sha256"],"selected_by":[name],"original_qualification_granted":False}
    core_B = next(item for item in bundle["menu"] if item["tag"]=="B")
    for record in records:
        _before_B(config,study)
        if not time.time() < min(auth["deployment_deadline_unix"],GLOBAL_STOP):raise ValueError("SEPARATE_DEPLOYMENT_DEADLINE_STOP")
        policy = copy.deepcopy(record["checkpoint"]["policy"]); counts["logical_policy_deepcopies"] += 1
        before = copy.deepcopy(policy["counters"])
        name = "BETA_"+record["role"]+"_"+record["item"]["arm_id"].removeprefix("BETA_")+"_MEAN"
        counts["deploy_mean_entry"] += 1
        try:
            result = beta.deploy_mean(policy,context["feature_names"],context["features"],qa_validated=True,frozen_axis_sha256=inventory["axis_object_sha256"])
        except (ValueError,OverflowError) as error:
            counts["deploy_mean_failed"] += 1
            decisions[name] = {"status":"PREDICTIVE_REJECT_EXPLICIT_ORIGINAL_B_FALLBACK_REQUEST","error_type":type(error).__name__,"error":str(error),
                "actual_continuous_action":None,"full_recipe_sha256":None,"checkpoint":record["item"],
                "fallback_core":{"tag":"B","recipe_sha256":core_B["recipe_sha256"],"action":copy.deepcopy(core_B["action"])},
                "original_qualification_granted":False,"training_sample_eligible":False}
        else:
            counts["deploy_mean_completed"] += 1
            if policy["counters"]["forward"] != before["forward"]+1 or any(policy["counters"][key] != before[key] for key in ("score_evaluations","parameter_updates")):
                raise ValueError("PURE_FROZEN_MEAN_FORWARD_COUNTERS_REQUIRED")
            if record["role"]=="PARENT" and result["lambda"] != .5:
                raise ValueError("ACTUAL_SYMMETRIC_PARENT_MEAN_MUST_ALIAS_POINT5")
            add_catalog(name,result)
            decisions[name] = {"status":"FROZEN_CONTINUOUS_MEAN_PROPOSAL_NOT_QUALIFIED",**result,
                "checkpoint":record["item"],"role":record["role"],"generation_index":record["generation_index"]}
        finally:
            counts["actual_policy_forward_delta"] += policy["counters"]["forward"]-before["forward"]
        if beta.policy_sha256(policy) != record["item"]["policy_behavior_sha256"]:
            raise ValueError("FROZEN_BETA_MODEL_PARAMETERS_CHANGED_DURING_MEAN")
    for value in GRID:
        _before_B(config,study)
        if not time.time() < min(auth["deployment_deadline_unix"],GLOBAL_STOP):raise ValueError("SEPARATE_DEPLOYMENT_DEADLINE_STOP")
        name = "BETA_AXIS_FIXED_L"+str(round(value*100)).zfill(3)
        counts["fixed_axis_map_entry"] += 1
        result = mapping.map_lambda(axis,value,expected_axis_sha256=inventory["axis_object_sha256"])
        counts["fixed_axis_map_completed"] += 1
        add_catalog(name,result); fixed[name] = {"status":"FIXED_AXIS_CONTROL_NOT_QUALIFIED",**result,"training_sample_eligible":False}
    original_early = next(item for item in bundle["menu"] if item["tag"]=="EARLY_H150")
    _before_B(config,study)
    if not time.time() < min(auth["deployment_deadline_unix"],GLOBAL_STOP):raise ValueError("SEPARATE_DEPLOYMENT_DEADLINE_STOP")
    return {"schema":"v8.beta.continuous_mean_and_grid_extras_before_B.v1","continuous_decisions":decisions,
        "fixed_axis_controls":fixed,"full_recipe_catalog":catalog,"actual_counts":counts,
        "context25":context,"causal25_numeric_identity_sha256":digest({"names":context["feature_names"],"values":context["features"]}),
        "actual_seven_role_source_proof":source_proof,"proof_audit":proof_audit,
        "all_choices_before_any_B_result":True,"inventory":spec["inventory"],"deployment_authorization":spec["deployment_authorization"],
        "core5_interface_not_used_for_continuous_hashes":True,
        "same_fullrecipe_execution_aliases_not_independent_replication_or_attempt_savings":True,
        "training_rollouts_never_deduplicated":True,
        "required_new_job_paid_exact_raw_repeat_gate":{"continuous_tag":"BETA_AXIS_FIXED_L100",
            "continuous_recipe_sha256":fixed["BETA_AXIS_FIXED_L100"]["full_recipe_sha256"],
            "original_core_tag":"EARLY_H150","original_core_recipe_sha256":original_early["recipe_sha256"],
            "both_new_paid_START_END_required":True,"do_not_alias_away_either_required_repeat":True,
            "exact_original_raw_and_scorer_gate_required":True,"static_physical_equivalence_claimed":False},
        "original_B_outside_Beta_support":True,"lambda0_is_B_or_noop":False,
        "training_clock_read_or_extended":False,"physical_dispatch_or_qualification_granted":False}


def predict_before_B(P,config,study):
    """Future root calls once; exception carries all consumed inference work."""
    counts = {"A3_actual_live_seven_role_proof_entry":0,"A3_actual_live_seven_role_proof_completed":0,
        "A3_scoped_context39_preparation_entry":0,"A3_scoped_context39_preparation_completed":0,
        "commissioned25_projection":0,"deploy_mean_entry":0,"deploy_mean_completed":0,"deploy_mean_failed":0,
        "actual_policy_forward_delta":0,"logical_policy_deepcopies":0,"fixed_axis_map_entry":0,"fixed_axis_map_completed":0,
        "restore":0,"BetaArm_constructor":0,"initialize":0,"RNG_draws":0,"fit_gradient_or_update":0,"new_physics":0}
    try:
        return _predict_before_B(P,config,study,counts)
    except BaseException as error:
        error.beta_mean_extension_consumed_work = copy.deepcopy(counts)
        raise
