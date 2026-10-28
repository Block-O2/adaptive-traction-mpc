"""Frozen existing-case selection and evaluation identity, with no model imports.

Candidate only: the main agent must register and review it before deployment.
Call install(sc, C, P, sha, put) once in a fresh, single-case worker process.
It composes case identity with the original execution-mode metadata repair.
It changes loader/evaluation bindings, never plant/scorer/mode_metadata code.
"""
from __future__ import annotations

import ast
import copy
import datetime
import difflib
import hashlib
import inspect
import importlib
import sys
import json
import os
from pathlib import Path
import re
import textwrap


SCHEMA = "ihear.v7.existing_case_adapter.candidate.v2"
STAGE = "runtime/source/stages/stage5_personalized_motion_learning/"
CASE_PREFIX = STAGE + "configs/high_rom_v1/"
CASE_HASHES = {'high_rom_nominal_sync_120_v1': 'd9f4d636b98db5792cf4b50915f4509bf2274c1c80764d6d8629bf22e3ae9b96', 'high_rom_matrix_light_soft_sync_v1': 'ab98dfc8c68363750b865fe455fdb77b9b579434a7b2df34fd382d0d38fb9d0e', 'high_rom_matrix_heavy_stiff_sync_v1': '44387b2b48a4d486d4fa5f7b980e698a3546365eea95bad2b1c2c50620342ccf', 'high_rom_matrix_short_segments_sync_v1': '01a7c9ef5c88f17e5206b25b2a0c8b42b85a5e8346c65b18c276b82cd65c15fa', 'high_rom_v7_heavy_soft_sync_cf1': '86830ef586eb7629f39d84c29bf3b56bc0a5c8d524f122a9d500b19314fe0547', 'high_rom_v7_light_stiff_sync_cf1': '60b5e70eedce0387402d947ca76aeb956344b6676b0ec1377d82b2f91b0b4eff', 'high_rom_matrix_long_segments_sync_v1': '16e81a1cb87efe52b1133c169fd55e546c6e77664ff56298c8a01e3be19d95a4', 'high_rom_matrix_mixed_sync_v1': 'b595f0d5f4746ba341009e204753bbbbd06a0de9c4e767ae6287799a4cebf98f', 'high_rom_matrix_up2_xplus_sync_v1': '4b77e610067c9cdbb37e6eb66f280dda80fa310ac5b19c71cfd5f44bfa33272c', 'high_rom_matrix_up4_xminus_sync_v1': '319437a18cb0eef07279e8f5b09007a2d957a60781eac99d18f11158ad60b995', 'high_rom_v8_dev_heavy035': '305b90192d653a234f2375e23d99ee98fe9ed9030239a05c767a8133d90164e9', 'high_rom_v8_dev_light065': 'cf2b735402009a7a15f6b8aff01c759579c4cfb93ac0301cc0f18803407d1ece', 'high_rom_v8_val_heavy065': 'cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c', 'high_rom_v8_val_light035': '224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87'}
NOMINAL_KEY = "high_rom_nominal_sync_120_v1"
OPTIONS_REL = STAGE + "configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json"
OPTIONS_SHA256 = "d11bb72950f9f74e451548f57ff509e89f92e10aa18f8c62f78bd7a4b7f4c6bb"
TASK_REL = CASE_PREFIX + "stage5_goal_task_120_v1.json"
TASK_SHA256 = "40b445813ec7df9d5db3b95b31a338f5d158058cdbd62449e330af949585f986"
SCORING_REL = STAGE + "docs/high_rom_v1/PHASE_B_MATRIX.json"
SCORING_SHA256 = "b95e84f28353024a248920681d46b4d1e26d1aa71c95b50dfa19b344858d1e97"
QUALIFY_REL = STAGE + "scripts/single_human_sac_expert_v1/qualify.py"
LOADER_REL = STAGE + "scripts/single_human_sac_expert_v1/sac_env.py"
EVALUATOR_REL = STAGE + "scripts/high_rom_v1/evaluate_execution_mode.py"
SCORER_REL = STAGE + "scripts/high_rom_v1/summarize_phase_b.py"
MODE_METADATA_REL = "runtime/code/mode_metadata.py"
MODE_METADATA_SHA256 = "b59b68d9a00e8bc113ff8d264c652ba32729742a7c611c0ed4422b32d223e297"
RUNTIME_REL = STAGE + "src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py"
PATH_ANCHOR = "case_path=S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'"
PATH_REPLACEMENT = "case_path=REGISTERED_CASE_PATH"
MODE_ANCHOR = "execution_mode='SCIENTIFIC_SIMULATION'"
MODE_REPLACEMENT = "execution_mode=env.summary['execution_mode']"
SYNC_CANDIDATES = frozenset(("high_rom_sync_feedback_v1", "synchronous_diagnostic_only_feedback_replanning_active"))


