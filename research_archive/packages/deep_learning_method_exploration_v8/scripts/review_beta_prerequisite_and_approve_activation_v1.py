"""Root review of actual closed raw/scorer evidence; no actor or physics."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
AUDIT = "families/history_conditioned/audit/V8COMPENG03_BETA_PREREQUISITE_V1/RESULT.json"
AUDIT_SHA = "b2f06106b0f66ff149d8ff47aa179a4806ae597bd9b365c95731c7cfa20bcf88"
DRIVER = "scripts/activate_reviewed_beta_branch_v2.py"
DRIVER_SHA = "eb9a85c07527596718dbac68c2c55825bfe4591ce4be357179d619c37f66b2e0"
HARD = {"force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed",
        "session_clearance", "true_clearance", "measured_sleeve_clearance",
        "no_shank_table_contact", "no_human_rom_violation"}


def sha(relative):
    h = hashlib.sha256()
    with (P / relative).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 2**20), b""):
            h.update(block)
    return h.hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def new(relative, value):
    with (P / relative).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    assert sha(AUDIT) == AUDIT_SHA and sha(DRIVER) == DRIVER_SHA
    data = load(AUDIT)
    assert data["status"] == "PASS_CLOSED_SOURCE_CAUSAL_HARD_DATA_WITH_TWO_PHASE_PARTIAL"
    assert data["errors"] == [] and data["closure"]["errors"] == []
    assert data["pre_B_decision_count"] == 55 and data["all_expected_pre_B_selectors_bound_before_B"] is True
    assert data["original_scorer_replays"] == 7 and len(data["trials"]) == 7
    assert data["all_seven_original_hard11_true"] is True and data["true_hard_safety_violation"] is False
    assert data["all_five_core_complete"] is False and data["all_five_complete_PASS_claim"] is False
    assert all(row["errors"] == [] for row in data["source_proof_audits"])
    assert len(data["C_actual_loaded_module_proofs"]) == 3
    assert all(row["actual_loaded_and_both_freezes_match"] is True for row in data["C_actual_loaded_module_proofs"])
    assert all(row["status"] == "PASS" for row in data["raw_equivalence"])
    group = "V8COMPENG03"
    assert data["group"] == group
    hard_rows = {}
    sources = {AUDIT: AUDIT_SHA, **data["source_files_sha256"], **data["closure"]["metadata_files_sha256"]}
    for row in data["trials"]:
        assert row["errors"] == [] and set(row["hard11"]) == HARD
        assert all(value is True for value in row["hard11"].values())
        assert row["source_files_sha256"]
        hard_rows[row["id"]] = {"hard_safety_conditions": row["hard11"],
            "true_hard_safety_violation": False, "original_evidence_files_sha256": row["source_files_sha256"]}
        sources.update(row["source_files_sha256"])
    assert set(hard_rows) == set(data["closure"]["ids"])
    controls = {}
    partials = {}
    for tag in ["B", "HISTORY_B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]:
        rel = "attempts/" + group + "_" + tag + "_RESULT.json"
        original = load(rel)
        sources[rel] = sha(rel)
        ref = {"path": rel, "sha256": sources[rel]}
        audited = next(row for row in data["trials"] if row["id"] == original["id"])
        if "PHASE" in tag:
            assert original["complete"] is False and original["qualified"] is False
            assert audited["complete"] is False and audited["full_qualified"] is False
            assert original["protected_task_failure"]["abort_reason"] == "NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT"
            partials[tag] = {"complete": False, "error": original["error"],
                "actual_new_native_steps": original["actual_new_native_steps"], "original_result": ref}
        else:
            assert original["complete"] is True and original["qualified"] is True
            assert audited["complete"] is True and audited["full_qualified"] is True
            controls[tag] = {"complete": True, "qualified": True, "original_result": ref}
    for relative, expected in sources.items():
        assert sha(relative) == expected, relative
    axis_review = "audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json"
    axis = load(axis_review)
    assert axis["mean_lambda05_full_original_qualified"] is True and axis["true_hard_safety_violation"] is False
    assert sha(axis_review) == "c17a601051a275cdc4327f63e0aa027f50608d3ee409dbca8573f3cd435f761a"
    review_rel = "audit/BETA_AXIS_PREREQUISITE_MAIN_REVIEW_V1.json"
    new(review_rel, {"schema": "v8.beta_axis_prerequisite_main_review.v1",
        "status": "PASS_BETA_AXIS_PREREQUISITE_WITH_ORIGINAL_FIVE_MENU_PARTIALS_PRESERVED",
        "reviewed_unix": time.time(), "group": group, "pre_B_decision_count": 55,
        "all55_pre_B_decisions_valid": True, "generic_five_menu_complete": False,
        "all_actual_job_owners_closed": True, "true_hard_safety_violation": False,
        "beta_axis_action_permission_unchanged": True, "continuous_lambda_domain": [0., 1.],
        "original_evidence_files_sha256": sources, "original_B_H_controls": controls,
        "phase_partials_preserved": partials, "original_hard_safety_by_attempt": hard_rows,
        "axis_gate1_review": {"path": axis_review, "sha256": sha(axis_review)},
        "main_reason": "Independent Beta old18 axis has its own exact mapping and qualified mean .5. Generic modal8 phase partials remain failures and cannot become Beta successes. Original11 conditions are true, deriving violation=false; no task threshold or axis restriction changed.",
        "new_model_or_physics_calls": 0})
    template = "families/ppo_reward/continuous_scale_v1/ACTIVATION_V2_MAIN_SOURCE_APPROVAL_BETA_PREREQUISITE_TEMPLATE_REVIEW_ONLY.json"
    approval = load(template)
    assert sha(template) == "6987aadf2140490b6f58b6052eeada7176fb08dd1dafc6859f9fff1bb257bdb3"
    for relative, expected in approval["direct_source_files_sha256"].items():
        assert sha(relative) == expected, relative
    for table in approval["reviewed_manifest_tables"]:
        assert sha(table["path"]) == table["sha256"]
        for relative, expected in load(table["path"])[table["mapping_key"]].items():
            assert sha(table["path_prefix"] + relative) == expected
    approval.update(status="APPROVED_BY_MAIN_FOR_ONE_ACTUAL_BETA_ACTIVATION",
        actual_activation_authorized=True, all_prior_hard_safety_reviewed_no_true=True,
        register_once_7200s_after_all_prior_closed=True, approved_unix=time.time(),
        beta_prerequisite_review={"path": review_rel, "sha256": sha(review_rel)},
        review_notice="Root read final V2 source, pinned durable/helper independent reviews and seven actual original-scorer replays. Authorize one bounded durable init, then each balanced physics batch separately. No automatic dispatch or clock reset.")
    out = "freeze/BETA_ACTIVATION_MAIN_SOURCE_APPROVAL_V2.json"
    new(out, approval)
    print(json.dumps({"status": "ROOT_REVIEW_APPROVAL_ONLY_NO_ACTOR_OR_PHYSICS",
                      "prerequisite": {"path": review_rel, "sha256": sha(review_rel)},
                      "main_source_approval": {"path": out, "sha256": sha(out)}}))


if __name__ == "__main__":
    main()
