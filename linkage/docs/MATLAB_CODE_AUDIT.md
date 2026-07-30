# Read-Only Audit of `singleArmDual.m`

## Audit conventions and preservation

Labels used below:

- **Fact** — directly visible in the MATLAB source.
- **Inference** — a reasonable interpretation of the source, not an author
  statement.
- **Unresolved** — requires execution evidence or professor confirmation.

The root-level untracked file was moved byte-for-byte to
`linkage/matlab/reference/professor_original/singleArmDual.m`.

| Property | Recorded value |
|---|---|
| SHA-256 before and after move | `b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f` |
| File type / encoding | UTF-8 Unicode text, no BOM |
| Line endings | CRLF |
| Size | 34,420 bytes |
| Line count | 864 newline terminators; 865 logical numbered lines |
| Mode / modification time | read-only `-r--r--r--`; 2026-07-30 18:00:51 +0800 |
| Git state on receipt | untracked |

Publishing permission is no longer a blocker for the intake documentation.
This audit does not reproduce the preserved source.

## 1. File form

**Facts**

- The file is a MATLAB **script with two local functions**, not a primary
  function or class. It starts with `clear; close all; clc;` and executes
  top-to-bottom (lines 1–838).
- The main execution entry is running the script itself. Parameter definition
  begins at line 9, the simulation loop at line 123, animation at line 333, and
  summary plots at line 666.
- Local functions are `inertia_matrix` (lines 840–851) and `coriolis_matrix`
  (lines 853–865). They are not nested functions.
- All simulation variables are defined in the script. No pre-existing base
  workspace variable is read before definition.

**Inference**

- The script is intended as a self-contained demonstration rather than a
  reusable plant/controller API.

**Unresolved**

- Whether the professor normally runs it directly, from a project folder, or
  with unpublished companion files is not stated.

## 2. Mechanical model

**Facts**

- The modeled patient limb has two planar rigid links and two generalized
  coordinates: thigh/hip angle `th1` and knee flexion `th2` (lines 10–18,
  132–149).
- The state is
  `x = [th1, th2, dth1, dth2]^T` (lines 87–90, 132–137).
- Hip position is fixed at `[0,0]^T`. The thigh absolute direction is
  `[cos(th1), sin(th1)]^T`; the shank absolute angle is
  `th1 - th2` (lines 144–173).
- Positive `th1` raises the thigh above the horizontal bed. Positive `th2`
  denotes knee flexion and subtracts from the thigh angle in the shank absolute
  orientation.
- Human-link parameters are `L1=0.45 m`, `L2=0.40 m`, `m1=8.5 kg`,
  `m2=3.8 kg`, centers at half length, and slender-rod inertias
  `I_i=m_i L_i^2/12` (lines 10–18).
- Two robot-arm interaction points are placed at 55% of thigh length and 50%
  of shank length. Displayed endpoints lie at fixed normal offsets 0.13 m and
  0.12 m (lines 20–32, 158–173).
- Arm 1/2 equivalent stiffnesses are 350/300 N/m and damping values are 25/20
  N·s/m (lines 20–32). Normal force magnitudes are saturated at 500/400 N
  (lines 190–208).
- Coordinates are planar Cartesian `[X,Y]`, with X along the body/bed and Y
  upward away from the bed (lines 339–346).

The two robot arms do **not** have modeled joints, masses, actuator dynamics, or
independent degrees of freedom. They are geometric endpoints and equivalent
normal-force elements.

**Input interpretation**

- There is no external input argument or commanded robot joint vector.
- The plant is driven internally by joint tracking torque, two mapped endpoint
  forces, and a safety torque:
  `tau_total = tau_ctrl + J1^T F1 + J2^T F2 + tau_safety`
  (lines 262–285).

**Unresolved**

- `TODO / needs professor confirmation`: whether `tau_total`, `tau_ctrl`, the
  two endpoint forces, or future robot joint commands should be regarded as the
  intended control input for subsequent work.
- `TODO / needs professor confirmation`: whether the robot endpoints represent
  prescribed poses, compliant attachments, or measured physical end effectors.

## 3. Dynamics

**Facts**

- This is a dynamic rather than purely kinematic simulation. It computes a
  2×2 inertia matrix, Coriolis/centrifugal matrix, gravity vector, generalized
  torque, and acceleration (lines 257–285, 840–865).
