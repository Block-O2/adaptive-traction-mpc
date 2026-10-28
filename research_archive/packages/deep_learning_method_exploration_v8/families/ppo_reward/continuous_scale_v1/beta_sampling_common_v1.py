"""Source-only JSON/source/approval utilities. Never initializes an actor."""
from pathlib import Path
import hashlib
import json
import time

ARM_IDS = ["BETA_RF_RAW", "BETA_PPO_RAW", "BETA_RF_SCALED", "BETA_PPO_SCALED"]
ORIGINAL_GLOBAL_DEADLINE_UNIX = 1793114740.0


def canonical(value):
    return json.loads(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda:handle.read(4*2**20),b""):h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def bounded_path(package,relative):
    if not isinstance(relative,str):raise ValueError("BETA_PATH_NOT_STRING")
    package=Path(package).resolve();result=(package/relative).resolve()
    if not result.is_relative_to(package):raise ValueError("BETA_PATH_ESCAPES_PACKAGE")
    return result


def load_verified(package,relative,expected_sha):
    path=bounded_path(package,relative)
    if sha(path)!=expected_sha:raise ValueError("BETA_FROZEN_DOCUMENT_CHANGED:"+relative)
    return load(path)


def verify_launch(package,spec,*,group=None,require_live_window=True):
    """Require root-created approval, Gate1 review and initialized future window.

    This function defines a future schema. No actual approval/window/checkpoint
    is created by this source candidate.
    """
    if spec.get("schema")!="v8.continuous_beta_sampling_job.v1":raise ValueError("EXPLICIT_BETA_JOB_SCHEMA")
    auth=load_verified(package,spec["launch_authorization_path"],spec["launch_authorization_sha256"])
    if auth.get("schema")!="v8.beta_real_sampling_authorization.v1" or auth.get("approved_for_real_sampling") is not True:
        raise ValueError("MAIN_REAL_BETA_SAMPLING_APPROVAL_REQUIRED")
    if sha(bounded_path(package,"ACTIVATION.json"))!=auth["activation_sha256"]:
        raise ValueError("ORIGINAL_UNIQUE_ACTIVATION_CHANGED")
    if group is not None and group not in auth["authorized_job_groups"]:raise ValueError("UNAUTHORIZED_BETA_JOB_GROUP")
    required_sources={"families/ppo_reward/continuous_scale_v1/beta_sampling_common_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_sampling_sequence_candidate_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_onpolicy_receipt_adapter_candidate_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_group_transaction_candidate_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_optimizer_candidate_v2.py",
        "families/ppo_reward/continuous_scale_v1/beta_policy.py",
        "families/ppo_reward/continuous_scale_v1/axis_mapping.py",
        "source/v8_onpolicy_receipt_adapter_v2.py","source/v8_worker_v1.py",
        "runtime/code/stream_runtime_evidence.py","families/critic_value/source/value_api.py"}
    if not required_sources<=set(auth.get("source_files_sha256",{})):
        raise ValueError("COMPLETE_REAL_BETA_SOURCE_CLOSURE_REQUIRED")
    for relative,expected in auth["source_files_sha256"].items():
        if sha(bounded_path(package,relative))!=expected:raise ValueError("REAL_BETA_APPROVED_SOURCE_CHANGED:"+relative)
    for key in ("approved_contract_path","approved_contract_sha256","gate1_review_path","gate1_review_sha256",
                "axis_path","axis_file_sha256","axis_object_sha256","case_route_manifest","case_route_manifest_sha256",
                "receipt_adapter_path","receipt_adapter_sha256"):
        if auth[key]!=spec[key]:raise ValueError("BETA_AUTHORIZATION_SPEC_BINDING:"+key)
    if sha(bounded_path(package,spec["approved_contract_path"]))!=spec["approved_contract_sha256"]:
        raise ValueError("BETA_TRAINING_CONTRACT_CHANGED")
    gate=load_verified(package,spec["gate1_review_path"],spec["gate1_review_sha256"])
    if gate.get("schema")!="v8.beta_axis_gate1_main_review.v1" or gate.get("status")!="PASS_ENGINEERING_MAPPING_REVIEWED_FOR_REAL_SAMPLING" or gate.get("axis_object_sha256")!=spec["axis_object_sha256"] or gate.get("lambda1_original_H150_exact_raw_PASS") is not True or gate.get("true_hard_safety_violation") is not False:
        raise ValueError("ACTUAL_MAIN_GATE1_REVIEW_REQUIRED")
    if gate.get("original_B_full_qualified") is not True or gate.get("original_H150_full_qualified") is not True or gate.get("lambda0_and_lambda05_engineering_review_completed") is not True:
        raise ValueError("GATE1_ORIGINAL_CONTROLS_AND_ZERO_MIDPOINT_REVIEW_REQUIRED")
    if gate.get("mean_lambda05_full_original_qualified") is not True:
        raise ValueError("INITIAL_BETA_MEAN_POINT5_FULL_ORIGINAL_ABILITY_GATE_REQUIRED")
    if not gate.get("original_evidence_files_sha256"):raise ValueError("GATE1_REAL_EVIDENCE_FILES_REQUIRED")
    for relative,expected in gate["original_evidence_files_sha256"].items():
        if sha(bounded_path(package,relative))!=expected:raise ValueError("GATE1_ORIGINAL_EVIDENCE_CHANGED")
    routes=load_verified(package,spec["case_route_manifest"],spec["case_route_manifest_sha256"])
    if spec["case_route_manifest"]!="freeze/ONPOLICY_V1_CASE_ROUTES.json" or len(routes["development_routes"])!=2:
        raise ValueError("SAME_ORIGINAL_TWO_DEVELOPMENT_CASE_ROUTES_REQUIRED")
    window=auth["initialized_window"]
    if window.get("clock_initialized_after_main_approval") is not True or window["original_global_deadline_unix"]!=ORIGINAL_GLOBAL_DEADLINE_UNIX:
        raise ValueError("BETA_FUTURE_WINDOW_NOT_INITIALIZED_OR_GLOBAL_CLOCK_RESET")
    if not gate["reviewed_unix"]<=auth["approved_unix"]<=window["initialized_unix"]<window["local_stop_unix"]<=ORIGINAL_GLOBAL_DEADLINE_UNIX:
        raise ValueError("GATE1_APPROVAL_WINDOW_ORDER")
    if time.time()<window["initialized_unix"] or (require_live_window and time.time()>=window["local_stop_unix"]):
        raise ValueError("BETA_LOCAL_OR_GLOBAL_CLOCK_REJECTION")
    if window["local_stop_unix"]-window["initialized_unix"]>auth["registered_max_local_window_s"]:
        raise ValueError("UNAPPROVED_LOCAL_WINDOW_EXTENSION")
    if auth["arm_ids"]!=ARM_IDS:raise ValueError("FOUR_BETA_ARM_ORDER")
    return auth,gate,routes
