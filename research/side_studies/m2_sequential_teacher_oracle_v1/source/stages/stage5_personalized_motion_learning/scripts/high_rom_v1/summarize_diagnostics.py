"""Extract sampled ROM, CR12 joint margins and unchanged soft-limit loads."""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from summarize_phase_b import DOC, STAGE


def main() -> None:
    xml = ET.parse(STAGE / "models/cr12_v0.xml")
    limits = np.array([[float(v) for v in xml.find(f".//joint[@name='joint{i}']").attrib["range"].split()]
                       for i in range(1, 7)])
    groups = {}
    for label, file_name, hard_deg in (
        ("high_rom", "PHASE_B_RESULTS.json", (125., 125.)),
        ("low_rom", "PHASE_B_LOW_ROM_RESULTS.json", (80., 100.)),
    ):
        rows = json.loads((DOC / file_name).read_text())["rows"]
        details = []
        for row in rows:
            path = Path(row["output"])
            with np.load(path / "trace.npz") as z:
                mask = z["stage"] == "TASK"
                q = z["evaluation_only_human_state_rad_rad_s"][mask, :2]
                dq = z["evaluation_only_human_state_rad_rad_s"][mask, 2:]
                robot = z["cr12_q_rad"]
            upper = np.radians(np.array(hard_deg) - 5.) + 1e-9
            lower = np.radians((5., 5.)) - 1e-9
            zhi = np.maximum((q - upper) / math.radians(5.), 0.)
            zlo = np.maximum((lower - q) / math.radians(5.), 0.)
            torque = 25. * (zhi ** 3 - zlo ** 3)
            torque += 2. * (zhi ** 2 * np.maximum(dq, 0.) - zlo ** 2 * np.maximum(-dq, 0.))
            margin = np.minimum(robot - limits[:, 0], limits[:, 1] - robot)
            summary = json.loads((path / "summary.json").read_text())
            ages = [r["activation_age_ms"] for r in summary["timing"]["requests"]
                    if r.get("activation_age_ms") is not None]
            details.append(dict(case_key=row["case_key"], output=str(path),
                                minimum_sampled_cr12_joint_limit_margin_deg=float(np.degrees(np.min(margin))),
                                maximum_sampled_human_q_deg=np.degrees(np.max(q, axis=0)).tolist(),
                                minimum_sampled_human_hard_limit_margin_deg=float(np.min(np.array(hard_deg) - np.degrees(q))),
                                maximum_sampled_absolute_soft_limit_torque_nm=float(np.max(np.abs(torque))),
                                maximum_all_stage_plan_activation_age_ms=float(max(ages))))
        groups[label] = dict(rom_hard_deg=list(hard_deg), rows=details,
                             minimum_sampled_cr12_joint_limit_margin_deg=min(d["minimum_sampled_cr12_joint_limit_margin_deg"] for d in details),
                             minimum_sampled_human_hard_limit_margin_deg=min(d["minimum_sampled_human_hard_limit_margin_deg"] for d in details),
                             maximum_sampled_absolute_soft_limit_torque_nm=max(d["maximum_sampled_absolute_soft_limit_torque_nm"] for d in details),
                             maximum_all_stage_plan_activation_age_ms=max(d["maximum_all_stage_plan_activation_age_ms"] for d in details))
    target = DOC / "PHASE_B_DIAGNOSTICS.json"
    target.write_text(json.dumps(dict(schema="high_rom_v1_phase_b_sampled_diagnostics",
                                      cr12_joint_limits_source="models/cr12_v0.xml",
                                      soft_limit_law_source="stage3_full3d/src/traction_mpc_stage3/human.py:soft_limit_torque",
                                      high_rom=groups["high_rom"], low_rom=groups["low_rom"]), indent=2) + "\n")
    print(json.dumps({label: {k: groups[label][k] for k in (
        "minimum_sampled_cr12_joint_limit_margin_deg", "minimum_sampled_human_hard_limit_margin_deg",
        "maximum_sampled_absolute_soft_limit_torque_nm", "maximum_all_stage_plan_activation_age_ms")}
                      for label in groups}))


if __name__ == "__main__":
    main()
