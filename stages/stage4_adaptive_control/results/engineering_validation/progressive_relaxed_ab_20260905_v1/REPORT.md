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



**Executed 2/6 scheduled runs. Campaign stopped: P1_40_40_not_COMPLETE.**

Exploratory diagnostic evidence only. The previous failed bench qualification, including the 0.25 ms energy residual, remains unchanged. No clinical safety, validated compliance physics or authoritative capability claim is supported.

## Frozen setup

Spec JSON SHA256: `09c919ca8a274cecb2abdd6e3aa667a71b0e1b47bebe62d0a68754c94efbaedb`

Spec MD SHA256: `a404f645ad4befb6b31e5e47ce5a2e4187741c95ddc8da8506c666614a76441c`

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
| 40/40 | P1 | SAFE_INCOMPLETE | reference_completed | 14.1062 | 0.55642 | 0.370376 | 0.827694 | STRICT_PASS |
| 40/80 | rigid | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 40/80 | P1 | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 90/120 | rigid | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |
| 90/120 | P1 | NOT_RUN | CAMPAIGN_STOP | — | — | — | — | — |

Return/final offset is error from initial [5,10] deg at the last sample. When return_reached=false, this is NOT a completed return error. Missing endpoint means the target hold was not reached. All incomplete-run RMS/peak values cover only that executed prefix.

| Trajectory | Arm | Command RMS/peak N | Physical RMS/peak N | Force-rate peak N/s | Moment peak Nm | Translation mm | Rotation deg | Wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40/40 | rigid | 99.1582 / 121.049 | 98.9913 / 117.448 | 251692 | 17.6907 | 0.0475381 | 0.0683494 | 31.4556 |
| 40/40 | P1 | 99.4216 / 121.679 | 99.2824 / 118.682 | 8711.51 | 19.119 | 1.03979 | 0.509747 | 55.4343 |
| 40/80 | rigid | — / — | — / — | — | — | — | — | — |
| 40/80 | P1 | — / — | — / — | — | — | — | — | — |
| 90/120 | rigid | — / — | — / — | — | — | — | — | — |
| 90/120 | P1 | — / — | — / — | — | — | — | — | — |

RMS force values are time-weighted trapezoidal norms. Command RMS uses issued-command timestamps; physical RMS uses physics timestamps. Force/moment rates are world-vector finite differences using actual dt. The baseline raw summary assumes 1 ms for some derivatives; those uncorrected fields are preserved but not used here.

## Matched-time force/tracking/deformation trade-off

The 40/40 pair has identical full physical-time coverage (14.10625 s); both reached the end of the reference. P1 remains SAFE_INCOMPLETE because endpoint/return tracking tolerance was not met. The common-interval comparison therefore uses the entire executed reference, not the previous 0.5 ms truncated evidence. No time shifting or smoothing is applied.

| Trajectory | Common end s | Arm | Force peak N | Force RMS N | Rate peak N/s | Tracking RMSE deg | Translation mm | Rotation deg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [40, 40] | 14.1062 | rigid | 117.448 | 98.9913 | 251692 | 0.157621 | 0.0475381 | 0.0683494 |
| [40, 40] | 14.1062 | P1 | 118.682 | 99.2824 | 8711.51 | 0.55642 | 1.03979 | 0.509747 |

Historical media note: `hip40_knee40_matched_prefix.png` was externalized
during repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).

## Energy residual policy and trend

Energy residual is diagnostic, not an instantaneous hard stop. This campaign uses frozen four-window (50 ms each) persistence and material-amplitude guards. The prior strict numerical qualification FAIL and old 0.5 ms exploratory stop remain unchanged. Engineering bounds 3 mm/1 deg are harder-pair admission criteria; gross emergency bounds are 10 mm/10 deg. See frozen Spec for exact growth thresholds.

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

