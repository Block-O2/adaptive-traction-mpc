from pathlib import Path
import json

from sensor_time_integrity_v3 import audit_session


def record(root: Path, rep: int, times: list[float]) -> None:
    directory = root / f"rep_{rep:02d}"
    directory.mkdir()
    wall = {
        "native_dt_s": 0.00025,
        "sensor_samples": [{"sample_time_s": t} for t in times],
        "causal_sensor_estimates": [
            {"sample_time_s": t, "fast_motion_valid": i > 0}
            for i, t in enumerate(times)],
        "command_receipts": [
            {"applied": True, "native_steps": 20,
             "start_physics_s": t, "end_physics_s": t + 0.005,
             "source_sample_time_s": t}
            for t in times[:-1]],
    }
    (directory / "runtime_artifacts.json").write_text(json.dumps({"wall_physics": wall}))


def test_continuous_multirepetition_audit_and_gap_detection(tmp_path: Path) -> None:
    record(tmp_path, 1, [0, 0.005, 0.010])
    record(tmp_path, 2, [0.015, 0.020, 0.025])
    ok = audit_session(tmp_path, 2)
    assert ok["status"] == "PASS"
    assert ok["total_sample_count"] == 6
    assert ok["unique_sample_intervals_s_rounded_9dp"] == [0.005]
    record_path = tmp_path / "rep_02" / "runtime_artifacts.json"
    data = json.loads(record_path.read_text())
    data["wall_physics"]["sensor_samples"][1]["sample_time_s"] = 0.025
    record_path.write_text(json.dumps(data))
    bad = audit_session(tmp_path, 2)
    assert bad["status"] == "FAIL"
    assert bad["first_anomaly"]["kind"] == "missed_or_off_grid_sample"
