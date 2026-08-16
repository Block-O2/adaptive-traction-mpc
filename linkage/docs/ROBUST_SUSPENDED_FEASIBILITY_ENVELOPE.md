# Robust Suspended Feasibility / Liftoff Envelope

## Status and scope

The deterministic implementation and its mechanical contract tests are
present. The user executed the registered full numerical envelope on
2026-08-15 with MATLAB R2025b Update 1. The generated local outputs are
mechanically complete, and all 51 reached boundaries satisfy the recorded
coarse-to-refined numerical convergence criteria.

The diagnostic retains the current Human Model V2, passive model,
single-contact force map, geometric path, tube schedule, horizontal bed model,
calibrated hip height, 5 N guard, and 80/120/200 N engineering force boxes.
It changes no controller and runs no dynamic takeover or formal 18-case
matrix. The result is a quasistatic engineering envelope, not clinical safety,
a patient-population guarantee, a validated mattress model, or proof of
dynamic liftoff/recontact.

## Geometric path and candidate set

Progress `s in [0,1]` parameterizes only the retained outbound geometry from
`[5,10] deg` to `[45,84] deg`. All samples use `qdot=qddot=0`. The return path
has the same geometric envelope in reverse, but this identity says nothing
about dynamic recontact.

At every progress value, the existing continuous
`hybrid_tube_v1_tube_schedule` supplies the component-wise 0/5/10 degree tube.
A deterministic rectangular candidate grid includes the exact path posture,
tube edges, and zero offset. Candidates outside ROM, at `q2<=0`, with active
soft limits, with rank loss, or with excessive exact torque residual are not
eligible for a recommended posture. Soft-active samples remain countable
diagnostics; their torque cannot improve the selected envelope.

Selection minimizes required component force. Ties are resolved by path
deviation and then lexicographic joint posture, so no preferred posture is
hard-coded.

## Nominal and registered-robust hold force

For every eligible candidate,

```text
tau_hold = G(q) + tau_passive_left(q,0)
A(q) F_hold = tau_hold
m_nom(q;B) = B - norm(F_hold,Inf)
```

The robust requirement reuses, without changing ranges or directions, every
one-at-a-time case and the mild/moderate/adverse deterministic combinations
registered in `ROBUST_FORCE_MARGIN_SENSITIVITY.md`:

```text
m_robust(q;B) = B - max_theta norm(F_hold(q,theta),Inf)
```

The implementation records the worst case ID, force components and norms,
nominal map singular value and condition number, exact torque residual, and
soft-limit clearance. “Robust” means only robust to this finite deterministic
engineering set.

## Bed support and same-posture overlap

The nominal calibrated `h_hip`, `y=0` plane, eight fixed lower-surface
candidates, and unilateral Kelvin-Voigt law are evaluated at zero velocity.
Bed availability uses the existing `contact_force_threshold_N`; no new support
threshold is introduced. Total bed force, active contact count, point gaps and
penetrations, and generalized bed torque are retained in the MAT workspace.

Three different questions remain separate:

1. whether the nominal path posture has bed support;
2. whether any eligible tube candidate has bed support;
3. whether one and the same eligible candidate has both bed support and a
   registered-robust robot-only margin above the requested threshold.

Only the third defines the quasistatic transfer overlap. Support at one posture
and robot feasibility at another cannot be combined into a window.

For each force bound and tube, `SUPPORT_GAP` means the tube loses bed support
before robot-only robust feasibility begins and no same-posture overlap exists.
`QUASISTATIC_TRANSFER_WINDOW_EXISTS` means a sampled continuous same-posture
overlap exists. Neither label proves a dynamic handoff.

## Boundary extraction and convergence

The production configuration uses:

- full-path progress step `0.01` and candidate step `1 deg`;
- local boundary progress step `0.002` and candidate step `0.5 deg`;
- a `0.02` progress refinement window;
- recorded coarse-to-refined `q2` and entry-margin changes;
- mechanical convergence tolerances of `0.75 deg` in selected `q2` and `2 N`
  in the boundary metric.

These are numerical-resolution checks, not safety thresholds. The output
reports the observed change and mechanical-convergence boolean for every
reached nominal, robust, bed-end, overlap-start, and overlap-end boundary.
The 0/5/10/20 N robust levels are diagnostic reserve levels, not medical
standards.

## Output contract

The ignored local result directory is:

```text
linkage/results/local/bed_supported_load_transfer_v1/
robust_suspended_feasibility_envelope/
```

