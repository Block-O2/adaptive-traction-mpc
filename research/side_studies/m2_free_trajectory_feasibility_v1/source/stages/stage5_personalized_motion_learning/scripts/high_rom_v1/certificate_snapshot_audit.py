"""One frozen deployable snapshot: exact per-call certificate audit and timing."""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from pathlib import Path
import sys
from time import perf_counter_ns, process_time_ns

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
for relative in ("stages/stage5_personalized_motion_learning/src",
                 "stages/stage4_adaptive_control/src", "stages/stage3_full3d/src"):
    sys.path.insert(0, str(ROOT / relative))

from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as mono
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import (
    CombinedRigidTableClearanceV1, _quintic_sample_powers)
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import _jsonable


def _stable(value):
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k != "runtime_ms"}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def _digest(value) -> str:
    payload = json.dumps(_stable(_jsonable(value)), sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    payload = args.snapshot.read_bytes()
    original = CombinedRigidTableClearanceV1.certified_minimum
    runs = []
    for repetition in range(args.repeats):
        calls = []
        def audited(self, coefficients, duration_s):
            started = perf_counter_ns()
            lower = original(self, coefficients, duration_s)
            elapsed_ms = (perf_counter_ns() - started) / 1e6
            calls.append({
                "input_sha256": hashlib.sha256(
                    np.asarray(coefficients, dtype=float).tobytes()
                    + np.asarray([duration_s], dtype=float).tobytes()).hexdigest(),
                "duration_s": float(duration_s), "lower_m": float(lower),
                "proof_sha256": _digest(self.last_certificate),
                "certificate_ms": elapsed_ms,
            })
            return lower
        before = {"trig": mono._trig_bounds.cache_info()._asdict(),
                  "endpoint": mono._endpoint_bounds.cache_info()._asdict(),
                  "grid": _quintic_sample_powers.cache_info()._asdict()}
        CombinedRigidTableClearanceV1.certified_minimum = audited
        try:
            wall_start, cpu_start = perf_counter_ns(), process_time_ns()
            planner, kwargs = pickle.loads(payload)
            decision = planner.decide(**kwargs)
            wall_ms = (perf_counter_ns() - wall_start) / 1e6
            cpu_ms = (process_time_ns() - cpu_start) / 1e6
        finally:
            CombinedRigidTableClearanceV1.certified_minimum = original
        after = {"trig": mono._trig_bounds.cache_info()._asdict(),
                 "endpoint": mono._endpoint_bounds.cache_info()._asdict(),
                 "grid": _quintic_sample_powers.cache_info()._asdict()}
        runs.append({"repetition": repetition + 1, "wall_ms": wall_ms,
                     "cpu_ms": cpu_ms, "certificate_calls": len(calls),
                     "certificate_ms_sum": sum(x["certificate_ms"] for x in calls),
                     "cache_before": before, "cache_after": after,
                     "executed_label": decision.record()["executed_label"],
                     "decision_sha256": _digest(decision.record()),
                     "calls": calls})
        print(json.dumps({k: runs[-1][k] for k in (
            "repetition", "wall_ms", "certificate_calls", "certificate_ms_sum",
            "executed_label", "decision_sha256")}), flush=True)
    result = {"schema": "high_rom_certificate_snapshot_audit_v1",
              "snapshot": str(args.snapshot.resolve()),
              "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
              "runs": runs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
