# Rigid vs P1 90/120 exploratory matched A/B

> [!IMPORTANT]
> **PRE-CORRECTION / RETIRED DIAGNOSTIC EVIDENCE**
>
> This report predates the corrected low-latency robot velocity-feedback
> measurement path and is retained only as diagnostic provenance. Current
> authoritative conclusions are in [CURRENT_STATE](../../../docs/research/CURRENT_STATE.md)
> and the [corrected High-ROM evidence](../../summaries/phase3a_corrected_high_rom/README.md).
> Commands and paths below are frozen historical provenance; they are retired,
> non-current, and must not be treated as executable reproduction instructions.



**Both arms executed 100% of the registered outbound and return reference and retained formal SAFE_INCOMPLETE. Neither arm entered BRAKE or required Safety Filter intervention. Rigid returned within the strict tolerance but missed the target-hold endpoint criterion; P1 missed both endpoint and return precision.**



Exploratory diagnostic evidence only. The prior strict compliant numerical-qualification FAIL remains unchanged. No clinical-safety, qualified-compliance or formal capability-envelope claim.



## Frozen contract

Checkpoint commit `5e3800ae6570c45b125e74ea678cdf2b72f48d69`; Spec SHA256 `46bf69df321b5ab3998ab94c155ce8be5e6b53cef54f664f8f89ba0797539df1`; MD SHA256 `5b557eec0f06a58865f14c38a82481b778eb3aa9edaec99235486083b6296e45`. Exactly rigid 90/120 then P1 90/120, fresh processes. No 120/120.

Both used dt=0.25 ms, 20 physics substeps per unchanged 5 ms control tick, de23ea3 Fixed MPC, suspended_high_rom, nominal Human/model lock, 140 mm adapter, seed 44104, registered quintic timing, allocator, measurement boundary, Reference Manager, Safety Filter, BRAKE and force contracts. The only experimental variable was interface.

P1 unchanged: K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad.



## Matched metrics

| Metric | Rigid | P1 |
| --- | --- | --- |
| Formal classification | SAFE_INCOMPLETE | SAFE_INCOMPLETE |
| Termination | reference_completed | reference_completed |
| Practical completion | full reference executed; precision criterion not met | full reference executed; precision criterion not met |
| Outbound / return reference % | 100.0/100.0 | 100.0/100.0 |
| Final phase / physical time s | 29.257750000048688/29.257750000048688 | 29.257750000048688/29.257750000048688 |
| Tracking RMSE / max norm deg | 1.9287312178848812/5.14806657958787 | 1.7414572193118323/4.598244471789953 |
| Tracking max q1/q2 deg | [2.87375, 4.61092] | [2.36214, 4.15901] |
| Endpoint / return error deg | 4.183907755253273/0.051916540413415646 | 3.8415923600307877/0.8669470395400918 |
| Command force RMS / peak N | 114.42309065782143/199.78836731220062 | 107.42059515476507/139.44196590431284 |
| Physical force RMS / peak N | 110.05324927291103/158.727018116726 | 104.98939470359082/130.22758300268117 |
| Force slew RMS / peak N/s | 2221.3164664847163/251692.00776539982 | 263.27043449794604/8711.5096970233 |
| Moment RMS / peak Nm | 33.81017427236065/65.1566784261068 | 29.797595568535954/57.72530862057714 |
| BRAKE entries / duration s | 0/0.0 | 0/0.0 |
| BRAKE_INFEASIBLE / NO_SAFE_ACTION | 0/0 | 0/0 |
| Filter intervention count / peak | 0/0.0 | 0/0.0 |
| Minimum feasible candidates | 1 | 1 |
| Human cuff acceleration RMS / peak | 2.0532161313455486/13.112926807256999 | 0.37629632295992355/9.03507534400489 |
| Peak acceleration time s | 22.0804 | 0.000125 |
| Human cuff jerk RMS / peak | 375.4214789209172/26419.71581251809 | 47.22357658707905/1934.7379150504494 |
| Proxy RMSE q1/q2 deg | [0.169729, 0.201602] | [0.345114, 0.569559] |
| Proxy peak q1/q2 deg | [0.752224, 0.840283] | [0.567423, 1.04495] |
| Force >200 duration / excess impulse | 0.0/0.0 | 0.0/0.0 |
| Force contract | STRICT_PASS | STRICT_PASS |
| Wall runtime s | 66.0184 | 115.781 |



