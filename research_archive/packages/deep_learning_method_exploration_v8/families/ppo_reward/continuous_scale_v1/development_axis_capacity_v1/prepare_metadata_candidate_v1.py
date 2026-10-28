"""SOURCE_ONLY approved metadata builder; no map, learner or physics imports."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import time

HERE="families/ppo_reward/continuous_scale_v1/development_axis_capacity_v1/"
STOP=1793114740.0
ORIGINALS={"V8DEVCAP01H":("V8BETA01H","4f01e7b9d056d73733ea37abc0e24a12e56c492624d2ca334ef5df7bd68a7577","305b90192d653a234f2375e23d99ee98fe9ed9030239a05c767a8133d90164e9",2026102751),"V8DEVCAP01L":("V8BETA01L","0c71ecc7b3d995d654a95aa37a0a981039e5fd62a5f27f5c502799ad8e57d2fe","cf2b735402009a7a15f6b8aff01c759579c4cfb93ac0301cc0f18803407d1ece",2026102752)}

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument("--package",required=True);cli.add_argument("--approval",required=True);cli.add_argument("--approval-sha256",required=True);args=cli.parse_args()
    package=Path(args.package).resolve();written={};started=False
    def path(relative):
        target=(package/relative).resolve()
        if not target.is_relative_to(package) or "real_runs" in target.parts or "results" in target.relative_to(package).parts:raise ValueError("NO_POLICY_RUN_RAW_OR_OUTCOME_PATH")
        return target
    def sha(relative):return hashlib.sha256(path(relative).read_bytes()).hexdigest()
    def read(relative):return json.loads(path(relative).read_text())
    def ref(r):
        if sha(r["path"])!=r["sha256"]:raise ValueError("APPROVED_EXACT_METADATA_REF_CHANGED:"+r["path"])
        return read(r["path"])
    def write(relative,value):
        target=path(relative)
        with target.open("x") as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n");f.flush();os.fsync(f.fileno())
        fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        written[relative]=sha(relative);return {"path":relative,"sha256":written[relative]}
    ar=str(Path(args.approval).resolve().relative_to(package))
    if sha(ar)!=args.approval_sha256:raise ValueError("EXACT_NEW_MAIN_METADATA_APPROVAL_REQUIRED")
    auth=read(ar)
    if (auth.get("schema")!="v8.dev_axis_capacity_metadata_main_approval.v1" or auth.get("status")!="MAIN_APPROVED_METADATA_PREPARATION_ONLY" or
        auth.get("model_map_fit_RNG_physics_calls")!=0 or auth.get("global_stop_unix")!=STOP or auth.get("builder_sha256")!=sha(HERE+"prepare_metadata_candidate_v1.py")):raise ValueError("MAIN_SOURCE_REVIEW_REQUIRED_NO_AUTOMATIC_ACTIVATION")
    def clock():
        if not auth["local_start_unix"]<=time.time()<min(auth["local_stop_unix"],STOP):raise TimeoutError("METADATA_PREPARATION_LOCAL_GLOBAL_STOP")
    if not 0<auth["local_stop_unix"]-auth["local_start_unix"]<=60:raise ValueError("METADATA_PREPARATION_MAX60S")
    clock();manifest=ref(auth["source_manifest"]);requirements=ref(manifest["runtime_source_requirements"])
    if auth["source_files_sha256"]!=requirements["runtime_sources_sha256"]:raise ValueError("CURRENT_HASH_CANNOT_UPGRADE_MAIN_SOURCE_APPROVAL")
    for original_manifest in requirements["baseline_job_source_manifests"].values():ref(original_manifest)
    for relative,expected in {**manifest["files_sha256"],**auth["source_files_sha256"]}.items():
        if sha(relative)!=expected:raise ValueError("SOURCE_CLOSURE_CHANGED:"+relative)
        if path(relative).suffix==".py":ast.parse(path(relative).read_text())
    if sha("ACTIVATION.json")!="6c9046e286afc923ca5b1ad9c4f4c787c95ad858e88ab8d3ec6f26e7d096694f" or read("ACTIVATION.json")["hard_stop_unix"]!=STOP:raise ValueError("ORIGINAL_ACTIVATION_REQUIRED")
    runtime=ref(auth["runtime_approval"])
    if (runtime.get("status")!="MAIN_APPROVED_FIXED_EXPOSED_DEV_CAPACITY_ONLY" or runtime.get("authorized_groups")!=list(ORIGINALS) or
        runtime.get("required_new_parameter_jobs_closed") is not True or runtime.get("pure_map_calls_per_case")!=5 or runtime.get("model_calls")!=0 or
        runtime.get("global_stop_unix")!=STOP or runtime.get("source_files_sha256")!=auth["source_files_sha256"]):raise ValueError("INDEPENDENT_FIXED_MAP_AND_FUTURE_PHYSICS_MAIN_AUTHORITY_REQUIRED")
    ref(runtime["required_new_parameter_jobs_closed_review"])
    targets=[HERE+n for n in ["METADATA_PREPARE_START_V1.json","METADATA_PREPARE_END_V1.json","METADATA_PREPARE_FAILED_V1.json","ACTUAL_REGISTRATION_V1.json"]]+["experiments/"+g+".json" for g in ORIGINALS]
    if any(path(p).exists() for p in targets):raise ValueError("EXCLUSIVE_NEW_METADATA_ONLY_NO_RETRY")
    try:
        write(HERE+"METADATA_PREPARE_START_V1.json",{"pid":os.getpid(),"unix":time.time(),"approval":{"path":ar,"sha256":args.approval_sha256},"new_map_model_physics_calls":0});started=True
        refs={r["path"]:r["sha256"] for r in [auth["source_manifest"],manifest["runtime_source_requirements"],auth["runtime_approval"],runtime["required_new_parameter_jobs_closed_review"]]};refs[ar]=args.approval_sha256
        refs.update(manifest["files_sha256"]);refs.update(auth["source_files_sha256"])
        configs=[];conditions=[]
        for group,(old,old_sha,case_sha,seed) in ORIGINALS.items():
            clock();old_path="experiments/"+old+".json"
            if sha(old_path)!=old_sha:raise ValueError("ORIGINAL_BETA01_CONFIG_CHANGED")
            source=read(old_path)
            if source["case_sha256"]!=case_sha or sha(source["case_path"])!=case_sha or source["condition"]["seed"]!=seed or source["fork_phase"]!="OUTBOUND" or source["fork_slot"]!=0:raise ValueError("EXACT_ORIGINAL_EXPOSED_DEV_CASE_SEED_PREFIX_REQUIRED")
            keep=["B","H150","case_key","case_path","case_sha256","condition","continuation_policy","fork_phase","fork_slot","matched_reference_group","mode","short_horizons_s","worker"]
            config={k:source[k] for k in keep if k in source}
            config.update(group=group,algorithm="v8_fixed_development_axis_capacity_v1",mode="development",scientific_branch="EXPOSED_DEVELOPMENT_CAPABILITY_NOT_NEW_VALIDATION_NOT_TRAINING",job_wall_cap_s=1800,onpolicy_sampling=False,historical_repeats={})
            config["condition"]={**source["condition"],"name":group,"role":"Fixed-axis capacity on exposed original Beta training context; no fitting, selection or new validation."}
            config["local_stop_unix"]=runtime["local_stop_unix_by_group"][group]
            if not time.time()<config["local_stop_unix"]<=STOP:raise ValueError("ORIGINAL_GLOBAL_STOP_CANNOT_EXTEND")
            menu=read("freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json")["action_contracts"]
            config["actions"]=[{"tag":tag,"action":menu[i]["action"]} for tag,i in [("B",0),("EARLY_H150",2)]]
            config["development_axis_capacity"]={"schema":"v8.fixed_dev_axis_capacity_job.v1","runtime_approval":auth["runtime_approval"],"axis_object_sha256":"ad1e44aca095b872ba673d077124841058f4ae55c9002b016f19253d22131faf","original_config":{"path":old_path,"sha256":old_sha}}
            config["frozen_artifacts"]={**refs,old_path:old_sha,source["case_path"]:case_sha}
            configs.append(write("experiments/"+group+".json",config));conditions.append({"group":group,"original_config":{"path":old_path,"sha256":old_sha},"case_path":source["case_path"],"case_sha256":case_sha,"seed":seed,"original_prefix":source["condition"]["prefix"],"fork_phase":"OUTBOUND","fork_slot":0})
        registration=write(HERE+"ACTUAL_REGISTRATION_V1.json",{"schema":"v8.exposed_dev_axis_capacity_registration.v1","branch":"EXPOSED_DEVELOPMENT_CAPABILITY_NOT_NEW_VALIDATION_NOT_TRAINING","conditions":conditions,"configs":configs,"fixed_order":["B","EARLY_H150","AXIS_L1_REPEAT","AXIS_L05","AXIS_L025","AXIS_L075","AXIS_L0"],"new_map_model_physics_calls":0,"future_serial_dispatch_requires_separate_exact_config_main_review":True})
        clock();write(HERE+"METADATA_PREPARE_END_V1.json",{"status":"METADATA_ONLY_NOT_DISPATCHED","configs":configs,"registration":registration,"files_sha256":dict(written),"source_files_sha256":auth["source_files_sha256"],"new_map_model_fit_RNG_physics_calls":0})
    except BaseException as error:
        if started:write(HERE+"METADATA_PREPARE_FAILED_V1.json",{"error_type":type(error).__name__,"error":str(error),"already_written_sha256":written,"new_map_model_physics_calls":0,"retry_authorized":False})
        raise

if __name__=="__main__":main()
