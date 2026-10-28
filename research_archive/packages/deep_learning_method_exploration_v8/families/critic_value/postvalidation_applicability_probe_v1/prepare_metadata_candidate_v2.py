"""SOURCE_ONLY metadata builder：仅输出自有prepared目录，不复制root wrapper/不prepare job。

未来须metadata与runtime两项独立主批；六原冻结任务全部闭合后才可构建。
不读原预测/模型/原raw，不运行sequence/比较器/评分器/物理。
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import time

HERE = "families/critic_value/postvalidation_applicability_probe_v1/"
STOP = 1793114740.0
WORKER = "c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe"
GROUPS = {"V8POSTAPP01": ("V8VAL03", "cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c", 2026102753), "V8POSTAPP02": ("V8VAL04", "224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87", 2026102754)}
MANDATORY = ["V8VAL03", "V8VAL04", "V8FMEAN03", "V8FMEAN04", "V8CONVAL01", "V8CONVAL02"]
TAGS = ["B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]
BRANCH = "EXPOSED_POSTVALIDATION_IMPLEMENTATION_CAPABILITY_DIAGNOSTIC_NOT_GENERALIZATION"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "metadata-approval", "runtime-approval", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    def path(rel):
        value = (package / rel).resolve()
        if not value.is_relative_to(package) or value.suffix.lower() in (".gz", ".npz") or "/runtime/source/results/" in str(value):
            raise ValueError("POSTAPP_METADATA_PATH_OR_TYPE")
        return value
    def load(rel):
        return json.loads(path(rel).read_text())
    metadata = json.loads(args.metadata_approval.read_text())
    runtime = json.loads(args.runtime_approval.read_text())
    manifest_path = HERE + "SOURCE_MANIFEST_V2.json"
    manifest = load(manifest_path)
    if metadata.get("status") != "MAIN_APPROVED_POSTAPP_METADATA_BUILD_ONLY_V2" or metadata.get("builder_sha256") != sha(__file__) or metadata.get("manifest_sha256") != sha(path(manifest_path)) or not (metadata["issued_unix"] <= time.time() < metadata["expires_unix"] <= min(metadata["issued_unix"] + 60, STOP)):
        raise ValueError("EXACT_NEW_METADATA_APPROVAL_REQUIRED")
    if runtime.get("status") != "MAIN_APPROVED_EXPOSED_POSTVALIDATION_FIXED_APPLICABILITY_V2" or runtime.get("authorized_groups") != list(GROUPS) or runtime.get("global_stop_unix") != STOP or runtime.get("new_model_fit_scorer_calls") != 0 or runtime.get("original_raw_compare_per_case") != 1:
        raise ValueError("SEPARATE_EXACT_FUTURE_RUNTIME_APPROVAL_REQUIRED")
    output = args.output.resolve()
    if not output.is_relative_to(package / HERE / "prepared") or str(output) != metadata["output_absolute_path"]:
        raise ValueError("UNIQUE_OWNED_PREPARED_OUTPUT_REQUIRED")
    activation = load("ACTIVATION.json")
    plan = load("runtime/RUN_PLAN.json")
    if activation["hard_stop_unix"] != STOP or activation["clock_must_not_reset"] is not True or runtime["local_stop_unix"] > min(STOP, plan["physics_hard_stop_unix"]) or time.time() >= min(runtime["local_stop_unix"], plan["dispatch_cutoff_unix"]) - 600:
        raise ValueError("ORIGINAL_CLOCK_OR_600S_START_RESERVE")
    closure = []
    for group in MANDATORY:
        begin = load("owned/" + group + "_SUPERVISOR.json")
        end = load("owned/" + group + "_SUPERVISOR_END.json")
        if end.get("state") != "STOP" or end.get("survivors") != []:
            raise ValueError("MANDATORY_FROZEN_JOB_NOT_CLOSED:" + group)
        for identity in list(end["known_owned"].values()) + [begin["identity"], begin["worker"]]:
            stat = Path("/proc") / str(identity["pid"]) / "stat"
            if stat.exists() and int(stat.read_text().rsplit(")", 1)[1].split()[19]) == identity["start_ticks"]:
                raise ValueError("MANDATORY_ORIGINAL_PID_ALIVE:" + group)
        closure.append({"group": group, "worker_exit_code": end.get("worker_exit_code"), "supervisor_end_sha256": sha(path("owned/" + group + "_SUPERVISOR_END.json"))})
    dependencies = {}
    def pin(rel, expected=None):
        actual = sha(path(rel))
        if expected is not None and actual != expected:
            raise ValueError("POSTAPP_DEPENDENCY_CHANGED:" + rel)
        if rel in dependencies and dependencies[rel] != actual:
            raise ValueError("POSTAPP_CONFLICTING_PIN:" + rel)
        dependencies[rel] = actual
    for rel, h in manifest["source_files_sha256"].items():
        pin(rel, h)
    pin(manifest_path)
    root_wrapper = "source/v8_postapp_fixed_v2.py"
    pin(root_wrapper, manifest["source_files_sha256"][HERE + "root_wrapper_candidate_v2.py"])
    pin("source/v8_worker_v2.py", WORKER)
    for rel in ["ACTIVATION.json", "runtime/RUN_PLAN.json", "runtime/EXECUTION_CODE_MANIFEST.json", "freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json", "runtime/FROZEN_18D.json", "runtime/PARAMETER_MAP.json", "runtime/ACTION_SET.json", "runtime/MOTION_ACCEPTANCE_PROTOCOL.json"]:
        pin(rel)
    for rel, h in load("runtime/EXECUTION_CODE_MANIFEST.json")["files"].items():
        pin("runtime/" + rel, h)
    approval_rel = str(args.runtime_approval.resolve().relative_to(package))
    pin(approval_rel)
    for group in MANDATORY:
        for rel in ["owned/" + group + "_SUPERVISOR.json", "owned/" + group + "_SUPERVISOR_END.json", "experiments/" + group + ".json", "jobs/" + group + "/SOURCE_MANIFEST.json"]:
            pin(rel)
    menu = load("freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json")["action_contracts"]
    if len(menu) != 5:
        raise ValueError("EXACT_ORIGINAL_FIVE_MENU")
    configs = {}
    catalogs = {}
    for new_group, (old_group, case_sha, seed) in GROUPS.items():
        old = load("experiments/" + old_group + ".json")
        old_job = load("jobs/" + old_group + "/SOURCE_MANIFEST.json")
        if old_job["config_sha256"] != sha(path("experiments/" + old_group + ".json")) or (old["case_sha256"], old["condition"]["seed"]) != (case_sha, seed):
            raise ValueError("EXACT_OLD_CASE_CONFIG_SEED_IDENTITY")
        for rel, h in old_job["files"].items():
            if rel.endswith(".py"):
                pin(rel, h)
        # Original case bytes are not opened here; root dispatch will verify this job pin.
        if old_job["files"].get(old["case_path"]) != case_sha:
            raise ValueError("ORIGINAL_CASE_HASH_NOT_JOB_FROZEN")
        dependencies[old["case_path"]] = case_sha
        original_B_rel = "attempts/" + old_group + "_B_RESULT.json"
        original_B = load(original_B_rel)
        if original_B.get("complete") is not True or original_B.get("qualified") is not True:
            raise ValueError("ORIGINAL_VALIDATION_B_NOT_COMPLETE_QUALIFIED")
        pin(original_B_rel)
        rows = []
        actions = []
        for index, tag in enumerate(TAGS):
            original = next(a for a in old["actions"] if a["tag"] == tag)
            if original["action"] != menu[index]["action"]:
                raise ValueError("ORIGINAL_CONFIG_NOT_EXACT_MENU")
            recipe = copy.deepcopy(menu[index])
            if index:
                recipe["action"]["terminal_timing_applicability"] = True
            new_tag = tag if not index else tag + "_APPLICABILITY"
            old_result = "attempts/" + old_group + "_" + tag + "_RESULT.json"
            pin(old_result)
            rows.append({"original_tag": tag, "tag": new_tag, "old_recipe_sha256": digest(menu[index]), "recipe_sha256": digest(recipe), "full_recipe": recipe, "original_result_reference_only": {"path": old_result, "sha256": dependencies[old_result]}, "original_label_not_valid_for_new_recipe": bool(index)})
            actions.append({"tag": new_tag, "action": copy.deepcopy(recipe["action"]), "category": BRANCH})
        catalogs[new_group] = {"schema": "v8.postapp.fixed_changed_recipe_catalog.v1", "scope": BRANCH, "rows": rows, "model_labels_or_choices_transferred": False}
        keep = ["B", "H150", "arms", "condition", "case_path", "case_sha256", "continuation_policy", "short_horizons_s", "fork_phase", "fork_slot"]
        config = {k: copy.deepcopy(old[k]) for k in keep if k in old}
        config.update(group=new_group, worker="v8_worker_v2.py", algorithm="v8_postapp_fixed_v2", actions=actions, mode="engineering", scientific_branch=BRANCH, historical_repeats={}, job_wall_cap_s=1800, local_stop_unix=runtime["local_stop_unix"])
        config["condition"].update(name=new_group, split="EXPOSED_POSTVALIDATION_DEVELOPMENT", role="固定接口能力诊断；与原validation同两参数条件，非额外独立验证", scope=BRANCH)
        config["postvalidation_applicability_probe"] = {"runtime_approval": {"path": approval_rel, "sha256": dependencies[approval_rel]}, "original_group": old_group, "original_B_result": {"path": original_B_rel, "sha256": dependencies[original_B_rel]}}
        configs[new_group] = config
    # All checks above precede creation. This builder writes no root config/approval/job.
    output.mkdir(parents=True, exist_ok=False)
    def new(name, value):
        with (output / name).open("x") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    for group in GROUPS:
        new(group + "_RECIPES.json", catalogs[group])
        rel = str((output / (group + "_RECIPES.json")).relative_to(package))
        dependencies[rel] = sha(output / (group + "_RECIPES.json"))
    for group, config in configs.items():
        rel = str((output / (group + "_RECIPES.json")).relative_to(package))
        config["postvalidation_applicability_probe"]["recipe_catalog"] = {"path": rel, "sha256": dependencies[rel]}
        config["frozen_artifacts"] = copy.deepcopy(dependencies)
        new(group + ".json", config)
    new("PREPARED_METADATA.json", {"status": "PREPARED_OWNED_PROPOSALS_NOT_ROOT_JOB_OR_PHYSICS_AUTHORITY", "mandatory_closed": closure, "config_sha256": {g: sha(output / (g + ".json")) for g in GROUPS}, "metadata_approval_sha256": sha(args.metadata_approval), "runtime_approval_sha256": sha(args.runtime_approval), "new_model_map_RNG_fit_scorer_raw_physics_calls": 0, "root_must_copy_config_bytes_then_prepare_and_approve_owned_physics": True})


if __name__ == "__main__":
    main()
