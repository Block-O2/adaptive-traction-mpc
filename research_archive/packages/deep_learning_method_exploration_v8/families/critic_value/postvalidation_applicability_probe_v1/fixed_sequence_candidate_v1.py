"""SOURCE_ONLY：已暴露两条件固定applicability诊断，无学习/映射/随机策略。

未来运行须主审另批。原worker/阈值/任务/评分器均不变；原模型结果不转移到新recipe。
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import marshal
import os
import sys
import time
import types

HERE = "families/critic_value/postvalidation_applicability_probe_v1/"
STOP = 1793114740.0
WORKER_SHA = "c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe"
COMPARE = "runtime/control/base_campaign.py"
COMPARE_SHA = "98cfe2df845a41dac272aaa71cc0d7ffffd84c0ec9b59ed97c1ae24270b64ad6"
BRANCH = "EXPOSED_POSTVALIDATION_IMPLEMENTATION_CAPABILITY_DIAGNOSTIC_NOT_GENERALIZATION"
MANDATORY = ["V8VAL03", "V8VAL04", "V8FMEAN03", "V8FMEAN04", "V8CONVAL01", "V8CONVAL02"]
ORIGINAL = ["B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]
ORDER = ["B"] + [t + "_APPLICABILITY" for t in ORIGINAL[1:]]
CASES = {"V8POSTAPP01": ("V8VAL03", "cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c", 2026102753), "V8POSTAPP02": ("V8VAL04", "224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87", 2026102754)}
HARD = ["force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed", "session_clearance", "true_clearance", "measured_sleeve_clearance", "no_shank_table_contact", "no_human_rom_violation"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bounded(package, relative):
    path = (package / relative).resolve()
    if not path.is_relative_to(package):
        raise ValueError("POSTAPP_PATH_ESCAPE")
    return path


def load(package, relative):
    return json.loads(bounded(package, relative).read_text())


def closed_identity(identity):
    try:
        tail = (Path("/proc") / str(identity["pid"]) / "stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return True
    return int(tail[19]) != identity["start_ticks"]


def require_closed(package, group):
    begin = load(package, "owned/" + group + "_SUPERVISOR.json")
    end = load(package, "owned/" + group + "_SUPERVISOR_END.json")
    if end.get("state") != "STOP" or end.get("survivors") != []:
        raise ValueError("MANDATORY_FROZEN_JOB_NOT_CLOSED:" + group)
    for identity in list(end["known_owned"].values()) + [begin["identity"], begin["worker"]]:
        if not closed_identity(identity):
            raise ValueError("ORIGINAL_OWNED_PID_STILL_LIVE:" + group)
    return {"group": group, "begin_sha256": sha(package / "owned" / (group + "_SUPERVISOR.json")), "end_sha256": sha(package / "owned" / (group + "_SUPERVISOR_END.json")), "worker_exit_code": end.get("worker_exit_code")}


def joined_evidence(package, config, study, tag):
    ident = config["group"] + "_" + tag
    row = copy.deepcopy(study.last_row)
    if row.get("id") != ident or getattr(study, "active_owned_child_pid", None) is not None:
        raise ValueError("POSTAPP_ONLY_EXACT_JOINED_CURRENT_CHILD")
    rel = "attempts/" + ident + "_RESULT.json"
    original = load(package, rel)
    for key in ("id", "complete", "qualified", "error", "actual_new_native_steps", "action"):
        if original.get(key) != row.get(key):
            raise ValueError("POSTAPP_ORIGINAL_RESULT_DIFFERS:" + key)
    events = {}
    needle = ('"' + ident + '"').encode()
    with (package / "runtime/ATTEMPTS.jsonl").open("rb") as stream:
        for raw in stream:
            if needle not in raw:
                continue
            event = json.loads(raw)
            if event.get("id") != ident or event.get("event") not in ("START", "END"):
                continue
            if event["event"] in events:
                raise ValueError("POSTAPP_DUPLICATE_ORIGINAL_EVENT")
            events[event["event"]] = {"record": event, "raw_line_sha256": hashlib.sha256(raw.rstrip(b"\n")).hexdigest()}
    if set(events) != {"START", "END"} or events["END"]["record"].get("joined") is not True or events["END"]["record"].get("parent_hash_equal") is not True:
        raise ValueError("POSTAPP_JOIN_OR_PARENT_PREFIX_UNKNOWN")
    if events["START"]["record"].get("config_sha256") != sha(package / "experiments" / (config["group"] + ".json")) or events["START"]["record"].get("job_source_sha256") != sha(package / "jobs" / config["group"] / "SOURCE_MANIFEST.json"):
        raise ValueError("POSTAPP_ACTUAL_START_SOURCE_IDENTITY")
    source = row["metrics_path"] if row.get("complete") is True else rel
    if row.get("complete") is True:
        metric = load(package, source)
        common = metric.get("native_physical_audit", {}).get("unchanged_evaluator", {}).get("physical_task_result", {}).get("scorer_v2_common_conditions", {})
    else:
        common = row.get("protected_task_failure", {}).get("hard_safety_conditions", {})
    conditions = {key: common.get(key) for key in HARD}
    hard = True if row.get("true_hard_safety_violation") is True or any(v is False for v in conditions.values()) else False if all(v is True for v in conditions.values()) else None
    return {"tag": tag, "original_row": row, "original_result": {"path": rel, "sha256": sha(package / rel)}, "original_events": events, "safety_source": {"path": source, "sha256": sha(package / source)}, "hard_conditions": conditions, "true_hard_safety_violation": hard, "complete": row.get("complete"), "qualified": row.get("qualified"), "partial_cost_NOT_RANKED": row.get("complete") is not True}


def loaded_compare_proof(package, job):
    """验证实际loaded原函数code，不由模块同名属性推定；不exec函数/模块。"""
    module = sys.modules.get("base_campaign")
    if module is None or Path(module.__file__).resolve() != package / COMPARE:
        raise ValueError("POSTAPP_ORIGINAL_BASE_MODULE_NOT_ACTUALLY_LOADED")
    if sha(package / COMPARE) != COMPARE_SHA or job["files"].get(COMPARE) != COMPARE_SHA:
        raise ValueError("POSTAPP_ORIGINAL_COMPARE_SOURCE_NOT_JOB_PINNED")
    function = module.compare_raw
    tree = ast.parse((package / COMPARE).read_text(), filename=str(package / COMPARE))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "compare_raw")
    compiled = compile(ast.Module(body=[node], type_ignores=[]), str(package / COMPARE), "exec", dont_inherit=True, optimize=sys.flags.optimize)
    expected = next(c for c in compiled.co_consts if isinstance(c, types.CodeType) and c.co_name == "compare_raw")
    actual_code = hashlib.sha256(marshal.dumps(function.__code__)).hexdigest()
    expected_code = hashlib.sha256(marshal.dumps(expected)).hexdigest()
    if function.__globals__ is not module.__dict__ or Path(function.__code__.co_filename).resolve() != package / COMPARE or actual_code != expected_code:
        raise ValueError("POSTAPP_ACTUAL_COMPARE_CODE_NOT_PINNED_ORIGINAL_BODY")
    helper = function.__globals__["array_items"]
    helper_path = Path(helper.__code__.co_filename).resolve()
    if not helper_path.is_relative_to(package) or sha(helper_path) != job["files"].get(str(helper_path.relative_to(package))):
        raise ValueError("POSTAPP_ORIGINAL_STREAM_HELPER_NOT_JOB_PINNED")
    return function, {"actual_loaded_module": str(Path(module.__file__).resolve()), "actual_module_source_sha256": sha(package / COMPARE), "actual_function_code_sha256": actual_code, "expected_pinned_AST_function_code_sha256": expected_code, "actual_function_globals_is_original_module": True, "helper_actual_code_file": str(helper_path), "helper_source_sha256": sha(helper_path), "AST_compile_only_no_exec": 1}


def sequence(study, config):
    owner_pid = os.getpid()
    package = Path(os.environ["ACL2_PACKAGE"]).resolve()
    group = config["group"]
    from acl2_shared import put
    pending = None
    completed = {}
    stopped = None
    counts = {"physical_proposals_yielded": 0, "original_compare_raw_entered": 0, "original_compare_raw_returned": 0, "source_AST_compile_only_checks": 0, "model_initialize_restore_forward_score_fit_RNG_map": 0, "new_scorer_or_direct_physics_calls": 0}
    def owner():
        if os.getpid() != owner_pid:
            raise GeneratorExit("POSTAPP_FORK_CHILD_NO_OWNER_WRITE")
    def save(name, value):
        owner()
        put("analysis/" + group + "_POSTAPP_" + name + ".json", value)
    def frozen():
        owner()
        for rel, h in config["frozen_artifacts"].items():
            if sha(bounded(package, rel)) != h:
                raise ValueError("POSTAPP_FROZEN_DEPENDENCY_CHANGED:" + rel)
    def record(tag):
        owner()
        value = joined_evidence(package, config, study, tag)
        completed[tag] = value
        save("BRANCH_" + tag, value)
        if value["true_hard_safety_violation"] is True:
            raise RuntimeError("POSTAPP_TRUE_HARD_STOP_ALL_REST")
        if value["true_hard_safety_violation"] is not False:
            raise RuntimeError("POSTAPP_UNKNOWN_HARD_STOP_ALL_REST")
        return value
    try:
        if study.child is not None or study.fork_done is not True or study.metrics or config.get("fork_phase") != "OUTBOUND" or config.get("fork_slot") != 0:
            raise ValueError("POSTAPP_ONLY_ORIGINAL_COLD_OUT0_BEFORE_CANDIDATES")
        frozen()
        spec = config["postvalidation_applicability_probe"]
        approval = load(package, spec["runtime_approval"]["path"])
        if sha(package / spec["runtime_approval"]["path"]) != spec["runtime_approval"]["sha256"] or approval.get("status") != "MAIN_APPROVED_EXPOSED_POSTVALIDATION_FIXED_APPLICABILITY_V1" or group not in approval["authorized_groups"] or approval.get("new_model_fit_scorer_calls") != 0 or approval.get("original_raw_compare_per_case") != 1:
            raise ValueError("POSTAPP_EXACT_NEW_MAIN_AUTHORITY_REQUIRED")
        if config.get("scientific_branch") != BRANCH or config.get("onpolicy_sampling") or config.get("worker") != "v8_worker_v2.py" or sha(package / "source/v8_worker_v2.py") != WORKER_SHA:
            raise ValueError("POSTAPP_FIXED_ONLY_ORIGINAL_WORKER_REQUIRED")
        if group not in CASES or (config["case_sha256"], config["condition"]["seed"]) != CASES[group][1:] or approval.get("global_stop_unix") != STOP:
            raise ValueError("POSTAPP_EXACT_ALREADY_EXPOSED_CASE_AND_CLOCK")
        closure = [require_closed(package, g) for g in MANDATORY]
        baseline_group = CASES[group][0]
        old = load(package, "experiments/" + baseline_group + ".json")
        if any(config[k] != old[k] for k in ("case_path", "case_sha256", "B", "H150", "fork_phase", "fork_slot")) or config["condition"]["prefix"] != old["condition"]["prefix"]:
            raise ValueError("POSTAPP_ORIGINAL_CASE_PREFIX_BASE_CHANGED")
        job = load(package, "jobs/" + group + "/SOURCE_MANIFEST.json")
        manifest_path = HERE + "SOURCE_MANIFEST_V1.json"
        manifest = load(package, manifest_path)
        if approval.get("source_manifest") != {"path": manifest_path, "sha256": sha(package / manifest_path)} or config["frozen_artifacts"].get(manifest_path) != sha(package / manifest_path):
            raise ValueError("POSTAPP_MAIN_APPROVED_EXACT_SOURCE_MANIFEST_REQUIRED")
        for rel, h in manifest["source_files_sha256"].items():
            if config["frozen_artifacts"].get(rel) != job["files"].get(rel) or job["files"].get(rel) != h or sha(package / rel) != h:
                raise ValueError("POSTAPP_ACTUAL_JOB_SOURCE_CLOSURE:" + rel)
        if Path(__file__).resolve() != package / HERE / "fixed_sequence_candidate_v1.py":
            raise ValueError("POSTAPP_ACTUAL_LOADED_SEQUENCE_PATH")
        supervisor = load(package, "owned/" + group + "_SUPERVISOR.json")
        config_sha = sha(package / "experiments" / (group + ".json"))
        if job["config_sha256"] != supervisor["config_sha256"]:
            raise ValueError("POSTAPP_JOB_SUPERVISOR_CONFIG_DIFFERS")
        if job["config_sha256"] != config_sha or supervisor["worker"]["pid"] != owner_pid or closed_identity(supervisor["worker"]):
            raise ValueError("POSTAPP_CURRENT_OWNER_CONFIG_REQUIRED")
        catalog = load(package, spec["recipe_catalog"]["path"])
        if sha(package / spec["recipe_catalog"]["path"]) != spec["recipe_catalog"]["sha256"] or [a["tag"] for a in config["actions"]] != ORDER or len(catalog["rows"]) != 5:
            raise ValueError("POSTAPP_EXACT_FIXED_RECIPE_ORDER")
        menu = load(package, "freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json")["action_contracts"]
        for index, (action, item) in enumerate(zip(config["actions"], catalog["rows"])):
            recipe = copy.deepcopy(menu[index])
            if index:
                recipe["action"]["terminal_timing_applicability"] = True
            if item["full_recipe"] != recipe or item["recipe_sha256"] != digest(recipe) or action["action"] != recipe["action"]:
                raise ValueError("POSTAPP_ONLY_ONE_CAUSAL_FLAG_MAY_CHANGE_RECIPE")
        plan = load(package, "runtime/RUN_PLAN.json")
        if plan["physical_timeout_s"] != 600 or config["local_stop_unix"] != approval["local_stop_unix"] or config["job_wall_cap_s"] != 1800:
            raise ValueError("POSTAPP_ORIGINAL_CHILD_CAP_AND_ONE_FROZEN_LOCAL_CLOCK")
        stop = min(config["local_stop_unix"], supervisor["cutoff_unix"], plan["physics_hard_stop_unix"], STOP)
        save("FIXED_BEFORE_B", {"owner_pid": owner_pid, "catalog": catalog, "counts": counts, "mandatory_closed": closure, "source_job_sha256": sha(package / "jobs" / group / "SOURCE_MANIFEST.json"), "supervisor_sha256": sha(package / "owned" / (group + "_SUPERVISOR.json")), "local_stop_from_existing_clocks": stop, "not_model_choices": True})
        for action in config["actions"]:
            frozen()
            if time.time() >= min(stop, plan["dispatch_cutoff_unix"]) - plan["physical_timeout_s"]:
                stopped = "ORIGINAL_CHILD_START_TIME_RESERVE_NOT_MET"
                break
            pending = action["tag"]
            index = ORDER.index(pending)
            counts["physical_proposals_yielded"] += 1
            yield {"tag": pending, "action": copy.deepcopy(action["action"]), "category": BRANCH, "prediction": {"fixed_not_learned": True, "full_recipe_sha256": catalog["rows"][index]["recipe_sha256"], "original_model_labels_not_transferred": True}}
            receipt = record(pending)
            tag = pending
            pending = None
            if tag == "B":
                if receipt["complete"] is not True or receipt["qualified"] is not True:
                    stopped = "OWN_B_NOT_COMPLETE_QUALIFIED_ALL_NONB_NOT_RUN"
                    break
                compare, proof = loaded_compare_proof(package, job)
                counts["source_AST_compile_only_checks"] += 1
                oldjob = load(package, "jobs/" + baseline_group + "/SOURCE_MANIFEST.json")
                if oldjob["files"].get(COMPARE) != COMPARE_SHA:
                    raise ValueError("POSTAPP_OLD_B_COMPARE_SOURCE_DIFFERENT")
                before = {"actual_loaded_compare_proof": proof, "old_config_sha256": sha(package / "experiments" / (baseline_group + ".json")), "new_config_sha256": config_sha, "old_job_source_sha256": sha(package / "jobs" / baseline_group / "SOURCE_MANIFEST.json"), "new_job_source_sha256": sha(package / "jobs" / group / "SOURCE_MANIFEST.json"), "case_sha256": config["case_sha256"], "seed": config["condition"]["seed"], "prefix": config["condition"]["prefix"], "original_B_result": spec["original_B_result"], "new_B_result": receipt["original_result"]}
                counts["original_compare_raw_entered"] += 1
                save("B_RAW_COMPARE_ENTERED", {"counts": dict(counts), **before})
                raw = compare(package / "runtime/source/results" / (baseline_group + "_B"), package / "runtime/source/results" / (group + "_B"))
                counts["original_compare_raw_returned"] += 1
                save("B_RAW_GATE", {"original_compare_result": raw, "counts": dict(counts), **before})
                if raw.get("status") != "PASS":
                    stopped = "ORIGINAL_B_CROSS_JOB_RAW_DIFF_ALL_NONB_NOT_RUN"
                    break
            if receipt["complete"] is not True:
                stopped = "PARTIAL_STOP_REMAINING_NOT_RUN"
                break
            # 完整但motion不合格仍保留并继续；从不改qualification或按JF挑recipe。
        save("FINAL", {"status": BRANCH, "completed": completed, "NOT_RUN": [t for t in ORDER if t not in completed], "stop": stopped, "counts": counts, "root_raw_scorer_owner_and_actual_cost_close_required": True, "all_families_NOT_FULLY_EXPLORED": True})
    except GeneratorExit:
        if os.getpid() != owner_pid:
            return
        last = None
        if pending and getattr(study, "last_row", {}).get("id") == group + "_" + pending:
            try:
                last = joined_evidence(package, config, study, pending)
            except BaseException as error:
                last = {"UNKNOWN_original_evidence": True, "error_type": type(error).__name__, "error": str(error)}
        save("OWNER_CLOSE", {"pending": pending, "completed": completed, "last_original_evidence": last, "counts": counts, "no_success_imputation": True})
        return
    except BaseException as error:
        if os.getpid() != owner_pid:
            return
        save("ERROR", {"error_type": type(error).__name__, "error": str(error), "pending": pending, "completed": completed, "NOT_RUN": [t for t in ORDER if t not in completed], "counts": counts, "unreturned_compare_work_UNKNOWN_not_zero": counts["original_compare_raw_entered"] != counts["original_compare_raw_returned"]})
        raise
