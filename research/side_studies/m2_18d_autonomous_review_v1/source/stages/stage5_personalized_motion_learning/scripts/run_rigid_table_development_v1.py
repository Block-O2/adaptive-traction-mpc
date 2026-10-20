"""Restart-safe unchanged-controller full-physics DEVELOPMENT replication.

Each admitted case is reinitialized from its new assembly; no old checkpoint,
robot state, belief, fitted geometry or residual weights are imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

import mujoco
import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case
from traction_mpc_stage5.rigid_table_assembly_v1 import assess_assembly


STAGE = Path(__file__).resolve().parents[1]
ASSEMBLY = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/assembly_v1"
NOMINAL = STAGE / "configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1/nominal_reference_rigid_table_v1.json"


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class ContactIntervalMonitor:
    """Read solved contact forces immediately after every native mj_step2."""

    def __init__(self) -> None:
        self.rows: list[tuple[float, ...]] = []
        self.peak_detail: dict[str, dict] = {}
        self.native = mujoco.mj_step2

    def observed(self, model: mujoco.MjModel, data: mujoco.MjData) -> None:
        t0 = float(data.time)
        self.native(model, data)
        bed = model.geom("bed").id
        thigh = model.geom("thigh_geom").id
        shank = model.geom("shank_geom").id
        normal = [0.0, 0.0]
        tangent = [0.0, 0.0]
        distance = [0.0, 0.0]
        active = [0.0, 0.0]
        for i in range(data.ncon):
            c = data.contact[i]
            pair = {int(c.geom1), int(c.geom2)}
            if bed not in pair:
                continue
            j = 0 if thigh in pair else 1 if shank in pair else None
            if j is None:
                continue
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, i, force)
            normal[j] += float(force[0])
            tangent[j] += float(np.linalg.norm(force[1:3]))
            active[j] = 1.0
            distance[j] = min(distance[j], float(c.dist))
            name = ("thigh", "shank")[j]
            if name not in self.peak_detail or force[0] > self.peak_detail[name]["normal_n"]:
                self.peak_detail[name] = {
                    "interval_start_s": t0,
                    "interval_end_s": float(data.time),
                    "normal_n": float(force[0]),
                    "distance_m": float(c.dist),
                    "position_world_m": c.pos.tolist(),
                    "geom_pair": [model.geom(int(c.geom1)).name,
                                  model.geom(int(c.geom2)).name],
                }
        self.rows.append((t0, float(data.time), normal[0], tangent[0],
                          normal[1], tangent[1], distance[0], distance[1],
                          active[0], active[1],
                          *data.qpos[:].tolist(), *data.qvel[:].tolist(),
                          *data.ctrl[:].tolist()))

    def save(self, output: Path) -> dict:
        columns = ["interval_start_s", "interval_end_s", "thigh_normal_n",
                   "thigh_tangent_n", "shank_normal_n", "shank_tangent_n",
                   "thigh_contact_distance_m", "shank_contact_distance_m",
                   "thigh_contact", "shank_contact"]
        if self.rows:
            array = np.asarray(self.rows, dtype=float)
            if array.shape[1] != 10 + 2 * 8 + 6:
                raise RuntimeError(f"unexpected CR12/Human actuator state shape {array.shape}")
            columns += [f"qpos_{i}" for i in range(8)]
            columns += [f"qvel_{i}" for i in range(8)]
            columns += [f"ctrl_{i}" for i in range(6)]
            np.savez_compressed(output / "contact_intervals.npz", rows=array,
                                columns=np.asarray(columns))
            dt = array[:, 1] - array[:, 0]
            if np.any(dt <= 0) or np.max(np.abs(dt - 0.00025)) > 1e-8:
                raise RuntimeError("nonpositive or unexpected physical interval duration")
        else:
            array = np.empty((0, 32))
            dt = np.empty(0)
        contacts = {}
        for j, name in enumerate(("thigh", "shank")):
            mask = array[:, 8+j] > 0
            distances = array[mask, 6+j]
            contacts[name] = {
                "contact_interval_count": int(np.sum(mask)),
                "contact_duration_s": float(np.sum(dt[mask])),
                "force_active_duration_s": float(np.sum(dt[array[:, 2+2*j] > 1e-8])),
                "first_contact_s": float(array[np.flatnonzero(mask)[0], 0]) if np.any(mask) else None,
                "last_contact_s": float(array[np.flatnonzero(mask)[-1], 1]) if np.any(mask) else None,
                "normal_peak_n": float(np.max(array[:, 2+2*j])) if len(array) else 0.0,
                "normal_impulse_n_s": float(np.dot(dt, array[:, 2+2*j])) if len(array) else 0.0,
                "tangent_peak_n": float(np.max(array[:, 3+2*j])) if len(array) else 0.0,
                "minimum_contact_distance_m": float(np.min(distances)) if len(distances) else None,
                "peak_contact_detail": self.peak_detail.get(name),
            }
        summary = {
            "schema": "rigid_table_v1_physical_interval_contact_monitor",
            "force_timestamp_semantics": "mj_step2 constraint solve for executed interval; read before next boundary refresh",
            "physical_interval_count": len(array),
            "duration_s": float(np.sum(dt)),
            "contacts": contacts,
            "controller_input": False,
        }
        write_json(output / "contact_summary.json", summary)
        return summary


def run_one(case_path: Path, output: Path) -> dict:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    screen = assess_assembly(case)
    if not screen["valid"]:
        raise ValueError(f"case has no valid rigid-table initial assembly: {screen['category']}: {screen['reason']}")
    monitor = ContactIntervalMonitor()
    mujoco.mj_step2 = monitor.observed
    summary = None
    error = None
    try:
        summary = run_executed_case(output, qualification_case=case,
            qualification_arm="continual_adaptive", simulate_planning_latency=True,
            formal_qualification=False, dev_a_recovery=True,
            dev_c_bumpless_transfer=False)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        mujoco.mj_step2 = monitor.native
    output.mkdir(parents=True, exist_ok=True)
    contact = monitor.save(output)
    write_json(output / "rigid_table_run_manifest.json", {
        "schema": "rigid_table_v1_unchanged_controller_development",
        "case_path": str(case_path),
        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "command": sys.argv,
        "assembly": screen,
        "controller_flags": {"dev_a_recovery": True,
                             "dev_c_bumpless_transfer": False,
                             "simulate_planning_latency": True,
                             "formal_qualification": False,
                             "qualification_arm": "continual_adaptive"},
        "physical_contact_monitor": "post-mj_step2 native interval; evaluation only",
        "summary_status": summary["status"] if summary else None,
        "runner_error": error,
    })
    if error:
        write_json(output / "runner_exception.json", error)
    return {"case_key": case["case_key"],
            "status": summary["status"] if summary else "PRESERVED_RUNNER_EXCEPTION",
            "abort_reason": summary.get("abort_reason") if summary else error["message"],
            "commissioning_completed": bool(summary and summary.get("commissioning")),
            "recovery_entered": summary.get("dev_a_recovery", {}).get("entered") if summary else None,
            "recovery_succeeded": summary.get("dev_a_recovery", {}).get("succeeded") if summary else None,
            "task_interval_count": summary.get("task", {}).get("integration_interval_count") if summary else None,
            "thigh_normal_peak_n": contact["contacts"]["thigh"]["normal_peak_n"],
            "shank_normal_peak_n": contact["contacts"]["shank"]["normal_peak_n"],
            "physical_interval_count": contact["physical_interval_count"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-keys", nargs="*")
    parser.add_argument("--include-nominal", action="store_true")
    args = parser.parse_args()
    mapping = json.loads((ASSEMBLY / "OLD_TO_NEW_CASE_MAPPING.json").read_text(encoding="utf-8"))
    allowed = {row["case_key"] for row in mapping if row["revised_validity"]["valid"]}
    files = sorted((ASSEMBLY / "cases").glob("*.json"))
    if args.include_nominal:
        files.append(NOMINAL)
        allowed.add("nominal_reference_rigid_table_v1")
    if args.case_keys:
        requested = set(args.case_keys)
        files = [file for file in files if file.stem in requested]
        if {file.stem for file in files} != requested:
            raise ValueError("requested case key has no versioned case JSON")
    files = [file for file in files if file.stem in allowed]
    if not files:
        raise ValueError("no mechanically valid cases selected")
    args.output.mkdir(parents=True, exist_ok=True)
    batch = {"schema": "rigid_table_v1_unchanged_controller_development_batch",
             "evidence_category": "consumed_old24_repaired_assembly_development_not_fresh",
             "selected_case_keys": [file.stem for file in files],
             "mechanically_invalid_old_case_keys": [row["case_key"] for row in mapping
                                                     if not row["revised_validity"]["valid"]],
             "rows": []}
    for file in files:
        output = args.output / file.stem
        if (output / "rigid_table_run_manifest.json").exists():
            manifest = json.loads((output / "rigid_table_run_manifest.json").read_text())
            row = {"case_key": file.stem, "status": manifest["summary_status"],
                   "resumed_existing_artifact": True}
        elif output.exists() and any(output.iterdir()):
            row = {"case_key": file.stem, "status": "INCOMPLETE_INTERRUPTED_ARTIFACT_PRESERVED",
                   "resumed_existing_artifact": True}
        else:
            row = run_one(file, output)
            row["resumed_existing_artifact"] = False
        batch["rows"].append(row)
        write_json(args.output / "batch_status.json", batch)
        print(json.dumps(row, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
