# Robust Force-Margin Sensitivity

## Scope

This is a deterministic, robot-only quasistatic sensitivity diagnostic for
the Bed-Supported Load Transfer V1 preposition. It asks whether the nominal
200 N component-force reserve at `[7,20] deg` and `[5,20] deg` survives the
registered engineering model/contact perturbations.

It does not modify the controller, 5 N guard, Human Model V2 nominal
constructor, bed model, trajectory, 10 degree tube, or the 80/120/200 N
engineering force boxes. It runs no dynamic liftoff or formal matrix and
generates no GIF. The perturbation ranges are engineering sensitivity ranges,
not clinical population bounds or a probability distribution.

At each posture and perturbed parameter struct,

\[
\tau_{hold}=G(q,\theta)+\tau_{passive,left}(q,0,\theta),\qquad
A(q,\theta)F_{hold}=\tau_{hold},
\]

and the reported 200 N component reserve is

\[
m_F=200-\lVert F_{hold}\rVert_\infty.
\]

All perturbations pass through the validated
`bed_supported_v1_parameter_override` interface. The retained Human V2
dynamics, passive-torque, and single-contact force-map implementations perform
the calculations; their formulas are not copied into the diagnostic.

## Registered one-at-a-time cases

The deterministic case registry contains:

- total/segment mass scaling: `+/-5%` and `+/-10%`; segment masses and inertias
  scale consistently with total body mass;
- independent `lc1` and `lc2` scaling: `+/-5%` and `+/-10%`;
- passive stiffness matrix scaling: `+/-10%` and `+/-20%`;
- independent `q_rest1`/`q_rest2` offsets of `+/-2 deg` and same-direction
  offsets of both rest angles;
- robot contact location `sc`: `+/-2%` and `+/-5%`.

For every case and both postures, the output records force components, 2-norm,
infinity norm, force margin, nominal-relative margin change, torque residual,
mapping singular value/condition number, 200 N feasibility, and the requested
10 N/5 N/positive-below-5/nonpositive classifications.

## Nominal reproduction

| Posture | F_parallel (N) | F_perp (N) | norm inf (N) | margin (N) | Soft-limit clearance |
|---|---:|---:|---:|---:|---:|
| Practical `[7,20] deg` | -190.485281 | 15.711983 | 190.485281 | 9.514719 | 2 deg |
| Nominal maximum `[5,20] deg` | -189.445873 | 15.533882 | 189.445873 | 10.554127 | activation boundary |

The nominal advantage of `[5,20] deg` is `1.039407 N`, exactly reproducing
the preceding dense force-margin map.

## One-at-a-time sensitivity

The worst one-at-a-time case is `+10%` mass:

| Posture | F_parallel (N) | margin (N) | nominal-relative change (N) | 200 N feasible |
|---|---:|---:|---:|---|
| `[7,20] deg` | -206.802653 | -6.802653 | -16.317373 | no |
| `[5,20] deg` | -205.892916 | -5.892916 | -16.447043 | no |

At the practical posture, the adverse direction selected at the lower/full
registered level for each family is:

| Family | Lower-level adverse case / margin (N) | Full-level adverse case / margin (N) |
|---|---:|---:|
| mass | `+5%` / 1.356033 | `+10%` / -6.802653 |
| lc1 | `+5%` / 4.938336 | `+10%` / 0.361953 |
| lc2 | `-5%` / 6.691559 | `-10%` / 3.868399 |
| K | `+10%` / 6.783564 | `+20%` / 4.052409 |
| q_rest | both `-2 deg` / 2.183520 | same / 2.183520 |
| sc | `+2%` / 8.668282 | `+5%` / 7.459085 |

Mass is the strongest individual driver. At the full registered levels,
proximal COM location (`lc1`) and the same-direction rest-angle shift are the
next largest erosions. `lc2`, stiffness, and contact location matter but do
not individually dominate mass in this setup.

