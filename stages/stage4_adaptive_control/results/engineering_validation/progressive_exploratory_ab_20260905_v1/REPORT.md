# Exploratory progressive-interface A/B at 0.25 ms

> [!IMPORTANT]
> **PRE-CORRECTION / RETIRED DIAGNOSTIC EVIDENCE**
>
> This report predates the corrected low-latency robot velocity-feedback
> measurement path and is retained only as diagnostic provenance. Current
> authoritative conclusions are in [CURRENT_STATE](../../../docs/research/CURRENT_STATE.md)
> and the [corrected High-ROM evidence](../../summaries/phase3a_corrected_high_rom/README.md).
> Commands and paths below are frozen historical provenance; they are retired,
> non-current, and must not be treated as executable reproduction instructions.



**Executed 2/6 scheduled runs. Campaign stopped: positive_interface_energy_residual, compliant_40_40_loses_rigid_completion.**

Exploratory diagnostic evidence only. The previous failed bench qualification, including the 0.25 ms energy residual, remains unchanged. No clinical safety, validated compliance physics or authoritative capability claim is supported.

## Frozen setup

Spec JSON SHA256: `88b03c298c43306adbd2928ebf954fbbd0610c940045d963995d531851d3cea4`

Spec MD SHA256: `30569ef9a404c6fd32de5eaddaa1690b5ca0705d51b4e2e530c4c1544e3a6bed`

Branch codex/interface-phase3a-de23ea3; HEAD `99169491ea1336d6af74e3b63318afba18c1e881`. Controller baseline `de23ea3cdf9f0fb078496ba5ba4abb6a205ad955`.

Candidate P1 only: F=−(K1+K3||x||²)x−Dv; M=−(Kr1+Kr3||theta||²)theta−Dr*omega, with the registered two-port frame/moment transport. Fixed coincident rest frames; no preload capture. P1 was selected before these task results as the lower small-motion stiffness registered candidate. No P2 trial.

| Parameter | Value |
| --- | --- |
| damping_ns_m | 490.684 |
| k1_n_m | 60000 |
| k3_n_m3 | 5e+10 |
| kr1_nm_rad | 1800 |
| kr3_nm_rad3 | 4e+06 |
| rotational_damping_nms_rad | 12.448 |

Both arms have 0.25 ms physics, 20 substeps per unchanged 5 ms control tick. Same de23ea3 controller stack, suspended_high_rom, nominal High-ROM Human, frozen population prior/model/geometry, 140 mm adapter, seed 44104, trajectory law/timing, force contracts, Reference Manager, Safety Filter and BRAKE. Every executed run used a fresh process/state.

Controller bytecode is unchanged; local CONTROL_SUBSTEPS=20 preserves control cadence. The compliant arm uses its registered robot-port sensor adapter with unchanged noise/filter/sampling. Rigid mechanics and sensor reconstruction retain the baseline implementation.

## Six scheduled runs

| Trajectory | Arm | Task | Reason | Sim time s | RMSE deg | Endpoint deg | Return/final offset deg | Force class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40/40 | rigid | COMPLETE | reference_completed | 14.1062 | 0.157621 | 0.000533182 | 0.0127876 | STRICT_PASS |
| 40/40 | P1 | DIAGNOSTIC_STOP | positive_interface_energy_residual | 0.0005 | 0.000224217 | — | 0.000419345 | STRICT_PASS |
| 40/80 | rigid | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 40/80 | P1 | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 90/120 | rigid | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 90/120 | P1 | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |

Return/final offset is error from initial [5,10] deg at the last sample. When return_reached=false, this is NOT a completed return error. Missing endpoint means the target hold was not reached. All incomplete-run RMS/peak values cover only that executed prefix.

| Trajectory | Arm | Command RMS/peak N | Physical RMS/peak N | Force-rate peak N/s | Moment peak Nm | Translation mm | Rotation deg | Wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40/40 | rigid | 99.1582 / 121.049 | 98.9913 / 117.448 | 251692 | 17.6907 | 0.0475381 | 0.0683494 | 31.0286 |
| 40/40 | P1 | 85.625 / 85.625 | 2.64814 / 4.30863 | 8711.51 | 0.874077 | 0.00317482 | 0.00143959 | 0.324808 |
| 40/80 | rigid | — / — | — / — | — | — | — | — | — |
| 40/80 | P1 | — / — | — / — | — | — | — | — | — |
| 90/120 | rigid | — / — | — / — | — | — | — | — | — |
| 90/120 | P1 | — / — | — / — | — | — | — | — | — |

