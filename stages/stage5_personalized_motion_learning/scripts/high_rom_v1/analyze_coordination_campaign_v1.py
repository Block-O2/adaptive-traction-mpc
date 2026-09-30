"""Derive descriptive scientific evidence from the frozen formal rollout table."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import mujoco

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
DOC = STAGE / "docs/coordination_pacing_exploration_v1"
FIG = DOC / "figures"
FIG.mkdir(exist_ok=True)
RUNS = STAGE / "results/coordination_pacing_exploration_v1/runs"
rows = json.loads((DOC / "ALL_COORDINATION_ROLLOUTS.json").read_text())
matrix = json.loads((DOC / "CONDITION_MATRIX.json").read_text())
condition = {x["id"]: x for x in matrix["conditions"]}


def save(name, value):
    (DOC / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    a = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if not len(a): return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    return {"n": int(len(a)), "min": float(np.min(a)), "median": float(np.median(a)),
            "mean": float(np.mean(a)), "max": float(np.max(a))}


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0: return None
    return float(np.corrcoef(x, y)[0, 1])


def rank(values):
    a = np.asarray(values, float)
    order = np.argsort(a, kind="stable")
    ranks = np.empty(len(a), float)
    start = 0
    while start < len(a):
        stop = start + 1
        while stop < len(a) and a[order[stop]] == a[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + stop - 1) / 2
        start = stop
    return ranks


def key(row):
    p = row["pattern"]
    return (p["lead"], p["amplitude"], p["peak"], p["horizon"],
            p["synchronous"], p["return_reverse"])


valid = [x for x in rows if x["status"] == "VALID"]
matched = [x for x in valid if x["timing_isolated"]]
matched_all = [x for x in valid if x["arm"] == "MATCHED"]
native = [x for x in valid if x["arm"] == "NATIVE"]
counts = Counter(x["status"] for x in rows)

feasibility = {"schema": "coordination_feasibility_map_v1", "total_attempts": len(rows),
    "status_counts": counts, "by_lead_amplitude_horizon_arm": [], "failure_reasons": Counter()}
groups = defaultdict(list)
for r in rows:
    groups[(r["lead"], r["amplitude"], r["horizon"], r["arm"])].append(r)
    if r["status"] != "VALID":
        reason = (r.get("failure_reason") or "unknown").lower()
        category = next((name for name, fragments in (
            ("clearance", ("clearance", "geometry", "shank")),
            ("mechanics_force_moment", ("force", "moment", "mechanics")),
            ("velocity", ("velocity",)), ("acceleration", ("acceleration",)),
            ("phase_timeout", ("timeout", "phase time"))) if any(f in reason for f in fragments)), "other")
        feasibility["failure_reasons"][category] += 1
for grouping, subset in sorted(groups.items()):
    feasibility["by_lead_amplitude_horizon_arm"].append({
        "lead": grouping[0], "amplitude": grouping[1], "horizon": grouping[2], "arm": grouping[3],
        "attempts": len(subset), "valid": sum(x["status"] == "VALID" for x in subset),
        "infeasible": sum(x["status"] == "INFEASIBLE" for x in subset),
        "invalid": sum(x["status"] == "INVALID" for x in subset),
        "exceptions": sum(x["status"] == "EXCEPTION" for x in subset)})
save("COORDINATION_FEASIBILITY_MAP.json", feasibility)

def metric_changes(selection):
    output = []
    for x in selection:
        run = json.loads((RUNS / x["run_id"] / "rollout_result.json").read_text())
        base_id = (f"matched_baseline_{x['condition_id']}_certified" if x["arm"] == "MATCHED"
                   else f"baseline_{x['condition_id']}_a")
        base = json.loads((RUNS / base_id / "rollout_result.json").read_text())
        output.append({"run_id": x["run_id"], "condition_id": x["condition_id"],
            "benefit_n_s": x["benefit_n_s"], "duration_change_s": x["duration_change_s"],
            "mean_force_change_n": run["mean_force_n"] - base["mean_force_n"],
            "rms_force_change_n": run["rms_force_n"] - base["rms_force_n"],
            "peak_force_change_n": run["peak_force_n"] - base["peak_force_n"],
            "moment_integral_change_nm_s": run["moment_integral_nm_s"] - base["moment_integral_nm_s"],
            "moment_peak_change_nm": run["moment_peak_nm"] - base["moment_peak_nm"],
            "clearance_change_m": run["minimum_clearance_m"] - base["minimum_clearance_m"]
            if run.get("minimum_clearance_m") is not None and base.get("minimum_clearance_m") is not None else None})
    return output

matched_changes = metric_changes(matched)
native_changes = metric_changes(native)
paired = []
for x in native:
    y = next((z for z in matched_all if z["stage"] == x["stage"] and
              z["condition_id"] == x["condition_id"] and key(z) == key(x)), None)
    if y is not None:
        paired.append({"condition_id": x["condition_id"], "stage": x["stage"],
                       "pattern": x["pattern"], "native_benefit_n_s": x["benefit_n_s"],
                       "matched_benefit_n_s": y["benefit_n_s"],
                       "matched_timing_isolated": y["timing_isolated"],
                       "native_duration_change_s": x["duration_change_s"],
                       "matched_duration_change_s": y["duration_change_s"]})

coord_summary = {"schema": "coordination_benefit_summary_v1",
    "matched_valid_count": len(matched_all), "timing_isolated_count": len(matched),
    "timing_confounded_count": len(matched_all) - len(matched),
    "coordination_benefit_n_s": stats([x["benefit_n_s"] for x in matched]),
    "positive_coordination_benefit_n_s": stats([x["benefit_n_s"] for x in matched if x["benefit_n_s"] > 0]),
    "by_horizon": {h: stats([x["benefit_n_s"] for x in matched if x["horizon"] == h])
                   for h in ("H1", "H2", "H3", "H4")},
    "by_lead": {str(lead): stats([x["benefit_n_s"] for x in matched if x["lead"] == lead])
                for lead in (-1, 0, 1)},
    "best": max(matched, key=lambda x: x["benefit_n_s"]) if matched else None,
    "mean_force_change_n": stats([x["mean_force_change_n"] for x in matched_changes]),
    "rms_force_change_n": stats([x["rms_force_change_n"] for x in matched_changes]),
    "peak_force_change_n": stats([x["peak_force_change_n"] for x in matched_changes]),
    "moment_integral_change_nm_s": stats([x["moment_integral_change_nm_s"] for x in matched_changes]),
    "moment_peak_change_nm": stats([x["moment_peak_change_nm"] for x in matched_changes]),
    "clearance_change_m": stats([x["clearance_change_m"] for x in matched_changes]),
    "timing_residual_outbound_s": stats([x["phase_timing_residual_s"]["OUTBOUND"] for x in matched]),
    "timing_residual_return_s": stats([x["phase_timing_residual_s"]["RETURN"] for x in matched]),
    "matched_vs_native_paired_count": len(paired),
    "interpretation_rule": "Only timing_isolated rows are primary coordination evidence; nominally matched but timing-confounded rows remain descriptive."}
save("COORDINATION_BENEFIT_SUMMARY.json", coord_summary)

native_summary = {"schema": "native_timing_benefit_summary_v1",
    "native_valid_count": len(native),
    "native_benefit_n_s": stats([x["benefit_n_s"] for x in native]),
    "native_positive_benefit_n_s": stats([x["benefit_n_s"] for x in native if x["benefit_n_s"] > 0]),
    "best": max(native, key=lambda x: x["benefit_n_s"]) if native else None,
    "duration_change_s": stats([x["duration_change_s"] for x in native]),
    "mean_force_change_n": stats([x["mean_force_change_n"] for x in native_changes]),
    "benefit_vs_duration_change_pearson": corr([x["duration_change_s"] for x in native],
                                                [x["benefit_n_s"] for x in native]),
    "paired_native_vs_matched": paired,
    "prior_best": {"benefit_n_s": 85.948499, "duration_change_s": -.955,
                   "mean_force_increased_slightly": True,
                   "source": "SAFE_ACTION_HORIZON_EXPLORATION_REPORT.md"},
    "causal_limit": "Native and matched baselines have different prescribed durations; their benefit difference is descriptive, not an exact additive timing component."}
save("NATIVE_TIMING_BENEFIT_SUMMARY.json", native_summary)

credit = {"schema": "short_long_coordination_credit_v1", "matched_timing_isolated_count": len(matched)}
for name, short in (("first_0p5", "short_benefit_0p5_n_s"),
                    ("first_1p5", "short_benefit_1p5_n_s"),
                    ("outbound", "outbound_benefit_n_s")):
    credit[name] = {"pearson": corr([x[short] for x in matched], [x["benefit_n_s"] for x in matched]),
                    "spearman": corr(rank([x[short] for x in matched]), rank([x["benefit_n_s"] for x in matched])) if len(matched) >= 3 else None,
                    "short_worse_full_better": sum(x[short] < 0 < x["benefit_n_s"] for x in matched),
                    "short_better_full_worse": sum(x[short] > 0 > x["benefit_n_s"] for x in matched)}
credit["within_condition_first_1p5"] = []
for ident in sorted({x["condition_id"] for x in matched}):
    subset = [x for x in matched if x["condition_id"] == ident]
    concordant = discordant = ties = 0
    for i, left in enumerate(subset):
        for right in subset[i + 1:]:
            a = left["short_benefit_1p5_n_s"] - right["short_benefit_1p5_n_s"]
            b = left["benefit_n_s"] - right["benefit_n_s"]
            if a * b > 0: concordant += 1
            elif a * b < 0: discordant += 1
            else: ties += 1
    credit["within_condition_first_1p5"].append({"condition_id": ident, "n": len(subset),
        "spearman": corr(rank([x["short_benefit_1p5_n_s"] for x in subset]),
                         rank([x["benefit_n_s"] for x in subset])) if len(subset) >= 3 else None,
        "concordant_pairs": concordant, "discordant_pairs": discordant, "tied_pairs": ties,
        "pairwise_agreement": concordant / (concordant + discordant) if concordant + discordant else None})
save("SHORT_LONG_COORDINATION_CREDIT.json", credit)

cross = [x for x in rows if x["stage"] == "VALIDATION"]
cross_summary = {"schema": "cross_condition_validation_v1", "validation_conditions":
    [x["id"] for x in matrix["conditions"] if x["role"] == "validation"],
    "rows": cross, "status_counts": Counter(x["status"] for x in cross),
    "valid_count": sum(x["status"] == "VALID" for x in cross),
    "note": "Validation conditions were not used for pattern selection; if baseline replay excluded a condition, it contributes no validation evidence."}
save("CROSS_CONDITION_VALIDATION.json", cross_summary)

by_pattern = defaultdict(list)
validation_plan_keys = {key(x) for x in json.loads((DOC / "CROSS_CONDITION_PLAN.json").read_text())["entries"]}
for x in rows:
    if x["stage"] == "VALIDATION" or x["arm"] != "MATCHED" or key(x) not in validation_plan_keys:
        continue
    by_pattern[key(x)].append(x)
fixed_candidates = []
for p, subset in by_pattern.items():
    usable = [x for x in subset if x["timing_isolated"]]
    if len({condition[x["condition_id"]]["physical_condition_id"] for x in usable}) >= 2:
        fixed_candidates.append({"pattern": subset[0]["pattern"],
            "condition_count": len({x["condition_id"] for x in usable}),
            "physical_condition_count": len({condition[x["condition_id"]]["physical_condition_id"] for x in usable}),
            "attempted_condition_count": len({x["condition_id"] for x in subset}),
            "attempted_physical_condition_count": len({condition[x["condition_id"]]["physical_condition_id"] for x in subset}),
            "attempts": len(subset), "timing_isolated_valid": len(usable),
            "mean_benefit_n_s": float(np.mean([x["benefit_n_s"] for x in usable])),
            "median_benefit_n_s": float(np.median([x["benefit_n_s"] for x in usable])),
            "positive_fraction": float(np.mean([x["benefit_n_s"] > 0 for x in usable])),
            "infeasible_count": sum(x["status"] == "INFEASIBLE" for x in subset)})
fixed_candidates.sort(key=lambda x: (-x["physical_condition_count"], -x["condition_count"],
                                     -x["median_benefit_n_s"]))
fixed_best = fixed_candidates[0] if fixed_candidates else None
fixed_best_benefit = max(fixed_candidates, key=lambda x: x["median_benefit_n_s"]) if fixed_candidates else None
prevalidation_matched = [x for x in matched if x["stage"] != "VALIDATION"]
prevalidation_peak = max(prevalidation_matched, key=lambda x: x["benefit_n_s"]) if prevalidation_matched else None
prevalidation_peak_support = (next((x for x in fixed_candidates if key(x) == key(prevalidation_peak)), None)
                              if prevalidation_peak else None)
fixed_validation = []
if fixed_best is not None:
    wanted = key({"pattern": fixed_best["pattern"]})
    fixed_validation = [{"condition_id": x["condition_id"], "benefit_n_s": x["benefit_n_s"],
                         "timing_isolated": x["timing_isolated"], "status": x["status"]}
                        for x in cross if key(x) == wanted and x["arm"] == "MATCHED"]
fixed_best_benefit_validation = ([{"condition_id": x["condition_id"], "benefit_n_s": x["benefit_n_s"],
                                   "timing_isolated": x["timing_isolated"], "status": x["status"]}
                                  for x in cross if key(x) == key({"pattern": fixed_best_benefit["pattern"]})
                                  and x["arm"] == "MATCHED"] if fixed_best_benefit else [])
prevalidation_peak_validation = ([{"condition_id": x["condition_id"], "benefit_n_s": x["benefit_n_s"],
                                  "timing_isolated": x["timing_isolated"], "status": x["status"]}
                                 for x in cross if key(x) == key(prevalidation_peak) and x["arm"] == "MATCHED"]
                                if prevalidation_peak else [])
condition_best = {}
condition_arm_preference = {}
for ident in {x["condition_id"] for x in matched}:
    subset = [x for x in matched if x["condition_id"] == ident]
    condition_best[ident] = {"best_benefit_n_s": max(x["benefit_n_s"] for x in subset),
                             "best_pattern": max(subset, key=lambda x: x["benefit_n_s"])["pattern"]}
    native_subset = [x for x in native if x["condition_id"] == ident]
    if native_subset:
        native_best_row = max(native_subset, key=lambda x: x["benefit_n_s"])
        condition_arm_preference[ident] = {
            "matched_best_pattern": condition_best[ident]["best_pattern"],
            "native_best_pattern": native_best_row["pattern"],
            "native_best_benefit_n_s": native_best_row["benefit_n_s"],
            "same_pattern": key({"pattern": condition_best[ident]["best_pattern"]}) == key(native_best_row),
            "interpretation": "Descriptive arm-specific optima; different prescribed schedules and feasible sets prevent an exact causal timing attribution."}
state_rows = {s: {key(x): x["benefit_n_s"] for x in matched if x["condition_id"] == s}
              for s in ("low_ordinary_early", "low_ordinary_late")}
common_state_patterns = set(state_rows["low_ordinary_early"]) & set(state_rows["low_ordinary_late"])
state_rank_spearman = (corr(rank([state_rows["low_ordinary_early"][k] for k in sorted(common_state_patterns)]),
                            rank([state_rows["low_ordinary_late"][k] for k in sorted(common_state_patterns)]))
                       if len(common_state_patterns) >= 3 else None)
personalized = {"schema": "fixed_vs_personalized_analysis_v1",
    "best_fixed_pattern_selected_without_validation": fixed_best,
    "best_median_benefit_fixed_pattern_selected_without_validation": fixed_best_benefit,
    "prevalidation_peak_matched_pattern": prevalidation_peak,
    "prevalidation_peak_matched_pattern_support": prevalidation_peak_support,
    "fixed_pattern_selection_rule": "Among patterns frozen in the held-out validation plan, choose highest discovery/refinement timing-isolated physical-condition coverage, then state-row coverage, then median benefit; infeasible attempts retained in attempted coverage. Validation outcomes never enter selection. This is a descriptive comparator, not a trained policy.",
    "fixed_pattern_candidates": fixed_candidates,
    "fixed_pattern_validation_rows": fixed_validation,
    "best_median_benefit_fixed_pattern_validation_rows": fixed_best_benefit_validation,
    "prevalidation_peak_matched_pattern_validation_rows": prevalidation_peak_validation,
    "condition_specific_best": condition_best,
    "condition_arm_preference": condition_arm_preference,
    "early_late_common_pattern_count": len(common_state_patterns),
    "early_late_matched_rank_spearman": state_rank_spearman,
    "validation_condition_count": len({x["condition_id"] for x in cross}),
    "interpretation": "A fixed comparator is required; personalization is justified only if condition-specific gains persist on unused validation conditions and exceed timing/feasibility tradeoffs."}
save("FIXED_VS_PERSONALIZED_ANALYSIS.json", personalized)

learning = {"schema": "learning_readiness_assessment_v1", "training_performed": False,
    "value_hook": "Existing candidate_value_evaluator(state_or_belief, candidate_next_waypoint) adds one dimensionless scalar to existing planner terms. A future long-horizon coordination chunk would require candidate metadata describing multi-waypoint/phase path and timing, plus separately scaled force objective; raw N s must not be added directly to dimensionless cost.",
    "smallest_next_experiment": "Compare the best validated fixed coordination against a condition-indexed table on fresh, independently held-out supported conditions under the same safety and pacing contract; only then consider local ranking or long-horizon value learning.",
    "evidence": {"timing_isolated_count": len(matched), "validation_valid_count": cross_summary["valid_count"],
                 "fixed_pattern": fixed_best, "state_rank_spearman": state_rank_spearman},
    "provisional_decision": "test_fixed_policy_comparator_first" if fixed_best is not None else "insufficient_matched_evidence"}
save("LEARNING_READINESS_ASSESSMENT.json", learning)
(DOC / "LEARNING_READINESS_ASSESSMENT.md").write_text(
    "# Learning Readiness Assessment\n\nNo learner was trained. " + learning["value_hook"] +
    "\n\nThe next experiment is: " + learning["smallest_next_experiment"] + "\n")

def scatter(name, selection, xkey, ykey, xlabel, ylabel):
    if not selection: return
    fig, ax = plt.subplots(figsize=(7, 5))
    for lead, color, label in ((-1, "#2a6fbb", "knee-leading"), (0, "#777777", "synchronous"), (1, "#c94832", "hip-leading")):
        data = [r for r in selection if r["lead"] == lead]
        if data:
            ax.scatter([r[xkey] for r in data], [r[ykey] for r in data], alpha=.55, s=18, label=label, c=color)
    ax.axhline(0, color="black", lw=.7)
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.legend()
    fig.tight_layout(); fig.savefig(FIG / name, dpi=150); plt.close(fig)

scatter("coordination_parameter_vs_matched_benefit.png", matched, "amplitude", "benefit_n_s", "Lead amplitude / task span", "Matched coordination benefit (N s)")
scatter("coordination_parameter_vs_native_benefit.png", native, "amplitude", "benefit_n_s", "Lead amplitude / task span", "Native benefit (N s)")
scatter("benefit_vs_duration_change.png", native, "duration_change_s", "benefit_n_s", "Native duration change (s)", "Native benefit (N s)")
scatter("short_vs_long_benefit.png", matched, "short_benefit_1p5_n_s", "benefit_n_s", "First 1.5 s benefit (N s)", "Full repetition benefit (N s)")
if paired:
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter([x["matched_benefit_n_s"] for x in paired], [x["native_benefit_n_s"] for x in paired], s=17, alpha=.6)
    ax.set(xlabel="Matched benefit (N s)", ylabel="Native benefit (N s)")
    fig.tight_layout(); fig.savefig(FIG / "matched_vs_native_benefit.png", dpi=150); plt.close(fig)
if matched_changes:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([x["mean_force_change_n"] for x in matched_changes], [x["rms_force_change_n"] for x in matched_changes],
               c=[x["benefit_n_s"] for x in matched_changes], cmap="coolwarm", s=20)
    ax.set(xlabel="Mean force change (N)", ylabel="RMS force change (N)")
    fig.tight_layout(); fig.savefig(FIG / "force_intensity_changes.png", dpi=150); plt.close(fig)
if matched:
    ids = sorted({x["condition_id"] for x in matched})
    amp = sorted({x["amplitude"] for x in matched})
    grid = np.full((len(ids), len(amp)), np.nan)
    for i, ident in enumerate(ids):
        for j, a in enumerate(amp):
            v = [x["benefit_n_s"] for x in matched if x["condition_id"] == ident and x["amplitude"] == a]
            if v: grid[i, j] = np.median(v)
    fig, ax = plt.subplots(figsize=(7, max(4, len(ids) * .5)))
    image = ax.imshow(grid, aspect="auto", cmap="coolwarm")
    ax.set(xticks=range(len(amp)), xticklabels=amp, yticks=range(len(ids)), yticklabels=ids,
           xlabel="Lead amplitude / task span", title="Median matched benefit (N s)")
    fig.colorbar(image, ax=ax); fig.tight_layout(); fig.savefig(FIG / "coordination_condition_heatmap.png", dpi=150); plt.close(fig)
if feasibility["by_lead_amplitude_horizon_arm"]:
    fig, ax = plt.subplots(figsize=(7, 5))
    for lead, color in ((-1, "#2a6fbb"), (1, "#c94832")):
        subset = [x for x in feasibility["by_lead_amplitude_horizon_arm"] if x["lead"] == lead and x["arm"] == "MATCHED"]
        ax.scatter([x["amplitude"] for x in subset], [x["valid"] / x["attempts"] for x in subset], c=color, alpha=.65,
                   label="knee" if lead == -1 else "hip")
    ax.set(xlabel="Lead amplitude / task span", ylabel="Matched valid fraction", ylim=(-.05, 1.05))
    ax.legend(); fig.tight_layout(); fig.savefig(FIG / "feasibility_map.png", dpi=150); plt.close(fig)

status = "COORDINATION_PACING_EXPLORATION_COMPLETE" if (
    len(rows) >= 300 and (DOC / "CROSS_CONDITION_PLAN.json").exists() and
    len(rows) == sum(len(json.loads((DOC / name).read_text())["entries"]) for name in
                     ("COARSE_PLAN.json", "REFINEMENT_PLAN.json", "CROSS_CONDITION_PLAN.json"))) else "COORDINATION_PACING_EXPLORATION_PARTIAL"
report = f"""# Coordination & Pacing Decomposition Exploration v1

