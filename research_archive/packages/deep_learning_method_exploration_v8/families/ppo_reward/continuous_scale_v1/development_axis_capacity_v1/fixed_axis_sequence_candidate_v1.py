"""SOURCE_ONLY exposed-development fixed-axis capacity; no learner/reward APIs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import time

HERE="families/ppo_reward/continuous_scale_v1/development_axis_capacity_v1/"
AXIS="families/ppo_reward/continuous_scale_v1/FROZEN_AXIS_GATE1_V1.json"
MAPPING="families/ppo_reward/continuous_scale_v1/axis_mapping.py"
JOIN="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/mean_sequence_candidate_v1.py"
MENU="freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json"
STOP=1793114740.0
ORDER=[("AXIS_L1_REPEAT",1.0),("AXIS_L05",.5),("AXIS_L025",.25),("AXIS_L075",.75),("AXIS_L0",0.0)]
CASES={"V8DEVCAP01H":("305b90192d653a234f2375e23d99ee98fe9ed9030239a05c767a8133d90164e9",2026102751),"V8DEVCAP01L":("cf2b735402009a7a15f6b8aff01c759579c4cfb93ac0301cc0f18803407d1ece",2026102752)}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def sequence(study,config):
    owner_pid=os.getpid();package=Path(os.environ["ACL2_PACKAGE"]).resolve();group=config["group"]
    pending=None;completed={};mapped={};stop=None;counts={"pure_map_entered":0,"pure_map_returned":0,"physical_proposals_yielded":0,"model_initialize_restore_forward_score_fit_RNG_sampling":0}
    from acl2_shared import put
    def owner():
        if os.getpid()!=owner_pid:raise GeneratorExit("CHILD_CANNOT_WRITE_DEV_CAPACITY_PARENT_METADATA")
    def save(name,value):owner();put("analysis/"+group+"_DEV_CAPACITY_"+name+".json",value)
    def frozen():
        owner()
        if time.time()>=min(config["local_stop_unix"],STOP):raise TimeoutError("DEV_CAPACITY_ORIGINAL_GLOBAL_LOCAL_STOP")
        for relative,expected in config["frozen_artifacts"].items():
            target=(package/relative).resolve()
            if not target.is_relative_to(package) or "real_runs" in target.parts or sha(target)!=expected:raise ValueError("EXACT_FIXED_CAPACITY_SOURCE_CHANGED:"+relative)
    def load(relative,name):
        spec=importlib.util.spec_from_file_location(name,package/relative);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def record(tag):
        owner();receipt=joined._original_joined_evidence(package,config,study,tag);completed[tag]=receipt;save("BRANCH_"+tag,receipt)
        if receipt["true_hard_safety_violation"] is True:raise RuntimeError("TRUE_HARD_STOP_BEFORE_PARTIAL_CONTINUATION")
        if receipt["true_hard_safety_violation"] is not False:raise RuntimeError("UNKNOWN_HARD_STOP_NO_SUCCESS_IMPUTATION")
        return receipt
    try:
        frozen();spec=config["development_axis_capacity"];approval=json.loads((package/spec["runtime_approval"]["path"]).read_text())
        if (sha(package/spec["runtime_approval"]["path"])!=spec["runtime_approval"]["sha256"] or approval.get("status")!="MAIN_APPROVED_FIXED_EXPOSED_DEV_CAPACITY_ONLY" or
            group not in approval["authorized_groups"] or approval["required_new_parameter_jobs_closed"] is not True or approval["pure_map_calls_per_case"]!=5 or approval["model_calls"]!=0 or
            config["scientific_branch"]!="EXPOSED_DEVELOPMENT_CAPABILITY_NOT_NEW_VALIDATION_NOT_TRAINING" or config.get("onpolicy_sampling") or config["worker"]!="v8_worker_v2.py" or config["job_wall_cap_s"]!=1800):raise ValueError("MAIN_EXPLICIT_FIXED_CAPABILITY_MAP_AND_PHYSICS_AUTHORITY_REQUIRED")
        if group not in CASES or (config["case_sha256"],config["condition"]["seed"])!=CASES[group] or approval["global_stop_unix"]!=STOP or config["fork_phase"]!="OUTBOUND" or config["fork_slot"]!=0:raise ValueError("EXACT_ORIGINAL_TWO_DEV_CASES_SEEDS_OUT0_AND_GLOBAL_CLOCK")
        if any(config["frozen_artifacts"].get(p)!=h for p,h in approval["source_files_sha256"].items()):raise ValueError("RUNTIME_MAIN_REVIEWED_SOURCE_CLOSURE_REQUIRED")
        if config["frozen_artifacts"].get(HERE+"fixed_axis_sequence_candidate_v1.py")!=sha(__file__):raise ValueError("EXACT_NEW_SEQUENCE_REQUIRED")
        if json.loads((package/"runtime/RUN_PLAN.json").read_text())["physical_timeout_s"]!=600:raise ValueError("ORIGINAL_600S_CHILD_CAP_REQUIRED")
        mapping=load(MAPPING,"_dev_capacity_axis_"+group);joined=load(JOIN,"_dev_capacity_joined_"+group)
        axis=json.loads((package/AXIS).read_text());axis_sha=spec["axis_object_sha256"];menu=json.loads((package/MENU).read_text())["action_contracts"]
        native={"B":menu[0],"EARLY_H150":menu[2]}
        for tag,key in [("B","B"),("EARLY_H150","H150")]:
            candidate=dict(config[key]);candidate.pop("id",None)
            if candidate!=native[tag]["resolved_base_candidate"]:raise ValueError("ORIGINAL_B_H150_REFERENCE_CHANGED")
        for tag,lam in ORDER:
            counts["pure_map_entered"]+=1;mapped[tag]=mapping.map_lambda(axis,lam,expected_axis_sha256=axis_sha);counts["pure_map_returned"]+=1
        save("FIXED_BEFORE_B",{"branch":config["scientific_branch"],"order":["B","EARLY_H150",*[t for t,_ in ORDER]],"mapped":mapped,"counts":dict(counts),"owner_pid":owner_pid,"no_results_or_policy_used":True,"lambda0_is_not_B":True})
        for tag in ["B","EARLY_H150",*[t for t,_ in ORDER]]:
            frozen()
            if time.time()>=min(config["local_stop_unix"],STOP)-600:stop="LESS_THAN_ORIGINAL_600S_CHILD_START_RESERVE";break
            pending=tag;action=native[tag]["action"] if tag in native else mapped[tag]["proposal_action"]
            recipe_sha=digest(native[tag]) if tag in native else mapped[tag]["full_recipe_sha256"]
            proposal={"tag":tag,"action":action,"category":"EXPOSED_DEVELOPMENT_FIXED_AXIS_CAPACITY","prediction":{"full_recipe_sha256":recipe_sha,"physical_action_sha256":digest(action),"fixed_order_not_selected_using_results":True,"not_training_or_new_validation":True}}
            if tag=="AXIS_L1_REPEAT":proposal["repeat_of"]="EARLY_H150"
            counts["physical_proposals_yielded"]+=1;yield proposal
            receipt=record(tag);pending=None
            if tag=="B" and (receipt["complete"] is not True or receipt["qualified"] is not True):raise RuntimeError("ORIGINAL_B_COMPLETE_QUALIFIED_WHOLE_JOB_GATE")
            if receipt["complete"] is not True:stop="ENGINEERING_PARTIAL_REST_NOT_RUN";break
            if tag=="AXIS_L1_REPEAT":
                relative="audit/"+group+"_AXIS_L1_REPEAT_REPEAT_GATE.json";raw=json.loads((package/relative).read_text())
                if raw.get("status")!="PASS" or Path(raw["a"]).resolve()!=package/"runtime/source/results"/(group+"_EARLY_H150") or Path(raw["b"]).resolve()!=package/"runtime/source/results"/(group+"_AXIS_L1_REPEAT"):raise RuntimeError("ORIGINAL_FULL_RAW_H150_LAMBDA1_EQUIVALENCE_REQUIRED")
                if any(receipt["original_row"].get(k)!=completed["EARLY_H150"]["original_row"].get(k) for k in ["JF","JM","axes","qualified"]):raise RuntimeError("ORIGINAL_H150_LAMBDA1_SCORER_METADATA_DIFFERS")
                save("MAPPING_GATE",{"status":"PASS_NEW_PAID_LAMBDA1_RAW_GATE","original_gate":{"path":relative,"sha256":sha(package/relative)},"H150_qualification_is_not_a_filter":True})
        save("FINAL",{"status":"FIXED_EXPOSED_DEV_CAPABILITY_EVIDENCE_ONLY","completed":completed,"NOT_RUN":[t for t in ["B","EARLY_H150",*[v for v,_ in ORDER]] if t not in completed],"stop":stop,"counts":counts,"original_qualification_JF_JM_errors_activation_and_native_cost_preserved":True,"root_parent_raw_scorer_owner_and_cost_close_review_required":True})
    except GeneratorExit:
        if os.getpid()!=owner_pid:return
        last=None
        if pending and getattr(study,"last_row",{}).get("id")==group+"_"+pending:
            try:last=joined._original_joined_evidence(package,config,study,pending)
            except BaseException as error:last={"root_review_required":True,"error_type":type(error).__name__,"error":str(error)}
        save("OWNER_CLOSE",{"pending":pending,"completed":completed,"last_original_returned_evidence":last,"counts":counts,"no_success_imputation":True});return
    except BaseException as error:
        if os.getpid()!=owner_pid:return
        save("ERROR",{"error_type":type(error).__name__,"error":str(error),"pending":pending,"completed":completed,"counts":counts,"no_success_imputation":True});raise