RMS force values are time-weighted trapezoidal norms. Command RMS uses issued-command timestamps; physical RMS uses physics timestamps. Force/moment rates are world-vector finite differences using actual dt. The baseline raw summary assumes 1 ms for some derivatives; those uncorrected fields are preserved but not used here.

## Matched-prefix force/tracking/deformation trade-off

Full rigid and truncated compliant peaks are not a matched whole-task comparison. The following comparisons crop both arms to the same physical-time interval without shifting/smoothing; reference phases may still diverge because the unchanged manager responds to different observations.

| Trajectory | Common end s | Arm | Force peak N | Force RMS N | Rate peak N/s | Tracking RMSE deg | Translation mm | Rotation deg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [40, 40] | 0.0005 | rigid | 71.2268 | 62.0165 | 251692 | 6.50359e-05 | 3.25565e-05 | 7.33761e-05 |
| [40, 40] | 0.0005 | P1 | 4.30863 | 2.64814 | 8711.51 | 0.000224217 | 0.00317482 | 0.00143959 |

Historical media note: `hip40_knee40_matched_prefix.png` was externalized
during repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).

## Per-run diagnostics

### hip40_knee40_rigid_dt0250us

Termination: reference_completed; raw termination: reference_completed. Diagnostic guard uses the caller's existing break path; its generic raw physical-policy label must not be interpreted as an actual hard-force violation when the precise reason is deformation/energy.

Human ROM event: False; observed min/max deg: [4.9517487110988005, 9.908947779795536] / [40.02252695502779, 40.00881016625712]. BRAKE transitions: 0; BRAKE cycles: 0; final mode: TRACK; NO_SAFE_ACTION/MPC failure count: 0. MuJoCo warnings: 0.

Physical moment RMS/peak at R: {'peak': 17.690690552723446, 'rms': 12.657788301483322}; at H: {'peak': 17.690690552723446, 'rms': 12.657788301483322}. Rigid moments retain baseline weld-wrench semantics; progressive R/H moments are separately referenced.

| Motion channel | Acceleration RMS | Acceleration peak | Jerk RMS | Jerk peak |
| --- | --- | --- | --- | --- |
| human_cuff | 0.220101 | 0.745554 | 48.6609 | 1780.68 |
| human_joint | 0.555831 | 14.1861 | 178.711 | 10664.5 |
| robot_cuff | 0.219925 | 0.745094 | 49.1221 | 2028.57 |

Human-joint units rad/s² and rad/s³; cuff translation units m/s² and m/s³. Differentiated unsmoothed saved velocities; early transients are retained.

Rigid spring/damping energy: not applicable; no compliant storage law is assigned to the weld.

Transient force report: {"classification": "STRICT_PASS", "diagnostics_without_hard_thresholds": {"peak_physical_cuff_force_rate_n_s": 251692.00776539982, "peak_physical_cuff_moment_nm": 17.690690552723446, "peak_physical_cuff_moment_rate_nm_s": 53106.52544077124, "peak_surface_proxy_n": null}, "end_time_s": 14.1062499999898, "event_count": 0, "events": [], "maximum_causal_trailing_20ms_mean_n": 117.24281468741822, "maximum_causal_trailing_5ms_mean_n": 117.39252147614252, "maximum_contiguous_exceedance_duration_s": 0.0, "maximum_rolling_exceedance_duration_s": 0.0, "maximum_rolling_excess_impulse_ns": 0.0, "mechanical_classification": "STRICT_PASS", "numerical_confirmation": "runtime_observation", "numerical_confirmation_required": false, "peak_force_n": 117.44772249392015, "policy_id": "simulation_engineering_transient_v1", "runtime_stop_required": false, "sample_count": 56426, "simulation_engineering_only_not_clinical_safety": true, "start_time_s": 0.0, "violated_rule": null, "violated_rules": []}