- The source uses

  ```text
  M(q) q_ddot = tau_total - C(q,q_dot) q_dot - tau_gravity.
  ```

- With `h=-m2 L1 lc2 sin(th2)`, the coded Coriolis matrix is

  ```text
  C = [h*dth2, h*(dth1+dth2);
       -h*dth1, 0].
  ```

- The coded gravity vector is

  ```text
  tau_g1 = -m1*g*lc1*sin(th1)
           -m2*g*(L1*sin(th1)+lc2*sin(th1-th2))
  tau_g2 = -m2*g*lc2*sin(th1-th2).
  ```

- The arm forces use point Jacobians `J1`, `J2` and are mapped with
  `J_i^T F_i` (lines 175–208, 277–282).
- There is no explicit patient joint stiffness, passive joint damping, bed
  contact, ground reaction, friction, or separate human-interaction force
  beyond the two arm normal-force abstractions.
- Safety behavior includes soft boundary torques, a hip-knee coordination
  torque, velocity clipping, and hard joint-angle clipping (lines 210–255,
  287–303). These are mixed directly into the simulation.
- There are no algebraic solver equations, contact complementarity equations,
  or constraint multipliers.

**Reasonable inferences and risks**

- Because the coordinate comments and kinematics define zero hip angle as a
  horizontal thigh, a gravity torque proportional to `sin(th1)` gives zero
  gravity torque for a horizontal link. That appears inconsistent with the
  usual gravitational moment in the stated X-horizontal/Y-up frame.
  `TODO / needs professor confirmation`.
- The shank absolute angle is `th1-th2`, while the inertia/Coriolis formulas
  resemble a common two-link convention whose second angle is added.
  Sign consistency across kinematics, `M`, `C`, and gravity cannot be confirmed
  from comments alone. `TODO / needs professor confirmation`.
- `tau_gravity` is added to `tau_ctrl` and then subtracted in forward dynamics
  (lines 275 and 285). With exact arithmetic, the same coded gravity term
  cancels. This is consistent with computed-torque compensation but makes the
  simulated response insensitive to errors in that gravity expression.

## 4. Numerical simulation

**Facts**

- Fixed step `dt=0.0005 s`, total time 12 s, and `N=24001` samples
  (lines 60–64).
- Initial state is `[0.02, 0.02, 0, 0]^T` (lines 87–90).
- Acceleration is found by MATLAB backslash `M \ rhs`; there is no ODE,
  optimization, or nonlinear solver call (line 285).
- Integration is labeled and implemented as semi-implicit Euler: update
  velocity from acceleration, clip velocity, then update position from the new
  velocity and clip position (lines 287–303).
- The numerical loop always runs through `N-1`; there is no early simulation
  termination criterion. Q only stops the later animation (lines 132–329,
  650–662).
- Velocity limits are 60 deg/s hip and 80 deg/s knee. Hard joint limits are
  -5 to 85 degrees hip and -5 to 120 degrees knee (lines 34–46, 291–300).

**Inference**

- The very small step and hard clipping appear intended as practical numerical
  and kinematic protection, but no convergence or step-size study is present.

**Unresolved**

- `TODO / needs professor confirmation`: whether clipping is intended as part
  of the physical plant, only a visualization safeguard, or a temporary
  numerical device.
- No tolerance, energy check, matrix-conditioning check, or stability
  assumption is documented.

## 5. Controller

**Facts**

- Comments call it an impedance controller, but the implemented joint-level
  law is computed-torque feedforward plus PD feedback (lines 114–121,
  262–275):

  ```text
  e  = q - q_ref
  de = q_dot - q_dot_ref
  tau_ff = M(q) q_ddot_ref + C(q,q_dot) q_dot_ref
  tau_fb = -Kp e - Kd de
  tau_ctrl = tau_gravity + tau_ff + tau_fb.
  ```

- `Kp=diag(500,400)` and `Kd=diag(25,20)`. Safety gain is
  `diag(200,250)` with a 3-degree activation margin.
- Both hip and knee references are smooth cosines at 0.2 Hz, from 0 to 65
  degrees hip and 0 to 70 degrees knee (lines 48–85).
- State is assumed exactly known; there is no sensor or observer model.
- Feedforward and feedback are evaluated inside the plant simulation loop.
- There is no controller optimization, MPC, adaptive identification, or
  feedforward force command to either robot arm.