Status: **{status}**. Source {matrix['source_commit']}; {len(rows)} formal attempts ({counts['VALID']} VALID, {counts['INFEASIBLE']} INFEASIBLE, {counts['INVALID']} INVALID, {counts['EXCEPTION']} EXCEPTION). No learning was trained. Original production controller, Human dynamics, planner objective, safety screens, and scientific mode were unchanged.

## Timing path

The active zero-value/safe-action path does not use confidence/trust gamma. The waypoint scheduler chooses the shortest registered-grid quintic that meets fixed 0.5 velocity and 0.25 acceleration fractions, ROM, clearance, and phase time. Mechanics duration search can extend it; receipt governor, RSS/splice/fallback, measured-state terminal/HOLD transitions alter realized time. See CURRENT_TIMING_PATH_AUDIT.md.

## Matched protocol and primary result

The shortest baseline duration could not legally execute one mild altered path. This rejected pilot remains in MATCHED_PACING_VALIDATION.json. Before formal runs, v2 froze a common 1.3× registered-grid duration for each path and its matched baseline, retaining all original screens. Only equal segment-count and phase-residual ≤0.025 s comparisons are coordination-isolated.

There are {len(matched)} timing-isolated matched VALID runs of {len(matched_all)} matched VALID runs. Their median coordination benefit is {coord_summary['coordination_benefit_n_s']['median']} N s and best is {coord_summary['coordination_benefit_n_s']['max']} N s. Positive benefit means lower cumulative cuff-force integral. Mean/RMS/peak force changes are {coord_summary['mean_force_change_n']['median']}, {coord_summary['rms_force_change_n']['median']}, {coord_summary['peak_force_change_n']['median']} N at the median, respectively. These are descriptive within the frozen simulation conditions.

