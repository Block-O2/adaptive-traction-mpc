"""One-shot preregistration of new 120/120 functional cases; no simulation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/high_rom_v1"
CONFIG = STAGE / "configs/high_rom_v1"
OFFSETS = ((0., 0.), (9., 9.), (4., 17.), (11., 12.), (0., 0.))
STARTS = ((6., 11.), (8., 13.))
ALPHAS = (.35, .65)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def interpolate(a: object, b: object, alpha: float) -> object:
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            raise ValueError("physical schema differs")
        return [interpolate(x, y, alpha) for x, y in zip(a, b)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round((1. - alpha) * float(a) + alpha * float(b), 9)
    raise TypeError("expected numeric physical setup")


def main() -> None:
    spec_path = DOC / "HIGH_ROM_FUNCTION_FRESH16_SPEC.json"
    if spec_path.exists():
        raise FileExistsError("fresh16 preregistration already exists")
    matrix = json.loads((DOC / "PHASE_B_MATRIX.json").read_text())
    sync = [entry for entry in matrix["cases"]
            if entry["candidate"] == "high_rom_sync_feedback_v1"]
    if len(sync) != 8:
        raise RuntimeError("expected eight frozen Stage-B physical variants")
    parents = [json.loads((ROOT / x["path"]).read_text()) for x in sync]
    exposed = []
    for entry in matrix["cases"]:
        exposed.append(json.loads((ROOT / entry["path"]).read_text()))
    for path in CONFIG.glob("high_rom_nominal_sync_*_v1.json"):
        exposed.append(json.loads(path.read_text()))
    for path in (CONFIG / "low_rom_regression_cases").glob("*.json"):
        exposed.append(json.loads(path.read_text()))
    exposed_signatures = {digest({"physical": x["physical"], "task": x["task"]})
                          for x in exposed}
    rows, signatures = [], set()
    for i, parent in enumerate(parents):
        next_parent = parents[(i + 1) % 8]
        for j, (start, alpha) in enumerate(zip(STARTS, ALPHAS)):
            key = f"high_rom_function_fresh_{2*i+j+1:02d}_v1"
            physical = {name: interpolate(value, next_parent["physical"][name], alpha)
                        for name, value in parent["physical"].items()}
            task = {"start_deg": list(start), "goal_deg": [120., 120.],
                    "commissioning_waypoints_deg": [
                        [start[k] + offset[k] for k in range(2)] for offset in OFFSETS]}
            payload = {"physical": physical, "task": task}
            signature = digest(payload)
            if signature in exposed_signatures or signature in signatures:
                raise RuntimeError("fresh setup/task payload duplicate")
            signatures.add(signature)
            case = {"case_key": key,
                    "cell": {"family": "fresh_high_rom_function", "range": "120_both", "replicate": 2*i+j+1},
                    "evidence_category": "fresh_function_confirmation_preregistered_not_hardware_qualification",
                    **copy.deepcopy(payload), "research_model": "high_rom_v1",
                    "coordination_candidate": "high_rom_sync_feedback_v1"}
            path = CONFIG / f"{key}.json"
            if path.exists():
                raise FileExistsError(path)
            path.write_text(json.dumps(case, indent=2) + "\n")
            rows.append({"case_key": key, "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "material_payload_sha256": signature,
                         "parent_variants": [sync[i]["physical_variant"], sync[(i+1)%8]["physical_variant"]],
                         "interpolation_fraction_to_second_parent": alpha,
                         "start_deg": list(start), "goal_deg": [120., 120.]})
    freeze = json.loads((DOC / "HIGH_ROM_FUNCTION_FREEZE.json").read_text())
    instrumentation = json.loads((DOC / "HIGH_ROM_FUNCTION_INSTRUMENTATION.json").read_text())
    spec = {"schema": "high_rom_function_fresh16_preregistration_v1",
            "registered_before_any_fresh_run": True,
            "generation_rule": "eight ordered Stage-B sync physical setups, each interpolated toward the next cyclic setup at fractions 0.35 and 0.65; starts (6,11) and (8,13) degrees; fixed commissioning offsets; simultaneous (120,120) goal",
            "physical_domain": "coordinate-wise convex hull of Stage-B eight setups",
            "start_domain": "inside the existing Round19 legal-start observations; new High-ROM start capability is to be tested",
            "candidate": "high_rom_sync_feedback_v1",
            "candidate_source_set_sha256": freeze["candidate_set_sha256"],
            "evaluation_only_instrumentation_sha256": instrumentation["modified_candidate_dependency_files"][0]["current_sha256"],
            "controller_options_sha256": json.loads((DOC / "PHASE_B_FINGERPRINTS.json").read_text())["controller_options_sha256"],
            "physics_dt_s": .00025, "sensor_dt_s": .005,
            "case_count": 16, "all_goal_deg": [120., 120.],
            "excluded_case_count": 0, "exposed_material_payload_count": len(exposed_signatures),
            "scoring": {"base": "unchanged PHASE_B_MATRIX.json/scoring, using each registered start as RETURN target",
                        "native_truth": "both q within 1 degree and both dq within 2 deg/s at OUTBOUND->HOLD; every 0.25ms valid node in a >=0.5s consecutive HOLD run; actual RETURN at completion boundary",
                        "native_safety": "zero modeled contact/ROM violation, native shank clearance >=0, native interface force <=200N and moment <=60Nm with no missing load sample",
                        "native_timing": "zero expired activated plans, every activated plan age <100ms, no native phase timeout; original phase and global task timeouts",
                        "denominator": "all 16 registered cases, no exclusion, substitution or post-result tuning"},
            "cases": rows}
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(json.dumps({"registered": len(rows), "unique": len(signatures),
                      "exposed_payload_duplicate_count": 0,
                      "spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