Both force reports are STRICT_PASS with zero >200 N duration and zero excess impulse. Both logged 5852 SAFE_UNCHANGED filter cycles, zero intervention, zero BRAKE, zero BRAKE_INFEASIBLE and zero NO_SAFE_ACTION. No Human ROM, robot structural, MuJoCo-warning or nonfinite-state event occurred.



## Actual trajectory completion

Both arms reached 100% reference timing on outbound and return; neither terminated early. Formal labels retain the unchanged 0.06896926724078867 deg criterion. `reference_completed` describes timing coverage and is not itself physical endpoint success.



| Event | Rigid q_true deg | Rigid q_proxy deg | P1 q_true deg | P1 q_proxy deg |
| --- | --- | --- | --- | --- |
| target_arrival | [92.7718, 115.682] | [92.8171, 115.618] | [92.2485, 116.026] | [92.5688, 115.702] |
| return_end | [4.97888, 9.98904] | [4.99439, 10.0002] | [4.56756, 9.18924] | [5.01464, 10.0407] |
| reference_end | [4.96954, 9.94808] | [4.99536, 9.99403] | [4.55287, 9.13305] | [5.0141, 10.0284] |



Rigid best target-hold error is 4.183908 deg, so it does not physically meet the registered target criterion. It returns to within 0.051917 deg, satisfying that precision component. Full reference executed; target precision criterion not met.

P1 best target-hold error is 3.841592 deg and return error is 0.866947 deg. It executes the whole outward/return motion and returns near the initial pose, but does not meet either registered precision criterion. Full reference executed; precision criterion not met.



## P1 deformation and energy

| Metric | P1 |
| --- | --- |
| Translation peak / RMS mm | 1.0893543780383104 / 0.9694797074368352 |
| Rotation peak / RMS deg | 1.0509896812342214 / 0.6146742876818998 |
| Relative velocity peak m/s | 0.066659 |
| Relative angular velocity peak rad/s | 0.564738 |
| Target / return translation mm | 1.0729344940850443 / 0.8768801939870507 |
| Spring energy peak J | 0.467862 |
| Damping loss J | 0.186269 |
| Max absolute / running-normalized residual | 0.00295574110588831 J / 1.0538134835257698% |
| Final residual / trailing slope | -0.002891455024975731 J / 7.630934556914172e-05 J/s |
| Sustained-growth triggers / windows | 0 / 585 |

P1 translation remains small. Rotation peaks at 1.050990 deg, 0.050990 deg above the 1 deg descriptive engineering target; it is far below the 10 deg gross hard-stop and does not diverge. This target exceedance is retained as an unfavorable result. No persistent energy/amplitude-growth watchdog fires. The residual is diagnostic and cannot overturn the prior numerical-qualification FAIL.

The small rigid-column relative-pose trace in the plot is weld/geometry consistency, not compliant-interface deformation.



## Force, dynamics and proxy trade-off

Relative to rigid at 90/120, P1 reduces command peak 30.21%, physical-force peak 17.95%, physical-force RMS 4.60%, moment peak 11.41%, force-slew peak 96.54%, cuff-acceleration peak 31.10% and acceleration RMS 81.67%.

Tracking RMSE changes from 1.928731 to 1.741457 deg, while return precision worsens from 0.051917 to 0.866947 deg. P1 proxy RMSE q1/q2 is [0.3451138955873704, 0.569559083462544]; return-end proxy error is [0.4470830166880564, 0.8514627764365343]. Simulator truth appears only in this offline analysis and was never fed to control.



## Temporal alignment

Rigid global Human-cuff acceleration peak is 13.112927 m/s^2 at 22.080375 s. Its largest post-start peak is 13.112927 m/s^2 at 22.080375 s; neither is associated with BRAKE or filter intervention because neither occurs.

P1 global peak is the recurring startup transient, 9.035075 m/s^2 at 0.000125 s. Its largest t>=0.1 s peak is 1.996869 m/s^2 at 20.094625 s. `detailed_metrics.json` records nearest force, command, deformation-reversal, proxy and reference-transition times. These are temporal associations, not causal proof.



Historical media note: `aligned_90_120_diagnostics.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



Historical media note: `target_arrival_alignment.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



## Comparison with 40/40 and 40/80

