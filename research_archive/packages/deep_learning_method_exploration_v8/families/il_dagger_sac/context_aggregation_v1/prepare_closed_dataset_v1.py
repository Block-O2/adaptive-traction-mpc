"""Read-only closed-input preparation; no model imports, normalization or fit."""
from pathlib import Path
import argparse
import copy
from datetime import datetime
import hashlib
import json
import math
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def prepare(package, output):
    activation = load(package / "ACTIVATION.json")
    if time.time() >= datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp():
        raise ValueError("ORIGINAL_GLOBAL_DEADLINE")
    if output.exists() or not output.resolve().is_relative_to(Path(__file__).resolve().parent):
        raise ValueError("FRESH_ASSIGNED_DIRECTORY_OUTPUT_REQUIRED")
    source_hashes = {}
    def source(relative):
        path = package / relative
        source_hashes[relative] = sha(path)
        return load(path)
    menu = source("freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json")
    if menu["action_names"] != ["B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]:
        raise ValueError("FROZEN_MENU_ORDER")
    hashes = [digest(x) for x in menu["action_contracts"]]
    if hashes != menu["full_recipe_sha256"] or len(set(hashes)) != 5:
        raise ValueError("ACTUAL_FULL_MENU_DIGEST")
    lookup = {value: index for index, value in enumerate(hashes)}
    historical = source("families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json")
    if len(historical["rows"]) != 45 or len({r["group"] for r in historical["rows"]}) != 6:
        raise ValueError("ORIGINAL_45_ROW_SIX_CONTEXT_LIBRARY")
    parent_path = "families/ppo_reward/offline_fit_v2/checkpoints/qualified_force_raw/ALL_EXPOSED_DEVELOPMENT/BC_linear_commissioned25.json"
    parent = source(parent_path)["policy"]
    features = parent["feature_names"]
    if len(features) != 25 or [digest(x) for x in parent["action_contracts"]] != hashes[:3]:
        raise ValueError("FROZEN_BC_PARENT_FEATURE_OR_ACTION_IDENTITY")
    contexts = {}
    rows = []
    audit = []
    excluded = []
    seen = set()
    def add_context(group, context, origin):
        if context["feature_names"] != features or len(context["features"]) != 25 or not all(finite(v) for v in context["features"]):
            raise ValueError("ORIGINAL_CAUSAL25_ORDER_OR_VALUES")
        if not isinstance(context.get("quality"),dict) or len(context["quality"]) != 33 or not all(finite(v) for v in context["quality"].values()):
            raise ValueError("ORIGINAL_QA33_REQUIRED")
        identity = digest({"names":features,"values":context["features"]})
        value = {"context_group_evaluation_only":group,"parent_group_evaluation_only":group,
                 "origin":origin,"feature_names":copy.deepcopy(features),"features":copy.deepcopy(context["features"]),
                 "quality":copy.deepcopy(context["quality"]),"causal_features_sha256":identity,"legacy77d_valid":False}
        if group in contexts and contexts[group] != value:
            raise ValueError("SAME_PARENT_DIFFERENT_CAUSAL_CONTEXT")
        contexts[group] = value
        return identity
    def add_row(row):
        key=(row["context_group_evaluation_only"],row["full_recipe_sha256"])
        if key in seen:
            raise ValueError("DUPLICATE_PARENT_RECIPE_REQUIRES_REVIEW")
        seen.add(key);rows.append(row)
    for index, row in enumerate(historical["rows"]):
        if digest(row["action_recipe"]) != row["action_recipe_sha256"] or row["action_recipe"]["action"] != row["action"]:
            raise ValueError("HISTORICAL_ACTUAL_RECIPE_CONTENT")
        if row["boundary"] != {"phase":"OUTBOUND","slot":0} or row["continuation_policy"] != "FULL_POLICY_COMMITMENT_WITH_FROZEN_SLOT_OVERRIDES":
            raise ValueError("HISTORICAL_OUT0_FULL_POLICY_CONTRACT")
        add_context(row["group"],row["context"],"HISTORICAL_EXPOSED_DEVELOPMENT")
        audit.append({"source_row_index":index,"id":row["id"],"group":row["group"],"source_row_sha256":digest(row),
                      "full_recipe_sha256":row["action_recipe_sha256"],"in_frozen_five_menu":row["action_recipe_sha256"] in lookup,
                      "complete":row["labels_evaluation_only"]["complete"],
                      "original_qualified":row["labels_evaluation_only"]["original_qualified"],
                      "JF_N_s":row["labels_evaluation_only"]["JF_N_s"],"JM_Nm_s":row["labels_evaluation_only"]["JM_Nm_s"]})
        if row["action_recipe_sha256"] not in lookup:
            excluded.append({"id":row["id"],"reason":"OUTSIDE_FIXED_FIVE_MENU_NOT_RELABELED"});continue
        action_index=lookup[row["action_recipe_sha256"]]
        if row["action_recipe"] != menu["action_contracts"][action_index]:
            raise ValueError("HISTORICAL_MENU_CONTRACT_MISMATCH")
        add_row({"id":row["id"],"context_group_evaluation_only":row["group"],"origin":"HISTORICAL_V2",
                 "action_index":action_index,"full_recipe_sha256":hashes[action_index],
                 "labels_evaluation_only":copy.deepcopy(row["labels_evaluation_only"]),
                 "source_reference":{"historical_library_row_index":index,"historical_row_sha256":digest(row)},
                 "actual_new_physics_by_this_preparation":0})
    required_groups=["V8CTX01","V8CTX02","V8CTX03","V8CTX04"]
    closed=[];pending=[];closure=[]
    for group in required_groups:
        worker_path=package/"jobs"/group/"WORKER_DONE.json"
        physics_path=package/"jobs"/group/"PHYSICS_DONE.json"
        # No result, raw, context, or progress read occurs before this gate.
        if not worker_path.is_file() or not physics_path.is_file():
            pending.append(group);closure.append({"group":group,"worker_done_exists":worker_path.is_file(),
                "physics_done_exists":physics_path.is_file(),"any_result_or_context_or_raw_opened":False});continue
        worker=source(str(worker_path.relative_to(package)));physics=source(str(physics_path.relative_to(package)))
        if worker.get("status") != "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS" or worker.get("all_children_joined") is not True or not worker.get("parent_checks") or not all(r.get("unchanged") is True for r in worker["parent_checks"]) or physics.get("all_parent_unchanged") is not True or physics.get("status") != "COMPLETED":
            raise ValueError("GROUP_NOT_CLOSED:"+group)
        manifest=source("jobs/"+group+"/SOURCE_MANIFEST.json")
        payload=source("history/"+group+"_PREFORK_CAUSAL_CONTEXT.json")
        body={k:v for k,v in payload.items() if k!="causal_payload_sha256"}
        if digest(body) != payload["causal_payload_sha256"] or payload["schema"] != "ihear.causal_human_context.v1.77d" or payload["hidden_or_future_inputs_used"] is not False or payload["model_prediction_or_observe_calls"] != 0 or payload["model_vector_valid"] is not False or payload["phase"] != "OUTBOUND" or abs(payload["task_s"]) > 1e-9 or payload["capture_position"] != "parent request boundary BEFORE fork loop/candidate selection/control mutation":
            raise ValueError("NEW_ORIGINAL_CAUSAL_PAYLOAD_PROOF")
        values=dict(zip(payload["feature_names"],payload["features"]))
        if values["decision_slot"] != 0: raise ValueError("NEW_OUT0_SLOT")
        add_context(group,{"feature_names":features,"features":[values[n] for n in features],"quality":payload["quality"]},"NEW_EXPOSED_DEVELOPMENT")
        matched=[]
        for row in physics["rows"]:
            if row["id"] in (group+"_HISTORY_B",group+"_parent"):
                excluded.append({"id":row["id"],"reason":"REPEATED_B_OR_PARENT_NOT_NEW_CONTEXT_TEACHER"});continue
            digest_action=digest(row["action"])
            indices=[i for i,c in enumerate(menu["action_contracts"]) if digest(c["action"])==digest_action and c["action"]==row["action"]]
            if len(indices) != 1: raise ValueError("NEW_ACTUAL_ACTION_NOT_EXACT_FROZEN_MENU:"+row["id"])
            action_index=indices[0];contract=menu["action_contracts"][action_index]
            saved=source("attempts/"+row["id"]+"_RESULT.json")
            if saved != row: raise ValueError("CLOSED_WORKER_RESULT_DIFFERS")
            binding=source("attempts/"+row["id"]+"_EXECUTION_BINDING.json")
            candidate=copy.deepcopy(binding["candidate"]);candidate.pop("id",None)
            if binding["action"] != row["action"] or candidate != contract["resolved_base_candidate"]:
                raise ValueError("ACTUAL_EXECUTION_CANDIDATE_RECIPE_BINDING")
            expected={"runtime/FROZEN_18D.json":contract["frozen_18d_sha256"],**contract["planner_source_sha256"]}
            if any(manifest["files"].get(n)!=h for n,h in expected.items()):
                raise ValueError("ACTUAL_JOB_SOURCE_DIFFERS_FROM_FULL_RECIPE")
            if row.get("complete") is not True or not isinstance(row.get("qualified"),bool) or not all(finite(row.get(k)) for k in ("JF","JM")):
                raise ValueError("REQUESTED_NEW_COMPLETE_FIVE_MENU_ROWS_NOT_CLOSED_FULL")
            measured=source(row["metrics_path"])
            lineage_path=Path(measured["execution_lineage_path"]).resolve()
            if not lineage_path.is_relative_to(package): raise ValueError("ORIGINAL_LINEAGE_OUTSIDE_PACKAGE")
            lineage=source(str(lineage_path.relative_to(package)))
            if lineage["status"] != "PASS" or measured["axes"]["SCIENTIFIC_EXECUTION_CAUSAL_VALID"] != "PASS" or measured["J_F_N_s"] != row["JF"] or measured["moment_integral_Nm_s"] != row["JM"]:
                raise ValueError("NEW_ORIGINAL_METRICS_RECEIPTS_IDENTITY")
            if not isinstance(row.get("actual_new_native_steps"),int) or row["actual_new_native_steps"]<=0:
                raise ValueError("ACTUAL_NEW_CHILD_STEPS_REQUIRED")
            labels={"JF_N_s":row["JF"],"JM_Nm_s":row["JM"],"complete":row["complete"],"original_qualified":row["qualified"],
                    "original_axes":row["axes"],"motion_failed_requirements":row["motion_vs_B"]["failed_requirements"],
                    "motion_comparison":row["motion_vs_B"],"error":row.get("error")}
            add_row({"id":row["id"],"context_group_evaluation_only":group,"origin":"CLOSED_NEW_EXPOSED_CTX",
                     "action_index":action_index,"full_recipe_sha256":hashes[action_index],"labels_evaluation_only":labels,
                     "source_reference":{"result_path":"attempts/"+row["id"]+"_RESULT.json","metrics_path":row["metrics_path"],
                        "execution_lineage_path":str(lineage_path.relative_to(package)),"closed_worker_manifest":"jobs/"+group+"/SOURCE_MANIFEST.json",
                        "actual_new_native_steps_already_paid":row["actual_new_native_steps"],
                        "original_measured_sources_sha256":measured["sources"]},"actual_new_physics_by_this_preparation":0})
            matched.append(action_index)
        if sorted(matched) != list(range(5)): raise ValueError("NEW_CLOSED_CONTEXT_MISSING_OR_DUPLICATE_MENU")
        closed.append(group);closure.append({"group":group,"all_children_joined":True,"all_parent_unchanged":True,
                                         "five_unique_full_menu_rows":True,"any_result_or_context_or_raw_opened":True})
    teacher=[];missing=[]
    for group in sorted(contexts):
        choices=[r for r in rows if r["context_group_evaluation_only"]==group]
        available={r["action_index"] for r in choices}
        missing.append({"group":group,"missing_action_indices":sorted(set(range(5))-available),"labels_imputed":0})
        eligible=[r for r in choices if r["labels_evaluation_only"].get("complete") is True and r["labels_evaluation_only"].get("original_qualified") is True and all(finite(r["labels_evaluation_only"].get(k)) for k in ("JF_N_s","JM_Nm_s"))]
        if not eligible: raise ValueError("NO_OBSERVED_COMPLETE_ORIGINAL_QUALIFIED_TEACHER:"+group)
        selected=min(eligible,key=lambda r:(r["labels_evaluation_only"]["JF_N_s"],r["action_index"]))
        base=next(r for r in choices if r["action_index"]==0)["labels_evaluation_only"]
        lab=selected["labels_evaluation_only"]
        teacher.append({"context_group_evaluation_only":group,"source_row_id":selected["id"],"teacher_action_index":selected["action_index"],
                        "teacher_action_name":menu["action_names"][selected["action_index"]],"full_recipe_sha256":selected["full_recipe_sha256"],
                        "teacher_complete_and_qualified":True,"JF_N_s":lab["JF_N_s"],"JM_Nm_s":lab["JM_Nm_s"],
                        "delta_JF_vs_B":lab["JF_N_s"]-base["JF_N_s"],"delta_JM_vs_B":lab["JM_Nm_s"]-base["JM_Nm_s"],
                        "teacher_rule":"OBSERVED_COMPLETE_ORIGINAL_QUALIFIED_MIN_JF_WITHIN_FROZEN_FIVE_TIE_MENU_ORDER"})
    # Equal numerical feature vectors remain visible as a diagnostic, never
    # treated as independent evidence or fed as a parent/case feature.
    duplicate_numeric=[]
    identities={}
    for group,ctx in contexts.items(): identities.setdefault(ctx["causal_features_sha256"],[]).append(group)
    duplicate_numeric=[g for g in identities.values() if len(g)>1]
    unrestricted=[]
    for group in sorted({r["group"] for r in audit}):
        eligible=[r for r in audit if r["group"]==group and r["complete"] is True and r["original_qualified"] is True and finite(r["JF_N_s"]) and finite(r["JM_Nm_s"])]
        if eligible:
            best=min(eligible,key=lambda r:(r["JF_N_s"],r["full_recipe_sha256"]))
            unrestricted.append({"group":group,"unrestricted_historical_best_row":best,
                                 "outside_five_menu":not best["in_frozen_five_menu"],"used_as_five_class_teacher":False if not best["in_frozen_five_menu"] else "COMPARE_FIVE_TEACHER_RULE"})
    for relative,expected in source_hashes.items():
        if sha(package/relative)!=expected: raise ValueError("INPUT_CHANGED_DURING_READ_ONLY_PREPARATION:"+relative)
    document={"schema":"v8.out0_context_aggregation_dataset.v1","status":"COMPLETE_INPUT_READY_FOR_MAIN_REVIEW_NOT_TRAINED" if not pending else "DRAFT_INCOMPLETE_FOUR_CTX_INPUT_NOT_TRAINING_READY",
              "training_ready":not pending,"required_new_groups_evaluation_only":required_groups,"closed_new_groups_evaluation_only":closed,
              "pending_new_groups_not_opened":pending,"closure_audit":closure,"menu":menu,"feature_names":features,
              "contexts_evaluation_only":contexts,"rows":rows,"teacher_labels_training_only":teacher,
              "historical_original_45_source_row_audit":audit,"historical_unrestricted_teacher_audit":unrestricted,
              "excluded_source_rows":excluded,"missing_menu_labels":missing,
              "duplicate_numeric_context_groups_evaluation_only":duplicate_numeric,"source_files_sha256":source_hashes,
              "parent_BC_reference":{"path":parent_path,"policy_behavior_sha_declared_only":None,"normalization":parent["normalization"],"full_source_sha256":source_hashes[parent_path]},
              "new_development_normalization":"NOT_COMPUTED_NO_PREPROCESSING_FIT_AUTHORIZED",
              "model_fit":0,"normalization_fit":0,"model_initializations":0,"model_forward":0,"backward":0,"parameter_updates":0,
              "new_physics":0,"new_env_initializations":0,"data_semantics":"EXPOSED_EPISODE_CONTEXT_AGGREGATION_BC_NOT_NATIVE_EVENT_DAGGER",
              "JF_JM_scalarized":False,"teacher_uses_future_outcomes_only_as_exposed_training_label":True,
              "validation_context_or_results_read":False,"created_unix":time.time()}
    output.mkdir(parents=True)
    target=output/"DATASET_DRAFT.json"
    target.write_text(json.dumps(document,sort_keys=True,indent=2,allow_nan=False)+"\n")
    manifest={"schema":"v8.context_aggregation_preparation_manifest.v1","dataset_file_sha256":sha(target),"dataset_object_sha256":digest(document),
              "status":document["status"],"closed_context_count":len(closed),"total_context_count":len(contexts),"menu_rows":len(rows),
              "original_history_rows":len(audit),"historical_menu_rows":sum(r["origin"]=="HISTORICAL_V2" for r in rows),
              "teacher_labels":len(teacher),"pending_groups_not_opened":pending,"source_files_sha256":source_hashes,
              "preparation_source_sha256":sha(Path(__file__)),"model_fit":0,"normalization_fit":0,"model_forward":0,"parameter_updates":0,"new_physics":0}
    (output/"INPUT_SOURCE_MANIFEST.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--main-agent-authorized-read-only-preparation",action="store_true")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if not args.main_agent_authorized_read_only_preparation: raise ValueError("EXPLICIT_READ_ONLY_PREPARATION_SCOPE_REQUIRED")
    here=Path(__file__).resolve().parent
    output=Path(args.output).resolve()
    if not output.is_relative_to(here) or output.exists():
        raise ValueError("FRESH_ASSIGNED_DIRECTORY_OUTPUT_REQUIRED")
    try:
        result=prepare(here.parents[2],output)
    except BaseException as error:
        failure=output.with_name(output.name+"_PREPARATION_FAILURE.json")
        if not failure.exists():
            failure.write_text(json.dumps({"status":"READ_ONLY_PREPARATION_FAILED_NOT_TRAINED","error_type":type(error).__name__,
                "error":str(error),"source_sha256":sha(Path(__file__)),"created_unix":time.time(),"model_fit":0,
                "normalization_fit":0,"model_forward":0,"parameter_updates":0,"new_physics":0},sort_keys=True,indent=2)+"\n")
        raise
    print(json.dumps({k:v for k,v in result.items() if k!="source_files_sha256"},sort_keys=True))


if __name__=="__main__":
    main()
