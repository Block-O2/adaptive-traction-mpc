# Progressive global cuff interface: registered engineering bench

Status: preregistered for the user's requested component bench and conditional single 40/40 gate. Numerical choices below are engineering test budgets, not clinical or tissue limits. No new closed-loop trajectory has been used to select these parameters.

## Retired negative evidence

The previous Kt=500 N/m, Dt=35.63902676526988 Ns/m, Kr=20 Nm/rad, Dr=1 candidate is retired from this workstream. Its first 1 ms 40/40 run ended at 0.118 s on the existing Human ROM guard with 49.748 mm global cuff separation. Its files, source and frozen Spec remain untouched; hashes are retained in this registration. It is not requalified or rerun.

## Opt-in equation and motion semantics

R is the robot cuff site, H the Human cuff site. Rest remains coincident, with no loaded capture. In the moving H frame:

- x = R_H^T(p_R-p_H), u = R_H^T(v_R-v_H-omega_H cross (p_R-p_H)).
- theta = Log(R_H^T R_R), w = R_H^T(omega_R-omega_H).
- F_R = -R_H[(k1+k3||x||²)x+D u].
- M_R = -R_H[(kr1+kr3||theta||²)theta+Dr w], about R.
- F_H = -F_R; M_H = -M_R+(p_R-p_H) cross F_H, about H.
- U = k1||x||²/2+k3||x||⁴/4+kr1||theta||²/2+kr3||theta||⁴/4.
- Dissipation = D||u||²+Dr||w||² >=0.

Positive coefficients give positive radial/tangential tangent eigenvalues k1+3k3 r² and k1+k3 r². The same applies to rotation away from the SO(3) logarithm cut. This is a potential-based engineering bushing, not measured human tissue. Its constitutive passivity does not guarantee passivity of the explicit numerical step.

Translation and rotation are GLOBAL relative cuff-frame motions, not local tissue compression. The radial cubic intentionally couples coordinate magnitudes through ||x||; it does not introduce off-axis force under a one-axis static displacement. Zero direction error and isotropy are tested, rather than falsely claiming every mixed-axis tangent off-diagonal is zero. Transport moment is necessary for angular momentum balance, not parasitic constitutive coupling.

## Two candidates chosen from load-deflection goals

| ID | k1 N/m | k3 N/m³ | D Ns/m | kr1 Nm/rad | kr3 Nm/rad³ | Dr Nms/rad |
|---|---:|---:|---:|---:|---:|---:|
| P1 | 60000 | 5e10 | 490.68422685624563 | 1800 | 4e6 | 12.447966320580795 |
| P2 | 90000 | 6e10 | 497.92244971403426 | 2400 | 6e6 | 13.558199249717516 |

The small-motion slopes and progressive terms target <=1 mm at 100 N, <=2 mm at 200 N and <=1 deg at 50 Nm. Additional 300 N STATIC component loading checks the preferred <=3 mm extreme displacement; it does not change the controller's 200 N force contract. No task success data selects these coefficients.

Damping uses one frozen analytical rule: zeta=0.5 at the tangent stiffness of the 100 N translational / 20 Nm rotational static operating point, D=2*zeta*sqrt(m*k_tangent), Dr analogously. No damping sweep or outcome-based adjustment is allowed.

## Static bench

Solve k1 r+k3 r³=L monotonically for forces 25,50,100,150,200 N and moments 10,20,40,50 Nm. Save continuous curves 0–300 N and 0–50 Nm, root residuals and tangent eigenvalues. Check load-unload curves coincide (elastic law) and damping contributes zero at rest. Check x/y/z and a normalized diagonal direction for equal norm and no direction leakage (relative <=1e-12); root residual <=1e-8 in SI load units.

## Standalone MuJoCo ringdown

A free rigid body R is attached to fixed world frame H by the same interface law. Gravity, collision and controllers are absent in this component fixture; no Human/robot plant setting is edited. Initial displacement equals the constitutive static equilibrium under the stated load, with zero velocity. External preload is released at time zero. This initializes a bench release and never changes the bushing rest or a future 40/40 initial condition.