def _require(condition, reason):
    if not condition:
        raise RuntimeError("CASE_ADAPTER:" + reason)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def process_identity():
    """Read Linux process identity; never create a background process."""
    stat = Path("/proc/self/stat").read_text()
    parts = stat[stat.rindex(")") + 2:].split()
    return {"pid": os.getpid(), "ppid": os.getppid(), "start_ticks": int(parts[19])}


def _frozen_json(root, relative, expected_hash):
    path = root / relative
    _require(path.resolve() == path, "SYMLINK_OR_NONCANONICAL_FROZEN_PATH:" + relative)
    _require(path.is_file() and _sha(path) == expected_hash, "FROZEN_FILE_IDENTITY:" + relative)
    return json.loads(path.read_text())


def _validate(root, config):
    root = Path(root).resolve()
    allowed = {CASE_PREFIX + key + ".json": key for key in CASE_HASHES}
    relative = config.get("case_path")
    _require(relative in allowed, "CASE_PATH_NOT_WHITELISTED")
    key = allowed[relative]
    expected = CASE_HASHES[key]
    _require(config.get("case_sha256") == expected, "EXPLICIT_FROZEN_CASE_HASH_REQUIRED")
    _require(config.get("case_key", key) == key, "CONFIG_CASE_KEY_MISMATCH")
    cases = {name: _frozen_json(root, CASE_PREFIX + name + ".json", digest) for name, digest in CASE_HASHES.items()}
    nominal = cases[NOMINAL_KEY]
    for name, value in cases.items():
        _require(value["case_key"] == name, "FILE_CASE_KEY_MISMATCH")
        _require(value["task"] == nominal["task"], "TASK_OR_COMMISSIONING_CHANGED")
        _require(value.get("research_model") == "high_rom_v1", "RESEARCH_MODEL_CHANGED")
        _require(value.get("coordination_candidate") in SYNC_CANDIDATES, "CONTROLLER_DIRECTIONS_NOT_SYNC")
    task = _frozen_json(root, TASK_REL, TASK_SHA256)
    scoring = _frozen_json(root, SCORING_REL, SCORING_SHA256)
    options = _frozen_json(root, OPTIONS_REL, OPTIONS_SHA256)
    _require(nominal["task"]["start_deg"] == [5.0, 10.0] and nominal["task"]["goal_deg"] == [120.0, 120.0], "TASK_ENDPOINT_IDENTITY")
    _require(task["hold_duration_s"] == 0.5 and task["phase_timeout_s"] == 10.0, "HOLD_OR_DEADLINE_CHANGED")
    # Confirm both candidate names still enter the same original code branch.
    tree = ast.parse((root / RUNTIME_REL).read_text())
    matching = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        test = node.test
        if not (isinstance(test.left, ast.Name) and test.left.id == "candidate_mode" and len(test.ops) == 1 and isinstance(test.ops[0], ast.In)):
            continue
        try:
            values = ast.literal_eval(test.comparators[0])
        except (ValueError, TypeError):
            continue
        if isinstance(values, tuple) and SYNC_CANDIDATES.issubset(values):
            _require(len(node.body) == 1 and isinstance(node.body[0], ast.Assign), "SYNC_BRANCH_STRUCTURE_CHANGED")
            assignment = node.body[0]
            _require([ast.unparse(target) for target in assignment.targets] == ["directions"], "SYNC_BRANCH_TARGET_CHANGED")
            _require(ast.unparse(assignment.value) == "HumanWaypointFeedbackMPCConfigV1().normalized_coordination_directions", "SYNC_BRANCH_VALUE_CHANGED")
            matching.append(ast.unparse(node.test))
    _require(len(matching) == 1, "SYNC_BRANCH_NOT_UNIQUE")
    case = cases[key]
    descriptor = {"case_key": key, "physical_variant": case["cell"]["family"], "candidate": case["coordination_candidate"], "path": str((root / relative).relative_to(root / "runtime/source")), "sha256": expected}
    return {"root": root, "relative": relative, "path": root / relative, "case": case, "nominal": nominal, "options": options, "descriptor": descriptor, "task": task, "scoring": scoring["scoring"], "direction_branch": matching[0]}


