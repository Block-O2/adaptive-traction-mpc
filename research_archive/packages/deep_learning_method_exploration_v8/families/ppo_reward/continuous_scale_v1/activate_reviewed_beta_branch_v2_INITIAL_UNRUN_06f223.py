"""SOURCE_ONLY V2: independent approved source allowlist + all prior closure.

Future explicit main approval can register the original single-use two-hour
Beta window and run bounded durable init. No physics dispatch. Do not execute
this candidate before final main source review and actual-activation approval.
"""
from pathlib import Path
import argparse
import collections
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

P = Path(__file__).resolve().parents[1]
F = "families/ppo_reward/continuous_scale_v1/"
SELF = "scripts/activate_reviewed_beta_branch_v2.py"
RUN = F+"real_runs/GENUINE_BETA_V1"
ACTIVATION_OUTPUT = F+"ROOT_ACTIVATION_REAL_V1"
REQUEST = "freeze/BETA_ROOT_ACTIVATION_REQUEST_REAL_V1.json"
GLOBAL_STOP = 1793114740.0
DURABLE_MANIFEST = F+"DURABLE_TRANSACTION_SOURCE_MANIFEST_V2.json"
CORE_MANIFEST = "runtime/EXECUTION_CODE_MANIFEST.json"
CONTRACT = "freeze/BETA_MAIN_TRAINING_CONTRACT_V1.json"
WRAPPER = "source/v8_beta_onpolicy_sequence_v1.py"
KNOWN_REVIEWED = {
    DURABLE_MANIFEST:"21dcaf11ea683f8aba0f32387044a931765014e2e370075db84f1510d40de19b",
    F+"beta_root_prepare_candidate_v1.py":"7a977f0bd1fe2f29cdfdfe624b466169f08ceee9a77a413a4c2a29ae6141f9db",
    "source/v8_worker_v2.py":"c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe",
    "source/v8_case_adapter_v2.py":"f1f1d2f7e589133b92294206f3c9ab2d03fc9467637fc4a0f0aada3a12a8163b",
    WRAPPER:"1e3804cdba516ee48529618dcb89c5b8bcf188981895856b2d493124ab54f03f",
    CONTRACT:"3e5a95e65a1af44d6920b52789fd7f428ce33f3217e294befe97cb85889311b8",
}


def path(relative):
    if not isinstance(relative,str):raise ValueError("PACKAGE_RELATIVE_PATH_REQUIRED")
    result=(P/relative).resolve()
    if not result.is_relative_to(P):raise ValueError("ACTIVATION_PATH_ESCAPES_PACKAGE")
    return result


def sha(relative):
    h=hashlib.sha256()
    with path(relative).open("rb") as stream:
        for block in iter(lambda:stream.read(4*2**20),b""):h.update(block)
    return h.hexdigest()


