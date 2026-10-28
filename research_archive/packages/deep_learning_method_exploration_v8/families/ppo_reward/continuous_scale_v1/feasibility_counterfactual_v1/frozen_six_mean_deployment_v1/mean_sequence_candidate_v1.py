"""SOURCE_ONLY independent B/H150/lambda1/six-feasibility-mean sequence.

No V4 composition, no training or direct environment dispatch. Future root
thin wrapper/config and original worker_v2 physical approval are required.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os

HERE = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/"
HARD = ["force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed", "session_clearance",
        "true_clearance", "measured_sleeve_clearance", "no_shank_table_contact", "no_human_rom_violation"]
MODELS = ["FEAS_GLOBAL_RF1", "FEAS_GLOBAL_PPO3", "FEAS_CONTEXT_LOO_RF1", "FEAS_CONTEXT_LOO_PPO3", "FEAS_SPAN_GEOMETRY_RF1", "FEAS_SPAN_GEOMETRY_PPO3"]
WORKER_SHA = "c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _original_joined_evidence(package, config, study, tag):
    ident = config["group"]+"_"+tag; row = copy.deepcopy(study.last_row)
    if row.get("id") != ident or getattr(study, "active_owned_child_pid", None) is not None:
        raise ValueError("FEASIBILITY_SIX_ONLY_EXACT_JOINED_CURRENT_CHILD")
    result_path = "attempts/"+ident+"_RESULT.json"
    original = json.loads((package/result_path).read_text())
    for key in ("id", "complete", "qualified", "error", "actual_new_native_steps"):
        if original.get(key) != row.get(key):
            raise ValueError("CURRENT_ROW_NOT_EXACT_ORIGINAL_RESULT:"+key)
    events = {}
    for raw in (package/"runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
        event = json.loads(raw)
        if event.get("id") != ident or event.get("event") not in ("START", "END"):
            continue
        if event["event"] in events:
            raise ValueError("ORIGINAL_ATTEMPT_START_END_NOT_UNIQUE")
        events[event["event"]] = {"record":event, "raw_line_sha256":hashlib.sha256(raw).hexdigest()}
    if (set(events) != {"START", "END"} or events["END"]["record"].get("joined") is not True or
            events["END"]["record"].get("parent_hash_equal") is not True or
            events["START"]["record"].get("config_sha256") != sha(package/"experiments"/(config["group"]+".json"))):
        raise ValueError("EXACT_ORIGINAL_FROZEN_CONFIG_JOINED_CHILD_PARENT_PREFIX_REQUIRED")
    if row.get("complete") is True:
        source = row["metrics_path"]; measured = json.loads((package/source).read_text())
        common = measured.get("native_physical_audit", {}).get("unchanged_evaluator", {}).get("physical_task_result", {}).get("scorer_v2_common_conditions", {})
    else:
        source = result_path; measured = None
        common = row.get("protected_task_failure", {}).get("hard_safety_conditions", {})
    conditions = {key:common.get(key) for key in HARD}
    hard = True if row.get("true_hard_safety_violation") is True or any(v is False for v in conditions.values()) else False if all(v is True for v in conditions.values()) else None
    return {"tag":tag, "original_row":row, "original_result":{"path":result_path, "sha256":sha(package/result_path)},
            "original_events":events, "hard_safety_conditions":conditions, "true_hard_safety_violation":hard,
            "safety_source":{"path":source, "sha256":sha(package/source)}, "complete":row.get("complete"), "qualified":row.get("qualified"),
            "actual_native_steps_and_original_errors_preserved":True, "new_scorer_model_or_physics_calls_by_helper":0}


def sequence(study, config):
    owner_pid = os.getpid(); package = Path(os.environ["ACL2_PACKAGE"]).resolve()
    from acl2_shared import put
    group = config["group"]; pending = None; completed = {}; choices = None; mapping_gate = None
    aliases = {}; plan = []; stopped = None
    counts = {"adapter_entered":0, "adapter_returned":0, "physical_proposals_yielded_to_original_worker":0,
              "new_initialize_restore_fit_RNG_direct_physics":0}
    def owner():
        if os.getpid() != owner_pid:
            raise GeneratorExit("FORK_CHILD_CANNOT_WRITE_FEASIBILITY_SIX_PARENT_OUTPUT")
    def save(name, value):
        owner(); put("analysis/"+group+"_FEASIBILITY_SIX_"+name+".json", value)
    def frozen():
        owner()
        for relative, expected in config["frozen_artifacts"].items():
            path = (package/relative).resolve()
            if not path.is_relative_to(package) or sha(path) != expected:
                raise ValueError("FEASIBILITY_SIX_JOB_FROZEN_SOURCE_OR_MODEL_CHANGED:"+relative)
    def audit(tag):
        owner(); record = _original_joined_evidence(package, config, study, tag)
        completed[tag] = record; save("BRANCH_"+tag, record)
        if record["true_hard_safety_violation"] is True:
            raise RuntimeError("TRUE_HARD_SAFETY_STOP_BEFORE_ANY_PARTIAL_CONTINUATION")
        if record["true_hard_safety_violation"] is not False:
            raise RuntimeError("UNKNOWN_HARD_SAFETY_STOP_NO_SUCCESS_IMPUTATION")
        return record
    def proposal(tag, action, selected_by, full_recipe_sha256, repeat_of=None):
        result = {"tag":tag, "action":copy.deepcopy(action), "category":"INDEPENDENT_FROZEN_FEASIBILITY_SIX_MEAN_EVALUATION",
                  "prediction":{"selected_by":selected_by, "all_six_means_frozen_before_B":True,
                                "full_recipe_sha256":full_recipe_sha256, "physical_action_sha256":digest(action),
                                "shared_recipe_is_not_independent_replication_or_attempt_savings":True}}
        if repeat_of is not None:
            result["repeat_of"] = repeat_of
        return result
    try:
        owner(); frozen()
        if config.get("worker") != "v8_worker_v2.py" or sha(package/"source/v8_worker_v2.py") != WORKER_SHA or config.get("onpolicy_sampling"):
            raise ValueError("ORIGINAL_WORKER_V2_FROZEN_EVALUATION_ONLY")
        if config["frozen_artifacts"].get(HERE+"mean_sequence_candidate_v1.py") != sha(__file__):
            raise ValueError("ACTUAL_NEW_SEQUENCE_SOURCE_MUST_BE_JOB_FROZEN")
        adapter_path = package/HERE/"mean_adapter_candidate_v1.py"
        if config["frozen_artifacts"].get(HERE+"mean_adapter_candidate_v1.py") != sha(adapter_path):
            raise ValueError("ACTUAL_NEW_ADAPTER_SOURCE_MUST_BE_JOB_FROZEN")
        loader = importlib.util.spec_from_file_location("_frozen_feasibility_mean_"+group, adapter_path)
        adapter = importlib.util.module_from_spec(loader); loader.loader.exec_module(adapter)
        counts["adapter_entered"] += 1
        choices = adapter.predict_before_B(package, config, study)
        counts["adapter_returned"] += 1
        if (choices.get("schema") != "v8.frozen_feasibility_six_mean_decisions_before_B.v1" or
                choices.get("all_choices_before_B") is not True or list(choices["decisions"]) != MODELS or study.metrics):
            raise ValueError("EXACT_ALL_SIX_NEW_MEANS_BEFORE_B_REQUIRED")
        lambda1 = choices["lambda1_same_axis_linear_controls"]["mapped"]
        seen = {lambda1["full_recipe_sha256"]:"FEAS_SIX_LAMBDA1_REPEAT"}
        for label in MODELS:
            decision = choices["decisions"][label]
            if decision["status"] == "NUMERICAL_REJECTION_EXPLICIT_B_ANCHOR":
                if decision["fallback_core"] != {"tag":"B", "action":choices["native_reference_actions"]["B"]}:
                    raise ValueError("ONLY_EXPLICIT_ORIGINAL_B_OUTSIDE_AXIS_FALLBACK_ALLOWED")
                aliases[label] = {"tag":"B", "reason":"NUMERICAL_REJECTION_NOT_A_FEASIBILITY_SIX_SUCCESS"}; continue
            mapped = decision["prediction"]; key = mapped["full_recipe_sha256"]
            if digest(mapped["full_recipe"]) != key or digest(mapped["proposal_action"]) != mapped["physical_action_sha256"]:
                raise ValueError("EXACT_ACTUAL_AXIS_RECIPE_REQUIRED")
            if key not in seen:
                tag = "FEAS_SIX_MEAN_"+str(len(plan)+1).zfill(2)
                seen[key] = tag
                plan.append({"tag":tag, "action":mapped["proposal_action"], "full_recipe":mapped["full_recipe"], "full_recipe_sha256":key, "selected_by":[]})
            tag = seen[key]; aliases[label] = {"tag":tag, "reason":"EXACT_FULL_RECIPE_SHARED_DEPLOYMENT_EVALUATION_ONLY"}
            if tag != "FEAS_SIX_LAMBDA1_REPEAT":
                next(item for item in plan if item["tag"]==tag)["selected_by"].append(label)
        owner()
        put("predictions/"+group+"_FEASIBILITY_SIX_ALL_PRE_B_DECISIONS.json", {"decisions":choices, "plan":plan, "aliases":aliases,
            "lambda1_is_new_paid_repeat_not_static_H150_alias":True, "counts":counts, "owner_pid":owner_pid})
        for tag in ("B", "EARLY_H150", "FEAS_SIX_LAMBDA1_REPEAT"):
            owner(); frozen(); pending = tag
            action = lambda1["proposal_action"] if tag=="FEAS_SIX_LAMBDA1_REPEAT" else choices["native_reference_actions"][tag]
            labels = choices["lambda1_same_axis_linear_controls"]["registered_rule_names"] if tag=="FEAS_SIX_LAMBDA1_REPEAT" else []
            recipe_sha = lambda1["full_recipe_sha256"] if tag=="FEAS_SIX_LAMBDA1_REPEAT" else choices["native_reference_recipe_sha256"][tag]
            counts["physical_proposals_yielded_to_original_worker"] += 1
            yield proposal(tag, action, labels, recipe_sha, "EARLY_H150" if tag=="FEAS_SIX_LAMBDA1_REPEAT" else None)
            record = audit(tag); pending = None
            if tag=="B" and (record["complete"] is not True or record["qualified"] is not True):
                raise RuntimeError("ORIGINAL_B_FULL_QUALIFICATION_WHOLE_JOB_GATE")
            if tag=="EARLY_H150" and record["complete"] is not True:
                stopped = "ORIGINAL_H150_PARTIAL_CONTINUOUS_NOT_RUN"; break
            if tag=="FEAS_SIX_LAMBDA1_REPEAT":
                path = "audit/"+group+"_FEAS_SIX_LAMBDA1_REPEAT_REPEAT_GATE.json"
                raw = json.loads((package/path).read_text())
                expected_a = (package/"runtime/source/results"/(group+"_EARLY_H150")).resolve()
                expected_b = (package/"runtime/source/results"/(group+"_FEAS_SIX_LAMBDA1_REPEAT")).resolve()
                if raw.get("status") != "PASS" or Path(raw["a"]).resolve() != expected_a or Path(raw["b"]).resolve() != expected_b:
                    raise RuntimeError("NEW_PAID_LAMBDA1_ORIGINAL_H150_RAW_MAPPING_GATE_FAILED")
                if record["complete"] is not True:
                    stopped = "LAMBDA1_PARTIAL_NO_MEAN_EXECUTION"; break
                for key in ("JF", "JM", "axes", "qualified"):
                    if record["original_row"].get(key) != completed["EARLY_H150"]["original_row"].get(key):
                        raise RuntimeError("RAW_EQUAL_BUT_ORIGINAL_SCORER_RESULT_DIFFERS:"+key)
                mapping_gate = {"status":"PASS_NEW_PAID_FULL_RAW_MAPPING", "original_raw_gate":{"path":path, "sha256":sha(package/path)},
                                "H150_qualified":completed["EARLY_H150"]["qualified"], "qualification_used_as_filter":False}
                save("MAPPING_GATE", mapping_gate)
        if mapping_gate is not None:
            for item in plan:
                owner(); frozen(); pending = item["tag"]
                counts["physical_proposals_yielded_to_original_worker"] += 1
                yield proposal(item["tag"], item["action"], item["selected_by"], item["full_recipe_sha256"])
                record = audit(item["tag"]); pending = None
                if record["complete"] is not True:
                    stopped = "MEAN_ENGINEERING_PARTIAL_STOP_REST"; break
        save("FINAL_EXECUTION_LINK", {"schema":"v8.frozen_feasibility_six_mean_execution_link.v1", "pre_B_decisions":choices,
             "aliases":aliases, "fixed_plan":plan, "mapping_gate":mapping_gate, "stopped":stopped,
             "completed_original_evidence":completed, "NOT_RUN":[item["tag"] for item in plan if item["tag"] not in completed],
             "counts":counts, "actual_adapter_counts":choices["actual_counts"], "root_closed_parent_raw_scorer_receipt_activation_cost_review_still_required":True})
    except GeneratorExit:
        if os.getpid() != owner_pid:
            return
        last = None
        if pending and getattr(study,"last_row",{}).get("id") == group+"_"+pending:
            try: last = _original_joined_evidence(package, config, study, pending)
            except BaseException as error: last = {"root_review_required":True, "error_type":type(error).__name__, "error":str(error)}
        save("OWNER_CLOSE", {"pending":pending, "completed":completed, "last_original_returned_evidence":last, "counts":counts, "no_success_imputation":True})
        return
    except BaseException as error:
        if os.getpid() != owner_pid:
            return
        save("ERROR", {"error_type":type(error).__name__, "error":str(error), "pending":pending, "completed":completed,
                       "counts":counts, "adapter_consumed_work":getattr(error,"feasibility_mean_consumed_work",None), "no_success_imputation":True})
        raise
