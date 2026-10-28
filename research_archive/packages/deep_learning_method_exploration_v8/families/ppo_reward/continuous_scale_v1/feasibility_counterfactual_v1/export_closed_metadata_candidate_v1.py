"""SOURCE_ONLY root-only metadata exporter; never imports any learner API.

The main agent alone may later authorize this helper to read five explicitly
bound immutable files inside the real run. The proposing subagent has not read
those files and has not executed this helper.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

GLOBAL_STOP = 1793114740.0
REL = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/"
BINARY_SHA = "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_bytes_once(path, data):
    with path.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def write_once(path, data):
    write_bytes_once(path, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode())


def resources():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return {"unix": time.time(), "monotonic": time.monotonic(), "pid": os.getpid(),
            "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
            "CPU_user_s": r.ru_utime, "CPU_system_s": r.ru_stime, "RSS_peak_KiB": r.ru_maxrss,
            "resolved_binary": str(Path(sys.executable).resolve()), "binary_sha256": sha_bytes(Path(sys.executable).resolve().read_bytes()),
            "cpu_affinity": sorted(os.sched_getaffinity(0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--approval-sha256", required=True)
    args = parser.parse_args()
    package = Path(args.package).resolve(); auth_path = Path(args.approval).resolve()
    if not auth_path.is_relative_to(package) or sha_bytes(auth_path.read_bytes()) != args.approval_sha256:
        raise ValueError("ROOT_METADATA_EXPORT_AUTHORITY_FILE_SHA_REQUIRED")
    auth = json.loads(auth_path.read_text())
    def clock():
        if not auth["local_start_unix"] <= time.time() < min(auth["local_stop_unix"], GLOBAL_STOP):
            raise ValueError("METADATA_EXPORT_LOCAL_OR_ORIGINAL_GLOBAL_CLOCK")
    if (auth.get("schema") != "v8.beta_feasibility_metadata_export_main_approval.v1" or
            auth.get("status") != "APPROVED_BY_MAIN_FOR_ONE_METADATA_ONLY_EXPORT" or
            auth.get("source_sha256") != sha_bytes(Path(__file__).read_bytes()) or
            auth.get("original_global_stop_unix") != GLOBAL_STOP or auth.get("single_cpu") is not True or
            auth.get("learner_init_restore_forward_fit_RNG_physics") != 0 or
            not 0 < auth["local_stop_unix"]-auth["local_start_unix"] <= 20):
        raise ValueError("SOURCE_PINNED_ROOT_ONLY_METADATA_APPROVAL_REQUIRED")
    clock()
    if not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or sha_bytes(Path(sys.executable).resolve().read_bytes()) != BINARY_SHA:
        raise ValueError("EXACT_APPROVED_BINARY_NO_BYTECODE")
    if any(os.environ.get(k) != "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")):
        raise ValueError("METADATA_EXPORT_SINGLE_THREAD_ENV_REQUIRED")
    counts = {"JSON_read_entered": 1, "JSON_read_returned": 1, "exact_original_file_copy_entered": 0,
              "exact_original_file_copy_returned": 0, "learner_import_init_restore_forward_fit_RNG_physics": 0}
    def load(ref, allow_exact_real_run=False):
        clock(); path = (package/ref["path"]).resolve()
        if not path.is_relative_to(package) or ("real_runs" in path.relative_to(package).parts and not allow_exact_real_run):
            raise ValueError("UNAPPROVED_REAL_RUN_OR_OUTSIDE_PATH")
        raw = path.read_bytes()
        if sha_bytes(raw) != ref["sha256"]:
            raise ValueError("ROOT_PINNED_SOURCE_BYTES_CHANGED:"+ref["path"])
        counts["JSON_read_entered"] += 1
        value = json.loads(raw)
        counts["JSON_read_returned"] += 1
        return value, raw
    source_ref = auth["original_G0_RF_RAW_checkpoint"]
    source_path = (package/source_ref["path"]).resolve()
    expected_parent = package/"families/ppo_reward/continuous_scale_v1/real_runs/GENUINE_BETA_V1/GENERATION_0000"
    if source_path.parent != expected_parent.resolve() or source_path.name != "BETA_RF_RAW.json":
        raise ValueError("ONLY_ROOT_PINNED_IMMUTABLE_GENERATION0000_NO_CURRENT_OR_BEST_DISCOVERY")
    output = (package/auth["exclusive_output_path"]).resolve()
    allowed = (package/REL/"metadata_exports").resolve()
    if not output.is_relative_to(allowed) or output == allowed or output.exists():
        raise ValueError("EXCLUSIVE_NEW_PRIVATE_METADATA_EXPORT_ONLY")
    output.parent.mkdir(parents=True, exist_ok=True); output.mkdir(exist_ok=False); sync_dir(output.parent)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    initial = resources()
    write_once(output/"START.json", {"source_sha256": auth["source_sha256"], "authority_sha256": args.approval_sha256,
               "source_inventory": auth["source_inventory"], "original_G0_ref": source_ref,
               "local_stop_unix": auth["local_stop_unix"], "initial": initial, "counts": dict(counts)})
    sync_dir(output)
    def timeout(_signum, _frame):
        raise TimeoutError("ROOT_METADATA_EXPORT_APPROVED_STOP")
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.000001, min(auth["local_stop_unix"], GLOBAL_STOP)-time.time()))
    exports = {}; copied_sources = []
    try:
        inventory, _ = load(auth["source_inventory"])
        margin, _ = load(auth["closed_GateD_result"])
        done, _ = load(auth["closed_GateD_DONE"])
        if (inventory.get("included_jobs") != ["V8BETA01H", "V8BETA01L"] or len(inventory["selected_samples"]) != 4 or
                margin.get("schema") != "v8.beta_feasibility_counterfactual_margin_data.v1" or len(margin["rows"]) != 4 or
                margin["source_inventory"] != auth["source_inventory"] or margin["counts"]["components_returned"] != 4 or
                margin["counts"]["margin_values_returned"] != 180 or margin["counts"]["model_import_init_forward_restore_fit_RNG_physics"] != 0 or
                done.get("status") != "COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or done.get("result_sha256") != auth["closed_GateD_result"]["sha256"] or
                set(auth["original_closed_proposals_by_id"]) != {item["id"] for item in inventory["selected_samples"]}):
            raise ValueError("ROOT_REVIEWED_CLOSED_EXACT_FOUR_ROW_GATED_REQUIRED")
        checkpoint, raw_checkpoint = load(source_ref, allow_exact_real_run=True)
        policy = checkpoint["policy"]
        names = ("schema", "feature_names", "normalization", "weights", "axis_contract", "axis_contract_sha256", "seed", "arm_id", "gain", "version")
        policy_sha = digest({key: policy[key] for key in names})
        if (checkpoint.get("schema") != "v8.continuous_beta_arm_checkpoint.v2" or checkpoint.get("execution_mode") != "GENUINE_ON_POLICY" or
                checkpoint.get("pending") or policy.get("arm_id") != "BETA_RF_RAW" or policy.get("version") != 0 or
                checkpoint.get("policy_behavior_sha256") != policy_sha or checkpoint.get("batch_policy_sha256") != policy_sha or
                any(item["collection_policy_sha256"] != policy_sha for item in inventory["selected_samples"])):
            raise ValueError("BYTE_EXACT_ORIGINAL_COLLECTION_POLICY_METADATA_ONLY")
        counts["exact_original_file_copy_entered"] += 1
        dest = output/"ORIGINAL_G0_RF_RAW_EXACT.json"; write_bytes_once(dest, raw_checkpoint)
        if sha_bytes(dest.read_bytes()) != source_ref["sha256"]:
            raise ValueError("BEHAVIOR_EXPORT_CHANGED_ORIGINAL_BYTES")
        counts["exact_original_file_copy_returned"] += 1
        behavior_export = {"path": str(dest.relative_to(package)), "sha256": source_ref["sha256"]}
        copied_sources.append({"original": source_ref, "exact_export": behavior_export})
        for row, item in zip(margin["rows"], inventory["selected_samples"]):
            clock()
            if row["id"] != item["id"]:
                raise ValueError("MARGIN_ROWS_NOT_REGISTERED_ORIGINAL_ORDER")
            original = item["closed_proposal_original_ref_referenced_but_not_opened"]
            if auth["original_closed_proposals_by_id"].get(item["id"]) != original:
                raise ValueError("ONLY_FOUR_ORIGINAL_CLOSED_PROPOSAL_FILES_EXPLICITLY_APPROVED")
            proposal, raw_proposal = load(original, allow_exact_real_run=True)
            prediction, _ = load(item["prediction"])
            identity = dict(proposal); expected = identity.pop("proposal_identity_sha256")
            sample = proposal["sample"]
            if (digest(identity) != expected or prediction["proposal_identity_sha256"] != expected or
                    proposal["attempt_id"] != item["id"] or proposal["physical_receipt"] is not None or
                    proposal["qa_validated"] is not True or proposal["feature_names"] != policy["feature_names"] or
                    len(proposal["commissioned25"]) != 25 or
                    digest({"names": proposal["feature_names"], "values": proposal["commissioned25"]}) != proposal["causal_features_sha256"] or
                    sample["policy_sha256"] != policy_sha or sample["old_logprob"] != prediction["old_scalar_logdensity"] or
                    sample["lambda_sample"] != prediction["selected_lambda"] or sample["lambda_sample"] != row["lambda_sample"] or
                    sample["full_recipe_sha256"] != item["full_recipe_sha256"] or digest(sample["full_recipe"]) != sample["full_recipe_sha256"] or
                    sample["physical_action_sha256"] != item["physical_action_sha256"] or digest(sample["proposal_action"]) != sample["physical_action_sha256"] or
                    sample["full_recipe"]["action"] != sample["proposal_action"] or
                    digest(sample["rng_before"]) != prediction["rng_before_canonical_sha256"] or digest(sample["rng_after"]) != prediction["rng_after_canonical_sha256"]):
                raise ValueError("EXACT_ORIGINAL_QA25_OLD_DENSITY_ACTION_RECIPE_RNG_METADATA_BINDING")
            counts["exact_original_file_copy_entered"] += 1
            dest = output/(item["id"]+"_ORIGINAL_PROPOSAL_EXACT.json")
            write_bytes_once(dest, raw_proposal)
            if sha_bytes(dest.read_bytes()) != original["sha256"]:
                raise ValueError("PROPOSAL_EXPORT_CHANGED_ORIGINAL_BYTES")
            counts["exact_original_file_copy_returned"] += 1
            exports[item["id"]] = {"path": str(dest.relative_to(package)), "sha256": original["sha256"]}
            copied_sources.append({"original": original, "exact_export": exports[item["id"]]})
        clock(); signal.setitimer(signal.ITIMER_REAL, 0)
        replay_input = {"schema": "v8.beta_feasibility_counterfactual_replay_input.v1", "target": "FEASIBILITY_ONLY",
                        "margin_data": auth["closed_GateD_result"], "behavior_checkpoint_exact_export": behavior_export,
                        "original_closed_proposal_exact_exports_by_id": exports,
                        "fixed_behavior_replay_not_fresh_onpolicy": True, "export_authority_sha256": args.approval_sha256}
        write_once(output/"REPLAY_INPUT_V1.json", replay_input)
        write_once(output/"EXPORT_MANIFEST.json", {"copied_original_source_files": copied_sources, "counts": counts,
                   "policy_sha256_metadata_only": policy_sha, "context_is_original_causal25_no_recompute": True,
                   "G1_or_active_batch02_not_read": True, "learner_API_calls": 0})
        final = resources()
        write_once(output/"DONE.json", {"status": "COMPLETED_METADATA_ONLY_FIVE_EXACT_FILES", "initial": initial, "final": final,
                   "counts": counts, "replay_input": {"path": str((output/"REPLAY_INPUT_V1.json").relative_to(package)), "sha256": sha_bytes((output/"REPLAY_INPUT_V1.json").read_bytes())},
                   "original_run_CURRENT_window_checkpoints_unchanged": True})
        sync_dir(output)
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write_once(output/"FAILED.json", {"status": "FAILED_PRESERVED_NO_RETRY", "error_type": type(error).__name__, "error": str(error),
                   "counts": counts, "copied_original_source_files": copied_sources, "learner_API_calls": 0})
        sync_dir(output); raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    main()
