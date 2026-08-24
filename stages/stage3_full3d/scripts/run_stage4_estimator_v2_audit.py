from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.estimator_v2_audit import run_estimator_v2_observability_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = run_estimator_v2_observability_audit()
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
