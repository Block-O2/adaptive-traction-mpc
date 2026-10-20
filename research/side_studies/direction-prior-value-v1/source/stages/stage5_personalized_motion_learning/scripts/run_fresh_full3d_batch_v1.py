"""Restart-safe paired full-physics execution after the independent freeze."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import traceback

from freeze_fresh_full3d_v1 import DOC, REPO
from traction_mpc_stage5.fresh_qualification_v1.domain import canonical_json_hash, generate_cases
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


ARMS = ("continual_adaptive", "commissioning_only", "fixed_population")
REQUIRED = ("summary.json", "trace.npz", "config_snapshot.json",
            "learning_transitions.jsonl")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_checkpoint(path: Path, record: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _verify_freeze() -> dict:
    freeze = json.loads((DOC / "FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    subprocess = __import__("subprocess")
    if freeze["branch"] != subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=REPO, text=True).strip():
        raise RuntimeError("branch changed after freeze")
    if freeze["head"] != subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip():
        raise RuntimeError("HEAD changed after freeze")
    for name, expected in freeze["source_config_asset_sha256"].items():
        if _hash(REPO / name) != expected:
            raise RuntimeError(f"frozen dependency changed: {name}")
    return freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new-arms", type=int)
    args = parser.parse_args()
    freeze = _verify_freeze()
    generation = json.loads((args.case_bundle / "generation_summary.json").read_text())
    seed_record = json.loads((DOC / "SEED_MANIFEST.json").read_text(encoding="utf-8"))
    if generation["seed"] != int(seed_record["root_seed_uint64"]):
        raise RuntimeError("case bundle seed does not match independent formal seed")
    if generation["accepted_case_count"] != 24:
        raise ValueError("frozen case count is not 24")
    keys = generation["case_keys"]
    if len(set(keys)) != 24:
        raise ValueError("duplicate case keys")
    case_files = [args.case_bundle / "cases" / f"{key}.json" for key in keys]
    case_records = [json.loads(path.read_text(encoding="utf-8")) for path in case_files]
    if [case["case_key"] for case in case_records] != keys or canonical_json_hash(
        case_records) != generation["accepted_cases_canonical_sha256"]:
        raise RuntimeError("case JSON files disagree with pre-outcome generation seal")
    proposal_records = json.loads((args.case_bundle / "proposals.json").read_text(encoding="utf-8"))
    if canonical_json_hash(proposal_records) != generation["proposal_ledger_canonical_sha256"]:
        raise RuntimeError("proposal ledger changed after mechanical screening")
    regenerated_cases, regenerated_proposals = generate_cases(int(seed_record["root_seed_uint64"]))
    if (canonical_json_hash(regenerated_cases) != generation["accepted_cases_canonical_sha256"]
            or canonical_json_hash(regenerated_proposals) != generation["proposal_ledger_canonical_sha256"]):
        raise RuntimeError("formal cases do not regenerate from sealed seed and frozen source")
    case_hashes = [_hash(path) for path in case_files]
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output / "STATUS.json"
    checkpoint = (json.loads(checkpoint_path.read_text()) if checkpoint_path.exists()
                  else {"phase": "FORMAL_RUNNING", "branch": freeze["branch"],
                        "head": freeze["head"],
                        "seed_manifest_sha256": _hash(DOC / "SEED_MANIFEST.json"),
                        "generation_summary_sha256": _hash(args.case_bundle / "generation_summary.json"),
                        "remaining_case_keys": keys, "completed": {}})
    if checkpoint["generation_summary_sha256"] != _hash(args.case_bundle / "generation_summary.json"):
        raise RuntimeError("case bundle changed after first formal arm")
    if checkpoint["seed_manifest_sha256"] != _hash(DOC / "SEED_MANIFEST.json"):
        raise RuntimeError("formal seed manifest changed after first formal arm")
    if checkpoint["branch"] != freeze["branch"] or checkpoint["head"] != freeze["head"]:
        raise RuntimeError("Git provenance changed after first formal arm")
    _write_checkpoint(checkpoint_path, checkpoint)
    completed_this_call = 0
    for index, key in enumerate(keys):
        case_path = args.case_bundle / "cases" / f"{key}.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        if case["case_key"] != key:
            raise ValueError("case key/path mismatch")
        if _hash(case_path) != case_hashes[index]:
            raise RuntimeError("case file changed during batch")
        for previous_arm in ARMS:
            previous = checkpoint["completed"].get(f"{key}/{previous_arm}")
            if previous is not None and previous["case_sha256"] != _hash(case_path):
                raise RuntimeError(f"paired arms do not share the same physical case: {key}")
        order = ARMS[index % 3:] + ARMS[:index % 3]
        for arm in order:
            _verify_freeze()
            output = args.output / key / arm
            if output.exists() and any(output.iterdir()):
                if all((output / name).exists() for name in REQUIRED):
                    hashes = {name: _hash(output / name) for name in REQUIRED}
                    earlier = checkpoint["completed"].get(f"{key}/{arm}")
                    if earlier is not None and earlier["artifact_sha256"] != hashes:
                        raise RuntimeError(f"completed artifact changed: {key}/{arm}")
                    if earlier is not None and earlier["case_sha256"] != _hash(case_path):
                        raise RuntimeError(f"completed case snapshot changed: {key}/{arm}")
                    checkpoint["completed"][f"{key}/{arm}"] = {
                        "classification": "episode_artifacts_complete", "artifact_sha256": hashes,
                        "case_sha256": _hash(case_path)}
                    _write_checkpoint(checkpoint_path, checkpoint)
                    continue
                if (output / "runner_exception.json").exists():
                    exception_hash = _hash(output / "runner_exception.json")
                    earlier = checkpoint["completed"].get(f"{key}/{arm}")
                    if (earlier is not None and earlier["artifact_sha256"] !=
                            {"runner_exception.json": exception_hash}):
                        raise RuntimeError(f"preserved failure artifact changed: {key}/{arm}")
                    checkpoint["completed"][f"{key}/{arm}"] = {
                        "classification": "preserved_runner_exception",
                        "artifact_sha256": {"runner_exception.json": exception_hash},
                        "case_sha256": _hash(case_path)}
                    _write_checkpoint(checkpoint_path, checkpoint)
                    continue
                raise RuntimeError(f"incomplete interrupted arm requires inspection: {output}")
            checkpoint["active_case_key"] = key
            checkpoint["active_arm"] = arm
            _write_checkpoint(checkpoint_path, checkpoint)
            try:
                run_executed_case(output, qualification_case=case,
                    qualification_arm=arm, simulate_planning_latency=True,
                    formal_qualification=True)
            except Exception as error:
                output.mkdir(parents=True, exist_ok=True)
                (output / "runner_exception.json").write_text(json.dumps({
                    "case_key": key, "arm": arm, "case_sha256": _hash(case_path),
                    "error": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc(),
                }, indent=2) + "\n", encoding="utf-8")
                checkpoint["completed"][f"{key}/{arm}"] = {
                    "classification": "preserved_runner_exception",
                    "artifact_sha256": {"runner_exception.json": _hash(output / "runner_exception.json")},
                    "case_sha256": _hash(case_path)}
            else:
                if not all((output / name).exists() for name in REQUIRED):
                    raise RuntimeError(f"runner returned without complete artifacts: {output}")
                checkpoint["completed"][f"{key}/{arm}"] = {
                    "classification": "episode_artifacts_complete",
                    "artifact_sha256": {name: _hash(output / name) for name in REQUIRED},
                    "case_sha256": _hash(case_path)}
            checkpoint.pop("active_case_key", None)
            checkpoint.pop("active_arm", None)
            checkpoint["remaining_case_keys"] = [case_key for case_key in keys
                if not all(f"{case_key}/{a}" in checkpoint["completed"] for a in ARMS)]
            _write_checkpoint(checkpoint_path, checkpoint)
            completed_this_call += 1
            print(json.dumps({"case_key": key, "arm": arm,
                              "classification": checkpoint["completed"][f"{key}/{arm}"]["classification"],
                              "remaining_arms": 72 - len(checkpoint["completed"])}, sort_keys=True),
                  flush=True)
            if args.max_new_arms is not None and completed_this_call >= args.max_new_arms:
                return
    checkpoint["phase"] = "FORMAL_ALL_ARMS_COMPLETED"
    _write_checkpoint(checkpoint_path, checkpoint)


if __name__ == "__main__":
    main()
