"""Source candidate: durable four-arm publication, without actor imports.

Only the injected backend can construct/restore/optimize actors. Recovery uses
the already persisted UTF-8 checkpoint bytes and never invokes that backend.
CLI always selects the real backend; the isolated fixture injects a stub.
"""
from pathlib import Path
from contextlib import contextmanager
import argparse
import fcntl
import hashlib
import json
import os
import time
import traceback

ARMS = ["BETA_RF_RAW", "BETA_PPO_RAW", "BETA_RF_SCALED", "BETA_PPO_SCALED"]


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(encoded(value)[:-1]).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 2**20), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def within(root, relative):
    if not isinstance(relative, str):
        raise ValueError("PATH_MUST_BE_STRING")
    result = (Path(root).resolve() / relative).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("PATH_ESCAPES_ROOT")
    return result


def verified(root, item):
    path = within(root, item["path"])
    if sha(path) != item["sha256"]:
        raise ValueError("FROZEN_FILE_CHANGED:" + item["path"])
    return load(path)


class DurableRun:
    def __init__(self, package, run, *, fault=None):
        self.package = Path(package).resolve()
        self.run = within(self.package, str(run))
        family = self.package / "families/ppo_reward/continuous_scale_v1"
        if not self.run.is_relative_to(family) or self.run == family:
            raise ValueError("NEW_RUN_MUST_BE_INSIDE_CONTINUOUS_FAMILY")
        self.owner_pid = os.getpid()
        self.fault = fault

    def _owner(self):
        if os.getpid() != self.owner_pid:
            raise RuntimeError("FORK_CHILD_HAS_NO_TRANSACTION_WRITE_AUTHORITY")

    def _hit(self, point):
        if self.fault:
            self.fault(point)

    def _syncdir(self, directory):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write_bytes_new(self, path, data):
        self._owner()
        if not path.resolve().is_relative_to(self.run):
            raise ValueError("TRANSACTION_WRITE_ESCAPES_RUN")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self._syncdir(path.parent)

    def _new(self, path, value):
        self._write_bytes_new(path, encoded(value))

    @contextmanager
    def locked(self):
        self._owner()
        self.run.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.run.parent / (self.run.name + ".TRANSACTION.lock")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def _identity(self):
        identity = load(self.run / "RUN_IDENTITY.json")
        for item in identity["frozen_input_files"]:
            if sha(within(self.package, item["path"])) != item["sha256"]:
                raise ValueError("RUN_FROZEN_INPUT_CHANGED:" + item["path"])
        return identity

    def _pointer(self):
        path = self.run / "CURRENT.json"
        if not path.exists():
            return None
        current = load(path)
        self._validate_generation(current)
        return current

    def _validate_generation(self, pointer):
        final = within(self.package, pointer["generation_directory"])
        if final.parent != self.run or final.name != "GENERATION_%04d" % pointer["generation_index"]:
            raise ValueError("POINTER_GENERATION_PATH")
        transaction = final / "TRANSACTION.json"
        if sha(transaction) != pointer["transaction_sha256"]:
            raise ValueError("IMMUTABLE_GENERATION_TRANSACTION_CHANGED")
        manifest = load(transaction)
        if (manifest["generation_index"] != pointer["generation_index"] or
                manifest["checkpoints"] != pointer["checkpoints"] or
                manifest["status"] != pointer["status"] or set(manifest["checkpoints"]) != set(ARMS)):
            raise ValueError("POINTER_MANIFEST_IDENTITY")
        for arm, item in manifest["checkpoints"].items():
            target = within(self.package, item["path"])
            if target != final / (arm + ".json") or sha(target) != item["sha256"]:
                raise ValueError("IMMUTABLE_CHECKPOINT_CHANGED")
        return manifest

    def _pointer_replace(self, pointer):
        self._owner()
        temporary = self.run / ("CURRENT.tmp.%d.%d.json" % (os.getpid(), time.time_ns()))
        self._new(temporary, pointer)
        self._hit("before_pointer_replace")
        os.replace(temporary, self.run / "CURRENT.json")
        self._syncdir(self.run)
        self._hit("after_pointer_replace")

    def _materialize(self, output, computation_path):
        """Only writes validated, already computed bytes. No backend access."""
        index = output["generation_index"]
        final = self.run / ("GENERATION_%04d" % index)
        manifest = {arm: {"path": str((final / (arm + ".json")).relative_to(self.package)),
                          "sha256": entry["sha256"], "object_sha256": entry["object_sha256"]}
                    for arm, entry in output["checkpoint_bytes_utf8"].items()}
        expected_metadata = {**output["metadata"], "generation_index": index, "checkpoints": manifest,
                             "previous_pointer_sha256": digest(output["previous_pointer"]),
                             "computation_path": str(computation_path.relative_to(self.package)),
                             "computation_sha256": sha(computation_path), "all_four_published_together": True}
        if not final.exists():
            stage = self.run / ("STAGING_%04d_%d" % (index, time.time_ns()))
            stage.mkdir()
            if set(output["checkpoint_bytes_utf8"]) != set(ARMS):
                raise ValueError("COMPUTATION_MUST_CONTAIN_ALL_FOUR_CHECKPOINT_BYTES")
            for arm in ARMS:
                entry = output["checkpoint_bytes_utf8"][arm]
                data = entry["utf8"].encode()
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise ValueError("DURABLE_COMPUTED_BYTES_CHANGED")
                snapshot = json.loads(data)
                if digest(snapshot) != entry["object_sha256"]:
                    raise ValueError("DURABLE_COMPUTED_OBJECT_CHANGED")
                self._write_bytes_new(stage / (arm + ".json"), data)
                self._hit("after_checkpoint_write:" + arm)
            self._new(stage / "TRANSACTION.json", expected_metadata)
            self._hit("before_generation_rename")
            self._owner()
            if final.exists():
                raise ValueError("REFUSE_GENERATION_OVERWRITE")
            os.rename(stage, final)
            self._syncdir(self.run)
            self._hit("after_generation_rename")
        manifest = load(final / "TRANSACTION.json")
        if manifest != expected_metadata:
            raise ValueError("ORPHAN_GENERATION_NOT_THIS_DURABLE_COMPUTATION")
        for arm, entry in output["checkpoint_bytes_utf8"].items():
            if (sha(final / (arm + ".json")) != entry["sha256"] or
                    (final / (arm + ".json")).read_bytes() != entry["utf8"].encode()):
                raise ValueError("RECOVERY_MUST_PUBLISH_EXACT_COMPUTED_BYTES")
        pointer = {"schema": "v8.beta_durable_current_pointer.v1", "generation_index": index,
                   "generation_directory": str(final.relative_to(self.package)),
                   "transaction_sha256": sha(final / "TRANSACTION.json"),
                   "checkpoints": manifest["checkpoints"], "status": manifest["status"]}
        self._validate_generation(pointer)
        self._pointer_replace(pointer)
        return pointer

    def _paths(self, index):
        return (self.run / ("TRANSACTION_ATTEMPT_%04d.json" % index),
                self.run / ("TRANSACTION_COMPUTATION_%04d.json" % index))

    def _execute(self, *, index, previous, operation, prepared, backend, plan):
        intent, computation = self._paths(index)
        if intent.exists() or computation.exists() or (self.run / ("GENERATION_%04d" % index)).exists():
            raise ValueError("EXISTING_INTENT_OR_COMPUTATION_NO_REFIT_USE_EXPLICIT_RECOVERY")
        self._new(intent, {"schema": "v8.beta_durable_transaction_attempt.v1", "operation": operation,
                           "generation_index": index, "previous_pointer": previous,
                           "prepared_object_sha256": digest(prepared), "prepared": prepared,
                           "backend_mode": backend.mode, "created_unix": time.time(),
                           "optimizer_must_never_repeat_for_this_intent": True})
        self._hit("after_durable_intent")
        try:
            result = backend.initialize(plan) if operation == "init" else backend.compute(plan, prepared, operation)
            if result.get("status") not in ("READY_ALL_FOUR_INITIALIZED", "READY_ALL_FOUR_UPDATED", "READY_ALL_FOUR_CANCELLED"):
                self._new(self.run / ("ABORTED_PRIVATE_RESULT_%04d.json" % index), result)
                raise ValueError("ALL_FOUR_PRIVATE_DRAFTS_DID_NOT_COMPLETE")
            if set(result["snapshots"]) != set(ARMS):
                raise ValueError("PRIVATE_RESULT_HAS_PARTIAL_ARM_SET")
            snapshots = result["snapshots"]
            batches = {snapshot["batch_id"] for snapshot in snapshots.values()}
            if len(batches) != 1 or any(snapshot["pending"] for snapshot in snapshots.values()):
                raise ValueError("PRIVATE_ENDPOINTS_UNALIGNED_OR_PENDING")
            self._hit("after_all_private_drafts")
            data = {arm: encoded(snapshots[arm]) for arm in ARMS}
            output = {"schema": "v8.beta_durable_completed_computation.v1", "generation_index": index,
                      "previous_pointer": previous, "intent_sha256": sha(intent),
                      "checkpoint_bytes_utf8": {arm: {"utf8": blob.decode(),
                          "sha256": hashlib.sha256(blob).hexdigest(), "object_sha256": digest(snapshots[arm])}
                          for arm, blob in data.items()},
                      "metadata": {"status": result["status"], "operation": operation,
                          "backend_mode": backend.mode, "result_accounting": {k: v for k, v in result.items() if k != "snapshots"},
                          "prepared_object_sha256": digest(prepared), "created_unix": time.time(),
                          "optimizer_calls_on_recovery": 0, "best_checkpoint_selection": False},
                      "optimizer_must_not_run_on_recovery": True}
            self._new(computation, output)
            self._new(self.run / ("TRANSACTION_COMPUTATION_SEAL_%04d.json" % index),
                      {"computation_sha256": sha(computation), "intent_sha256": sha(intent),
                       "generation_index": index, "checkpoint_file_sha256": {a: v["sha256"]
                       for a, v in output["checkpoint_bytes_utf8"].items()}})
            self._hit("after_durable_computation")
            return self._materialize(output, computation)
        except BaseException as error:
            evidence = self.run / ("FAILED_ATTEMPT_%04d_%d.json" % (index, time.time_ns()))
            self._new(evidence, {"status": "NO_REFIT_REVIEW_DURABLE_INTENT_OR_COMPUTATION", "error": str(error),
                       "error_type": type(error).__name__, "traceback": traceback.format_exc(),
                       "computation_exists": computation.exists(), "intent_sha256": sha(intent),
                       "backend_consumed_work": backend.work_accounting(), "created_unix": time.time()})
            raise

    def initialize(self, plan_ref, backend):
        with self.locked():
            if self.run.exists():
                raise ValueError("REFUSE_REINITIALIZATION_OR_CLOCK_RESET")
            plan = verified(self.package, plan_ref)
            frozen = backend.validate_plan(plan, require_live_window=True)
            self.run.mkdir()
            self._syncdir(self.run.parent)
            self._hit("after_run_parent_fsync_before_identity_intent_actor")
            self._new(self.run / "RUN_IDENTITY.json", {"schema": "v8.beta_durable_run_identity.v1",
                       "plan": plan_ref, "frozen_input_files": [plan_ref] + frozen,
                       "backend_mode": backend.mode, "clock_initialized_by_this_wrapper": False,
                       "global_clock_reset": False, "created_unix": time.time()})
            return self._execute(index=0, previous=None, operation="init", prepared={"plan": plan_ref}, backend=backend, plan=plan)

    def prepare(self, input_ref, backend, *, operation="commit"):
        if operation not in ("commit", "cancel"):
            raise ValueError("PREPARE_OPERATION")
        with self.locked():
            identity = self._identity()
            if identity["backend_mode"] != backend.mode:
                raise ValueError("STUB_AND_REAL_RUNS_CANNOT_BE_INTERCHANGED")
            plan = verified(self.package, identity["plan"])
            current = self._pointer()
            if current is None:
                raise ValueError("INITIAL_GENERATION_NOT_PUBLISHED")
            inputs = verified(self.package, input_ref)
            # Backend evidence validation is metadata-only and hard safety has
            # priority over its live-clock/engineering decisions.
            proof = backend.prepare(plan, inputs, current, operation)
            prepared = {"schema": "v8.beta_durable_prepared_transaction.v1", "operation": operation,
                        "previous_pointer": current, "input": input_ref, "proof": proof,
                        "created_unix": time.time(), "optimizer_or_actor_calls": 0}
            name = "PREPARED_" + digest(prepared) + ".json"
            self._new(self.run / name, prepared)
            return {"path": str((self.run / name).relative_to(self.package)), "sha256": sha(self.run / name)}

    def commit(self, prepared_ref, backend, *, operation="commit"):
        if operation not in ("commit", "cancel"):
            raise ValueError("COMMIT_OPERATION")
        with self.locked():
            identity = self._identity()
            if identity["backend_mode"] != backend.mode:
                raise ValueError("STUB_AND_REAL_RUNS_CANNOT_BE_INTERCHANGED")
            plan = verified(self.package, identity["plan"])
            current = self._pointer()
            prepared = verified(self.package, prepared_ref)
            if prepared.get("operation") != operation or prepared.get("previous_pointer") != current:
                raise ValueError("PREPARED_TRANSACTION_STALE_OR_WRONG_OPERATION")
            index = current["generation_index"] + 1
            intent, computation = self._paths(index)
            if intent.exists() or computation.exists():
                raise ValueError("EXISTING_INTENT_NO_REPEATED_FIT_USE_RECOVERY")
            inputs = verified(self.package, prepared["input"])
            proof = backend.prepare(plan, inputs, current, operation)
            if digest(proof) != digest(prepared["proof"]):
                raise ValueError("ORIGINAL_PROPOSALS_RECEIPTS_OR_RNG_CHAIN_CHANGED")
            return self._execute(index=index, previous=current, operation=operation, prepared=prepared, backend=backend, plan=plan)

    def recover(self, index):
        """No backend parameter, imports, initialization, restore or fitting."""
        with self.locked():
            self._identity()
            intent, computation = self._paths(index)
            output = load(computation)
            seal = load(self.run / ("TRANSACTION_COMPUTATION_SEAL_%04d.json" % index))
            intention = load(intent)
            if (output.get("schema") != "v8.beta_durable_completed_computation.v1" or
                    output.get("generation_index") != index or output["intent_sha256"] != sha(intent) or
                    output.get("optimizer_must_not_run_on_recovery") is not True or
                    seal["computation_sha256"] != sha(computation) or seal["intent_sha256"] != sha(intent) or
                    output["previous_pointer"] != intention["previous_pointer"] or
                    output["metadata"]["prepared_object_sha256"] != intention["prepared_object_sha256"]):
                raise ValueError("NO_VERIFIED_COMPLETED_BYTES_FOR_ZERO_REFIT_RECOVERY")
            prepared = intention["prepared"]
            if "input" in prepared:
                inputs = verified(self.package, prepared["input"])
                proof = prepared["proof"]
                if proof.get("schema") == "v8.beta_exact_original_two_job_chain_proof.v1":
                    review = verified(self.package, inputs["root_closure_review"])
                    if review.get("true_hard_safety_violation") is not False:
                        raise ValueError("RECOVERY_GLOBAL_HARD_TRUE_OR_UNKNOWN")
                    verified(self.package, inputs["final_pending_bundle"])
                    for ref in inputs["job_configs"]:
                        verified(self.package, ref)
                    for path, expected in proof["original_evidence_files_sha256"].items():
                        if sha(within(self.package, path)) != expected:
                            raise ValueError("RECOVERY_ORIGINAL_EVIDENCE_CHANGED")
                    required = proof["original_event_records_and_hash_scopes"]
                    found = {}
                    for raw in (self.package / "runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
                        event = json.loads(raw)
                        key = str(event.get("id")) + "|" + str(event.get("event"))
                        if key in required:
                            if key in found:
                                raise ValueError("RECOVERY_DUPLICATE_ORIGINAL_EVENT")
                            found[key] = {"record": event,
                                "raw_line_without_newline_sha256": hashlib.sha256(raw).hexdigest(),
                                "canonical_record_sha256": digest(event)}
                    if found != required:
                        raise ValueError("RECOVERY_ORIGINAL_EVENT_RECORD_OR_BYTES_CHANGED")
            current = self._pointer()
            if current is not None and current["generation_index"] == index:
                manifest = self._validate_generation(current)
                if manifest["computation_sha256"] != sha(computation):
                    raise ValueError("CURRENT_GENERATION_NOT_THIS_COMPUTATION")
                return {"status": "ALREADY_PUBLISHED_IDENTICAL_COMPUTATION_ZERO_REFIT", "pointer": current,
                        "actor_initializations": 0, "actor_restores": 0, "optimizer_calls": 0}
            if current != output["previous_pointer"]:
                raise ValueError("RECOVERY_PREVIOUS_POINTER_CHANGED")
            pointer = self._materialize(output, computation)
            recovery = self.run / ("RECOVERED_%04d_%d.json" % (index, time.time_ns()))
            self._new(recovery, {"status": "RECOVERED_EXACT_COMPUTED_BYTES_ZERO_ACTOR_OR_OPTIMIZER", "generation_index": index,
                       "computation_sha256": sha(computation), "actor_initializations": 0, "actor_restores": 0,
                       "optimizer_calls": 0, "clock_reset": False, "created_unix": time.time()})
            return pointer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["init", "prepare", "commit", "cancel", "recover"])
    parser.add_argument("--package", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--input", help="Package-relative JSON input or prepared document")
    parser.add_argument("--input-sha256")
    parser.add_argument("--prepare-cancel", action="store_true")
    parser.add_argument("--generation", type=int)
    args = parser.parse_args()
    store = DurableRun(args.package, args.run)
    if args.operation == "recover":
        if args.generation is None:
            parser.error("recover requires --generation")
        result = store.recover(args.generation)
    else:
        if not args.input or not args.input_sha256:
            parser.error("mutation requires --input and --input-sha256")
        from beta_transaction_backend_candidate_v2 import RealBetaBackend
        backend = RealBetaBackend(Path(args.package).resolve())
        ref = {"path": args.input, "sha256": args.input_sha256}
        if args.operation == "init":
            result = store.initialize(ref, backend)
        elif args.operation == "prepare":
            result = store.prepare(ref, backend, operation="cancel" if args.prepare_cancel else "commit")
        else:
            result = store.commit(ref, backend, operation=args.operation)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
