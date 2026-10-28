"""SOURCE_ONLY future root metadata helper. No actor/adapter imports or dispatch.

activate materializes an ALREADY root-approved, fixed-time authorization+plan;
job materializes one already batch-approved experiment; bind joins already
closed artifacts and explicit root hard reviews. None calls DurableRun or a
learner. This candidate must be reviewed before any operation is executed.
"""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import time

FAMILY = "families/ppo_reward/continuous_scale_v1/"
ARMS = ["BETA_RF_RAW", "BETA_PPO_RAW", "BETA_RF_SCALED", "BETA_PPO_SCALED"]
GLOBAL_STOP = 1793114740.0
GATE = "audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json"
ROUTES = "freeze/ONPOLICY_V1_CASE_ROUTES.json"
NORM = "families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_0000/RF_RAW.json"
AXIS = FAMILY + "FROZEN_AXIS_GATE1_V1.json"
INIT_KEYS = ["normalization_source", "normalization_keys", "feature_names_keys",
    "initialization_seed", "sampling_seed", "optimizer", "expected_context_counts",
    "local_stop_unix", "beta_initial_shapes", "same_initial_weights_and_sampling_seed"]
REQUIRED = {FAMILY + name for name in (
    "beta_root_prepare_candidate_v1.py", "beta_durable_transaction_candidate_v2.py",
    "beta_transaction_backend_candidate_v2.py", "beta_transaction_evidence_candidate_v2.py",
    "beta_sampling_common_v1.py", "beta_sampling_sequence_candidate_v1.py",
    "beta_onpolicy_receipt_adapter_candidate_v1.py", "beta_group_transaction_candidate_v1.py",
    "beta_optimizer_candidate_v2.py", "beta_policy.py", "axis_mapping.py")}
REQUIRED |= {"source/v8_worker_v1.py", "source/v8_worker_v2.py", "source/acl2_shared.py",
    "source/v8_case_adapter_v2.py", "source/v8_onpolicy_receipt_adapter_v2.py",
    "runtime/code/stream_runtime_evidence.py", "families/critic_value/source/value_api.py"}


def canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 2**20), b""):
            h.update(block)
    return h.hexdigest()


