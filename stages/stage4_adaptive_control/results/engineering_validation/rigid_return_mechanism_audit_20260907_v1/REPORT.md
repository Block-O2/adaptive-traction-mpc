# Phase-3A rigid return mechanism audit

Evidence category: **exploratory diagnostic only**. This audit reads existing saved evidence only. It does not integrate dynamics, replay a trajectory, change a parameter, or revise the previous strict numerical-qualification result.

## Critical-window comparison

The 40/80 center is the first `BRAKE` sample at **t=11.935 s**, reference return progress **21.31%**. Windows are ±0.4 s. The 90/120 evidence has no actual q overlap: its closest return-phase estimated configuration is still **14.26°** away in two-joint Euclidean angle distance, so both same-progress and nearest-q comparisons are retained.

| slice | t | return progress | q est [hip,knee] deg | dq est [hip,knee] deg/s | qref deg | nominal command force | filter | lambda | cond(B Human) | cond(J robot) | mode |
|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---|
| 40/80 pre-filter | 11.930 | 21.24% | [37.25, 75.84] | [-32.62, 39.74] | [37.62, 75.25] | 206.08 | SAFE_FILTERED | -40.97 | 5.273 | 5.757 | TRACK |
| 40/80 BRAKE entry | 11.935 | 21.31% | [37.12, 75.84] | [-35.81, 36.88] | [37.60, 75.21] | 213.38 | FILTER_INFEASIBLE | 0.00 | 5.273 | 5.757 | BRAKE |
| 90/120 same return progress | 18.125 | 21.32% | [86.05, 108.29] | [-5.57, -5.63] | [84.17, 112.46] | 129.87 | SAFE_UNCHANGED | 0.00 | 4.889 | 7.983 | TRACK |
| 90/120 nearest q | 21.810 | 49.94% | [47.15, 65.70] | [-43.03, -2.72] | [47.60, 65.13] | 186.76 | SAFE_UNCHANGED | 0.00 | 5.428 | 5.558 | TRACK |

Additional component-level values at 40/80 BRAKE entry:

- Rejected TRACK desired Human torque: **[59.167, 1.714] Nm**.
- Rejected nominal allocator wrench `[Fx,Fy,Fz,Mx,My,Mz]`: **[-110.447, -0.050, 91.195, 0.000, 2.434, 0.001]**.
- Rejected nominal total command force `[Fx,Fy,Fz]`: **[-81.557, -0.035, 197.182] N**; from the preceding filterable cycle: **[-80.531, -0.240, 189.719] N**.
- Derived non-allocator feedback contribution `[Fx,Fy,Fz]`: **[28.890, 0.015, 105.987] N**; preceding cycle: **[30.138, -0.205, 98.757] N**. The 5 ms change is **[-1.247, 0.220, 7.230] N**, dominated by +z.
- The torque-preserving force direction changed by only **0.1275°**. Along that one-dimensional family, the minimum attainable total-force norm rose from **199.762 N** to **206.444 N**, crossing the unchanged 200 N gate.
- At entry, the stored supervisor candidate count is **6**, meaning six BRAKE-rate candidates were feasible after TRACK rejection; it is not a CEM-population feasible count.

Window peak slew values are in `critical_window_metrics.json`; component-aligned traces are in the two audit PNGs.

| slice | desired Human torque [Nm] | applied allocator [Fx,Fz,My] | applied command Fxyz [N] | physical Fxyz [N] | applied command Mxyz [Nm] | physical Mxyz [Nm] | dq proxy error [deg/s] |
|---|---|---|---|---|---|---|---|
| 40/80 pre-filter | [59.17, 1.71] | [-143.32, 66.09, -11.89] | [-113.14, -0.24, 164.92] | [-155.98, 9.12, 61.78] | [0.56, -29.84, 0.31] | [10.38, -21.04, -7.69] | [-13.30, 45.83] |
| 40/80 applied BRAKE | [35.42, 8.89] | [-94.82, 55.44, 3.10] | [-65.90, -0.02, 161.48] | [-191.17, 7.95, 41.29] | [0.41, -15.24, 0.36] | [10.79, -35.79, -8.13] | [-21.17, 48.47] |
| 90/120 same progress | [15.94, 11.93] | [-64.44, -6.87, 0.85] | [-69.45, -0.79, -109.74] | [-80.11, 25.21, -97.46] | [-0.30, 13.19, -0.13] | [35.40, -34.06, 13.01] | [1.22, 1.42] |
| 90/120 nearest q | [54.34, -2.32] | [-112.97, 53.31, 2.95] | [-125.58, -0.23, 138.24] | [-144.88, 28.71, 32.78] | [-0.29, -8.38, 0.18] | [9.64, -12.43, -2.27] | [-27.14, 29.64] |

