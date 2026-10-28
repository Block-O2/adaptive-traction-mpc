"""Ledger already completed fits without repeating them."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "offline_fit_v2"


def main():
    d = json.loads((RUN / "RESULTS.json").read_text())
    streams = {"ppo_reward": [], "il_dagger_sac": []}
    streams["ppo_reward"].append({"variant_id": "B_OFFLINE_SCHEMA_PREFLIGHT_V1", "status": "ENGINEERING_FAILED_PRE_FIT", "failure": "V2 producer filename retained v1 schema string; fixed by validating full recipe fields", "evidence": "families/ppo_reward/offline_fit_v1/FAILURE.json", "fits": 0, "parameter_updates": 0, "new_physics": 0, "fresh_on_policy_rollouts": 0, "failed_source_preserved": "families/ppo_reward/offline_fit_v1/failed_source.py"})
    for objective, obj in d["objectives"].items():
        for fold, f in obj["folds"].items():
            for model_name, m in f["models"].items():
                family = "il_dagger_sac" if model_name.startswith("BC_") else "ppo_reward"
                streams[family].append({"variant_id": objective + "/" + fold + "/" + model_name,
                                        "status": "COMPLETED_OFFLINE_DEVELOPMENT_FIT", "objective": objective,
                                        "representation": "linear_commissioned25" if "linear" in model_name else "constant",
                                        "data_semantics": "OFFLINE_TABLE_POLICY_OPTIMIZATION", "unique_historical_contexts_in_entire_dataset": 6,
                                        "unique_historical_three_action_rows_in_entire_dataset": 18,
                                        "train_groups_evaluation_metadata": f["train_groups_evaluation_only"],
                                        "evaluation_groups_evaluation_metadata": f["evaluate_groups_evaluation_only"],
                                        "fits": 1, "counters": m["counters"], "adam_steps": 0,
                                        "checkpoint": m["checkpoint"], "checkpoint_sha256": m["checkpoint_sha256"],
                                        "data_manifest": d["input_sha256"], "new_physics": 0, "fresh_on_policy_rollouts": 0,
                                        "implementation_valid": "API_REPLAY_PASS", "learning_information": "DEVELOPMENT_ONLY",
                                        "decision_valid_physical": "NOT_TESTED_BY_THIS_OPERATION", "task_valid_new_physical": "NOT_TESTED_BY_THIS_OPERATION",
                                        "generalization": "NOT_TESTED", "control_benefit": "NOT_GRANTED", "best_checkpoint_selection": "FIXED_FINAL_UPDATE"})
    streams["ppo_reward"].append({"variant_id": "B_FROZEN_ARGMAX_API_REPLAY", "status": "PASS", "evidence": "families/ppo_reward/offline_fit_v2/DEPLOYMENT_API_CHECK.json", "fits": 0, "model_forward_api": 144, "model_backward": 0, "parameter_updates": 0, "new_physics": 0, "fresh_on_policy_rollouts": 0})
    streams["il_dagger_sac"].append({"variant_id": "D_HISTORICAL_RECOVERY_ONLY", "status": "READ_ONLY_COMPLETED", "evidence": "families/il_dagger_sac/HISTORICAL_RECOVERY.md", "new_fits": 0, "new_physics": 0, "new_dagger_queries": 0, "new_SAC_updates": 0, "family_conclusion": "NOT_FULLY_EXPLORED"})
    for family, rows in streams.items():
        target = ROOT / "families" / family / "METHOD_VARIANT_LEDGER.jsonl"
        if target.exists():
            raise RuntimeError("REFUSE_LEDGER_OVERWRITE:" + str(target))
        target.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows))
    print(json.dumps({k: len(v) for k,v in streams.items()}))


if __name__ == "__main__":
    main()
