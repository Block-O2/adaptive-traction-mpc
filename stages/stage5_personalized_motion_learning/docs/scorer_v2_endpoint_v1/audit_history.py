"""Bounded read-only inventory for historical scorer-v1 RETURN endpoints."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOTS = {
    "high_rom_development": Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-v1/stages/stage5_personalized_motion_learning/results/high_rom_v1"),
    "runtime_development": Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-runtime-v1/stages/stage5_personalized_motion_learning/results/high_rom_runtime_v1"),
    "rss_development": Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/results"),
}
RSS_FAMILIES = ("smooth_runtime_v1", "motion_smoothness_v1", "rolling_suffix_splice_v1",
                "control_miss_attribution_v1", "runtime_gate_stability_v1")
CONFIG_ROOT = Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-waypoint-smoothness-v1/stages/stage5_personalized_motion_learning/configs/high_rom_v1")
OUT = Path("/private/tmp/scorer_v2_history_audit.json")


def final_boundary(path: Path) -> dict | None:
    """Read only the small leading final-boundary object, not 100k nodes."""
    key = b'"final_native_boundary_evaluation_only"'
    with path.open("rb") as stream:
        head = bytearray()
        while len(head) < 16 * 1024 * 1024:
            block = stream.read(1024 * 1024)
            if not block:
                break
            head.extend(block)
            ix = head.find(key)
            if ix < 0:
                continue
            colon = head.find(b":", ix + len(key))
            if colon < 0:
                continue
            payload = head[colon + 1:].decode("utf-8")
            try:
                value, _ = json.JSONDecoder().raw_decode(payload.lstrip())
            except json.JSONDecodeError:
                continue
            return value if isinstance(value, dict) else None
    return None


case_by_hash = {}
for case_path in CONFIG_ROOT.rglob("*.json"):
    try:
        data = json.loads(case_path.read_text())
    except (json.JSONDecodeError, UnicodeError):
        continue
    if isinstance(data, dict) and isinstance(data.get("task"), dict) and "start_deg" in data["task"]:
        case_by_hash[hashlib.sha256(case_path.read_bytes()).hexdigest()] = (case_path, data)

paths = []
for scope, root in ROOTS.items():
    if scope == "rss_development":
        paths.extend((scope, path.parent) for family in RSS_FAMILIES for path in (root / family).rglob("trace.npz"))
    else:
        paths.extend((scope, path.parent) for path in root.rglob("trace.npz"))
rows = []
for scope, path in paths:
    item = {"scope": scope, "run": str(path)}
    summary_path = path / "summary.json"
    launch_path = path / "HIGH_ROM_CASE_RESULT.json"
    artifact_path = path / "runtime_artifacts.json"
    if not summary_path.is_file() or not launch_path.is_file():
        item.update(classification="NO_RAW_TRACE", reason="summary or run manifest absent")
        rows.append(item)
        continue
    summary = json.loads(summary_path.read_text())
    launch = json.loads(launch_path.read_text())
    item.update(runner_status=summary.get("status"), case_key=launch.get("case_key"),
                case_sha256=launch.get("case_sha256"), evidence_category=launch.get("category"))
    if summary.get("status") != "COMPLETE":
        item.update(classification="NON_COMPLETE", reason="no successful RETURN endpoint")
        rows.append(item)
        continue
    case = case_by_hash.get(launch.get("case_sha256"))
    if case is None:
        item.update(classification="NO_RAW_TRACE", reason="registered start case unavailable")
        rows.append(item)
        continue
    config_path = path / "config_snapshot.json"
    if not config_path.is_file():
        item.update(classification="NO_RAW_TRACE", reason="scoring tolerance snapshot absent")
        rows.append(item)
        continue
    config = json.loads(config_path.read_text())
    start = np.radians(np.asarray(case[1]["task"]["start_deg"], dtype=float))
    angle = np.radians(np.asarray(config["completion_angle_tolerance_deg"], dtype=float))
    limit_deg = np.asarray(config["completion_velocity_tolerance_deg_s"], dtype=float)
    with np.load(path / "trace.npz", allow_pickle=False) as trace:
        source_t = float(trace["time_s"][-1])
        source = np.asarray(trace["evaluation_only_human_state_rad_rad_s"][-1], dtype=float)
    source_dq = np.degrees(source[2:])
    source_pos = bool(np.all(abs(source[:2] - start) <= angle))
    source_vel = bool(np.all(abs(source_dq) <= limit_deg))
    item.update(start_deg=case[1]["task"]["start_deg"], velocity_limit_deg_s=limit_deg.tolist(),
                source_time_s=source_t, source_q_deg=np.degrees(source[:2]).tolist(),
                source_dq_deg_s=source_dq.tolist(), source_return=source_pos and source_vel)
    if not artifact_path.is_file():
        item.update(classification="NO_RAW_TRACE", reason="native runtime artifact absent")
        rows.append(item)
        continue
    boundary = final_boundary(artifact_path)
    transitions = [x for x in summary["task"]["phase_transitions"]
                   if x.get("from") == "RETURN" and x.get("to") == "COMPLETE"]
    if boundary is None or len(transitions) != 1 or boundary.get("time_s") != transitions[0].get("time_s"):
        item.update(classification="NO_RAW_TRACE", reason="no exact recorded native physical commit boundary")
        rows.append(item)
        continue
    commit = np.r_[np.asarray(boundary["qpos_evaluation_only"][:2], dtype=float),
                   np.asarray(boundary["qvel_evaluation_only"][:2], dtype=float)]
    commit_dq = np.degrees(commit[2:])
    commit_pos = bool(np.all(abs(commit[:2] - start) <= angle))
    commit_vel = bool(np.all(abs(commit_dq) <= limit_deg))
    source_margin = abs(limit_deg - abs(source_dq))
    observed_dq_change = abs(commit_dq - source_dq)
    # No arbitrary near-boundary band: if the observed source-to-commit
    # change reaches the source's distance to the frozen threshold, the
    # source-only result cannot establish the endpoint classification.
    near = bool(np.any(source_margin <= observed_dq_change + 1e-12)
                or (source_pos and source_vel) != (commit_pos and commit_vel))
    item.update(commit_time_s=float(boundary["time_s"]),
                source_to_commit_ms=(float(boundary["time_s"]) - source_t) * 1000,
                commit_q_deg=np.degrees(commit[:2]).tolist(), commit_dq_deg_s=commit_dq.tolist(),
                commit_return=commit_pos and commit_vel,
                source_velocity_margin_deg_s=(limit_deg - abs(source_dq)).tolist(),
                observed_velocity_change_deg_s=observed_dq_change.tolist(),
                classification="NEAR_BOUNDARY" if near else "CLEAR_MARGIN")
    rows.append(item)

counts = {key: sum(x["classification"] == key for x in rows)
          for key in ("CLEAR_MARGIN", "NEAR_BOUNDARY", "NO_RAW_TRACE", "NON_COMPLETE")}
report = {"schema": "scorer_v2_historical_impact_inventory_v1",
          "scope": {k: str(v) for k, v in ROOTS.items()},
          "method": "source trace final q/dq; leading final-native-boundary object for complete cases; conservative near classification from observed source-to-commit velocity change; no interpolation",
          "counts": counts,
          "scanned_count": len(rows),
          "source_to_commit_endpoint_changes": sum(x.get("source_return") != x.get("commit_return")
                                                    for x in rows if "commit_return" in x),
          "rows": rows}
OUT.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("scanned_count", "counts", "source_to_commit_endpoint_changes")}))
print(OUT)
