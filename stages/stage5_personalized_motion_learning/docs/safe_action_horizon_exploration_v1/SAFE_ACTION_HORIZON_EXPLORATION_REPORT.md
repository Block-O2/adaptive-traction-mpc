# Safe Action-Space & Horizon Exploration v1

Status: **SAFE_ACTION_HORIZON_EXPLORATION_COMPLETE**. Scientific host: Y9000P / Ubuntu WSL2. Source: `origin/codex/zero-value-30rep-baseline-v3` at `1f6308b820b64fc2cc7d8a01baa42e433835e68e`. Campaign branch: `codex/safe-action-horizon-exploration-v1`. No RL or value learning was started. The production planner, controller, Human dynamics, scientific semantics and safety thresholds were not changed.

## Scientific question and method

The primary outcome is `J_F_task = integral ||F_cuff_measured|| dt` over OUTBOUND, HOLD and RETURN. `Benefit = matched_baseline_J_F_task - exploration_J_F_task`; positive means lower cumulative interaction cost. Force and moment, clearance, duration, smoothness, task completion and physical/scientific validity were retained as separate outcomes; no weighted reward was fitted.

The existing checkpoint after Rep1, Rep5, Rep15 and Rep25 seeded counterfactual Rep2, Rep6, Rep16 and Rep26. Unmodified matched baseline replays reproduced all four corresponding V3 `J_F_task` values to recorded precision, with physical and scientific PASS. Exploration never wrote state or Human-model updates back to those formal checkpoints. Source checkpoint hashes, candidate parameters, full path/trace artifacts, statuses, outcomes and raw file hashes are recorded in the manifests.

The isolated adapter proposes alternate 2D hip/knee waypoint progress and coordination through the existing planner feasibility screen, constrained quintic schedule, safety checks, controller, dynamics and scientific scorer. H1 affects one OUTBOUND decision; H2 affects three; H3 covers OUTBOUND; H4 covers OUTBOUND and RETURN. Accepted trajectories remain continuous and satisfy the existing gates. Small/medium/large and refined amplitudes scale the baseline local waypoint increment; remaining task span and a two-times generator-step research cap bound proposals, while the unchanged feasibility screens determine which are legal. Realized angular deviations are recorded per run. Counterfactuals use simulation only; simulation truth does not select an action.

The frozen coarse plan attempted 120 combinations. A subsequent frozen refinement plan attempted 64 around faster progress and the hip-leading clearance boundary. Cross-state validation then replayed five discovered best, near-neutral and safe-worse patterns at all four adaptation states (20 attempts). There were **204 formal attempts: 151 VALID, 48 INFEASIBLE and 5 INVALID**. Every valid run completed the task with physical and scientific PASS. The 53 rejected/invalid cases were geometry or clearance related. Four matched replays and four preserved infrastructure pilots are outside the 204 formal attempts. Two bounded infrastructure repair cycles fixed exploration bookkeeping/classification; neither altered production science.

## Action-space audit and behavioral diversity

All 390 V3 decisions were audited. The production action is a next Human hip/knee waypoint increment. Its regular OUTBOUND/RETURN candidates are five positive phase-progress coordination ratios at 0.5 or 1.0 scale of 20% task span. Median feasible candidates per decision were 9 OUTBOUND and 10 RETURN, with median maximum pairwise target distance **3.971 degrees** and direction spread **30.438 degrees**. HOLD has one candidate. The same selected label in all 390 decisions therefore demonstrates a stable choice within this lattice; it does not establish that the legal action landscape is exhausted.

Exploration produced physically different behavior. Among 151 valid branches, median first waypoint deviation from the matched baseline was **1.455 degrees** (range **0.364–5.371**), median reference-path RMS difference **3.048 degrees**, Human-q RMS difference **2.979 degrees**, Human-dq RMS difference **10.397 degrees/s**, and force-vector RMS difference **8.253 N**. The first target lay outside the baseline first-candidate convex hull in **129/151** valid runs and **56/56** beneficial runs. The best run's first action differed by **2.239 degrees**, with reference-path RMS difference **6.479 degrees**. This is evidence that the generator misses a productive progress region, despite its nonzero local candidate spread. It does not imply every outside-hull action is beneficial.

