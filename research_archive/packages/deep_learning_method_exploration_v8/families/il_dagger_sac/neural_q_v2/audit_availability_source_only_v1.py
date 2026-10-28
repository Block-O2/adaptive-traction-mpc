"""Source-only JSON availability audit. Zero learner imports or calls."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import os
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
SAC = "families/il_dagger_sac/discrete_sac_v1/"
A3 = "families/critic_value/coverage_state_v3/"
DATA = SAC + "data/offpolicy_first_completed_v5/SAC_OFFPOLICY_DATASET_V5.json"
DATA_SHA = "b8a2b12479f25112a8cdfc720a6ad0f56f24467cd4c143425c675f814812c39d"
MANIFEST = SAC + "data/offpolicy_first_completed_v5/SAC_OFFPOLICY_DATASET_MANIFEST_V5.json"
MANIFEST_SHA = "78544e67744a5eb3c384dd3f3042382c0a2bb2c4a9ac2a7755475546bd77803e"
EXTRA14 = ["estimated_q_hip", "estimated_q_knee", "estimated_dq_hip", "estimated_dq_knee",
           "request_reference_q_hip", "request_reference_q_knee", "request_reference_dq_hip", "request_reference_dq_knee"]
EXTRA14 += ["measured_force_world_" + x for x in ["x", "y", "z"]]
EXTRA14 += ["measured_moment_world_" + x for x in ["x", "y", "z"]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def main():
    start = time.time(); cpu = time.process_time()
    out = HERE / "AVAILABILITY_SOURCE_ONLY_V1.json"
    assert not out.exists(), "PRESERVE_SOURCE_ONLY_AUDIT_NO_OVERWRITE"
    identities = {}
    def read(relative):
        path = PACKAGE / relative
        identities[relative] = sha(path)
        return json.loads(path.read_text())
    dataset = read(DATA); read(MANIFEST)
    assert identities[DATA] == DATA_SHA and identities[MANIFEST] == MANIFEST_SHA
    rows = dataset["cohorts"]["AGGREGATE64"]
    assert len(rows) == 64 and len(dataset["feature_names"]) == 25
    assert [digest(x) for x in dataset["action_contracts"]] == dataset["full_recipe_sha256"]
    joined = read(A3 + "data/STATE_JOINED_DATASET_V1.json")
    scoped = read(A3 + "data/SCOPED_OUT0_STATES_V1.json")
    profiles = joined["input_source_profiles"]
    historic = {}
    for row in joined["rows"]:
        context = row["context"]
        raw = context["raw_payload"]
        values = dict(zip(raw["feature_names"], raw["features"]))
        numeric = digest({"names": dataset["feature_names"], "values": [values[n] for n in dataset["feature_names"]]})
        previous = historic.get(numeric)
        candidate = {"raw": raw, "proof": context["source_proof"], "group": row["group"]}
        if previous is not None:
            assert digest(previous["raw"]) == digest(raw)
        historic[numeric] = candidate
    old_history = read("families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json")
    old_numeric = {digest({"names": row["context"]["feature_names"], "values": row["context"]["features"]})
                   for row in old_history["rows"]}
    by_case = {}
    for row in rows:
        assert row["qa_validated"] is True and row["feature_names"] == dataset["feature_names"]
        assert all(finite(x) for x in row["features"])
        assert digest({"names": row["feature_names"], "values": row["features"]}) == row["causal_features_sha256"]
        assert row["done"] is True and row["next_state"] is None and row["complete"] is True
        assert row["original_evidence"]["hard_safety"] is False and row["original_evidence"]["ownership_PASS"] is True
        assert row["failure"] == float(not row["original_qualified"])
        target = max(-.9, min(.9, (row["baseline"]["JF_N_s"] - row["JF_N_s"]) / max(row["baseline"]["JF_N_s"], 1.))) if row["original_qualified"] else -1.
        assert target == row["canonical_terminal_return"]
        case = row["split_case_sha256_evaluation_only"]
        if case not in by_case:
            numeric = row["causal_features_sha256"]
            if numeric in historic:
                state = historic[numeric]
                raw, proof = state["raw"], state["proof"]
                group = state["group"]
                payload_source = "FROZEN_A3_JOINED_RAW_PAYLOAD"
            else:
                group = row["attempt_id"].split("_OP_")[0]
                assert group in ("V8OP01HR1", "V8OP01L2"), "ONLY_FIRST_COMPLETED_FROZEN_DEV_JOBS"
                done = read("jobs/" + group + "/WORKER_DONE.json")
                supervisor = read("owned/" + group + "_SUPERVISOR_END.json")
                assert done["status"] == "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS"
                assert supervisor["state"] == "STOP" and supervisor["worker_exit_code"] == 0 and not supervisor["survivors"]
                payload_source = "history/" + group + "_PREFORK_CAUSAL_CONTEXT.json"
                raw = read(payload_source)
                source = read("jobs/" + group + "/SOURCE_MANIFEST.json")
                path_profile = next(p for p in joined["input_source_profile_paths"] if p["callback"] == "source/v8_worker_v1.py")
                proof = {key: source["files"][path] for key, path in path_profile.items()}
            values = dict(zip(raw["feature_names"], raw["features"]))
            body = {k: v for k, v in raw.items() if k != "causal_payload_sha256"}
            checks = {"checksum": digest(body) == raw["causal_payload_sha256"],
                "OUT0_before_selection": raw["task_s"] == 0. and raw["phase"] == "OUTBOUND" and
                    raw["capture_position"] == "parent request boundary BEFORE fork loop/candidate selection/control mutation",
                "no_future_or_observe": raw["hidden_or_future_inputs_used"] is False and raw["model_prediction_or_observe_calls"] == 0,
                "legacy77_invalid_preserved": raw["model_vector_valid"] is False,
                "QA_current": raw["quality_missing"] == {} and raw["quality"]["observation_age"] == raw["quality"]["interface_age"] == 0.,
                "request_current": values["decision_slot"] == 0 and values["request_source_age"] == 0.,
                "expected_registration_error_only": raw["causality_errors"] == ["capture_is_not_registered_OUT1_boundary"],
                "source_profile_already_reviewed": proof in profiles,
                "same_25D_as_original_SAC_row": [values[n] for n in dataset["feature_names"]] == row["features"],
                "all_extra14_finite": all(finite(values.get(n)) for n in EXTRA14)}
            by_case[case] = {"case_sha256_evaluation_only": case, "group_evaluation_only": group,
                "causal25_sha256": numeric, "features25": row["features"],
                "extra14": {name: values.get(name) for name in EXTRA14}, "extra14_available": all(checks.values()),
                "availability_checks": checks, "source_profile": proof, "source_payload_body_sha256": raw["causal_payload_sha256"],
                "payload_source": payload_source, "old_BC_training_context_preexposed": numeric in old_numeric}
        else:
            assert by_case[case]["causal25_sha256"] == row["causal_features_sha256"]
    assert len(by_case) == 12 and len({r["parent_fingerprint_evaluation_only"] for r in rows}) == 12
    cases = sorted(by_case)
    folds = [{"fold": "LEAVE_CASE_" + case, "held_case_sha256": case,
              "train_indices": [i for i, row in enumerate(rows) if row["split_case_sha256_evaluation_only"] != case],
              "held_indices": [i for i, row in enumerate(rows) if row["split_case_sha256_evaluation_only"] == case]}
             for case in cases]
    profiles_used = {digest(x["source_profile"]): x["source_profile"] for x in by_case.values()}
    report = {"schema": "v8.neural_q_v2.source_only_availability.v1", "status": "METADATA_ONLY_NO_LEARNER_CALLS",
        "source_data_path": DATA, "source_data_sha256": DATA_SHA, "source_data_manifest_sha256": MANIFEST_SHA,
        "data_source_files_sha256": identities, "row_count": 64, "distinct_case_count": 12,
        "distinct_context_action_cells": len({r["same_context_action_key_evaluation_only"] for r in rows}),
        "qualified": sum(r["original_qualified"] for r in rows), "complete_original_failure": sum(not r["original_qualified"] for r in rows),
        "action_counts": dict(Counter(r["action_index"] for r in rows)), "missing_action_labels_not_imputed": True,
        "feature_names25": dataset["feature_names"], "feature_names39_if_separately_approved": dataset["feature_names"] + EXTRA14,
        "all_12_case_extra14_source_valid": all(c["extra14_available"] for c in by_case.values()),
        "39D_training_authorized": False, "primary_representation": "COMMISSION25",
        "cases": by_case, "case_folds": folds, "source_profiles_used": list(profiles_used.values()),
        "old_BC_prior_context_exposure_count": sum(c["old_BC_training_context_preexposed"] for c in by_case.values()),
        "all_development_already_exposed_not_independent_test": True,
        "source_record_sha256_by_index": [digest(r) for r in rows], "pid": os.getpid(), "start_unix": start,
        "end_unix": time.time(), "wall_s": time.time()-start, "cpu_self_s": time.process_time()-cpu,
        "model_initializations": 0, "model_fit_forward_gradient": 0, "normalizer_fits": 0,
        "physics_or_new_raw_streams": 0, "active_L2_H2_or_sealed_read": False}
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "data_sha256": DATA_SHA, "12_case_39D_available": report["all_12_case_extra14_source_valid"],
        "old_BC_preexposed": report["old_BC_prior_context_exposure_count"], "wall_s": report["wall_s"], "model_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
