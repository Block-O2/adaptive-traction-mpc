# Human Two-Link Model V2

## Purpose and isolation

Human Model V2 is a parallel anthropometric/passive-joint plant and slow
reference validation. Its MATLAB functions live under
`linkage/matlab/src/human_two_link_v2/` and use the unique
`human_two_link_v2_*` prefix. It does not replace or modify V1
`default_parameters.m`, V1 `dynamics_terms.m`, the preserved professor
reference, the old direct-torque oracle, or the frozen single-contact negative
baseline.

The V2 oracle has direct generalized-joint-torque authority only to verify the
plant and reference. It is not a robot command interface, endpoint-force
controller, NMPC result, clinical-safety result, or evidence that the
single-arm contact problem has been solved.

## Parameter provenance

### Literature/report-informed quantities

The anthropometric fractions are taken from Table 1 of the SmartSling modeling
paper, which reports thigh/shank lengths of 25.4%/23.3% body height,
thigh/shank/foot masses of 9.9%/4.6%/1.4% body mass, proximal COM fractions of
43.3%/43.0%, and 0.30 segment-length radii of gyration for thigh and shank:

- Cao et al., “Modeling and control of a bedside cable-driven lower-limb
  rehabilitation robot for bedridden individuals,” *Frontiers in
  Bioengineering and Biotechnology*, 2023:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC10702241/>.

That paper also describes synchronous sagittal hip/knee flexion and reports a
0–45 degree hip range during its impedance-estimation experiment. Those facts
motivate the trajectory class and 45 degree hip peak only. They do not define
the V2 timing, knee peak, speed, or a validated treatment protocol.

The project-specified ROM envelope, 0–80 degrees at the hip and 0–100 degrees
at the knee, is a conservative model-validation range rather than a claim of
universal human ROM. The 45/84 degree nominal peak stays inside that envelope.

### Engineering assumptions

The following are explicit engineering choices, not clinical constants:

- combining the reported 4.6% shank and 1.4% foot masses into one planar shank
  mass while retaining the supplied shank COM/radius model;
- `q_rest = [5, 10] deg`;
- `K_passive = diag(10,10) N m/rad` and
  `B_passive = diag(5,5) N m s/rad`, deliberately labeled low-end initial
  values;
- 5 degree soft-limit margin, cubic soft-limit shape, 25 N m physical restoring
  torque at the nominal ROM boundary, and 2 N m s/rad outward-velocity
  damping;
- a `1e-9 rad` numerical activation deadband at the soft-limit boundary, used
  only to prevent RK4 roundoff at the 5 degree starting pose from being logged
  as physical activation;
- `sc = 0.90 L2`, interpreted as the equivalent action location of a distal
  wide shank cuff or above-ankle brace, not an infinitesimal rigid point;
- the exact hold/move durations, minimum-jerk interpolation, and jerk values.

## Nominal adult parameters

For height (H) and body mass (M_b), the constructor uses

\[
\begin{aligned}
L_1&=0.254H,&L_2&=0.233H,\\
m_1&=0.099M_b,&m_2&=(0.046+0.014)M_b,\\
l_{c1}&=0.433L_1,&l_{c2}&=0.430L_2,\\
I_1&=m_1(0.30L_1)^2,&I_2&=m_2(0.30L_2)^2.
\end{aligned}
\]

The interface accepts any positive finite (H,M_b), although only the
requested nominal (H=1.72\,\mathrm{m}, M_b=75\,\mathrm{kg}) is run here.

| Quantity | Nominal value |
|---|---:|
| (L_1,L_2) | 0.436880, 0.400760 m |
| (m_1,m_2) | 7.425000, 4.500000 kg |
| (l_{c1},l_{c2}) | 0.189169, 0.172327 m |
| (I_1,I_2) | 0.127545, 0.0650465 kg m² |
| (s_c) | 0.360684 m |
| (g) | 9.81 m/s² |

## Dynamics and passive-torque convention

Coordinates remain

\[
q_1=\text{thigh absolute angle},\qquad
q_2=\text{positive knee flexion},\qquad
\phi=q_1-q_2.
\]

V2 uses one sign convention throughout:

\[
M(q)\ddot q+h(q,\dot q)+G(q)+\tau_{\rm passive,left}
=\tau_{\rm joint}.
\]

The physical soft-limit torque is defined on the right-hand side and points
toward the ROM interior. The left-side resistance is

\[
\tau_{\rm passive,left}
=K_{\rm passive}(q-q_{\rm rest})
+B_{\rm passive}\dot q
-\tau_{\rm soft,RHS}.
\]

The positive damping sign is required on the left: its dissipated power is

\[
\dot q^\mathsf{T}B_{\rm passive}\dot q\ge0.
\]