Runtime: {"controller_cost": {"estimator_mean_ms": 1.0197560340673966, "estimator_p95_ms": 1.4077502710279077, "fast_path_timing_note": "instrumented in the synchronous deterministic simulator with measured estimator/trust compute subtracted; this is desktop engineering timing, not hardware hard realtime", "filter_or_brake_plus_reference_manager": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.6396670069079846, "mean_ms": 0.33448164481519504, "p95_ms": 0.4755819056299515, "sample_count": 2822}, "full_high_level_fast_path_excluding_slow_estimator_trust": {"deadline_miss_count": 4, "deadline_ms": 20.0, "max_ms": 50.14974999357946, "mean_ms": 12.577121681146252, "p95_ms": 12.885697498859372, "sample_count": 706}, "model_lock_assertion": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.24958400172181427, "mean_ms": 0.10529011020154384, "p95_ms": 0.12712290626950562, "sample_count": 2822}, "mpc": {"deadline_miss_count": 1, "deadline_ms": 20.0, "max_ms": 25.947749993065372, "mean_ms": 10.683615898366202, "p95_ms": 10.986197492456995, "sample_count": 706}, "mpc_mean_ms": 10.683615898366202, "mpc_p95_ms": 10.986197492456995, "reference_manager_fast_update": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.08512497879564762, "mean_ms": 0.008479684667940985, "p95_ms": 0.010749994544312358, "sample_count": 2822}, "reference_manager_slow_trust_update": {"deadline_miss_count": 2, "deadline_ms": 20.0, "max_ms": 61.388041998725384, "mean_ms": 0.5522406304343511, "p95_ms": 0.18611449195304886, "sample_count": 706}, "rollout_wall_time_s": 30.06069137499435, "safety_filter": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.5110000201966614, "mean_ms": 0.1633812031476157, "p95_ms": 0.17732053674990306, "sample_count": 2822}, "wall_time_per_simulated_second": 2.1310193265407946}, "total_run_wall_s": 31.02856779200374, "wall_per_simulated_second": 2.1996326303607394}

### hip40_knee40_P1_dt0250us

Termination: positive_interface_energy_residual; raw termination: physical_force_policy_hard_violation. Diagnostic guard uses the caller's existing break path; its generic raw physical-policy label must not be interpreted as an actual hard-force violation when the precise reason is deformation/energy.

Human ROM event: False; observed min/max deg: [4.9996913201286315, 9.999580655192126] / [5.0, 10.0]. BRAKE transitions: 0; BRAKE cycles: 0; final mode: TRACK; NO_SAFE_ACTION/MPC failure count: 0. MuJoCo warnings: 0.

Physical moment RMS/peak at R: {'peak': 0.8740766068288552, 'rms': 0.5354425758197728}; at H: {'peak': 0.8740766281454906, 'rms': 0.5354425845213684}. Rigid moments retain baseline weld-wrench semantics; progressive R/H moments are separately referenced.

| Motion channel | Acceleration RMS | Acceleration peak | Jerk RMS | Jerk peak |
| --- | --- | --- | --- | --- |
| human_cuff | 8.86022 | 9.03508 | 1419.01 | 1419.01 |
| human_joint | 48.3194 | 48.7741 | 3760.62 | 3760.62 |
| robot_cuff | 9.14183 | 9.47686 | 2921.76 | 2921.76 |

Human-joint units rad/s² and rad/s³; cuff translation units m/s² and m/s³. Differentiated unsmoothed saved velocities; early transients are retained.

Energy/damping: {"damping_loss_j": 1.707458983728035e-05, "final_scale_j": 1.7849838547069284e-05, "max_abs_residual_j": 9.530691090569806e-08, "max_abs_residual_ratio": 0.0053393710343305175, "max_positive_residual_j": 9.530691090569806e-08, "max_positive_residual_ratio": 0.0053393710343305175, "max_power_identity_w": 1.3877787807814457e-17, "minimum_damping_power_w": 0.0, "net_port_work_j": -1.7849838547069284e-05, "numerical_qualification": "NOT_ESTABLISHED; exploratory override does not erase prior failed bench", "stored_peak_j": 8.705556206946333e-07}

Transient force report: {"classification": "STRICT_PASS", "diagnostics_without_hard_thresholds": {"peak_physical_cuff_force_rate_n_s": 8711.5096970233, "peak_physical_cuff_moment_nm": 0.8740766068288552, "peak_physical_cuff_moment_rate_nm_s": 1749.9373552133002, "peak_surface_proxy_n": null}, "end_time_s": 0.0005, "event_count": 0, "events": [], "maximum_causal_trailing_20ms_mean_n": null, "maximum_causal_trailing_5ms_mean_n": null, "maximum_contiguous_exceedance_duration_s": 0.0, "maximum_rolling_exceedance_duration_s": 0.0, "maximum_rolling_excess_impulse_ns": 0.0, "mechanical_classification": "STRICT_PASS", "numerical_confirmation": "runtime_observation", "numerical_confirmation_required": false, "peak_force_n": 4.308631692740495, "policy_id": "simulation_engineering_transient_v1", "runtime_stop_required": false, "sample_count": 3, "simulation_engineering_only_not_clinical_safety": true, "start_time_s": 0.0, "violated_rule": null, "violated_rules": []}

