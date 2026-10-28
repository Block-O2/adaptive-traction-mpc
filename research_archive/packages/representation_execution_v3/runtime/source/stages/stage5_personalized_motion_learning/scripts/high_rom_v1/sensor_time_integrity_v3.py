"""Read-only, per-repetition and whole-session sensor-time integrity audit."""
from __future__ import annotations

import json
import math
from pathlib import Path

PERIOD_S = 0.005
TOLERANCE_S = 1e-7


def audit_session(output: Path, upto: int) -> dict:
    times = []
    intervals = []
    control_intervals = []
    per_rep = []
    first_anomaly = None

    def flag(rep: int, kind: str, index: int, detail: object) -> None:
        nonlocal first_anomaly
        if first_anomaly is None:
            first_anomaly = {"repetition_index": rep, "kind": kind,
                             "local_index": index, "detail": detail}

    for rep in range(1, upto + 1):
        path = output / f"rep_{rep:02d}" / "runtime_artifacts.json"
        data = json.loads(path.read_text())["wall_physics"]
        samples = data["sensor_samples"]
        estimates = data["causal_sensor_estimates"]
        receipts = data["command_receipts"]
        if len(samples) != len(estimates):
            flag(rep, "sample_estimate_count", 0, [len(samples), len(estimates)])
        start_count = len(times)
        for index, sample in enumerate(samples):
            t = float(sample["sample_time_s"])
            if not math.isfinite(t):
                flag(rep, "nonfinite_sensor_time", index, t)
            if times:
                delta = t - times[-1]
                intervals.append(delta)
                if delta <= 0:
                    flag(rep, "duplicate_or_nonmonotonic_sample", index, delta)
                elif abs(delta - PERIOD_S) > TOLERANCE_S:
                    flag(rep, "missed_or_off_grid_sample", index,
                         {"previous_s": times[-1], "current_s": t, "interval_s": delta})
            times.append(t)
            if index < len(estimates):
                estimate = estimates[index]
                if abs(float(estimate["sample_time_s"]) - t) > TOLERANCE_S:
                    flag(rep, "causal_estimate_timestamp", index, t)
                if index > 0 and not estimate["fast_motion_valid"]:
                    flag(rep, "invalid_causal_acceleration_history", index, t)
        previous_control_end = None
        control_count = 0
        for index, receipt in enumerate(receipts):
            steps = receipt.get("native_steps", 0)
            if not receipt.get("applied") or not steps:
                continue
            start = float(receipt["start_physics_s"])
            end = float(receipt["end_physics_s"])
            source = float(receipt["source_sample_time_s"])
            duration = end - start
            control_intervals.append(duration)
            control_count += 1
            if not all(map(math.isfinite, (start, end, source))):
                flag(rep, "nonfinite_control_time", index, [start, end, source])
            elif (duration <= 0 or abs(duration - steps * float(data["native_dt_s"])) > TOLERANCE_S):
                flag(rep, "control_duration_or_native_steps", index, [duration, steps])
            elif previous_control_end is not None and abs(start - previous_control_end) > TOLERANCE_S:
                flag(rep, "control_gap_or_overlap", index,
                     {"previous_end_s": previous_control_end, "start_s": start})
            elif source > start + TOLERANCE_S:
                flag(rep, "future_control_source", index, [source, start])
            previous_control_end = end
        per_rep.append({"repetition_index": rep, "sample_count": len(samples),
                        "first_sample_s": times[start_count] if samples else None,
                        "last_sample_s": times[-1] if samples else None,
                        "control_interval_count": control_count})
    result = {
        "schema": "sensor_time_integrity_v3",
        "status": "PASS" if first_anomaly is None else "FAIL",
        "audited_repetitions": upto,
        "expected_sensor_period_s": PERIOD_S,
        "tolerance_s": TOLERANCE_S,
        "total_sample_count": len(times),
        "sensor_interval_count": len(intervals),
        "minimum_sample_interval_s": min(intervals, default=None),
        "maximum_sample_interval_s": max(intervals, default=None),
        "unique_sample_intervals_s_rounded_9dp": sorted({round(x, 9) for x in intervals}),
        "control_interval_count": len(control_intervals),
        "minimum_control_interval_s": min(control_intervals, default=None),
        "maximum_control_interval_s": max(control_intervals, default=None),
        "first_anomaly": first_anomaly,
        "per_repetition": per_rep,
    }
    return result
