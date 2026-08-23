"""Run the authorized MuJoCo protective-mode V1 engineering smoke."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from traction_mpc.mujoco_protective_mode_v1.artifacts import (
    write_case_artifacts,
    write_experiment_summary,
)
from traction_mpc.mujoco_protective_mode_v1.config import (
    HumanV2Parameters,
    ProtectiveModeConfig,
)
from traction_mpc.mujoco_protective_mode_v1.controller import ProtectiveModeController
from traction_mpc.mujoco_protective_mode_v1.environment import ProtectiveModeEnvironment
from traction_mpc.mujoco_protective_mode_v1.experiment import run_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--skip-gif", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (
        root / "linkage" / "results" / "local" / "mujoco_protective_mode_v1" / stamp
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    config = ProtectiveModeConfig()
    baseline = run_case(config, "baseline_30deg")
    environment = ProtectiveModeEnvironment(HumanV2Parameters(), config)
    initial = environment.reset()
    timing = ProtectiveModeController(HumanV2Parameters(), config, initial.robot_position_m)
    veto_time = timing.takeoff_start_s + 0.5 * config.transition_duration_s
    veto_probe = run_case(config, "manual_veto_probe", manual_veto_time_s=veto_time)

    sensitivity = []
    if baseline.metrics["mechanical_complete"]:
        for q_switch in (20.0, 25.0, 30.0, 32.5):
            if q_switch == config.q_switch_deg:
                sensitivity.append(baseline)
            else:
                sensitivity.append(
                    run_case(config.with_switch(q_switch), f"sensitivity_{q_switch:g}deg")
                )
        sensitivity_status = "EXECUTED_AFTER_BASELINE_GATE"
    else:
        sensitivity_status = "SKIPPED_BASELINE_NOT_MECHANICALLY_COMPLETE"

    write_case_artifacts(baseline, output_dir, make_gif=not args.skip_gif)
    write_case_artifacts(veto_probe, output_dir)
    for case in sensitivity:
        if case.case_name != baseline.case_name:
            write_case_artifacts(case, output_dir)
    write_experiment_summary(output_dir, baseline, veto_probe, sensitivity, sensitivity_status)
    print(f"OUTPUT_DIR={output_dir}")
    print(f"BASELINE={baseline.metrics['classification']}")
    print(f"SENSITIVITY={sensitivity_status}")
    print(
        "BASELINE_METRICS "
        f"q2_takeoff={baseline.metrics['takeoff_end_q2_deg']:.6g}deg "
        f"q2_terminal={baseline.metrics['terminal_q2_mean_deg']:.6g}deg "
        f"Fint_peak={baseline.metrics['max_interaction_force_n']:.6g}N "
        f"Fbed_peak={baseline.metrics['max_bed_force_n']:.6g}N "
        f"penetration={baseline.metrics['max_bed_penetration_mm']:.6g}mm"
    )
    print(
        "VETO_PROBE "
        f"q2_braking={veto_probe.metrics['veto_q2_braking_distance_deg']:.6g}deg "
        f"robot_braking={veto_probe.metrics['veto_robot_braking_distance_mm']:.6g}mm "
        f"peak_force={veto_probe.metrics['veto_peak_interaction_force_n']:.6g}N"
    )


if __name__ == "__main__":
    main()