Runtime: {"controller_cost": {"estimator_mean_ms": 0.9411101415984217, "estimator_p95_ms": 1.2720207450911403, "fast_path_timing_note": "instrumented in the synchronous deterministic simulator with measured estimator/trust compute subtracted; this is desktop engineering timing, not hardware hard realtime", "filter_or_brake_plus_reference_manager": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.7522909727413207, "mean_ms": 0.328784050826844, "p95_ms": 0.44932674209121615, "sample_count": 2822}, "full_high_level_fast_path_excluding_slow_estimator_trust": {"deadline_miss_count": 1, "deadline_ms": 20.0, "max_ms": 24.622124998131767, "mean_ms": 12.43676719126798, "p95_ms": 12.718395257252268, "sample_count": 706}, "model_lock_assertion": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.37195798358879983, "mean_ms": 0.09964391194829489, "p95_ms": 0.10957469348795709, "sample_count": 2822}, "mpc": {"deadline_miss_count": 1, "deadline_ms": 20.0, "max_ms": 22.246374981477857, "mean_ms": 10.655773367652625, "p95_ms": 10.887739495956339, "sample_count": 706}, "mpc_mean_ms": 10.655773367652625, "mpc_p95_ms": 10.887739495956339, "reference_manager_fast_update": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.027875008527189493, "mean_ms": 0.007838003011816396, "p95_ms": 0.008750008419156075, "sample_count": 2822}, "reference_manager_slow_trust_update": {"deadline_miss_count": 1, "deadline_ms": 20.0, "max_ms": 25.243291980586946, "mean_ms": 0.4788034664557339, "p95_ms": 0.1766462519299239, "sample_count": 706}, "rollout_wall_time_s": 30.51832012500381, "safety_filter": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.24879199918359518, "mean_ms": 0.16146817236833808, "p95_ms": 0.17053988703992218, "sample_count": 2822}, "wall_time_per_simulated_second": 2.163460886133868}, "total_run_wall_s": 31.455587915988872, "wall_per_simulated_second": 2.229904327231661}

Energy trend: {"complete_50ms_windows": 282, "damping_loss_j": 0.11656218238205944, "duration_s": 14.1062499999898, "final_normalized_residual": -0.008175959474250328, "final_signed_residual_j": -0.0017492458118600895, "initial_residual_j": 0.0, "maximum_abs_running_normalized_residual": 0.010523375426236905, "maximum_absolute_residual_j": 0.0021405170403464707, "maximum_positive_residual_j": 0.00012040369363197634, "minimum_damping_power_w": 0.0, "spring_energy_peak_j": 0.11624062208247858, "tail_200ms_slope_j_s": -9.889248404348089e-05, "watchdog_triggers": []}

Historical media note: `hip40_knee40_P1_dt0250us_energy.png` was externalized
during repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).

### hip40_knee40_P1_dt0250us

Termination: reference_completed; raw termination: reference_completed. Diagnostic guard uses the caller's existing break path; its generic raw physical-policy label must not be interpreted as an actual hard-force violation when the precise reason is deformation/energy.

Human ROM event: False; observed min/max deg: [4.528626811087134, 9.10562554376516] / [39.80837188497754, 39.62962405030493]. BRAKE transitions: 0; BRAKE cycles: 0; final mode: TRACK; NO_SAFE_ACTION/MPC failure count: 0. MuJoCo warnings: 0.

Physical moment RMS/peak at R: {'peak': 19.119027085120916, 'rms': 12.630555943120397}; at H: {'peak': 19.122901836018855, 'rms': 12.630537789860346}. Rigid moments retain baseline weld-wrench semantics; progressive R/H moments are separately referenced.

| Motion channel | Acceleration RMS | Acceleration peak | Jerk RMS | Jerk peak |
| --- | --- | --- | --- | --- |
| human_cuff | 0.279831 | 9.03508 | 44.2404 | 1934.74 |
| human_joint | 1.32453 | 48.7741 | 160.996 | 4708.96 |
| robot_cuff | 0.278772 | 9.47686 | 238.102 | 7563.18 |

Human-joint units rad/s² and rad/s³; cuff translation units m/s² and m/s³. Differentiated unsmoothed saved velocities; early transients are retained.

