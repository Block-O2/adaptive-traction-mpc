# Coordination & Pacing Decomposition Exploration v1

Status: **COORDINATION_PACING_EXPLORATION_COMPLETE**. Source b8a3989f7bd2d96938d0012857499a0321f05d5e; 518 formal attempts (356 VALID, 158 INFEASIBLE, 4 INVALID, 0 EXCEPTION). No learning was trained. Original production controller, Human dynamics, planner objective, safety screens, and scientific mode were unchanged.

## Timing path

The active zero-value/safe-action path does not use confidence/trust gamma. The waypoint scheduler chooses the shortest registered-grid quintic that meets fixed 0.5 velocity and 0.25 acceleration fractions, ROM, clearance, and phase time. Mechanics duration search can extend it; receipt governor, RSS/splice/fallback, measured-state terminal/HOLD transitions alter realized time. See CURRENT_TIMING_PATH_AUDIT.md.

## Matched protocol and primary result

The shortest baseline duration could not legally execute one mild altered path. This rejected pilot remains in MATCHED_PACING_VALIDATION.json. Before formal runs, v2 froze a common 1.3× registered-grid duration for each path and its matched baseline, retaining all original screens. Only equal segment-count and phase-residual ≤0.025 s comparisons are coordination-isolated.

There are 132 timing-isolated matched VALID runs of 171 matched VALID runs. Their median coordination benefit is -0.09954619560920719 N s and best is 40.62796012470335 N s. Positive benefit means lower cumulative cuff-force integral. Mean/RMS/peak force changes are -0.037787561685981075, -0.0312305655803371, -4.881672727208297e-05 N at the median, respectively. These are descriptive within the frozen simulation conditions.

J_F_task integrates physical cuff-force magnitude over TASK samples. J_F_session additionally includes the preceding session boundary and fresh-track bootstrap cost. Benefits here compare J_F_task; mean force is J_F_task divided by TASK duration. Each valid raw result also records segment plans and realizations, q range, dq/ddq RMS, moments, clearance, governor records, RSS/fallback counts, and a sampled actual hip/knee path.

## Native outcome and timing

The native arm has 185 VALID runs. Median native benefit is -6.69415619539609 N s, best 56.41865604539271 N s. Benefit versus duration-change Pearson correlation is -0.8695285133710989. The previous 85.948 N s best accompanied a 0.955 s shorter task and slightly higher mean force. No exact additive path/time decomposition is claimed because the matched and native baselines have different schedules.

## Feasibility and horizon

Rejection categories: {'clearance': 99, 'acceleration': 20, 'other': 28, 'velocity': 15}. Matched first-1.5-s versus full benefit Pearson/Spearman: -0.09700661144427797 / 0.49133585875066177. OUTBOUND relation: 0.27656309561440534 / 0.5925552952471392. H1/H2/H3/H4 comparisons remain in the rollout table and figures. Individual infeasible and invalid attempts remain included.

## Conditions, adaptation, and learning readiness

The condition matrix distinguishes physical/task conditions from early/late adaptation states of the same low-ROM Human. Validation-role cases were excluded from pattern selection. Coverage-first, median-benefit and prevalidation-peak fixed comparators are documented in FIXED_VS_PERSONALIZED_ANALYSIS.json. Early/late matched ranking Spearman across 12 shared patterns is 0.5034965034965035. Validation had 24 VALID runs of 28 attempts. The existing value hook scores one next waypoint with a dimensionless additive scalar; a future long-horizon path action would require an explicit trajectory/chunk description and separately scaled force units. The smallest next experiment is a frozen fixed-pattern versus condition-indexed table comparison on fresh supported conditions; no learner is implemented here.

## Evidence and limits

See ALL_COORDINATION_ROLLOUTS.csv/json, benefit/feasibility/credit/cross-condition/fixed-policy summaries, CONDITION_MATRIX.json, raw file hashes in each rollout result and RAW_DATA_MANIFEST.json, STATE.json, and figures/. Results are deterministic counterfactual scientific simulation, not independent Human subjects, hardware evidence, or statistical significance. Validation exclusions and timing-confounded comparisons must be checked in the linked JSON before generalization.

## Direct answers to the 17 scientific questions

1. **Active confidence/trust pacing?** No. The audited zero-value/safe-action scientific path contains no confidence/trust gamma in active timing decisions; historical pacing code is outside this path.

2. **Current segment/task speed?** The scheduler selects the shortest feasible 5 ms quintic using fixed 0.5 velocity and 0.25 acceleration fractions, ROM, continuous clearance and phase time. Mechanics duration search may lengthen it. Receipt governor deferrals, rolling splice, fallback, and measured-state phase/HOLD transitions determine realized task time.

3. **Coordination headroom at matched timing?** Yes, for at least one valid timing-isolated candidate. This applies only to rows with equal segment count and phase residual at most 0.025 s; 39 matched VALID rows remain timing-confounded. Held-out validation is addressed separately below.

