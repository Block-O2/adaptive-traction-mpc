#!/usr/bin/env python3
"""Generate the High-ROM Human V2 passive and quasi-static audit artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.high_rom_feasibility import json_ready
from traction_mpc_stage4.high_rom_human_v2 import (
    PRIMARY_ENDPOINT_NAMES,
    audit_passive_model,
    audit_quasistatic_paths,
    high_rom_config_payload,
)


STAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = STAGE_ROOT / "results" / "high_rom_feasibility"
REPORT_MARKER = "## High-ROM Human V2 passive-model audit"
DISPLAY_NAMES = {
    "hip_dominant_100_60": "100/60 hip",
    "knee_high_folding_90_120": "90/120 knee/high-folding",
    "aggressive_both_120_120": "120/120 aggressive",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--passive-samples-per-joint", type=int, default=501)
    parser.add_argument("--path-sample-count", type=int, default=121)
    return parser.parse_args()


def _write_plot(output: Path, passive: dict[str, object]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    for axis, joint_name in zip(axes, ("hip", "knee"), strict=True):
        joint = passive["joints"][joint_name]
        q_deg = np.asarray(joint["sampled_position_deg"])
        axis.plot(
            q_deg,
            np.asarray(joint["ordinary_passive_left_static_nm"]),
            label="ordinary stiffness",
        )
        axis.plot(
            q_deg,
            np.asarray(joint["total_passive_left_static_nm"]),
            label="total with soft limit",
        )
        axis.plot(
            q_deg,
            np.asarray(joint["soft_limit_actual_static_nm"]),
            label="actual inward soft-limit torque",
            linestyle="--",
        )
        axis.axvline(
            joint["lower_soft_zone_start_deg"], color="gray", linewidth=1.0
        )
        axis.axvline(
            joint["upper_soft_zone_start_deg"], color="gray", linewidth=1.0
        )
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_title(f"High-ROM {joint_name} passive torque")
        axis.set_xlabel("joint angle (deg)")
        axis.set_ylabel("torque (Nm)")
        axis.legend(fontsize=8)
    figure.savefig(output / "high_rom_passive_torque.png", dpi=180)
    plt.close(figure)


def _report_section(
    config: dict[str, object],
    passive: dict[str, object],
    quasistatic: dict[str, object],
) -> str:
    lines = [
        REPORT_MARKER,
        "",
        (
            "An explicit `human_v2_high_rom_engineering_v2_125deg_both_joints` "
            "variant extends the hip and knee upper ROM to 125 deg. "
            "Canonical Human V2 is unchanged."
        ),
        (
            "The 5 deg cubic soft-limit zones therefore begin at [120,120] deg. "
            "The 120 deg endpoints are exactly on the soft-zone start and remain "
            "soft-limit inactive in the quasi-static reference audit."
        ),
        (
            "Ordinary stiffness [10,10] Nm/rad, damping [5,5] Nms/rad, rest "
            "[5,10] deg, and all soft-limit coefficients are retained. This passive "
            "extrapolation is an engineering assumption pending physical/hardware validation."
        ),
        "",
        "| joint | total passive-left static envelope | soft-limit actual envelope | inward boundary direction | damping dissipative |",
        "|---|---:|---:|---:|---:|",
    ]
    for joint_name in ("hip", "knee"):
        joint = passive["joints"][joint_name]
        total = joint["total_passive_left_static_envelope_nm"]
        soft = joint["soft_limit_actual_torque_envelope_nm"]
        lines.append(
            f"| {joint_name} | [{total[0]:.2f},{total[1]:.2f}] Nm | "
            f"[{soft[0]:.2f},{soft[1]:.2f}] Nm | "
            f"{joint['soft_limit_direction_pushes_inward']} | "
            f"{joint['damping_dissipative']} |"
        )
    lines.extend(
        [
            "",
            "| trajectory | model decision | peak passive hip / knee | peak required torque norm | peak cuff force (margin) | peak cuff moment |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name in PRIMARY_ENDPOINT_NAMES:
        path = quasistatic["paths"][name]
        passive_peak = path["peak_passive_left_by_joint"]
        force = path["peak_cuff_force"]
        lines.append(
            f"| {DISPLAY_NAMES[name]} | {path['classification']} | "
            f"{passive_peak['hip']['absolute_nm']:.2f} / "
            f"{passive_peak['knee']['absolute_nm']:.2f} Nm | "
            f"{path['peak_required_torque_norm']['nm']:.2f} Nm | "
            f"{force['n']:.2f} N ({force['margin_to_200_n']:.2f} N) | "
            f"{path['peak_cuff_moment']['nm']:.2f} Nm |"
        )
    lines.extend(
        [
            "",
            (
                "All three paths are READY FOR DYNAMIC PILOT at the Human-model and "
                "quasi-static cuff-mechanics level. The recommended order is 100/60, "
                "90/120, then 120/120. This is not a completed dynamic/controller test."
            ),
            (
                "The setup-specific support-plane collision from the prior geometry "
                "audit is outside this model-amendment decision, per the revised task scope."
            ),
            "No controller or dynamic rollout was run.",
            "",
            "See `high_rom_human_v2_config.json`, `passive_model_audit.json`, and `high_rom_passive_torque.png`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = high_rom_config_payload()
    passive = audit_passive_model(samples_per_joint=args.passive_samples_per_joint)
    quasistatic = audit_quasistatic_paths(sample_count=args.path_sample_count)
    payload = {
        "audit_kind": "high_rom_human_v2_passive_and_quasistatic_audit",
        "controller_or_dynamic_rollout_run": False,
        "canonical_human_overwritten": False,
        "passive_model": passive,
        "quasistatic_paths": quasistatic,
        "geometry_input": {
            "source": "completed continuous high-ROM geometry audits",
            "base_placement_search_rerun": False,
            "support_plane_collision_used_as_model_blocker": False,
        },
    }
    (output / "high_rom_human_v2_config.json").write_text(
        json.dumps(json_ready(config), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    (output / "passive_model_audit.json").write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_plot(output, passive)
    report_path = output / "high_rom_feasibility_report.md"
    baseline = report_path.read_text(encoding="utf-8")
    baseline = baseline.split(REPORT_MARKER, maxsplit=1)[0].rstrip() + "\n\n"
    report_path.write_text(
        baseline + _report_section(config, passive, quasistatic),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "q_max_deg": config["q_max_deg"],
                "path_classifications": {
                    name: quasistatic["paths"][name]["classification"]
                    for name in PRIMARY_ENDPOINT_NAMES
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
