# Online decision budget audit

This is a read-only architecture audit and descriptive historical host profile for Learning Research v1. Source starting HEAD was `8654cf0`. It does not qualify hardware, wall-causal execution, worst-case execution time, or a learned controller. `RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` remains authoritative.

## Preliminary budget comes from the reference architecture

The 5 ms control/sample period is not a 5 ms high-level learner deadline. In `full3d_adaptive_integration_v1/runtime.py:3129–3219`, task planner requests occur at phase starts and completed old waypoint endpoints. An already admitted waypoint schedule executes without a high-level decision every control period. For the three read-only scientific baseline artifacts listed in the JSON, 41 task decisions have selected schedule duration median 0.620 s, p95 1.595 s, maximum 1.595 s. The 38 successive request sample intervals have median 0.8325 s, p95 1.60575 s and maximum 1.610 s. These intervals include HOLD/phase changes and are descriptive, not guaranteed decision slack.

For a moving waypoint endpoint, `safe_fallback.prepare_decision` admits a constant-velocity bridge of `8 × reference_period_s = 40 ms` and a stop before admitting the selected primary. The bridge forks at the latest certified grid node strictly before its endpoint. All 20 observed bridges in this audit have a 35 ms commit progress. A late or unvalidated primary cannot reverse the one-way `FallbackLatch` after braking commits. The certified stop then remains independently executable, but it does not extend the old action ranking deadline or make a late result acceptable. Stationary endpoints may wait under the existing supervisor and phase deadlines; they do not receive an arbitrary universal 35 ms deadline.

The independent source expiration ceiling is **strictly less than 100 ms**, beginning at the original sensor capture rather than worker start or revalidation capture. `online_planning.PlanLifecycle.expired/activate` enforces wall monotonic age in wall-causal mode. `execution_policy.ScientificPlanLifecycle` freezes the submission epoch while producer work completes and uses physical simulation age/epoch validity. Therefore, slow wall computation in Scientific Simulation does not invalidate the scientific trajectory, but its host profile must not be reported as a wall-causal budget PASS.

The preliminary producer budget for an actual moving handoff is:

`B = max(0, min(100 ms − source_age_at_observation_ready, certified_fork_progress − current_reference_progress, phase_remaining − selected_schedule_duration) − measured_activation_reserve)`.

`activation_reserve` includes worker-to-main collection, current-state activation revalidation, command construction and write. It must be measured on the deployment architecture; neither a fixed unexplained reserve nor hardware reliability can be inferred here. Fork progress is a reference-progress opportunity and is not itself a wall-clock guarantee. Once braking commits, drop the old result; restart from a fresh observation after the certified stop/hold if the existing architecture permits it.

## What actually belongs in full decision latency

The observed causal path is:

1. `WallPhysicsSession.capture` / runtime `_capture_boundary`: acquire the allowed deployable observation and preserve its original source capture epoch.
2. `AdaptiveHumanWaypointHWMPCV22.decide`: construct the current belief model, deployable value context and mechanics screen closure.
3. Research proposal adapter / `HumanWaypointFeedbackMPCV1.candidate_actions`: propose next hip/knee targets.
4. `TerminalSetHumanWaypointPlannerV1._evaluate` and `HumanWaypointFeedbackMPCV1._evaluate`: schedule each target through the existing quintic scheduler, continuous geometry/clearance, phase-time limits, optional mechanics duration search, current belief mechanics, and causal tracking offset clearance.
5. Research adapter: construct scaled deployable state/action/schedule features, predict Q only for admissible candidates and select by separate remaining-cost ranking. Log the original planner score. The historical raw hook adds `future_value` into its dimensionless cost and is not a valid place to add raw N·s.
6. `safe_fallback.prepare_decision`: attach the selected moving-endpoint primary's bridge/stop admission certificate before execution.
7. Runtime collects the worker result, checks C2 boundary continuity and constructs current activation validator.
8. `activation_validation.validate_activation` / `validate_rolling_composite`: revalidate the actual selected schedule against the current phase, model sequence, mechanics, geometry signature, causal state, original time budget and safe escape. Candidate admission at step 4 does not replace this later validation.
9. Runtime `_execute_interval` constructs the authoritative low-level controller/supervisor command and lifecycle activation checks source age at actual write.

