"""SOURCE_ONLY one-shot span-geometry same-LOO replay runner; no authority supplied.

No implicit retry, dispatch, mutable-run access or genuine actor restoration.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import types

GLOBAL_STOP = 1793114740.0
BINARY_SHA = "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"
COMMON_REL = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/"
REL = COMMON_REL+"span_geometry_v1/"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_once(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def fsync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def stats():
    used = resource.getrusage(resource.RUSAGE_SELF)
    stat = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    return {"unix": time.time(), "monotonic": time.monotonic(), "pid": os.getpid(), "start_ticks": int(stat[19]),
            "CPU_user_s": used.ru_utime, "CPU_system_s": used.ru_stime, "RSS_peak_KiB": used.ru_maxrss,
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "python_executable": sys.executable,
            "resolved_python_binary": str(Path(sys.executable).resolve()), "python_binary_sha256": sha(Path(sys.executable).resolve()),
            "python_version": sys.version, "bytecode_writes_disabled": sys.dont_write_bytecode,
            "scientific_libraries_imported": [name for name in ("numpy", "scipy", "torch") if name in sys.modules]}


def load_private(package, relative, namespace, rewrites):
    path = package/relative
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in rewrites:
            node.module = rewrites[node.module]
    module = types.ModuleType(namespace); module.__file__ = str(path)
    sys.modules[namespace] = module
    exec(compile(tree, str(path), "exec"), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--approval-sha256", required=True)
    args = parser.parse_args()
    package = Path(args.package).resolve(); approval_path = Path(args.approval).resolve()
    if not approval_path.is_relative_to(package) or sha(approval_path) != args.approval_sha256:
        raise ValueError("EXACT_MAIN_AUTHORITY_FILE_REQUIRED")
    approval = json.loads(approval_path.read_text())
    stage = approval["stage"]
    if stage != "GateG_SPAN_GEOMETRY_LOO_FIXED_BEHAVIOR_REPLAY":
        raise ValueError("ONLY_NEW_SEPARATELY_APPROVED_CONTEXT_LOO_STAGE")
    expected_input_schema = "v8.beta_feasibility_span_geometry_input.v1"
    cap = 60.0
    if (approval.get("schema") != "v8.beta_feasibility_counterfactual_main_approval.v1" or
            approval.get("status") != "APPROVED_BY_MAIN_FOR_EXACT_INDEPENDENT_OFFLINE_STAGE" or
            approval.get("runner_source_sha256") != sha(__file__) or approval.get("original_global_stop_unix") != GLOBAL_STOP or
            approval.get("single_cpu") is not True or approval.get("new_sampling_or_physics") != 0 or
            not 0 < approval["local_stop_unix"]-approval["local_start_unix"] <= cap or
            not approval["local_start_unix"] <= time.time() < min(approval["local_stop_unix"], GLOBAL_STOP)):
        raise ValueError("ONE_SHOT_REVIEWED_AUTHORITY_AND_UNRESET_CLOCK_REQUIRED")
    if (sha(Path(sys.executable).resolve()) != BINARY_SHA or not sys.dont_write_bytecode or
            os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or
            any(os.environ.get(key) != "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"))):
        raise ValueError("EXACT_APPROVED_BINARY_BYTECODE_AND_THREAD_ENV_REQUIRED")
    manifest_ref = approval["source_manifest"]
    manifest_path = (package/manifest_ref["path"]).resolve()
    if not manifest_path.is_relative_to(package) or sha(manifest_path) != manifest_ref["sha256"]:
        raise ValueError("INDEPENDENT_MAIN_APPROVED_EXACT_SOURCE_MANIFEST_REQUIRED")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("stage") != stage or manifest["source_files_sha256"] != approval["frozen_source_files_sha256"]:
        raise ValueError("CURRENT_HASH_CANNOT_UPGRADE_SOURCE_APPROVAL")
    source_ast = {}
    for relative, expected in approval["frozen_source_files_sha256"].items():
        path = (package/relative).resolve()
        if not path.is_relative_to(package) or "real_runs" in path.relative_to(package).parts or sha(path) != expected:
            raise ValueError("FROZEN_SOURCE_MISMATCH:"+relative)
        if path.suffix == ".py":
            tree = ast.parse(path.read_text(), filename=str(path))
            source_ast[relative] = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    algorithm = REL+"replay_span_geometry_candidate_v1.py"
    if approval["source_sha256"] != approval["frozen_source_files_sha256"].get(algorithm):
        raise ValueError("APPROVAL_NOT_EXACT_SELECTED_STAGE_SOURCE")
    input_ref = approval["input"]
    input_path = (package/input_ref["path"]).resolve()
    if (not input_path.is_relative_to(package) or "real_runs" in input_path.relative_to(package).parts or
            input_ref["sha256"] != approval["input_sha256"] or sha(input_path) != input_ref["sha256"] or
            json.loads(input_path.read_text()).get("schema") != expected_input_schema):
        raise ValueError("EXACT_STAGE_INPUT_NO_ACTUAL_RUN_READ")
    output = (package/approval["one_shot_output_path"]).resolve()
    allowed_parent = (package/REL/"diagnostics").resolve()
    if not output.is_relative_to(allowed_parent) or output == allowed_parent or output.exists():
        raise ValueError("FRESH_EXCLUSIVE_PRIVATE_OUTPUT_ONLY_NO_RETRY")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False); fsync_dir(output.parent)
    initial_affinity = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {min(initial_affinity)})
    if approval.get("address_space_limit_bytes")!=1073741824:
        raise ValueError("EXACT_ONE_GIB_PRIVATE_OFFLINE_LIMIT_REQUIRED")
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824))
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    initial = stats()
    write_once(output/"IDENTITY.json", {"stage": stage, "approval": {"path": str(approval_path.relative_to(package)), "sha256": args.approval_sha256},
               "input": input_ref, "source_manifest": manifest_ref, "source_AST_sha256": source_ast,
               "initial": initial, "initial_affinity_before_single_CPU_pin": initial_affinity, "no_automatic_retry": True})
    write_once(output/"START.json", {"stage": stage, "initial": initial, "approved_local_stop_unix": approval["local_stop_unix"], "global_stop_unix": GLOBAL_STOP})
    fsync_dir(output)
    call_state = {"candidate_source_module_exec_entered": 0, "candidate_source_module_exec_returned": 0,
                  "selected_stage_entry": 0, "selected_stage_returned": 0,
                  "actual_model_fit_or_forward": "SEE_ACTUAL_RETURNED_OR_FAILED_API_COUNTERS"}
    def timeout(_signum, _frame):
        raise TimeoutError("APPROVED_COUNTERFACTUAL_LOCAL_OR_GLOBAL_STOP")
    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.000001, min(approval["local_stop_unix"], GLOBAL_STOP)-time.time()))
    try:
        namespace = "_feascf_"+str(os.getpid())+"_"
        def module(relative, short, rewrites):
            call_state["candidate_source_module_exec_entered"] += 1
            loaded = load_private(package, relative, namespace+short, rewrites)
            call_state["candidate_source_module_exec_returned"] += 1
            return loaded
        module(COMMON_REL+"margin_data_candidate_v1.py", "margin", {})
        module("families/ppo_reward/continuous_scale_v1/axis_mapping.py", "axis", {})
        beta = module("families/ppo_reward/continuous_scale_v1/beta_policy.py", "beta", {"axis_mapping": namespace+"axis"})
        module(REL+"span_preconditioner_candidate_v1.py", "geometry", {})
        replay_api = module(REL+"replay_span_geometry_candidate_v1.py", "replay", {"margin_data_candidate_v1": namespace+"margin", "span_preconditioner_candidate_v1": namespace+"geometry"})
        call_state["selected_stage_entry"] += 1
        result = replay_api.replay_span_geometry(package, input_ref, approval, beta)
        call_state["selected_stage_returned"] += 1
        final = stats()
        # Scientific work has returned. Disable the timer only for durable
        # result/resource bookkeeping; no further scientific call is made.
        signal.setitimer(signal.ITIMER_REAL, 0)
        write_once(output/"RESULT.json", result)
        write_once(output/"DONE.json", {"status": "COMPLETED_EXACT_APPROVED_OFFLINE_STAGE", "stage": stage,
                   "initial": initial, "final": final, "wall_s": final["monotonic"]-initial["monotonic"],
                   "CPU_s": final["CPU_user_s"]+final["CPU_system_s"]-initial["CPU_user_s"]-initial["CPU_system_s"],
                   "runner_calls": call_state, "actual_scientific_counts": result["counts"], "result_sha256": sha(output/"RESULT.json"),
                   "original_WINDOW_CURRENT_checkpoints_touched": False, "new_sampling_or_physics": 0})
        fsync_dir(output)
    except BaseException as error:
        # Minimal paid-failure evidence precedes optional large partial trace.
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            final = stats()
        except BaseException as stats_error:
            final = {"resource_capture_failed": type(stats_error).__name__, "pid": os.getpid(), "unix": time.time()}
        write_once(output/"FAILED.json", {"status": "FAILED_PRESERVED_NO_RETRY", "stage": stage, "error_type": type(error).__name__, "error": str(error),
                   "initial": initial, "final": final, "runner_calls": call_state, "new_sampling_or_physics": 0})
        fsync_dir(output)
        work = getattr(error, "counterfactual_paid_work", None)
        if work is not None:
            write_once(output/"FAILED_PAID_WORK.json", work); fsync_dir(output)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