J_F_task integrates physical cuff-force magnitude over TASK samples. J_F_session additionally includes the preceding session boundary and fresh-track bootstrap cost. Benefits here compare J_F_task; mean force is J_F_task divided by TASK duration. Each valid raw result also records segment plans and realizations, q range, dq/ddq RMS, moments, clearance, governor records, RSS/fallback counts, and a sampled actual hip/knee path.

## Native outcome and timing

The native arm has {len(native)} VALID runs. Median native benefit is {native_summary['native_benefit_n_s']['median']} N s, best {native_summary['native_benefit_n_s']['max']} N s. Benefit versus duration-change Pearson correlation is {native_summary['benefit_vs_duration_change_pearson']}. The previous 85.948 N s best accompanied a 0.955 s shorter task and slightly higher mean force. No exact additive path/time decomposition is claimed because the matched and native baselines have different schedules.

## Feasibility and horizon

Rejection categories: {dict(feasibility['failure_reasons'])}. Matched first-1.5-s versus full benefit Pearson/Spearman: {credit['first_1p5']['pearson']} / {credit['first_1p5']['spearman']}. OUTBOUND relation: {credit['outbound']['pearson']} / {credit['outbound']['spearman']}. H1/H2/H3/H4 comparisons remain in the rollout table and figures. Individual infeasible and invalid attempts remain included.

