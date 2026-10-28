"""Baseworker generator for genuine sampling only; NEVER calls an update.

This module requires a main-agent-reviewed receipt adapter. No field guessing,
cache outcome substitution, cross-arm sharing, physical launch or mutation on
import. Main installs a thin source/ algorithm wrapper and freezes this file,
driver V2, categorical dependency, adapter, menu and every input snapshot.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text())


def _bounded_path(root, relative):
    if not isinstance(relative,str):
        raise ValueError("PATH_NOT_STRING")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("PATH_ESCAPES_NEW_RESEARCH_PACKAGE")
    return result


def _load_adapter(path, expected_sha):
    if _sha(path) != expected_sha:
        raise ValueError("RECEIPT_ADAPTER_SOURCE_CHANGED")
    spec = importlib.util.spec_from_file_location("_v8_reviewed_onpolicy_receipt_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module,"ADAPTER_SCHEMA",None) != "v8.reviewed_onpolicy_receipt_adapter.v1":
        raise ValueError("RECEIPT_ADAPTER_NOT_EXPLICITLY_REVIEWED_SCHEMA")
    for name in ("build_baseline_receipt", "build_onpolicy_receipt"):
        if not callable(getattr(module,name,None)):
            raise ValueError("MISSING_REVIEWED_ADAPTER_FUNCTION:" + name)
    return module


def sequence(study, config):
    """Yield B, then four arms x two actual independent child attempts.

    Two jobs (one per developer context) produce four pending receipts per arm.
    Root alone preflights all arms, updates copies and atomically commits them.
    An interrupted job is not automatically rerun: unresolved proposals must
    first be reconciled against original START/END/raw by the main agent.
    """
    sequence_owner_pid=os.getpid()
    from acl2_shared import put
    package = Path(os.environ["ACL2_PACKAGE"]).resolve()
    family = package / "families/ppo_reward"
    sys.path.insert(0,str(family))
    sys.path.insert(0,str(package / "families/critic_value/source"))
    from value_api import to_context25
    from categorical_policy import digest, policy_sha256
    from onpolicy_update_driver_v2 import OnPolicyArm, validate_recipe_menu

    if study.metrics:
        raise ValueError("SAMPLING_SEQUENCE_MUST_START_BEFORE_ANY_RESULT")
    if config.get("fork_phase") != "OUTBOUND" or config.get("fork_slot") != 0:
        raise ValueError("ONLY_REGISTERED_OUT0")
    spec = config["onpolicy_sampling"]
    if spec.get("schema") != "v8.onpolicy_sampling_job.v1":
        raise ValueError("UNREVIEWED_SAMPLING_JOB_SCHEMA")
    frozen = config["frozen_artifacts"]
    def verify_frozen():
        for relative, expected in frozen.items():
            if _sha(_bounded_path(package,relative)) != expected:
                raise ValueError("FROZEN_INPUT_CHANGED:" + relative)
    def require_frozen(relative, expected=None):
        if relative not in frozen or (expected is not None and frozen[relative] != expected):
            raise ValueError("DEPENDENCY_NOT_IN_WORKER_FROZEN_MANIFEST:" + relative)
        return _bounded_path(package,relative)
    verify_frozen()
    dependency_relative = "families/ppo_reward/categorical_policy.py"
    dependency_sha = frozen[dependency_relative]
    require_frozen("families/ppo_reward/onpolicy_update_driver_v2.py")
    require_frozen("families/ppo_reward/onpolicy_sequence_v2.py")
    require_frozen("families/critic_value/source/value_api.py")
    require_frozen(spec["approved_contract_path"], spec["approved_contract_sha256"])
    adapter_path = require_frozen(spec["receipt_adapter_path"],spec["receipt_adapter_sha256"])
    adapter = _load_adapter(adapter_path,spec["receipt_adapter_sha256"])
    menu_document = _load(require_frozen(spec["menu_path"],spec["menu_sha256"]))
    if menu_document.get("action_names") != ["B","LATE_H150","EARLY_H150","LATE_PHASE","EARLY_PHASE"]:
        raise ValueError("FIVE_RECIPE_ORDER_NOT_REGISTERED")
    contracts = menu_document["action_contracts"]
    recipe_hashes = menu_document["full_recipe_sha256"]
    if len(contracts) != 5 or [digest(x) for x in contracts] != recipe_hashes or len(set(recipe_hashes)) != 5:
        raise ValueError("FULL_MENU_CONTRACT_IDENTITY")
    # Match the exact candidate that baseworker.run_branch constructs.
    for recipe in contracts:
        action = recipe["action"]
        candidate = copy.deepcopy(config["B"] if action["family"] == "B" else config["H150"])
        candidate.update(copy.deepcopy(action.get("candidate_overrides",{})))
        candidate.pop("id",None)
        if candidate != recipe["resolved_base_candidate"]:
            raise ValueError("BASEWORKER_RESOLVED_CANDIDATE_MISMATCH")
        if _sha(package / "runtime/FROZEN_18D.json") != recipe["frozen_18d_sha256"]:
            raise ValueError("ORIGINAL_18D_IDENTITY")
        for relative, expected in recipe["planner_source_sha256"].items():
            if _sha(_bounded_path(package,relative)) != expected:
                raise ValueError("PLANNER_RECIPE_SOURCE_IDENTITY")
    context = to_context25(study.prefork_causal_context)
    context_sha = digest({"names":context["feature_names"],"values":context["features"]})
    logical_context = spec["development_context_id"]  # routing metadata only
    inputs = spec["arm_inputs"]
    if [x["arm_id"] for x in inputs] != ["RF_RAW","PPO_RAW","RF_SCALED","PPO_SCALED"]:
        raise ValueError("FOUR_ARM_FIXED_ORDER_REQUIRED")
    arms = {}
    source_ids = {}
    for item in inputs:
        path = require_frozen(item["snapshot_path"],item["snapshot_sha256"])
        snapshot = _load(path)
        arm = OnPolicyArm.restore(snapshot,approved_contract_sha256=spec["approved_contract_sha256"],
                                  frozen_menu_sha256=recipe_hashes,categorical_dependency_sha256=dependency_sha)
        if arm.arm_id != item["arm_id"] or logical_context not in arm.expected_context_counts:
            raise ValueError("ARM_OR_CONTEXT_ROUTE_IDENTITY")
        expected_algorithm = "PPO" if item["arm_id"].startswith("PPO") else "REINFORCE"
        expected_gain = 20.0 if item["arm_id"].endswith("SCALED") else 1.0
        if (arm.algorithm,arm.gain) != (expected_algorithm,expected_gain):
            raise ValueError("ARM_ALGORITHM_OR_REWARD_IDENTITY")
        validate_recipe_menu(arm.policy,recipe_hashes)
        if arm.policy["feature_names"] != context["feature_names"]:
            raise ValueError("ACTOR_FEATURE_ORDER")
        same_context = [r for r in arm.pending if r["context_group_evaluation_only"] == logical_context]
        if any(r["physical_result"] is None for r in same_context):
            raise ValueError("MAIN_AGENT_MUST_RECONCILE_UNRESOLVED_PRIOR_PROPOSAL")
        if any(r["causal_features_sha256"] != context_sha for r in same_context):
            raise ValueError("RESUME_CONTEXT_DIFFERS_FROM_PENDING_OBSERVATIONS")
        arms[arm.arm_id] = arm
        source_ids[arm.arm_id] = {"policy_sha256":policy_sha256(arm.policy),"parameter_updates":arm.policy["counters"]["parameter_updates"],"snapshot_sha256":item["snapshot_sha256"]}
    output_relative = spec["output_directory"]
    output = _bounded_path(package,output_relative)
    if not output.is_relative_to(family.resolve()):
        raise ValueError("SAMPLING_OUTPUT_MUST_BE_IN_PPO_FAMILY")
    if output.exists():
        raise ValueError("REFUSE_SAMPLING_JOB_OUTPUT_OVERWRITE")
    output.mkdir(parents=True)
    def save(stage):
        if os.getpid()!=sequence_owner_pid:return
        # All new snapshots remain pending; this sequence never calls finish.
        for arm_id,arm in arms.items():
            if policy_sha256(arm.policy) != source_ids[arm_id]["policy_sha256"] or arm.policy["counters"]["parameter_updates"] != source_ids[arm_id]["parameter_updates"]:
                raise ValueError("POLICY_UPDATED_INSIDE_SAMPLING_ONLY_JOB")
        put(output_relative + "/PENDING_CHECKPOINTS.json",{"schema":"v8.onpolicy_sampling_pending_bundle.v1","stage":stage,"sequence_owner_pid":sequence_owner_pid,
            "job_group_evaluation_only":config["group"],"development_context_id_evaluation_only":logical_context,
            "source_inputs":source_ids,"context25":context,"causal_features_sha256":context_sha,
            "snapshots":{name:arm.snapshot() for name,arm in arms.items()},"parameter_updates_in_this_job":0,
            "root_must_check_worker_done_and_all_parent_attempts":True,"created_unix":time.time()})
    save("READY_BEFORE_B")
    try:
        yield {"tag":"B","action":copy.deepcopy(contracts[0]["action"]),"category":"GENUINE_ONPOLICY_BASELINE_CONTROL",
               "prediction":{"full_recipe_sha256":recipe_hashes[0],"training_sample":False}}
        baseline_row = study.last_row
        if baseline_row["id"] != config["group"] + "_B" or baseline_row.get("complete") is not True or baseline_row.get("qualified") is not True:
            raise ValueError("B_FULL_ORIGINAL_QUALIFICATION_REQUIRED_BEFORE_LEARNER")
        baseline = adapter.build_baseline_receipt(package=package,config=config,context25=context,
                         logical_context_id=logical_context,row=copy.deepcopy(baseline_row))
        put(output_relative + "/B_BASELINE_RECEIPT.json",baseline)
        for item in inputs:
            arm = arms[item["arm_id"]]
            existing = sum(r["context_group_evaluation_only"] == logical_context for r in arm.pending)
            for sample_index in range(existing,2):
                verify_frozen()
                tag = "OP_" + arm.arm_id + "_" + str(sample_index+1).zfill(2)
                attempt_id = config["group"] + "_" + tag
                proposal = arm.propose(attempt_id=attempt_id,context_group_evaluation_only=logical_context,
                             feature_names=context["feature_names"],commissioned_values=context["features"],qa_validated=True,
                             complete_qualified_baseline_receipt=baseline)
                proposal_relative = output_relative + "/" + tag + "_PROPOSAL.json"
                put(proposal_relative,proposal)
                save("PROPOSED_BEFORE_PHYSICAL_START:" + tag)
                yield {"tag":tag,"action":copy.deepcopy(proposal["proposal_recipe"]["action"]),"category":"GENUINE_ONPOLICY_TRAINING_ROLLOUT",
                       "prediction":{"arm_id":arm.arm_id,"proposal_identity_sha256":proposal["proposal_identity_sha256"],
                          "proposal_path":proposal_relative,"proposal_file_sha256":_sha(package/proposal_relative),
                          "collection_policy_sha256":proposal["collection_policy_sha256"],"old_logprob":proposal["old_logprob"],
                          "action_index":proposal["action_index"],"full_recipe_sha256":proposal["proposal_recipe_sha256"],
                          "causal_features_sha256":context_sha,"same_recipe_attempts_are_independent_new_physical_attempts":True}}
                row = study.last_row
                if row.get("id") != attempt_id or row.get("action") != proposal["proposal_recipe"]["action"]:
                    raise ValueError("ACTUAL_WORKER_RESULT_OR_PROPOSAL_ACTION_IDENTITY")
                receipt = adapter.build_onpolicy_receipt(package=package,config=config,context25=context,
                                   logical_context_id=logical_context,proposal=copy.deepcopy(proposal),row=copy.deepcopy(row))
                put(output_relative + "/" + tag + "_PHYSICAL_RECEIPT.json",receipt)
                arm.accept_physical_receipt(receipt)
                if receipt.get("true_hard_safety_violation") is True:
                    save("HARD_SAFETY_STOP:" + tag)
                    raise ValueError("HARD_SAFETY_STOP_MAIN_AGENT_REVIEW")
                save("PHYSICAL_ATTEMPT_JOINED:" + tag)
                if receipt.get("engineering_complete") is not True or receipt.get("ownership_and_causality_audit_pass") is not True or arm.pending[-1]["physical_result"].get("driver_receipt_errors"):
                    raise ValueError("ENGINEERING_CENSORING_STOP_ALL_ARMS_NO_JOB_UPDATE")
        save("ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE")
        put(output_relative + "/SAMPLING_DONE.json",{"status":"PENDING_ONLY_NO_UPDATE","parameter_updates":0,
            "root_transaction_required_after_two_case_jobs":True,"shared_training_outcomes_between_arms":False,
            "expected_new_policy_attempts_this_fresh_job":8,"B_control_is_not_policy_training":True,
            "worker_parent_done_required_separately":True,"created_unix":time.time()})
    except BaseException as error:
        if os.getpid()!=sequence_owner_pid:return
        save("STOPPED_WITH_PRESERVED_PENDING")
        put(output_relative + "/SAMPLING_ERROR.json",{"error_type":type(error).__name__,"error":str(error),
            "parameter_updates":0,"main_agent_must_reconcile_all_consumed_physics":True,"created_unix":time.time()})
        raise
