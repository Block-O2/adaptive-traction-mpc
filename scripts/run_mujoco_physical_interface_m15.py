"""Run the authorized MuJoCo M1.5 physical-interface engineering smoke."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from traction_mpc.mujoco_protective_mode_v1.config import (
    HumanV2Parameters,
    ProtectiveModeConfig,
)
from traction_mpc.mujoco_protective_mode_v1.physical_interface_m15 import (
    INTERFACES,
    PROBE_POSTURES_DEG,
    M15Config,
    run_authority_probe,
    run_bed_start_equilibrium,
)
from traction_mpc.mujoco_protective_mode_v1.physical_interface_m15_artifacts import (
    write_m15_artifacts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (
        root / "linkage" / "results" / "local" / "mujoco_physical_interface_m15" / stamp
    )

    model_config = ProtectiveModeConfig()
    diagnostic_config = M15Config()
    equilibrium = run_bed_start_equilibrium(diagnostic_config, model_config)
    probes = [
        run_authority_probe(interface, posture, direction, diagnostic_config, model_config)
        for interface in INTERFACES
        for posture in PROBE_POSTURES_DEG
        for direction in (-1, 1)
    ]

    bilateral = [case.metrics for case in probes if case.metrics["interface"] == "bilateral_point"]
    bed_ready = equilibrium.metrics["classification"] == "STABLE_AT_REQUESTED_TERMINAL"
    pose_ready = all(not case["initial_posture_not_equilibrium"] for case in bilateral)
    bidirectional_authority = all(
        case["effective_delta_q2_deg_per_mm"] is not None
        and case["effective_delta_q2_deg_per_mm"] > 0.0
        for case in bilateral
    )
    deformation_not_dominant = all(
        case["motion_absorbed_by_interface_ratio"] is not None
        and case["motion_absorbed_by_interface_ratio"] <= 0.5
        for case in bilateral
    )
    force_gate = all(not case["force_veto_triggered"] for case in bilateral)
    rerun_ready = (
        bed_ready
        and pose_ready
        and bidirectional_authority
        and deformation_not_dominant
        and force_gate
    )
    full_motion_status = (
        "ELIGIBLE_FOR_SEPARATE_FULL_MOTION_RERUN"
        if rerun_ready
        else "SKIPPED_PHYSICAL_INTERFACE_GATE_NOT_SATISFIED"
    )
    summary = {
        "evidence_category": "engineering_smoke_not_authoritative",
        "scientific_constants_unchanged": {
            "actuator_force_limit_n": model_config.actuator_force_limit_n,
            "force_veto_limit_n": model_config.force_veto_limit_n,
            "q_terminal_deg": model_config.q_terminal_deg,
            "q_switch_deg": model_config.q_switch_deg,
            "normal_trajectory": "unchanged Human V2 taught trajectory; not executed in M1.5",
        },
        "hardware_fact_status": "no repository evidence for real cuff topology or robot command contract",
        "tension_only_topology": "one unilateral axial force direction; not a fixed cuff",
        "bilateral_point_hypothesis": (
            "MuJoCo connect constraint at a 15 mm offset; nominal 1800 N/m and 35 Ns/m "
            "direct-format solver parameters with effective planar x/z coupling; "
            "not hardware validated"
        ),
        "model_parameters": asdict(HumanV2Parameters()),
        "model_config": asdict(model_config),
        "diagnostic_config": asdict(diagnostic_config),
        "bed_start": equilibrium.metrics,
        "authority_probes": [case.metrics for case in probes],
        "rerun_gate": {
            "bed_start_stable_at_requested_terminal": bed_ready,
            "probe_postures_remain_representative": pose_ready,
            "bilateral_authority_has_correct_sign_both_directions": bidirectional_authority,
            "bilateral_interface_deformation_not_majority_of_motion": deformation_not_dominant,
            "no_force_veto": force_gate,
            "rerun_ready": rerun_ready,
        },
        "full_2_to_30_to_2_motion_status": full_motion_status,
        "q_switch_sensitivity": "NOT_RUN_BY_SCOPE",
    }
    write_m15_artifacts(output_dir, equilibrium, probes, summary)

    print(f"OUTPUT_DIR={output_dir}")
    print(f"BED_START={equilibrium.metrics['classification']}")
    print(f"RERUN_READY={rerun_ready}")
    print(f"FULL_MOTION={full_motion_status}")
    for interface in INTERFACES:
        selected = [case.metrics for case in probes if case.metrics["interface"] == interface]
        authority = [case["effective_delta_q2_deg_per_mm"] for case in selected]
        absorption = [case["motion_absorbed_by_interface_ratio"] for case in selected]
        print(
            f"INTERFACE={interface} "
            f"authority_range=[{min(authority):.6g},{max(authority):.6g}]deg/mm "
            f"absorption_range=[{min(absorption):.6g},{max(absorption):.6g}]"
        )


if __name__ == "__main__":
    main()
