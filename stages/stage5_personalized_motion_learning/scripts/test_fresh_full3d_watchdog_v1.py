"""Development-only injected timing faults for physical watchdog regression."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("stale", "infeasible"), required=True)
    args = parser.parse_args()
    case = json.loads(args.case.read_text())
    original = AdaptiveHumanWaypointHWMPCV22.decide
    calls = 0

    def injected(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1 and args.mode == "stale":
            result = original(self, **kwargs)
            time.sleep(0.110)
            return result
        if calls == 1 and args.mode == "infeasible":
            time.sleep(0.025)
            raise ValueError("injected development-only no-feasible diagnostic")
        return original(self, **kwargs)

    AdaptiveHumanWaypointHWMPCV22.decide = injected
    try:
        summary = run_executed_case(args.output, qualification_case=case,
            qualification_arm="continual_adaptive", simulate_planning_latency=True)
    finally:
        AdaptiveHumanWaypointHWMPCV22.decide = original
    first = summary["decisions"][0]
    print(json.dumps({"mode": args.mode, "status": summary["status"],
        "abort_reason": summary["abort_reason"],
        "physical_intervals": summary["task"]["integration_interval_count"],
        "boundary_samples": summary["task"]["boundary_sample_count"],
        "deadline_wait_intervals": first["deadline_wait_physical_intervals"],
        "plan_activated": first["plan_activated"],
        "minimum_true_clearance_m": summary["task"]["minimum_true_physical_clearance_m_evaluation_only"]},
        sort_keys=True))


if __name__ == "__main__":
    main()