## Headroom, amplitude and force tradeoff

Of 151 valid branches, **56** had positive Benefit. Their median Benefit was **37.550 N·s** (about **7.50%** of matched baseline), or **58.44 times** the V3 late repetition SD of 0.642500 N·s and **19.61 times** its range of 1.914894 N·s. These comparisons are descriptive effect sizes, not statistical significance. The overall valid-sample median Benefit was **−8.655 N·s**; arbitrary legal perturbation was often worse. Amplitude alone had little monotonic predictive power across all directions (Spearman **0.046** for first-action deviation versus Benefit).

The largest observed legal Benefit was **85.948499 N·s (17.1375%)** at the EARLY state, using faster/large/H4: baseline **501.521818** to exploration **415.573318 N·s**. This is **133.77** baseline SDs and **44.88** baseline ranges as descriptive references. The first action was 2.239 degrees from baseline. A smaller faster/fine-high/H4 version gave **73.071–73.512 N·s** across four states. The finer faster-progress sweep showed positive benefits at smaller amplitudes as well; no universal angular threshold can be inferred because direction and duration matter.

The best run's completion time fell from **5.560 to 4.605 s**. Its mean measured task force rose slightly from **90.202 to 90.244 N**; peak cuff force rose **2.398 N** to **111.157 N**. Its minimum deployable clearance fell **1.614 mm** to **16.087 mm** while retaining PASS; peak moment was **14.890 N·m**, cumulative moment **45.775 N·m·s**. Algebraic decomposition of the integral attributes **+86.143 N·s** to reduced task duration and **−0.194 N·s** to the mean-force change. Across the 56 beneficial runs, median first-1.5-s Benefit was **−4.637 N·s**, median duration change **−0.420 s**, and median mean-force change **+0.062 N**. Thus the discovered objective headroom is principally **less time under cuff load**, not lower force intensity. Force, clearance and moment should remain explicit alongside integral cost in any later decision.

## Horizon and credit assignment

The best H4 branch looked worse at first: Benefit **−1.108 N·s** over 0.5 s and **−5.254 N·s** over 1.5 s. It became **+43.190 N·s** over OUTBOUND and **+85.948 N·s** over the full repetition. Across valid attempts, H1/H2/H3/H4 maximum full-task Benefits were **13.971 / 43.493 / 42.323 / 85.948 N·s**. The strongest differences emerged by OUTBOUND and strengthened when faster progress was sustained through RETURN.

First-1.5-s Benefit predicted full-task Benefit poorly and in the wrong direction in this designed sweep: Pearson **−0.896**, Spearman **−0.923**, and within-checkpoint pairwise ranking agreement **11.4%** (313 concordant, 2430 discordant pairs). There were **56** short-worse/full-better and **69** short-better/full-worse valid branches. Immediate-to-full Spearman was **−0.784**. Benefit tracked duration reduction closely (Pearson **0.9994**). These are descriptive associations within a nonrandom designed set, with related candidates and shared states. They show a clear horizon/credit issue for this outcome: selecting by near-term cuff-force integral would reject the best sustained faster behavior.

## State dependence and fixed-behavior test

Cross-state validation used five patterns at each of four frozen Human-adaptation states. Full-task Benefit (N·s) was:

| Pattern | Rep2 | Rep6 | Rep16 | Rep26 |
|---|---:|---:|---:|---:|
| faster / large / H4 | **85.948** | **85.026** | **84.562** | **85.109** |
| faster / fine-high / H4 | 73.433 | 73.075 | 73.071 | 73.512 |
| faster / small / H3 | −0.100 | −0.559 | −0.557 | −0.200 |
| hip-leading / very-small / H2 | −24.516 | −24.038 | −24.425 | −23.102 |
| slower / small / H1 | −9.897 | −11.266 | −11.315 | −10.817 |