The fixture uses m=1.2311469164688353 kg and isotropic I=0.05453691494379049 kg m². These are reciprocals of the largest eigenvalues of translational/rotational blocks of J_rel M^-1 J_rel^T at the frozen de23ea3 [5°,10°] reset. The full matrix and derivation are saved. This choice exercises the lightest principal directional inertia locally; it discards translation/rotation coupling and configuration dependence, so it is not a globally conservative reduction or full-system qualification.

Three initial releases per candidate:

1. 200 N translation, direction normalized [1,2,3].
2. 50 Nm rotation, direction normalized [2,-1,1].
3. Combined 200 N / 50 Nm in those directions.

For each release: dt=1,0.5,0.25 ms; two deterministic repeats; 0.2 s duration. Total: 2 candidates ×3 releases ×3 timesteps ×2 repeats =36 standalone ringdowns. MuJoCo implicitfast/Newton/100 iterations/1e-8 tolerance; interface forces remain explicitly evaluated. No controller trajectory is executed during bench selection.

Order: P1 then P2; listed releases; listed dt; repeat1 then repeat2. End a case on warning/nonfinite or emergency motion (1 cm or 10°), preserving it as failed. Complete other registered bench cases so both registered candidates are assessed; do not add candidates/refinements. A provenance or implementation error stops the campaign for review.

## Numerical gates frozen before dynamics

- Repeat arrays: rtol=0, atol=1e-12; no warning or nonfinite state.
- Action/reaction and instantaneous power residuals <=1e-9 SI; damping >=-1e-10 W.
- All cases must finish, maximum translation <=3 mm and rotation <=1°.
- At 0.2 s, total kinetic+spring energy <=1e-4 of initial energy. A positive stepwise increase >max(1e-10 J,1e-5 initial energy) fails free-ringdown passivity.
- Interface R=U-U0+integral(P_R+P_H+D)dt. S=max(max U,final Edamp,max absolute net port work). max|R|/S <=1%; max positive R/S <=0.5%. Save total mechanical-energy balance separately too. Zero energy scale uses a 1e-10 J absolute residual budget.
- Compare 1 ms and 0.5 ms to 0.25 ms at matching physical time, linearly interpolating coarse vectors onto the fine grid; no smoothing/event shift. Both comparisons require L∞<=5%, L2<=2%, native peak difference<=5%; additionally transmitted force peak difference<=2 N.
- For near-zero reference signals use absolute budgets: force 0.1 N, moment 0.01 Nm, translation 1e-5 m, rotation 1e-4 rad, energy 1e-5 J. The gate is max(absolute budget, relative budget × reference norm). Report N/A relative errors for zero reference.
- If 1 ms Linf exceeds the absolute budget, 0.5 ms Linf must be no larger (1e-12 roundoff allowance). All dt must satisfy their own mechanics, energy and bounded-ringdown gates. The 0.25 ms reference is finite, not an exact solution.

Constitutive mechanics, discrete energy and timestep agreement are reported separately. Passing load-deflection curves alone cannot qualify 1 ms execution. Finite bounded trajectories alone cannot establish waveform convergence.

## Conditional 40/40 and stop

Select the lowest k1 among candidates passing every static and numerical gate. Selection is frozen BEFORE any 40/40. If none pass, STOP, no 40/40. If one is selected, run that candidate exactly once at 1 ms under the unchanged de23ea3 suspended/measurement/MPC/Reference Manager/force/solver/seed/trajectory contract. No alternate candidate after a task failure.

Require COMPLETE, original force contract satisfied, Human ROM respected, translation <=3 mm (report <=2 mm target separately), rotation <=1°, no BRAKE/NO_SAFE_ACTION. Report tracking vs preserved rigid 40/40; do not rerun rigid or harder endpoints. No 40/80,90/120,120/120, scans, tuning or new controller logic.

All source/config/old evidence hashes are recorded before execution. Save commands, static curves, every ringdown and failures, gate tables, plots and exact git status in a new directory. Leave everything uncommitted. This JSON plus this MD is the preregistration; no thresholds or coefficients are revised after observing dynamics.