| Point | Rigid formal | P1 formal | BRAKE R/P1 | Tracking RMSE R/P1 deg | Physical peak R/P1 N | Return error R/P1 deg |
| --- | --- | --- | --- | --- | --- | --- |
| 40/40 | COMPLETE | SAFE_INCOMPLETE | 0 / 0 | 0.15762147448942807 / 0.5564197370684401 | 117.44772249392015 / 118.6823131214332 | 0.012787567011908862 / 0.8276943837567448 |
| 40/80 | SAFE_INCOMPLETE | SAFE_INCOMPLETE | 1 / 0 | 24.66185503228125 / 0.4474783158106737 | 197.49715692658623 / 123.20384078663761 | 64.24116946897739 / 0.7970020802046687 |
| 90/120 | SAFE_INCOMPLETE | SAFE_INCOMPLETE | 0 / 0 | 1.9287312178848812 / 1.7414572193118323 | 158.727018116726 / 130.22758300268117 | 0.051916540413415646 / 0.8669470395400918 |



The 40/80 feasibility/BRAKE improvement does not extend as a direct rescue at 90/120 because rigid itself no longer hits the BRAKE boundary. The current frozen controller is non-monotone across these trajectory points: rigid BRAKEs and fails the physical return at 40/80, yet remains TRACK and returns within tolerance at 90/120. P1 remains TRACK at both points. At 90/120 P1 still reduces force severity and tracking RMSE modestly, but worsens return precision and slightly exceeds the 1 deg interface-rotation target.



## Evidence interpretation

### DIRECTLY OBSERVED

- Both 90/120 arms execute the entire reference without BRAKE, Safety Filter intervention, NO_SAFE_ACTION, warning, ROM or force-contract event.

- Neither arm meets the target-hold endpoint tolerance. Rigid meets return precision; P1 does not.

- P1 lowers force peak/RMS, force slew, moment peak and cuff acceleration in this pair, with bounded millimeter translation and 1.051 deg peak rotation.



### SUPPORTED BY CURRENT EVIDENCE

P1 provides force/transient smoothing at 90/120, but the specific 40/80 BRAKE-boundary rescue cannot be replicated because there is no rigid BRAKE to rescue. The result supports a trajectory-dependent, non-monotone controller-boundary mechanism rather than a simple amplitude-ordered capability expansion.



### UNRESOLVED

Why rigid 40/80 enters BRAKE while rigid 90/120 remains TRACK is unresolved. Candidate explanations involving trajectory timing, reference geometry, estimator/proxy state and safety-filter feasibility need separate causal tests. One run per arm does not establish repeatability.



### NOT SUPPORTED

No claim of numerical qualification, clinical safety, monotone High-ROM capability expansion, or universal force reduction. P1 does not turn 90/120 into formal COMPLETE and exceeds the descriptive 1 deg rotation target by 0.051 deg.



## Further High-ROM testing

Direct progression to 120/120 is not justified from this pair alone. The non-monotone rigid behavior and P1 rotation-target exceedance make a harder-amplitude rollout difficult to interpret, while the prior strict numerical-qualification FAIL remains. A separately preregistered repeat/mechanism study at the existing 40/80 and 90/120 points is scientifically justified before any further amplitude escalation. No such run is authorized or executed here.



## Reproducibility

Run directories: `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/progressive_90_120_ab_20260907_v1/hip90_knee120_rigid_dt0250us` and `/Users/hankli/Desktop/coding/adaptive-traction-mpc-interface-phase3a/stages/stage4_adaptive_control/results/engineering_validation/progressive_90_120_ab_20260907_v1/hip90_knee120_P1_dt0250us`. Postprocessing verified 273 arrays, 375 frozen hashes, exact paired initial state/config and matching model fingerprints. Both runs used fresh PIDs 5788 and 5825.

New files remain uncommitted after checkpoint. Scientific variable: rigid versus registered P1 interface. Controller, timestep, substeps, solver, gains, estimator, Human/robot, geometry, adapter, reference timing, seed, force limits/contracts, Reference Manager, Safety Filter and BRAKE remain unchanged. No 120/120 or extra rollout.



Commands:

```text

PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_90_120_ab.py

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_90_120_ab.py --freeze

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_90_120_ab.py --run-next  # twice, exactly rigid then P1

PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/summarize_progressive_90_120_ab.py

git diff --check

git status --short

```



No formal experiment command is admitted.