def descriptor(P, C):
    """Return original-scorer case metadata only, with no hidden parameters."""
    return copy.deepcopy(_validate(P, C)["descriptor"])


def scorer_inputs(P, C):
    """Inputs for unmodified evaluate_execution_mode.evaluate, no execution."""
    binding = _validate(P, C)
    return {"case": copy.deepcopy(binding["descriptor"]), "goal_deg": copy.deepcopy(binding["case"]["task"]["goal_deg"]), "start_deg": copy.deepcopy(binding["case"]["task"]["start_deg"])}


def _derive_audit(original, case_path):
    source = textwrap.dedent(inspect.getsource(original))
    _require(source.count(PATH_ANCHOR) == 1, "AUDIT_PATH_ANCHOR_NOT_UNIQUE")
    _require(source.count(MODE_ANCHOR) == 1, "AUDIT_MODE_ANCHOR_NOT_UNIQUE")
    tree = ast.parse(source)
    _require(len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef) and tree.body[0].name == "physical_audit", "UNEXPECTED_AUDIT_SOURCE")
    changed = source.replace(PATH_ANCHOR, PATH_REPLACEMENT).replace(MODE_ANCHOR, MODE_REPLACEMENT)
    before = ast.parse(source)
    after = ast.parse(changed)
    assignments = [n for n in ast.walk(before) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "case_path" for t in n.targets)]
    changed_assignments = [n for n in ast.walk(after) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "case_path" for t in n.targets)]
    _require(len(assignments) == len(changed_assignments) == 1, "CASE_PATH_ASSIGNMENT_NOT_UNIQUE")
    assignments[0].value = ast.Name(id="REGISTERED_CASE_PATH", ctx=ast.Load())
    mode_values = [n for n in ast.walk(before) if isinstance(n, ast.keyword) and n.arg == "execution_mode" and isinstance(n.value, ast.Constant) and n.value.value == "SCIENTIFIC_SIMULATION"]
    _require(len(mode_values) == 1, "AUDIT_METADATA_MODE_KEYWORD_NOT_UNIQUE")
    mode_values[0].value = ast.parse("env.summary['execution_mode']", mode="eval").body
    _require(ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False), "AUDIT_CHANGE_EXCEEDS_TWO_METADATA_RHS")
    namespace = dict(original.__globals__, REGISTERED_CASE_PATH=case_path)
    exec(compile(changed, "<v7 physical_audit: frozen case path and actual execution mode>", "exec"), namespace)
    diff = "".join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile="original_physical_audit", tofile="case_bound_physical_audit"))
    return namespace["physical_audit"], {"before_source": source, "after_source": changed, "before_sha256": hashlib.sha256(source.encode()).hexdigest(), "after_sha256": hashlib.sha256(changed.encode()).hexdigest(), "unified_diff": diff, "ast_only_changes": ["physical_audit.case_path assignment RHS", "HIGH_ROM_CASE_RESULT.execution_mode keyword RHS"]}


