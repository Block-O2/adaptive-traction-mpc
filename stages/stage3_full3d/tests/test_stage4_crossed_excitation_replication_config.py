from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


STAGE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = STAGE_ROOT / "configs" / "stage4_crossed_excitation_replication.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_selected_levels_exist_in_frozen_source_configs() -> None:
    config = _load(CONFIG_PATH)
    patient_source = config["source_contracts"]["patient_config"]
    trajectory_source = config["source_contracts"]["trajectory_config"]
    audit_source = config["source_contracts"]["offline_excitation_audit"]

    patient_path = STAGE_ROOT / patient_source["path"]
    trajectory_path = STAGE_ROOT / trajectory_source["path"]
    audit_path = STAGE_ROOT / audit_source["path"]
    assert _sha256(patient_path) == patient_source["sha256"]
    assert _sha256(trajectory_path) == trajectory_source["sha256"]
    assert _sha256(audit_path) == audit_source["sha256"]

    patient_ids = {case["case_id"] for case in _load(patient_path)["cases"]}
    trajectory_cases = {
        case["trajectory_id"]: case for case in _load(trajectory_path)["cases"]
    }
    for level in config["patient_levels"]:
        assert level["patient_id"] in patient_ids
    for level in config["trajectory_levels"]:
        source = trajectory_cases[level["trajectory_id"]]
        assert source["duration_s"] == level["duration_s"] == 23.0


def test_fraction_is_balanced_and_matches_preregistered_rule() -> None:
    config = _load(CONFIG_PATH)
    cases = config["cases"]
    patient_index = {x["patient_id"]: x["index"] for x in config["patient_levels"]}
    trajectory_index = {
        x["trajectory_id"]: x["index"] for x in config["trajectory_levels"]
    }
    seed_index = {
        x["measurement_seed"]: x["index"] for x in config["measurement_seed_levels"]
    }
    block_offset = {"offset_1": 1, "offset_2": 2}

    assert len(cases) == 18
    assert len({case["case_id"] for case in cases}) == 18
    for case in cases:
        expected = (
            patient_index[case["patient_id"]]
            + trajectory_index[case["trajectory_id"]]
            + block_offset[case["block"]]
        ) % 3
        assert seed_index[case["measurement_seed"]] == expected

    assert set(Counter(x["patient_id"] for x in cases).values()) == {6}
    assert set(Counter(x["trajectory_id"] for x in cases).values()) == {6}
    assert set(Counter(x["measurement_seed"] for x in cases).values()) == {6}
    assert set(Counter((x["patient_id"], x["trajectory_id"]) for x in cases).values()) == {2}
    assert set(Counter((x["patient_id"], x["measurement_seed"]) for x in cases).values()) == {2}
    assert set(Counter((x["trajectory_id"], x["measurement_seed"]) for x in cases).values()) == {2}


def test_fixed_contract_and_runtime_are_frozen() -> None:
    config = _load(CONFIG_PATH)
    fixed = config["fixed_contract"]
    assert fixed["arms"] == ["prior_only", "trusted_adaptive"]
    assert fixed["sensor_regime"] == "noise_bias_drift_200hz"
    assert fixed["mpc_seed"] == 20260824
    assert fixed["active_excitation"] is False
    assert fixed["trajectory_retuning"] is False
    assert fixed["post_hoc_success_threshold"] is False
    assert fixed["output_overwrite"] is False
    assert fixed["prior_only_patient_specific_beta_application"] is False
    assert fixed["trusted_adaptive_requires_valid_causal_promotion"] is True
    assert [x["measurement_seed"] for x in config["measurement_seed_levels"]] == [
        44104,
        54113,
        64122,
    ]
    assert all(case["duration_s"] == 23.0 for case in config["cases"])
    assert all(case["wall_time_limit_s"] == 32.0 for case in config["cases"])


def test_execution_counts_and_bridge_hashes_are_exact() -> None:
    config = _load(CONFIG_PATH)
    cases = config["cases"]
    new_cases = [x for x in cases if x["execution_source"] == "new_formal_run"]
    bridge_cases = [
        x for x in cases if x["execution_source"] == "read_only_existing_formal_bridge"
    ]
    design = config["fractional_design"]
    assert len(new_cases) == design["new_paired_cases_to_execute"] == 16
    assert len(bridge_cases) == design["read_only_bridge_paired_cases"] == 2
    assert design["selected_analytical_arms"] == 2 * len(cases) == 36
    assert design["new_arms_to_execute"] == 2 * len(new_cases) == 32

    registered = config["read_only_bridge_artifact_hashes"]
    assert set(registered) == {case["case_id"] for case in bridge_cases}
    for case in bridge_cases:
        source_dir = STAGE_ROOT / case["source_result_directory"]
        for filename, expected_hash in registered[case["case_id"]].items():
            assert _sha256(source_dir / filename) == expected_hash