## Conditions, adaptation, and learning readiness

The condition matrix distinguishes physical/task conditions from early/late adaptation states of the same low-ROM Human. Validation-role cases were excluded from pattern selection. Coverage-first, median-benefit and prevalidation-peak fixed comparators are documented in FIXED_VS_PERSONALIZED_ANALYSIS.json. Early/late matched ranking Spearman across {len(common_state_patterns)} shared patterns is {state_rank_spearman}. Validation had {cross_summary['valid_count']} VALID runs of {len(cross)} attempts. The existing value hook scores one next waypoint with a dimensionless additive scalar; a future long-horizon path action would require an explicit trajectory/chunk description and separately scaled force units. The smallest next experiment is a frozen fixed-pattern versus condition-indexed table comparison on fresh supported conditions; no learner is implemented here.

## Evidence and limits

See ALL_COORDINATION_ROLLOUTS.csv/json, benefit/feasibility/credit/cross-condition/fixed-policy summaries, CONDITION_MATRIX.json, raw file hashes in each rollout result and RAW_DATA_MANIFEST.json, STATE.json, and figures/. Results are deterministic counterfactual scientific simulation, not independent Human subjects, hardware evidence, or statistical significance. Validation exclusions and timing-confounded comparisons must be checked in the linked JSON before generalization.
"""
best_matched = coord_summary["best"]
best_native = native_summary["best"]
best_matched_percent = (100 * best_matched["benefit_n_s"] /
                        best_matched["baseline_J_F_task_n_s"] if best_matched else None)
best_matched_change = (next((x for x in matched_changes if x["run_id"] == best_matched["run_id"]), None)
                       if best_matched else None)
best_matched_baseline = (json.loads((RUNS / f"matched_baseline_{best_matched['condition_id']}_certified" /
                                   "rollout_result.json").read_text()) if best_matched else None)
best_outbound_lead = (best_matched["coordination_lead_metrics"]["OUTBOUND"]["mean_normalized_hip_minus_knee"]
                      if best_matched else None)
best_baseline_outbound_lead = (best_matched_baseline["coordination_lead_metrics"]["OUTBOUND"]["mean_normalized_hip_minus_knee"]
                               if best_matched_baseline else None)
matched_by_lead = {lead: [x for x in matched if x["lead"] == lead] for lead in (-1, 0, 1)}
infeasible_by_lead = {lead: sum(x["status"] == "INFEASIBLE" for x in rows if x["lead"] == lead)
                      for lead in (-1, 0, 1)}
attempts_by_lead = {lead: sum(x["lead"] == lead for x in rows) for lead in (-1, 0, 1)}
best_per_horizon = {h: max((x["benefit_n_s"] for x in matched if x["horizon"] == h), default=None)
                    for h in ("H1", "H2", "H3", "H4")}
horizon_summary_text = "; ".join(
    f"{h}: n={coord_summary['by_horizon'][h]['n']}, median={coord_summary['by_horizon'][h]['median']:.3f}, best={best_per_horizon[h]:.3f} N s"
    for h in ("H1", "H2", "H3", "H4") if best_per_horizon[h] is not None)
positive_horizons = [h for h, best in best_per_horizon.items() if best is not None and best > 0]
within_credit_spearman = stats([x["spearman"] for x in credit["within_condition_first_1p5"]])
within_credit_pair_agreement = stats([x["pairwise_agreement"] for x in credit["within_condition_first_1p5"]])
validation_fixed_positive = sum(x["timing_isolated"] and x["benefit_n_s"] > 0 for x in fixed_validation)
best_benefit_validation_description = "; ".join(
    f"{x['condition_id']}: {x['status']}, {x['benefit_n_s']} N s, timing-isolated={x['timing_isolated']}"
    for x in fixed_best_benefit_validation) or "none"
peak_validation_description = "; ".join(
    f"{x['condition_id']}: {x['status']}, {x['benefit_n_s']} N s, timing-isolated={x['timing_isolated']}"
    for x in prevalidation_peak_validation) or "none"
def pattern_desc(x):
    if x is None: return "none"
    p = x["pattern"]
    return (f"lead={p['lead']}, amplitude={p['amplitude']}, peak={p['peak']}, "
            f"horizon={p['horizon']}, return_reverse={p['return_reverse']}")
report += f"""
## Direct answers to the 17 scientific questions