def _cold_run_contract(run):
    """Read the already loaded harness function's AST, never call it."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(run)))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run_executed_case"]
    _require(len(calls) == 1, "HARNESS_RUNTIME_CALL_NOT_UNIQUE")
    keywords = {item.arg: item.value for item in calls[0].keywords if item.arg is not None}
    session = keywords.get("session_context")
    empty = lambda node: isinstance(node, ast.Dict) and not node.keys
    _require(empty(session) or isinstance(session, ast.IfExp) and empty(session.body) and isinstance(session.orelse, ast.Constant) and session.orelse.value is None, "HARNESS_MAY_RESUME_OLD_HUMAN")
    for key, expected in [("qualification_arm", "commissioning_only"), ("formal_qualification", False), ("task_timeout_s", 30.0)]:
        value = keywords.get(key)
        _require(isinstance(value, ast.Constant) and value.value == expected, "HARNESS_CONTRACT_CHANGED:" + key)
    return {key: ast.unparse(keywords[key]) for key in ["session_context", "qualification_arm", "formal_qualification", "task_timeout_s"]}


def install(sc, C, P, sha, put):
    """Install once, before a fresh cold sc.run, without model/scorer execution.

    C must explicitly contain case_path/case_sha256/group. P is the isolated
    v7 package. sha and put are the worker's existing identity/output helpers.
    All writes use put under audit/case_adapter/<group>/; source is untouched.
    """
    root = Path(P).resolve()
    _require(not getattr(sc, "_v7_existing_case_adapter", None), "ALREADY_INSTALLED")
    group = C.get("group", "")
    _require(isinstance(group, str) and re.fullmatch(r"[A-Za-z0-9_]{1,120}", group) is not None, "INVALID_GROUP_ID")
    binding = _validate(root, C)
    _require(_sha(root / MODE_METADATA_REL) == MODE_METADATA_SHA256, "ORIGINAL_MODE_METADATA_SOURCE_CHANGED")
    mode_metadata = importlib.import_module("mode_metadata")
    _require(Path(mode_metadata.__file__).resolve() == root / MODE_METADATA_REL, "MODE_METADATA_ROOT_NOT_ISOLATED")
    _require(mode_metadata.INSTALLED_AUDIT is None, "MODE_METADATA_ALREADY_HAS_OWNER")
    _require(Path(sc.STUDY).resolve() == root / "runtime", "STUDY_ROOT_NOT_ISOLATED")
    cold_run_contract = _cold_run_contract(sc.run)
    old_loader = sc.load_case_options
    _require(Path(inspect.getsourcefile(old_loader)).resolve() == root / LOADER_REL, "LOADER_NOT_ORIGINAL_ISOLATED_FUNCTION")
    _require(old_loader.__name__ == "load_case_options", "LOADER_ALREADY_REPLACED")
    # This original loader reads two JSON files only; no plant/model creation.
    old_case, old_options = old_loader()
    _require(old_case == binding["nominal"], "ORIGINAL_LOADER_NOT_NOMINAL")
    _require(old_options == binding["options"], "ORIGINAL_OPTIONS_DIFFER")
    metric_globals = sc.r2.BASE_METRIC.__globals__
    original_audit = metric_globals.get("physical_audit")
    _require(callable(original_audit), "BASE_METRIC_AUDIT_BINDING_MISSING")
    _require(Path(inspect.getsourcefile(original_audit)).resolve() == root / QUALIFY_REL, "AUDIT_NOT_ORIGINAL_ISOLATED_FUNCTION")
    audit_globals = original_audit.__globals__
    _require(audit_globals.get("physical_audit") is original_audit, "QUALIFY_AUDIT_ALREADY_REBOUND")
    _require(getattr(sys.modules.get("qualify"), "__dict__", None) is audit_globals, "QUALIFY_MODULE_OWNER_MISMATCH")
    _require(getattr(sys.modules.get("final_qualification"), "__dict__", None) is metric_globals, "FINAL_QUALIFICATION_MODULE_OWNER_MISMATCH")
    derived, source_audit = _derive_audit(original_audit, binding["path"])
    protected = {str(path.relative_to(root)): _sha(path) for path in [root / QUALIFY_REL, root / LOADER_REL, root / EVALUATOR_REL, root / SCORER_REL, root / RUNTIME_REL, root / OPTIONS_REL, root / TASK_REL, root / SCORING_REL, root / MODE_METADATA_REL]}
    _require(all(sha(root / relative) == digest for relative, digest in protected.items()), "CALLER_SHA_DISAGREEMENT")
    selected_case = copy.deepcopy(binding["case"])
    selected_options = copy.deepcopy(binding["options"])
    config_identity = _digest(C)

    def recheck():
        _require(mode_metadata.INSTALLED_AUDIT is physical_audit, "MODE_METADATA_OWNER_CHANGED")
        _require(metric_globals.get("physical_audit") is physical_audit and audit_globals.get("physical_audit") is physical_audit, "AUDIT_ALIAS_OWNER_CHANGED")
        _require(sc.load_case_options is load_case_options, "CASE_LOADER_OWNER_CHANGED")
        _require(_digest(C) == config_identity, "MUTABLE_CONFIG_CHANGED")
        _require(_sha(binding["path"]) == binding["descriptor"]["sha256"], "SELECTED_CASE_FILE_CHANGED")
        for relative, digest in protected.items():
            _require(_sha(root / relative) == digest, "PROTECTED_SOURCE_CHANGED:" + relative)

    def load_case_options():
        recheck()
        return copy.deepcopy(selected_case), copy.deepcopy(selected_options)

    def physical_audit(env):
        recheck()
        _require(env.case == selected_case, "ENV_CASE_MISMATCH")
        _require(env.options == selected_options, "ENV_OPTIONS_MISMATCH")
        summary = env.summary
        qualification = summary.get("qualification", {})
        _require(qualification.get("hidden_case_evaluation_only") == selected_case, "SUMMARY_HIDDEN_CASE_MISMATCH")
        _require(qualification.get("case_key") == selected_case["case_key"], "SUMMARY_CASE_KEY_MISMATCH")
        _require(qualification.get("arm") == "commissioning_only", "COMMISSIONING_ARM_CHANGED")
        _require(summary.get("execution_mode") == "SCIENTIFIC_SIMULATION", "EXECUTION_MODE_CHANGED")
        episode = Path(env.episode_dir).resolve()
        _require(episode.parent == root / "runtime/source/results", "EPISODE_NOT_IN_ISOLATED_RESULTS")
        persisted_summary = episode / "summary.json"
        _require(persisted_summary.is_file(), "PERSISTED_SUMMARY_MISSING")
        persisted = json.loads(persisted_summary.read_text())
        _require(persisted.get("qualification", {}).get("hidden_case_evaluation_only") == selected_case, "PERSISTED_HIDDEN_CASE_MISMATCH")
        launch_path = episode / "HIGH_ROM_CASE_RESULT.json"
        cache_used = not (episode / "runtime_artifacts.json").exists() and (episode / "runtime_artifacts.json.gz").exists() and (episode / "SAC_PHYSICAL_AUDIT.json").exists()
        if cache_used:
            _require(launch_path.is_file() and json.loads(launch_path.read_text()).get("case_sha256") == binding["descriptor"]["sha256"], "CACHED_AUDIT_CASE_IDENTITY_MISMATCH")
        result = derived(env)
        _require(launch_path.is_file() and json.loads(launch_path.read_text()).get("case_sha256") == binding["descriptor"]["sha256"], "SCORER_LAUNCH_CASE_IDENTITY_MISMATCH")
        raw = result.get("unchanged_evaluator", {}).get("raw_scorer_v2", {})
        for field, expected in [("case_key", selected_case["case_key"]), ("physical_variant", binding["descriptor"]["physical_variant"]), ("candidate", binding["descriptor"]["candidate"]), ("registered_case_sha256", binding["descriptor"]["sha256"]), ("case_hash_valid", True)]:
            _require(raw.get(field) == expected, "RETURNED_OR_CACHED_SCORER_IDENTITY_MISMATCH:" + field)
        put("audit/case_adapter/" + group + "/" + episode.name + ".json", {"schema": SCHEMA, "status": "IDENTITY_BOUND_ORIGINAL_AUDIT_RETURNED", "process": process_identity(), "case_descriptor": copy.deepcopy(binding["descriptor"]), "options_sha256": OPTIONS_SHA256, "hidden_case_canonical_sha256": _digest(selected_case), "persisted_summary_sha256": _sha(persisted_summary), "launch_sha256": _sha(launch_path), "cached_audit_used": cache_used, "original_audit_pass": result.get("pass_"), "actor_hidden_parameters_added": False})
        return result

    metadata = {"schema": SCHEMA, "status": "INSTALLED_EVALUATION_IDENTITY_ONLY", "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "process": process_identity(), "group": group, "config_canonical_sha256": config_identity, "case_descriptor": copy.deepcopy(binding["descriptor"]), "package_case_path": binding["relative"], "options_sha256": OPTIONS_SHA256, "task_sha256": TASK_SHA256, "scoring_sha256": SCORING_SHA256, "controller_direction_branch": binding["direction_branch"], "physical_audit_derivation": source_audit, "mode_metadata_composition": {"source_relative_path": MODE_METADATA_REL, "original_source_sha256": MODE_METADATA_SHA256, "original_install_function_unchanged": True, "future_install_route": "original INSTALLED_AUDIT owner-check fast path", "final_owner_bindings": ["qualify.physical_audit", "final_qualification.physical_audit", "campaign_r2.BASE_METRIC.__globals__[physical_audit]", "mode_metadata.INSTALLED_AUDIT"]}, "protected_file_sha256": protected, "adapter_source_sha256": _sha(__file__), "cold_start_contract": cold_run_contract, "cold_start_required": True, "session_context_required": "new empty dict; never an existing updater/plant", "actor_hidden_parameters_added": False, "model_or_scorer_calls_during_install": 0, "physical_starts_during_install": 0, "qualification_inherited": False}
    put("audit/case_adapter/" + group + "/INSTALL.json", metadata)
    # These are the actual aliases used by campaign_r2.BASE_METRIC and qualify.
    sc.load_case_options = load_case_options
    metric_globals["physical_audit"] = physical_audit
    audit_globals["physical_audit"] = physical_audit
    mode_metadata.INSTALLED_AUDIT = physical_audit
    sc._v7_existing_case_adapter = copy.deepcopy(metadata)
    return copy.deepcopy(metadata)
