"""SOURCE_ONLY one closed six-mean group; stdlib metadata, no learner/raw APIs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import time

HERE="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/"
MASTER_SHA="b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e"
LABELS=["FEAS_GLOBAL_RF1","FEAS_GLOBAL_PPO3","FEAS_CONTEXT_LOO_RF1","FEAS_CONTEXT_LOO_PPO3","FEAS_SPAN_GEOMETRY_RF1","FEAS_SPAN_GEOMETRY_PPO3"]
ROLES={"capture","runtime","observer","observation_contract","history_guard","runtime_loader","callback"}
HARD=["force","moment","torque","human_speed","human_acceleration","robot_speed","session_clearance","true_clearance","measured_sleeve_clearance","no_shank_table_contact","no_human_rom_violation"]


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def at(value,pointer):
    for key in pointer:value=value[key]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package",required=True);parser.add_argument("--approval",required=True);parser.add_argument("--approval-sha256",required=True)
    args=parser.parse_args();package=Path(args.package).resolve();cache={};identities={};output=None;created=False
    counts={"JSON_decodes":0,"target_event_JSON_decodes":0,"unique_file_hashes":0,"policy_digest_checks":0,"weight_digest_checks":0,"receipt_metadata_checks":0,"new_model_forward_score_fit_RNG_physics":0}
    def path(relative):
        target=(package/relative).resolve()
        if not target.is_relative_to(package) or "real_runs" in target.parts or "results" in target.relative_to(package).parts or target.suffix in (".npz",".gz",".csv",".parquet"):
            raise ValueError("NO_RAW_NATIVE_SCORER_RESULT_OR_ACTUAL_RUN_ACCESS")
        return target
    def sha(relative):
        if relative not in identities:identities[relative]=hashlib.sha256(path(relative).read_bytes()).hexdigest();counts["unique_file_hashes"]+=1
        return identities[relative]
    def read(relative):
        if relative not in cache:sha(relative);cache[relative]=json.loads(path(relative).read_text());counts["JSON_decodes"]+=1
        return cache[relative]
    def ref(reference):
        if sha(reference["path"])!=reference["sha256"]:raise ValueError("EXACT_APPROVED_METADATA_REF_CHANGED:"+reference["path"])
        return read(reference["path"])
    def require(condition,message):
        if not condition:raise ValueError(message)
    def write(name,value):
        with (output/name).open("x") as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    approval_relative=str(Path(args.approval).resolve().relative_to(package));require(sha(approval_relative)==args.approval_sha256,"EXACT_MAIN_AUTHORITY_REQUIRED")
    auth=read(approval_relative);group=auth["group"]
    require(auth.get("schema")=="v8.sixmean_closed_metadata_review_main_approval.v2" and auth.get("status")=="APPROVED_ONCE_FOR_EXACT_CLOSED_GROUP_METADATA_ONLY" and group in ("V8FMEAN03","V8FMEAN04") and auth.get("model_calls_permitted")==0 and auth.get("all_actual_owners_enumerated") is True,"EXACT_SEPARATELY_APPROVED_CLOSED_GROUP_ONLY")
    def clock():require(auth["local_start_unix"]<=time.time()<min(auth["local_stop_unix"],1793114740.0),"CLOSED_METADATA_LOCAL_GLOBAL_CLOCK")
    require(0<auth["local_stop_unix"]-auth["local_start_unix"]<=60,"MAX60S_INDEPENDENT_METADATA_BUDGET")
    clock();manifest=ref(auth["source_manifest"])
    for relative,expected in manifest["files_sha256"].items():require(sha(relative)==expected,"REVIEW_SOURCE_OR_CONTRACT_CHANGED")
    require(auth["root_master"]["sha256"]==MASTER_SHA and sha(auth["root_master"]["path"])==MASTER_SHA,"EXACT_FROZEN_MASTER_RELEASE_REQUIRED")
    output=path(auth["output_relative_path"]);require(output==package/HERE/"outputs"/(group+"_ONCE_V2") and not output.exists(),"EXCLUSIVE_PER_CLOSED_GROUP_OUTPUT_NO_RETRY")
    output.parent.mkdir(exist_ok=True);output.mkdir(exist_ok=False);created=True
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    initial=resource.getrusage(resource.RUSAGE_SELF);started=time.time()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("CLOSED_METADATA_WALL_STOP")))
    signal.setitimer(signal.ITIMER_REAL,max(.001,min(auth["local_stop_unix"],1793114740.0)-time.time()))
    write("START.json",{"group":group,"unix":started,"pid":os.getpid(),"start_ticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),"approval_sha256":args.approval_sha256,"source_manifest":auth["source_manifest"],"CPU_user_s":initial.ru_utime,"CPU_system_s":initial.ru_stime,"RSS_peak_KiB":initial.ru_maxrss,"AS_limit_bytes":1073741824,"model_calls":0})
    try:
        # Main supplies JSON pointers into original closed metadata, not guessed
        # supervisor field names or new fabricated process/request identities.
        closed=ref(auth["artifacts"]["closed_review"])
        for meaning,expected in [("group",group),("all_known_owners_closed",True),("all_started_children_joined",True),("survivors_empty",[])]:
            require(at(closed,auth["closure_fact_pointers"][meaning])==expected,"ORIGINAL_CLOSED_OWNER_FACT_NOT_ESTABLISHED:"+meaning)
        require(auth["owners"],"EXACT_ORIGINAL_PID_STARTTICKS_LIST_REQUIRED");owner_proof=[]
        for owner in auth["owners"]:
            record=at(ref(owner["original_metadata_ref"]),owner["record_pointer"])
            require(record[owner["pid_key"]]==owner["pid"] and record[owner["start_ticks_key"]]==owner["start_ticks"] and isinstance(owner["start_ticks"],int) and owner["start_ticks"]>0,"OWNER_PID_TICKS_NOT_ORIGINAL_METADATA")
            proc=Path("/proc")/str(owner["pid"])/"stat";current=int(proc.read_text().rsplit(")",1)[1].split()[19]) if proc.exists() else None
            require(current!=owner["start_ticks"],"ORIGINAL_OWNER_STILL_ACTIVE_NO_GROUP_READS")
            owner_proof.append({"pid":owner["pid"],"original_start_ticks":owner["start_ticks"],"current_start_ticks":current,"closed":True})
        artifacts=auth["artifacts"];config=ref(artifacts["config"]);inventory=ref(artifacts["inventory"]);job=ref(artifacts["job_source_manifest"])
        require(artifacts["config"]["path"]=="experiments/"+group+".json" and config["group"]==group and job["config_sha256"]==artifacts["config"]["sha256"] and artifacts["inventory"]["sha256"]=="c29d4607e6a32298493c338aeb1f35a3ba6a10ffdd9ae9abb212e119d4c17b1c","EXACT_CONFIG_JOB_SOURCE_AND_SIX_INVENTORY")
        for relative,expected in config["frozen_artifacts"].items():require(sha(relative)==expected,"FROZEN_ARTIFACT_CHANGED:"+relative)
        require(artifacts["pre_B"]["path"]=="predictions/"+group+"_FEASIBILITY_SIX_ALL_PRE_B_DECISIONS.json","EXACT_ORIGINAL_PRE_B_OUTPUT")
        pre=ref(artifacts["pre_B"]);choice=pre["decisions"];api=choice["actual_counts"]
        require(choice["all_choices_before_B"] is True and list(choice["decisions"])==LABELS and set(pre["aliases"])==set(LABELS),"ORIGINAL_ALL6_BEFORE_B_DECISIONS_REQUIRED")
        require(api["logical_policy_copies"]==6 and api["deploy_mean_entered"]==6 and api["deploy_mean_returned"]+api["deploy_mean_numerical_rejection"]==6 and api["deploy_mean_returned"]<=api["beta_internal_forward_counter_delta"]<=6 and api["restore_initialize_fit_gradient_RNG_sampling_physics"]==0 and api["fixed_linear_lambda1_map"]==1,"ORIGINAL_ACTUAL6_COUNTERS_NO_RESTORE_RNG_FIT")
        require(all(api[k]==1 for k in ["actual_seven_role_proof_entered","actual_seven_role_proof_returned","causal_context39_entered","causal_context39_returned","commissioned25_projection"]),"ORIGINAL_CAUSAL_API_COUNTS")
        audit=choice["proof_audit"];proof=choice["actual_seven_role_proof"]
        require(set(proof)==set(audit["roles"])==ROLES and audit["job_source_manifest_sha256"]==artifacts["job_source_manifest"]["sha256"] and audit["config_sha256"]==artifacts["config"]["sha256"] and audit["current_task_B_or_candidate_result_used"] is False and audit["actual_in_memory_callback_code_checked"] is True,"ORIGINAL_LIVE_SOURCE_PROOF_METADATA")
        for role,row in audit["roles"].items():
            require(proof[role]==row["actual_file_sha256"]==row["job_manifest_file_sha256"]==row["expected_profile_sha256"]==job["files"][row["path"]]==sha(row["path"]) and Path(row["actual_loaded_module_file"]).resolve()==path(row["path"]),"ORIGINAL_SEVEN_LOADED_ROLE_IDENTITY:"+role)
        require([m["label"] for m in inventory["models"]]==LABELS,"FIXED6_NO_BEST_SELECTION")
        fields=("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version");model_ids={}
        for item in inventory["models"]:
            result=ref(item["closed_result"]);algorithm=item["policy_json_path"][1];policy=result["private_policies"][algorithm]
            pd=digest({k:policy[k] for k in fields});wd=digest(policy["weights"]);counts["policy_digest_checks"]+=1;counts["weight_digest_checks"]+=1
            require(pd==item["policy_sha256"] and wd==item["weights_sha256"],"FROZEN_POLICY_WEIGHTS_NOT_ACTUAL_FIXED_ENDPOINT")
            decision=choice["decisions"][item["label"]]
            if decision["status"]!="NUMERICAL_REJECTION_EXPLICIT_B_ANCHOR":
                prediction=decision["prediction"]
                require(decision["status"]=="FROZEN_MEAN_NOT_PHYSICALLY_QUALIFIED" and decision["model"]==item and prediction["policy_sha256"]==pd and digest(prediction["full_recipe"])==prediction["full_recipe_sha256"] and digest(prediction["proposal_action"])==prediction["physical_action_sha256"],"ACTUAL_PREB_POLICY_FULLRECIPE_IDENTITY")
            else:require(decision["fallback_core"]=={"tag":"B","action":choice["native_reference_actions"]["B"]} and decision["original_qualification_granted"] is False,"NUMERICAL_REJECT_ONLY_EXPLICIT_B_ANCHOR")
            model_ids[item["label"]]={"policy_sha256":pd,"weights_sha256":wd}
        execution=ref(artifacts["execution"])
        require(artifacts["execution"]["path"] in ["analysis/"+group+"_FEASIBILITY_SIX_"+suffix+".json" for suffix in ["FINAL_EXECUTION_LINK","ERROR","OWNER_CLOSE"]],"EXACT_CLOSED_FINAL_OR_ERROR_METADATA")
        if artifacts["execution"]["path"].endswith("FINAL_EXECUTION_LINK.json"):
            require(execution["pre_B_decisions"]==choice and execution["aliases"]==pre["aliases"] and execution["fixed_plan"]==pre["plan"] and execution["actual_adapter_counts"]==api,"CLOSED_FINAL_NOT_EXACT_ORIGINAL_PREB_PLAN")
        require(execution["counts"]["new_initialize_restore_fit_RNG_direct_physics"]==0,"ORIGINAL_SEQUENCE_READ_ONLY_COUNTER")
        events={};target_rows=[]
        for raw in path("runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
            if group.encode() not in raw:continue
            event=json.loads(raw);counts["target_event_JSON_decodes"]+=1
            if event.get("event") not in ("START","END"):continue
            entry={"record":event,"raw_line_sha256":hashlib.sha256(raw).hexdigest()}
            target_rows.append(entry)
            if event.get("event")=="START" and event.get("group")==group:
                require(isinstance(event.get("id"),str) and event["id"].startswith(group+"_") and event.get("config_sha256")==artifacts["config"]["sha256"] and event.get("job_source_sha256")==artifacts["job_source_manifest"]["sha256"],"EXACT_GROUP_CONFIG_JOB_START_ID_REQUIRED")
                key=(event["id"],"START");require(key not in events,"DUPLICATE_ORIGINAL_START_END");events[key]=entry
        start_ids={ident for ident,kind in events if kind=="START"}
        for entry in target_rows:
            event=entry["record"]
            if event.get("event")!="END" or event.get("id") not in start_ids:continue
            require("group" not in event or event["group"]==group,"ORIGINAL_END_OPTIONAL_GROUP_CONFLICT")
            key=(event["id"],"END");require(key not in events,"DUPLICATE_ORIGINAL_START_END");events[key]=entry
        receipts={};registered_tags=["B","EARLY_H150","FEAS_SIX_LAMBDA1_REPEAT",*[item["tag"] for item in pre["plan"]]]
        present={tag for tag in registered_tags if path("analysis/"+group+"_FEASIBILITY_SIX_BRANCH_"+tag+".json").exists()}
        require(set(auth["branch_refs"])==present,"ALL_EXISTING_ORIGINAL_PLAN_BRANCH_RECEIPTS_MUST_BE_APPROVED")
        for tag,reference in auth["branch_refs"].items():
            require(reference["path"]=="analysis/"+group+"_FEASIBILITY_SIX_BRANCH_"+tag+".json","EXACT_ORIGINAL_BRANCH_SIDECAR")
            branch=ref(reference);row=branch["original_row"];ident=group+"_"+tag
            require(branch["original_result"]["path"]=="attempts/"+ident+"_RESULT.json","EXACT_ORIGINAL_ATTEMPT_RESULT_METADATA")
            original=ref(branch["original_result"])
            require(row["id"]==ident and all(row.get(k)==original.get(k) for k in ["id","complete","qualified","error","actual_new_native_steps","JF","JM","axes"]),"ORIGINAL_RESULT_METADATA_PARITY")
            for event_type in ("START","END"):require(branch["original_events"][event_type]==events[(ident,event_type)],"ORIGINAL_EVENT_RECORD_RAWLINE_HASH")
            require(events[(ident,"START")]["record"].get("config_sha256")==artifacts["config"]["sha256"] and events[(ident,"END")]["record"].get("joined") is True and events[(ident,"END")]["record"].get("parent_hash_equal") is True,"ORIGINAL_CONFIG_JOINED_UNCHANGED_PARENT_RECEIPT")
            conditions=branch["hard_safety_conditions"];require(set(conditions)==set(HARD),"ORIGINAL_ELEVEN_HARD_FIELDS_REQUIRED")
            hard=True if row.get("true_hard_safety_violation") is True or any(v is False for v in conditions.values()) else False if all(v is True for v in conditions.values()) else None
            require(branch["true_hard_safety_violation"] is hard and branch["new_scorer_model_or_physics_calls_by_helper"]==0,"ORIGINAL_HARD_THREE_VALUE_NOT_RECLASSIFIED")
            counts["receipt_metadata_checks"]+=1;receipts[tag]=branch
        def receipt_state(tag):
            ident=group+"_"+tag;branch=receipts.get(tag)
            if branch is None:return {"state":"ATTEMPTED_BUT_MISSING_CLOSED_RECEIPT" if (ident,"START") in events else "NOT_RUN","actual_START":events.get((ident,"START")),"source_receipt":None}
            row=branch["original_row"]
            return {"state":"COMPLETE" if row.get("complete") is True else "ENGINEERING_PARTIAL","complete":row.get("complete"),"original_qualified":row.get("qualified"),"JF":row.get("JF"),"JM":row.get("JM"),"error":row.get("error"),"true_hard_safety_violation_three_value":branch["true_hard_safety_violation"],"actual_new_native_steps":row.get("actual_new_native_steps"),"source_receipt":auth["branch_refs"][tag]}
        gates={tag:receipt_state(tag) for tag in ["B","EARLY_H150","FEAS_SIX_LAMBDA1_REPEAT"]}
        rawgate=None
        if artifacts.get("lambda1_raw_gate"):
            rawgate=ref(artifacts["lambda1_raw_gate"])
            require(artifacts["lambda1_raw_gate"]["path"]=="audit/"+group+"_FEAS_SIX_LAMBDA1_REPEAT_REPEAT_GATE.json","ORIGINAL_MAPPING_GATE_PATH")
        mean_tags=[item["tag"] for item in pre["plan"]];any_mean_started=any((group+"_"+tag,"START") in events for tag in mean_tags)
        if any_mean_started:
            require(gates["B"].get("complete") is True and gates["B"].get("original_qualified") is True and gates["EARLY_H150"].get("complete") is True and gates["FEAS_SIX_LAMBDA1_REPEAT"].get("complete") is True and all(gate.get("true_hard_safety_violation_three_value") is False for gate in gates.values()) and rawgate is not None and rawgate.get("status")=="PASS","ORIGINAL_B_H150_LAMBDA1_GATES_BEFORE_ACTUAL_MEANS")
            require(Path(rawgate["a"]).resolve()==package/"runtime/source/results"/(group+"_EARLY_H150") and Path(rawgate["b"]).resolve()==package/"runtime/source/results"/(group+"_FEAS_SIX_LAMBDA1_REPEAT"),"MAPPING_GATE_METADATA_BINDS_ACTUAL_NEW_REPEAT")
            for key in ["JF","JM","axes","qualified"]:require(receipts["EARLY_H150"]["original_row"].get(key)==receipts["FEAS_SIX_LAMBDA1_REPEAT"]["original_row"].get(key),"ORIGINAL_H_LAMBDA1_SCORER_METADATA_PARITY")
        lambda1=choice["lambda1_same_axis_linear_controls"]["mapped"]
        require(digest(lambda1["full_recipe"])==lambda1["full_recipe_sha256"] and digest(lambda1["proposal_action"])==lambda1["physical_action_sha256"] and pre["lambda1_is_new_paid_repeat_not_static_H150_alias"] is True,"ORIGINAL_LAMBDA1_NEW_PAID_MAPPING_IDENTITY")
        plan_by_tag={item["tag"]:item for item in pre["plan"]};require(len(plan_by_tag)==len(pre["plan"]),"UNIQUE_ORIGINAL_PHYSICAL_PLAN_TAGS")
        for item in pre["plan"]:require(digest(item["full_recipe"])==item["full_recipe_sha256"],"ORIGINAL_PLAN_FULL_RECIPE_SHA")
        linked={}
        for label in LABELS:
            decision=choice["decisions"][label];alias=pre["aliases"][label];tag=alias["tag"]
            require(tag in ["B","FEAS_SIX_LAMBDA1_REPEAT",*mean_tags],"ALIAS_OUTSIDE_ORIGINAL_CONTINUOUS_PLAN")
            if decision["status"]=="NUMERICAL_REJECTION_EXPLICIT_B_ANCHOR":require(tag=="B","REJECT_ALIAS_MUST_BE_B")
            else:
                mapped=decision["prediction"];target=lambda1 if tag=="FEAS_SIX_LAMBDA1_REPEAT" else plan_by_tag.get(tag)
                require(target is not None and mapped["full_recipe_sha256"]==target["full_recipe_sha256"] and mapped["full_recipe"]==target["full_recipe"] and mapped["proposal_action"]==target.get("proposal_action",target.get("action")),"EACH_MODEL_ALIAS_MUST_BE_ITS_ACTUAL_FULL_RECIPE")
                if tag in plan_by_tag:require(label in plan_by_tag[tag]["selected_by"],"ORIGINAL_PLAN_MISSING_SELECTED_MODEL")
            linked[label]={"model":model_ids[label],"decision_status":decision["status"],"alias":alias,"actual_receipt":receipt_state(tag),"numerical_rejection_B_anchor_not_model_qualification":decision["status"]=="NUMERICAL_REJECTION_EXPLICIT_B_ANCHOR","shared_recipe_is_not_independent_replication":True}
        clock();final=resource.getrusage(resource.RUSAGE_SELF)
        report={"schema":"v8.sixmean_closed_group_metadata_review.v2","status":"CLOSED_METADATA_LINKED_SIX_RESULTS_NOT_A_NEW_EVALUATION","group":group,"root_master":auth["root_master"],"owners":owner_proof,"original_pre_B_actual_API_counts":api,"original_execution_counts":execution.get("counts"),"original_execution_error_or_stop":{k:execution.get(k) for k in ["error_type","error","stopped","pending"]},"original_gates":gates,"lambda1_raw_gate_metadata":rawgate,"all_six_alias_receipts":linked,"original_END_native_steps_by_attempt":{ident:entry["record"].get("native_steps") for (ident,kind),entry in events.items() if kind=="END"},"original_event_identities":list(events.values()),"counts_this_review":counts,"source_ref_sha256":identities,"no_new_model_API_or_physics":True,"no_raw_or_scorer_imports":True,"qualification_is_original_receipt_only_not_new_control_gain":True,"wall_s":time.time()-started,"CPU_s":final.ru_utime+final.ru_stime-initial.ru_utime-initial.ru_stime,"peak_RSS_KiB":final.ru_maxrss}
        write("REPORT.json",report);write("DONE.json",{"status":report["status"],"report_sha256":hashlib.sha256((output/"REPORT.json").read_bytes()).hexdigest(),"new_model_or_physics_calls":0})
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0)
        if created:write("FAILED.json",{"status":"FAILED_METADATA_REVIEW_PRESERVED_NO_RETRY","error_type":type(error).__name__,"error":str(error),"counts":counts,"new_model_or_physics_calls":0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=="__main__":main()
