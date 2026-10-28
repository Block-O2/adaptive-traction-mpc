"""Authorized closed GateL/four-endpoint metadata audit; no learner import."""
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


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with path.open("x") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def stats():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return {"unix":time.time(), "monotonic":time.monotonic(), "pid":os.getpid(),
            "start_ticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),
            "CPU_user_s":r.ru_utime, "CPU_system_s":r.ru_stime, "RSS_peak_KiB":r.ru_maxrss,
            "binary":str(Path(sys.executable).resolve()), "binary_sha256":sha(Path(sys.executable).resolve())}


def main():
    output = ROOT/"reports/GATEL_ACTUAL_METADATA_REVIEW_V1"
    output.parent.mkdir(exist_ok=True); output.mkdir(exist_ok=False)
    initial = stats(); reads = {}
    counts = {"closed_JSON_reads":0, "stored_policy_digest_checks":0, "stored_weight_digest_checks":0,
              "stored_alpha_beta_mean_ratio_checks":0, "stored_half_advantage_checks":0,
              "stored_half_gradient_scalar_checks":0, "stored_gradient_decomposition_scalar_checks":0,
              "new_model_import_init_restore_forward_score_fit_RNG_physics":0}
    write(output/"START.json", {"source_sha256":sha(__file__), "source_AST_sha256":hashlib.sha256(ast.dump(ast.parse(Path(__file__).read_text()),include_attributes=False).encode()).hexdigest(), "initial":initial})
    def read(path):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT) or "real_runs" in path.parts:
            raise ValueError("ONLY_APPROVED_CLOSED_METADATA_EXPORTS_AND_RESULTS")
        reads[str(path.relative_to(PACKAGE))] = sha(path)
        counts["closed_JSON_reads"] += 1
        return json.loads(path.read_text())
    try:
        lpath = ROOT/"context_loo_v1/diagnostics/GATEL_ONCE_V1/RESULT.json"
        cpath = ROOT/"diagnostics/GATEC_ONCE_V1/RESULT.json"
        if sha(lpath)!="55369ef436e9b0b54023ee7cdb20e9c520d1933c2ed69f865bc3f7f011129db2" or sha(cpath)!="28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044":
            raise ValueError("EXACT_CLOSED_GLOBAL_AND_LOO_RESULTS_REQUIRED")
        loo, global_result = read(lpath), read(cpath)
        ldone = read(lpath.parent/"DONE.json"); cdone = read(cpath.parent/"DONE.json")
        identity = read(lpath.parent/"IDENTITY.json")
        g0 = read(ROOT/"metadata_exports/ROOT_G0_CLOSED4_EXACT_V1/ORIGINAL_G0_RF_RAW_EXACT.json")["policy"]
        input_document = read(PACKAGE/loo["input"]["path"])
        if loo["rewards"] != global_result["rewards"] or loo["behavior_density_sha256"] != global_result["behavior_density_sha256"]:
            raise ValueError("BASELINE_ONLY_COMPARISON_MUST_HAVE_IDENTICAL_REWARDS_AND_BEHAVIOR")
        for result, done, path in [(loo,ldone,lpath),(global_result,cdone,cpath)]:
            if done["status"] != "COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or done["result_sha256"] != sha(path):
                raise ValueError("ACTUAL_CLOSED_DONE_RESULT_BINDING")
        endpoints = {}
        for family, result, path in [("GLOBAL",global_result,cpath),("CONTEXT_LOO",loo,lpath)]:
            for algorithm in ["REINFORCE","PPO"]:
                label = "FEAS_"+family+"_"+("RF1" if algorithm=="REINFORCE" else "PPO3")
                policy = result["private_policies"][algorithm]
                fields = ("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version")
                policy_digest = digest({key:policy[key] for key in fields}); counts["stored_policy_digest_checks"] += 1
                weights_digest = digest(policy["weights"]); counts["stored_weight_digest_checks"] += 1
                if (policy["normalization"] != g0["normalization"] or policy["axis_contract"] != g0["axis_contract"] or
                        weights_digest != result["traces"][algorithm][-1]["weights_after_sha256"] or
                        policy["counters"]["parameter_updates"] != (1 if algorithm=="REINFORCE" else 3)):
                    raise ValueError("ACTUAL_FIXED_ENDPOINT_WEIGHT_NORM_AXIS_AND_FINAL_STEP_BINDING")
                means = {}
                for group, stored in result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm].items():
                    counts["stored_alpha_beta_mean_ratio_checks"] += 1
                    if policy_digest != stored["policy_sha256"] or stored["lambda"] != stored["alpha"]/(stored["alpha"]+stored["beta"]):
                        raise ValueError("STORED_MEAN_METADATA_NOT_THIS_FIXED_POLICY")
                    means[group] = {"lambda":stored["lambda"], "delta_vs_initial_half":stored["lambda"]-.5,
                                    "full_recipe_sha256":stored["full_recipe_sha256"], "physical_action_sha256":stored["physical_action_sha256"],
                                    "physical_qualification":"UNKNOWN_NOT_RUN"}
                endpoints[label] = {"closed_result":{"path":str(path.relative_to(PACKAGE)),"sha256":sha(path)},
                                    "policy_json_path":["private_policies",algorithm], "policy_sha256":policy_digest,
                                    "weights_sha256":weights_digest, "counters":policy["counters"], "stored_means":means,
                                    "all_parameters_finite":all(math.isfinite(v) for row in policy["weights"] for v in row),
                                    "total_weight_delta_from_G0_stored_arrays":math.sqrt(sum((a-b)**2 for x,y in zip(policy["weights"],g0["weights"]) for a,b in zip(x,y)))}
        for full, half in zip(loo["advantages"],loo["same_context_centered_half_LOO_analytic_only"]):
            counts["stored_half_advantage_checks"] += 1
            if half != .5*full:
                raise ValueError("HALF_ADVANTAGE_METADATA_INCONSISTENT")
        decomposition = loo["initial_gradient_decomposition"]
        residual = 0.0
        for old, new, half, between in zip(decomposition["closed_global_raw_gradient"],decomposition["new_LOO_raw_gradient"],decomposition["centered_raw_gradient_half_LOO_analytic_only"],decomposition["empirical_between_context_offset_component_global_minus_half_LOO"]):
            for a,b,c,d in zip(old,new,half,between):
                counts["stored_half_gradient_scalar_checks"] += 1
                counts["stored_gradient_decomposition_scalar_checks"] += 1
                if c != .5*b:
                    raise ValueError("HALF_RAW_GRADIENT_METADATA_INCONSISTENT")
                residual = max(residual,abs(a-(c+d)))
        ratios = [row["ratio"] for epochs in loo["traces"].values() for epoch in epochs for row in epoch["rows"]]
        report = {"schema":"v8.beta_feasibility_gatel_actual_metadata_review.v1", "status":"CLOSED_BASELINE_ONLY_FIXED_BEHAVIOR_DIAGNOSTIC_NO_PHYSICS",
                  "actual_GateL_result":{"path":str(lpath.relative_to(PACKAGE)),"sha256":sha(lpath)},
                  "actual_GateC_result":{"path":str(cpath.relative_to(PACKAGE)),"sha256":sha(cpath)},
                  "actual_GateL_API_counts":loo["counts"], "actual_GateL_model_forward":24, "actual_GateL_training_forward":20,
                  "genuine_actor_updates":0, "new_sampling_or_physics":0, "four_fixed_endpoint_metadata":endpoints,
                  "rewards_unchanged":loo["rewards"], "LOO_peer_baselines":loo["per_row_peer_baselines"],
                  "LOO_advantages":loo["advantages"], "centered_half_advantages_analytic_only":loo["same_context_centered_half_LOO_analytic_only"],
                  "initial_cosine_global_vs_LOO_stored":decomposition["cosine_global_vs_LOO"],
                  "between_context_component_norm_stored":decomposition["between_context_component_norm"],
                  "gradient_decomposition_metadata_max_residual":residual,
                  "GateL_epoch_metadata":{a:[{k:e[k] for k in ("epoch","raw_gradient_norm","gradient_clip_scale","weight_delta_norm")} for e in epochs] for a,epochs in loo["traces"].items()},
                  "ratio_range": [min(ratios),max(ratios)],
                  "gradient_clipped_epochs":sum(e["gradient_clip_scale"]!=1.0 for epochs in loo["traces"].values() for e in epochs),
                  "surrogate_suppressed_rows":sum(row["surrogate_gradient_suppressed"] for epochs in loo["traces"].values() for e in epochs for row in e["rows"]),
                  "strong_linear_rules_reused_not_refit":loo["same_axis_lambda_margin_linear_rules_REUSED_NO_REFIT"],
                  "actual_GateL_resources":{k:ldone[k] for k in ("initial","final","wall_s","CPU_s")},
                  "actual_GateC_resources":{k:cdone[k] for k in ("initial","final","wall_s","CPU_s")},
                  "actual_GateL_source_identity":identity, "actual_GateL_input":input_document,
                  "mechanism_scope":"Changing baseline changed finite sample rawgradient direction and mean shifts; L mean still opposes local2point linear lambda1 direction. No claim credit fully fixed, unbiasedness empirically proven, lower variance, physical success or JF/JM gains.",
                  "primary_sources":["https://arxiv.org/html/2402.14740v2#S2.SS3","https://aclanthology.org/2024.acl-long.662/"],
                  "source_claim_limit":"Same-context leave-other-reward construction parallels displayed RLOO estimator section2.3, not an LLM-system replication;3/4 and1/2 factors are this study algebra, not claimed paper outcomes.",
                  "metadata_reads_sha256":reads, "metadata_counts":counts, "realrun_raw_active_or_new_validation_reads":False}
        write(output/"REPORT.json",report)
        final = stats(); write(output/"DONE.json",{"status":"COMPLETED_METADATA_ONLY_FOUR_ENDPOINT_REVIEW","initial":initial,"final":final,"counts":counts,"report_sha256":sha(output/"REPORT.json")})
    except BaseException as error:
        write(output/"FAILED.json",{"error_type":type(error).__name__,"error":str(error),"counts":counts,"reads_sha256":reads}); raise


if __name__ == "__main__":
    main()