The runner writes `summary.txt`, `envelope_samples.csv`,
`boundary_summary.csv`, `boundary_details.csv`, a complete MAT workspace, a
console log, and six headless PNG figures. No GIF is generated.

`boundary_summary.csv` has one row for every 80/120/200 N by strict/5/10 degree
case and includes nominal zero entry, robust 0/5/10/20 N entries, bed-support
end, overlap start/end/duration, segment count, support-gap flag, and
classification. `boundary_details.csv` carries the refined posture, forces,
worst uncertainty case, conditioning, residual, soft clearance, bed load,
contact count, and convergence deltas for each reached boundary. Full
point-wise bed gaps, penetrations, and generalized torques remain in the MAT
workspace.

## Mechanical validation

Eleven new tests cover the two path endpoints, strict-tube identity, known
`[5,10] deg` static force, robust-versus-nominal ordering, exact force-bound
margin translation, exclusion of soft-active recommendations, initial bed
calibration reproduction, deterministic overlap and support-gap labels,
boundary-refinement convergence recording, and nominal-input immutability.

The retained suite currently reports 98 passed, 0 failed, and 0 incomplete.
MATLAB `checkcode` reports zero issues for the new source and runner.

The production run used 30 registered uncertainty cases. All 51 reached
nominal, robust, bed-end, overlap-start, and overlap-end boundaries meet the
`0.75 deg` selected-`q2` and `2 N` boundary-metric convergence criteria.

## Numerical boundaries

`NR` means the threshold is not reached anywhere on the outbound path.

| Bound | Tube | Nominal 0 N | Robust 0 N | Robust 5 N | Robust 10 N | Robust 20 N | Bed-support end | Robust overlap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 80 N | strict | NR | NR | NR | NR | NR | 0.394 | none |
| 80 N | 5 deg | NR | NR | NR | NR | NR | 0.414 | none |
| 80 N | 10 deg | NR | NR | NR | NR | NR | 0.432 | none |
| 120 N | strict | 0.548 | NR | NR | NR | NR | 0.394 | none |
| 120 N | 5 deg | 0.536 | NR | NR | NR | NR | 0.414 | none |
| 120 N | 10 deg | 0.524 | NR | NR | NR | NR | 0.432 | none |
| 200 N | strict | 0.120 | 0.230 | 0.246 | 0.264 | 0.304 | 0.394 | `[0.230,0.394]` |
| 200 N | 5 deg | 0.048 | 0.198 | 0.222 | 0.246 | 0.294 | 0.414 | `[0.198,0.414]` |
| 200 N | 10 deg | 0.000 | 0.108 | 0.142 | 0.202 | 0.280 | 0.432 | `[0.108,0.432]` |

The 80 N box is not even nominally feasible over the retained path. The
120 N box becomes nominally feasible near `s=0.52..0.55`, but remains just
outside registered robustness at peak flexion: its best robust margins are
`-1.333`, `-0.778`, and `-0.224 N` for strict, 5 degree, and 10 degree tubes.
It therefore has no robust suspended region under this finite uncertainty set.

Only the 200 N box forms a registered-robust suspended region. At the peak
geometry `s=1`, its robust reserve grows to `78.667`, `79.222`, and `79.776 N`
for strict, 5 degree, and 10 degree tubes, respectively. Larger knee flexion
therefore produces a clear reserve increase under the current model; the
approximately 10 N nominal reserve observed near `q2=20 deg` is not the
largest reserve available later on the path.

## Nominal versus robust entry

Uncertainty delays 200 N entry relative to the nominal envelope:

- strict: `s=0.120` nominal to `s=0.230` robust;
- 5 degree: `s=0.048` nominal to `s=0.198` robust;
- 10 degree: `s=0` nominal to `s=0.108` robust.

At `s=0`, the 10 degree tube nominal optimum `[5,20] deg` has `10.554 N`
reserve, while the registered adverse combination requires `237.675 N` and
gives `-37.675 N` reserve. At `s=1`, uncertainty erosion is much smaller,
about `19.5..19.7 N` across the three tubes.

Relative to strict tracking, the 5 degree tube advances 200 N robust entry by
`0.032` progress (`q2_path` from `27.020` to `24.652 deg`), and the 10 degree
tube advances it by `0.122` progress (`q2_path` to `17.992 deg`). The selected
robust postures are:

