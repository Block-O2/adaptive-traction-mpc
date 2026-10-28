#!/usr/bin/env python3
"""Replay a real archived context through an already trained, frozen Value API.

No fit/update, RNG draw, MuJoCo import or physics. This is an interface smoke,
using a training context; it is not an independent test or physical qualification.
Run with the archive's fresh scientific environment, for example:
  python -B tools/check_learning_interface.py --repo . --output /tmp/value-smoke-001
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

PACKAGE = Path("research_archive/packages/deep_learning_method_exploration_v8")
FAMILY = PACKAGE / "families/critic_value"
PINS = {
    "model": "5642ff8e36199e85e734daa81af24f039827b5f3f4369e5e3d268b742122c905",
    "source": "9803755f97cf772cff58c38c31931ff3ec22949de3dc8b7e7f248a41bd254f23",
    "fixture": "569ddd3dfe95e109158f9c7bd8c39198fdd1c363fa815df69bfc48a771d1fcd5",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="A new output directory; existing directories are rejected.")
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": "ihear.archive.learning_interface_smoke.v1",
        "status": "FAIL",
        "scope": "ARCHIVED_TRAINING_CONTEXT_INTERFACE_REPLAY",
        "new_training_updates": 0,
        "new_physics_steps": 0,
        "independent_generalization_test": False,
        "physical_task_qualification": "NOT_RUN",
        "risk_is_safety_certificate": False,
    }
    try:
        paths = {
            "model": repo / FAMILY / "models/VALUE_FAMILY_V1_FROZEN.json",
            "source": repo / FAMILY / "source/value_api.py",
            "fixture": repo / "deployment/fixtures/v8_commissioned25_context.json",
        }
        result["artifacts"] = {}
        for key, path in paths.items():
            digest = sha(path)
            if digest != PINS[key]:
                raise RuntimeError("FROZEN_ARTIFACT_SHA256_MISMATCH: " + key)
            result["artifacts"][key] = {"path": str(path.relative_to(repo)),
                                        "sha256": digest, "bytes": path.stat().st_size}
        bundle = json.loads(paths["model"].read_text())
        fixture = json.loads(paths["fixture"].read_text())
        if bundle["schema"] != "v8.value_family_frozen.v1":
            raise RuntimeError("WRONG_FROZEN_MODEL_SCHEMA")
        if fixture["provenance"]["source_group"] not in bundle["train_contexts"]:
            raise RuntimeError("TRAINING_CONTEXT_PROVENANCE_MISMATCH")
        if not any(abs(float(value)) > 1e-12
                   for member in bundle["methods"]["ABS_25"]["cost_weights"]
                   for row in member for value in row):
            raise RuntimeError("MODEL_HAS_NO_NONZERO_TRAINED_COST_WEIGHTS")
        spec = importlib.util.spec_from_file_location("ihear_archived_value_api", paths["source"])
        if spec is None or spec.loader is None:
            raise RuntimeError("CANNOT_LOAD_ORIGINAL_VALUE_API")
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        context = api.to_context25(fixture["context"])
        if len(context["features"]) != 25 or context["feature_names"] != api.FEATURE_NAMES:
            raise RuntimeError("INVALID_ORIGINAL_INPUT_SCHEMA")
        decisions = {}
        for objective in ("JF_QUALIFIED", "STRICT_JM"):
            decision = api.predict(bundle, context, method="ABS_25", objective=objective)
            if len(decision["predictions"]) != len(bundle["menu"]):
                raise RuntimeError("PREDICTION_MENU_INCOMPLETE")
            if decision["future_qualification_mask_used"] is not False:
                raise RuntimeError("FUTURE_QUALIFICATION_MASK_NOT_ALLOWED")
            if decision["risk_is_calibrated_or_safety_certificate"] is not False:
                raise RuntimeError("UNSUPPORTED_SAFETY_CLAIM")
            decision["abstained"] = decision["choice_tag"] is None
            decisions[objective] = decision
        result.update(
            status="PASS_INTERFACE_ONLY",
            input_shape=[25],
            input_feature_names=context["feature_names"],
            original_77d_valid=context["legacy77d_valid"],
            archived_context_provenance=fixture["provenance"],
            checkpoint_schema=bundle["schema"],
            checkpoint_frozen_unix=bundle["frozen_unix"],
            method="ABS_25",
            trained_model_loaded=True,
            predictions=decisions,
            inference_calls=2,
            runtime={"python": sys.version.split()[0],
                     "numpy": api.np.__version__},
            interpretation="Original frozen model actually predicted and selected/abstained; "
                           "no physical qualification, control superiority or generalization is tested.",
        )
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["traceback"] = traceback.format_exc()
    (output / "RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "output": str(output / "RESULT.json"),
                      "input_shape": result.get("input_shape"),
                      "choices": {k: v["choice_tag"] for k, v in result.get("predictions", {}).items()},
                      "new_training_updates": 0, "new_physics_steps": 0}, ensure_ascii=False))
    return 0 if result["status"] == "PASS_INTERFACE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
