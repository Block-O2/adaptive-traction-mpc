"""Source-only Gate1 V2: only original fork-parent may write shared evidence.

No environment, model, sampler or physical launch occurs on import. Root must
review the config and install its own source/ wrapper before any physical use.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time


def _load(path):
    return json.loads(Path(path).read_text())


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 2**20), b""):
            h.update(block)
    return h.hexdigest()


def _path(package, relative):
    if not isinstance(relative, str):
        raise ValueError("GATE1_PATH_NOT_STRING")
    path = (package / relative).resolve()
    if not path.is_relative_to(package):
        raise ValueError("GATE1_PATH_ESCAPES_PACKAGE")
    return path


def sequence(study, config):
    """B -> original H150 -> lambda1 exact repeat -> lambda0 -> lambda.5.

    All branches use the worker's single live OUT0 parent and independent full
    child continuations. The worker's original repeat_of gate runs before this
    generator resumes; we also require its saved PASS before later lambdas.
    """
    owner_pid = os.getpid()
    owner_start_ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    from acl2_shared import put as original_put
    def assert_owner():
        if os.getpid() != owner_pid:
            raise GeneratorExit("FORK_CHILD_HAS_NO_SHARED_GENERATOR_WRITE_AUTHORITY")
    def put(relative, payload):
        assert_owner()
        original_put(relative, payload)
    package = Path(os.environ["ACL2_PACKAGE"]).resolve()
    here = package / "families/ppo_reward/continuous_scale_v1"
    sys.path.insert(0, str(here))
    from axis_mapping import digest, map_lambda, validate_axis

    if study.metrics or config.get("fork_phase") != "OUTBOUND" or config.get("fork_slot") != 0:
        raise ValueError("FRESH_SINGLE_LIVE_OUT0_PARENT_REQUIRED")
    spec = config["continuous_axis_gate1"]
    if spec.get("schema") != "v8.continuous_axis_gate1_job.v1" or spec.get("exposed_engineering_condition") != "knownheavy":
        raise ValueError("REGISTERED_EXPOSED_KNOWNHEAVY_ENGINEERING_JOB_ONLY")
    if spec.get("independent_generalization_test") is not False:
        raise ValueError("GATE1_IS_EXPOSED_ENGINEERING_NOT_GENERALIZATION")
    frozen = config["frozen_artifacts"]

    def required(relative, expected=None):
        if relative not in frozen or (expected is not None and frozen[relative] != expected):
            raise ValueError("GATE1_DEPENDENCY_NOT_FROZEN:" + relative)
        return _path(package, relative)

    def verify():
        for relative, expected in frozen.items():
            if _sha(_path(package, relative)) != expected:
                raise ValueError("GATE1_FROZEN_FILE_CHANGED:" + relative)

    for relative in ("families/ppo_reward/continuous_scale_v1/gate1_sequence_candidate_v2.py",
                     "families/ppo_reward/continuous_scale_v1/GATE1_OWNER_WRITE_AUTHORITY_V2.md",
                     "families/ppo_reward/continuous_scale_v1/axis_mapping.py",
                     "source/v8_worker_v1.py", "runtime/code/analyze_matched.py",
                     "runtime/code/stream_runtime_evidence.py", "source/acl2_shared.py"):
        required(relative)
    required(spec["approved_contract_path"], spec["approved_contract_sha256"])
    axis_path = required(spec["axis_path"], spec["axis_file_sha256"])
    verify()
    axis = _load(axis_path)
    validate_axis(axis, spec["axis_object_sha256"])
    for relative, expected in axis["source_files_sha256"].items():
        required(relative, expected)
    for name in ("B", "H150"):
        original = next(x for x in _load(package / "runtime/ACTION_SET.json")["arms"] if x["id"] == name)
        if config[name] != original:
            raise ValueError("GATE1_ORIGINAL_CANDIDATE_CHANGED:" + name)
    if config["H150"] != axis["h150_candidate"]:
        raise ValueError("GATE1_AXIS_H150_TEMPLATE_CHANGED")
    mapped = {label: map_lambda(axis, value, expected_axis_sha256=spec["axis_object_sha256"])
              for label, value in (("AXIS_L1", 1.0), ("AXIS_L0", 0.0), ("AXIS_L05", .5))}
    for label, entry in mapped.items():
        candidate = copy.deepcopy(config["H150"])
        candidate.update(entry["proposal_action"]["candidate_overrides"])
        candidate.pop("id", None)
        if candidate != entry["full_recipe"]["resolved_base_candidate"]:
            raise ValueError("ACTUAL_WORKER_CANDIDATE_BINDING:" + label)
    output_relative = spec["output_directory"]
    output = _path(package, output_relative)
    if not output.is_relative_to(here) or output.exists():
        raise ValueError("GATE1_FRESH_CONTINUOUS_FAMILY_OUTPUT_REQUIRED")
    assert_owner()
    output.mkdir(parents=True)
    captures = []

    def save_status(status, **extra):
        put(output_relative + "/GATE1_STATUS.json", {
            "schema": "v8.continuous_axis_gate1_progress.v1", "status": status,
            "group": config["group"], "created_unix": time.time(),
            "owner_pid": owner_pid, "owner_start_ticks": owner_start_ticks,
            "fork_child_GeneratorExit_never_writes_shared_files": True,
            "axis_object_sha256": spec["axis_object_sha256"],
            "rows": captures, "real_training_updates": 0,
            "same_recipe_attempts_are_new_physical_work": True,
            "parent_prefix_accounted_once_by_worker_parent": True,
            "parent_prefix_steps_not_multiplied_by_child_count": True,
            "root_must_close_parent_DONE_and_all_START_END": True,
            "lambda_zero_is_original_B": False,
            "independent_generalization_test": False, **extra})

    def capture(tag, action):
        assert_owner()
        row = copy.deepcopy(study.last_row)
        ident = config["group"] + "_" + tag
        if row.get("id") != ident or row.get("action") != action:
            raise ValueError("GATE1_ORIGINAL_WORKER_RESULT_IDENTITY")
        result_path = package / "attempts" / (ident + "_RESULT.json")
        if not result_path.is_file() or _load(result_path) != row:
            raise ValueError("GATE1_SAVED_ORIGINAL_RESULT_IDENTITY")
        files = {"attempts/" + ident + "_RESULT.json": _sha(result_path)}
        # Preserve source paths and complete original payloads. No synthesized
        # activation/receipt/fallback or guessed child-owner semantics appear.
        source = package / "runtime/source/results" / ident
        for path in (source / "trace.npz", source / "runtime_artifacts.json.gz", source / "summary.json",
                     package / "runtime/output" / (ident + "_DATA.json"),
                     package / "runtime/output" / (ident + "_PARTIAL_COMPUTE.json"),
                     package / "attempts" / (ident + "_EXECUTION_BINDING.json")):
            if path.is_file():
                files[str(path.relative_to(package))] = _sha(path)
        measured = None
        lineage = None
        if row.get("complete") is True:
            report_path = _path(package, row["metrics_path"])
            measured = _load(report_path)
            lineage_path = Path(measured["execution_lineage_path"]).resolve()
            if not lineage_path.is_relative_to(package):
                raise ValueError("GATE1_ORIGINAL_LINEAGE_OUTSIDE_PACKAGE")
            lineage = _load(lineage_path)
            files[str(report_path.relative_to(package))] = _sha(report_path)
            files[str(lineage_path.relative_to(package))] = _sha(lineage_path)
            if lineage.get("status") != "PASS" or measured["axes"]["SCIENTIFIC_EXECUTION_CAUSAL_VALID"] != "PASS":
                raise ValueError("GATE1_ORIGINAL_EXECUTION_RECEIPT_AUDIT_FAILED")
        summary = _load(source / "summary.json") if (source / "summary.json").is_file() else None
        bundle = {"tag": tag, "original_worker_result": row,
                  "original_measured_report": measured, "original_execution_lineage": lineage,
                  "original_learning_records": summary.get("learning_records") if summary else None,
                  "original_decisions": summary.get("decisions") if summary else None,
                  "source_files_sha256": files, "actual_new_native_steps_this_child": row.get("actual_new_native_steps"),
                  "qualification_copied_from_original_worker": row.get("qualified"),
                  "JF_full_only": row.get("JF") if row.get("complete") else None,
                  "JM_full_only": row.get("JM") if row.get("complete") else None,
                  "rejections_fallback_and_activation_preserved_in_original_payloads": True,
                  "partial_costs_not_success_ranked": True, "lambda_zero_is_original_B": False}
        put(output_relative + "/" + tag + "_ORIGINAL_EVIDENCE.json", bundle)
        captures.append(bundle)
        save_status("ORIGINAL_EVIDENCE_SAVED:" + tag)
        return row

    save_status("READY_BEFORE_B")
    try:
        for tag, action in (("B", {"family": "B"}),
                            ("H150", {"family": "H150", "legacy": [0.0, 0.0]})):
            assert_owner()
            verify()
            yield {"tag": tag, "action": copy.deepcopy(action), "category": "CONTINUOUS_AXIS_GATE1_ENGINEERING",
                   "prediction": {"role": "ORIGINAL_" + tag, "training_sample": False}}
            row = capture(tag, action)
            if row.get("complete") is not True or row.get("qualified") is not True:
                raise ValueError("ORIGINAL_FULL_QUALIFICATION_REQUIRED:" + tag)
        entry = mapped["AXIS_L1"]
        assert_owner()
        verify()
        yield {"tag": "AXIS_L1", "action": copy.deepcopy(entry["proposal_action"]),
               "repeat_of": "H150", "category": "CONTINUOUS_AXIS_GATE1_EXACT_RAW_EQUIVALENCE",
               "prediction": {"lambda": 1.0, "full_recipe_sha256": entry["full_recipe_sha256"],
                              "required_original_repeat_of": "H150", "training_sample": False}}
        row = capture("AXIS_L1", entry["proposal_action"])
        raw_path = package / "audit" / (config["group"] + "_AXIS_L1_REPEAT_GATE.json")
        raw_gate = _load(raw_path)
        if row.get("complete") is not True or row.get("qualified") is not True or raw_gate.get("status") != "PASS":
            raise ValueError("LAMBDA1_MUST_BE_ORIGINAL_H150_FULL_QUALIFIED_AND_EXACT_RAW_EQUAL")
        if Path(raw_gate["a"]).resolve() != package / "runtime/source/results" / (config["group"] + "_H150") or Path(raw_gate["b"]).resolve() != package / "runtime/source/results" / (config["group"] + "_AXIS_L1"):
            raise ValueError("WRONG_RAW_COMPARISON_PAIR")
        put(output_relative + "/LAMBDA1_ORIGINAL_H150_EXACT_RAW_GATE.json", {"original_raw_gate": raw_gate,
            "original_raw_gate_path": str(raw_path.relative_to(package)), "original_raw_gate_sha256": _sha(raw_path)})
        for tag in ("AXIS_L0", "AXIS_L05"):
            assert_owner()
            verify()
            entry = mapped[tag]
            yield {"tag": tag, "action": copy.deepcopy(entry["proposal_action"]),
                   "category": "CONTINUOUS_AXIS_GATE1_ENGINEERING",
                   "prediction": {"lambda": entry["lambda"], "full_recipe_sha256": entry["full_recipe_sha256"],
                                  "lambda1_exact_raw_gate_sha256": _sha(raw_path),
                                  "lambda_zero_is_original_B": False, "training_sample": False}}
            capture(tag, entry["proposal_action"])
        save_status("CHILD_SEQUENCE_COMPLETE_ROOT_PARENT_CLOSURE_REQUIRED",
                    motion_qualification_and_costs_must_be_assessed_separately=True)
    except GeneratorExit:
        if os.getpid() != owner_pid:
            return
        save_status("OWNER_GENERATOR_CLOSED_PRESERVE_ALREADY_CAPTURED_EVIDENCE",
                    root_must_reconcile_ANY_started_child_not_captured=True)
        return
    except BaseException as error:
        if os.getpid() != owner_pid:
            return
        save_status("STOPPED_PRESERVE_ALL_ORIGINAL_EVIDENCE", error_type=type(error).__name__, error=str(error),
                    root_must_reconcile_ANY_started_child_not_captured=True)
        raise