def load(relative):return json.loads(path(relative).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def verified(ref):
    if sha(ref["path"])!=ref["sha256"]:raise ValueError("MAIN_PINNED_ARTIFACT_CHANGED:"+ref["path"])
    return load(ref["path"])


def pinned_ref(relative,sources):
    if relative not in sources or sha(relative)!=sources[relative]:raise ValueError("NO_INDEPENDENT_MAIN_APPROVED_SHA:"+relative)
    return {"path":relative,"sha256":sources[relative]}


def new(relative,value):
    destination=path(relative)
    with destination.open("x") as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write("\n");stream.flush();os.fsync(stream.fileno())
    fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def _source_allowed(relative):
    parts=set(Path(relative).parts)
    if (relative.endswith(".jsonl") or "ATTEMPTS" in relative or
            parts & {"owned","jobs","attempts","output","results","history","predictions","tmp","__pycache__"}):
        raise ValueError("DYNAMIC_ATTEMPT_OR_OUTPUT_FILE_MUST_NOT_BE_AUTH_SOURCE:"+relative)
    path(relative)


def source_authority(ref):
    """All expected SHA values originate in a separate pinned MAIN approval.

    Current file SHA is only compared with that approval; never promoted into
    an approved expectation. Transitive source tables themselves are pinned.
    """
    approval=verified(ref)
    if (approval.get("schema")!="v8.beta_activation_main_source_approval.v2" or
            approval.get("status")!="APPROVED_BY_MAIN_FOR_ONE_ACTUAL_BETA_ACTIVATION" or
            approval.get("actual_activation_authorized") is not True or
            approval.get("all_prior_hard_safety_reviewed_no_true") is not True or
            approval.get("register_once_7200s_after_all_prior_closed") is not True or
            approval.get("maximum_metadata_and_initialization_wall_s")!=120 or
            approval.get("driver")!={"path":SELF,"sha256":sha(SELF)} or
            approval.get("approved_unix",float("inf"))>time.time()):
        raise ValueError("INDEPENDENT_MAIN_V2_SOURCE_AND_ONE_ACTIVATION_APPROVAL_REQUIRED")
    sources={}
    def add(relative,expected):
        _source_allowed(relative)
        if not isinstance(expected,str) or len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("EXPLICIT_VALID_MAIN_SOURCE_SHA_REQUIRED")
        if relative in sources and sources[relative]!=expected:raise ValueError("CONFLICTING_REVIEWED_SOURCE_SHA:"+relative)
        sources[relative]=expected
    for relative,expected in approval["direct_source_files_sha256"].items():add(relative,expected)
    tables=approval["reviewed_manifest_tables"]
    expected_tables={(DURABLE_MANIFEST,"full_model_axis_control_dependency_sha256",""),(CORE_MANIFEST,"files","runtime/")}
    if len(tables)!=2 or {(item["path"],item["mapping_key"],item["path_prefix"]) for item in tables}!=expected_tables:
        raise ValueError("EXACT_REVIEWED_DURABLE_AND_RUNTIME_CORE_TABLES_REQUIRED")
    for item in tables:
        document=verified(item)
        add(item["path"],item["sha256"])
        for relative,expected in document[item["mapping_key"]].items():add(item["path_prefix"]+relative,expected)
    for relative,expected in KNOWN_REVIEWED.items():
        if sources.get(relative)!=expected:raise ValueError("MAIN_APPROVAL_MUST_PRESERVE_EXACT_REVIEWED_ANCHOR:"+relative)
    if sources.get(SELF)!=approval["driver"]["sha256"]:raise ValueError("V2_DRIVER_MUST_BE_EXPLICIT_MAIN_ALLOWLIST_MEMBER")
    required={"ACTIVATION.json","runtime/RUN_PLAN.json",CORE_MANIFEST,
        "audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json",F+"FROZEN_AXIS_GATE1_V1.json",
        "freeze/ONPOLICY_V1_CASE_ROUTES.json","experiments/V8OP02H.json",
        "families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json"}
    if not required<=set(sources):raise ValueError("MAIN_APPROVED_ALL_INITIALIZATION_INPUTS_REQUIRED")
    for relative,expected in sources.items():
        if sha(relative)!=expected:raise ValueError("ACTUAL_SOURCE_DIFFERS_FROM_INDEPENDENT_MAIN_APPROVAL:"+relative)
    # This ref is supplied independently by CLI and is itself immutable input;
    # no self-referential hash is inserted into the approval document.
    add(ref["path"],ref["sha256"])
    return approval,sources


def proc_identity(pid):
    try:
        row=Path("/proc")/str(pid)/"stat"
        values=row.read_text().rsplit(")",1)[1].split()
        return {"pid":int(pid),"start_ticks":int(values[19]),"state":values[0]}
    except FileNotFoundError:return None


def collect_identities(value,found):
    if isinstance(value,dict):
        if "pid" in value and "start_ticks" in value:
            pid=int(value["pid"]);ticks=int(value["start_ticks"])
            if pid<=0 or ticks<=0:raise ValueError("INVALID_ORIGINAL_PROCESS_IDENTITY")
            found.add((pid,ticks))
        for child in value.values():collect_identities(child,found)
    elif isinstance(value,list):
        for child in value:collect_identities(child,found)


def all_prior_closed(approval):
    """Read only closure metadata; failed/custom DONE never means still live."""
    starts=sorted((P/"owned").glob("*_SUPERVISOR.json"))
    groups={item.name[:-len("_SUPERVISOR.json")] for item in starts}
    end_groups={item.name[:-len("_SUPERVISOR_END.json")] for item in (P/"owned").glob("*_SUPERVISOR_END.json")}
    if not starts or groups!=end_groups:raise ValueError("ALL_PRIOR_SUPERVISOR_START_AND_END_PAIRS_REQUIRED")
    events={};raw_hashes={}
    for raw in path("runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
        event=json.loads(raw)
        if event.get("event") not in ("START","END"):continue
        key=(event["id"],event["event"])
        if key in events:raise ValueError("DUPLICATE_ORIGINAL_START_OR_END:"+event["id"])
        if sum(event["id"].startswith(group+"_") for group in groups)!=1:
            raise ValueError("ORIGINAL_PHYSICAL_ATTEMPT_WITHOUT_ONE_SUPERVISOR:"+event["id"])
        events[key]=event;raw_hashes[event["id"]+"|"+event["event"]]=hashlib.sha256(raw).hexdigest()
    start_ids={ident for ident,event in events if event=="START"}
    end_ids={ident for ident,event in events if event=="END"}
    if start_ids!=end_ids:raise ValueError("ALL_PRIOR_ACTUAL_STARTS_REQUIRE_ORIGINAL_ENDS")
    identities=set();closed={}
    allowed_statuses=set(approval["allowed_closed_worker_statuses"])
    for group in sorted(groups):
        base="owned/"+group
        supervisor=load(base+"_SUPERVISOR.json");end=load(base+"_SUPERVISOR_END.json")
        exit_row=load(base+"_EXIT.json");done=load("jobs/"+group+"/WORKER_DONE.json")
        if end.get("state")!="STOP" or end.get("survivors") or done.get("status") not in allowed_statuses:
            raise ValueError("PRIOR_WORKER_NOT_EXPLICITLY_CLOSED_OR_UNREVIEWED_DONE_STATUS:"+group)
        if done.get("all_children_joined") is False:raise ValueError("ORIGINAL_DONE_REPORTS_UNJOINED_CHILD:"+group)
        known=end.get("known_owned")
        if not isinstance(known,dict) or not supervisor.get("identity") or not supervisor.get("worker"):
            raise ValueError("ORIGINAL_SUPERVISOR_KNOWN_PROCESS_IDENTITIES_REQUIRED:"+group)
        if exit_row.get("pid")!=supervisor["worker"]["pid"]:
            raise ValueError("EXIT_NOT_ORIGINAL_SUPERVISED_WORKER_IDENTITY:"+group)
        for original in (supervisor,end,exit_row,done):collect_identities(original,identities)
        group_ids=sorted(ident for ident in start_ids if ident.startswith(group+"_"))
        if not group_ids:raise ValueError("SUPERVISED_PHYSICS_HAS_NO_ORIGINAL_START_END:"+group)
        for ident in group_ids:
            begin=events[(ident,"START")];finish=events[(ident,"END")]
            if finish.get("joined") is not True:raise ValueError("PRIOR_END_NOT_JOINED:"+ident)
            if any(not isinstance(event.get("pid"),int) or not isinstance(event.get("start_ticks"),int) for event in (begin,finish)):
                raise ValueError("ORIGINAL_START_END_PID_STARTTICKS_REQUIRED:"+ident)
            if begin.get("unix",float("inf"))>finish.get("unix",-float("inf")):
                raise ValueError("ORIGINAL_ATTEMPT_END_PRECEDES_START")
            if begin.get("config_sha256")!=supervisor.get("config_sha256"):
                raise ValueError("START_NOT_ORIGINAL_SUPERVISED_CONFIG:"+ident)
            collect_identities(begin,identities);collect_identities(finish,identities)
        closed[group]={"done_status":done["status"],"worker_exit_code":end.get("worker_exit_code"),
            "attempt_ids":group_ids,"failed_or_custom_DONE_preserved_not_relabelled":True,
            "closure_files_sha256":{relative:sha(relative) for relative in (
                base+"_SUPERVISOR.json",base+"_SUPERVISOR_END.json",base+"_EXIT.json","jobs/"+group+"/WORKER_DONE.json")}}
    exited=[]
    for pid,ticks in sorted(identities):
        current=proc_identity(pid)
        if current is not None and current["start_ticks"]==ticks:
            raise ValueError("ORIGINAL_KNOWN_PID_STARTTICKS_NOT_EXITED_INCLUDING_ZOMBIE:"+str(pid))
        exited.append({"pid":pid,"start_ticks":ticks,"original_identity_absent":True,"current_reused_pid_identity":current})
    return {"schema":"v8.beta_activation_all_prior_original_closure.v2","groups":closed,
        "original_unique_START_END_raw_line_sha256":raw_hashes,"original_known_process_identities_exited":exited,
        "prior_supervisor_count":len(groups),"prior_unique_joined_attempts":len(start_ids),
        "dynamic_attempts_log_not_added_to_AUTH_sources":True,"new_physics":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration-review",required=True);parser.add_argument("--integration-review-sha256",required=True)
    parser.add_argument("--main-source-approval",required=True);parser.add_argument("--main-source-approval-sha256",required=True)
    args=parser.parse_args()
    main_ref={"path":args.main_source_approval,"sha256":args.main_source_approval_sha256}
    approval,sources=source_authority(main_ref)
    binary=hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
    if binary!=approval["expected_python_binary_sha256"]:raise ValueError("EXACT_APPROVED_SCIENTIFIC_INTERPRETER_REQUIRED")
    review_ref={"path":args.integration_review,"sha256":args.integration_review_sha256}
    integration=verified(review_ref)
    if (integration.get("status")!="PASS_EXPOSED_LIVE_INTEGRATION_AND_ORIGINAL_RAW" or
            integration.get("true_hard_safety_violation") is not False or
            integration.get("all_five_core_complete") is not True or
            integration.get("all_expected_pre_B_selectors_bound_before_B") is not True):
        raise ValueError("ACTUAL_EXPOSED_INTEGRATION_ORIGINAL_RAW_REVIEW_REQUIRED")
    if approval.get("integration_review")!=review_ref:raise ValueError("INDEPENDENT_MAIN_APPROVAL_MUST_BIND_ACTUAL_INTEGRATION_REVIEW")
    with path("freeze/BETA_ROOT_ACTIVATION_ONCE.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if any(path(relative).exists() for relative in (RUN,ACTIVATION_OUTPUT,REQUEST)):
            raise ValueError("ONE_ORIGINAL_REQUEST_PLAN_RUN_ONLY_NO_ACTIVATION_RETRY_OR_CLOCK_RESET")
        if path("STOP_REQUESTED").exists():raise ValueError("ORIGINAL_GLOBAL_STOP_REQUEST_NO_NEW_ACTIVATION")
        closure=all_prior_closed(approval)
        categorical_end=load("families/ppo_reward/onpolicy_runs/GENUINE_V1/FINITE_WINDOW_END_V1.json")
        if approval.get("categorical_finite_end")!={"path":"families/ppo_reward/onpolicy_runs/GENUINE_V1/FINITE_WINDOW_END_V1.json",
                "sha256":sha("families/ppo_reward/onpolicy_runs/GENUINE_V1/FINITE_WINDOW_END_V1.json")}:
            raise ValueError("ACTUAL_ORIGINAL_CATEGORICAL_FINITE_END_MUST_BE_MAIN_BOUND")
        activation=load("ACTIVATION.json");runtime=load("runtime/RUN_PLAN.json");contract=load(CONTRACT)
        if activation["hard_stop_unix"]!=GLOBAL_STOP or activation.get("clock_must_not_reset") is not True:
            raise ValueError("UNIQUE_GLOBAL_ACTIVATION_CHANGED")
        if not all(contract.get(key) is True for key in ("real_initialization_authorized","real_sampling_authorized","real_updates_authorized")):
            raise ValueError("ORIGINAL_MAIN_BETA_INITIALIZATION_SAMPLING_UPDATE_CONTRACT_REQUIRED")
        if not time.time()+7200.<min(runtime["dispatch_cutoff_unix"]-1800.,GLOBAL_STOP):
            raise ValueError("ORIGINAL_GLOBAL_RUNTIME_RESERVE_CANNOT_FIT_UNEXTENDED_BETA_WINDOW")
        for relative,expected in sources.items():
            if sha(relative)!=expected:raise ValueError("APPROVED_SOURCE_CHANGED_AFTER_PRIOR_CLOSURE:"+relative)
        new("audit/BETA_ACTIVATION_PRIOR_CLOSURE_V2.json",closure)
        initialized=time.time();stop=initialized+7200.;held_deadline=min(initialized+120.,stop,GLOBAL_STOP)
        route_path="freeze/ONPOLICY_V1_CASE_ROUTES.json";routes=load(route_path)["development_routes"]
        parameters={"normalization_source":pinned_ref("families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json",sources),
            "normalization_keys":["policy","normalization"],"feature_names_keys":["policy","feature_names"],
            "initialization_seed":2791,"sampling_seed":2792,
            "optimizer":{"learning_rate":.15,"max_gradient_norm":1.,"ppo_clip_range":.2},
            "expected_context_counts":{key:2 for key in routes},"local_stop_unix":stop,
            "beta_initial_shapes":[2.,2.],"same_initial_weights_and_sampling_seed":True}
        request={"schema":"v8.beta_root_activation_request.v1","status":"APPROVED_BY_MAIN_AGENT",
            "approved_for_real_initialization":True,"approved_for_real_sampling":True,"approved_for_real_updates":True,
            "approved_unix":approval["approved_unix"],"activation_sha256":sources["ACTIVATION.json"],"source_files_sha256":sources,
            "sequence_wrapper":{"path":WRAPPER,"sha256":sources[WRAPPER],"algorithm":"v8_beta_onpolicy_sequence_v1"},
            "approved_contract":pinned_ref(CONTRACT,sources),
            "gate1_review":pinned_ref("audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json",sources),
            "axis":pinned_ref(F+"FROZEN_AXIS_GATE1_V1.json",sources),"case_routes":pinned_ref(route_path,sources),
            "base_job_template":pinned_ref("experiments/V8OP02H.json",sources),"run_path":RUN,
            "candidate_job_groups":[f"V8BETA{batch:02d}{suffix}" for batch in range(1,11) for suffix in ("H","L")],
            "initialized_window":{"clock_initialized_after_main_approval":True,"initialized_unix":initialized,
                "local_stop_unix":stop,"original_global_deadline_unix":GLOBAL_STOP},
            "initialization_parameters":parameters,"durable_initialization_parameters_sha256":digest(parameters),
            "exposed_integration_review":review_ref,"independent_main_source_approval":main_ref,
            "original_prior_closure_audit":{"path":"audit/BETA_ACTIVATION_PRIOR_CLOSURE_V2.json","sha256":sha("audit/BETA_ACTIVATION_PRIOR_CLOSURE_V2.json")},
            "held_metadata_and_initialization_deadline_unix":held_deadline,
            "no_automatic_physics_dispatch":True,"categorical_or_global_clock_reset":False}
        new(REQUEST,request)
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",MKL_NUM_THREADS="1")
        def bounded_command(command,audit,actor_possible):
            remaining=held_deadline-time.time()
            if remaining<=0:raise TimeoutError("ORIGINAL_HELD_120S_INITIALIZATION_STOP_NO_RETRY")
            try:
                result=subprocess.run(command,cwd=P,text=True,capture_output=True,timeout=remaining,env=env)
            except subprocess.TimeoutExpired as error:
                new(audit,{"status":"TIMEOUT_PRESERVED_NO_RETRY","stdout":str(error.stdout),"stderr":str(error.stderr),
                    "actor_calls_may_have_begun":actor_possible,"held_deadline_unix":held_deadline,"original_local_stop_unix":stop,"new_physics":0})
                raise
            new(audit,{"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr,
                "actor_calls_may_have_begun":actor_possible,"held_deadline_unix":held_deadline,"original_local_stop_unix":stop,
                "new_physics":0,"failure_requires_original_intent_review_no_reinitialization":True})
            if result.returncode!=0:raise RuntimeError("BETA_ACTIVATION_CHILD_FAILED_PRESERVE_ORIGINAL_INTENT:"+audit)
        bounded_command([sys.executable,"-B",str(path(F+"beta_root_prepare_candidate_v1.py")),"activate","--package",str(P),
            "--request",REQUEST,"--request-sha",sha(REQUEST),"--destination",ACTIVATION_OUTPUT],"audit/BETA_ACTIVATION_METADATA_CLI_V2.json",False)
        plan=ACTIVATION_OUTPUT+"/RUN_PLAN.json"
        bounded_command([sys.executable,"-B",str(path(F+"beta_durable_transaction_candidate_v2.py")),"init","--package",str(P),
            "--run",RUN,"--input",plan,"--input-sha256",sha(plan)],"audit/BETA_DURABLE_INITIALIZATION_CLI_V2.json",True)
        current=load(RUN+"/CURRENT.json")
        if current.get("generation_index")!=0 or current.get("status")!="READY_ALL_FOUR_INITIALIZED":
            raise ValueError("ACTUAL_INITIAL_ATOMIC_GENERATION_ZERO_NOT_COMPLETE")
        print(json.dumps({"status":"BETA_REAL_INITIALIZED_NO_PHYSICS","local_start":initialized,"local_stop":stop,
            "original_global_stop":GLOBAL_STOP,"plan_sha256":sha(plan),"CURRENT_sha256":sha(RUN+"/CURRENT.json")},allow_nan=False))


if __name__=="__main__":main()