4. **Best and typical matched benefit?** Best 40.62796012470335 N s (2.6561165040366226% of that row's matched baseline); median -0.09954619560920719 N s over 132 timing-isolated VALID rows. The best row is validation_sync_120_000_matched (lead=1, amplitude=0.12, peak=0.5, horizon=H3, return_reverse=False), with RSS/fallback/duration-search counts 10/10/0 and minimum clearance 0.009887531875584759 m. Selection of the maximum is exploratory.

5. **Cuff-force intensity?** Matched median candidate-minus-baseline changes in mean/RMS/peak force are -0.037787561685981075/-0.0312305655803371/-4.881672727208297e-05 N. For the best matched row they are -2.0781565281178302/-2.2675590171344737/-2.714224954144086 N; its moment integral and peak change by 2.8988440745103077 N m s and 0.1890037543497325 N m. Per-run clearance changes are in COORDINATION_BENEFIT_SUMMARY.json; a lower force integral can coexist with a higher moment or intensity metric.

6. **Previous timing-mediated headroom?** The previous best 85.948 N s coincided with a 0.955 s shorter task and slightly higher mean force. Current native best is 56.41865604539271 N s with duration change 0.3600000000017207 s, versus matched best 40.62796012470335 N s; those maxima use different baselines/candidates, so their difference is not a causal or additive timing share. The paired native/matched table and duration changes support only a descriptive timing interpretation.

7. **Promising ordering/path?** The strongest timing-isolated row is lead=1, amplitude=0.12, peak=0.5, horizon=H3, return_reverse=False in sync_120. Its measured OUTBOUND mean normalized hip-minus-knee lead is 0.0919989488441953, versus 0.01894531958730701 for its matched baseline. Positive timing-isolated counts/valid comparisons by knee/synchronous/hip lead are 5/54, 0/2, and 54/76; inspect condition-specific effects before treating this as a policy.

8. **Infeasible patterns and reasons?** Infeasible counts/attempts by knee/synchronous/hip lead are 105/236, 4/18, and 49/264. Failure categories are {'clearance': 99, 'acceleration': 20, 'other': 28, 'velocity': 15}; exact reasons and amplitudes remain in the rollout table and feasibility map. No safety threshold was relaxed.

9. **Benefit by horizon?** Timing-isolated horizon results are H1: n=55, median=-0.149, best=3.463 N s; H2: n=15, median=-0.051, best=4.072 N s; H3: n=36, median=0.131, best=40.628 N s; H4: n=26, median=0.100, best=6.661 N s. The earliest tested horizon with a positive example is H1. A positive example does not establish that horizon as a general optimum.

10. **Short-horizon credit?** First-1.5-s versus full matched benefit Spearman/Pearson are 0.49133585875066177/-0.09700661144427797 pooled; median within-condition Spearman and pairwise agreement are 0.39999999999999997 and 0.6666666666666666. There are 22 short-better/full-worse and 5 short-worse/full-better sign reversals. Thus short scores provide partial ranking information but do not reliably decide full-repetition benefit; condition-specific details are in SHORT_LONG_COORDINATION_CREDIT.json.

11. **Condition-dependent preference?** Timing-isolated condition-specific best patterns are recorded for 9 state rows in FIXED_VS_PERSONALIZED_ANALYSIS.json. Matched and native best patterns agree in 1 of 9 comparable state rows; scheduling and feasibility can therefore alter the apparent preference. These are in-sample optima from different schedules, not a causal timing-only test. Held-out validation rows are separately labeled.

12. **Adaptation-state preference?** The early/late low-ROM state comparison shares 12 timing-isolated patterns and has rank Spearman 0.5034965034965035. It tests ordering changes within that one physical task, without implying a new Human population.

13. **Fixed policy comparator?** The coverage-first fixed candidate is lead=-1, amplitude=0.02, peak=0.3, horizon=H1, return_reverse=False; it was valid with matched timing in 6 physical conditions and 7 state rows of discovery/refinement, with median benefit -0.0839880272397977 N s. On validation conditions, 0 of 2 attempted coverage-first rows had positive timing-isolated benefit. The separate best-median-benefit fixed candidate is lead=-1, amplitude=0.02, peak=0.7, horizon=H4, return_reverse=False; its held-out results are sync_120: VALID, 1.0574601542962228 N s, timing-isolated=True; variable_start_120: VALID, 1.033690192600261 N s, timing-isolated=True. The prevalidation peak matched pattern is lead=1, amplitude=0.12, peak=0.5, horizon=H3, return_reverse=False; it was timing-isolated valid in 5 discovery/refinement physical conditions, with median benefit -0.0950234865525772 N s and positive fraction 0.4; its held-out results are sync_120: VALID, 40.62796012470335 N s, timing-isolated=True; variable_start_120: VALID, 39.76163408409502 N s, timing-isolated=True. All three were chosen without validation outcomes. Missing or infeasible rows count against broad applicability; a successful fixed comparator still requires prospective replication before deployment.

14. **Is personalization justified now?** The condition-best table can indicate heterogeneity, but it is in-sample. A claim that personalization improves over the frozen fixed comparator requires fresh condition-indexed validation; current evidence supports that comparison as the next test, not a trained personalized controller.

15. **Future learner action/horizon?** If that comparison later supports learning, represent lead direction, amplitude, catch-up peak, horizon, return behavior, multiple waypoint/phase path, and the pacing context. The current one-waypoint action cannot express a whole coordination chunk.

16. **Existing value hook?** The existing candidate_value_evaluator adds a dimensionless scalar for one next waypoint. It can rank local alternatives after explicit scaling, but a long-horizon trajectory/value model needs an interface carrying the multi-waypoint action and timing. Raw N s cannot be added directly to its dimensionless cost.

17. **Smallest next learning experiment?** On fresh supported conditions, preregister one frozen fixed coordination pattern and one condition-indexed lookup/table, apply the same certified matched/native pacing screens, and compare held-out full-task force, intensity, timing, feasibility and short/full rank. Train no neural policy until that simpler comparator fails.
