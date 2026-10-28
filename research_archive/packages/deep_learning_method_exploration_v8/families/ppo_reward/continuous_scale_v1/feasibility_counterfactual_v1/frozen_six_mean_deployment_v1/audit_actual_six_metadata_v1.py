"""Authorized actual six-inventory audit: stdlib metadata only, no learner imports."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

PACKAGE=Path(__file__).resolve().parents[5]
HERE="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/"
LABELS=["FEAS_GLOBAL_RF1","FEAS_GLOBAL_PPO3","FEAS_CONTEXT_LOO_RF1","FEAS_CONTEXT_LOO_PPO3","FEAS_SPAN_GEOMETRY_RF1","FEAS_SPAN_GEOMETRY_PPO3"]


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def main():
    output=PACKAGE/HERE/"metadata_actual_six_inventory_review_v1";output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    started=time.time();initial=resource.getrusage(resource.RUSAGE_SELF);files={};cache={};checks=[];blockers=[]
    counts={"unique_file_SHA_reads":0,"unique_JSON_decodes":0,"source_AST_parses":0,"policy_digest_checks":0,"weight_digest_checks":0,"forward_score_init_restore_fit_gradient_RNG_physics_calls":0}
    def path(relative):
        target=(PACKAGE/relative).resolve()
        if not target.is_relative_to(PACKAGE) or "real_runs" in target.parts or "results" in target.relative_to(PACKAGE).parts:raise ValueError("METADATA_AUDIT_FORBIDS_RAW_OR_ACTUAL_RUN")
        return target
    def sha(relative):
        if relative not in files:files[relative]=hashlib.sha256(path(relative).read_bytes()).hexdigest();counts["unique_file_SHA_reads"]+=1
        return files[relative]
    def read(relative):
        if relative not in cache:sha(relative);cache[relative]=json.loads(path(relative).read_text());counts["unique_JSON_decodes"]+=1
        return cache[relative]
    def check(name,value,detail=None):
        row={"check":name,"PASS":bool(value)}
        if detail is not None:row["detail"]=detail
        checks.append(row)
        if not value:blockers.append(row)
    def ref(reference,frozen=None):
        check("EXACT_REF:"+reference["path"],sha(reference["path"])==reference["sha256"] and (frozen is None or frozen.get(reference["path"])==reference["sha256"]))
        return read(reference["path"])
    def write(name,value):
        with (output/name).open("x") as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    own=str(Path(__file__).resolve().relative_to(PACKAGE));tree=ast.parse(path(own).read_text());counts["source_AST_parses"]+=1
    write("START.json",{"unix":started,"pid":os.getpid(),"start_ticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),"source_sha256":sha(own),"source_AST_sha256":hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),"CPU_affinity":sorted(os.sched_getaffinity(0)),"CPU_user_s":initial.ru_utime,"CPU_system_s":initial.ru_stime,"RSS_peak_KiB":initial.ru_maxrss,"binary":str(Path(sys.executable).resolve()),"binary_sha256":hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),"model_calls":0})
    try:
        endref={"path":"audit/FEASIBILITY_SIX_MEAN_METADATA_PREPARE_END_V1.json","sha256":"b58d8a96cec0eb46046b19ee806049ea2f0d194c9beec9b2034e8817bfd5767f"};end=ref(endref)
        inventory=ref(end["inventory"]);auth=ref(end["authorization"]);review=ref(end["review"]);registration=ref(end["registration"])
        check("MAIN_SUPPLIED_ACTUAL_INVENTORY_AND_AUTH",end["inventory"]["sha256"]=="c29d4607e6a32298493c338aeb1f35a3ba6a10ffdd9ae9abb212e119d4c17b1c" and end["authorization"]["sha256"]=="dcc9066e7c6ecfe634c0fec6848bc9b0de5b1cf484823a86c4b2480ec3843983")
        check("END_COMPLETE_ZERO_API_NOT_RUNTIME_VALIDATION",end["status"]=="COMPLETED_METADATA_ONLY_ALL_SIX_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS" and end["model_init_restore_forward_fit_RNG_physics_calls"]==0 and end["runtime_six_adapter_or_original_four_runtime_not_claimed_validated"] is True and end["original_four_configs_inventory_and_sources_unchanged"] is True and end["future_physics_dispatch_requires_separate_main_approval"] is True)
        for relative,expected in end["files_sha256"].items():check("END_IMMUTABLE_OUTPUT:"+relative,sha(relative)==expected)
        check("SIX_SCHEMA_STATUS_ORDER",inventory["schema"]=="v8.frozen_feasibility_six_mean_inventory.v1" and inventory["status"]=="ALL_SIX_ACTUAL_FIXED_FINAL_ENDPOINTS_FROZEN_NOT_BEST" and [m["label"] for m in inventory["models"]]==LABELS)
        check("SIX_AUTH_SCHEMA_MEAN_ONLY_NO_PHYSICS",auth["schema"]=="v8.frozen_feasibility_six_mean_main_approval.v1" and auth["status"]=="APPROVED_BY_MAIN_FOR_SIX_FROZEN_MEANS_ONLY" and auth["authorized_job_groups"]==["V8FMEAN03","V8FMEAN04"] and auth["mean_forward_only"] is True and auth["restore_fit_RNG_or_sampling"]==0 and auth["physics_dispatch_authorized"] is False and auth["inventory"]==end["inventory"])
        check("EXACT_GLOBAL_ACTIVATION_AND_READONLY_CLOCK",sha("ACTIVATION.json")==auth["activation_sha256"] and read("ACTIVATION.json")["hard_stop_unix"]==1793114740.0 and read("ACTIVATION.json")["clock_must_not_reset"] is True and auth["approved_unix"]<=started<min(auth["deployment_deadline_unix"],1793114740.0))
        approval=ref(review["metadata_main_source_approval"]);requirements=ref(approval["source_requirements_manifest"])
        check("APPROVED_V2_SOURCE_CLOSURE_36",approval["source_requirements_manifest"]["sha256"]=="3ac4508b5eb5286a84dd3c619e16cb976dcd93b759d0f0c7ddcf66337ccb6d3a" and auth["source_files_sha256"]==review["source_files_sha256"]==end["source_files_sha256"]==approval["source_files_sha256"]==requirements["runtime_sources_sha256"] and len(auth["source_files_sha256"])==36)
        check("V1_BUILDER_AND_CONTRACT_NONOPERATIVE",HERE+"prepare_six_mean_metadata_candidate_v1.py" not in auth["source_files_sha256"] and HERE+"EXPERIMENT_CONTRACT_SOURCE_ONLY_V1.json" not in auth["source_files_sha256"] and auth["source_files_sha256"].get(HERE+"prepare_six_mean_metadata_candidate_v2.py")=="c220869abefdbb7af25f19d01a6cb163a7a0a136bad2757a0efc099e6edda402")
        for relative,expected in auth["source_files_sha256"].items():check("MAIN_APPROVED_ACTUAL_SOURCE:"+relative,sha(relative)==expected)
        check("ROOT_WRAPPER_EXACT_PRIVATE_CANDIDATE",auth["root_wrapper"]==requirements["root_wrapper"] and sha(auth["root_wrapper"]["path"])==sha(HERE+"root_wrapper_candidate_v1.py")=="86b0970bf41c7ea7b171d607025d1535cf4ea81c5af8f32e0641c21dafb1d4a1")
        for relative in [HERE+"mean_adapter_candidate_v1.py",HERE+"mean_sequence_candidate_v1.py",HERE+"root_wrapper_candidate_v1.py",HERE+"prepare_six_mean_metadata_candidate_v2.py",auth["root_wrapper"]["path"]]:ast.parse(path(relative).read_text());counts["source_AST_parses"]+=1
        prior=ref(inventory["original_four_inventory"])
        check("ORIGINAL_FOUR_MODELS_EXACT_UNCHANGED",inventory["original_four_inventory"]["sha256"]=="8cdf0b16ba19b472511a7e2142d4c1fc812e5581e8badfd8f819a677fca8fadf" and inventory["models"][:4]==prior["models"] and len(prior["models"])==4)
        preserved={"experiments/V8FMEAN01.json":"05726018bf00d5f07b8356dc5e2d5b9011d994004895b9acdac82ffc939bb0a9","experiments/V8FMEAN02.json":"3a25601f56412e878d7cd611e60967e2e5390f31a19c31b78f01e080953c021b","freeze/FEASIBILITY_FOUR_MEAN_MAIN_AUTHORIZATION_V1.json":"8c0231e686836ea50abcc2042225516ce5e539967c7ca9f179d8e8138961d48f","freeze/FEASIBILITY_FOUR_MEAN_NEW_PARAMETER_REGISTRATION_V1.json":"54881dd5e6b170f95f8d075ef9a06d69be2640b40fb113aaab50a510964a43ba","freeze/FEASIBILITY_FOUR_MEAN_ENDPOINT_MAIN_REVIEW_V1.json":"c25321b1515b46c56aa580fd83f97ccf9c601354b7144bc27c7953f014622c5f"}
        for relative,expected in preserved.items():check("ORIGINAL4_UNMODIFIED:"+relative,sha(relative)==expected)
        behavior=ref(inventory["original_behavior_exact_export"])["policy"];axis=ref(inventory["axis"]);menu=ref(inventory["original_recipe_menu"])["action_contracts"]
        fields=("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version");density=digest({key:behavior[key] for key in fields[:6]});endpoint_metadata=[]
        for item in inventory["models"]:
            result=ref(item["closed_result"]);done=ref(item["closed_DONE"]);algorithm="PPO" if item["label"].endswith("PPO3") else "REINFORCE";steps=3 if algorithm=="PPO" else 1;policy=result["private_policies"][algorithm]
            schema="v8.beta_feasibility_span_geometry_private_result.v1" if "SPAN_GEOMETRY" in item["label"] else "v8.beta_feasibility_context_loo_private_result.v1" if "CONTEXT_LOO" in item["label"] else "v8.beta_feasibility_counterfactual_private_result.v1"
            pd=digest({key:policy[key] for key in fields});wd=digest(policy["weights"]);counts["policy_digest_checks"]+=1;counts["weight_digest_checks"]+=1
            check(item["label"]+":ACTUAL_CANONICAL_DIGESTS",pd==item["policy_sha256"] and wd==item["weights_sha256"]==result["traces"][algorithm][-1]["weights_after_sha256"])
            check(item["label"]+":FIXED_SCHEMA_CLOSED_DATA_AXIS_NORM_COUNTERS",result["schema"]==schema and result["target"]=="FEASIBILITY_ONLY" and result["data_semantics"]=="FIXED_BEHAVIOR_COUNTERFACTUAL_REPLAY_NOT_NEW_ON_POLICY" and done["status"]=="COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" and done["result_sha256"]==item["closed_result"]["sha256"] and item["policy_json_path"]==["private_policies",algorithm] and result["behavior_density_sha256"]==density and policy["normalization"]==behavior["normalization"] and policy["axis_contract"]==axis==behavior["axis_contract"] and policy["axis_contract_sha256"]==inventory["axis_object_sha256"] and policy["feature_names"]==behavior["feature_names"] and len(policy["feature_names"])==25 and policy["gain"]==1.0 and len(policy["weights"])==2 and all(len(row)==26 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in row) for row in policy["weights"]) and policy["counters"]=={"forward":14 if algorithm=="PPO" else 10,"parameter_updates":steps,"score_evaluations":12 if algorithm=="PPO" else 4} and len(result["traces"][algorithm])==steps)
            means=result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm]
            check(item["label"]+":STORED_MEAN_IDENTITY_WITHOUT_FORWARD",set(means)=={"V8BETA01H","V8BETA01L"} and all(m["policy_sha256"]==pd for m in means.values()))
            endpoint_metadata.append({"label":item["label"],"policy_sha256":pd,"weights_sha256":wd,"counters":policy["counters"],"stored_means":{k:v["lambda"] for k,v in means.items()},"physical_qualification":"UNKNOWN_NOT_RUN"})
        geo_manifest=ref(inventory["geometry_source_manifest"]);geo_identity=ref(inventory["geometry_actual_identity"])
        check("GEOMETRY_EXACT_CLOSED_SOURCE_AND_INPUT",inventory["geometry_source_manifest"]["sha256"]=="72301018a87d9351a830bd53dd4dcb02a39f62a9970057f6d10a96930985e083" and geo_identity["source_manifest"]==inventory["geometry_source_manifest"] and all(auth["source_files_sha256"].get(k)==v for k,v in geo_manifest["source_files_sha256"].items()) and inventory["closed_geometry_result"]["sha256"]=="c8cfcbd65927717cc94bc91f0d38ad72da579582aada215e806d7dcc0b9b41e4")
        check("END_REVIEW_FULL6_PREFLIGHT_SAME",end["all_six_actual_model_metadata_preflight"]==review["all_six_actual_model_metadata_preflight"] and [i["label"] for i in end["all_six_actual_model_metadata_preflight"]]==LABELS and all(i["model_or_forward_calls"]==0 for i in end["all_six_actual_model_metadata_preflight"]))
        check("REVIEW_BEFORE_PHYSICS_ALL6_NO_BEST",review["status"]=="ALL_SIX_FINAL_MODELS_AND_PROGRAM_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS" and review["new_parameter_parents_not_started_at_freeze"] is True and review["outcome_or_best_endpoint_selection"] is False and review["models_object_sha256"]==digest(inventory["models"]) and review["new_parameter_registration"]==inventory["new_parameter_registration"]==end["registration"] and review["runtime_six_adapter_not_yet_executed"] is True)
        refs=[end["inventory"],end["authorization"],end["review"],end["registration"],inventory["original_four_inventory"],inventory["geometry_source_manifest"],inventory["geometry_actual_identity"],inventory["closed_geometry_result"],inventory["axis"],inventory["original_recipe_menu"],inventory["A3_adapter_manifest"],inventory["original_behavior_exact_export"],inventory["closed_global_result"],*[r for m in inventory["models"] for r in (m["closed_result"],m["closed_DONE"])]]
        expected_config_shas=["7f05d2e7b8d7e02f37597e2be8d70933f4b3145ec07391c1c7ec81cbe4d6f491","afe0d0773e02c0ee9f8c0d379bc013995dcb86c91986fef0a5097637e954c65f"]
        jobs=[]
        for i,group in enumerate(["V8FMEAN03","V8FMEAN04"]):
            configref=end["configs"][i];config=ref(configref);frozen=config["frozen_artifacts"];oldconfig=read("experiments/"+["V8FMEAN01","V8FMEAN02"][i]+".json");condition=registration["conditions"][i]
            check(group+":EXACT_MAIN_CONFIG_AND_129_PINS",configref["sha256"]==expected_config_shas[i] and config["group"]==group and len(frozen)==129)
            for relative,expected in frozen.items():check(group+":ACTUAL_FROZEN_PIN:"+relative,sha(relative)==expected)
            for reference in refs:check(group+":REQUIRED_ADAPTER_JSON_REF_FROZEN:"+reference["path"],frozen.get(reference["path"])==reference["sha256"])
            for relative,expected in {**auth["source_files_sha256"],**axis["source_files_sha256"]}.items():check(group+":TRANSITIVE_SOURCE_AXIS_PIN:"+relative,frozen.get(relative)==expected)
            spec=config["frozen_feasibility_six_means"]
            check(group+":EXACT_SEPARATE_SIX_ONLY_INTERFACE",config["algorithm"]=="v8_frozen_feasibility_sixmeanonly_v1" and spec=={"schema":"v8.frozen_feasibility_six_mean_job.v1","inventory":end["inventory"],"deployment_authorization":end["authorization"]} and "frozen_feasibility_means" not in config and config["worker"]=="v8_worker_v2.py" and config["fork_phase"]=="OUTBOUND" and config["fork_slot"]==0 and config["job_wall_cap_s"]==1800 and config["mode"]=="validation" and not config.get("onpolicy_sampling"))
            check(group+":SAME_ORIGINAL_SEED_ROUTE_NATIVE_PERMISSION",config["condition"]["seed"]==oldconfig["condition"]["seed"]==condition["seed"]==[2026102753,2026102754][i] and config["case_path"]==oldconfig["case_path"] and config["case_sha256"]==oldconfig["case_sha256"]==condition["payload"]["sha256"]==sha(config["case_path"]) and config["actions"]==oldconfig["actions"] and config["B"]==oldconfig["B"] and config["H150"]==oldconfig["H150"])
            jobs.append({"group":group,"config_sha256":configref["sha256"],"frozen_pin_count":len(frozen),"seed":condition["seed"],"case_sha256":config["case_sha256"]})
        guard=end["prewrite_any_case_START_guard"]
        check("V2_GENERIC_CASE_GUARD_PREWRITE_COMPLETE",guard["scope"]=="ALL_START_EVENTS_BY_EXACT_CONFIG_CASE_SHA_OR_ORIGINAL_ROUTE_NOT_JOB_IDS" and guard["START_count_reviewed"]==158 and guard["matching_START_count"]==0 and guard["completed_before_any_artifact_write"] is True and end["original_two_parameter_any_START_count"]==0 and review["prewrite_any_case_START_guard"]==guard)
        starts_bytes=path("runtime/ATTEMPTS.jsonl").read_bytes();current_matches=[]
        for line in starts_bytes.splitlines():
            event=json.loads(line)
            if event.get("event")!="START":continue
            config_path="experiments/"+event["group"]+".json";config=read(config_path)
            check("CURRENT_START_EXACT_CONFIG:"+event["id"],sha(config_path)==event["config_sha256"] and config["group"]==event["group"])
            if config.get("case_sha256") in guard["target_case_sha256"] or config.get("case_path") in guard["target_case_paths"]:current_matches.append({"id":event["id"],"group":event["group"],"unix":event["unix"]})
        check("ASOF_REVIEW_NO_ORIGINAL_TWO_CASE_START",not current_matches,current_matches)
        builder_start=read("audit/FEASIBILITY_SIX_MEAN_METADATA_PREPARE_START_V1.json");owner_closure=[]
        for pid,ticks in [(1217431,62787808),(builder_start["pid"],None),(1213098,62669907),(1213095,62669904)]:
            proc=Path("/proc")/str(pid)/"stat";current=int(proc.read_text().rsplit(")",1)[1].split()[19]) if proc.exists() else None
            closed=current is None or (ticks is not None and current!=ticks)
            check("ORIGINAL_PROCESS_CLOSED:"+str(pid),closed)
            owner_closure.append({"pid":pid,"original_start_ticks":ticks,"current_start_ticks":current,"closed":closed,"original_ticks_not_in_builder_START":ticks is None})
        final=resource.getrusage(resource.RUSAGE_SELF)
        report={"schema":"v8.actual_six_mean_metadata_independent_review.v1","status":"PASS_METADATA_ONLY_FUTURE_SIX_RUNTIME_NOT_YET_VALIDATED" if not blockers else "BLOCKED_METADATA_PRECONDITIONS","checks":checks,"blockers":blockers,"reviewed_END":endref,"actual_inventory":end["inventory"],"actual_auth":end["authorization"],"six_model_metadata":endpoint_metadata,"jobs":jobs,"owner_closure":owner_closure,"source_files_sha256":files,"counts":counts,"wall_s":time.time()-started,"CPU_s":final.ru_utime+final.ru_stime-initial.ru_utime-initial.ru_stime,"peak_RSS_KiB":final.ru_maxrss,"main_external_builder_resources_reported_by_parent":{"wall_including_launcher_s":.1753,"inclusive_child_CPU_s":.1708,"not_core_builder_resource":True},"runtime_six_adapter_and_original_four_runtime_NOT_YET_VALIDATED":True,"no_inference_no_raw_no_realrun_no_ENG02_outcome_reads":True,"physics_dispatch_authority_from_this_review":False}
        write("REVIEW.json",report);write("DONE.json",{"status":report["status"],"review_sha256":hashlib.sha256((output/"REVIEW.json").read_bytes()).hexdigest(),"blocker_count":len(blockers),"model_calls":0})
        print(json.dumps({"status":report["status"],"checks":len(checks),"blockers":blockers,"jobs":jobs,"counts":counts,"review_sha256":hashlib.sha256((output/"REVIEW.json").read_bytes()).hexdigest()},ensure_ascii=False))
    except BaseException as error:
        write("FAILED.json",{"error_type":type(error).__name__,"error":str(error),"checks":checks,"counts":counts,"model_calls":0});raise


if __name__=="__main__":main()
