"""Beta-specific real-artifact adapter candidate; no writes or model calls.

Uses the reviewed root V2 read-only _binding function. Scalar proposal
schema and physical_receipt fields are intentionally distinct from categorical.
"""
from pathlib import Path
import copy
import importlib.util
import json
import math
import sys

from beta_sampling_common_v1 import bounded_path,canonical,digest,load,sha

ADAPTER_SCHEMA="v8.reviewed_continuous_beta_receipt_adapter.v1"
HARD=["force","moment","torque","human_speed","human_acceleration","robot_speed","session_clearance","true_clearance","measured_sleeve_clearance","no_shank_table_contact","no_human_rom_violation"]


def _reference(package,config):
    spec=config["onpolicy_sampling"]
    if spec.get("schema")!="v8.continuous_beta_sampling_job.v1":raise ValueError("BETA_SCHEMA_NOT_CATEGORICAL_JOB")
    relative="source/v8_onpolicy_receipt_adapter_v2.py"
    if relative not in config["frozen_artifacts"]:raise ValueError("ROOT_REVIEWED_BINDING_SOURCE_NOT_FROZEN")
    path=bounded_path(package,relative)
    if sha(path)!=config["frozen_artifacts"][relative]:raise ValueError("ROOT_REVIEWED_BINDING_CHANGED")
    loader=importlib.util.spec_from_file_location("_beta_root_reviewed_receipt_binding_v2",path)
    module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
    if module.ADAPTER_SCHEMA!="v8.reviewed_onpolicy_receipt_adapter.v1":raise ValueError("ROOT_BINDING_SCHEMA_CHANGED")
    return module


def build_baseline_receipt(*,package,config,context25,logical_context_id,row):
    reference=_reference(package,config)
    b=reference._binding(package,config,context25,logical_context_id,row)
    end=b["events"]["END"]["record"]
    if row["id"]!=config["group"]+"_B" or row["action"]!={"family":"B"} or row.get("complete") is not True or row.get("qualified") is not True:
        raise ValueError("ACTUAL_FULL_ORIGINAL_B_QUALIFICATION_REQUIRED")
    if end.get("returncode")!=0 or end.get("joined") is not True or end.get("parent_hash_equal") is not True:
        raise ValueError("ACTUAL_B_JOIN_AND_PARENT_UNCHANGED_REQUIRED")
    return {"schema":"v8.beta_original_B_baseline_receipt.v1","complete":True,"original_qualified":True,
        "JF_N_s":row["JF"],"JM_Nm_s":row["JM"],"result_source_sha256":sha(b["result_path"]),
        "result_path":str(b["result_path"].relative_to(b["package"])),"context_group_evaluation_only":logical_context_id,
        "causal_features_sha256":b["context_sha"],"case_sha256_evaluation_only":config["case_sha256"],
        "events_original_records_and_hash_scopes":b["events"],"original_worker_result":canonical(row),
        "completed_original_B_not_a_training_sample":True,
        "B_is_outside_beta_curve_support":True,"not_a_Beta_training_sample":True}


def _guard_fallback_fields(value,pointer=""):
    """Preserve actual named evidence; do not synthesize a safe/default value."""
    found=[]
    if isinstance(value,dict):
        for key,child in value.items():
            path=pointer+"/"+str(key).replace("~","~0").replace("/","~1")
            if any(token in str(key).lower() for token in ("guard","fallback","reject","activation")):
                found.append({"original_json_pointer":path,"actual_value":copy.deepcopy(child)})
            else:found.extend(_guard_fallback_fields(child,path))
    elif isinstance(value,list):
        for index,child in enumerate(value):found.extend(_guard_fallback_fields(child,pointer+"/"+str(index)))
    return found