- Force saturation, safety torques, velocity clipping, and hard position
  clipping act as safety/protection layers, but joint control torque itself has
  no explicit saturation.

**Inference**

- Plant, controller, safety logic, robot interaction model, logging, and
  visualization are tightly coupled in one script.

**Unresolved**

- `TODO / needs professor confirmation`: physical units and intended actuator
  limits for `Kp`, `Kd`, `K_safety`, and joint torques.
- `TODO / needs professor confirmation`: whether the reference trajectories are
  clinical targets, illustrative trajectories, or test signals.

## 6. Outputs

**Facts**

- Console progress and final summaries report joint ranges, maximum arm forces,
  safety activation count, and maximum tracking errors (lines 123–130,
  323–331, 825–836).
- An interactive animation displays body/link geometry, endpoint paths,
  velocities, forces, references, tracking plots, and joint torques
  (lines 333–664).
- Three final figure windows contain twelve summary subplots plus a separate
  safety/coordination figure (lines 666–823).
- Arrays left in the script workspace include state, references, torques,
  endpoint forces/positions/orientations/velocities, and safety activation.
- The source does not save MAT files, figures, videos, CSVs, or an execution
  log.
- It defines no formal task-success threshold or acceptance metric.

**Risks**

- Several log arrays are initialized to zero but first written at `k+1`.
  Therefore their first sample does not represent the nonzero initial state or
  initial endpoint geometry (lines 87–112, 305–321).
- `constraint_violation_log` records safety-layer activation near a margin, not
  necessarily violation of a hard joint limit.

## 7. Dependencies

**Facts**

- No Simulink model, external file, global variable, symbolic expression,
  optimization routine, Control System Toolbox call, Robotics System Toolbox
  call, or other nonlocal function is visible.
- The script relies on base MATLAB matrix operations and graphics, including
  `yyaxis`, `sgtitle`, `KeyPressFcn`, `drawnow`, and `pause`.
- Local functions in scripts require MATLAB R2016b or newer. `yyaxis` requires
  R2016a or newer, and `sgtitle` is available in modern releases (commonly
  R2018b or newer). A conservative visible-source requirement is therefore
  MATLAB R2018b or newer.

**Portability risks**

- Four trail plots specify four-component `[R,G,B,alpha]` line colors
  (lines 447–456). Support for alpha in line `Color` properties varies by
  MATLAB graphics version; this may be a runtime blocker.
- Unicode Chinese text and the warning emoji require compatible fonts and
  graphics.
- `clear` and `close all` at script start complicate a wrapper that wants to
  preserve caller variables and figure state.

**Unresolved**

- MATLAB is unavailable on the intake machine, so release/toolbox behavior
  could not be checked with `ver` or `license`.
- `TODO / needs professor confirmation`: the MATLAB release and operating
  system used to produce the expected baseline.

## 8. Risks and ambiguities

1. The gravity expression and stated horizontal-zero frame need confirmation.
2. The knee-flexion sign must be checked consistently across kinematics,
   inertia, Coriolis, and gravity terms.
3. Each endpoint is constructed at exactly its desired normal offset, so
   `offset_error1` and `offset_error2` are identically zero apart from roundoff
   (lines 158–173, 190–205). The stiffness term therefore never supplies an
   intentional force; only normal damping remains.
4. Endpoint velocity/force uses the attachment-point Jacobian and omits the
   derivative of the rotating normal offset. It is unclear whether force is
   meant to act at the attachment point or displayed endpoint.
5. There are no robot joint coordinates or endpoint commands, despite the
   dual-arm description.
6. Hard clipping changes the continuous dynamics and can mask controller or
   model instability.
7. Safety activation is called a violation in variable names and reports.
8. Initial log columns are zero rather than reconstructed from the initial
   state.
9. `inertia_matrix` and `coriolis_matrix` accept some unused arguments, which
   may reflect a generic signature or incomplete formulation.
10. Graphics compatibility and the absence of saved outputs make automated
    headless reproduction uncertain.

None of these observations is silently corrected in the preserved source.

## 9. Portability assessment

**Likely straightforward to reproduce**

- Parameter definitions, cosine references, planar forward kinematics,
  Jacobians, 2×2 matrix calculations, piecewise safety torques, clipping,
  semi-implicit Euler, and numeric summaries.