No best-direction switch was observed among these four states and five validation patterns, despite Human-model progression. A simple fixed faster-progress behavior is therefore a serious comparator for this registered task. This does not exclude state dependence in other tasks, less sampled regions, conditions or real hardware. These states were also used during discovery/refinement, so the cross-state repeat is a reproducibility check, not independent held-out validation.

## Safety and feasibility landscape

Faster progress was valid in **80/80** attempted branches, slower in **24/24**. Hip-leading was valid in **28/40**, with 12 infeasible; hip-dominant was 16 valid, 2 infeasible and 2 invalid. Knee-leading was **3/20** valid; knee-dominant was **0/20** valid. All rejection reasons were existing shank/table geometry, causal tracking-offset clearance or session clearance limit. Longer H4 hip-leading deviations met the clearance boundary even at very small tested amplitude. No clearance, ROM, speed, acceleration, force or scientific-validity requirement was loosened. A rejected pattern is a map of the current safe domain, not a candidate to repair by weakening a threshold.

## Answers and next research step

1. **Current action diversity:** nonzero within the positive-progress lattice, but it omits the observed productive faster-progress region; 56/56 beneficial first actions began outside its first-candidate hull.
2. **Maximum legal Benefit:** 85.948499 N·s, 17.1375%, in a complete PASS repetition.
3. **Typical positive Benefit:** median 37.550 N·s among 56 positive runs; overall median is negative.
4. **Relative to baseline variation:** best 133.77 SDs; positive median 58.44 SDs. These are effect-size references only.
5. **Required deviation:** the best first step was 2.239 degrees away; benefits also occurred at smaller locally scaled faster steps. There is no global degree threshold.
6. **Horizon of meaningful separation:** OUTBOUND reveals the major difference; sustained H4 gives the largest full-task gains.
7. **Short versus full ranking:** strongly inverted in this design; within-state pairwise agreement 11.4%.
8. **State dependence:** the tested best faster pattern held across EARLY through LATE states, with no switch observed.
9. **Fixed behavior:** a fixed faster-progress schedule may capture much of this task's headroom; it needs broader independent testing.
10. **Long-horizon credit:** yes, primarily because cumulative force depends on completion duration while early force can be higher.
11. **Unsafe regions:** knee-leading/dominant and sustained hip-leading are often blocked by the existing clearance/geometry gates.
12. **Next control freedom:** study **phase-progress rate and sustained OUTBOUND/RETURN pacing** against a fixed-policy comparator across new tasks, starting states and Human conditions, while reporting mean/peak force, clearance and duration separately. Do not select or train a learner yet.

This campaign used deterministic scientific simulation and selected adaptation checkpoints. It does not establish statistical significance, generalize to hardware, or prove a global optimum. In particular, lower `J_F_task` here should not be described as lower force intensity. The next stage should pre-register broader held-out validation and retain all hard safety screens before deciding whether personalization or a more complex learner is needed.

## Evidence map

- Frozen design: `ACTION_HORIZON_EXPLORATION_CONTRACT.md/json`; V3 audit: `CURRENT_ACTION_SPACE_AUDIT.md/json`.
- Per-attempt data: `ALL_EXPLORATORY_ROLLOUTS.csv/json`; stage plans/progress: `COARSE_PLAN.json`, `REFINEMENT_PLAN.json`, `CROSS_STATE_PLAN.json`, and progress JSONs.
- Aggregates: `ACTION_DIVERSITY_SUMMARY.json`, `HORIZON_HEADROOM_SUMMARY.json`, `CROSS_STATE_VALIDATION.json`, `FAILURE_INFEASIBILITY_SUMMARY.json`.
- Integrity: `MATCHED_BASELINE_REPLAY.json`, `RAW_DATA_MANIFEST.json`, `PRODUCTION_FINGERPRINT.json`, `STATE.json`; raw traces are Git-ignored under `results/safe_action_horizon_exploration_v1/runs`.
- Figures: `figures/` contains six static distribution, amplitude, horizon, state, short/full, and diversity plots.