| ±0.4 s window | command force slew [N/s] | physical force slew [N/s] | command moment slew [Nm/s] | physical moment slew [Nm/s] |
|---|---:|---:|---:|---:|
| 40/80 event | 11465.0 | 197745.7 | 3066.0 | 64767.1 |
| 90/120 same progress | 1725.2 | 17457.7 | 97.2 | 3684.0 |
| 90/120 nearest q | 8908.5 | 105713.7 | 502.5 | 17137.1 |

## DIRECTLY OBSERVED

- From 11.920→11.935 s, the selected TRACK action remains **[59.167, 1.714] Nm**. `mpc_status` is `NO_NEW_MPC` at 11.925, 11.930, and the 11.935 transition. The last CEM update was at 11.920 s; there is no immediate CEM winner switch at BRAKE entry.
- Nominal executable-force norm progresses **185.493 → 196.917 → 206.083 → 213.383 N** over those four 5 ms cycles. At 11.930 s the filter applies λ=-40.971 and returns exactly 200 N; at 11.935 s the filter reports `FILTER_INFEASIBLE`.
- The force component that changes most from the last filterable nominal command to the rejected command is world z: **+7.463 N** in 5 ms, versus x **-1.026 N**. Most of the z rise appears in the derived low-level feedback term (**+7.230 N**), while the nominal allocator wrench changes only slightly.
- Human allocation condition number changes -0.0010% and robot attachment-Jacobian condition number changes -0.0003% from 11.930 to 11.935 s. No local conditioning collapse is present.
- Immediately after TRACK rejection, all six registered BRAKE-rate candidates are feasible and `NO_SAFE_ACTION` remains zero. This is a TRACK-command feasibility loss followed by successful BRAKE fallback, not total safe-action depletion.
- At equal return progress, 90/120 is in a very different configuration and has nominal command force **129.87 N**. At its closest return configuration, it remains `SAFE_UNCHANGED` at **186.76 N**; the minimum norm along its local torque-preserving family is **186.07 N**.

## SUPPORTED BY CURRENT EVIDENCE

- The dominant mechanism is a **directional executable-force incompatibility**: the total command's component orthogonal to the torque-preserving nullspace rises above 200 N. Force magnitude is the trigger variable, but direction relative to the allowed nullspace explains why a nonzero λ can rescue 11.930 s and cannot rescue 11.935 s.
- The immediate loss is history/velocity and low-level tracking-context dependent more than a static singularity. The same held Human torque and nearly unchanged B/J geometry encounter a rising +z feedback demand. The 40/80 estimator also shows a large knee-velocity proxy error at entry (**+48.47°/s**), whereas 90/120 at equal progress has **+1.42°/s**; this is associated evidence, not proof that the estimator caused the event.
- 90/120 avoids the transition because its realized return path does not traverse the 40/80 BRAKE state and its executable command remains inside the gate at the examined same-progress and closest-q slices. Its larger nominal ROM therefore does not imply a monotonic increase in this local feasibility demand.
- The optimizer contributes upstream: the 11.920 s CEM update raises the nominal force from 128.168 N at 11.915 s to 185.493 N. Current logs support that this action left little later margin; they do not show that CEM selected a wrong winner.

## UNRESOLVED

