# Progressive global cuff interface engineering bench

> [!IMPORTANT]
> **PRE-CORRECTION / RETIRED DIAGNOSTIC EVIDENCE**
>
> This report predates the corrected low-latency robot velocity-feedback
> measurement path and is retained only as diagnostic provenance. Current
> authoritative conclusions are in [CURRENT_STATE](../../../docs/research/CURRENT_STATE.md)
> and the [corrected High-ROM evidence](../../summaries/phase3a_corrected_high_rom/README.md).
> Commands and paths below are frozen historical provenance; they are retired,
> non-current, and must not be treated as executable reproduction instructions.



**Overall numerical qualification: FAIL. Neither candidate selected. The 40/40 gate is closed; no new closed-loop trajectory was executed.**

User-authorized engineering evidence only, not formal/authoritative evidence and not a clinical or measured-tissue model. All failed results are retained. No tuning followed the results.



## Frozen contract

JSON SHA256: `aedebae72fa4c2137a5e73e46f3d03616d3dd821cb9057e80ac242f27fe9643e`

MD SHA256: `daf96956680050686919ec2b56ce3a114824156a8fb2b8fefefe52dc7fa7c779`

Branch: `codex/interface-phase3a-de23ea3`; HEAD: `99169491ea1336d6af74e3b63318afba18c1e881`; baseline: `de23ea3cdf9f0fb078496ba5ba4abb6a205ad955`.

Two candidates; three release cases; dt = 1, 0.5, 0.25 ms; two repeats each: exactly 36 standalone ringdowns of 0.2 s. No MPC/Reference Manager/High-ROM trajectory is called by the bench. The 0.25 ms data are a finite reference, not independently qualified exact mechanics evidence.



## Model and candidates

In cuff H coordinates: x = R_H^T(p_R-p_H), u = R_H^T(v_R-v_H-omega_H cross (p_R-p_H)); theta = Log(R_H^T R_R), w = R_H^T(omega_R-omega_H).

F_R = -R_H[(K1 + K3 ||x||^2)x + D u]; M_R = -R_H[(Kr1 + Kr3 ||theta||^2)theta + Dr w].

F_H = -F_R; M_H = -M_R + (p_R-p_H) cross F_H. Moments are about their respective attachment origins; the transport moment is required for angular action-reaction and port power.

U = K1 ||x||^2/2 + K3 ||x||^4/4 + Kr1 ||theta||^2/2 + Kr3 ||theta||^4/4; dissipation = D ||u||^2 + Dr ||w||^2 >= 0. Fixed zero rest displacement/rotation; explicit opt-in only.

Positive tangent eigenvalues K1+K3 r^2 and K1+3 K3 r^2 guarantee smooth monotone radial stiffening. The radial law preserves force direction; its mixed-axis magnitude dependence is intentional. Static axis/diagonal checks do not certify full-plant coupling.

| Candidate | K1 N/m | K3 N/m^3 | D Ns/m | Kr1 Nm/rad | Kr3 Nm/rad^3 | Dr Nms/rad |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | 60000 | 5e+10 | 490.684226856 | 1800 | 4e+06 | 12.447966321 |
| P2 | 90000 | 6e+10 | 497.922449714 | 2400 | 6e+06 | 13.558199250 |

Damping uses the frozen analytic rule zeta=0.5, D=2*zeta*sqrt(m*K_tangent) at 100 N, and the rotational analog at 20 Nm. Coefficients were selected from deformation targets without inspecting a new High-ROM trajectory.

Bench: one free rigid body against a fixed cuff frame, no gravity/contact/controller. Mass 1.23114691647 kg, isotropic inertia 0.0545369149438 kg m^2, from smallest principal directional inertia at the frozen nominal 5/10 deg reset. This omits full coupling and configuration dependence; it is a local test fixture, not a globally conservative plant surrogate. MuJoCo 3.10.0, implicitfast, Newton, 100 iterations, tolerance 1e-8; interface load applied explicitly each step.



## Static load-deflection

| Candidate | Load type | Load N or Nm | Deflection | Unit |
| --- | --- | --- | --- | --- |
| P1 | force | 25 | 0.373312 | mm |
| P1 | force | 50 | 0.627466 | mm |
| P1 | force | 100 | 0.950671 | mm |
| P1 | force | 150 | 1.168942 | mm |
| P1 | force | 200 | 1.337856 | mm |
| P1 | force | 300 | 1.598196 | mm |
| P1 | moment | 10 | 0.300028 | deg |
| P1 | moment | 20 | 0.533710 | deg |
| P1 | moment | 40 | 0.853042 | deg |
| P1 | moment | 50 | 0.971282 | deg |
| P2 | force | 25 | 0.265326 | mm |
| P2 | force | 50 | 0.481250 | mm |
| P2 | force | 100 | 0.786620 | mm |
| P2 | force | 150 | 1.000000 | mm |
| P2 | force | 200 | 1.165837 | mm |
| P2 | force | 300 | 1.420889 | mm |
| P2 | moment | 10 | 0.229524 | deg |
| P2 | moment | 20 | 0.420743 | deg |
| P2 | moment | 40 | 0.697030 | deg |
| P2 | moment | 50 | 0.801522 | deg |

