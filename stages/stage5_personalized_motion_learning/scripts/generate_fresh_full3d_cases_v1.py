"""Generate fixed pre-outcome setup/task cases and retain every proposal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage5.fresh_qualification_v1.domain import canonical_json_hash, generate_cases


def _write_new(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-manifest", type=Path)
    parser.add_argument("--development-seed", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.seed_manifest is None) == (args.development_seed is None):
        parser.error("provide exactly one seed source")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(args.output)
    if args.seed_manifest is not None:
        seed_record = json.loads(args.seed_manifest.read_text(encoding="utf-8"))
        seed = int(seed_record["root_seed_uint64"])
    else:
        seed = args.development_seed
    cases, proposals = generate_cases(seed)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "cases").mkdir()
    for case in cases:
        _write_new(args.output / "cases" / f"{case['case_key']}.json", case)
    _write_new(args.output / "proposals.json", proposals)
    _write_new(args.output / "generation_summary.json", {
        "schema": "fresh_full3d_case_generation_v1", "seed": seed,
        "accepted_case_count": len(cases), "proposal_count": len(proposals),
        "rejection_count": len(proposals) - len(cases),
        "acceptance_fraction": len(cases) / len(proposals),
        "case_keys": [case["case_key"] for case in cases],
        "accepted_cases_canonical_sha256": canonical_json_hash(cases),
        "proposal_ledger_canonical_sha256": canonical_json_hash(proposals),
    })
    print(json.dumps({"accepted": len(cases), "proposals": len(proposals),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
