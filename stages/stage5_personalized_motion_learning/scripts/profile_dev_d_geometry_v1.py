"""Isolated path-check timing, not end-to-end planner qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter_ns

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import (
    CombinedRigidTableClearanceV1, RigidTableReferenceEnvelopeV1,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import (
    SessionClearanceContract, nominal_control_geometry,
)


def time_calls(function: object, q: np.ndarray, repeats: int) -> dict:
    values = np.empty(repeats, dtype=float)
    result = None
    for i in range(repeats):
        started = perf_counter_ns()
        result = function(q)
        values[i] = (perf_counter_ns() - started) / 1e6
    return {"median_ms": float(np.median(values)),
            "p95_ms": float(np.percentile(values, 95)),
            "maximum_ms": float(np.max(values)),
            "result_min_m": float(np.min(np.asarray(result, dtype=float)))}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=1000)
    args = p.parse_args()
    if args.output.exists() or args.repeats < 10:
        raise ValueError("output must be new and repeats >=10")
    geometry = nominal_control_geometry()
    old = SessionClearanceContract(geometry)
    envelope = RigidTableReferenceEnvelopeV1(geometry)
    combined = CombinedRigidTableClearanceV1(old, envelope)
    q = np.radians(np.column_stack([
        np.linspace(5.0, 60.0, 121), np.linspace(10.0, 80.0, 121)]))
    functions = {"retained_shank_only": old.evaluate,
                 "dev_d_envelope_only": lambda x: np.minimum.reduce(
                     list(envelope.margins(x).values())),
                 "dev_d_combined": combined.evaluate}
    measurements = {}
    for width in (1, 2, 121):
        subset = q[:width] if width > 1 else q[0]
        measurements[str(width)] = {
            name: time_calls(fn, subset, args.repeats)
            for name, fn in functions.items()}
    source = Path(__file__).resolve().parents[1] / (
        "src/traction_mpc_stage5/full3d_adaptive_integration_v1/rigid_table_reference.py")
    report = {"schema": "dev_d_isolated_geometry_timing_v1",
              "evidence_category": "development_microbenchmark_not_deadline_qualification",
              "repeats": args.repeats,
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "q_source": "deterministic registered-angle synthetic grid; no hidden case",
              "measurements": measurements}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["measurements"], indent=2))


if __name__ == "__main__":
    main()