Both candidates pass the registered static targets, positive-stiffness and axis-alignment checks. The additional 300 N point is a static extreme-load point, not a trajectory or capability scan.

Historical media note: `load_deflection_curves.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



## Determinism, deformation and mechanics

18/18 repeat pairs passed rtol=0, atol=1e-12; 414 array pairs were rechecked during postprocessing, maximum absolute difference 0. All 36/36 runs have complete 0.2 s coverage, finite values, zero MuJoCo warnings and no runtime errors.

| Candidate | Maximum translation mm | Maximum rotation deg | Largest final/initial total energy |
| --- | --- | --- | --- |
| P1 | 1.337856 | 0.971282 | 1.816e-20 |
| P2 | 1.165837 | 0.801522 | 2.130e-22 |

Across all cases: max force balance residual 0 N; moment balance 1.93948e-17 Nm; instantaneous power identity residual 2.13163e-14 W. Damping power never negative. Motion remains bounded, but successful decay alone does not satisfy the discrete passivity gate.



## Timestep comparison and discrete energy

Waveform thresholds are Linf <=5%, L2 <=2%, native peak relative difference <=5%, plus independent physical-force peak difference <=2 N. Frozen absolute budgets are force 0.1 N, moment 0.01 Nm, translation 0.01 mm, rotation 1e-4 rad, energy 1e-5 J; each norm uses max(absolute budget, relative budget). Comparisons use coarse linear interpolation on the fine time grid, with no shifting or smoothing. Full per-case values are in numerical_comparison.csv.

| Candidate | dt vs .25 ms | Force Linf % | Force L2 % | Moment Linf % | Moment L2 % | x Linf % | theta Linf % | Force peak delta N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 1 ms | 18.7883 | 28.3819 | 7.9502 | 13.8466 | 9.5357 | 5.6286 | 0.0000 |
| P1 | .5 ms | 5.6908 | 9.0162 | 2.5475 | 4.5145 | 2.9699 | 1.8103 | 0.0000 |
| P2 | 1 ms | 19.0508 | 28.9454 | 8.7931 | 15.4017 | 10.8291 | 6.3020 | 0.0000 |
| P2 | .5 ms | 5.7786 | 9.1732 | 2.7780 | 4.9971 | 3.3733 | 2.0212 | 0.0000 |

Native force peaks agree because the prescribed 200 N initial preload sets the maximum in these releases. This passes the 2 N peak gate but does not establish waveform convergence. Half-step errors decrease, yet force and moment waveform gates still fail.

Interface residual R=U-U0+integral(P+D)dt; scale S=max(max U, final dissipated energy, max absolute net port work). Required max|R|/S <=1%, positive R/S <=0.5%. Total kinetic+spring energy may increase per step by at most max(1e-10 J, 1e-5 E0).

| Candidate | Release | dt ms | max abs R/S % | max total-E step rise J | allowed rise J | Energy gate |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | translation_release_200n | 1.0 | 20.494361 | 0 | 9.37407e-07 | False |
| P1 | translation_release_200n | 0.5 | 9.894460 | 0 | 9.37407e-07 | False |
| P1 | translation_release_200n | 0.25 | 4.873973 | 0 | 9.37407e-07 | False |
| P1 | rotation_release_50nm | 1.0 | 0.555904 | 0.000544957 | 3.41219e-06 | False |
| P1 | rotation_release_50nm | 0.5 | 0.134008 | 3.43634e-05 | 3.41219e-06 | False |
| P1 | rotation_release_50nm | 0.25 | 0.032910 | 2.15249e-06 | 3.41219e-06 | True |
| P1 | combined_release_200n_50nm | 1.0 | 4.437891 | 3.17672e-08 | 4.34959e-06 | False |
| P1 | combined_release_200n_50nm | 0.5 | 2.133248 | 1.20269e-07 | 4.34959e-06 | False |
| P1 | combined_release_200n_50nm | 0.25 | 1.050445 | 2.41411e-08 | 4.34959e-06 | False |
| P2 | translation_release_200n | 1.0 | 21.387696 | 0 | 8.88733e-07 | False |
| P2 | translation_release_200n | 0.5 | 10.321618 | 0 | 8.88733e-07 | False |
| P2 | translation_release_200n | 0.25 | 5.082267 | 0 | 8.88733e-07 | False |
| P2 | rotation_release_50nm | 1.0 | 0.636391 | 0.00061425 | 2.92284e-06 | False |
| P2 | rotation_release_50nm | 0.5 | 0.155883 | 3.87657e-05 | 2.92284e-06 | False |
| P2 | rotation_release_50nm | 0.25 | 0.038225 | 2.42877e-06 | 2.92284e-06 | True |
| P2 | combined_release_200n_50nm | 1.0 | 4.978189 | 9.85018e-14 | 3.81157e-06 | False |
| P2 | combined_release_200n_50nm | 0.5 | 2.403851 | 6.47968e-09 | 3.81157e-06 | False |
| P2 | combined_release_200n_50nm | 0.25 | 1.184003 | 5.10142e-18 | 3.81157e-06 | False |

Translation energy residuals are negative (excess discrete loss relative to the registered port-work identity), not evidence of net energy creation. Rotation-only ringdowns at 1 and 0.5 ms additionally exceed the per-step total-energy-rise budget. All final energies decay, but these discrete-energy failures remain. At 0.25 ms the translation residual is still 4.873973% / 5.082267% (P1/P2), so that reference is not fully energy-qualified either.

These failures occur in a controller-free mechanics bench under explicit load stepping. They establish failure of this implemented model/numerical contract combination. They cannot be attributed to CEM, actions or Reference Manager divergence, and do not establish failure of the continuous conservative spring law.

Historical media note: `ringdown_convergence.png` was externalized during
repository closeout. Its archived path and SHA-256 remain in
[`EXTERNAL_RAW_ARCHIVE_SHA256SUMS`](../../summaries/phase3a_corrected_high_rom/EXTERNAL_RAW_ARCHIVE_SHA256SUMS).



## Verdict and closed-loop gate

| Check | Verdict |
| --- | --- |
| bench_static | PASS |
| MECHANICS_CONSISTENCY | PASS_WITHIN_STANDALONE_BENCH |
| DETERMINISM | PASS |
| DISCRETE_ENERGY | FAIL |
| BENCH_TIMESTEP_AGREEMENT | FAIL |
| CLOSED_LOOP_TIMESTEP_AGREEMENT | NOT_RUN |
| TASK_RESULT | NOT_RUN_GATE_CLOSED |
| FORCE_CONTRACT | NOT_EVALUATED_NO_CLOSED_LOOP |
| motion_bounds | PASS_WITHIN_STANDALONE_BENCH |

No candidate satisfies all required numerical gates; no compliant 40/40 or rigid-vs-compliant A/B is authorized by these gates. No controller/task failure or physical force-contract classification is inferred from this standalone bench.

Preserved rigid 40/40 context: COMPLETE / STRICT_PASS, tracking RMSE 0.1624167776 deg, physical force peak 117.4563479259 N. New compliant task tracking, Human ROM, BRAKE/NO_SAFE_ACTION, force-contract result and degradation versus rigid are unavailable because no closed-loop gate run was executed. Bench preload peaks are not comparable to these full-task peaks.

The old linear candidate (Kt=500 N/m, Dt=35.6390267653 Ns/m, Kr=20 Nm/rad, Dr=1 Nms/rad) is retired in the new registration and retained as negative evidence: 49.7481 mm separation during the early 40/40 hold, stopped at 0.118 s. All historical evidence hashes remain unchanged.



## Files, commands and checks

Added: progressive_interface.py; PROGRESSIVE_INTERFACE_BENCH_SPEC.md/.json; run_progressive_interface_bench.py; test_progressive_interface.py; summarize_progressive_interface_bench.py; this new result directory. Existing untracked interface/qualification work was preserved. No tracked file changed.

Commands (Python = /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python):

```text

PYTHONDONTWRITEBYTECODE=1 <Python> -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_interface.py

<Python> stages/stage4_adaptive_control/scripts/run_progressive_interface_bench.py --freeze

<Python> stages/stage4_adaptive_control/scripts/run_progressive_interface_bench.py --run

<Python> stages/stage4_adaptive_control/scripts/summarize_progressive_interface_bench.py

git status --short

git diff --check

```

Nine targeted tests passed before freezing/execution. Bench command exited successfully with 36 mechanically complete runs, but numerical qualification failed. Postprocessing verifies frozen hashes, original sources/configs, old evidence, both repeats and full coverage; it performs no simulation.

Verified 61 original frozen source/config files, 21 old evidence files, 6 old implementation files and 3 registered new implementation files.

Only the opt-in interface law/coefficients and isolated bench were introduced. No MPC, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, trajectory law, seed or closed-loop numerical settings changed. Bench timestep variation was preregistered. No 40/80, 90/120, 120/120, capability scan, new 40/40 or other A/B rollout was run. No post-result parameter or threshold changes. Everything remains uncommitted; no push or merge.

Formal command reserved for user: none at present; the numerical gate is closed. Do not run the conditional 40/40.
