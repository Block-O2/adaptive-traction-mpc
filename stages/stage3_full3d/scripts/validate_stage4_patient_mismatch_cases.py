from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.patient_mismatch import (
    CASE_SCHEMA_VERSION,
    FROZEN_SHARED_AB_CONTRACT,
    load_patient_case_specs,
    paired_arm_contracts,
    patient_case_record,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construct and validate preregistered Stage-4 patient cases."
    )
    parser.add_argument(
        "--case-config",
        type=Path,
        default=Path("configs/stage4_patient_mismatch_cases.json"),
    )
    args = parser.parse_args()
    specs = load_patient_case_specs(args.case_config)
    records = [patient_case_record(spec) for spec in specs]
    invalid = [item["case_id"] for item in records if not item["physically_valid"]]
    outside_bounds = [
        item["case_id"]
        for item in records
        if not item["representability"]["inside_current_estimator_box"]
    ]
    if invalid or outside_bounds:
        raise RuntimeError(
            f"invalid cases={invalid}; outside estimator bounds={outside_bounds}"
        )
    payload = {
        "schema_version": CASE_SCHEMA_VERSION,
        "full_experiment_executed": False,
        "case_count": len(records),
        "shared_ab_contract": FROZEN_SHARED_AB_CONTRACT,
        "paired_arm_contracts": {
            item["case_id"]: paired_arm_contracts(item["case_id"])
            for item in records
        },
        "case_records": records,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
