"""Read-only frozen argmax/API replay. No learning or physical API."""
from pathlib import Path
import hashlib
import json
import sys
import time

sys.dont_write_bytecode = True
from categorical_policy import select_out0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "offline_fit_v2"


def main():
    start = time.time()
    manifest = json.loads((RUN / "DEPLOYMENT_API_FREEZE.json").read_text())
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in manifest["files"]}
    assert before == manifest["files"]
    dataset = json.loads((ROOT / "families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json").read_text())
    contexts = {r["group"]: r["context"] for r in dataset["rows"]}
    passes = []
    forwards = 0
    for path in manifest["files"]:
        if "/checkpoints/" not in path:
            continue
        document = json.loads((ROOT / path).read_text())
        policy = document["policy"]
        for row in document["evaluation"]:
            ctx = contexts[row["context_group_evaluation_only"]]
            result = select_out0(policy, ctx["feature_names"], ctx["features"], qa_validated=True)
            forwards += 1
            assert result["action_index"] == row["selected_action_index"]
            assert result["full_recipe_sha256"] == row["selected_full_recipe_sha256"]
            assert result["full_recipe_sha256"] in manifest["action_full_recipe_sha256"]
            assert result["proposal_action"] == result["action"]["action"]
            assert result["original_qualification_granted"] is False
        passes.append(path)
    policy = document["policy"]
    ctx = next(iter(contexts.values()))
    rejected = []
    for name, names, values, qa in (("QA_FALSE", ctx["feature_names"], ctx["features"], False),
                                     ("WRONG_ORDER", list(reversed(ctx["feature_names"])), ctx["features"], True),
                                     ("NAN_FEATURE", ctx["feature_names"], [float('nan')] + ctx["features"][1:], True)):
        try:
            select_out0(policy, names, values, qa_validated=qa)
            raise AssertionError("INVALID_INPUT_NOT_REJECTED:" + name)
        except ValueError:
            rejected.append(name)
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in manifest["files"]}
    assert after == before
    result = {"status": "PASS", "frozen_models": len(passes), "argmax_context_replays": forwards,
              "schema_rejections": rejected, "input_and_models_unchanged": True,
              "model_forward_api": forwards, "model_backward": 0, "parameter_updates": 0,
              "new_physics": 0, "fresh_on_policy_rollouts": 0, "wall_s": time.time()-start}
    (RUN / "DEPLOYMENT_API_CHECK.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
