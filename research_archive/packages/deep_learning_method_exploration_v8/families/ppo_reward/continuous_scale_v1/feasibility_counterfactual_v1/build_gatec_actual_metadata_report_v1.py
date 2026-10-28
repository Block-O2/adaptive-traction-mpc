"""Authorized closed-artifact metadata report; imports no learner/model code."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_once(path, data):
    with path.open("x") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def stats():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return {"unix": time.time(), "monotonic": time.monotonic(), "pid": os.getpid(),
            "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
            "CPU_user_s": r.ru_utime, "CPU_system_s": r.ru_stime, "RSS_peak_KiB": r.ru_maxrss,
            "binary": str(Path(sys.executable).resolve()), "binary_sha256": sha(Path(sys.executable).resolve())}


def main():
    output = ROOT/"reports"/"GATEC_ACTUAL_METADATA_REVIEW_V1"
    output.parent.mkdir(exist_ok=True); output.mkdir(exist_ok=False)
    initial = stats(); reads = {}; counts = {"JSON_files_read": 0, "model_import_init_restore_forward_score_fit_RNG_physics": 0}
    write_once(output/"START.json", {"source_sha256": sha(__file__), "source_AST_sha256": hashlib.sha256(ast.dump(ast.parse(Path(__file__).read_text()), include_attributes=False).encode()).hexdigest(), "initial": initial})
    def read(path):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT) or "real_runs" in path.parts:
            raise ValueError("ONLY_APPROVED_CLOSED_PRIVATE_EXPORT_OR_DIAGNOSTIC_ARTIFACTS")
        reads[str(path.relative_to(PACKAGE))] = sha(path)
        counts["JSON_files_read"] += 1
        return json.loads(path.read_text())
    try:
        result_path = ROOT/"diagnostics/GATEC_ONCE_V1/RESULT.json"
        if sha(result_path) != "28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044":
            raise ValueError("EXACT_CLOSED_GATEC_REQUIRED")
        result = read(result_path); done = read(ROOT/"diagnostics/GATEC_ONCE_V1/DONE.json")
        identity = read(ROOT/"diagnostics/GATEC_ONCE_V1/IDENTITY.json")
        gated = read(ROOT/"diagnostics/GATED_ONCE_V1/RESULT.json")
        export = ROOT/"metadata_exports/ROOT_G0_CLOSED4_EXACT_V1"
        export_done = read(export/"DONE.json"); export_manifest = read(export/"EXPORT_MANIFEST.json")
        replay_input = read(export/"REPLAY_INPUT_V1.json")
        checkpoint = read(PACKAGE/replay_input["behavior_checkpoint_exact_export"]["path"])
        proposals = {ident: read(PACKAGE/ref["path"]) for ident, ref in replay_input["original_closed_proposal_exact_exports_by_id"].items()}
        if done["result_sha256"] != sha(result_path) or done["status"] != "COMPLETED_EXACT_APPROVED_OFFLINE_STAGE":
            raise ValueError("GATEC_NOT_CLOSED_EXACT_SUCCESS")
        source_policy = checkpoint["policy"]
        source_weights = source_policy["weights"]
        if any(v != 0.0 for row in source_weights for v in row[1:]) or source_weights[0] != source_weights[1]:
            raise ValueError("INITIAL_CONSTANT_SYMMETRIC_POLICY_METADATA_NOT_AS_RECORDED")
        row_table = []
        for row, advantage in zip(gated["rows"], result["advantages"]):
            critical = min(row["original_45_components"], key=lambda item: item["signed_normalized_margin"])
            row_table.append({"id": row["id"], "context": row["group_evaluation_only"], "lambda_sample": row["lambda_sample"],
                              "dense_reward": row["reward_FEASIBILITY_ONLY"], "global_advantage": advantage,
                              "critical_original_component": critical["name"], "qualified": row["original_qualified"],
                              "failed_requirements": row["original_motion_failed_requirements"],
                              "actual_original_costs_evaluation_only": row["JF_and_JM_evaluation_only"]})
        context_summary = []
        for group in sorted({r["context"] for r in row_table}):
            rows = [r for r in row_table if r["context"] == group]
            mean = sum(r["dense_reward"] for r in rows)/2
            context_summary.append({"context": group, "sample_count": 2, "reward_mean": mean,
                                    "empirical_context_mean_offset_from_global": mean-result["meanbaseline"],
                                    "both_global_advantages_same_sign": rows[0]["global_advantage"]*rows[1]["global_advantage"] > 0,
                                    "no_LOO_gradient_or_new_baseline_run_performed": True})
        endpoints = {}
        for algorithm, policy in result["private_policies"].items():
            if policy["normalization"] != source_policy["normalization"]:
                raise ValueError("NORMALIZER_CHANGED")
            endpoints[algorithm] = {"counters": policy["counters"], "normalization_SHA_unchanged": True,
                                   "stored_weights_sha256": hashlib.sha256(json.dumps(policy["weights"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
                                   "total_weight_delta_norm_from_stored_arrays": math.sqrt(sum((a-b)**2 for x,y in zip(policy["weights"], source_weights) for a,b in zip(x,y))),
                                   "stored_context_means": {g: {"lambda": m["lambda"], "delta_vs_initial_half": m["lambda"]-.5,
                                                                           "full_recipe_sha256": m["full_recipe_sha256"], "physical_qualification": "UNKNOWN_NOT_RUN"}
                                                            for g,m in result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm].items()}}
        all_ratios = [row["ratio"] for trace in result["traces"].values() for epoch in trace for row in epoch["rows"]]
        report = {"schema": "v8.beta_feasibility_gatec_actual_metadata_review.v1", "status": "CLOSED_ACTUAL_FIXED_BEHAVIOR_REPLAY_ONLY",
                  "actual_GateC_result_sha256": sha(result_path), "row_table": row_table, "context_summary": context_summary,
                  "original_global_baseline": result["meanbaseline"], "actual_GateC_API_counts": result["counts"],
                  "actual_completed_model_forward": 24, "actual_training_forward": 20,
                  "actual_epochs": {a: [{k:e[k] for k in ("epoch", "raw_gradient_norm", "gradient_clip_scale", "weight_delta_norm", "weights_before_sha256", "weights_after_sha256")} for e in epochs] for a,epochs in result["traces"].items()},
                  "RF_PPO_initial_gradient_exact_equal": result["traces"]["REINFORCE"][0]["gradient"] == result["traces"]["PPO"][0]["gradient"],
                  "ratio_range": [min(all_ratios), max(all_ratios)],
                  "surrogate_gradient_suppression_count": sum(row["surrogate_gradient_suppressed"] for trace in result["traces"].values() for e in trace for row in e["rows"]),
                  "gradient_clipped_epoch_count": sum(e["gradient_clip_scale"] != 1.0 for trace in result["traces"].values() for e in trace),
                  "stored_final_endpoints": endpoints, "actual_linear_rules_not_refit": result["same_axis_lambda_margin_linear_rules"],
                  "resources_from_actual_DONE": {k:done[k] for k in ("initial", "final", "wall_s", "CPU_s")},
                  "actual_source_authority_identity": identity, "metadata_export_counts": export_done["counts"],
                  "metadata_export_original_copy_proof": export_manifest,
                  "original_floor_zero_gradient_reference": result["zero_gradient_original_reward_reference"],
                  "claim_limit": "observable feasibility information and finite private gradient; no new onpolicy data, no endpoint physical qualification or JF/JM improvement",
                  "all_old_16_physical_policy_attempts_paid_but_only4unique_coverage": True,
                  "metadata_review_reads_sha256": reads, "metadata_review_counts": counts,
                  "new_LOO_or_centered_training_runs": 0, "original_WINDOW_CURRENT_12mean_inventory_changes": False}
        write_once(output/"REPORT.json", report)
        final = stats()
        write_once(output/"DONE.json", {"status": "COMPLETED_METADATA_ONLY_REVIEW", "initial": initial, "final": final,
                   "counts": counts, "report_sha256": sha(output/"REPORT.json")})
    except BaseException as error:
        write_once(output/"FAILED.json", {"error_type": type(error).__name__, "error": str(error), "counts": counts, "reads_sha256": reads})
        raise


if __name__ == "__main__":
    main()
