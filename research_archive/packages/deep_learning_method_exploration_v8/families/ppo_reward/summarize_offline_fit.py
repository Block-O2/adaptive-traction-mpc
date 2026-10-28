"""Read approved fit outputs; no model update or physical API."""
from pathlib import Path
import hashlib
import json
import math
import time

HERE = Path(__file__).resolve().parent
RUN = HERE / "offline_fit_v2"
ROOT = HERE.parents[1]


def put(p, x):
    p.write_text(json.dumps(x, sort_keys=True, indent=2, allow_nan=False))


def main():
    start = time.time()
    summary = json.loads((RUN / "RESULTS.json").read_text())
    table = json.loads((ROOT / "families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json").read_text())
    context = {r["group"]: r["context"]["features"] for r in table["rows"]}
    by_group = {}
    for r in table["rows"]:
        by_group.setdefault(r["group"], {})[r["action_recipe_sha256"]] = r
    hashes = summary["action_full_recipe_sha256"]
    aggregate = {}
    deployed = {}
    gradient = {}
    for objective, data in summary["objectives"].items():
        folds = [f for name, f in data["folds"].items() if name.startswith("LEAVE_OUT_")]
        agg = {}
        for source in ("baselines", "models"):
            for method in folds[0][source]:
                rows = []
                for fold in folds:
                    item = fold[source][method]
                    rows.extend(item if isinstance(item, list) else item["evaluation"])
                agg[method] = {"selected_actions": [r["selected_action_index"] for r in rows],
                               "qualified_count": sum(r["original_qualified"] for r in rows), "total_contexts": len(rows),
                               "table_reward_sum": sum(r["table_reward"] for r in rows),
                               "delta_JF_sum_among_originally_qualified": sum(r["delta_JF_vs_B_N_s"] for r in rows if r["original_qualified"]),
                               "delta_JM_sum_among_originally_qualified": sum(r["delta_JM_vs_B_Nm_s"] for r in rows if r["original_qualified"]),
                               "partial_or_unqualified_cost_excluded_from_success_sum": True}
        aggregate[objective] = agg
        full = data["folds"]["ALL_EXPOSED_DEVELOPMENT"]
        rules = full["simple_rules"]
        deployed[objective] = {"rules": rules,
                               "models": {k: {f: v[f] for f in ("checkpoint", "checkpoint_sha256", "behavior_sha256")} for k, v in full["models"].items()},
                               "action_full_recipe_sha256": hashes,
                               "training_data_scope": "ALL_EXPOSED_DEVELOPMENT_ONLY"}
        norm = rules["nearest"]["normalization"]
        parts = {name: [[0.0] * 26 for _ in range(3)] for name in ("unqualified_floor", "qualified_reward")}
        count = {name: 0 for name in parts}
        for group, rewards in data["reward_table_evaluation_only"].items():
            x = [1.0] + [(v-m)/s for v,m,s in zip(context[group],norm["mean"],norm["scale"])]
            for action, reward in enumerate(rewards):
                row = by_group[group][hashes[action]]
                part = "qualified_reward" if row["eligible_for_success_ranking"] else "unqualified_floor"
                count[part] += 1
                for i in range(3):
                    coefficient = reward * ((1.0 if i == action else 0.0) - 1/3) / 18
                    for j in range(26):
                        parts[part][i][j] += coefficient * x[j]
        norms = {k: math.sqrt(sum(x*x for row in v for x in row)) for k,v in parts.items()}
        dot = sum(x*y for r,s in zip(parts["unqualified_floor"],parts["qualified_reward"]) for x,y in zip(r,s))
        gradient[objective] = {"definition": "Analytic expected uniform categorical objective gradient over existing 18 labels, all-context train normalization; no forward/backward/update API",
                               "row_counts": count, "gradient_norms": norms,
                               "unqualified_to_qualified_norm_ratio": None if norms["qualified_reward"] == 0 else norms["unqualified_floor"] / norms["qualified_reward"],
                               "gradient_cosine": None if min(norms.values()) == 0 else dot/(norms["unqualified_floor"]*norms["qualified_reward"]),
                               "failure_floor_unique_cause_established": False}
    put(RUN / "DEVELOPMENT_CV_AGGREGATE.json", aggregate)
    put(RUN / "FROZEN_RULES_AND_MODELS.json", deployed)
    put(RUN / "REWARD_GRADIENT_DECOMPOSITION.json", gradient)
    checkpoints = list((RUN / "checkpoints").rglob("*.json"))
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoints if "ALL_EXPOSED_DEVELOPMENT" in p.parts}
    for p in (RUN / "ACTION_MENU.json", RUN / "FROZEN_RULES_AND_MODELS.json", HERE / "categorical_policy.py"):
        manifest[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    put(RUN / "DEPLOYMENT_API_FREEZE.json", {"frozen_unix": time.time(), "files": manifest,
                                             "feature_order": next(r for r in table["rows"])["context"]["feature_names"],
                                             "action_full_recipe_sha256": hashes, "new_test_results_used": False,
                                             "API": "categorical_policy.select_out0(policy,feature_names,commissioned_values,qa_validated=True)",
                                             "rule_tie_order": "training contexts sorted lexical only as fixed tie metadata; no case or group fed as feature"})
    put(RUN / "SUMMARY_OPERATION.json", {"wall_s": time.time()-start, "new_fits": 0, "model_forward": 0, "model_backward": 0, "parameter_updates": 0, "physics": 0})
    print(json.dumps({"reward_gradient": gradient, "all_exposed_stump": deployed["qualified_force_raw"]["rules"]["stump"], "outputs": ["DEVELOPMENT_CV_AGGREGATE.json", "FROZEN_RULES_AND_MODELS.json", "REWARD_GRADIENT_DECOMPOSITION.json", "DEPLOYMENT_API_FREEZE.json"]}))


if __name__ == "__main__":
    main()