## Deterministic combined stress cases

Directions are not preassigned by sign. They are selected from the measured
Layer-1 margin at the primary `[7,20] deg` posture, then the same combined
parameter struct is evaluated at both postures:

- **mild**: the two largest lower-level erosions, `mass +5%` and both rest
  angles `-2 deg`;
- **moderate**: all lower-level adverse family choices;
- **adverse**: all full-level adverse family choices.

| Case | `[7,20]` margin (N) | `[5,20]` margin (N) | 200 N feasible at either posture |
|---|---:|---:|---|
| mild | -5.975167 | -5.000594 | no |
| moderate | -17.969214 | -16.743433 | no |
| adverse | -39.091587 | -37.674743 | no |

These combinations are transparent engineering stress cases. They are not
statistically calibrated joint patient distributions, and correlation or
likelihood is not implied.

## Five-newton guard interpretation

At `[7,20] deg`, a 5 N cutoff would reject the following registered cases:

`mass +5%`, `mass +10%`, `lc1 +5%`, `lc1 +10%`, `lc2 -10%`, `K +20%`,
`q_rest2 -2 deg`, both rest angles `-2 deg`, and all three combined cases.

The first registered one-at-a-time case below 5 N is `mass +5%`; the first
nonpositive case is `mass +10%`. The smallest positive margin is `0.361953 N`
under `lc1 +10%`.

Therefore, the guard is useful as an operational filter **if the perturbed
required force is known accurately**, but a nominal-model 5 N reserve is
**clearly insufficient as an uncertainty allowance** under these registered
engineering ranges. The nominal `[7,20] deg` point passes the guard while a
single `+5%` mass perturbation leaves only `1.356 N`, and the mild deterministic
combination is already infeasible.

This does not establish that 5 N is or is not a clinical safety margin.

## `[5,20]` versus `[7,20]`

`[5,20] deg` retains a force-margin advantage in every registered case. The
advantage is about `0.975 N`, `1.226 N`, and `1.417 N` in the mild, moderate,
and adverse combined cases. It does not change the feasibility class: both
postures fail all three combined stress cases, and both fail the worst
one-at-a-time mass case.

The approximately 1 N nominal advantage therefore has little practical
robustness significance in this diagnostic. Retaining `[7,20] deg` and its
2 degree soft-limit clearance is the more defensible practical choice; this
is a posture-selection interpretation only and does not modify the existing
controller or guard.

## Decision boundary

The evidence categories remain distinct:

1. **Nominal feasibility:** both postures are exact robot-only holds under the
   nominal model and 200 N box.
2. **Engineering robustness:** the approximately 10 N nominal reserve does not
   survive the registered sensitivity set; even the mild combined stress case
   is infeasible.
3. **Clinical safety:** not evaluated. Neither 200 N nor 5 N is established as
   clinically safe, and the perturbations do not represent patient statistics.

Consequently, the 200 N / 10 degree nominal result alone does not justify
proceeding to a dynamic takeover experiment as robustness evidence. A future
dynamic study would first need an approved response to the parameter-dependent
force requirement; this diagnostic does not authorize guard changes, force-
bound changes, controller tuning, or a different support model.

The follow-on full-path implementation reuses this exact registered case set
to compute nominal and registered-robust liftoff boundaries plus same-posture
bed-support overlap. The subsequent user-run result finds a continuous robust
overlap only for the 200 N box; see
[ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md](ROBUST_SUSPENDED_FEASIBILITY_ENVELOPE.md).

## Reproduction and artifacts

Headless command:

```text
matlab -batch "addpath(genpath('linkage/matlab')); run_robust_force_margin_sensitivity"
```

Ignored outputs are under:

```text
linkage/results/local/bed_supported_load_transfer_v1/robust_force_margin_sensitivity/
```

They include `summary.txt`, `sensitivity_cases.csv`, the complete MAT
workspace, console log, and four headless PNG figures. No GIF is generated.