class MetadataOwner:
    def __init__(self, package):
        self.package = Path(package).resolve()
        self.pid = os.getpid()

    def owner(self):
        if os.getpid() != self.pid:
            raise RuntimeError("CHILD_CANNOT_WRITE_ROOT_METADATA")

    def path(self, relative):
        if not isinstance(relative, str):
            raise ValueError("RELATIVE_PATH_STRING_REQUIRED")
        path = (self.package / relative).resolve()
        if not path.is_relative_to(self.package):
            raise ValueError("PATH_ESCAPES_PACKAGE")
        return path

    def load(self, relative):
        return json.loads(self.path(relative).read_text())

    def ref(self, relative):
        return {"path": relative, "sha256": sha(self.path(relative))}

    def verified(self, ref):
        if sha(self.path(ref["path"])) != ref["sha256"]:
            raise ValueError("ORIGINAL_DOCUMENT_CHANGED:" + ref["path"])
        return self.load(ref["path"])

    def syncdir(self, directory):
        self.owner()
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def directory_new(self, path):
        self.owner()
        if not path.parent.is_dir():
            raise ValueError("PARENT_MUST_ALREADY_EXIST_AND_BE_SYNCED")
        path.mkdir()
        self.syncdir(path.parent)

    def write_new(self, relative, value):
        self.owner()
        path = self.path(relative)
        if not path.parent.is_dir():
            raise ValueError("EXPLICIT_EXISTING_OUTPUT_PARENT_REQUIRED")
        data = (json.dumps(canonical(value), indent=2, allow_nan=False) + "\n").encode()
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.syncdir(path.parent)
        return self.ref(relative)

    def freeze(self, files):
        for relative, expected in files.items():
            if sha(self.path(relative)) != expected:
                raise ValueError("APPROVED_SOURCE_OR_DATA_CHANGED:" + relative)

    def original_activation(self, expected):
        if sha(self.path("ACTIVATION.json")) != expected:
            raise ValueError("UNIQUE_ACTIVATION_CHANGED")
        activation = self.load("ACTIVATION.json")
        parsed = datetime.datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
        if (parsed != GLOBAL_STOP or activation["hard_stop_unix"] != GLOBAL_STOP or
                activation.get("clock_must_not_reset") is not True):
            raise ValueError("GLOBAL_ACTIVATION_OR_ORIGINAL_DEADLINE_CHANGED")
        return activation

    def events(self, groups):
        found = {}
        for raw in self.path("runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
            row = json.loads(raw)
            if row.get("event") not in ("START", "END") or not any(
                    row.get("id", "").startswith(group + "_") for group in groups):
                continue
            key = (row["id"], row["event"])
            if key in found:
                raise ValueError("DUPLICATE_ORIGINAL_START_END")
            found[key] = {"record": row, "raw_line_without_newline_sha256": hashlib.sha256(raw).hexdigest()}
        return found

    def closed(self, group, *, complete):
        supervisor = self.load("owned/" + group + "_SUPERVISOR_END.json")
        done = self.load("jobs/" + group + "/WORKER_DONE.json")
        exit_ref = self.ref("owned/" + group + "_EXIT.json")
        if supervisor.get("state") != "STOP" or supervisor.get("survivors"):
            raise ValueError("ACTIVE_OR_SURVIVING_PHYSICAL_OWNER_NOT_READABLE")
        if complete and (supervisor.get("worker_exit_code") != 0 or
                done.get("status") != "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS" or
                self.load("audit/" + group + "_PARENT_RAW_GATE.json").get("status") != "PASS"):
            raise ValueError("COMPLETE_CLOSED_WORKER_AND_PARENT_RAW_REQUIRED")
        return [self.ref("owned/" + group + "_SUPERVISOR_END.json"),
            self.ref("jobs/" + group + "/WORKER_DONE.json"), exit_ref]

    def activate(self, request_ref, destination):
        """Future metadata operation; never initializes Beta or invokes backend."""
        request = self.verified(request_ref)
        if (request.get("schema") != "v8.beta_root_activation_request.v1" or
                request.get("status") != "APPROVED_BY_MAIN_AGENT" or
                any(request.get(key) is not True for key in (
                    "approved_for_real_initialization", "approved_for_real_sampling", "approved_for_real_updates"))):
            raise ValueError("EXPLICIT_SEPARATE_MAIN_INITIALIZATION_SAMPLING_UPDATE_APPROVALS_REQUIRED")
        self.original_activation(request["activation_sha256"])
        self.freeze(request["source_files_sha256"])
        wrapper = request["sequence_wrapper"]
        if (not wrapper["path"].startswith("source/") or
                Path(wrapper["path"]).stem != wrapper["algorithm"] or
                request["source_files_sha256"].get(wrapper["path"]) != wrapper["sha256"] or
                not REQUIRED <= set(request["source_files_sha256"])):
            raise ValueError("ROOT_THIN_BETA_WRAPPER_AND_ALL_V2_DEPENDENCIES_MUST_BE_APPROVED")
        gate = self.verified(request["gate1_review"])
        axis = self.verified(request["axis"])
        routes = self.verified(request["case_routes"])["development_routes"]
        self.verified(request["approved_contract"])
        if (request["gate1_review"]["path"] != GATE or request["axis"]["path"] != AXIS or
                request["case_routes"]["path"] != ROUTES or
                gate.get("schema") != "v8.beta_axis_gate1_main_review.v1" or
                gate.get("status") != "PASS_ENGINEERING_MAPPING_REVIEWED_FOR_REAL_SAMPLING" or
                gate.get("true_hard_safety_violation") is not False or
                gate.get("axis_object_sha256") != digest(axis) or
                any(gate.get(key) is not True for key in (
                    "lambda1_original_H150_exact_raw_PASS", "original_B_full_qualified",
                    "original_H150_full_qualified", "lambda0_and_lambda05_engineering_review_completed",
                    "mean_lambda05_full_original_qualified"))):
            raise ValueError("ACTUAL_CLOSED_GATE1_MAPPING_AND_MEAN_ABILITY_REVIEW_REQUIRED")
        self.freeze(gate["original_evidence_files_sha256"])
        window = request["initialized_window"]
        if (window.get("clock_initialized_after_main_approval") is not True or
                window.get("original_global_deadline_unix") != GLOBAL_STOP or
                window["local_stop_unix"] - window["initialized_unix"] != 7200.0 or
                not gate["reviewed_unix"] <= request["approved_unix"] <= window["initialized_unix"] <= time.time() <
                    min(window["initialized_unix"] + 60.0, window["local_stop_unix"]) or
                window["local_stop_unix"] > GLOBAL_STOP):
            raise ValueError("PREAPPROVED_ONCE_ONLY_TWO_HOUR_BETA_WINDOW_REQUIRED")
        parameters = request["initialization_parameters"]
        if set(parameters) != set(INIT_KEYS) or digest(parameters) != request["durable_initialization_parameters_sha256"]:
            raise ValueError("ROOT_MUST_BIND_EXACT_TEN_INITIALIZATION_KEYS")
        normalization = self.verified(parameters["normalization_source"])
        if (parameters["normalization_source"]["path"] != NORM or
                parameters["normalization_keys"] != ["policy", "normalization"] or
                parameters["feature_names_keys"] != ["policy", "feature_names"] or
                len(normalization["policy"]["feature_names"]) != 25 or
                parameters["optimizer"] != {"learning_rate": .15, "max_gradient_norm": 1.0, "ppo_clip_range": .2} or
                parameters["beta_initial_shapes"] != [2.0, 2.0] or
                parameters["same_initial_weights_and_sampling_seed"] is not True or
                parameters["local_stop_unix"] != window["local_stop_unix"] or
                parameters["expected_context_counts"] != {key: 2 for key in routes} or len(routes) != 2):
            raise ValueError("FROZEN_G0_NORMALIZATION_BETA22_OPTIMIZER_AND_TWO_DEV_ROUTE_IDENTITY")
        for seed_key in ("initialization_seed", "sampling_seed"):
            if not isinstance(parameters[seed_key], int) or isinstance(parameters[seed_key], bool):
                raise ValueError("EXPLICIT_INTEGER_SEED_REQUIRED")
        run = self.path(request["run_path"])
        real_parent = self.path(FAMILY + "real_runs")
        if run.parent != real_parent or run.exists():
            raise ValueError("FRESH_BETA_REAL_RUN_ONLY")
        output = self.path(destination)
        if not output.is_relative_to(self.path(FAMILY)) or output.is_relative_to(run) or output == run:
            raise ValueError("ACTIVATION_PLAN_MUST_BE_OUTSIDE_ACTUAL_RUN")
        if real_parent.exists():
            self.syncdir(real_parent)
            self.syncdir(real_parent.parent)
        else:
            self.directory_new(real_parent)
            self.syncdir(real_parent)
        self.directory_new(output)
        authorization_path = str((output / "LAUNCH_AUTHORIZATION.json").relative_to(self.package))
        spec = {"schema": "v8.continuous_beta_sampling_job.v1",
            "launch_authorization_path": authorization_path,
            "approved_contract_path": request["approved_contract"]["path"],
            "approved_contract_sha256": request["approved_contract"]["sha256"],
            "gate1_review_path": GATE, "gate1_review_sha256": request["gate1_review"]["sha256"],
            "axis_path": AXIS, "axis_file_sha256": request["axis"]["sha256"], "axis_object_sha256": digest(axis),
            "case_route_manifest": ROUTES, "case_route_manifest_sha256": request["case_routes"]["sha256"],
            "receipt_adapter_path": FAMILY + "beta_onpolicy_receipt_adapter_candidate_v1.py",
            "receipt_adapter_sha256": request["source_files_sha256"][FAMILY + "beta_onpolicy_receipt_adapter_candidate_v1.py"]}
        authorization = {key: copy.deepcopy(request[key]) for key in (
            "approved_unix", "approved_for_real_initialization", "approved_for_real_sampling", "approved_for_real_updates",
            "activation_sha256", "source_files_sha256", "initialized_window", "durable_initialization_parameters_sha256")}
        authorization.update(schema="v8.beta_real_sampling_authorization.v1", arm_ids=ARMS,
            registered_max_local_window_s=7200.0, authorized_job_groups=request["candidate_job_groups"],
            root_activation_request=request_ref, **{k: v for k, v in spec.items() if k not in ("schema", "launch_authorization_path")})
        auth_ref = self.write_new(authorization_path, authorization)
        spec["launch_authorization_sha256"] = auth_ref["sha256"]
        plan = {"schema": "v8.beta_durable_run_plan.v1", "launch_spec": spec, **parameters,
            "run_path": request["run_path"], "root_activation_request": request_ref,
            "sequence_wrapper": wrapper, "base_job_template": request["base_job_template"],
            "minimum_job_start_reserve_s": 1800.0, "minimum_new_balanced_batch_start_reserve_s": 3400.0,
            "job_wall_cap_s": 1800.0, "never_dispatch_automatically": True}
        return self.write_new(str((output / "RUN_PLAN.json").relative_to(self.package)), plan)

    def plan_for_run(self, run):
        identity = self.load(run + "/RUN_IDENTITY.json")
        self.freeze({ref["path"]: ref["sha256"] for ref in identity["frozen_input_files"]})
        plan = self.verified(identity["plan"])
        if plan["run_path"] != run:
            raise ValueError("PLAN_RUN_IDENTITY_MISMATCH")
        spec = plan["launch_spec"]
        auth = self.verified({"path": spec["launch_authorization_path"], "sha256": spec["launch_authorization_sha256"]})
        self.original_activation(auth["activation_sha256"])
        self.freeze(auth["source_files_sha256"])
        return plan, auth

    def job(self, run, batch_authorization_ref, context, group, *, first_pending_ref=None):
        plan, auth = self.plan_for_run(run)
        approval = self.verified(batch_authorization_ref)
        current_ref = self.ref(run + "/CURRENT.json")
        current = self.verified(current_ref)
        routes = self.load(ROUTES)["development_routes"]
        if (approval.get("schema") != "v8.beta_batch_dispatch_authorization.v1" or
                approval.get("status") != "APPROVED_BY_MAIN_AGENT_FOR_ONE_BALANCED_BATCH" or
                approval.get("run_identity_sha256") != sha(self.path(run + "/RUN_IDENTITY.json")) or
                approval.get("current_pointer") != current_ref or
                approval.get("local_stop_unix") != plan["local_stop_unix"] or
                approval.get("global_stop_unix") != GLOBAL_STOP or
                len(approval.get("ordered_jobs", [])) != 2 or
                {job["development_context_id"] for job in approval["ordered_jobs"]} != set(routes)):
            raise ValueError("EXPLICIT_CURRENT_GENERATION_AND_SINGLE_BATCH_MAIN_APPROVAL_REQUIRED")
        entry = {"group": group, "development_context_id": context}
        if (entry not in approval["ordered_jobs"] or group not in auth["authorized_job_groups"] or
                not re.fullmatch(r"[A-Za-z0-9_]{1,100}", group) or
                self.path("experiments/" + group + ".json").exists() or self.path("jobs/" + group).exists()):
            raise ValueError("FRESH_BATCH_AUTHORIZED_BETA_GROUP_REQUIRED")
        position = approval["ordered_jobs"].index(entry)
        if (position == 0) != (first_pending_ref is None):
            raise ValueError("FIRST_CURRENT_THEN_SECOND_CLOSED_PENDING_ORDER")
        reserve = 3400.0 if position == 0 else 1800.0
        if not approval["approved_unix"] <= time.time() < min(plan["local_stop_unix"], GLOBAL_STOP) - reserve:
            raise ValueError("UNCHANGED_BETA_LOCAL_WINDOW_START_RESERVE_REJECTION")
        route = routes[context]
        config = self.verified(plan["base_job_template"])
        allowed = ("B", "H150", "arms", "matched_reference_group", "condition", "short_horizons_s", "continuation_policy")
        config = {key: copy.deepcopy(config[key]) for key in allowed if key in config}
        case_path = "runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/" + route["case_key"] + ".json"
        if sha(self.path(case_path)) != route["case_sha256"]:
            raise ValueError("ORIGINAL_INSTALLED_DEV_CASE_PAYLOAD_CHANGED")
        config.update(group=group, mode="development", worker="v8_worker_v2.py", algorithm=plan["sequence_wrapper"]["algorithm"],
            actions=[], historical_repeats={}, case_key=route["case_key"], case_sha256=route["case_sha256"],
            case_path=case_path, fork_phase="OUTBOUND", fork_slot=0, local_stop_unix=plan["local_stop_unix"], job_wall_cap_s=1800)
        config["condition"].update(name=group, seed=route["seed"], scope="Original two development routes; cold actual OUT0 commissioning25; continuous Beta sampling only.")
        dependencies = dict(auth["source_files_sha256"])
        axis = self.load(AXIS)
        dependencies.update(axis["source_files_sha256"])
        for key in ("approved_contract", "gate1_review", "axis", "case_routes"):
            original = self.verified(plan["root_activation_request"])[key]
            dependencies[original["path"]] = original["sha256"]
        dependencies[case_path] = route["case_sha256"]
        dependencies[batch_authorization_ref["path"]] = batch_authorization_ref["sha256"]
        dependencies[plan["launch_spec"]["launch_authorization_path"]] = plan["launch_spec"]["launch_authorization_sha256"]
        inputs = []
        if position == 0:
            if set(current["checkpoints"]) != set(ARMS):
                raise ValueError("CURRENT_MUST_CONTAIN_FOUR_BETA_ARMS")
            source_refs = current["checkpoints"]
        else:
            first_group = approval["ordered_jobs"][0]["group"]
            self.closed(first_group, complete=True)
            first_config = self.load("experiments/" + first_group + ".json")
            expected_path = first_config["onpolicy_sampling"]["output_directory"] + "/PENDING_CHECKPOINTS.json"
            first = self.verified(first_pending_ref)
            if (first_pending_ref["path"] != expected_path or first.get("group_evaluation_only") != first_group or
                    first.get("stage") != "ALL_EIGHT_FRESH_CHILD_RECEIPTS_COLLECTED_NO_UPDATE" or
                    first.get("parameter_updates_in_this_job") != 0 or
                    first_config.get("beta_batch_authorization") != batch_authorization_ref):
                raise ValueError("SECOND_JOB_REQUIRES_EXACT_CLOSED_FIRST_PENDING_AND_SAME_BATCH_APPROVAL")
            source_refs = {arm: self.ref(first_config["onpolicy_sampling"]["output_directory"] + "/" + arm + "_PENDING.json") for arm in ARMS}
            if any(digest(self.verified(source_refs[arm])) != digest(first["snapshots"][arm]) for arm in ARMS):
                raise ValueError("DIRECT_FIRST_PENDING_CHANGED_FROM_BUNDLE")
            dependencies[first_pending_ref["path"]] = first_pending_ref["sha256"]
        for arm in ARMS:
            ref = source_refs[arm]
            state = self.verified(ref)
            if (state.get("schema") != "v8.continuous_beta_arm_checkpoint.v2" or
                    state.get("execution_mode") != "GENUINE_ON_POLICY" or state["policy"]["arm_id"] != arm or
                    state["local_stop_unix"] != plan["local_stop_unix"] or
                    (position == 0 and state.get("pending"))):
                raise ValueError("EXACT_GENUINE_BETA_CHECKPOINT_WITH_ORIGINAL_CLOCK_REQUIRED")
            inputs.append({"arm_id": arm, "snapshot_path": ref["path"], "snapshot_sha256": ref["sha256"]})
            dependencies[ref["path"]] = ref["sha256"]
        config["onpolicy_sampling"] = {**plan["launch_spec"], "development_context_id": context, "arm_inputs": inputs,
            "output_directory": run + "/sampling/" + group}
        config["beta_batch_authorization"] = batch_authorization_ref
        config["frozen_artifacts"] = dependencies
        self.freeze(dependencies)
        return self.write_new("experiments/" + group + ".json", config)

    def bind(self, run, groups, review_ref, destination, *, cancelling=False):
        """No adapters/actors. Root review binds originals; prepare revalidates."""
        plan, auth = self.plan_for_run(run)
        review = self.verified(review_ref)
        early_resolutions = list(review.get("cancel_started_attempt_safety", {}).values()) + list(review.get("started_attempt_safety", {}).values()) + list(review.get("resolved_unknown_hard_attempts", {}).values())
        if review.get("true_hard_safety_violation") is True or any(
                isinstance(row, dict) and row.get("true_hard_safety_violation") is True for row in early_resolutions):
            raise ValueError("GLOBAL_HARD_SAFETY_STOP_BEFORE_CENSOR_CLOCK_OR_BIND")
        if len(groups) not in ((1, 2) if cancelling else (2,)) or len(set(groups)) != len(groups):
            raise ValueError("ONE_OR_TWO_CLOSED_CANCEL_JOBS_OR_TWO_COMMIT_JOBS")
        configs = [self.load("experiments/" + group + ".json") for group in groups]
        for config in configs:
            self.closed(config["group"], complete=not cancelling)
        # No pending data is read until every actual physical owner is closed.
        bundles = [self.load(config["onpolicy_sampling"]["output_directory"] + "/PENDING_CHECKPOINTS.json") for config in configs]
        snapshots = bundles[-1]["snapshots"]
        resolutions = list(review.get("cancel_started_attempt_safety", {}).values()) + list(review.get("started_attempt_safety", {}).values()) + list(review.get("resolved_unknown_hard_attempts", {}).values())
        receipts = [p.get("physical_receipt") for state in snapshots.values() for p in state.get("pending", [])]
        if review.get("true_hard_safety_violation") is True or any(
                isinstance(row, dict) and row.get("true_hard_safety_violation") is True for row in resolutions + receipts):
            raise ValueError("GLOBAL_HARD_SAFETY_STOP_BEFORE_CENSOR_CLOCK_OR_BIND")
        status = "ENGINEERING_CENSOR_CANCEL_ALL_ARMS" if cancelling else "READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS"
        if (review.get("schema") != "v8.beta_four_arm_root_closure_review.v1" or review.get("status") != status or
                review.get("true_hard_safety_violation") is not False or
                any(review.get(key) is not True for key in ("all_started_children_joined", "all_parent_prefixes_unchanged", "all_started_attempts_hard_safety_reviewed")) or
                review.get("pending_snapshot_object_sha256") != {arm: digest(snapshots[arm]) for arm in ARMS}):
            raise ValueError("EXACT_PENDING_AND_ORIGINAL_MAIN_SAFE_CLOSURE_REVIEW_REQUIRED")
        self.freeze(review["original_evidence_files_sha256"])
        events = self.events(groups)
        starts = {ident for ident, event in events if event == "START"}
        ends = {ident for ident, event in events if event == "END"}
        safety = review.get("cancel_started_attempt_safety" if cancelling else "started_attempt_safety", {})
        if starts != ends or set(safety) != starts:
            raise ValueError("EXACT_ACTUAL_STARTED_SET_REQUIRES_PER_ATTEMPT_ORIGINAL_HARD_REVIEW")
        for ident in starts:
            entry = safety[ident]
            if entry.get("true_hard_safety_violation") is not False or not entry.get("original_evidence_files_sha256"):
                raise ValueError("NO_GUESSED_OR_UNKNOWN_ATTEMPT_HARD_STATUS")
            self.freeze(entry["original_evidence_files_sha256"])
            end = events[(ident, "END")]["record"]
            if end.get("joined") is not True or end.get("parent_hash_equal") is False:
                raise ValueError("ORIGINAL_JOIN_OR_PARENT_PREFIX_VIOLATION")
        for config, bundle in zip(configs, bundles):
            if (config["group"] not in auth["authorized_job_groups"] or
                    config["onpolicy_sampling"].get("schema") != "v8.continuous_beta_sampling_job.v1" or
                    bundle.get("group_evaluation_only") != config["group"] or
                    bundle.get("parameter_updates_in_this_job") != 0 or
                    (not cancelling and bundle.get("stage") != "ALL_EIGHT_FRESH_CHILD_RECEIPTS_COLLECTED_NO_UPDATE")):
                raise ValueError("EXACT_BETA_CLOSED_JOB_AND_PENDING_IDENTITY_REQUIRED")
            self.freeze(config["frozen_artifacts"])
            for arm in ARMS:
                direct = self.load(config["onpolicy_sampling"]["output_directory"] + "/" + arm + "_PENDING.json")
                if digest(direct) != digest(bundle["snapshots"][arm]):
                    raise ValueError("PENDING_DIRECT_BUNDLE_MISMATCH")
        result = {"schema": "v8.beta_root_bound_pending_input.v1",
            "job_configs": [self.ref("experiments/" + group + ".json") for group in groups],
            "root_expected_sampling_groups": groups,
            "final_pending_bundle": self.ref(configs[-1]["onpolicy_sampling"]["output_directory"] + "/PENDING_CHECKPOINTS.json"),
            "root_closure_review": review_ref, "created_unix": time.time(),
            "metadata_binding_only_actor_adapter_calls": 0,
            "full_receipt_RNG_and_parent_chain_rechecked_by_durable_prepare_before_any_update": True}
        return self.write_new(destination, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["activate", "job", "bind"])
    parser.add_argument("--package", required=True)
    parser.add_argument("--request"); parser.add_argument("--request-sha")
    parser.add_argument("--destination"); parser.add_argument("--run")
    parser.add_argument("--batch-authorization"); parser.add_argument("--batch-authorization-sha")
    parser.add_argument("--group"); parser.add_argument("--context")
    parser.add_argument("--first-pending"); parser.add_argument("--first-pending-sha")
    parser.add_argument("--groups", nargs="+"); parser.add_argument("--review"); parser.add_argument("--review-sha")
    parser.add_argument("--cancel", action="store_true")
    args = parser.parse_args()
    owner = MetadataOwner(args.package)
    if args.operation == "activate":
        result = owner.activate({"path": args.request, "sha256": args.request_sha}, args.destination)
    elif args.operation == "job":
        first = {"path": args.first_pending, "sha256": args.first_pending_sha} if args.first_pending else None
        result = owner.job(args.run, {"path": args.batch_authorization, "sha256": args.batch_authorization_sha},
            args.context, args.group, first_pending_ref=first)
    else:
        result = owner.bind(args.run, args.groups, {"path": args.review, "sha256": args.review_sha}, args.destination, cancelling=args.cancel)
    print(json.dumps({"metadata_output": result, "actor_adapter_calls": 0, "new_physics": 0}, allow_nan=False))


if __name__ == "__main__":
    main()