Moving the passive term to the right negates the entire term. Writing
`-B*dq` on the left would be anti-damping and is intentionally not used.
Deterministic tests verify both the algebraic right/left conversion and
damping dissipativity.

## ROM and soft limit

\[
q_{\min}=[0,0]^\circ,\qquad q_{\max}=[80,100]^\circ.
\]

Let (m=5^\circ). The physical right-side soft torque is exactly zero in

\[
q_{\min}+m\le q\le q_{\max}-m
\]

apart from the documented (10^{-9}) rad numerical boundary deadband. In a
lower soft zone, with normalized penetration (z\), it is

\[
+25z^3+2z^2\max(-\dot q,0),
\]

and in an upper soft zone it is

\[
-25z^3-2z^2\max(\dot q,0).
\]

Thus position torque always points inward and velocity damping acts only on
outward motion. The cubic/quadratic factors make the torque continuous with
zero slope at activation. No state or velocity is hard-clipped. Tests cover
zero safe-zone torque, lower/upper direction, continuity, and left-side sign.

## Slow passive engineering reference

`slow_passive_flexion_v2` is named only a **SmartSling-range-inspired
synchronous slow engineering trajectory**. It is not a therapist demonstration
or clinically validated protocol.

| Phase | Time | Progress |
|---|---:|---:|
| initial hold | 0–1.0 s | 0 |
| flexion | 1.0–7.5 s | quintic 0→1 |
| peak hold | 7.5–8.5 s | 1 |
| return | 8.5–15.0 s | quintic 1→0 |
| final hold | 15.0–16.0 s | 0 |

The common progress maps

\[
q_{\rm start}=[5,10]^\circ
\quad\text{to}\quad
q_{\rm peak}=[45,84]^\circ.
\]

Observed analytic reference extrema are:

| Metric | hip | knee |
|---|---:|---:|
| maximum velocity | 0.201384 | 0.372561 rad/s |
| maximum acceleration | 0.095400 | 0.176491 rad/s² |
| maximum jerk | 0.152528 | 0.282176 rad/s³ |

Velocity is below 0.40 rad/s and acceleration below 1.5 rad/s². The jerk is
recorded as an engineering descriptor, not a clinical-safety threshold.

## Oracle validation evidence

The independent V2 oracle uses

\[
\tau_{\rm joint}=M\ddot q_{\rm ref}+h+G+\tau_{\rm passive,left}
-K_p(q-q_{\rm ref})-K_d(\dot q-\dot q_{\rm ref}),
\]

with the old numerical gains copied into V2 configuration rather than calling
or editing the old oracle file. RK4 uses `dt=0.002 s`; initial position and
velocity exactly equal the reference.

| Observed metric | Value |
|---|---:|
| RMSE (q_1/q_2) | (7.18\times10^{-10}) / (2.74\times10^{-9}) deg |
| maximum error (q_1/q_2) | (1.58\times10^{-9}) / (5.94\times10^{-9}) deg |
| maximum passive-left torque | 7.062 / 13.065 N m |
| maximum oracle torque | 42.025 / 7.734 N m |
| maximum oracle torque norm | 42.086 N m |
| minimum actual ROM margin | 5.000 / 10.000 deg |
| ROM violations | 0 |
| soft-limit activations / maximum soft torque | 0 / 0 N m |
| NaN/Inf count | 0 |

These values show exact-model plant/reference consistency only. They do not
validate endpoint-force authority or a rehabilitation controller.

## Tests, commands, and artifacts

The V2 test file adds 18 deterministic tests covering the requested
anthropometric formulas and input validation, mass/Coriolis/gravity identities,
passive sign and damping, soft limits, distal contact position, trajectory
continuity and bounds, oracle accuracy, finite values, and ROM behavior. The
V2 test runner also runs every existing V1 and endpoint-force regression:
42/42 pass in MATLAB R2025b Update 1.

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_human_model_v2_tests"
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "addpath(genpath('linkage/matlab')); run_human_model_v2_baseline"
```

Ignored evidence is under `linkage/results/local/human_model_v2/`: nominal MAT
workspace, metrics CSV, parameter MAT/text snapshots, MATLAB version, command
record, logs, and exactly one 65-frame GIF,
`slow_passive_flexion_v2_nominal.gif`.

The only execution warning is MATLAB's inability to access the user's default
`~/Documents/MATLAB` directory. Repository execution and evidence generation
are unaffected.

## Scope conclusion

V2 clears the anthropometry, passive-sign, ROM, soft-limit, trajectory, and
exact-model-oracle plant checks with no model/runtime blocker. It does not
authorize editing the frozen negative baseline. A subsequent task may build a
new endpoint-force comparison against V2, but should first specify an
equilibrium-preserving force allocation and conditioning-aware feasibility
policy without retroactively changing V1 evidence.