def build_onpolicy_receipt(*,package,config,context25,logical_context_id,proposal,row):
    reference=_reference(package,config)
    b=reference._binding(package,config,context25,logical_context_id,row)
    P=b["package"];ident=b["id"];p=canonical(proposal);sample=p["sample"]
    if p.get("schema")!="v8.continuous_beta_physical_proposal.v1" or p.get("physical_receipt") is not None or p.get("data_semantics")!="GENUINE_NEW_ON_POLICY_CONTINUOUS_SCALAR_ROLLOUT":
        raise ValueError("ACTUAL_BETA_UNJOINED_PROPOSAL_SCHEMA_REQUIRED")
    body=copy.deepcopy(p);identity=body.pop("proposal_identity_sha256")
    if digest(body)!=identity:raise ValueError("BETA_ACTUAL_CANONICAL_PROPOSAL_IDENTITY")
    if p["attempt_id"]!=ident or p["context_group_evaluation_only"]!=logical_context_id or p["causal_features_sha256"]!=b["context_sha"]:
        raise ValueError("BETA_PHYSICAL_ATTEMPT_CONTEXT_BINDING")
    lam=sample["lambda_sample"]
    if isinstance(lam,bool) or not isinstance(lam,(int,float)) or not math.isfinite(lam) or not 0<lam<1 or sample.get("post_sampling_clip") is not False or sample.get("deterministic_mean_deployment") is not False or sample.get("sampling_measure")!="scalar Lebesgue d_lambda" or not math.isfinite(sample["old_logprob"]):
        raise ValueError("ACTUAL_INTERIOR_UNCLIPPED_BETA_SCALAR_SAMPLE_REQUIRED")
    spec=config["onpolicy_sampling"]
    axis=load(bounded_path(P,spec["axis_path"]))
    if sha(bounded_path(P,spec["axis_path"]))!=spec["axis_file_sha256"] or digest(axis)!=spec["axis_object_sha256"]:
        raise ValueError("ACTUAL_FROZEN_AXIS_JSON_CHANGED")
    from axis_mapping import map_lambda
    mapped=map_lambda(axis,lam,expected_axis_sha256=spec["axis_object_sha256"])
    if digest(sample["full_recipe"])!=sample["full_recipe_sha256"] or digest(sample["proposal_action"])!=sample["physical_action_sha256"] or digest(mapped["full_recipe"])!=sample["full_recipe_sha256"] or digest(row["action"])!=digest(sample["proposal_action"]):
        raise ValueError("BETA_ACTUAL_LAMBDA_FULL_RECIPE_ACTION_BINDING")
    prediction_path=P/"predictions"/(ident+".json");prediction=load(prediction_path)
    for field,expected in {"proposal_identity_sha256":identity,"collection_policy_sha256":sample["policy_sha256"],
                           "old_scalar_logdensity":sample["old_logprob"],"selected_lambda":lam,
                           "axis_contract_sha256":sample["axis_contract_sha256"],
                           "selected_physical_action_sha256":sample["physical_action_sha256"],
                           "full_recipe_sha256":sample["full_recipe_sha256"],
                           "rng_before_canonical_sha256":digest(sample["rng_before"]),
                           "rng_after_canonical_sha256":digest(sample["rng_after"])}.items():
        if prediction.get(field)!=expected:raise ValueError("ACTUAL_BETA_PREDICTION_BINDING:"+field)
    start=b["events"]["START"]["record"]
    if prediction["created_unix"]>start["unix"]:raise ValueError("BETA_PROPOSAL_AFTER_PHYSICS")
    if prediction["sampling_parent_pid"]!=start["pid"] or prediction["sampling_parent_start_ticks"]!=start["start_ticks"]:
        raise ValueError("ORIGINAL_GENERATOR_PARENT_EVENT_AUTHORITY")
    proposal_path=bounded_path(P,prediction["proposal_path"])
    if sha(proposal_path)!=prediction["proposal_file_sha256"] or digest(load(proposal_path))!=digest(p):
        raise ValueError("BETA_PRESAMPLED_CANONICAL_JSON_NOT_EXACT")
    measured_path=bounded_path(P,row["metrics_path"]) if row.get("metrics_path") else None
    measured=load(measured_path) if measured_path and measured_path.is_file() else None
    data_path=P/"runtime/output"/(ident+"_DATA.json")
    data=load(data_path) if data_path.is_file() else None
    audit=(measured or {}).get("native_physical_audit") or (data or {}).get("metric",{}).get("physical_audit",{})
    common=audit.get("unchanged_evaluator",{}).get("physical_task_result",{}).get("scorer_v2_common_conditions",{})
    hard=True if any(common.get(k) is False for k in HARD) else False if all(common.get(k) is True for k in HARD) else None
    lineage_path=Path(measured["execution_lineage_path"]).resolve() if measured and measured.get("execution_lineage_path") else None
    if lineage_path is not None and not lineage_path.is_relative_to(P.resolve()):raise ValueError("BETA_LINEAGE_PATH_ESCAPE")
    lineage=load(lineage_path) if lineage_path and lineage_path.is_file() else None
    owns=bool(lineage and lineage.get("status")=="PASS" and lineage.get("ownership_error_count")==0 and measured["axes"].get("SCIENTIFIC_EXECUTION_CAUSAL_VALID")=="PASS")
    raw=P/"runtime/source/results"/ident/"runtime_artifacts.json.gz"
    stream_sha=None;receipts=positive=positive_steps=0
    if raw.is_file():
        relative="runtime/code/stream_runtime_evidence.py"
        if sha(P/relative)!=config["frozen_artifacts"][relative]:raise ValueError("FROZEN_STREAM_READER_CHANGED")
        sys.path.insert(0,str(P/"runtime/code"))
        from stream_runtime_evidence import array_items
        if Path(sys.modules[array_items.__module__].__file__).resolve()!=P/relative:
            raise ValueError("WRONG_LOADED_ORIGINAL_STREAM_READER")
        import hashlib
        stream=hashlib.sha256()
        for receipt in array_items(raw,"command_receipts"):
            stream.update(json.dumps(receipt,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()+b"\n")
            receipts+=1
            if receipt.get("applied") is True and isinstance(receipt.get("native_steps"),int) and receipt["native_steps"]>0:
                positive+=1;positive_steps+=receipt["native_steps"]
        stream_sha=stream.hexdigest() if receipts else None
    end=b["events"]["END"]["record"]
    engineering=bool(row.get("complete") is True and row.get("error") is None and end.get("returncode")==0 and end.get("joined") is True and end.get("parent_hash_equal") is True and owns and hard is not None)
    protected=bool(isinstance(row.get("protected_task_failure"),dict) and hard is False)
    summary_path=P/"runtime/source/results"/ident/"summary.json"
    summary=load(summary_path) if summary_path.is_file() else None
    execution_binding_path=P/"attempts"/(ident+"_EXECUTION_BINDING.json")
    execution_binding=load(execution_binding_path) if execution_binding_path.is_file() else None
    if execution_binding:
        candidate=copy.deepcopy(execution_binding["candidate"]);candidate.pop("id",None)
        if digest(execution_binding["action"])!=digest(sample["proposal_action"]) or digest(candidate)!=digest(sample["full_recipe"]["resolved_base_candidate"]):
            raise ValueError("ACTUAL_BETA_EXECUTION_BINDING_CANDIDATE_CHANGED")
    engineering=bool(engineering and execution_binding is not None and summary is not None and stream_sha is not None and positive>0)
    sources={}
    for path in (b["result_path"],prediction_path,proposal_path,measured_path,data_path,lineage_path,summary_path,execution_binding_path):
        if path and path.is_file():sources[str(path.relative_to(P))]=sha(path)
    if isinstance(row.get("actual_new_native_steps"),bool):raise ValueError("ACTUAL_NATIVE_STEPS_CANNOT_BE_BOOLEAN")
    return {"schema":"v8.continuous_beta_physical_receipt.v1","attempt_id":ident,"arm_id":p["arm_id"],
        "proposal_identity_sha256":identity,"axis_contract_sha256":sample["axis_contract_sha256"],"selected_lambda":lam,
        "selected_physical_action_sha256":sample["physical_action_sha256"],"selected_full_recipe_sha256":sample["full_recipe_sha256"],
        "context_group_evaluation_only":logical_context_id,"causal_features_sha256":b["context_sha"],
        "genuine_new_physical_attempt":True,"historical_or_cached_outcome":False,
        "attempt_start_sha256":b["events"]["START"]["canonical_record_sha256"],"attempt_end_sha256":b["events"]["END"]["canonical_record_sha256"],
        "result_source_sha256":sha(b["result_path"]),"native_ownership_sha256":sha(lineage_path) if lineage_path and lineage_path.is_file() else None,
        "applied_reference_receipt_stream_sha256":stream_sha,"actual_new_native_steps":row.get("actual_new_native_steps"),
        "engineering_complete":engineering,"ownership_and_causality_audit_pass":owns,"complete":row.get("complete"),
        "original_qualified":row.get("qualified"),"protected_task_failure":protected,"true_hard_safety_violation":hard,
        "JF_N_s":row.get("JF"),"JM_Nm_s":row.get("JM"),"original_motion_failure_requirements":row.get("motion_vs_B",{}).get("failed_requirements"),
        "original_worker_result":canonical(row),
        "requested_vs_actual_execution_metadata":{"requested_old18d_parameters":sample["proposal_action"]["parameters"],
            "original_execution_rows":copy.deepcopy(row.get("execution")),"requested_parameters_are_not_an_activation_certificate":True},
        "events_original_records_and_hash_scopes":b["events"],"original_artifact_files_sha256":sources,
        "case_sha256_evaluation_only":config["case_sha256"],
        "safety_source":{"path":str(measured_path.relative_to(P)) if measured_path else str(data_path.relative_to(P)),"required_common_conditions":{k:common.get(k) for k in HARD},"unknown_is_not_false":True},
        "ownership_source":{"path":str(lineage_path.relative_to(P)) if lineage_path else None,"original_lineage_status":lineage.get("status") if lineage else None,"original_lineage_join_kind":lineage.get("join_kind") if lineage else None,"null_request_ids_not_fabricated":True},
        "applied_stream_scope":{"path":str(raw.relative_to(P)),"container_sha256":sha(raw) if raw.is_file() else None,
            "hash_definition":"sha256 every original command_receipts object as sorted compact ensure_ascii=False UTF-8 JSON plus newline; original order; includes inherited prefix",
            "receipt_count":receipts,"positive_step_receipts":positive,"archived_positive_native_steps_including_inherited_prefix":positive_steps,
            "selected_lambda_not_claimed_to_own_every_archived_native_step":True},
        "original_guard_fallback_evidence":{"summary_actual_fields":_guard_fallback_fields(summary) if summary else [],"audit_actual_fields":_guard_fallback_fields(audit),"result_actual_fields":_guard_fallback_fields(row)},
        "event_pid_semantics":"Original START/END writer is fork parent; never relabeled as physical child owner",
        "scalar_logdensity_semantics":"Policy samples a requested recipe on a 1D curve; no ambient18D/applied-command density claimed",
        "complete_motion_failure_gets_minus1_partial_engineering_censors_group":True,
        "requested_lambda_is_not_an_actual_activation_certificate":True}
