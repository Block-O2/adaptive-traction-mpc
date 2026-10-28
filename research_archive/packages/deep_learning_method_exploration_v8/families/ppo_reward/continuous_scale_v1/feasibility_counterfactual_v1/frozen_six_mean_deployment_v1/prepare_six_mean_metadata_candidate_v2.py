"""SOURCE_ONLY V2 main-reviewed six-mean metadata builder; zero model imports/calls."""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import time

HERE="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/"
GEOMETRY="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/span_geometry_v1/"
STOP=1793114740.0
PATHS={"inventory":"freeze/FEASIBILITY_SIX_MEAN_ACTUAL_INVENTORY_V1.json",
       "authorization":"freeze/FEASIBILITY_SIX_MEAN_MAIN_AUTHORIZATION_V1.json",
       "registration":"freeze/FEASIBILITY_SIX_MEAN_NEW_PARAMETER_REGISTRATION_V1.json",
       "review":"freeze/FEASIBILITY_SIX_MEAN_ENDPOINT_MAIN_REVIEW_V1.json",
       "START":"audit/FEASIBILITY_SIX_MEAN_METADATA_PREPARE_START_V1.json",
       "END":"audit/FEASIBILITY_SIX_MEAN_METADATA_PREPARE_END_V1.json",
       "FAILED":"audit/FEASIBILITY_SIX_MEAN_METADATA_PREPARE_FAILED_V1.json"}
