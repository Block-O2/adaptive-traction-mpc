"""Approved <=60s STUB_ONLY failed-worker closure and init-fsync fixture.

All fake packages are under this fixture's output. No real raw/result, Beta
actor, adapter, learner, rollout or physics module is imported or executed.
"""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json
import os
import resource
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
GLOBAL_STOP = 1793114740.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False); stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-stub-partial-cancel-60s", action="store_true", required=True)
    parser.parse_args()
    binding_path = HERE / "PARTIAL_CANCEL_STUB_SOURCE_BINDING_V2.json"
    binding = json.loads(binding_path.read_text())
    for name, expected in binding["files_sha256"].items():
        path = HERE / name
        assert sha(path) == expected, name
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    output = HERE / "partial_cancel_stub_fixture_v2"
    assert not output.exists(), "KEEP_FAILURE_NO_RETRY_OR_OVERWRITE"
    assert time.time() < GLOBAL_STOP
    output.mkdir()
    allowed_cpus = sorted(os.sched_getaffinity(0)); os.sched_setaffinity(0, {allowed_cpus[0]})
    start = time.time(); cpu = time.process_time(); deadline = min(start + 60, GLOBAL_STOP)
    ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    def rss():
        return int(next(row for row in Path("/proc/self/status").read_text().splitlines() if row.startswith("VmRSS:")).split()[1])
    rss_start = rss(); maxrss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    put(output / "START.json", {"status": "STARTED_STUB_ONLY_PARTIAL_CANCELLATION_FIXTURE", "pid": os.getpid(),
        "start_ticks": ticks, "start_unix": start, "cpu_start_s": cpu, "rss_start_kib": rss_start,
        "ru_maxrss_start_kib": maxrss_start, "local_deadline_unix": deadline,
        "original_global_deadline_unix": GLOBAL_STOP, "binding_sha256": sha(binding_path),
        "binary": str(Path(sys.executable).resolve()), "binary_sha256": sha(Path(sys.executable).resolve()),
        "cpu_affinity_single_cpu": sorted(os.sched_getaffinity(0)),
        "actual_Beta_adapter_raw_physics_calls": 0})
    def timeout(signum, frame):
        raise TimeoutError("STUB_PARTIAL_CANCEL_60S_LIMIT")
    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.time()))
    sys.path.insert(0, str(HERE))
    import beta_durable_transaction_candidate_v2 as core
    import beta_transaction_evidence_candidate_v2 as evidence
    counts = {"actual_evidence_verify_entry_calls": 0, "stub_adapter_calls": 0,
              "stub_initialize_calls": 0, "stub_checkpoint_dicts_constructed": 0,
              "actual_durable_initialize_api_calls": 0, "real_Beta_initialize_restore_forward_gradient_or_update": 0,
              "real_adapter_or_raw_or_physics": 0}
    source_API_entries = {name: 0 for name in ("hard_gate", "_cancel_attempt_closure", "_rng_chain")}
    for function_name in source_API_entries:
        original = getattr(evidence, function_name)
        def counted(*args, _name=function_name, _function=original, **kwargs):
            source_API_entries[_name] += 1
            return _function(*args, **kwargs)
        setattr(evidence, function_name, counted)
    cases = []

    def fail_adapter(*args):
        counts["stub_adapter_calls"] += 1
        raise AssertionError("NO_B_OR_POLICY_ADAPTER_ALLOWED_WITHOUT_PROPOSALS")

    def build_case(name, *, before_B=False, numeric=False, prefix_hash=True, prefix_proof=False,
                   pending_hard=False, reviewed_hard=False, unknown_safety=False, open_child=False):
        package = output / name / "STUB_ONLY_PACKAGE"
        package.mkdir(parents=True)
        group = "STUB_ONLY_" + name.upper()
        current = {"generation_index": 0, "checkpoints": {}}
        old, final = {}, {}
        for arm in core.ARMS:
            state = {"schema": "STUB_ONLY_CHECKPOINT_NOT_A_BETA_MODEL", "execution_mode": "STUB_ONLY",
                "policy": {"weights": [[0]], "counters": {"forward": 0, "backward_equivalent": 0, "parameter_updates": 0}},
                "rng": ["STUB_INITIAL"], "pending": [], "seen_attempt_ids": [], "numerical_no_proposal": [],
                "finished_batches": [], "failed_private_updates": [], "batch_id": 0,
                "expected_context_counts": {"STUB_CONTEXT_A": 2, "STUB_CONTEXT_B": 2}, "optimizer": {}}
            old[arm] = state; final[arm] = copy.deepcopy(state)
            path = package / "CURRENT_STUB" / (arm + ".json"); put(path, state)
            current["checkpoints"][arm] = {"path": str(path.relative_to(package)), "sha256": sha(path)}
        if numeric:
            state = final[core.ARMS[0]]
            reservation = group + "_NUMERICAL_RESERVED_NOT_DISPATCHED"
            state["numerical_no_proposal"] = [{"attempt_id_reserved_but_not_dispatched": reservation,
                "rng_before": ["STUB_INITIAL"], "rng_after": ["STUB_CONSUMED"], "STUB_ONLY": True}]
            state["seen_attempt_ids"] = [reservation]; state["rng"] = ["STUB_CONSUMED"]
        if pending_hard:
            final[core.ARMS[0]]["pending"] = [{"attempt_id": group + "_STUB_PENDING_HARD",
                "physical_receipt": {"true_hard_safety_violation": True, "engineering_complete": False,
                                     "STUB_ONLY_NOT_REAL_RECEIPT": True}}]
        output_relative = "STUB_ONLY_OUTPUT"
        bundle = {"schema": "v8.continuous_beta_pending_bundle.v1", "STUB_ONLY_NOT_REAL_JOB": True,
            "stage": "OWNER_STOPPED_PENDING_PRESERVED_NO_UPDATE", "parameter_updates_in_this_job": 0,
            "group_evaluation_only": group, "logical_context_evaluation_only": "STUB_CONTEXT_A",
            "snapshots": final, "context25": {"STUB_ONLY_NO_REAL_CONTEXT": True}}
        bundle_path = package / output_relative / "PENDING_CHECKPOINTS.json"; put(bundle_path, bundle)
        for arm in core.ARMS:
            put(package / output_relative / (arm + "_PENDING.json"), final[arm])
        config = {"group": group, "STUB_ONLY_NOT_REAL_JOB": True, "frozen_artifacts": {},
            "onpolicy_sampling": {"schema": "v8.continuous_beta_sampling_job.v1", "output_directory": output_relative,
                "development_context_id": "STUB_CONTEXT_A", "arm_inputs": [{"arm_id": arm,
                    "snapshot_path": current["checkpoints"][arm]["path"],
                    "snapshot_sha256": current["checkpoints"][arm]["sha256"]} for arm in core.ARMS]}}
        config_path = package / "experiments" / (group + ".json"); put(config_path, config)
        ids = [group + "_parent"] + ([] if before_B else [group + "_B"])
        event_rows = []
        for ident in ids:
            event_rows.append({"event": "START", "id": ident, "group": group, "config_sha256": sha(config_path),
                "pid": os.getpid(), "start_ticks": ticks, "kind": "STUB_ONLY_NO_ACTUAL_PHYSICS", "unix": start})
            if open_child and ident.endswith("_B"):
                continue
            end = {"event": "END", "id": ident, "joined": True, "returncode": 1, "unix": start + .001,
                   "STUB_ONLY": True}
            if ident.endswith("_B") and prefix_hash is not None:
                end["parent_hash_equal"] = prefix_hash
            event_rows.append(end)
        event_path = package / "runtime/ATTEMPTS.jsonl"; event_path.parent.mkdir()
        with event_path.open("x") as stream:
            for row in event_rows:
                stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        put(package / "jobs" / group / "WORKER_DONE.json", {"status": "FAILED_PRESERVED", "rows": [],
            "error": "STUB_ONLY_ADAPTER_ENGINEERING_FAILURE", "STUB_ONLY": True})
        put(package / "owned" / (group + "_SUPERVISOR_END.json"), {"state": "STOP", "worker_exit_code": 1,
            "survivors": [], "STUB_ONLY": True})
        put(package / "owned" / (group + "_EXIT.json"), {"pid": os.getpid(), "active_child": None, "STUB_ONLY": True})
        safety_path = package / "audit/STUB_ONLY_MAIN_ORIGINAL_SAFE_RECONCILIATION.json"
        put(safety_path, {"STUB_ONLY_NOT_REAL_SAFETY_EVIDENCE": True, "reviewed_attempts": ids,
                          "true_hard_safety_violation": False})
        safety_ref = {str(safety_path.relative_to(package)): sha(safety_path)}
        review = {"schema": "v8.beta_four_arm_root_closure_review.v1", "STUB_ONLY_NOT_REAL_AUTHORITY": True,
            "status": "ENGINEERING_CENSOR_CANCEL_ALL_ARMS", "group_transaction_id": group + "_STUB_TX",
            "true_hard_safety_violation": False, "all_started_attempts_hard_safety_reviewed": True,
            "all_started_children_joined": True, "all_parent_prefixes_unchanged": True,
            "pending_snapshot_object_sha256": {arm: core.digest(final[arm]) for arm in core.ARMS},
            "original_evidence_files_sha256": safety_ref,
            "cancel_started_attempt_safety": {ident: {"true_hard_safety_violation": False,
                "original_evidence_files_sha256": safety_ref, "STUB_ONLY": True} for ident in ids},
            "resolved_unknown_hard_attempts": {ident: {"true_hard_safety_violation": False,
                "original_evidence_files_sha256": safety_ref, "STUB_ONLY": True} for ident in ids}}
        if reviewed_hard:
            review["cancel_started_attempt_safety"][ids[-1]]["true_hard_safety_violation"] = True
        if unknown_safety:
            review["cancel_started_attempt_safety"][ids[-1]]["true_hard_safety_violation"] = None
        if prefix_proof:
            prefix_path = package / "runtime/reports/STUB_ONLY_PARENT_CHECKS.json"
            put(prefix_path, [{"id": group + "_B", "unchanged": True, "before": "STUB_EQUAL_PREFIX",
                               "after": "STUB_EQUAL_PREFIX", "child_exitcode": 1, "STUB_ONLY": True}])
            review["parent_prefix_evidence_by_attempt"] = {group + "_B":
                {"path": str(prefix_path.relative_to(package)), "sha256": sha(prefix_path)}}
        review_path = package / "STUB_ONLY_ROOT_REVIEW.json"; put(review_path, review)
        inputs = {"schema": "v8.beta_root_bound_pending_input.v1", "STUB_ONLY_NOT_REAL_INPUT": True,
            "job_configs": [{"path": str(config_path.relative_to(package)), "sha256": sha(config_path)}],
            "root_expected_sampling_groups": [group], "final_pending_bundle":
                {"path": str(bundle_path.relative_to(package)), "sha256": sha(bundle_path)},
            "root_closure_review": {"path": str(review_path.relative_to(package)), "sha256": sha(review_path)}}
        assert not (package / "audit" / (group + "_PARENT_RAW_GATE.json")).exists()
        assert not (package / output_relative / "B_BASELINE_RECEIPT.json").exists()
        return package, group, inputs, current, final

    try:
        specifications = [
            ("failed_B_missing_parent_raw", {}, True, None),
            ("before_B_dispatch_no_complete_B", {"before_B": True}, True, None),
            ("numerical_rng_reservation_preserved", {"numeric": True}, True, None),
            ("unknown_END_with_original_prefix_proof", {"prefix_hash": None, "prefix_proof": True}, True, None),
            ("mutated_parent_not_overridden", {"prefix_hash": False, "prefix_proof": True}, False, "PREFIX_MUTATED"),
            ("unknown_prefix_without_evidence", {"prefix_hash": None}, False, "NEEDS_ORIGINAL_EQUAL_PARENT"),
            ("true_pending_hard_not_engineering_cancel", {"pending_hard": True}, False, "GLOBAL_HARD_SAFETY_STOP"),
            ("true_reviewed_attempt_not_false_override", {"reviewed_hard": True}, False, "GLOBAL_HARD_SAFETY_STOP"),
            ("unknown_started_safety_rejected", {"unknown_safety": True}, False, "REQUIRES_EXPLICIT_SAFE"),
            ("unjoined_child_rejected", {"open_child": True}, False, "ALL_ACTUAL_START_END")]
        for name, kwargs, expected_pass, error_fragment in specifications:
            package, group, inputs, current, final = build_case(name, **kwargs)
            frozen_final = core.digest(final)
            counts["actual_evidence_verify_entry_calls"] += 1
            try:
                proof = evidence.verify_pending_input(package, inputs, current, cancelling=True,
                    rebuild_receipt=fail_adapter, rebuild_baseline=fail_adapter)
                assert expected_pass, "EXPECTED_REJECTION_BUT_PASSED"
                assert proof["closed_jobs"][group]["complete_parent_raw_gate_present"] is False
                assert proof["closed_jobs"][group]["complete_parent_raw_gate_status"] is None
                outcome = "PASS_CANCEL_ORIGINAL_CLOSED_PARTIAL_NO_FABRICATED_RAW_GATE"
                put(package / "STUB_ONLY_ACCEPTED_PROOF.json", proof)
            except ValueError as error:
                assert not expected_pass and error_fragment in str(error), (name, str(error))
                outcome = str(error)
                put(package / "STUB_ONLY_REJECTION.json", {"status": "EXPECTED_REJECTION", "error": outcome})
            assert core.digest(final) == frozen_final, "EVIDENCE_MUTATED_PENDING_RNG_OR_COST"
            cases.append({"case": name, "outcome": outcome, "expected_pass": expected_pass,
                          "no_complete_B_or_parent_raw_created": True, "pending_and_rng_unchanged": True})
        fsync_package = output / "mkdir_fsync" / "STUB_ONLY_PACKAGE"
        family = fsync_package / "families/ppo_reward/continuous_scale_v1"; family.mkdir(parents=True)
        plan = fsync_package / "STUB_ONLY_PLAN.json"; put(plan, {"STUB_ONLY": True})
        order = []
        class OrderedStore(core.DurableRun):
            def _syncdir(self, directory):
                super()._syncdir(directory)
                order.append("FSYNC_DONE:" + str(Path(directory).relative_to(fsync_package)))
            def _new(self, path, value):
                order.append("NEW:" + path.name)
                super()._new(path, value)
        class StubInitializer:
            mode = "STUB_ONLY_FSYNC_ORDER_NO_ACTOR"
            def validate_plan(self, plan, *, require_live_window): return []
            def initialize(self, plan):
                counts["stub_initialize_calls"] += 1; counts["stub_checkpoint_dicts_constructed"] += 4
                order.append("STUB_INITIALIZER_AFTER_DURABLE_INTENT")
                return {"status": "READY_ALL_FOUR_INITIALIZED", "snapshots": {arm:
                    {"STUB_ONLY_NO_BETA": True, "batch_id": 0, "pending": []} for arm in core.ARMS}}
            def work_accounting(self): return {"STUB_ONLY": True, "actual_Beta_calls": 0}
        store = OrderedStore(fsync_package, "families/ppo_reward/continuous_scale_v1/RUN")
        counts["actual_durable_initialize_api_calls"] += 1
        store.initialize({"path": str(plan.relative_to(fsync_package)), "sha256": sha(plan)}, StubInitializer())
        assert order.index("FSYNC_DONE:families/ppo_reward/continuous_scale_v1") < order.index("NEW:RUN_IDENTITY.json")
        assert order.index("NEW:RUN_IDENTITY.json") < order.index("NEW:TRANSACTION_ATTEMPT_0000.json") < order.index("STUB_INITIALIZER_AFTER_DURABLE_INTENT")
        put(output / "MKDIR_PARENT_FSYNC_ACTUAL_ORDER.json", {"STUB_ONLY": True, "actual_fsync_order": order})
        cases.append({"case": "run_parent_directory_fsync_before_identity_intent_or_actor", "status": "PASS_ACTUAL_FSYNC_ORDER_WITH_STUB_INITIALIZER"})
        assert counts["stub_adapter_calls"] == 0
        forbidden = [name for name in sys.modules if name in ("beta_policy", "beta_optimizer_candidate_v2",
                     "beta_transaction_backend_candidate_v2", "beta_group_transaction_candidate_v1",
                     "beta_onpolicy_receipt_adapter_candidate_v1", "mujoco", "categorical_policy")]
        assert not forbidden, forbidden
        put(output / "END.json", {"status": "PASS_STUB_ONLY_PARTIAL_CANCEL_AND_MKDIR_PARENT_FSYNC_V2",
            "cases": cases, "counts": counts, "pid": os.getpid(), "start_ticks": ticks,
            "instrumented_actual_source_API_entry_calls": source_API_entries,
            "start_unix": start, "end_unix": time.time(), "wall_s": time.time()-start, "cpu_self_s": time.process_time()-cpu,
            "rss_start_kib": rss_start, "rss_end_kib": rss(), "ru_maxrss_start_kib": maxrss_start,
            "ru_maxrss_end_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "local_deadline_unix": deadline, "original_global_deadline_unix": GLOBAL_STOP,
            "binding_sha256": sha(binding_path), "new_real_Beta_adapter_raw_or_physics": 0,
            "full_real_integration_claim": False, "real_beta_clock_initialized": False})
        print(json.dumps({"status": "PASS", "cases": len(cases), "counts": counts, "wall_s": time.time()-start}, sort_keys=True))
    except BaseException as error:
        put(output / "FAILED.json", {"status": "FAILED_STUB_ONLY_PRESERVE_NO_RETRY", "error_type": type(error).__name__,
            "error": str(error), "cases_completed": cases, "counts": counts, "created_unix": time.time()})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
