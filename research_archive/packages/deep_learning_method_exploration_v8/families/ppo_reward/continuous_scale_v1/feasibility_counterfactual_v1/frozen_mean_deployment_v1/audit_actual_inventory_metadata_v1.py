"""Independent metadata-only audit; never import deployment/learner code."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

PACKAGE = Path(__file__).resolve().parents[5]
HERE = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_mean_deployment_v1/"
LABELS = ["FEAS_GLOBAL_RF1", "FEAS_GLOBAL_PPO3", "FEAS_CONTEXT_LOO_RF1", "FEAS_CONTEXT_LOO_PPO3"]
STOP = 1793114740.0


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def main():
    output = PACKAGE/HERE/"metadata_actual_inventory_review_v1"
    output.mkdir(exist_ok=False)
    started = time.time(); initial = resource.getrusage(resource.RUSAGE_SELF)
    files = {}; cached = {}; checks = []; blockers = []
    counters = {"file_SHA_reads":0, "unique_JSON_decodes":0, "source_AST_parses":0,
                "stored_policy_digest_checks":0, "stored_weight_digest_checks":0,
                "adapter_helper_predict_forward_model_init_restore_fit_RNG_physics_calls":0}

    def write(name, value):
        with (output/name).open("x") as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n")

    def path(relative):
        candidate = (PACKAGE/relative).resolve()
        if not candidate.is_relative_to(PACKAGE) or "real_runs" in candidate.parts or "results" in candidate.relative_to(PACKAGE).parts:
            raise ValueError("METADATA_AUDIT_FORBIDS_ACTUAL_RUN_OR_PHYSICAL_RESULTS:"+relative)
        return candidate

    def sha(relative):
        if relative not in files:
            files[relative] = hashlib.sha256(path(relative).read_bytes()).hexdigest()
            counters["file_SHA_reads"] += 1
        return files[relative]

    def read(relative):
        if relative not in cached:
            sha(relative); cached[relative] = json.loads(path(relative).read_text())
            counters["unique_JSON_decodes"] += 1
        return cached[relative]

    def check(label, value, detail=None):
        item = {"check":label, "PASS":bool(value)}
        if detail is not None: item["detail"] = detail
        checks.append(item)
        if not value: blockers.append(item)

    def ref(item, frozen=None):
        good = sha(item["path"]) == item["sha256"]
        if frozen is not None: good = good and frozen.get(item["path"]) == item["sha256"]
        check("EXACT_REFERENCE:"+item["path"], good)
        return read(item["path"])

    own_relative = str(Path(__file__).resolve().relative_to(PACKAGE))
    tree = ast.parse(path(own_relative).read_text()); counters["source_AST_parses"] += 1
    write("START.json", {"source_sha256":sha(own_relative), "source_AST_sha256":hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
                         "unix":started, "pid":os.getpid(), "startticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),
                         "model_or_physical_calls_permitted":0})
    try:
        inventory_path = "freeze/FEASIBILITY_FOUR_MEAN_ACTUAL_INVENTORY_V1.json"
        inventory = read(inventory_path)
        check("MAIN_SUPPLIED_ACTUAL_INVENTORY_SHA", sha(inventory_path)=="8cdf0b16ba19b472511a7e2142d4c1fc812e5581e8badfd8f819a677fca8fadf")
        auth = read("freeze/FEASIBILITY_FOUR_MEAN_MAIN_AUTHORIZATION_V1.json")
        freeze = ref(inventory["main_endpoint_freeze_review"])
        registration = ref(inventory["new_parameter_registration"])
        original_registration = ref(registration["original_registration"])
        activation = read("ACTIVATION.json")
        axis = ref(inventory["axis"])
        menu = ref(inventory["original_recipe_menu"])["action_contracts"]
        a3_manifest = ref(inventory["A3_adapter_manifest"])
        behavior = ref(inventory["original_behavior_exact_export"])["policy"]
        old_report = read("families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/reports/GATEL_ACTUAL_METADATA_REVIEW_V1/REPORT.json")
        check("PRIOR_ENDPOINT_METADATA_REPORT_EXACT", sha("families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/reports/GATEL_ACTUAL_METADATA_REVIEW_V1/REPORT.json")=="52f3fe9cf37bc3d94efeb2718a13bc720f5e05ed5c961f5fe22bfb7543a5e84a")
        check("INVENTORY_SCHEMA_STATUS_ALL4_FIXED_ORDER", inventory.get("schema")=="v8.frozen_feasibility_four_mean_inventory.v1" and inventory.get("status")=="ALL_FOUR_ACTUAL_FIXED_FINAL_ENDPOINTS_FROZEN_NOT_BEST" and [item["label"] for item in inventory["models"]]==LABELS)
        check("AUTH_SCHEMA_STATUS_JOBS_MEAN_ONLY_NO_PHYSICS", auth.get("schema")=="v8.frozen_feasibility_mean_main_approval.v1" and auth.get("status")=="APPROVED_BY_MAIN_FOR_FOUR_FROZEN_MEANS_ONLY" and auth.get("authorized_job_groups")==["V8FMEAN01","V8FMEAN02"] and auth.get("mean_forward_only") is True and auth.get("restore_fit_RNG_or_sampling")==0 and auth.get("physics_dispatch_authorized") is False)
        check("AUTH_BINDS_THIS_EXACT_INVENTORY", auth["inventory"]=={"path":inventory_path,"sha256":sha(inventory_path)})
        check("AUTH_CURRENT_DEPLOYMENT_CLOCK_NOT_TRAINING_RENEWAL", auth["approved_unix"]<=started<min(auth["deployment_deadline_unix"],STOP) and auth["activation_sha256"]==sha("ACTIVATION.json") and activation.get("hard_stop_unix")==STOP and activation.get("clock_must_not_reset") is True)
        check("MAIN_FREEZE_ALL4_NO_SELECTION_BEFORE_NEW_PHYSICS", freeze.get("schema")=="v8.frozen_feasibility_endpoint_freeze_review.v1" and freeze.get("status")=="ALL_FOUR_FINAL_MODELS_AND_PROGRAM_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS" and freeze.get("new_parameter_parents_not_started_at_freeze") is True and freeze.get("outcome_or_best_endpoint_selection") is False and freeze.get("source_files_sha256")==auth["source_files_sha256"] and freeze.get("models_object_sha256")==digest(inventory["models"]) and freeze.get("new_parameter_registration")==inventory["new_parameter_registration"] and freeze.get("original_validation_physics_start_count")==0)
        check("REGISTRATION_SCHEMA_ORIGINAL_TASK_AND_JOBS", registration.get("schema")=="v8.feasibility_four_mean_new_parameter_registration.v1" and registration.get("job_groups")==["V8FMEAN01","V8FMEAN02"] and registration.get("original_task_and_equations_unchanged") is True)
        check("AXIS_CONTENT_OBJECT_SHA", digest(axis)==inventory["axis_object_sha256"]=="ad1e44aca095b872ba673d077124841058f4ae55c9002b016f19253d22131faf")
        behavior_fields = ("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256")
        behavior_density = digest({key:behavior[key] for key in behavior_fields})
        policy_fields = (*behavior_fields,"seed","arm_id","gain","version")
        endpoints = []
        for item in inventory["models"]:
            result = ref(item["closed_result"]); done = ref(item["closed_DONE"])
            algorithm = "PPO" if item["label"].endswith("PPO3") else "REINFORCE"
            is_loo = "CONTEXT_LOO" in item["label"]
            policy = result["private_policies"][algorithm]
            expected_schema = "v8.beta_feasibility_context_loo_private_result.v1" if is_loo else "v8.beta_feasibility_counterfactual_private_result.v1"
            check(item["label"]+":RESULT_DONE_BASELINE_AND_FINAL_PATH", result.get("schema")==expected_schema and result.get("target")=="FEASIBILITY_ONLY" and done.get("status")=="COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" and done.get("result_sha256")==item["closed_result"]["sha256"] and item["policy_json_path"]==["private_policies",algorithm] and (not is_loo or (result.get("baseline_kind")=="PER_CONTEXT_LEAVE_OTHER_INDEPENDENT_DRAW_REWARD_OUT" and result.get("completed_global_baseline_reference",{}).get("sha256")==inventory["closed_global_result"]["sha256"])))
            pd = digest({key:policy[key] for key in policy_fields}); wd = digest(policy["weights"])
            counters["stored_policy_digest_checks"] += 1; counters["stored_weight_digest_checks"] += 1
            prior = old_report["four_fixed_endpoint_metadata"][item["label"]]
            check(item["label"]+":CANONICAL_POLICY_WEIGHTS_PRIOR_REPORT_PARITY", pd==item["policy_sha256"]==prior["policy_sha256"] and wd==item["weights_sha256"]==prior["weights_sha256"]==result["traces"][algorithm][-1]["weights_after_sha256"])
            nsteps = 3 if algorithm=="PPO" else 1
            check(item["label"]+":BEHAVIOR_DENSITY_AXIS_NORM_FINAL_STEP", result["behavior_density_sha256"]==behavior_density and policy["normalization"]==behavior["normalization"] and policy["axis_contract"]==axis and policy["axis_contract_sha256"]==inventory["axis_object_sha256"] and policy["feature_names"]==behavior["feature_names"] and len(policy["feature_names"])==25 and len(policy["weights"])==2 and all(len(row)==26 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in row) for row in policy["weights"]) and policy["counters"]["parameter_updates"]==nsteps and len(result["traces"][algorithm])==nsteps)
            endpoints.append({"label":item["label"],"policy_sha256":pd,"weights_sha256":wd,"behavior_density_sha256":result["behavior_density_sha256"],"private_step_count":nsteps,"stored_means_reused_without_forward":prior["stored_means"]})
        check("TWO_COMPLETE_GLOBAL_LOO_RESULTS_NO_SUBSTITUTION", inventory["models"][0]["closed_result"]==inventory["models"][1]["closed_result"]==inventory["closed_global_result"] and inventory["models"][2]["closed_result"]==inventory["models"][3]["closed_result"] and inventory["models"][0]["closed_result"]!=inventory["models"][2]["closed_result"])
        global_result = ref(inventory["closed_global_result"])
        rules = global_result["same_axis_lambda_margin_linear_rules"]
        check("ALL3_ALREADY_PAID_LINEAR_RULES_LAMBDA1_NO_REFIT", len(rules)==3 and all(rule["selected_lambda"]==1.0 for rule in rules.values()))
        minimum = {HERE+"mean_adapter_candidate_v1.py",HERE+"mean_sequence_candidate_v1.py","families/ppo_reward/continuous_scale_v1/beta_policy.py","families/ppo_reward/continuous_scale_v1/axis_mapping.py","families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py","families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json","source/v8_worker_v2.py","source/acl2_shared.py",auth["root_wrapper"]["path"]}
        check("AUTH_EXPLICIT_MINIMUM_SOURCE_CLOSURE_AND_ROOTWRAPPER", minimum<=set(auth["source_files_sha256"]) and auth["source_files_sha256"].get(auth["root_wrapper"]["path"])==auth["root_wrapper"]["sha256"])
        check("ROOTWRAPPER_EXACT_APPROVED_CANDIDATE_BYTES", sha(auth["root_wrapper"]["path"])==auth["root_wrapper"]["sha256"]==sha(HERE+"root_wrapper_candidate_v1.py")=="e6646056b393861631b75b817fe346e61b0e8e33208f1b19cba5e8268a743c67")
        for relative in [HERE+"mean_adapter_candidate_v1.py",HERE+"mean_sequence_candidate_v1.py",auth["root_wrapper"]["path"]]:
            ast.parse(path(relative).read_text()); counters["source_AST_parses"] += 1
        a3_bundle = ref(a3_manifest["bundles"]["A3"])
        check("A3_ADAPTER_MANIFEST_EXACT_AUTH_SOURCE", a3_manifest["adapter_sha256"]==auth["source_files_sha256"].get("families/critic_value/coverage_state_v3/source/live_selector_adapter_candidate_v1.py"))
        callback_profiles = [(proof,paths) for proof,paths in zip(a3_bundle["input_source_profiles"],a3_bundle["input_source_profile_paths"]) if paths["callback"]=="source/v8_worker_v2.py"]
        check("A3_EXACTLY_ONE_WORKER2_SEVENROLE_SOURCE_PROFILE", len(callback_profiles)==1 and set(callback_profiles[0][1])=={"capture","runtime","observer","observation_contract","history_guard","runtime_loader","callback"})
        proof, profile_paths = callback_profiles[0]
        for role, relative in profile_paths.items(): check("A3_PROFILE_CURRENT_STATIC_SOURCE:"+role, sha(relative)==proof[role])
        for r in [a3_manifest["bundles"]["A3"],*a3_manifest["api_files"]["A3"].values()]:
            check("A3_BUNDLE_OR_API_IN_AUTH:"+r["path"], auth["source_files_sha256"].get(r["path"])==r["sha256"])
        refs_required = [auth["inventory"],inventory["main_endpoint_freeze_review"],inventory["new_parameter_registration"],inventory["axis"],inventory["original_recipe_menu"],inventory["A3_adapter_manifest"],inventory["original_behavior_exact_export"],inventory["closed_global_result"],*sum(([i["closed_result"],i["closed_DONE"]] for i in inventory["models"]),[])]
        native = {"B":menu[0],"EARLY_H150":menu[2]}
        jobs = []
        for group, seed in [("V8FMEAN01",2026102753),("V8FMEAN02",2026102754)]:
            relative = "experiments/"+group+".json"; config = read(relative); frozen = config["frozen_artifacts"]; spec = config["frozen_feasibility_means"]
            for filename, expected in frozen.items(): check(group+":FROZEN_ACTUAL_SHA:"+filename, sha(filename)==expected)
            check(group+":OUT0_ALGORITHM_WORKER_NO_TRAINING", config["group"]==group and config["worker"]=="v8_worker_v2.py" and config["algorithm"]=="v8_frozen_feasibility_meanonly_v1" and config["fork_phase"]=="OUTBOUND" and config["fork_slot"]==0 and not config.get("onpolicy_sampling") and config["mode"]=="validation" and config["job_wall_cap_s"]==1800)
            check(group+":SPEC_EXACT_AUTH_INVENTORY", spec.get("schema")=="v8.frozen_feasibility_mean_job.v1" and spec["inventory"]==auth["inventory"] and spec["deployment_authorization"]["path"]=="freeze/FEASIBILITY_FOUR_MEAN_MAIN_AUTHORIZATION_V1.json" and sha(spec["deployment_authorization"]["path"])==spec["deployment_authorization"]["sha256"])
            for r in [*refs_required,spec["deployment_authorization"],{"path":"ACTIVATION.json","sha256":auth["activation_sha256"]}]:
                check(group+":RUNTIME_READ_REF_FROZEN:"+r["path"], frozen.get(r["path"])==r["sha256"])
            for filename, expected in {**auth["source_files_sha256"],**axis["source_files_sha256"]}.items(): check(group+":AUTH_AXIS_RUNTIME_SOURCE_PIN:"+filename,frozen.get(filename)==expected==sha(filename))
            for tag, recipe in native.items():
                candidate = dict(config["B"] if tag=="B" else config["H150"]); candidate.pop("id",None)
                check(group+":NATIVE_REFERENCE_CANDIDATE:"+tag,candidate==recipe["resolved_base_candidate"])
            check(group+":ONLY_TWO_NATIVE_REFERENCE_ACTIONS", [i["tag"] for i in config["actions"]]==["B","EARLY_H150"] and [i["action"] for i in config["actions"]]==[native[k]["action"] for k in ("B","EARLY_H150")])
            registered = next(i for i in registration["conditions"] if i["group"]==group)
            original = next(i for i in original_registration["cases"] if i["case_key"]==registered["case_key"])
            check(group+":ORIGINAL_SEED_PAYLOAD_ROUTE_NO_NEW_TASK", config["condition"]["seed"]==registered["seed"]==original["seed"]==seed and config["case_sha256"]==registered["payload"]["sha256"]==original["payload_sha256"]==sha(config["case_path"])==sha(registered["payload"]["path"]) and registered["payload"]["path"]==original["payload_relative_path"] and original["role"]=="FROZEN_VALIDATION" and original["task_equal_original"] is True)
            jobs.append({"group":group,"config_sha256":sha(relative),"seed":seed,"case_key":registered["case_key"],"payload_sha256":config["case_sha256"],"frozen_artifact_count":len(frozen),"required_runtime_reference_count":len({i['path'] for i in refs_required}),"actual_job_source_manifest_and_prefork_runtime_proof":"NOT_CREATED_OR_CALLED_BY_THIS_REVIEW; worker must create and adapter must verify at actual coldOUT0"})
        events_relative = "runtime/ATTEMPTS.jsonl"
        raw_lines = path(events_relative).read_bytes().splitlines(); sha(events_relative)
        parent_starts = []
        for line in raw_lines:
            event = json.loads(line)
            if event.get("event")=="START" and (event.get("id") in {"V8VAL01_parent","V8VAL02_parent","V8FMEAN01_parent","V8FMEAN02_parent"} or (str(event.get("group","")).startswith(("V8VAL","V8FMEAN")) and event.get("kind")=="LEGAL_COLD_PARENT")):
                parent_starts.append({key:event.get(key) for key in ("id","group","unix","utc","kind","config_sha256")})
        check("NO_ORIGINAL_VALIDATION_OR_FOUR_MEAN_PARENT_START_AS_OF_AUDIT", not parent_starts,parent_starts)
        final = resource.getrusage(resource.RUSAGE_SELF)
        report = {"schema":"v8.frozen_feasibility_four_mean_independent_metadata_review.v1","status":"PASS_METADATA_PREREQUISITES_ONLY_NOT_PHYSICAL_DISPATCH_AUTHORITY" if not blockers else "BLOCKED_METADATA_PREREQUISITES", "reviewed_inventory_sha256":sha(inventory_path),"reviewed_unix":time.time(),"checks":checks,"blockers":blockers,"jobs":jobs,"endpoints":endpoints,"behavior_density_sha256":behavior_density,"A3_seven_role_static_profile":profile_paths,"A3_live_proof_not_performed":True,"required_future_gates":["Actual original worker coldOUT0 and seven loaded roles/prefork payload proof before any B","B full qualification whole-job gate","Complete H150 may fail motion; no H150 qualification filter","New paid lambda1 repeat_of EARLY_H150 must pass full raw equivalence and original result parity","Original hard violation TRUE or UNKNOWN stops; no success imputation","Four means all retained; exact fullrecipe deployment sharing only; no independent replication claim","Separate main physical authorization, original global deadline and actual supervisor/source manifest closure"],"actual_parent_starts_as_of_audit":parent_starts,"file_identities_sha256":files,"counters":counters,"wall_s":time.time()-started,"CPU_s":final.ru_utime+final.ru_stime-initial.ru_utime-initial.ru_stime,"peak_RSS_KiB":final.ru_maxrss,"binary":str(Path(sys.executable).resolve()),"binary_sha256":hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),"real_run_raw_physical_result_active_or_new_validation_outcome_reads":False,"model_calls":0}
        write("REVIEW.json", report)
        write("DONE.json",{"status":report["status"],"review_sha256":hashlib.sha256((output/"REVIEW.json").read_bytes()).hexdigest(),"model_calls":0,"blocker_count":len(blockers)})
        print(json.dumps({"status":report["status"],"checks":len(checks),"blockers":blockers,"jobs":jobs,"counts":counters,"review_sha256":hashlib.sha256((output/"REVIEW.json").read_bytes()).hexdigest()},ensure_ascii=False))
    except BaseException as error:
        write("FAILED.json",{"error_type":type(error).__name__,"error":str(error),"counters":counters,"checks":checks,"model_calls":0}); raise


if __name__ == "__main__":
    main()