OLD_INVENTORY={"path":"freeze/FEASIBILITY_FOUR_MEAN_ACTUAL_INVENTORY_V1.json","sha256":"8cdf0b16ba19b472511a7e2142d4c1fc812e5581e8badfd8f819a677fca8fadf"}
GEO_RESULT={"path":GEOMETRY+"diagnostics/GATEG_ONCE_V1/RESULT.json","sha256":"c8cfcbd65927717cc94bc91f0d38ad72da579582aada215e806d7dcc0b9b41e4"}
GEO_DONE={"path":GEOMETRY+"diagnostics/GATEG_ONCE_V1/DONE.json","sha256":"13e4eea60ce818add0ba01b070949694ca98f5d0a6653ec425177eefd5fcc781"}
GROUPS=["V8FMEAN03","V8FMEAN04"]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package",required=True);parser.add_argument("--approval",required=True);parser.add_argument("--approval-sha256",required=True)
    args=parser.parse_args();package=Path(args.package).resolve();written={};started=False
    def path(relative):
        target=(package/relative).resolve()
        if not target.is_relative_to(package) or "real_runs" in target.parts or "results" in target.relative_to(package).parts:
            raise ValueError("METADATA_ONLY_NO_RAW_OR_ACTUAL_RUN_PATH")
        return target
    def sha(relative):return hashlib.sha256(path(relative).read_bytes()).hexdigest()
    def read(relative):return json.loads(path(relative).read_text())
    def ref(reference):
        if sha(reference["path"])!=reference["sha256"]:raise ValueError("EXACT_APPROVED_REF_CHANGED:"+reference["path"])
        return read(reference["path"])
    def sync_dir(directory):
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    def write(relative,value):
        target=path(relative)
        with target.open("x") as stream:
            stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n");stream.flush();os.fsync(stream.fileno())
        sync_dir(target.parent);written[relative]=sha(relative)
        return {"path":relative,"sha256":written[relative]}
    approval_path=Path(args.approval).resolve()
    if not approval_path.is_relative_to(package):raise ValueError("MAIN_APPROVAL_MUST_BE_IN_PACKAGE")
    approval_relative=str(approval_path.relative_to(package))
    if sha(approval_relative)!=args.approval_sha256:raise ValueError("EXACT_MAIN_APPROVAL_SHA_REQUIRED")
    auth=read(approval_relative)
    if (auth.get("schema")!="v8.feasibility_six_mean_metadata_main_approval.v1" or
            auth.get("status")!="APPROVED_BY_MAIN_SOURCE_AND_METADATA_FREEZE_ONLY" or
            auth.get("metadata_only") is not True or auth.get("all_six_models_and_program_reviewed") is not True or
            auth.get("outcome_or_best_selection") is not False or auth.get("future_physics_authority") is not False or
            auth.get("model_or_forward_or_fit_calls")!=0 or auth.get("global_stop_unix")!=STOP or
            auth.get("builder_source_sha256")!=sha(HERE+"prepare_six_mean_metadata_candidate_v2.py")):
        raise ValueError("INDEPENDENT_EXACT_MAIN_SOURCE_METADATA_AUTHORITY_REQUIRED")
    def clock():
        if not auth["local_start_unix"]<=time.time()<min(auth["local_stop_unix"],STOP):raise TimeoutError("METADATA_PREPARE_LOCAL_GLOBAL_DEADLINE")
    if not 0<auth["local_stop_unix"]-auth["local_start_unix"]<=60:raise ValueError("METADATA_LOCAL_WINDOW_MAX60_NOT_TRAINING_CLOCK")
    clock();spec=ref(auth["source_requirements_manifest"])
    if spec["runtime_sources_sha256"]!=auth["source_files_sha256"]:raise ValueError("CURRENT_HASHES_CANNOT_UPGRADE_MAIN_SOURCE_APPROVAL")
    for relative,expected in auth["source_files_sha256"].items():
        if sha(relative)!=expected:raise ValueError("SOURCE_CLOSURE_CHANGED:"+relative)
        if path(relative).suffix==".py":ast.parse(path(relative).read_text())
    if sha("ACTIVATION.json")!=auth["activation_sha256"] or read("ACTIVATION.json").get("hard_stop_unix")!=STOP:raise ValueError("ORIGINAL_ACTIVATION_CLOCK_REQUIRED")
    # V2: inspect every actual START's exact frozen config, independent of ID.
    # This must finish before ANY write, including the builder START artifact.
    four=ref(OLD_INVENTORY)
    original_registration=ref(four["new_parameter_registration"])
    target_case_hashes={item["payload"]["sha256"] for item in original_registration["conditions"]}
    target_case_paths=set()
    if len(original_registration["conditions"])!=2 or len(target_case_hashes)!=2:
        raise ValueError("EXACT_TWO_ORIGINAL_VALIDATION_CASE_HASHES_REQUIRED")
    for i,old_group in enumerate(["V8FMEAN01","V8FMEAN02"]):
        old_config=read("experiments/"+old_group+".json")
        if old_config["case_sha256"]!=original_registration["conditions"][i]["payload"]["sha256"]:
            raise ValueError("ORIGINAL_TWO_ROUTE_CONFIG_REGISTRATION_HASH_MISMATCH")
        target_case_paths.add(old_config["case_path"])
    events=path("runtime/ATTEMPTS.jsonl").read_bytes()
    starts=[json.loads(line) for line in events.splitlines() if line]
    start_config_proof={};matching_starts=[];actual_start_count=0
    for event in starts:
        if event.get("event")!="START":continue
        clock();actual_start_count+=1
        group=event.get("group");expected=event.get("config_sha256")
        if not isinstance(group,str) or not group or not isinstance(expected,str) or len(expected)!=64:
            raise ValueError("START_WITHOUT_EXACT_CONFIG_PROVENANCE_FAIL_CLOSED")
        config_relative="experiments/"+group+".json"
        if config_relative not in start_config_proof:
            config=read(config_relative);actual_sha=sha(config_relative)
            if actual_sha!=expected or config.get("group")!=group:
                raise ValueError("START_CONFIG_CHANGED_CANNOT_ESTABLISH_ACTUAL_CASE_FAIL_CLOSED:"+group)
            start_config_proof[config_relative]={"config_sha256":actual_sha,"case_sha256":config.get("case_sha256"),"case_path":config.get("case_path")}
        proof=start_config_proof[config_relative]
        if proof["config_sha256"]!=expected:
            raise ValueError("MULTIPLE_START_CONFIG_IDENTITIES_FAIL_CLOSED:"+group)
        if proof["case_sha256"] in target_case_hashes or proof["case_path"] in target_case_paths:
            matching_starts.append({"id":event.get("id"),"group":group,"kind":event.get("kind"),"config":config_relative,**proof})
    if matching_starts:
        raise ValueError("ORIGINAL_TWO_PARAMETER_CASE_ANY_START_ALREADY_EXISTS_BEFORE_METADATA_WRITE:"+json.dumps(matching_starts,sort_keys=True))
    prewrite_case_guard={"scope":"ALL_START_EVENTS_BY_EXACT_CONFIG_CASE_SHA_OR_ORIGINAL_ROUTE_NOT_JOB_IDS", "target_case_sha256":sorted(target_case_hashes),
                        "target_case_paths":sorted(target_case_paths),"START_count_reviewed":actual_start_count,
                        "exact_START_config_proof":start_config_proof,"matching_START_count":0,
                        "ATTEMPTS_metadata_sha256":hashlib.sha256(events).hexdigest(),"completed_before_any_artifact_write":True}
    targets=[*PATHS.values(),"experiments/V8FMEAN03.json","experiments/V8FMEAN04.json"]
    if any(path(relative).exists() for relative in targets):raise ValueError("EXCLUSIVE_NEW_ARTIFACTS_ONLY_PRESERVE_PRIOR_ATTEMPTS")
    try:
        write(PATHS["START"],{"status":"STARTED_METADATA_ONLY","unix":time.time(),"pid":os.getpid(),"main_approval":{"path":approval_relative,"sha256":args.approval_sha256},"source_requirements_manifest":auth["source_requirements_manifest"],"prewrite_any_case_START_guard":prewrite_case_guard,"model_calls":0});started=True
        four=ref(OLD_INVENTORY);geometry=ref(GEO_RESULT);done=ref(GEO_DONE)
        if (done["status"]!="COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or done["result_sha256"]!=GEO_RESULT["sha256"] or
                geometry["schema"]!="v8.beta_feasibility_span_geometry_private_result.v1" or geometry["target"]!="FEASIBILITY_ONLY" or
                geometry["endpoint_selection"]!="BOTH_FIXED_FINAL_RF1_PPO3_NOT_BEST" or
                geometry["original_four_feasibility_mean_inventory_unmodified"] is not True):raise ValueError("ACTUAL_COMPLETE_GEOMETRY_FIXED_TWO_FINAL_MODELS_REQUIRED")
        geo_identity_path=GEOMETRY+"diagnostics/GATEG_ONCE_V1/IDENTITY.json"
        geo_identity={"path":geo_identity_path,"sha256":sha(geo_identity_path)};identity=read(geo_identity_path)
        geo_manifest=identity["source_manifest"]
        if geo_manifest!={"path":GEOMETRY+"SOURCE_MANIFEST_V1.json","sha256":"72301018a87d9351a830bd53dd4dcb02a39f62a9970057f6d10a96930985e083"} or identity["input"]!=geometry["input"]:
            raise ValueError("ACTUAL_GEOMETRY_SOURCE_AND_INPUT_IDENTITY_REQUIRED")
        if geometry["counts"]!=ref(ref(geo_manifest)["contract"])["successful_exact_instrumented_counts"]:raise ValueError("ACTUAL_GEOMETRY_COUNTS_NOT_FULL_CONTRACT")
        owner_closure=[]
        for pid,ticks in [(1213098,62669907),(1213095,62669904)]:
            proc=Path("/proc")/str(pid)/"stat"
            current=int(proc.read_text().rsplit(")",1)[1].split()[19]) if proc.exists() else None
            if current==ticks:raise ValueError("ORIGINAL_GEOMETRY_OWNER_STILL_ALIVE")
            owner_closure.append({"pid":pid,"original_start_ticks":ticks,"current_start_ticks":current,"closed":True})
        models=list(four["models"]);behavior=ref(four["original_behavior_exact_export"])["policy"]
        fields=("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version")
        for algorithm,label,steps in [("REINFORCE","FEAS_SPAN_GEOMETRY_RF1",1),("PPO","FEAS_SPAN_GEOMETRY_PPO3",3)]:
            policy=geometry["private_policies"][algorithm]
            if (policy["normalization"]!=behavior["normalization"] or policy["axis_contract"]!=behavior["axis_contract"] or
                    policy["counters"]["parameter_updates"]!=steps or len(geometry["traces"][algorithm])!=steps or
                    digest(policy["weights"])!=geometry["traces"][algorithm][-1]["weights_after_sha256"]):raise ValueError("GEOMETRY_FINAL_WEIGHT_NORM_AXIS_STEP_IDENTITY")
            policy_digest=digest({key:policy[key] for key in fields})
            if any(row["policy_sha256"]!=policy_digest for row in geometry["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm].values()):raise ValueError("STORED_MEAN_METADATA_NOT_FINAL_POLICY")
            models.append({"label":label,"closed_result":GEO_RESULT,"closed_DONE":GEO_DONE,"policy_json_path":["private_policies",algorithm],"policy_sha256":policy_digest,"weights_sha256":digest(policy["weights"])})
        if len(models)!=6 or len({m["label"] for m in models})!=6:raise ValueError("EXACT_ALL6_NOT_BEST")
        expected_labels=["FEAS_GLOBAL_RF1","FEAS_GLOBAL_PPO3","FEAS_CONTEXT_LOO_RF1","FEAS_CONTEXT_LOO_PPO3","FEAS_SPAN_GEOMETRY_RF1","FEAS_SPAN_GEOMETRY_PPO3"]
        if [item["label"] for item in models]!=expected_labels:raise ValueError("EXACT_SIX_FIXED_ENDPOINT_ORDER_NO_SELECTION")
        behavior_density=digest({key:behavior[key] for key in fields[:6]});all_six_preflight=[]
        for item in models:
            result=ref(item["closed_result"]);closed_done=ref(item["closed_DONE"])
            algorithm="PPO" if item["label"].endswith("PPO3") else "REINFORCE";steps=3 if algorithm=="PPO" else 1
            expected_schema="v8.beta_feasibility_span_geometry_private_result.v1" if "SPAN_GEOMETRY" in item["label"] else "v8.beta_feasibility_context_loo_private_result.v1" if "CONTEXT_LOO" in item["label"] else "v8.beta_feasibility_counterfactual_private_result.v1"
            policy=result["private_policies"][algorithm]
            if (result["schema"]!=expected_schema or result["target"]!="FEASIBILITY_ONLY" or
                    result["data_semantics"]!="FIXED_BEHAVIOR_COUNTERFACTUAL_REPLAY_NOT_NEW_ON_POLICY" or
                    closed_done["status"]!="COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or closed_done["result_sha256"]!=item["closed_result"]["sha256"] or
                    item["policy_json_path"]!=["private_policies",algorithm] or result["behavior_density_sha256"]!=behavior_density or
                    policy["normalization"]!=behavior["normalization"] or policy["axis_contract"]!=behavior["axis_contract"] or
                    policy["axis_contract_sha256"]!=behavior["axis_contract_sha256"] or policy["feature_names"]!=behavior["feature_names"] or len(policy["feature_names"])!=25 or policy["gain"]!=1.0 or
                    len(policy["weights"])!=2 or any(len(row)!=26 or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in row) for row in policy["weights"]) or
                    policy["counters"]!={"forward":14 if algorithm=="PPO" else 10,"parameter_updates":steps,"score_evaluations":12 if algorithm=="PPO" else 4} or
                    len(result["traces"][algorithm])!=steps or digest(policy["weights"])!=result["traces"][algorithm][-1]["weights_after_sha256"] or
                    digest(policy["weights"])!=item["weights_sha256"] or digest({key:policy[key] for key in fields})!=item["policy_sha256"]):
                raise ValueError("ALL_SIX_ACTUAL_RESULT_POLICY_WEIGHT_FEATURE_NORM_AXIS_COUNTER_PREFLIGHT:"+item["label"])
            saved=result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm]
            if set(saved)!={"V8BETA01H","V8BETA01L"} or any(value["policy_sha256"]!=item["policy_sha256"] for value in saved.values()):
                raise ValueError("ALL_SIX_STORED_MEAN_IDENTITY_NO_NEW_FORWARD")
            all_six_preflight.append({"label":item["label"],"policy_sha256":item["policy_sha256"],"weights_sha256":item["weights_sha256"],
                                      "actual_policy_counters":policy["counters"],"behavior_density_sha256":behavior_density,"model_or_forward_calls":0})
        prior_registration=ref(four["new_parameter_registration"])
        registration={**prior_registration,"schema":"v8.feasibility_six_mean_new_parameter_registration.v1","job_groups":GROUPS,"created_unix":time.time(),
                      "conditions":[{**item,"group":GROUPS[i]} for i,item in enumerate(prior_registration["conditions"])],"all_original_six_final_models_before_first_new_parameter_physics":True}
        registration_ref=write(PATHS["registration"],registration);clock()
        review={"schema":"v8.frozen_feasibility_endpoint_freeze_review.v1","status":"ALL_SIX_FINAL_MODELS_AND_PROGRAM_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS",
                "frozen_unix":time.time(),"original_global_stop_unix":STOP,"new_parameter_parents_not_started_at_freeze":True,"original_validation_physics_start_count":0,
                "outcome_or_best_endpoint_selection":False,"source_files_sha256":auth["source_files_sha256"],"models_object_sha256":digest(models),"new_parameter_registration":registration_ref,
                "original_four_inventory":OLD_INVENTORY,"actual_geometry_result":GEO_RESULT,"actual_geometry_DONE":GEO_DONE,"actual_geometry_owner_closure":owner_closure,
                "metadata_main_source_approval":{"path":approval_relative,"sha256":args.approval_sha256},"model_inference_or_fit_by_builder":0}
        review["all_six_actual_model_metadata_preflight"]=all_six_preflight
        review["prewrite_any_case_START_guard"]=prewrite_case_guard
        review["runtime_six_adapter_not_yet_executed"]=True
        review["payload_bytes_structurally_exposed_not_byte_blind"]=True
        review["fixed_behavior_replay_not_fresh_onpolicy"]=True
        review["all_six_evaluated_no_best_selection"]=True
        review_ref=write(PATHS["review"],review)
        inventory={**four,"schema":"v8.frozen_feasibility_six_mean_inventory.v1","status":"ALL_SIX_ACTUAL_FIXED_FINAL_ENDPOINTS_FROZEN_NOT_BEST","models":models,
                   "main_endpoint_freeze_review":review_ref,"new_parameter_registration":registration_ref,"original_four_inventory":OLD_INVENTORY,
                   "geometry_source_manifest":geo_manifest,"geometry_actual_identity":geo_identity,"closed_geometry_result":GEO_RESULT}
        inventory_ref=write(PATHS["inventory"],inventory)
        authorization={"schema":"v8.frozen_feasibility_six_mean_main_approval.v1","status":"APPROVED_BY_MAIN_FOR_SIX_FROZEN_MEANS_ONLY","inventory":inventory_ref,
                       "authorized_job_groups":GROUPS,"mean_forward_only":True,"restore_fit_RNG_or_sampling":0,"activation_sha256":auth["activation_sha256"],
                       "approved_unix":auth["approved_unix"],"deployment_deadline_unix":auth["deployment_deadline_unix"],"source_files_sha256":auth["source_files_sha256"],
                       "root_wrapper":spec["root_wrapper"],"physics_dispatch_authorized":False}
        if not time.time()<authorization["deployment_deadline_unix"]<=STOP:raise ValueError("NEW_READONLY_DEPLOYMENT_DEADLINE_CANNOT_EXTEND_GLOBAL")
        auth_ref=write(PATHS["authorization"],authorization)
        frozen_extra={r["path"]:r["sha256"] for r in [inventory_ref,review_ref,registration_ref,auth_ref,OLD_INVENTORY,geo_manifest,geo_identity,GEO_RESULT,GEO_DONE,*[m["closed_result"] for m in models],*[m["closed_DONE"] for m in models]]}
        frozen_extra.update(auth["source_files_sha256"])
        frozen_extra[auth["source_requirements_manifest"]["path"]]=auth["source_requirements_manifest"]["sha256"]
        frozen_extra[spec["contract"]["path"]]=spec["contract"]["sha256"]
        frozen_extra[approval_relative]=args.approval_sha256
        config_refs=[]
        for i,group in enumerate(GROUPS):
            original_group=["V8FMEAN01","V8FMEAN02"][i];config=read("experiments/"+original_group+".json")
            for relative,expected in config["frozen_artifacts"].items():
                if sha(relative)!=expected:raise ValueError("ORIGINAL4_CONFIG_SOURCE_OR_DATA_CHANGED:"+relative)
            condition=registration["conditions"][i]
            if (config["condition"]["seed"]!=condition["seed"] or config["case_sha256"]!=condition["payload"]["sha256"] or
                    sha(config["case_path"])!=condition["payload"]["sha256"]):raise ValueError("EXACT_SAME_REGISTERED_VALIDATION_ROUTE_AND_SEED")
            config={**config,"group":group,"algorithm":"v8_frozen_feasibility_sixmeanonly_v1","condition":{**config["condition"],"name":group,"role":"All six fixed final feasibility endpoints, B/H150/lambda1 frozen before original new-parameter physics."},
                    "scientific_branch":"FROZEN_SIX_FEASIBILITY_MEANS_NEW_PARAMETER_VALIDATION","frozen_artifacts":{**config["frozen_artifacts"],**frozen_extra}}
            config.pop("frozen_feasibility_means",None)
            config["frozen_feasibility_six_means"]={"schema":"v8.frozen_feasibility_six_mean_job.v1","inventory":inventory_ref,"deployment_authorization":auth_ref}
            config_refs.append(write("experiments/"+group+".json",config));clock()
        write(PATHS["END"],{"status":"COMPLETED_METADATA_ONLY_ALL_SIX_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS","completed_unix":time.time(),
              "inventory":inventory_ref,"authorization":auth_ref,"registration":registration_ref,"review":review_ref,"configs":config_refs,
              "files_sha256":dict(written),"source_files_sha256":auth["source_files_sha256"],"geometry_owner_closure":owner_closure,
              "all_six_actual_model_metadata_preflight":all_six_preflight,"runtime_six_adapter_or_original_four_runtime_not_claimed_validated":True,
              "original_validation_parent_START_count":0,"original_two_parameter_any_START_count":0,"prewrite_any_case_START_guard":prewrite_case_guard,
              "ATTEMPTS_metadata_sha256":hashlib.sha256(events).hexdigest(),"model_init_restore_forward_fit_RNG_physics_calls":0,
              "original_four_configs_inventory_and_sources_unchanged":True,"future_physics_dispatch_requires_separate_main_approval":True})
    except BaseException as error:
        if started:write(PATHS["FAILED"],{"status":"FAILED_METADATA_ONLY_PRESERVED_NO_RETRY","error_type":type(error).__name__,"error":str(error),"files_already_written_sha256":written,"model_or_physical_calls":0})
        raise


if __name__=="__main__":
    main()
