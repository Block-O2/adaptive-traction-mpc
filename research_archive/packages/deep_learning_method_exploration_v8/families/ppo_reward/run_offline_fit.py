"""Approved bounded historical-table diagnostics; NEVER fresh on-policy RL."""
from pathlib import Path
import copy
import hashlib
import json
import math
import os
import random
import signal
import sys
import time
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
from categorical_policy import initialize, choose, update, policy_sha256, digest, OFFLINE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json"
OUT = HERE / "offline_fit_v2"
PLAN = HERE / "OFFLINE_FIT_PLAN_V1.json"
TIMEOUT = 120
DEADLINE = None  # The original activation is loaded below; never reset.


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))
    temp.replace(path)


def normalize(groups, contexts):
    xs = [contexts[g]["features"] for g in groups]
    n = len(xs)
    means = [sum(x[j] for x in xs) / n for j in range(25)]
    scales = [math.sqrt(sum((x[j] - means[j]) ** 2 for x in xs) / n) for j in range(25)]
    return {"mean": means, "scale": [v if v >= 1e-9 else 1.0 for v in scales],
            "fit_scope": "TRAINING_CONTEXTS_ONLY", "training_groups_evaluation_metadata": list(groups)}


def feedback(row, base, objective):
    z = row["labels_evaluation_only"]
    b = base["labels_evaluation_only"]
    if z["complete"] is not True or z["original_qualified"] is not True:
        return -1.0
    if objective == "force_with_JM_nonincrease" and z["JM_Nm_s"] > b["JM_Nm_s"]:
        return -1.0
    component = "JM_Nm_s" if objective == "qualified_moment" else "JF_N_s"
    gain = 20.0 if objective == "qualified_force_scaled" else 1.0
    return max(-0.9, min(0.9, gain * (b[component] - z[component]) / max(abs(b[component]), 1.0)))


def select_teacher(group, table, objective):
    eligible = [i for i in range(3) if table[group][i]["eligible_for_success_ranking"]]
    if objective == "force_with_JM_nonincrease":
        eligible = [i for i in eligible if table[group][i]["labels_evaluation_only"]["JM_Nm_s"] <= table[group][0]["labels_evaluation_only"]["JM_Nm_s"]]
    key = "JM_Nm_s" if objective == "qualified_moment" else "JF_N_s"
    return min(eligible, key=lambda i: (table[group][i]["labels_evaluation_only"][key], i))


def simple_baselines(train, table, contexts, rewards, teachers, norm):
    const = max(range(3), key=lambda i: (sum(rewards[g][i] for g in train), -i))
    best = (-float("inf"), 0, 0.0, 0, 0)
    for feature in range(25):
        vals = sorted(set(contexts[g]["features"][feature] for g in train))
        thresholds = [(a + b) / 2 for a, b in zip(vals, vals[1:])]
        for threshold in thresholds:
            for left in range(3):
                for right in range(3):
                    score = sum(rewards[g][left if contexts[g]["features"][feature] <= threshold else right] for g in train)
                    if score > best[0] + 1e-15:
                        best = (score, feature, threshold, left, right)
    if best[0] == -float("inf"):
        best = (sum(rewards[g][const] for g in train), 0, 0.0, const, const)
    return {"constant_action_index": const,
            "stump": {"feature_index": best[1], "feature_name": contexts[train[0]]["feature_names"][best[1]], "threshold": best[2], "left_action_index": best[3], "right_action_index": best[4]},
            "nearest": {"training_contexts": [{"features": contexts[g]["features"], "teacher_action_index": teachers[g]} for g in train], "normalization": norm}}


def simple_select(kind, rules, features):
    if kind == "best_constant":
        return rules["constant_action_index"]
    if kind == "stump":
        t = rules["stump"]
        return t["left_action_index"] if features[t["feature_index"]] <= t["threshold"] else t["right_action_index"]
    n = rules["nearest"]
    distances = [sum(((a - b) / s) ** 2 for a, b, s in zip(features, r["features"], n["normalization"]["scale"])) for r in n["training_contexts"]]
    return n["training_contexts"][min(range(len(distances)), key=lambda i: (distances[i], i))]["teacher_action_index"]


def eval_row(group, action, table, rewards):
    r = table[group][action]
    z = r["labels_evaluation_only"]
    return {"context_group_evaluation_only": group, "selected_action_index": action,
            "selected_full_recipe_sha256": r["action_recipe_sha256"], "source_row_id": r["id"],
            "complete": z["complete"], "original_qualified": z["original_qualified"],
            "JF_N_s": z["JF_N_s"], "JM_Nm_s": z["JM_Nm_s"],
            "delta_JF_vs_B_N_s": z["delta_JF_vs_B_N_s"], "delta_JM_vs_B_Nm_s": z["delta_JM_vs_B_Nm_s"],
            "motion_failed_requirements": z["motion_failed_requirements"],
            "jerk_RMS_deg_s3": z["jerk_RMS_deg_s3"], "table_reward": rewards[group][action],
            "data_semantics": OFFLINE, "new_physics": 0}


