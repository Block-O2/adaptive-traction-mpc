"""Independent numerical consistency checks, without rerunning simulation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE.parents[1]
BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=BASE / "broad_old24_valid_v1")
    args = parser.parse_args()
    mapping = json.loads((BASE / "assembly_v1/OLD_TO_NEW_CASE_MAPPING.json").read_text())
    assert len(mapping) == 24
    valid = [row for row in mapping if row["revised_validity"]["valid"]]
    assert len(valid) == 22
    for row in mapping:
        assert _digest(ROOT / row["original_case_path"]) == row["original_case_sha256"]
        assert _digest(ROOT / row["revised_case_path"]) == row["revised_case_sha256"]
        old = json.loads((ROOT / row["original_case_path"]).read_text())
        new = json.loads((ROOT / row["revised_case_path"]).read_text())
        old["physical"]["hip_translation_xz_m"][1] = new["physical"]["hip_translation_xz_m"][1]
        assert old == new
    total_planner = 0
    deadline_misses = 0
    completed = 0
    for row in valid:
        output = args.runs / row["case_key"]
        summary = json.loads((output / "summary.json").read_text())
        contact = json.loads((output / "contact_summary.json").read_text())
        manifest = json.loads((output / "rigid_table_run_manifest.json").read_text())
        assert manifest["controller_flags"]["dev_a_recovery"] is True
        assert manifest["controller_flags"]["dev_c_bumpless_transfer"] is False
        assert manifest["controller_flags"]["formal_qualification"] is False
        assert summary["task"]["boundary_interval_relation_holds"]
        with np.load(output / "contact_intervals.npz") as data:
            intervals = np.asarray(data["rows"], dtype=float)
        with np.load(output / "trace.npz", allow_pickle=True) as data:
            trace_end = float(data["time_s"][-1])
            physics_steps = int(data["physics_steps"][-1])
            max_command = float(np.max(np.abs(data["cr12_actuator_command_nm"])))
        assert max_command > 0, "actual robot actuation not seen"
        assert len(intervals) == physics_steps == contact["physical_interval_count"]
        assert abs(intervals[0, 0]) < 1e-12
        assert abs(intervals[-1, 1] - trace_end) < 1e-7
        dt = intervals[:, 1] - intervals[:, 0]
        assert np.max(np.abs(dt - 0.00025)) < 1e-8
        assert np.max(np.abs(intervals[1:, 0] - intervals[:-1, 1])) < 1e-8
        for j, name in enumerate(("thigh", "shank")):
            values = contact["contacts"][name]
            normal = intervals[:, 2+2*j]
            mask = intervals[:, 8+j] > 0
            assert np.isclose(values["normal_peak_n"], np.max(normal), atol=1e-8)
            assert np.isclose(values["normal_impulse_n_s"], np.dot(dt, normal), atol=1e-8)
            assert np.isclose(values["contact_duration_s"], np.sum(dt[mask]), atol=1e-8)
        total_planner += len(summary["timing"]["high_level_planning_runtime_ms"])
        deadline_misses += sum(t > 100.0 for t in summary["timing"]["high_level_planning_runtime_ms"])
        completed += summary["status"] == "COMPLETE"
    assert total_planner == 125
    assert deadline_misses == 8
    assert completed == 5
    v2 = json.loads((BASE / "assembly_v2/OLD_TO_NEW_CASE_MAPPING.json").read_text())
    assert len(v2) == 24
    assert sum(bool(row["v2_validity"]["valid"]) for row in v2) == 23
    changed = []
    for row in v2:
        old_path = ROOT / row["v1_case_path"]
        new_path = ROOT / row["v2_case_path"]
        assert _digest(old_path) == row["v1_case_sha256"]
        assert _digest(new_path) == row["v2_case_sha256"]
        old_case = json.loads(old_path.read_text())
        new_case = json.loads(new_path.read_text())
        if old_case != new_case:
            changed.append(row["case_key"])
            old_case["physical"]["hip_translation_xz_m"][1] = new_case["physical"]["hip_translation_xz_m"][1]
            assert old_case == new_case
    assert changed == ["balanced_near_upper_current_rom_r02"]
    supplemental = BASE / "supplemental_v2/balanced_near_upper_current_rom_r02"
    added_summary = json.loads((supplemental / "summary.json").read_text())
    added_contact = json.loads((supplemental / "contact_summary.json").read_text())
    added_manifest = json.loads((supplemental / "rigid_table_run_manifest.json").read_text())
    assert added_summary["status"] == "ABORTED"
    assert added_summary["abort_reason"] == "ACTIVE_RECOVERY_ABORTED:ACTIVE_RECOVERY_NO_FEASIBLE_SEGMENT"
    assert added_manifest["controller_flags"]["dev_a_recovery"] is True
    assert added_manifest["controller_flags"]["dev_c_bumpless_transfer"] is False
    assert added_manifest["controller_flags"]["formal_qualification"] is False
    with np.load(supplemental / "contact_intervals.npz") as data:
        added_intervals = np.asarray(data["rows"], dtype=float)
    with np.load(supplemental / "trace.npz", allow_pickle=True) as data:
        assert np.max(np.abs(data["cr12_actuator_command_nm"])) > 0
        assert len(added_intervals) == int(data["physics_steps"][-1])
    added_dt = added_intervals[:, 1] - added_intervals[:, 0]
    assert len(added_intervals) == added_contact["physical_interval_count"] == 28080
    assert np.max(np.abs(added_dt - 0.00025)) < 1e-8
    assert np.max(np.abs(added_intervals[1:, 0] - added_intervals[:-1, 1])) < 1e-8
    for j, name in enumerate(("thigh", "shank")):
        saved = added_contact["contacts"][name]
        normal = added_intervals[:, 2 + 2*j]
        assert np.isclose(saved["normal_peak_n"], np.max(normal), atol=1e-8)
        assert np.isclose(saved["normal_impulse_n_s"], np.dot(added_dt, normal), atol=1e-8)
    assert added_contact["contacts"]["thigh"]["normal_peak_n"] == 0.0
    print(json.dumps({"schema": "rigid_table_v1_artifact_verification",
                      "old_mapping_rows": len(mapping), "executed_case_count": len(valid),
                      "all_original_and_revised_hashes_match": True,
                      "all_semantic_case_differences_only_hip_z": True,
                      "all_interval_contact_integrals_recomputed": True,
                      "all_trace_physics_counts_match": True,
                      "all_runs_actuate_CR12": True,
                      "planner_calls": total_planner,
                      "deadline_misses": deadline_misses,
                      "completed": completed,
                      "v2_valid_initial_endpoint_count": 23,
                      "v2_only_geometry_modified_case_keys": changed,
                      "v2_supplemental_contact_intervals": len(added_intervals),
                      "v2_supplemental_status": added_summary["abort_reason"]}, sort_keys=True))


if __name__ == "__main__":
    main()