Runtime: {"controller_cost": {"estimator_mean_ms": 0.09250000584870577, "estimator_p95_ms": 0.09250000584870577, "fast_path_timing_note": "instrumented in the synchronous deterministic simulator with measured estimator/trust compute subtracted; this is desktop engineering timing, not hardware hard realtime", "filter_or_brake_plus_reference_manager": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.03216598997823894, "mean_ms": 0.03216598997823894, "p95_ms": 0.03216598997823894, "sample_count": 1}, "full_high_level_fast_path_excluding_slow_estimator_trust": {"deadline_miss_count": 0, "deadline_ms": 20.0, "max_ms": 11.391540989279747, "mean_ms": 11.391540989279747, "p95_ms": 11.391540989279747, "sample_count": 1}, "model_lock_assertion": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.12120799510739744, "mean_ms": 0.12120799510739744, "p95_ms": 0.12120799510739744, "sample_count": 1}, "mpc": {"deadline_miss_count": 0, "deadline_ms": 20.0, "max_ms": 9.986499993829057, "mean_ms": 9.986499993829057, "p95_ms": 9.986499993829057, "sample_count": 1}, "mpc_mean_ms": 9.986499993829057, "mpc_p95_ms": 9.986499993829057, "reference_manager_fast_update": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.018207996618002653, "mean_ms": 0.018207996618002653, "p95_ms": 0.018207996618002653, "sample_count": 1}, "reference_manager_slow_trust_update": {"deadline_miss_count": 0, "deadline_ms": 20.0, "max_ms": 0.1722919987514615, "mean_ms": 0.1722919987514615, "p95_ms": 0.1722919987514615, "sample_count": 1}, "rollout_wall_time_s": 0.013007625006139278, "safety_filter": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.1595419889781624, "mean_ms": 0.1595419889781624, "p95_ms": 0.1595419889781624, "sample_count": 1}, "wall_time_per_simulated_second": 26.015250012278557}, "total_run_wall_s": 0.32480837500770576, "wall_per_simulated_second": 649.6167500154115}

## Interpretation

The observed stop occurred at 0.0005 s, after only two physics steps and before a second 5 ms control cycle. The positive residual is 9.53069109e-8 J, versus an 8.92491927e-8 J budget (0.533937% versus 0.5%). This is a frozen diagnostic-budget exceedance at a very small energy scale, not demonstrated macroscopic instability or validated nonpassivity. The instantaneous constitutive power identity still holds. No ROM event, warning, or engineering-motion violation occurred before this stop. The derivative/jerk values use only three states and one jerk sample for P1.

The secondary machine reason compliant_40_40_loses_rigid_completion follows from this diagnostic truncation. It is not independent evidence that P1 would fail to finish the trajectory absent that guard. No guard threshold was relaxed and no run was resumed.

Consistent positive trend across all three points: NOT_ESTABLISHED_INCOMPLETE_THREE_POINT_COVERAGE. Rescued tested points: [].

If the 40/40 guard stops the campaign, 40/80 improvement and 90/120 failure-mode/completion trend remain untested. A prefix force decrease alone cannot establish a useful interaction improvement when tracking, deformation or energy invalidates the comparison.

This run supports further investigation of the discrete-energy diagnostic at startup and interface integration, not a demonstrated benefit from compliant High-ROM mechanics. The 0.5 ms prefix cannot establish whether additional compliant modeling will improve task behavior. It does not justify promoting the candidate or claiming capability gains. No automatic tuning, threshold change or additional run is authorized.

## Reproducibility and scope

Ten preflight tests passed before freeze; these checked reset/model equality, original runtime bytecode bindings, synthetic stop rules and actual-dt derivatives without time integration. Postprocessing verified 255 NPZ arrays, exact paired initial states, paired config/model fingerprints and 290 frozen file hashes. git diff --check passed; tracked diff is empty.

Added this task: PROGRESSIVE_EXPLORATORY_AB_SPEC.md/.json; run_progressive_exploratory_ab.py; test_progressive_exploratory_ab.py; summarize_progressive_exploratory_ab.py; this new result directory. Existing files, failed bench evidence and old soft-interface negative evidence are unchanged. Everything remains uncommitted.

Only the paired interface and the explicitly requested common 0.25 ms physics experiment differ from historical rigid 1 ms evidence. No controller gains/costs/constraints, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, seed, adapter, trajectory law, integrator or solver were modified. No extra run, replay, capability scan or retuning.

Commands:

```text

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_exploratory_ab.py

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_exploratory_ab.py --freeze

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_exploratory_ab.py --run-next  # 2 separate process invocations; see started.json per run

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/summarize_progressive_exploratory_ab.py

git diff --check

git status --short

```

Formal command reserved for user: none; these outputs are exploratory, and the stop rule admits no further execution under this campaign.