1. **Active confidence/trust pacing?** No. The audited zero-value/safe-action scientific path contains no confidence/trust gamma in active timing decisions; historical pacing code is outside this path.

2. **Current segment/task speed?** The scheduler selects the shortest feasible 5 ms quintic using fixed 0.5 velocity and 0.25 acceleration fractions, ROM, continuous clearance and phase time. Mechanics duration search may lengthen it. Receipt governor deferrals, rolling splice, fallback, and measured-state phase/HOLD transitions determine realized task time.

3. **Coordination headroom at matched timing?** {'Yes, for at least one valid timing-isolated candidate' if any(x['benefit_n_s'] > 0 for x in matched) else 'No positive timing-isolated candidate in these attempted conditions'}. This applies only to rows with equal segment count and phase residual at most 0.025 s; {len(matched_all)-len(matched)} matched VALID rows remain timing-confounded. Held-out validation is addressed separately below.

4. **Best and typical matched benefit?** Best {coord_summary['coordination_benefit_n_s']['max']} N s ({best_matched_percent}% of that row's matched baseline); median {coord_summary['coordination_benefit_n_s']['median']} N s over {len(matched)} timing-isolated VALID rows. The best row is {best_matched['run_id'] if best_matched else 'none'} ({pattern_desc(best_matched)}), with RSS/fallback/duration-search counts {best_matched['rss_event_count'] if best_matched else None}/{best_matched['fallback_event_count'] if best_matched else None}/{best_matched['duration_search_count'] if best_matched else None} and minimum clearance {best_matched['minimum_clearance_m'] if best_matched else None} m. Selection of the maximum is exploratory.

5. **Cuff-force intensity?** Matched median candidate-minus-baseline changes in mean/RMS/peak force are {coord_summary['mean_force_change_n']['median']}/{coord_summary['rms_force_change_n']['median']}/{coord_summary['peak_force_change_n']['median']} N. For the best matched row they are {best_matched_change['mean_force_change_n'] if best_matched_change else None}/{best_matched_change['rms_force_change_n'] if best_matched_change else None}/{best_matched_change['peak_force_change_n'] if best_matched_change else None} N; its moment integral and peak change by {best_matched_change['moment_integral_change_nm_s'] if best_matched_change else None} N m s and {best_matched_change['moment_peak_change_nm'] if best_matched_change else None} N m. Per-run clearance changes are in COORDINATION_BENEFIT_SUMMARY.json; a lower force integral can coexist with a higher moment or intensity metric.

6. **Previous timing-mediated headroom?** The previous best 85.948 N s coincided with a 0.955 s shorter task and slightly higher mean force. Current native best is {native_summary['native_benefit_n_s']['max']} N s with duration change {best_native['duration_change_s'] if best_native else None} s, versus matched best {coord_summary['coordination_benefit_n_s']['max']} N s; those maxima use different baselines/candidates, so their difference is not a causal or additive timing share. The paired native/matched table and duration changes support only a descriptive timing interpretation.

7. **Promising ordering/path?** The strongest timing-isolated row is {pattern_desc(best_matched)} in {best_matched['condition_id'] if best_matched else 'none'}. Its measured OUTBOUND mean normalized hip-minus-knee lead is {best_outbound_lead}, versus {best_baseline_outbound_lead} for its matched baseline. Positive timing-isolated counts/valid comparisons by knee/synchronous/hip lead are {sum(x['benefit_n_s'] > 0 for x in matched_by_lead[-1])}/{len(matched_by_lead[-1])}, {sum(x['benefit_n_s'] > 0 for x in matched_by_lead[0])}/{len(matched_by_lead[0])}, and {sum(x['benefit_n_s'] > 0 for x in matched_by_lead[1])}/{len(matched_by_lead[1])}; inspect condition-specific effects before treating this as a policy.

8. **Infeasible patterns and reasons?** Infeasible counts/attempts by knee/synchronous/hip lead are {infeasible_by_lead[-1]}/{attempts_by_lead[-1]}, {infeasible_by_lead[0]}/{attempts_by_lead[0]}, and {infeasible_by_lead[1]}/{attempts_by_lead[1]}. Failure categories are {dict(feasibility['failure_reasons'])}; exact reasons and amplitudes remain in the rollout table and feasibility map. No safety threshold was relaxed.

9. **Benefit by horizon?** Timing-isolated horizon results are {horizon_summary_text}. The earliest tested horizon with a positive example is {positive_horizons[0] if positive_horizons else 'none'}. A positive example does not establish that horizon as a general optimum.

10. **Short-horizon credit?** First-1.5-s versus full matched benefit Spearman/Pearson are {credit['first_1p5']['spearman']}/{credit['first_1p5']['pearson']} pooled; median within-condition Spearman and pairwise agreement are {within_credit_spearman['median']} and {within_credit_pair_agreement['median']}. There are {credit['first_1p5']['short_better_full_worse']} short-better/full-worse and {credit['first_1p5']['short_worse_full_better']} short-worse/full-better sign reversals. Thus short scores provide partial ranking information but do not reliably decide full-repetition benefit; condition-specific details are in SHORT_LONG_COORDINATION_CREDIT.json.

11. **Condition-dependent preference?** Timing-isolated condition-specific best patterns are recorded for {len(condition_best)} state rows in FIXED_VS_PERSONALIZED_ANALYSIS.json. Matched and native best patterns agree in {sum(x['same_pattern'] for x in condition_arm_preference.values())} of {len(condition_arm_preference)} comparable state rows; scheduling and feasibility can therefore alter the apparent preference. These are in-sample optima from different schedules, not a causal timing-only test. Held-out validation rows are separately labeled.

12. **Adaptation-state preference?** The early/late low-ROM state comparison shares {len(common_state_patterns)} timing-isolated patterns and has rank Spearman {state_rank_spearman}. It tests ordering changes within that one physical task, without implying a new Human population.

13. **Fixed policy comparator?** The coverage-first fixed candidate is {pattern_desc(fixed_best)}; it was valid with matched timing in {fixed_best['physical_condition_count'] if fixed_best else 0} physical conditions and {fixed_best['condition_count'] if fixed_best else 0} state rows of discovery/refinement, with median benefit {fixed_best['median_benefit_n_s'] if fixed_best else None} N s. On validation conditions, {validation_fixed_positive} of {len(fixed_validation)} attempted coverage-first rows had positive timing-isolated benefit. The separate best-median-benefit fixed candidate is {pattern_desc(fixed_best_benefit)}; its held-out results are {best_benefit_validation_description}. The prevalidation peak matched pattern is {pattern_desc(prevalidation_peak)}; it was timing-isolated valid in {prevalidation_peak_support['physical_condition_count'] if prevalidation_peak_support else 0} discovery/refinement physical conditions, with median benefit {prevalidation_peak_support['median_benefit_n_s'] if prevalidation_peak_support else None} N s and positive fraction {prevalidation_peak_support['positive_fraction'] if prevalidation_peak_support else None}; its held-out results are {peak_validation_description}. All three were chosen without validation outcomes. Missing or infeasible rows count against broad applicability; a successful fixed comparator still requires prospective replication before deployment.

14. **Is personalization justified now?** The condition-best table can indicate heterogeneity, but it is in-sample. A claim that personalization improves over the frozen fixed comparator requires fresh condition-indexed validation; current evidence supports that comparison as the next test, not a trained personalized controller.

15. **Future learner action/horizon?** If that comparison later supports learning, represent lead direction, amplitude, catch-up peak, horizon, return behavior, multiple waypoint/phase path, and the pacing context. The current one-waypoint action cannot express a whole coordination chunk.

16. **Existing value hook?** The existing candidate_value_evaluator adds a dimensionless scalar for one next waypoint. It can rank local alternatives after explicit scaling, but a long-horizon trajectory/value model needs an interface carrying the multi-waypoint action and timing. Raw N s cannot be added directly to its dimensionless cost.

17. **Smallest next learning experiment?** On fresh supported conditions, preregister one frozen fixed coordination pattern and one condition-indexed lookup/table, apply the same certified matched/native pacing screens, and compare held-out full-task force, intensity, timing, feasibility and short/full rank. Train no neural policy until that simpler comparator fails.
"""
(DOC / "COORDINATION_PACING_EXPLORATION_REPORT.md").write_text(report)
fingerprints = {"schema": "coordination_pacing_fingerprints_v1", "git_head": subprocess.check_output(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
    "python": sys.version, "platform": platform.platform(),
    "numpy": np.__version__, "mujoco": mujoco.__version__,
    "matplotlib": matplotlib.__version__,
    "formal_run_source_commits": sorted({json.loads((RUNS / x["run_id"] / "rollout_result.json").read_text()).get("source_commit")
                                         for x in rows}),
    "files_sha256": {str(p.relative_to(ROOT)): digest(p) for p in
        [DOC / "CONDITION_MATRIX.json", DOC / "COORDINATION_PACING_EXPLORATION_CONTRACT_V2.json",
         STAGE / "scripts/high_rom_v1/coordination_pacing_adapter_v1.py",
         STAGE / "scripts/high_rom_v1/run_coordination_rollout_v1.py",
         STAGE / "scripts/high_rom_v1/run_coordination_campaign_v1.py",
         STAGE / "scripts/high_rom_v1/analyze_coordination_campaign_v1.py"]}}
save("FINGERPRINTS.json", fingerprints)
state = json.loads((DOC / "STATE.json").read_text())
state.update(status=status, phase="FINAL_ANALYSIS", formal_attempts=len(rows),
             next_action="review report and compare fixed policy against condition-indexed table in a future preregistered study")
save("STATE.json", state)
print(json.dumps({"status": status, "attempts": len(rows), "timing_isolated": len(matched),
                  "best_coordination_benefit_n_s": coord_summary["coordination_benefit_n_s"]["max"],
                  "best_native_benefit_n_s": native_summary["native_benefit_n_s"]["max"]}))