**MATLAB-specific or baseline-sensitive**

- Script/base-workspace execution, local functions after script code, graphics
  callbacks, `yyaxis`, `sgtitle`, animation timing, Chinese font rendering, and
  four-component colors.

**Route assessment**

- MATLAB-first is plausible if the original baseline runs in the professor's
  release and its expected figures/metrics can be captured.
- A hybrid route is plausible later if MATLAB remains the reference oracle.
- A Python port is technically plausible for the numeric core, but porting now
  would risk encoding unresolved sign, gravity, force, and safety assumptions.

No route is selected in this intake.

## Baseline execution evidence

This section records observed execution evidence only. It does not change or
resolve the source-code inferences in Sections 1–9.

### Superseded intake probe

The earlier `which matlab` and `/Applications` probes did not find MATLAB.
That observation was limited to the shell path and `/Applications`; it did not
establish that MATLAB was absent from the machine. The Desktop installation
described below supersedes the earlier execution blocker.

### MATLAB location and version

On 2026-07-30, the requested Desktop search returned:

```text
$ find ~/Desktop -maxdepth 3 -name "MATLAB*.app" -print
/Users/hankli/Desktop/MATLAB_R2025b.app
/Users/hankli/Desktop/matlab/MATLAB_R2025b.app
```

The first path is the actual application bundle and contains the executable
`bin/matlab`. The second path is an empty directory and is not runnable.

The exact version command was:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab -batch "disp(version)"
```

Observed output:

```text
[警告: 目录访问失败: /Users/hankli/Documents/MATLAB]
25.2.0.3042426 (R2025b) Update 1
```

The warning is a MATLAB startup-path warning. It did not prevent the version
probe or the reference execution.

### Exact reference command and preservation check

The successful reference/capture command was:

```text
/Users/hankli/Desktop/MATLAB_R2025b.app/bin/matlab \
  -logfile /Users/hankli/Desktop/coding/adaptive-traction-mpc/linkage/results/local/professor_reference_baseline/console.log \
  -batch "addpath('/Users/hankli/Desktop/coding/adaptive-traction-mpc/linkage/matlab/runners'); run_professor_reference_capture"
