#!/usr/bin/env python3
"""Seal the exact Phase-1B-F architecture and evidence hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    stage5 = Path("stages/stage5_personalized_motion_learning")
    roots = (
        Path("stages/stage3_full3d/src/traction_mpc_stage3"),
        Path("stages/stage4_adaptive_control/src/traction_mpc_stage4"),
        stage5 / "src/traction_mpc_stage5/architecture_recovery_v2",
    )
    paths = [path for root in roots for path in sorted(root.glob("*.py"))]
    paths.extend(
        [
            stage5 / "scripts/architecture_recovery_v2/run_functional_campaign.py",
            stage5 / "scripts/architecture_recovery_v2/phase1bf/analyze_freeze_evidence.py",
            stage5 / "scripts/architecture_recovery_v2/phase1bf/verify_phase2_logging_equivalence.py",
            Path(__file__).resolve(),
            stage5 / "configs/architecture_recovery_v2/phase1bf/freeze_qualification_v2.json",
            stage5 / "configs/architecture_recovery_v2/phase1bf/continual_adaptation_ablation_v3.json",
            stage5 / "docs/architecture_recovery_v2/phase1bf/CONTRACT_AMENDMENT_V2.md",
            stage5 / "docs/architecture_recovery_v2/phase1bf/GATE_ADDENDUM_V1.md",
            stage5 / "docs/architecture_recovery_v2/phase1bf/TRACE_ADDENDUM_V1.md",
            stage5 / "docs/architecture_recovery_v2/phase1bf/FRAGILITY_AUDIT_V1.md",
            stage5 / "docs/architecture_recovery_v2/phase1bf/HARDWARE_TRANSFER_RISK_LEDGER_V1.md",
            stage5 / "docs/architecture_recovery_v2/phase1bf/FREEZE_CANDIDATE_V1.md",
        ]
    )
    evidence = [
        stage5
        / "results/architecture_recovery_v2/phase1bf/freeze_qualification_v2/result.json",
        stage5
        / "results/architecture_recovery_v2/phase1bf/continual_adaptation_ablation_v3/result.json",
        stage5
        / "results/architecture_recovery_v2/phase1bf/freeze_evidence_audit_v1/audit.json",
        stage5
        / "results/architecture_recovery_v2/phase1bf/phase2_logging_equivalence_v1/result.json",
    ]
    status = subprocess.run(
        ["git", "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    payload = {
        "schema": "architecture_recovery_v2.phase1bf.freeze_manifest.v1",
        "status": "PHASE_1B_F_FROZEN",
        "scope": "conditional_planar_human_v2_simulation",
        "git_branch": subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "git_status_short_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "architecture_and_contract_sha256": {
            str(path): sha256(path) for path in paths
        },
        "freeze_evidence_sha256": {str(path): sha256(path) for path in evidence},
        "prohibitions": {
            "architecture_tuning_before_phase2": True,
            "deployable_hidden_truth": True,
            "held_out_seed_reuse": True,
            "hardware_readiness_claim": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