| Tube | Entry path posture (deg) | Selected posture (deg) | Margin | Bed force | Soft clearance |
|---:|---:|---:|---:|---:|---:|
| strict | `[14.200,27.020]` | `[14.200,27.020]` | 0.449 N | 30.948 N | 9.200 deg |
| 5 deg | `[12.920,24.652]` | `[10.718,26.854]` | 0.304 N | 90.341 N | 5.718 deg |
| 10 deg | `[9.320,17.992]` | `[5.436,26.376]` | 0.177 N | 598.514 N | 0.436 deg |

The earliest 10 degree result is mathematically feasible under the registered
set but is boundary-adjacent: it has almost no extra force reserve, limited
soft-zone clearance, and a very large force from the current fixed-hip bed
abstraction. It should not be treated as a preferred dynamic liftoff point.

## Bed support, overlap, and support gap

The nominal path loses the retained 2 N bed support at approximately
`s=0.394`, `q_path=[20.760,39.156] deg`. Searching the unchanged tube can
retain some support to `s=0.414` for 5 degrees and `s=0.432` for 10 degrees.
At those refined tube endpoints, the selected support postures retain one
contact point and approximately `2.124` and `2.252 N` bed force.

For 200 N, each tube has one continuous same-posture overlap segment. Coarse
sampled overlap ranges, supplemented by the refined endpoints, are:

| Tube | Progress interval | Sampled selected q1 range | Sampled selected q2 range | Robust margin range | Bed-force range |
|---:|---:|---:|---:|---:|---:|
| strict | `[0.230,0.394]` | 14.20..20.76 deg | 27.02..39.16 deg | 0.449..36.452 N | 2.338..30.948 N |
| 5 deg | `[0.198,0.414]` | 10.72..20.81 deg | 26.85..41.39 deg | 0.304..40.436 N | 2.124..90.341 N |
| 10 deg | `[0.108,0.432]` | 5.09..20.78 deg | 26.38..43.47 deg | 0.177..43.699 N | 2.252..682.648 N |

Thus `QUASISTATIC_TRANSFER_WINDOW_EXISTS` for all three 200 N tubes and no
`SUPPORT_GAP` occurs. The 80 N and 120 N cases are classified
`ROBOT_ONLY_THRESHOLD_NOT_REACHED`, not `SUPPORT_GAP`: their failure is the
absence of a robust suspended region over the entire path, rather than bed
contact ending slightly too early.

The large support forces selected by the early wide-tube solutions expose the
limitations of the current fixed-hip Kelvin-Voigt abstraction. They do not
validate mattress load, patient pressure, or dynamic feasibility.

## Liftoff, return, and next dynamic candidate

The earliest mathematical 200 N robust-overlap entries are `s=0.230`,
`0.198`, and `0.108` for strict, 5 degree, and 10 degree tubes. A more
defensible region for a future dynamic experiment is not the zero-margin edge.
For example, the 200 N / 10 degree envelope reaches 20 N registered reserve at
`s=0.280`, with path posture `[16.200,30.720] deg`, selected posture
`[18.024,32.544] deg`, `14.141 N` bed load, and `13.024 deg` soft clearance.

On geometric return, bed contact first becomes available when the outbound
bed-end boundary is crossed in reverse: `s=0.394`, `0.414`, or `0.432`.
If robot-only registered feasibility must persist until load return is
complete, recontact/load transfer must finish no later than the corresponding
overlap lower boundary `s=0.230`, `0.198`, or `0.108`. This is only a
quasistatic geometry interpretation.

Of the three force bounds, 200 N is the only defensible candidate for the next
approved dynamic load-transfer experiment because it is the only one with a
registered-robust suspended region and a continuous support overlap. The
10 degree tube gives the longest window, but its earliest edge is
boundary-seeking; a reserved-margin point such as the 20 N region is the more
informative initialization. This prioritization is not a clinical safety
claim and does not itself authorize the dynamic run.

## Reproduction command

The user-run envelope is reproduced with:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_robust_suspended_feasibility_envelope"
```

Review `summary.txt`, `boundary_summary.csv`, and `boundary_details.csv`
before using a force-bound case for a later dynamic load-transfer study.

## Dynamic follow-up

The 200 N / 10 degree, 20 N-reserve candidate is consumed by the separate
[Dynamic Robust Load Transfer V1](DYNAMIC_ROBUST_LOAD_TRANSFER_V1.md).
That implementation does not reinterpret this quasistatic envelope as a
dynamic safety proof: it additionally predicts inverse-dynamics force and
bounded residual at the current candidate motion, and it requires real stable
bed unloading/recontact before the corresponding hybrid transitions.