```

`linkage/matlab/runners/run_professor_reference_capture.m` is an external
runner. It calls the preserved script with `run`, then captures data after the
script returns. It does not edit, preprocess, or replace any line in the
professor source.

The professor source SHA-256 was checked before and after execution and remained
exactly:

```text
b8c95ab1df3507efd610a3a72057e31a33724626d37341bd5d5a4abaa833c19f
```

No source, parameter, equation, controller, constraint, time step, duration,
solver, or graphics setting was changed.

### Observed execution result

- MATLAB exited with code 0 on the final capture run.
- The numeric loop reached `仿真完成！`.
- The animation initialized, printed its Q-key instruction, ran at the
  source-coded pace, and reached `动画播放完成！`.
- All three expected figure windows initialized and were saved:
  1. `双机械臂仰卧位屈髋屈膝康复训练`;
  2. `双机械臂仰卧位康复训练 - 仿真结果汇总`;
  3. `安全约束与协调性分析`.
- Visual inspection of the three exported PNGs found complete axes, traces,
  legends, Chinese text, and the final animation pose. The four-component trail
  colors, `yyaxis`, and `sgtitle` did not produce a graphics error in R2025b.
- The only warning in the successful console log was the startup-path warning
  for `/Users/hankli/Documents/MATLAB`.
- The preserved script itself raised no runtime error. The final
  `runtime_error.txt` contains `NONE`.

There was one capture-tool incident before the successful run: after the
professor script had completed its simulation, animation, plots, and printed
summary, the external runner referenced an empty error-report variable that the
source's initial `clear` had removed. This was not an error in
`singleArmDual.m`. The ignored external runner was corrected to recreate that
capture variable, and the unchanged professor script was rerun successfully.

The original script's final printed metrics were:

```text
total simulation time: 12.0 s
hip range: 0.0 deg to 65.0 deg
knee range: -0.0 deg to 70.0 deg
arm 1 maximum force: 4.4 N
arm 2 maximum force: 5.3 N
safety-constraint activation count: 0
maximum tracking error: hip 1.16 deg, knee 1.14 deg
```

The captured arrays give the corresponding unrounded values:

| Metric | Observed value |
|---|---:|
| Hip range | 0.000000000 to 64.984906062 deg |
| Knee range | -0.015910729 to 70.004111824 deg |
| Arm 1 maximum force | 4.437117175 N |
| Arm 2 maximum force | 5.345507135 N |
| Hip maximum tracking error | 1.155851439 deg |
| Knee maximum tracking error | 1.144779620 deg |

### Workspace-derived numerical checks

The runner saved 191 numeric/text/struct workspace variables to a MATLAB v7.3
MAT file. MATLAB R2025b then loaded that file successfully for the checks below.
All transition checks cover the 24,000 integration transitions; the initial
zero-filled log column is not treated as a simulated transition.

| Check | Observed value |
|---|---:|
| Arm 1 spring displacement error range | -5.5511151231257827e-17 to 5.5511151231257827e-17 m |
| Arm 2 spring displacement error range | -8.3266726846886741e-17 to 8.3266726846886741e-17 m |
| Arm 1 stiffness normal-force component | -1.9428902930940239e-14 to 1.9428902930940239e-14 N |
| Arm 2 stiffness normal-force component | -2.4980018054066022e-14 to 2.4980018054066022e-14 N |
| Arm 1 damping normal-force component | -4.437117175256356 to 4.372439832855359 N |
| Arm 2 damping normal-force component | -5.345507135192400 to 5.342024600522790 N |
| Coded gravity-vector norm | 0.037562405740526 to 31.557924490804872 N·m |
| Maximum gravity cancellation residual | 1.4654943925052066e-14 N·m |
| Minimum eigenvalue of `M(q)` | 0.065597346526537 |
| Condition-number range of `M(q)` | 13.124517550184029 to 36.083563011945969 |
| Hip/knee/any velocity clipping | 0 / 0 / 0 transitions |
| Hip/knee/any hard angle clipping | 0 / 0 / 0 transitions |
| Hip/knee/any safety-torque activation | 0 / 0 / 0 transitions |
| Source safety-activation log count | 0 |

The stiffness and damping values above are the signed scalar components along
each coded limb normal, before the source's total-force saturation. The
workspace reconstruction also matched the logged arm-force vectors to
floating-point precision.

For the gravity check, the diagnostic reconstructed, at every transition, both
the coded right-hand side with `tau_gravity` added in `tau_ctrl` and subtracted
in forward dynamics, and the algebraically cancelled right-hand side. The
maximum difference was `1.4654943925052066e-14 N·m`, while the coded gravity
vector itself reached `31.557924490804872 N·m`. This is execution evidence that
the coded compensation cancels the coded gravity term to floating-point
precision in this baseline.

Velocity- and angle-clipping counts were reconstructed from each logged state,
logged total torque, and the coded `M`, `C`, gravity, integration order, and
limits. Safety-torque counts were reconstructed from each state using the coded
four safety conditions and were cross-checked against
`constraint_violation_log`.

### Saved local evidence

All runtime artifacts are under the ignored directory
`linkage/results/local/professor_reference_baseline/`:

- `console.log` — successful run console output and warning;
- `commands.txt` — exact locator, version, run, and verification commands;
- `runtime_error.txt` — `NONE` for the successful reference run;
- `workspace_numeric.mat` — load-verified workspace data;
- `numerical_diagnostics.mat` and `numerical_diagnostics.txt`;
- `capture_status.mat` and `verification.log`;
- `figure_manifest.tsv`;
- `figure_01.fig` / `figure_01.png` — final animation window;
- `figure_02.fig` / `figure_02.png` — twelve-panel summary;
- `figure_03.fig` / `figure_03.png` — safety and coordination analysis;
- `run_dynamics_consistency_checks.m` — ignored local numerical-audit runner.

## Dynamics-consistency follow-up

The cleaned capture runner now explicitly restores
`execution_completed=false` after a source runtime error and guards runner
state against the source's initial `clear`. The unchanged professor baseline
was rerun through this runner in MATLAB R2025b and exited 0 with three figures,
a loadable workspace, and unchanged final metrics.

An independent COM/energy derivation, source comparison, deterministic
trajectory/grid checks, and descriptive torque decomposition are recorded in
[DYNAMICS_CONSISTENCY_AUDIT.md](DYNAMICS_CONSISTENCY_AUDIT.md). No source
equation was corrected.
