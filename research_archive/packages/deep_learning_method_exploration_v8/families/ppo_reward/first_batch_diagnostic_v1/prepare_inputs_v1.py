"""Read only six explicitly approved CLOSED dev groups; zero learner calls."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
GROUPS = ["V8CTX01", "V8CTX02", "V8CTX03", "V8CTX04", "V8OP01HR1", "V8OP01L2"]
ARMS = ["RF_RAW", "PPO_RAW", "RF_SCALED", "PPO_SCALED"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    start = time.time(); cpu_start = time.process_time()
    target = HERE / "INPUTS_V1.json"
    assert not target.exists(), "NO_PREPARATION_OVERWRITE"
    identity = {"pid": os.getpid(), "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
                "start_unix": start, "binary": str(Path(sys.executable).resolve()), "source_sha256": sha(Path(__file__).resolve()),
                "actual_model_calls": 0, "new_physics": 0}
    with (HERE / "PREPARATION_START.json").open("x") as stream:
        json.dump(identity, stream, sort_keys=True, indent=2); stream.write("\n")
    source_files = {}
    def read(relative):
        path = PACKAGE / relative
        source_files[relative] = sha(path)
        return json.loads(path.read_text())
    menu_path = "freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json"
    menu = read(menu_path)
    assert [digest(recipe) for recipe in menu["action_contracts"]] == menu["full_recipe_sha256"]
    contexts = []
    for group in GROUPS:
        done = read("jobs/" + group + "/WORKER_DONE.json")
        supervisor = read("owned/" + group + "_SUPERVISOR_END.json")
        read("owned/" + group + "_EXIT.json")
        parent = read("audit/" + group + "_PARENT_RAW_GATE.json")
        assert done["status"] == "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS"
        assert supervisor["state"] == "STOP" and supervisor["worker_exit_code"] == 0 and not supervisor["survivors"]
        assert parent["status"] == "PASS"
        config = read("experiments/" + group + ".json")
        raw_path = "history/" + group + "_PREFORK_CAUSAL_CONTEXT.json"
        raw = read(raw_path)
        labels = {h: [] for h in menu["full_recipe_sha256"]}
        excluded = []
        for result_path in sorted((PACKAGE / "attempts").glob(group + "_*_RESULT.json")):
            if result_path.name in (group + "_parent_RESULT.json", group + "_HISTORY_B_RESULT.json"):
                excluded.append(result_path.name)
                continue
            relative = str(result_path.relative_to(PACKAGE))
            result = read(relative)
            binding_path = "attempts/" + result["id"] + "_EXECUTION_BINDING.json"
            binding = read(binding_path)
            candidate = copy.deepcopy(binding["candidate"])
            candidate.pop("id", None)
            matches = [i for i, recipe in enumerate(menu["action_contracts"])
                       if digest(binding["action"]) == digest(recipe["action"]) and
                       digest(candidate) == digest(recipe["resolved_base_candidate"])]
            assert len(matches) == 1, (group, result["id"], matches)
            index = matches[0]
            assert result["action"] == binding["action"]
            labels[menu["full_recipe_sha256"][index]].append({
                "attempt_id": result["id"], "action_name": menu["action_names"][index],
                "full_recipe_sha256": menu["full_recipe_sha256"][index],
                "result_path": relative, "result_sha256": source_files[relative],
                "execution_binding_path": binding_path, "execution_binding_sha256": source_files[binding_path],
                "complete": result.get("complete"), "original_qualified": result.get("qualified"),
                "JF_N_s": result.get("JF"), "JM_Nm_s": result.get("JM"),
                "motion_failed_requirements": result.get("motion_vs_B", {}).get("failed_requirements"),
                "actual_new_native_steps": result.get("actual_new_native_steps"),
                "is_original_B_control": result["id"] == group + "_B"})
        assert sum(row["is_original_B_control"] for rows in labels.values() for row in rows) == 1
        contexts.append({"group_evaluation_only": group, "raw_context_path": raw_path,
            "raw_context_file_sha256": source_files[raw_path], "raw_context_object_sha256": digest(raw),
            "raw_context_causal_payload_sha256": raw["causal_payload_sha256"],
            "case_sha256_evaluation_only": config["case_sha256"], "labels_by_full_recipe_sha256_evaluation_only": labels,
            "excluded_parent_and_HISTORY_B_filenames_not_used_as_observations": excluded})
    checkpoints = []
    for generation in (0, 2):
        directory = "families/ppo_reward/onpolicy_runs/GENUINE_V1/GENERATION_%04d/" % generation
        transaction = read(directory + "TRANSACTION.json")
        for arm in ARMS:
            path = directory + arm + ".json"
            checkpoint = read(path)
            assert source_files[path] == transaction["checkpoints"][arm]["sha256"]
            policy = checkpoint["policy"]
            assert policy["action_sha256"] == menu["full_recipe_sha256"]
            assert [digest(c) for c in policy["action_contracts"]] == menu["full_recipe_sha256"]
            checkpoints.append({"generation": generation, "arm_id": arm, "checkpoint_path": path,
                "checkpoint_file_sha256": source_files[path], "policy_behavior_sha256": checkpoint["batch_policy_sha256"],
                "weight_sha256": digest(policy["weights"]), "initial_policy_counters": policy["counters"]})
    for path in ["audit/GENUINE_BATCH1_MAIN_MECHANISM_REVIEW_V1.json", "audit/ACTION_PERMISSION_CORRECTION_V1.json",
                 "audit/ONPOLICY_JSON_IDENTITY_CORRECTION_APPROVAL_V1.json", "audit/ONPOLICY_FINITE_SCHEDULING_EXCEPTION_V1.json",
                 "ACTIVATION.json"]:
        read(path)
    for path in ["families/ppo_reward/categorical_policy.py", "families/critic_value/source/value_api.py",
                 "families/ppo_reward/onpolicy_update_driver_v2.py", "source/v8_worker_v1.py",
                 "source/v7_causal_context.py"]:
        source_files[path] = sha(PACKAGE / path)
    target.write_text(json.dumps({"schema": "v8.first_genuine_batch_fixed_diagnostic_inputs.v1",
        "status": "SIX_CLOSED_DEV_GROUPS_FIXED_GEN0_GEN2_BEFORE_INFERENCE", "created_unix": time.time(),
        "contexts": contexts, "checkpoints": checkpoints, "menu": menu,
        "source_files_sha256": source_files, "intended_select_out0_calls": 48,
        "actual_model_calls_in_preparation": 0, "sealed_or_active_H2_read": False,
        "missing_action_labels": "UNKNOWN_NO_INTERPOLATION_OR_IMPUTATION"}, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"inputs": str(target), "sha256": sha(target), "source_file_count": len(source_files),
                      "contexts": len(contexts), "checkpoints": len(checkpoints),
                      "measured_observations": sum(len(rows) for c in contexts for rows in c["labels_by_full_recipe_sha256_evaluation_only"].values()),
                      "actual_model_calls": 0}, sort_keys=True))
    with (HERE / "PREPARATION_END.json").open("x") as stream:
        json.dump({**identity, "status": "PASS_READ_ONLY_METADATA_PREPARATION", "end_unix": time.time(),
                   "wall_s": time.time()-start, "cpu_self_s": time.process_time()-cpu_start,
                   "inputs_sha256": sha(target), "source_files": len(source_files)}, stream, sort_keys=True, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
