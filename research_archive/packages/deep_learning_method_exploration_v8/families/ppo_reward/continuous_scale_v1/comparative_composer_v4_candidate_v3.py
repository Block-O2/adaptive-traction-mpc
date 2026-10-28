"""SOURCE_ONLY: wrap frozen V3; add separately frozen continuous evaluation.

V2 retains the original55 as a subset and uses existing V3 adapter hooks.
No code is executed on import beyond standard-library definitions. Actual use
needs a new root wrapper/config, immutable endpoint inventories and dispatch
approval. Never reads a mutable CURRENT or training pending checkpoint.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time

FAMILY = "families/ppo_reward/continuous_scale_v1/"
V3 = "source/v8_comparative_validation_candidate_v3.py"
V3_SHA = "874fd52f71852480a23fef3aae6b91e494f1e9f6ed7974a6537e38d9b360c2a9"
BETA = FAMILY+"beta_frozen_mean_extension_candidate_v1.py"
BETA_SHA = "4dd92a133c1cc7eecd60b7c51aea66cc360e0692e103a68d65ed02df09f26876"
ORIGINAL55 = FAMILY+"COMPARATIVE_ORIGINAL_55_CORE_LABELS_V1.json"
ORIGINAL55_SHA = "633b7f0d1081554085ed807e28d81248e50dbeed4813b30f20d933d34109372f"
WORKER_SHA = "c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe"
CORE_TAGS = ["B","LATE_H150","EARLY_H150","LATE_PHASE","EARLY_PHASE"]
HARD = ["force","moment","torque","human_speed","human_acceleration","robot_speed",
    "session_clearance","true_clearance","measured_sleeve_clearance","no_shank_table_contact","no_human_rom_violation"]
GRID_TAGS = ["BETA_AXIS_FIXED_L000","BETA_AXIS_FIXED_L025","BETA_AXIS_FIXED_L050","BETA_AXIS_FIXED_L075","BETA_AXIS_FIXED_L100"]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(package,relative):
    path=(package/relative).resolve()
    if not path.is_relative_to(package):raise ValueError("V4_PATH_ESCAPES_PACKAGE")
    return path


def load(package,relative):return json.loads(bounded(package,relative).read_text())


def required(package,config,ref):
    if config["frozen_artifacts"].get(ref["path"])!=ref["sha256"] or sha(bounded(package,ref["path"]))!=ref["sha256"]:
        raise ValueError("V4_ACTUAL_SOURCE_OR_INPUT_NOT_JOB_FROZEN:"+ref["path"])
    return bounded(package,ref["path"])


def immutable_inventory(package,config,ref):
    """Reject mutable run aliases; only actual immutable inventory JSON is read."""
    required(package,config,ref)
    def inspect(value):
        if isinstance(value,dict):
            if isinstance(value.get("path"),str):
                relative=value["path"];name=Path(relative).name.upper()
                if (name.startswith("CURRENT") or "PENDING" in name or "SAMPLING" in name or
                        any(part.lower() in ("pending_inputs","sampling") for part in Path(relative).parts)):
                    raise ValueError("V4_NO_MUTABLE_RUN_OR_SAMPLING_STATE_IN_FROZEN_INVENTORY")
            for child in value.values():inspect(child)
        elif isinstance(value,list):
            for child in value:inspect(child)
    document=load(package,ref["path"]);inspect(document)
    return document


def module_at(package,name,ref,config):
    actual=required(package,config,ref)
    if name in sys.modules:raise ValueError("V4_FRESH_PRIVATE_MODULE_NAME_REQUIRED")
    spec=importlib.util.spec_from_file_location(name,actual)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name,None);raise
    return module


def _attempt_original_evidence(package,config,study,tag):
    """Only the just-joined current-job child is read. No new scorer/model call."""
    ident=config["group"]+"_"+tag
    row=copy.deepcopy(study.last_row)
    if row.get("id")!=ident or getattr(study,"active_owned_child_pid",None) is not None:
        raise ValueError("V4_NOT_EXACT_JOINED_CURRENT_CHILD")
    result_path="attempts/"+ident+"_RESULT.json";original=load(package,result_path)
    for key in ("id","complete","qualified","error","actual_new_native_steps"):
        if original.get(key)!=row.get(key):raise ValueError("V4_ROW_NOT_ORIGINAL_RESULT:"+key)
    events={}
    for raw in bounded(package,"runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
        event=json.loads(raw)
        if event.get("id")!=ident or event.get("event") not in ("START","END"):continue
        if event["event"] in events:raise ValueError("V4_DUPLICATE_ORIGINAL_ATTEMPT_EVENT")
        events[event["event"]]={"record":event,"raw_line_without_newline_sha256":hashlib.sha256(raw).hexdigest()}
    if set(events)!={"START","END"}:raise ValueError("V4_ORIGINAL_CHILD_START_END_MISSING")
    if events["END"]["record"].get("joined") is not True or events["END"]["record"].get("parent_hash_equal") is not True:
        raise ValueError("V4_ORIGINAL_CHILD_NOT_JOINED_OR_PARENT_PREFIX_CHANGED")
    if events["START"]["record"].get("config_sha256")!=sha(package/"experiments"/(config["group"]+".json")):
        raise ValueError("V4_ORIGINAL_START_NOT_ACTUAL_FROZEN_JOB")
    metrics=None;safety_source=None
    if row.get("complete") is True:
        safety_source=row["metrics_path"];metrics=load(package,safety_source)
        common=metrics.get("native_physical_audit",{}).get("unchanged_evaluator",{}).get("physical_task_result",{}).get("scorer_v2_common_conditions",{})
    else:
        common=row.get("protected_task_failure",{}).get("hard_safety_conditions",{})
        safety_source=result_path
    conditions={key:common.get(key) for key in HARD}
    hard=True if row.get("true_hard_safety_violation") is True or any(value is False for value in conditions.values()) else False if all(value is True for value in conditions.values()) else None
    return {"tag":tag,"original_row":row,"original_result":{"path":result_path,"sha256":sha(package/result_path)},
        "original_events":events,"hard_safety_conditions":conditions,"true_hard_safety_violation":hard,
        "safety_source":{"path":safety_source,"sha256":sha(package/safety_source)},
        "complete":row.get("complete"),"qualified":row.get("qualified"),"metrics":metrics,
        "partial_error_and_actual_native_steps_preserved":True,"no_new_physics_or_scorer_call":True}


def _continuous_plan(beta,menu,hashes):
    if (beta.get("schema")!="v8.beta.continuous_mean_and_grid_extras_before_B.v1" or
            beta.get("all_choices_before_any_B_result") is not True or len(beta["continuous_decisions"])!=12 or
            set(beta["fixed_axis_controls"])!=set(GRID_TAGS)):
        raise ValueError("V4_INDEPENDENT_CONTINUOUS_SCHEMA_12_MEANS_AND_FIVE_GRID_REQUIRED")
    if beta["actual_counts"].get("deploy_mean_entry")!=12 or beta["actual_counts"].get("logical_policy_deepcopies")!=12:
        raise ValueError("V4_ACTUAL_ALL_TWELVE_LOGICAL_MEAN_CALLS_REQUIRED_EVEN_IF_ALIASED")
    if any(beta["actual_counts"].get(key)!=0 for key in ("restore","BetaArm_constructor","initialize","RNG_draws","fit_gradient_or_update","new_physics")):
        raise ValueError("V4_BETA_EXTENSION_MUST_BE_FROZEN_FORWARD_ONLY")
    catalog=beta["full_recipe_catalog"]
    for key,item in catalog.items():
        if digest(item["full_recipe"])!=key or item["full_recipe"]["action"]!=item["actual_action"]:
            raise ValueError("V4_ACTUAL_CONTINUOUS_FULLRECIPE_AND_ACTION_BINDING")
    preferred=["BETA_AXIS_FIXED_L100"]+list(beta["continuous_decisions"])+GRID_TAGS[:4]
    plan=[];seen=set();aliases={};core_aliases={}
    for name in preferred:
        decision=beta["fixed_axis_controls"].get(name,beta["continuous_decisions"].get(name))
        key=decision.get("full_recipe_sha256")
        if key is None:
            fallback=decision.get("fallback_core",{})
            if fallback.get("tag")!="B" or fallback.get("recipe_sha256")!=hashes[0] or fallback.get("action")!=menu[0]["action"]:
                raise ValueError("V4_MEAN_REJECTION_REQUIRES_EXPLICIT_ORIGINAL_B_FALLBACK")
            core_aliases[name]={"tag":"B","reason":"REJECTED_BETA_PREDICTION_SAFE_ANCHOR_OUTSIDE_AXIS_NOT_SUCCESS"}
            continue
        if key not in catalog or decision["proposal_action"]!=catalog[key]["actual_action"]:
            raise ValueError("V4_CONTINUOUS_DECISION_NOT_ACTUAL_RECIPE_CATALOG")
        if key in seen:
            aliases[name]=next(item["tag"] for item in plan if item["full_recipe_sha256"]==key)
            continue
        if key in hashes and name!="BETA_AXIS_FIXED_L100":
            index=hashes.index(key)
            if catalog[key]["full_recipe"]!=menu[index] or catalog[key]["actual_action"]!=menu[index]["action"]:
                raise ValueError("V4_SAME_HASH_CORE_CONTINUOUS_DIFFERENT_ACTUAL_RECIPE")
            core_aliases[name]={"tag":CORE_TAGS[index],"reason":"IDENTICAL_COMPLETE_RECIPE_SHARED_EVALUATION_NOT_REPLICATION"}
            continue
        tag="BETA_AXIS_L100_REPEAT" if name=="BETA_AXIS_FIXED_L100" else name if name in GRID_TAGS else "BETA_MEAN_UNIQUE_"+str(len(plan)).zfill(2)
        item={"tag":tag,"action":copy.deepcopy(catalog[key]["actual_action"]),"full_recipe":copy.deepcopy(catalog[key]["full_recipe"]),
            "full_recipe_sha256":key,"selected_by":list(catalog[key]["selected_by"]),"permission":"CONTINUOUS_SCALAR_AXIS",
            "all_mean_and_grid_choices_frozen_before_B":True}
        if name=="BETA_AXIS_FIXED_L100":item["repeat_of"]="EARLY_H150"
        plan.append(item);aliases[name]=tag;seen.add(key)
    if not plan or plan[0]["tag"]!="BETA_AXIS_L100_REPEAT" or plan[0]["repeat_of"]!="EARLY_H150":
        raise ValueError("V4_LAMBDA1_NEW_PAID_REPEAT_MUST_PRECEDE_ALL_OTHER_CONTINUOUS_ATTEMPTS")
    return plan,aliases,core_aliases


def sequence(study,config):
    owner_pid=os.getpid();package=Path(os.environ["ACL2_PACKAGE"]).resolve()
    from acl2_shared import append,put
    group=config["group"];legacy=None;legacy_exhausted=False
    counts={"preserved_V3_next_entry":0,"preserved_V3_yielded":0,"beta_extension_entry":0,"beta_extension_completed":0,
        "physical_proposals_yielded_to_original_worker":0,
        "new_fit":0,"initialize":0,"restore":0,"RNG_draws":0,"new_physics_dispatched_directly_by_composer":0}
    completed=[];branch_records={};continuous=[];all_core={};beta=None;mapping_gate=None;continuous_stop=None;pending_tag=None
    def owner():
        if os.getpid()!=owner_pid:raise GeneratorExit("V4_CHILD_HAS_NO_SHARED_WRITE_AUTHORITY")
    def save(relative,value):owner();put(relative,value)
    def freeze_all():
        owner()
        for relative,expected in config["frozen_artifacts"].items():
            if sha(bounded(package,relative))!=expected:raise ValueError("V4_FROZEN_DEPENDENCY_CHANGED:"+relative)
    def advance():
        owner();counts["preserved_V3_next_entry"]+=1
        value=next(legacy);counts["preserved_V3_yielded"]+=1;return value
    def audit(tag):
        owner();record=_attempt_original_evidence(package,config,study,tag)
        branch_records[tag]=record;completed.append(tag)
        save("analysis/"+group+"_V4_BRANCH_"+tag+".json",record)
        if record["true_hard_safety_violation"] is True:raise RuntimeError("V4_TRUE_HARD_SAFETY_STOP")
        if record["true_hard_safety_violation"] is not False:raise RuntimeError("V4_UNKNOWN_HARD_SAFETY_STOP_NO_SUCCESS_IMPUTATION")
        return record
    try:
        owner();freeze_all()
        self_relative=str(Path(__file__).resolve().relative_to(package))
        required(package,config,{"path":self_relative,"sha256":sha(Path(__file__))})
        required(package,config,{"path":"source/v8_worker_v2.py","sha256":WORKER_SHA})
        if config.get("worker")!="v8_worker_v2.py":raise ValueError("V4_REVIEWED_ORIGINAL_WORKER_V2_REQUIRED")
        if study.metrics or study.child is not None or study.fork_done is not True or config.get("onpolicy_sampling"):
            raise ValueError("V4_COLD_OUT0_FROZEN_EVALUATION_ONLY_NOT_TRAINING_SAMPLER")
        spec=config["comparative_composer_v4"]
        if (spec.get("schema")!="v8.comparative_composer_v4_job.v2" or spec.get("status")!="APPROVED_BY_MAIN_AGENT" or
                spec.get("no_training") is not True or spec.get("no_outcome_reselection") is not True or
                spec.get("root_postclosure_raw_and_scorer_review_required") is not True):
            raise ValueError("V4_SEPARATE_NEW_ROOT_CONFIG_AND_REVIEW_REQUIRED")
        if spec["preserved_v3"]!={"path":V3,"sha256":V3_SHA} or spec["beta_mean_extension"]!={"path":BETA,"sha256":BETA_SHA}:
            raise ValueError("V4_EXACT_REVIEWED_V3_AND_BETA_SOURCE_BODIES_REQUIRED")
        expected_core_count=spec.get("expected_core_pre_B_decision_count")
        if type(expected_core_count) is not int or expected_core_count<55:
            raise ValueError("V4_EXACT_EXPECTED_CORE_TOTAL_REQUIRED_ORIGINAL55_IS_ONLY_SUBSET")
        if "future_frozen_core_extensions" in spec:
            raise ValueError("V4_USE_EXISTING_V3_PARALLEL_SELECTOR_ADAPTERS_NO_NEW_GENERIC_HOOKS")
        required(package,config,{"path":ORIGINAL55,"sha256":ORIGINAL55_SHA})
        original_subset=load(package,ORIGINAL55)
        original_labels=original_subset["labels"]
        if (original_subset.get("schema")!="v8.comparative_original_55_core_selector_labels.v1" or
                len(original_labels)!=55 or len(set(original_labels))!=55):
            raise ValueError("V4_FIXED_ORIGINAL55_LABEL_ARTIFACT_INVALID")
        original=module_at(package,"_v4_preserved_v3_"+group,spec["preserved_v3"],config)
        legacy=original.sequence(study,config)
        # V3 itself invokes its configured parallel_selector_adapters (including
        # separately approved Neural/E2 additions). Its first yield is unrun B.
        first=advance()
        if first.get("tag")!="B" or study.metrics:raise ValueError("V4_V3_FIRST_YIELD_MUST_BE_UNEXECUTED_B")
        v3_path="predictions/"+group+"_FROZEN_CONTEXT_DECISIONS.json"
        v3_record=load(package,v3_path)
        if (len(v3_record["decisions"])!=expected_core_count or
                not set(original_labels).issubset(v3_record["decisions"]) or
                v3_record.get("before_any_candidate_outcome") is not True):
            raise ValueError("V4_CORE_TOTAL_MUST_MATCH_REGISTERED_COUNT_AND_PRESERVE_ORIGINAL55_SUBSET")
        all_core=copy.deepcopy(v3_record["decisions"])
        core_spec=config["comparative_validation"]
        menu=load(package,core_spec["menu_path"])["action_contracts"]
        hashes=[digest(item) for item in menu]
        if len(set(hashes))!=5 or [item["tag"] for item in config["actions"]]!=CORE_TAGS or [a["action"] for a in config["actions"]]!=[r["action"] for r in menu]:
            raise ValueError("V4_ORIGINAL_ACTUAL_FIVE_RECIPE_PERMISSION")
        for label,decision in all_core.items():
            index=hashes.index(decision["choice_recipe_sha256"])
            if decision["choice_tag"]!=CORE_TAGS[index] or decision["choice_action"]!=menu[index]["action"]:
                raise ValueError("V4_PRESERVED_CORE_DECISION_ACTION_IDENTITY:"+label)
        # All core5 additions were computed by the existing frozen V3 adapter
        # mechanism. Logical selectors and nested forwards remain distinct;
        # e.g. a future 68-selector/63-forward Neural extension is not counted
        # as 68 forwards here. Original V3 counters/extension records are kept.
        immutable_inventory(package,config,config["beta_mean_extension"]["inventory"])
        beta_api=module_at(package,"_v4_beta_mean_"+group,spec["beta_mean_extension"],config)
        counts["beta_extension_entry"]+=1
        beta=beta_api.predict_before_B(package,config,study)
        counts["beta_extension_completed"]+=1
        if study.metrics or beta["context25"]["feature_names"]!=v3_record["context25"]["feature_names"] or beta["context25"]["features"]!=v3_record["context25"]["features"]:
            raise ValueError("V4_SAME_ACTUAL_COMMISSIONED25_AND_ALL_SELECTIONS_BEFORE_B")
        continuous,aliases,core_aliases=_continuous_plan(beta,menu,hashes)
        save("predictions/"+group+"_V4_ALL_PRE_B_DECISIONS.json",{
            "schema":"v8.comparative_v4_all_pre_B_decisions.v2","owner_pid":owner_pid,"created_unix":time.time(),
            "preserved_V3_record":{"path":v3_path,"sha256":sha(package/v3_path)},
            "actual_core_pre_B_logical_decision_count":len(all_core),"expected_core_pre_B_decision_count":expected_core_count,
            "original55_fixed_subset":{"path":ORIGINAL55,"sha256":ORIGINAL55_SHA,"labels":original_labels},
            "additional_core_labels_via_existing_V3_adapters":[label for label in all_core if label not in original_labels],
            "five_recipe_decisions":all_core,
            "preserved_V3_actual_API_accounting":{"counts":v3_record["counts"],
                "nested_A_inference_API_calls":v3_record["nested_A_inference_API_calls"],
                "extension_records":v3_record["extension_records"]},
            "independent_continuous_extension":beta,"continuous_execution_plan":continuous,
            "continuous_exact_recipe_aliases":aliases,"explicit_core_alias_or_B_fallback":core_aliases,
            "possible_C_history_B_is_selected_after_B_not_pre_B":True,"all_current_choices_before_B":True,
            "permission_sets_not_pooled_as_same_action_space_rankings":True,"counts":counts})
        proposal=first
        while True:
            owner();freeze_all()
            tag=proposal["tag"]
            outgoing=copy.deepcopy(proposal)
            outgoing.setdefault("prediction",{})["V4_continuous_safe_anchor_or_exact_alias_labels"]=[label for label,d in core_aliases.items() if d["tag"]==tag]
            pending_tag=tag
            counts["physical_proposals_yielded_to_original_worker"]+=1
            yield outgoing
            record=audit(tag)
            pending_tag=None
            if tag=="B" and (record["complete"] is not True or record["qualified"] is not True):
                raise RuntimeError("V4_ORIGINAL_B_COMPLETE_QUALIFIED_WHOLE_JOB_GATE")
            try:proposal=advance()
            except StopIteration:
                legacy_exhausted=True;break
        # The exact original V3 generator completed: C5 stayed after B, with
        # its original HISTORY_B replay in the original relative order.
        original_link=load(package,"analysis/"+group+"_SELECTOR_EXECUTION_LINK.json")
        if len(original_link["history_decisions"])!=5:raise ValueError("V4_ORIGINAL_C_FIVE_AFTER_B_DECISIONS_REQUIRED")
        early=branch_records.get("EARLY_H150")
        if early is None or early["complete"] is not True:
            mapping_gate={"status":"NOT_RUN_ORIGINAL_EARLY_H150_PARTIAL","qualification_used_as_filter":False,
                "continuous_tags_not_run":[item["tag"] for item in continuous],"success_imputed":False}
        else:
            for position,item in enumerate(continuous):
                owner();freeze_all()
                if position>0 and mapping_gate.get("status")!="PASS_NEW_PAID_RAW_AND_FULL_COMPLETION_MATCH":
                    break
                action={"tag":item["tag"],"action":copy.deepcopy(item["action"]),"category":"FROZEN_CONTINUOUS_AXIS_MATCHED_EVALUATION",
                    "prediction":{"permission":"CONTINUOUS_SCALAR_AXIS","full_recipe_sha256":item["full_recipe_sha256"],
                        "selected_by":item["selected_by"],"all_decisions_frozen_before_B":True,
                        "shared_actual_recipe_not_independent_replication_or_attempt_savings":True}}
                if "repeat_of" in item:action["repeat_of"]=item["repeat_of"]
                pending_tag=item["tag"]
                counts["physical_proposals_yielded_to_original_worker"]+=1
                yield action
                record=audit(item["tag"])
                pending_tag=None
                if position==0:
                    gate_path="audit/"+group+"_"+item["tag"]+"_REPEAT_GATE.json"
                    gate=load(package,gate_path)
                    expected_a=(package/"runtime/source/results"/(group+"_EARLY_H150")).resolve()
                    expected_b=(package/"runtime/source/results"/(group+"_"+item["tag"])).resolve()
                    if gate.get("status")!="PASS" or Path(gate["a"]).resolve()!=expected_a or Path(gate["b"]).resolve()!=expected_b:
                        raise RuntimeError("V4_NEW_PAID_LAMBDA1_EARLY_H150_RAW_REPEAT_GATE_FAILED")
                    complete=record["complete"] is True
                    if complete:
                        a=early["original_row"];b=record["original_row"]
                        for key in ("JF","JM","axes","qualified"):
                            if a.get(key)!=b.get(key):raise RuntimeError("V4_RAW_EQUAL_BUT_ORIGINAL_SCORER_RESULT_DIFFERS:"+key)
                    mapping_gate={"status":"PASS_NEW_PAID_RAW_AND_FULL_COMPLETION_MATCH" if complete else "STOP_LAMBDA1_PARTIAL_NO_OTHER_CONTINUOUS_RUN",
                        "raw_gate":{"path":gate_path,"sha256":sha(package/gate_path)},
                        "original_EARLY_H150_qualified":early["qualified"],"lambda1_qualified":record["qualified"],
                        "qualification_used_as_filter":False,"root_closed_original_scorer_replay_still_required":True,"success_imputed":False}
                    save("analysis/"+group+"_V4_CONTINUOUS_MAPPING_GATE.json",mapping_gate)
                    if not complete:break
                elif record["complete"] is not True:
                    continuous_stop={"status":"STOP_REST_AFTER_ORIGINAL_CONTINUOUS_ENGINEERING_PARTIAL",
                        "tag":item["tag"],"original_result":record["original_result"],"success_imputed":False}
                    break
        save("analysis/"+group+"_V4_SELECTOR_EXECUTION_LINK.json",{
            "schema":"v8.comparative_v4_execution_link.v2","five_recipe_pre_B_decisions":all_core,
            "actual_core_pre_B_logical_decision_count":len(all_core),"expected_core_pre_B_decision_count":expected_core_count,
            "original55_fixed_subset":{"path":ORIGINAL55,"sha256":ORIGINAL55_SHA,"labels":original_labels},
            "original_C_after_B_three_recipe_decisions":original_link["history_decisions"],
            "continuous_decisions_and_fixed_grid":beta,"mapping_gate":mapping_gate,"continuous_stop":continuous_stop,
            "completed_tags":completed,"continuous_NOT_RUN":[item["tag"] for item in continuous if item["tag"] not in completed],
            "original_partial_errors_and_paid_work":branch_records,"counts":counts,
            "original_V3_final_counts":original_link["counts"],"actual_beta_counts":beta["actual_counts"],
            "permission_sets_reported_separately":True,"new_training":False,"no_outcome_based_reselection":True,
            "root_parent_closure_original_raw_scorer_and_actual_step_audit_still_required":True})
    except GeneratorExit:
        if os.getpid()!=owner_pid:return
        closing_result=None
        if pending_tag and getattr(study,"last_row",{}).get("id")==group+"_"+pending_tag:
            try:closing_result=_attempt_original_evidence(package,config,study,pending_tag)
            except BaseException as close_error:
                closing_result={"status":"ORIGINAL_WORKER_RESULT_REQUIRES_ROOT_CLOSURE_REVIEW","error_type":type(close_error).__name__,"error":str(close_error)}
        save("analysis/"+group+"_V4_OWNER_CLOSE.json",{"status":"OWNER_CLOSED_PRESERVE_ALL_ORIGINAL_EVIDENCE","counts":counts,
            "completed_tags":completed,"last_yielded_unreconciled_tag":pending_tag,"original_just_returned_worker_result":closing_result,
            "continuous_NOT_RUN_OR_UNRECONCILED":[item["tag"] for item in continuous if item["tag"] not in completed]})
        return
    except BaseException as error:
        if os.getpid()!=owner_pid:return
        save("analysis/"+group+"_V4_COMPOSER_ERROR.json",{"error_type":type(error).__name__,"error":str(error),"counts":counts,
            "completed_tags":completed,"last_yielded_unreconciled_tag":pending_tag,
            "continuous_NOT_RUN_OR_UNRECONCILED":[item["tag"] for item in continuous if item["tag"] not in completed],
            "beta_failed_paid_work":getattr(error,"beta_mean_extension_consumed_work",None),
            "core_nested_failed_paid_work_requires_original_V3_and_adapter_evidence":True,
            "original_partial_errors_and_paid_work":branch_records,"no_missing_result_success_imputation":True})
        raise
    finally:
        # No child destructor may close a parent-owned generator or write its
        # close/error files. Dropping the child reference lets V3's own guarded
        # GeneratorExit handler return silently in that child.
        if os.getpid()==owner_pid and legacy is not None and not legacy_exhausted:
            legacy.close()
