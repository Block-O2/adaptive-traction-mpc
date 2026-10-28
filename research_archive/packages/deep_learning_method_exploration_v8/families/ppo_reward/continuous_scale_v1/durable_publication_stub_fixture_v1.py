"""One approved <=60s STUB_ONLY publication fixture, never a Beta fit."""
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
PACKAGE = HERE.parents[2]
GLOBAL_STOP = 1793114740.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fresh_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class StubBackend:
    mode = "STUB_ONLY_NO_BETA_ACTOR_ADAPTER_OR_REAL_RECEIPT"

    def __init__(self, core, *, fail_arm=None):
        self.core = core
        self.fail_arm = fail_arm
        self.counts = {"stub_initializer_calls": 0, "stub_actor_objects": 0,
                       "stub_adapter_prepare_calls": 0, "stub_compute_calls": 0,
                       "stub_optimizer_calls": 0, "stub_cancel_calls": 0}
        self.private = {}

    def work_accounting(self):
        return {**self.counts, "partial_stub_states": copy.deepcopy(self.private),
                "actual_Beta_actor_or_optimizer_calls": 0}

    def validate_plan(self, plan, *, require_live_window):
        assert plan["schema"] == "STUB_ONLY_PUBLICATION_PLAN_NOT_RESEARCH_AUTHORIZATION"
        source = HERE / "beta_durable_transaction_candidate_v1.py"
        return [{"path": str(source.relative_to(PACKAGE)), "sha256": sha(source)}]

    def initialize(self, plan):
        self.counts["stub_initializer_calls"] += 1
        self.counts["stub_actor_objects"] += 4
        snapshots = {arm: {"schema": "STUB_ONLY_CHECKPOINT_NOT_BETA", "arm_id": arm,
                    "batch_id": 0, "pending": [], "stub_weight": 0, "stub_rng_marker": "INITIAL"}
                     for arm in self.core.ARMS}
        return {"status": "READY_ALL_FOUR_INITIALIZED", "snapshots": snapshots,
                "STUB_ONLY": True, "actual_Beta_calls": 0}

    def prepare(self, plan, inputs, current, operation):
        self.counts["stub_adapter_prepare_calls"] += 1
        assert inputs["schema"] == "STUB_ONLY_PENDING_INPUT_NOT_PHYSICAL_EVIDENCE"
        return {"STUB_ONLY": True, "input_digest": self.core.digest(inputs),
                "current_digest": self.core.digest(current), "operation": operation}

    def compute(self, plan, prepared, operation):
        self.counts["stub_compute_calls"] += 1
        self.private = {}
        for index, arm in enumerate(self.core.ARMS):
            old = self.core.verified(PACKAGE, prepared["previous_pointer"]["checkpoints"][arm])
            new = copy.deepcopy(old)
            if operation == "cancel":
                self.counts["stub_cancel_calls"] += 1
            else:
                self.counts["stub_optimizer_calls"] += 1
                new["stub_weight"] += 1
            new["batch_id"] += 1
            new["stub_rng_marker"] = "CONSUMED_STUB_RNG_NOT_REWOUND"
            self.private[arm] = new
            if self.fail_arm == index:
                raise RuntimeError("INJECTED_STUB_PRIVATE_ARM_FAILURE_" + arm)
        return {"status": "READY_ALL_FOUR_CANCELLED" if operation == "cancel" else "READY_ALL_FOUR_UPDATED",
                "snapshots": self.private, "STUB_ONLY": True, "actual_Beta_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-stub-publication-60s", action="store_true", required=True)
    args = parser.parse_args()
    binding_path = HERE / "DURABLE_TRANSACTION_STUB_SOURCE_BINDING_V1.json"
    binding = json.loads(binding_path.read_text())
    for relative, expected in binding["files_sha256"].items():
        path = HERE / relative
        assert sha(path) == expected, "PREEXECUTION_FROZEN_SOURCE_CHANGED:" + relative
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    output = HERE / "durable_publication_stub_fixture_v1"
    assert not output.exists(), "NO_OVERWRITE_OR_SECOND_FIXTURE"
    assert time.time() < GLOBAL_STOP, "ORIGINAL_HARD_STOP"
    output.mkdir()
    start = time.time(); cpu_start = time.process_time(); deadline = min(start + 60, GLOBAL_STOP)
    ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    usage_start = resource.getrusage(resource.RUSAGE_SELF)
    initial_rss = int(next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")).split()[1])
    fresh_json(output / "START.json", {"status": "STARTED_STUB_ONLY_PUBLICATION_FIXTURE", "pid": os.getpid(),
        "start_ticks": ticks, "start_unix": start, "cpu_start_s": cpu_start, "rss_start_kib": initial_rss,
        "ru_maxrss_start_kib": usage_start.ru_maxrss, "local_deadline_unix": deadline,
        "original_global_deadline_unix": GLOBAL_STOP, "source_binding_sha256": sha(binding_path),
        "actual_Beta_calls": 0, "new_physics": 0})

    def timeout(signum, frame):
        raise TimeoutError("STUB_FIXTURE_60S_LOCAL_DEADLINE")
    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.time()))
    sys.path.insert(0, str(HERE))
    import beta_durable_transaction_candidate_v1 as core
    from beta_transaction_evidence_candidate_v1 import hard_gate
    core_api_calls = {name: 0 for name in ("initialize", "prepare", "commit", "recover", "_materialize", "_pointer_replace", "_write_bytes_new")}
    for method_name in core_api_calls:
        original_method = getattr(core.DurableRun, method_name)
        def counted(self, *args, _name=method_name, _method=original_method, **kwargs):
            core_api_calls[_name] += 1
            return _method(self, *args, **kwargs)
        setattr(core.DurableRun, method_name, counted)
    cases, backends = [], []

    def ref(path):
        return {"path": str(path.relative_to(PACKAGE)), "sha256": sha(path)}

    def setup(name, *, fail_arm=None):
        root = output / name
        root.mkdir()
        plan = root / "STUB_ONLY_PLAN.json"
        pending = root / "STUB_ONLY_INPUT.json"
        fresh_json(plan, {"schema": "STUB_ONLY_PUBLICATION_PLAN_NOT_RESEARCH_AUTHORIZATION"})
        fresh_json(pending, {"schema": "STUB_ONLY_PENDING_INPUT_NOT_PHYSICAL_EVIDENCE", "case": name})
        backend = StubBackend(core, fail_arm=fail_arm); backends.append(backend)
        store = core.DurableRun(PACKAGE, str((root / "RUN").relative_to(PACKAGE)))
        initial = store.initialize(ref(plan), backend)
        return store, backend, ref(pending), initial

    def expect_failure(function, contains=None):
        try:
            function()
        except (ValueError, RuntimeError, FileNotFoundError, BlockingIOError) as error:
            if contains:
                assert contains in str(error), (contains, str(error))
            return type(error).__name__ + ":" + str(error)
        raise AssertionError("EXPECTED_FAILURE_DID_NOT_OCCUR")

    def one_fault(name, point, *, can_recover):
        store, backend, pending, initial = setup(name)
        prepared = store.prepare(pending, backend)
        def inject(actual):
            if actual == point:
                raise RuntimeError("INJECTED_STUB_PUBLICATION_FAULT:" + point)
        store.fault = inject
        failure = expect_failure(lambda: store.commit(prepared, backend), "INJECTED_STUB_PUBLICATION_FAULT")
        pointer_before = store._pointer()
        all_or_old = pointer_before["generation_index"] in (0, 1)
        assert all_or_old and len(pointer_before["checkpoints"]) == 4
        if point != "after_pointer_replace":
            assert pointer_before == initial, "FAILURE_PARTIALLY_PUBLISHED"
        paid_before = copy.deepcopy(backend.counts)
        repeat = expect_failure(lambda: store.commit(prepared, backend))
        assert backend.counts == paid_before, "PRIOR_INTENT_RERAN_COMPUTE_OR_ADAPTER"
        store.fault = None
        if can_recover:
            result = store.recover(1)
            assert backend.counts == paid_before, "RECOVERY_CALLED_STUB_BACKEND"
            now = store._pointer(); assert now["generation_index"] == 1
            computation = core.load(store.run / "TRANSACTION_COMPUTATION_0001.json")
            for arm, item in now["checkpoints"].items():
                assert core.within(PACKAGE, item["path"]).read_bytes() == computation["checkpoint_bytes_utf8"][arm]["utf8"].encode()
            assert all(core.verified(PACKAGE, item)["stub_weight"] == 1 for item in now["checkpoints"].values())
            recovery = "PASS_EXACT_COMPUTED_BYTES_ZERO_STUB_OPTIMIZER_OR_ADAPTER"
        else:
            recovery = expect_failure(lambda: store.recover(1))
            assert store._pointer() == initial
        cases.append({"case": name, "fault": point, "failure": failure, "repeat_blocked": repeat,
                      "recovery": recovery, "counts": copy.deepcopy(backend.counts), "all_or_previous_pointer": True})

    try:
        for name, point, recover in [
            ("intent_only", "after_durable_intent", False),
            ("computed_before_stage", "after_durable_computation", True),
            ("partial_staging_two_checkpoints", "after_checkpoint_write:" + core.ARMS[1], True),
            ("complete_orphan_generation", "after_generation_rename", True),
            ("before_atomic_pointer", "before_pointer_replace", True),
            ("after_atomic_pointer", "after_pointer_replace", True)]:
            one_fault(name, point, can_recover=recover)
        store, backend, pending, initial = setup("third_private_arm_failure", fail_arm=2)
        prepared = store.prepare(pending, backend)
        error = expect_failure(lambda: store.commit(prepared, backend), "INJECTED_STUB_PRIVATE_ARM_FAILURE")
        assert store._pointer() == initial and not (store.run / "GENERATION_0001").exists()
        paid = copy.deepcopy(backend.counts)
        expect_failure(lambda: store.commit(prepared, backend), "EXISTING_INTENT")
        assert paid == backend.counts and backend.counts["stub_optimizer_calls"] == 3
        failure_records = list(store.run.glob("FAILED_ATTEMPT_0001_*.json"))
        assert len(failure_records) == 1 and len(core.load(failure_records[0])["backend_consumed_work"]["partial_stub_states"]) == 3
        cases.append({"case": "third_private_arm_failure", "failure": error, "all_or_previous_pointer": True,
                      "three_consumed_stub_steps_preserved_no_refit": True, "counts": paid})
        store, backend, pending, initial = setup("cancel_all_four_no_fit")
        prepared = store.prepare(pending, backend, operation="cancel")
        pointer = store.commit(prepared, backend, operation="cancel")
        assert pointer["generation_index"] == 1 and backend.counts["stub_optimizer_calls"] == 0
        assert backend.counts["stub_cancel_calls"] == 4
        assert all(core.verified(PACKAGE, i)["stub_weight"] == 0 and
                   core.verified(PACKAGE, i)["stub_rng_marker"] == "CONSUMED_STUB_RNG_NOT_REWOUND"
                   for i in pointer["checkpoints"].values())
        cases.append({"case": "cancel_all_four_no_fit", "all_or_previous_pointer": True,
                      "counts": copy.deepcopy(backend.counts), "stub_rng_preserved": True})
        known = {"true_hard_safety_violation": False, "all_started_attempts_hard_safety_reviewed": True}
        hard_snap = {"x": {"pending": [{"attempt_id": "STUB_ONLY_HARD", "physical_receipt":
                     {"engineering_complete": False, "true_hard_safety_violation": True}}]}}
        expect_failure(lambda: hard_gate(known, hard_snap, cancelling=True), "GLOBAL_HARD_SAFETY_STOP")
        expect_failure(lambda: hard_gate({**known, "true_hard_safety_violation": None}, {}, cancelling=True), "UNKNOWN_GLOBAL")
        unknown = {"x": {"pending": [{"attempt_id": "STUB_ONLY_UNKNOWN", "physical_receipt": None}]}}
        expect_failure(lambda: hard_gate(known, unknown, cancelling=True), "UNKNOWN_RECEIPT")
        hard_gate({**known, "resolved_unknown_hard_attempts": {"STUB_ONLY_UNKNOWN":
            {"true_hard_safety_violation": False, "original_evidence_files_sha256": {"STUB_ONLY_NOT_REAL": "STUB"}}}}, unknown, cancelling=True)
        cases.append({"case": "actual_source_hard_three_value_gate", "true_before_censor": True,
                      "unknown_not_safe": True, "explicit_cancel_reconciliation_structure_only": True,
                      "original_evidence_validation_not_claimed": True})
        forbidden = [name for name in sys.modules if name in ("beta_policy", "beta_optimizer_candidate_v2",
                     "beta_group_transaction_candidate_v1", "beta_onpolicy_receipt_adapter_candidate_v1",
                     "mujoco", "categorical_policy")]
        assert not forbidden, forbidden
        totals = {key: sum(b.counts[key] for b in backends) for key in backends[0].counts}
        status = "PASS_STUB_ONLY_DURABLE_PUBLICATION_FAILURE_AND_ZERO_REFIT_RECOVERY"
        end = {"status": status, "cases": cases, "actual_stub_counts": totals,
               "instrumented_core_API_entry_calls_including_failures": core_api_calls,
               "source_binding_sha256": sha(binding_path), "pid": os.getpid(), "start_ticks": ticks,
               "start_unix": start, "end_unix": time.time(), "wall_s": time.time()-start,
               "cpu_self_s": time.process_time()-cpu_start,
               "rss_end_kib": int(next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")).split()[1]),
               "ru_maxrss_end_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "local_deadline_unix": deadline, "original_global_deadline_unix": GLOBAL_STOP,
               "actual_Beta_initialize_restore_sample_forward_score_update": 0,
               "actual_real_adapter_calls": 0, "actual_real_receipts_or_jobs_used": 0,
               "actual_env_or_physics": 0, "real_beta_clock_initialized": False,
               "full_real_Beta_integration_validation_claim": False}
        fresh_json(output / "END.json", end)
        print(json.dumps({"status": status, "wall_s": end["wall_s"], "counts": totals, "cases": len(cases)}, sort_keys=True))
    except BaseException as error:
        fresh_json(output / "FAILED.json", {"status": "FAILED_STUB_ONLY_KEEP_EVIDENCE_NO_AUTORETRY",
                   "error_type": type(error).__name__, "error": str(error), "cases_completed": cases,
                   "counts": [b.work_accounting() for b in backends], "created_unix": time.time()})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