def main():
    global DEADLINE
    if OUT.exists():
        raise RuntimeError("REFUSE_TO_OVERWRITE_EXISTING_FIT")
    OUT.mkdir()
    start = time.time()
    cpu = time.process_time()
    activation = json.loads((ROOT / "ACTIVATION.json").read_text())
    from datetime import datetime
    DEADLINE = datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if start >= DEADLINE - TIMEOUT:
        raise RuntimeError("INSUFFICIENT_GLOBAL_TIME")
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("LOCAL_120S_TIMEOUT")))
    signal.alarm(min(TIMEOUT, int(DEADLINE - start)))
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in (DATA, PLAN, Path(__file__), HERE / "categorical_policy.py", ROOT / "ACTIVATION.json")}
    put(OUT / "START.json", {"pid": os.getpid(), "proc_start_ticks": Path('/proc/self/stat').read_text().split()[21], "start_unix": start, "local_timeout_s": TIMEOUT, "hard_deadline_unix": DEADLINE, "inputs": inputs, "data_semantics": OFFLINE, "main_agent_approval": "Explicit 120s single CPU offline fit approval", "physical_attempts": 0, "env_constructs": 0, "dynamics_calls": 0})
    data = json.loads(DATA.read_text())
    # V2 filename adds full recipe identity while retaining the producer's v1
    # top-level schema string. Verify the actual required fields below.
    assert data["schema"] in ("v8.historical_recipe_dataset.v1", "v8.historical_recipe_dataset.v2")
    assert all("action_recipe" in r and "resolved_base_candidate" in r["action_recipe"] and "planner_source_sha256" in r["action_recipe"] for r in data["rows"])
    rows = data["rows"]
    by_group = defaultdict(list)
    for r in rows:
        by_group[r["group"]].append(r)
    groups = sorted(by_group)
    assert len(groups) == 6
    table = {}
    contexts = {}
    for group, rs in by_group.items():
        b = next(r for r in rs if r["action"]["family"] == "B")
        late = next(r for r in rs if r["action"] == {"family": "H150", "legacy": [0.0, 0.0], "original_B_through_outbound_slots": 1})
        early = next(r for r in rs if r["action"] == {"family": "H150", "legacy": [0.0, 0.0]})
        table[group] = [b, late, early]
        assert b["eligible_for_success_ranking"]
        contexts[group] = b["context"]
        assert len(contexts[group]["features"]) == 25 and all(contexts[group]["checks"].values())
        assert all(r["context"]["features"] == contexts[group]["features"] for r in (b, late, early))
    contracts = [r["action_recipe"] for r in table[groups[0]]]
    hashes = [r["action_recipe_sha256"] for r in table[groups[0]]]
    assert all([r["action_recipe_sha256"] for r in table[g]] == hashes for g in groups)
    assert [digest(x) for x in contracts] == hashes
    put(OUT / "ACTION_MENU.json", {"action_names": ["B", "LATE_H150", "EARLY_H150"], "action_contracts": contracts, "full_recipe_sha256": hashes, "new_physics": 0})
    variants = ["qualified_force_raw", "qualified_force_scaled", "force_with_JM_nonincrease", "qualified_moment"]
    summary = {"schema": "v8.offline_recipe_policy_fit.v1", "data_semantics": OFFLINE,
               "scope": "All six historical contexts already exposed; all held-out folds are development CV, not independent tests", "action_full_recipe_sha256": hashes,
               "input_sha256": inputs, "objectives": {}, "physical_attempts": 0, "fresh_on_policy_rollouts": 0, "env_constructs": 0, "dynamics_calls": 0}
    totals = Counter()
    for objective in variants:
        rewards = {g: [feedback(r, table[g][0], objective) for r in table[g]] for g in groups}
        teachers = {g: select_teacher(g, table, objective) for g in groups}
        feasible_rewards = [rewards[g][i] for g in groups for i in range(3) if table[g][i]["eligible_for_success_ranking"]]
        obj = {"reward_table_evaluation_only": rewards, "teacher_actions_evaluation_only": teachers, "teacher_counts": dict(Counter(teachers.values())),
               "feasible_reward_range": [min(feasible_rewards), max(feasible_rewards)], "failure_floor": -1.0,
               "teacher_representable_by_constant": len(set(teachers.values())) == 1, "folds": {}}
        for hold in [None] + groups:
            fold = "ALL_EXPOSED_DEVELOPMENT" if hold is None else "LEAVE_OUT_" + hold
            train = [g for g in groups if g != hold]
            test = groups if hold is None else [hold]
            norm = normalize(train, contexts)
            rules = simple_baselines(train, table, contexts, rewards, teachers, norm)
            fold_result = {"train_groups_evaluation_only": train, "evaluate_groups_evaluation_only": test, "simple_rules": rules, "models": {}, "baselines": {}}
            for kind in ("best_constant", "stump", "nearest"):
                fold_result["baselines"][kind] = [eval_row(g, simple_select(kind, rules, contexts[g]["features"]), table, rewards) for g in test]
            for action in range(3):
                fold_result["baselines"]["fixed_" + str(action)] = [eval_row(g, action, table, rewards) for g in test]
            for representation in ("constant", "linear_commissioned25"):
                for algorithm in ("BC", "REINFORCE", "PPO"):
                    policy = initialize(contracts, contexts[train[0]]["feature_names"], seed=20261027, normalization=norm)
                    policy["representation"] = representation
                    rng = random.Random(20261027)
                    initial_rng = rng.getstate()
                    updates = 80 if algorithm == "PPO" else 160
                    train_trace = []
                    for iteration in range(updates):
                        records = []
                        collection_identity = policy_sha256(policy)
                        if algorithm == "BC":
                            for g in train:
                                records.append({"features": contexts[g]["features"], "teacher_action_index": teachers[g], "teacher_complete_and_qualified": True})
                        else:
                            for g in train:
                                for _ in range(3):
                                    sample = choose(policy, contexts[g]["features"], deterministic=False, rng=rng, behavior_sha256=collection_identity)
                                    records.append({"features": contexts[g]["features"], "action_index": sample["action_index"], "old_logprob": sample["logprob"], "collection_policy_sha256": sample["policy_sha256"], "reward": rewards[g][sample["action_index"]], "historical_table_row_id": table[g][sample["action_index"]]["id"]})
                        baseline = 0.0 if algorithm == "BC" else sum(r["reward"] for r in records) / len(records)
                        info = update(policy, records, algorithm=algorithm, data_semantics=OFFLINE,
                                      learning_rate=0.1 if algorithm == "BC" else 0.15,
                                      epochs=3 if algorithm == "PPO" else 1, clip_range=0.2,
                                      advantage_baseline=baseline, allow_offline_table=True)
                        train_trace.append({"iteration": iteration, "records": len(records), "reward_baseline": baseline, "steps": info["steps"]})
                    key = algorithm + "_" + representation
                    evals = []
                    for g in test:
                        choice = choose(policy, contexts[g]["features"], deterministic=True)
                        er = eval_row(g, choice["action_index"], table, rewards)
                        er["probabilities"] = choice["probabilities"]
                        evals.append(er)
                    policy["objective"] = objective
                    policy["scope"] = "EXPOSED_DEVELOPMENT_FIT"
                    policy["data_sha256"] = sha(DATA)
                    model_path = OUT / "checkpoints" / objective / fold / (key + ".json")
                    put(model_path, {"policy": policy, "rng_initial": initial_rng, "rng_final": rng.getstate(), "train_trace": train_trace, "evaluation": evals})
                    fold_result["models"][key] = {"checkpoint": str(model_path.relative_to(ROOT)), "checkpoint_sha256": sha(model_path), "behavior_sha256": policy_sha256(policy), "counters": policy["counters"], "evaluation": evals,
                                                          "first_gradient_norm": train_trace[0]["steps"][0]["gradient_norm"], "last_gradient_norm": train_trace[-1]["steps"][-1]["gradient_norm"]}
                    totals.update(policy["counters"])
                    totals["fits"] += 1
            obj["folds"][fold] = fold_result
        summary["objectives"][objective] = obj
    summary["counters"] = dict(totals)
    put(OUT / "RESULTS.json", summary)
    frozen = {}
    for p in sorted((OUT / "checkpoints").rglob("*.json")):
        if "ALL_EXPOSED_DEVELOPMENT" in p.parts:
            frozen[str(p.relative_to(ROOT))] = sha(p)
    frozen[str((OUT / "ACTION_MENU.json").relative_to(ROOT))] = sha(OUT / "ACTION_MENU.json")
    put(OUT / "FROZEN_DEPLOYMENT_MANIFEST.json", {"files": frozen, "frozen_unix": time.time(), "independent_test_results_opened": False, "scope": "Potential transfer candidates, no control benefit granted"})
    # All mutation above stays under this family's output path.
    assert {k: sha(ROOT / k) for k in inputs} == inputs
    put(OUT / "END.json", {"status": "COMPLETE", "pid": os.getpid(), "start_unix": start, "end_unix": time.time(), "wall_s": time.time() - start, "cpu_s": time.process_time() - cpu,
                           "counters": dict(totals), "source_inputs_unchanged": True, "new_physics": 0, "fresh_on_policy_rollouts": 0, "env_constructs": 0, "dynamics_calls": 0})
    print(json.dumps({"status": "COMPLETE", "wall_s": time.time() - start, "counters": dict(totals), "output": str(OUT)}))


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        if OUT.exists():
            put(OUT / "FAILURE.json", {"error_type": type(error).__name__, "error": str(error), "time_unix": time.time(), "preserve_all_partial_outputs": True, "new_physics": 0})
        raise