Energy/damping: {"damping_loss_j": 0.11656218238205944, "final_scale_j": 0.21394991222366372, "max_abs_residual_j": 0.0021405170403464707, "max_abs_residual_ratio": 0.010004757740254501, "max_positive_residual_j": 0.00012040369363197634, "max_positive_residual_ratio": 0.0005627658005585253, "max_power_identity_w": 4.405276057134477e-15, "minimum_damping_power_w": 0.0, "net_port_work_j": -0.21012479901511652, "numerical_qualification": "NOT_ESTABLISHED; exploratory override does not erase prior failed bench", "stored_peak_j": 0.11624062208247858}

Transient force report: {"classification": "STRICT_PASS", "diagnostics_without_hard_thresholds": {"peak_physical_cuff_force_rate_n_s": 8711.5096970233, "peak_physical_cuff_moment_nm": 19.119027085120916, "peak_physical_cuff_moment_rate_nm_s": 1749.9373552133002, "peak_surface_proxy_n": null}, "end_time_s": 14.1062499999898, "event_count": 0, "events": [], "maximum_causal_trailing_20ms_mean_n": 118.45105125310909, "maximum_causal_trailing_5ms_mean_n": 118.62068965698427, "maximum_contiguous_exceedance_duration_s": 0.0, "maximum_rolling_exceedance_duration_s": 0.0, "maximum_rolling_excess_impulse_ns": 0.0, "mechanical_classification": "STRICT_PASS", "numerical_confirmation": "runtime_observation", "numerical_confirmation_required": false, "peak_force_n": 118.6823131214332, "policy_id": "simulation_engineering_transient_v1", "runtime_stop_required": false, "sample_count": 56426, "simulation_engineering_only_not_clinical_safety": true, "start_time_s": 0.0, "violated_rule": null, "violated_rules": []}

Runtime: {"controller_cost": {"estimator_mean_ms": 1.07757469145159, "estimator_p95_ms": 1.430790995073039, "fast_path_timing_note": "instrumented in the synchronous deterministic simulator with measured estimator/trust compute subtracted; this is desktop engineering timing, not hardware hard realtime", "filter_or_brake_plus_reference_manager": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 1.1950420157518238, "mean_ms": 0.3413952819651229, "p95_ms": 0.48245383077301085, "sample_count": 2822}, "full_high_level_fast_path_excluding_slow_estimator_trust": {"deadline_miss_count": 0, "deadline_ms": 20.0, "max_ms": 16.398707986809313, "mean_ms": 12.843579048931957, "p95_ms": 13.123979515512474, "sample_count": 706}, "model_lock_assertion": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.3013339883182198, "mean_ms": 0.10699294840413377, "p95_ms": 0.13216283550718796, "sample_count": 2822}, "mpc": {"deadline_miss_count": 0, "deadline_ms": 20.0, "max_ms": 13.85991700226441, "mean_ms": 10.684520367050817, "p95_ms": 10.89453099120874, "sample_count": 706}, "mpc_mean_ms": 10.684520367050817, "mpc_p95_ms": 10.89453099120874, "reference_manager_fast_update": {"deadline_miss_count": 0, "deadline_ms": 1.0, "max_ms": 0.036667013773694634, "mean_ms": 0.008410391139366858, "p95_ms": 0.01103892573155462, "sample_count": 2822}, "reference_manager_slow_trust_update": {"deadline_miss_count": 1, "deadline_ms": 20.0, "max_ms": 27.091249998193234, "mean_ms": 0.4890682198016221, "p95_ms": 0.18559401360107586, "sample_count": 706}, "rollout_wall_time_s": 54.33620887500001, "safety_filter": {"deadline_miss_count": 0, "deadline_ms": 5.0, "max_ms": 0.8015409985091537, "mean_ms": 0.1677276832106854, "p95_ms": 0.18249584391014648, "sample_count": 2822}, "wall_time_per_simulated_second": 3.8519244218016344}, "total_run_wall_s": 55.434338083985494, "wall_per_simulated_second": 3.9297714193372144}