- Per-candidate CEM scores, winner identity/switching history, and CEM-population feasible counts are not present in these saved arrays. The supervisor's `feasible_candidate_count` cannot answer those questions.
- The rejected 11.935 s command can be decomposed into saved nominal allocator and derived non-allocator feedback, but the evidence does not split that feedback further into position versus velocity terms. A causal attribution to estimator error, robot tracking lag, or a particular gain is therefore not supported.
- Because 90/120 has no close return-phase q overlap with the 40/80 event, the saved evidence cannot isolate configuration from history with a matched-state counterfactual.

## NOT SUPPORTED

- A Human allocation singularity or robot cuff-Jacobian singularity as the immediate cause.
- Exhaustion of BRAKE candidates or `NO_SAFE_ACTION` at the transition.
- An immediate CEM winner switch at 11.935 s.
- Physical-force contract violation as the trigger: 40/80's physical peak is 197.50 N and its saved force-contract classification remains unchanged.
- Any claim that higher target ROM must monotonically worsen executable feasibility.

## Repeated P1 acceleration peak

| P1 trajectory | peak [m/s²] | peak time [s] | reference phase [s] | mode | acceleration vector [m/s²] |
|---|---:|---:|---:|---|---|
| 40/40 | 9.035075344 | 0.000125 | 0.000000 | TRACK | [1.425799, 0.000000, -8.921866] |
| 40/80 | 9.035075344 | 0.000125 | 0.000000 | TRACK | [1.425799, 0.000000, -8.921866] |
| 90/120 | 9.035075344 | 0.000125 | 0.000000 | TRACK | [1.425799, 0.000000, -8.921866] |

All three peaks are bit-identical and occur in the first finite-difference interval **[0, 0.00025] s**, centered at 0.000125 s, with reference phase 0 and initial TRACK mode. Initial P1 translation and physical force are effectively zero. This directly locates the peak at the shared controller/interface startup transient before trajectory motion; the saved evidence does not support a later trajectory transition or a trajectory-specific mechanism.

## Existing rigid outcomes

| trajectory | formal task label | tracking RMSE | endpoint error | return error | BRAKE cycles | FILTER_INFEASIBLE | command peak | physical peak |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 40/40 | COMPLETE | 0.158° | 0.001° | 0.013° | 0 | 0 | 121.05 N | 117.45 N |
| 40/80 | SAFE_INCOMPLETE | 24.662° | 0.017° | 64.241° | 1786 | 1 | 200.00 N | 197.50 N |
| 90/120 | SAFE_INCOMPLETE | 1.929° | 4.184° | 0.052° | 0 | 0 | 199.79 N | 158.73 N |

40/40 completes without BRAKE. Rigid 40/80 reaches the outbound endpoint within tolerance but enters BRAKE early in return and finishes with a large return error. Rigid 90/120 stays TRACK throughout and physically returns within tolerance, but retains its original `SAFE_INCOMPLETE` label because its outbound endpoint error exceeds the frozen 0.068969° tolerance.

## Dominant hypothesis and next test

The strongest current hypothesis is: **the 40/80 non-monotonic boundary is created when a held CEM torque action, evolving robot/cuff tracking feedback, and the one-dimensional torque-preserving Safety Filter combine so that the irreducible force component exceeds 200 N.** The evidence rules against an instantaneous geometry-conditioning collapse and against BRAKE-candidate depletion. It supports a trajectory-history/local-state interaction, with optimizer choice upstream and the Safety Filter providing the deterministic transition criterion.

A single frozen 120/120 exploratory A/B is scientifically justified next as a discriminator of whether the non-monotonic return-path effect persists at another symmetric high-ROM point. It would not establish a monotonic capability boundary or causally isolate the mechanism. No 120/120 run was performed here.

## Audit integrity

- Evidence coverage: all five expected saved files were present for each audited run; all arrays used here were finite; saved warning counts were zero.
- Source evidence hashes are recorded in `source_hashes.json`.
- Generated tables and plots are checksummed in `SHA256SUMS`.
- No controller, P1, safety, trajectory, solver, dt, seed, model, or tolerance setting was changed.