Full requested latency ends at reference ready/validated for execution (step 8), with actual command activation (step 9) reported separately as a conservative additional boundary. Sensor-capture-to-validation/activation is broader than observation-ready-to-validation and is useful when an exact observation-ready event is absent. It must be labeled accurately.

`PlanLifecycle.records()` already preserves capture, request, snapshot, enqueue, worker start/finish, result collection, validation start/finish, actual activation and disposition. The new `latency_evidence.py` joins research decomposition only within each run and preserves failed/expired outcomes. Missing older feature/proposal/Q fields are missing evidence, not zero-duration stages. The new `latency_tools.DecisionLatency` refuses to classify inference-only traces as a complete pipeline measurement and includes interstage gaps in its total.

## Historical actual host profile

The audit JSON fingerprints three unchanged `wsl_learning_scientific_baseline_v1` artifacts: synchronous high-ROM, hip-leading high-ROM and ordinary low-ROM. All 41 task requests activated under Scientific Simulation. Their host timing is:

| Actual measured boundary | Median | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|
| Capture → selected reference validated | 50.953 ms | 67.231 ms | 69.153 ms | 70.166 ms |
| Capture → actual command activation | 51.452 ms | 67.684 ms | 69.454 ms | 70.468 ms |
| Worker computation | 31.620 ms | 44.540 ms | 45.232 ms | 45.678 ms |
| Worker finish → main result collection | 10.534 ms | 12.852 ms | 13.703 ms | 13.792 ms |
| Validation + command construction | 7.604 ms | 10.987 ms | 11.255 ms | 11.313 ms |

These raw data already show why inference-only timing would be misleading. Historical host computation plus collection and activation work is often longer than the 35 ms moving-bridge opportunity, despite each scientific physical epoch remaining valid. The learner must measure its actual added candidate scheduling work; it cannot infer adequate latency from a tiny network or from the 0.6–1.6 s waypoint duration. Computation is the largest measured component; main-loop collection and final validation also matter. No policy distillation is justified solely by this historical profile: first measure the research adapter's full candidate-count scaling and avoid redundant baseline/candidate evaluation where the scientific interface permits that engineering improvement.

## Delivered instrumentation and limits

New modules under `scripts/value_learning_v1/`:

- `latency_tools.py`: strict stage recorder, actual distributions (median/p95/p99/max), explicit architecture opportunity calculation and failure-preserving summaries.
- `latency_test_tools.py`: six accounting guards; PASS after correcting a floating-point equality in a test, with no behavioral/scientific source change.
- `latency_evidence.py`: read-only aggregation of existing request/activation metadata, selected schedule duration, moving bridge/fork duration, and chosen candidate `execution_screen.research_latency` decomposition.
- `latency_benchmark_models.py`: `benchmark_models(models, X)` against **actual trained** `model.predict(X)` models and actual recorded features; batched/unbatched candidate-count scaling, CPU input copying and first/warm call effects. `time_actual_update` separately times the actual update operation. This utility does not manufacture synthetic training measurements or claim full-decision timing.

CPU is mandatory in this campaign. The planned NumPy scaled ridge and small tanh MLP have no GPU inference dependency; optional GPU is useful only after a genuine GPU model path exists and transfer cost can be measured. Model training/update must produce versioned candidates off the active task path, validate them and switch at explicit repetition boundaries. If a candidate is absent/late, retain the last validated active model; do not retrain it in place.

Actual current learned-pipeline and trained-model benchmark results must be saved separately by the coordinator after the adapter/models exist. This audit is a prerequisite, not completion of the latency gate.
