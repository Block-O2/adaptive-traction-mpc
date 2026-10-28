"""Separately approved environment correction: same frozen 48 API calls; preserve V1 failure."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json
import math
import os
import platform
import resource
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
GLOBAL_STOP = 1793114740.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def rss():
    return int(next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")).split()[1])


def kl(p, q):
    if any(a > 0 and b == 0 for a, b in zip(p, q)):
        return {"status": "POSITIVE_MASS_OVER_ZERO", "value": None}
    return {"status": "FINITE", "value": sum(a * math.log(a / b) for a, b in zip(p, q) if a > 0)}


def label_state(rows):
    if not rows:
        return "UNKNOWN"
    if any(row["complete"] is not True for row in rows):
        return "OBSERVED_INCOMPLETE_NO_SUCCESS_RANKING"
    statuses = {row["original_qualified"] for row in rows}
    return "OBSERVED_QUALIFIED" if statuses == {True} else "OBSERVED_FAILED_ORIGINAL_QUALIFICATION" if statuses == {False} else "OBSERVED_MIXED_QUALIFICATION"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-once-env-correction-48-forwards-60s", action="store_true", required=True)
    parser.parse_args()
    binding_path = HERE / "SOURCE_AND_DATA_FREEZE_V2.json"
    binding = json.loads(binding_path.read_text())
    for relative, expected in binding["local_files_sha256"].items():
        path = HERE / relative
        assert sha(path) == expected, relative
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    inputs = json.loads((HERE / "INPUTS_V1.json").read_text())
    assert len(inputs["checkpoints"]) == 8 and len(inputs["contexts"]) == 6
    for relative, expected in inputs["source_files_sha256"].items():
        assert sha(PACKAGE / relative) == expected, relative
    output = HERE / "inference_once_v2"
    assert not output.exists(), "FAILURE_IS_PRESERVED_NO_RETRY_OR_OVERWRITE"
    output.mkdir()
    allowed_cpus = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {allowed_cpus[0]})
    start = time.time(); cpu_start = time.process_time(); deadline = min(start + 60, GLOBAL_STOP)
    assert start < GLOBAL_STOP
    ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    before_rss = rss(); before_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    binary = Path(sys.executable).resolve()
    write_new(output / "START.json", {"status": "STARTED_APPROVED_ONCE_48_FORWARD_NO_FIT_NO_PHYSICS", "pid": os.getpid(),
        "start_ticks": ticks, "start_unix": start, "cpu_start_s": cpu_start, "rss_start_kib": before_rss,
        "ru_maxrss_start_kib": before_maxrss, "local_deadline_unix": deadline, "original_global_deadline_unix": GLOBAL_STOP,
        "binary": str(binary), "invoked_sys_executable": sys.executable, "binary_sha256": sha(binary), "python_version": sys.version,
        "platform": platform.platform(), "source_binding_sha256": sha(binding_path),
        "cpu_affinity_single_cpu": sorted(os.sched_getaffinity(0)),
        "inputs_sha256": sha(HERE / "INPUTS_V1.json"), "planned_select_out0_calls": 48,
        "threads_environment": {name: os.environ.get(name) for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONDONTWRITEBYTECODE"]}})
    def timeout(signum, frame):
        raise TimeoutError("DIAGNOSTIC_60S_LOCAL_OR_GLOBAL_HARD_STOP")
    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.time()))
    actual = {"select_out0_entry_calls": 0, "select_out0_completed_calls": 0, "actual_policy_forward_counter_delta": 0,
              "to_context25_calls": 0, "logical_policy_deepcopies": 0, "model_initialize": 0,
              "actor_restore_api": 0, "fit_or_gradient_or_parameter_update": 0, "RNG_draws": 0, "new_physics": 0}
    results = []
    try:
        sys.path.insert(0, str(PACKAGE / "families/ppo_reward"))
        sys.path.insert(0, str(PACKAGE / "families/critic_value/source"))
        import categorical_policy as categorical
        import value_api
        from value_api import to_context25
        assert Path(categorical.__file__).resolve() == PACKAGE / "families/ppo_reward/categorical_policy.py"
        assert Path(value_api.__file__).resolve() == PACKAGE / "families/critic_value/source/value_api.py"
        import numpy as np
        import scipy
        assert sha(binary) == "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"
        assert np.__version__ == "2.2.6" and scipy.__version__ == "1.15.3"
        write_new(output / "ENVIRONMENT_CONFIRMED_BEFORE_FIRST_API.json", {
            "status": "ACTUAL_ENVIRONMENT_CONFIRMED_ZERO_POLICY_CALLS_SO_FAR",
            "numpy_version": np.__version__, "numpy_module": str(Path(np.__file__).resolve()),
            "numpy_module_sha256": sha(Path(np.__file__).resolve()),
            "scipy_version": scipy.__version__, "scipy_module": str(Path(scipy.__file__).resolve()),
            "scipy_module_sha256": sha(Path(scipy.__file__).resolve()),
            "invoked_sys_executable": sys.executable, "resolved_binary": str(binary), "binary_sha256": sha(binary),
            "pid": os.getpid(), "start_ticks": ticks, "unix": time.time(), "cpu_self_elapsed_s": time.process_time()-cpu_start,
            "rss_kib": rss(), "actual_calls": copy.deepcopy(actual), "source_and_data_unchanged": True})
        contexts = {}
        for item in inputs["contexts"]:
            raw = json.loads((PACKAGE / item["raw_context_path"]).read_text())
            actual["to_context25_calls"] += 1
            context = to_context25(raw)
            context_sha = digest({"names": context["feature_names"], "values": context["features"]})
            contexts[item["group_evaluation_only"]] = {**item, "context25": context, "causal25_numeric_identity_sha256": context_sha,
                "derived_context25_object_sha256": digest(context)}
        write_new(output / "CAUSAL25_CONTEXTS.json", contexts)
        with (output / "FORWARD_TRACE.jsonl").open("x") as trace:
            for item in inputs["checkpoints"]:
                checkpoint = json.loads((PACKAGE / item["checkpoint_path"]).read_text())
                policy = copy.deepcopy(checkpoint["policy"]); actual["logical_policy_deepcopies"] += 1
                original_policy_sha = categorical.policy_sha256(policy)
                assert original_policy_sha == item["policy_behavior_sha256"]
                assert [digest(recipe) for recipe in policy["action_contracts"]] == inputs["menu"]["full_recipe_sha256"]
                for group, context in contexts.items():
                    assert time.time() < deadline
                    before = copy.deepcopy(policy["counters"])
                    actual["select_out0_entry_calls"] += 1
                    try:
                        selected = categorical.select_out0(policy, context["context25"]["feature_names"],
                            context["context25"]["features"], qa_validated=True)
                    finally:
                        actual["actual_policy_forward_counter_delta"] += policy["counters"]["forward"] - before["forward"]
                    actual["select_out0_completed_calls"] += 1
                    assert policy["counters"]["forward"] == before["forward"] + 1
                    assert all(policy["counters"][key] == before[key] for key in ("backward_equivalent", "parameter_updates"))
                    assert categorical.policy_sha256(policy) == original_policy_sha
                    probs = selected["probabilities"]
                    labels = context["labels_by_full_recipe_sha256_evaluation_only"]
                    measured = labels[selected["full_recipe_sha256"]]
                    state = label_state(measured)
                    mass = {"OBSERVED_QUALIFIED": 0.0, "OBSERVED_FAILED_ORIGINAL_QUALIFICATION": 0.0, "UNKNOWN": 0.0,
                            "OBSERVED_INCOMPLETE_NO_SUCCESS_RANKING": 0.0, "OBSERVED_MIXED_QUALIFICATION": 0.0}
                    for h, probability in zip(inputs["menu"]["full_recipe_sha256"], probs):
                        mass[label_state(labels[h])] += probability
                    row = {"generation": item["generation"], "arm_id": item["arm_id"], "context_evaluation_only": group,
                        "checkpoint_path": item["checkpoint_path"], "checkpoint_file_sha256": item["checkpoint_file_sha256"],
                        "policy_behavior_sha256": original_policy_sha, "policy_weight_sha256": item["weight_sha256"],
                        "categorical_source_sha256": inputs["source_files_sha256"]["families/ppo_reward/categorical_policy.py"],
                        "raw_context_file_sha256": context["raw_context_file_sha256"],
                        "causal25_numeric_identity_sha256": context["causal25_numeric_identity_sha256"],
                        "action_names": inputs["menu"]["action_names"], "action_recipe_sha256": inputs["menu"]["full_recipe_sha256"],
                        "probabilities": probs, "entropy_nats": -sum(p * math.log(p) for p in probs if p > 0),
                        "argmax_action_index": selected["action_index"], "argmax_action_name": inputs["menu"]["action_names"][selected["action_index"]],
                        "argmax_full_recipe_sha256": selected["full_recipe_sha256"], "argmax_measured_label_status": state,
                        "argmax_actual_observations_evaluation_only": measured,
                        "probability_mass_by_observed_qualification_status": mass,
                        "argmax_task_benefit_inferred": False, "new_physics": 0}
                    results.append(row)
                    trace.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"); trace.flush(); os.fsync(trace.fileno())
        assert actual["select_out0_completed_calls"] == actual["actual_policy_forward_counter_delta"] == 48
        lookup = {(row["generation"], row["arm_id"], row["context_evaluation_only"]): row for row in results}
        changes = []
        for row in results:
            if row["generation"] != 2:
                continue
            old = lookup[(0, row["arm_id"], row["context_evaluation_only"])]
            changes.append({"arm_id": row["arm_id"], "context_evaluation_only": row["context_evaluation_only"],
                "old_argmax": old["argmax_action_name"], "new_argmax": row["argmax_action_name"],
                "argmax_changed": old["argmax_action_index"] != row["argmax_action_index"],
                "entropy_delta_nats": row["entropy_nats"] - old["entropy_nats"],
                "KL_GEN2_to_GEN0": kl(row["probabilities"], old["probabilities"]),
                "KL_GEN0_to_GEN2": kl(old["probabilities"], row["probabilities"]),
                "total_variation": .5 * sum(abs(a-b) for a, b in zip(old["probabilities"], row["probabilities"])),
                "probability_delta": [a-b for a, b in zip(row["probabilities"], old["probabilities"])],
                "observed_qualification_mass_before": old["probability_mass_by_observed_qualification_status"],
                "observed_qualification_mass_after": row["probability_mass_by_observed_qualification_status"]})
        for relative, expected in inputs["source_files_sha256"].items():
            assert sha(PACKAGE / relative) == expected, relative
        write_new(output / "RESULTS.json", {"schema": "v8.first_batch_fixed_policy_inference_diagnostic.v1",
            "status": "PASS_48_FORWARD_ONLY_EXPOSED_DEVELOPMENT", "predictions": results, "changes": changes,
            "actual_calls": actual, "independent_validation_or_control_gain_claim": False,
            "no_policy_checkpoint_source_files_mutated": True})
        write_new(output / "END.json", {"status": "PASS_48_FORWARD_ONLY_NO_FIT_NO_PHYSICS", "actual_calls": actual,
            "pid": os.getpid(), "start_ticks": ticks, "start_unix": start, "end_unix": time.time(),
            "wall_s": time.time()-start, "cpu_self_s": time.process_time()-cpu_start, "rss_start_kib": before_rss,
            "rss_end_kib": rss(), "ru_maxrss_start_kib": before_maxrss,
            "ru_maxrss_end_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "local_deadline_unix": deadline, "original_global_deadline_unix": GLOBAL_STOP,
            "binary": str(binary), "binary_sha256": sha(binary), "results_sha256": sha(output / "RESULTS.json"),
            "sealed_or_active_H2_read": False})
        print(json.dumps({"status": "PASS", "actual_calls": actual, "wall_s": time.time()-start}, sort_keys=True))
    except BaseException as error:
        write_new(output / "FAILED.json", {"status": "FAILED_KEEP_ALL_EVIDENCE_NO_RETRY", "error": str(error),
            "error_type": type(error).__name__, "traceback": traceback.format_exc(), "actual_calls": actual,
            "completed_prediction_rows": len(results), "created_unix": time.time(), "new_physics": 0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