## Interpretation

The new relaxed-energy policy allowed P1 to execute the full reference. The campaign closes at the P1 40/40 COMPLETE gate, not an energy/pathology guard. Endpoint error 0.37037595 deg and return error 0.82769438 deg exceed the unchanged 0.06896926724 deg tolerance.

Observed full-40/40 trade-off: physical force peak increases from 117.44772 to 118.68231 N and RMS from 98.99135 to 99.28240 N; tracking RMSE increases from 0.157621 to 0.556420 deg. Global P1 translation/rotation remain within 1.039794 mm / 0.509747 deg. Peak moment increases from 17.69069 to 19.11903 Nm. Both force contracts classify STRICT_PASS; no ROM event, warning, BRAKE or NO_SAFE_ACTION occurs.

The maximum full-run force derivative occurs at startup (t=0.00025 s) in both arms. It decreases from 251692 to 8711.51 N/s with P1. Excluding only the registered first 1 s initial hold, peak derivative decreases from 8712.73 to 707.129 N/s: the smoothing effect is also present during later reference execution. This derivative benefit does not reduce the overall peak/RMS force or preserve the original completion accuracy.

| Run | Overall rate peak time s | After initial hold rate peak N/s | After initial hold rate RMS N/s |
| --- | --- | --- | --- |
| hip40_knee40_rigid_dt0250us | 0.00025 | 8712.73 | 516.197 |
| hip40_knee40_P1_dt0250us | 0.00025 | 707.129 | 134.799 |

P1 energy remains finite. Maximum absolute residual 0.002140517 J; final signed residual -0.001749246 J; maximum absolute running-normalized residual 1.05234%, final ratio -0.817596%. Final-200ms slope -9.88925e-5 J/s. Peak stored energy 0.1162406 J; cumulative damping loss 0.1165622 J. All 282 completed 50 ms windows show no registered persistent-growth trigger. Residuals are not zero and prior strict numerical qualification remains failed.

Consistent positive trend across all three points: NOT_ESTABLISHED_INCOMPLETE_THREE_POINT_COVERAGE. Rescued tested points: [].

If the 40/40 guard stops the campaign, 40/80 improvement and 90/120 failure-mode/completion trend remain untested. A prefix force decrease alone cannot establish a useful interaction improvement when tracking, deformation or energy invalidates the comparison.

Interpret stopped or incomplete comparisons only over the recorded coverage. A reduced force peak without preserved task completion is a trade-off, not a rescued task. The force-rate benefit is offset by higher peak/RMS force and worse tracking at 40/40. No consistent three-point trend can be established when harder points are unexecuted. Further compliant-interface research may investigate the observed trade-off, but this evidence does not qualify the physics or justify tuning in this campaign.

## Reproducibility and scope

Twelve preflight tests passed before freeze; these checked reset/model equality, original runtime bytecode bindings, synthetic stop rules and actual-dt derivatives without time integration. Postprocessing verified 261 NPZ arrays, exact paired initial states, paired config/model fingerprints and 330 frozen file hashes. git diff --check passed; tracked diff is empty.

Added this task: PROGRESSIVE_RELAXED_AB_SPEC.md/.json; run_progressive_relaxed_ab.py; test_progressive_relaxed_ab.py; summarize_progressive_relaxed_ab.py; this new result directory. Existing files, failed bench evidence and old soft-interface negative evidence are unchanged. Everything remains uncommitted.

Only the paired interface and the explicitly requested common 0.25 ms physics experiment differ from historical rigid 1 ms evidence. No controller gains/costs/constraints, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, seed, adapter, trajectory law, integrator or solver were modified. No extra run, replay, capability scan or retuning.

Commands:

```text

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_relaxed_ab.py

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_relaxed_ab.py --freeze

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_relaxed_ab.py --run-next  # 2 separate process invocations; see started.json per run

PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/summarize_progressive_relaxed_ab.py

git diff --check

git status --short

```

Formal command reserved for user: none; these outputs are exploratory, and the stop rule admits no further execution under this campaign.
