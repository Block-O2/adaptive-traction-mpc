"""Prepare a new fixed-policy interface probe; never dispatch physics.

The two changed recipes are not the five original learned-model actions.
Original failures and labels stay unchanged. No model is queried or trained.
"""
from pathlib import Path
import copy
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def new(relative, value):
    with (P / relative).open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main():
    activation = load("ACTIVATION.json")
    assert activation["hard_stop_unix"] == 1793114740.0
    assert time.time() < activation["hard_stop_unix"] - 3600
    old = load("experiments/V8COMPENG03.json")
    assert old["case_sha256"] == "44387b2b48a4d486d4fa5f7b980e698a3546365eea95bad2b1c2c50620342ccf"
    assert sha(P / "source/v8_worker_v2.py") == "c425ce6609b3a845b8a0427d01bc51bb16cbf0554d1464790e4a98f9fdfb7dfe"
    menu = {row["tag"]: row for row in old["actions"]}
    actions = [copy.deepcopy(menu["B"]), copy.deepcopy(menu["EARLY_H150"])]
    actions[1]["tag"] = "H150"
    changes = []
    for tag in ("LATE_PHASE", "EARLY_PHASE"):
        failed = load("attempts/V8COMPENG03_" + tag + "_RESULT.json")
        assert failed["complete"] is False
        assert failed["protected_task_failure"]["abort_reason"] == "NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT"
        assert all(failed["protected_task_failure"]["hard_safety_conditions"].values())
        row = copy.deepcopy(menu[tag])
        before = copy.deepcopy(row["action"])
        row["tag"] = tag + "_APPLICABILITY"
        row["action"]["terminal_timing_applicability"] = True
        assert {k: v for k, v in row["action"].items() if k != "terminal_timing_applicability"} == before
        changes.append({"old_tag": tag, "new_tag": row["tag"], "old_action_sha256": digest(before),
                        "new_action_sha256": digest(row["action"]),
                        "original_failed_result_sha256": sha(P / ("attempts/V8COMPENG03_" + tag + "_RESULT.json"))})
        actions.append(row)
    for row in actions:
        row["category"] = "FIXED_PHASE_CAUSAL_APPLICABILITY_IMPLEMENTATION_PROBE"
        row.pop("prediction", None)
    deps = {}
    core = load("runtime/EXECUTION_CODE_MANIFEST.json")
    for relative, expected in core["files"].items():
        rel = "runtime/" + relative
        assert sha(P / rel) == expected
        deps[rel] = expected
    for relative in ["ACTIVATION.json", "runtime/RUN_PLAN.json", "runtime/EXECUTION_CODE_MANIFEST.json",
                     "source/v8_worker_v2.py", "source/v8_case_adapter_v2.py", "source/acl2_shared.py",
                     "source/acl2_modal_planner.py", "source/acl2_modal_retimed.py", "runtime/FROZEN_18D.json",
                     "runtime/PARAMETER_MAP.json", "runtime/ACTION_SET.json", "runtime/MOTION_ACCEPTANCE_PROTOCOL.json",
                     "experiments/V8COMPENG03.json", str(Path(__file__).relative_to(P))]:
        actual = sha(P / relative)
        assert relative not in deps or deps[relative] == actual
        deps[relative] = actual
    group = "V8PHAPP01"
    approval = "freeze/PHASE_APPLICABILITY_PROBE_MAIN_APPROVAL_V1.json"
    new(approval, {"status": "APPROVED_BY_MAIN_AGENT_FIXED_INTERFACE_PROBE_ONLY", "created_unix": time.time(),
        "activation_id": activation["activation_id"], "original_global_stop_unix": activation["hard_stop_unix"],
        "group": group, "scope": "Known-heavy exposed condition only; no independent generalization claim",
        "motivation": "Both original modal8 phase recipes fail an original optional terminal-timing knee-reference assertion. Test the already implemented causal applicability gate without changing original task/scorer/assertion.",
        "only_recipe_change": "At RETURN slot5, existing worker checks current issued-reference knee position/velocity against public goal at original1e-10 tolerances; omit optional timing request if inapplicable. Original planner, guards and evaluator unchanged.",
        "recipe_changes": changes, "required_order": [row["tag"] for row in actions],
        "task_failure_and_partial_costs_must_remain": True,
        "original_five_model_menu_not_modified_or_relabelled": True,
        "learned_policy_model_calls": 0, "new_fit": 0,
        "old_Q_values_not_validated_for_new_recipe": True,
        "qualification_required_before_task_gain": True,
        "B_and_H150_full_raw_cross_job_identity_required": True,
        "same_start_prefix_identity_required_before_causal_attribution": True,
        "original_11_hard_conditions_required": True,
        "job_wall_cap_s": 1800, "each_physical_timeout_s": 600,
        "physics_serial": True, "dependencies": deps})
    deps[approval] = sha(P / approval)
    config = copy.deepcopy(old)
    for key in ["comparative_validation", "frozen_selectors", "holdout_protocol", "holdout_protocol_sha256"]:
        config.pop(key, None)
    config.update(group=group, algorithm=None, actions=actions, frozen_artifacts=deps,
                  scientific_branch="FIXED_PHASE_CAUSAL_APPLICABILITY_MECHANISM_PROBE",
                  mode="engineering", historical_repeats={}, job_wall_cap_s=1800)
    config["condition"]["name"] = group
    config["condition"]["scope"] = "Exposed exact known-heavy; distinct fixed repaired recipes, not original model action labels or validation."
    new("experiments/" + group + ".json", config)
    print(json.dumps({"status": "PREPARED_NO_PHYSICS_NO_MODEL_CALLS", "group": group,
                      "config_sha256": sha(P / ("experiments/" + group + ".json")),
                      "approval_sha256": sha(P / approval)}))


if __name__ == "__main__":
    main()
