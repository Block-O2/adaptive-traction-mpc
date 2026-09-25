# Rigid-table assembly repair v1 — pre-controller-outcome contract

Evidence category: VERSIONED DEVELOPMENT ASSEMBLY, not fresh qualification.
Historical `fresh_qualification_v1` proposals, acceptance, formal failures, and
integrated-contact diagnosis remain untouched.  The new approved physical
interpretation is a fixed, hard table, a fixed hip, and physically legal
installation variation.  Neither mattress sinking nor tissue compression is
represented by independent negative hip-z displacement.

## Physical and numerical rule

The unchanged Stage-3/5 model has bed plane `z=0.012 m`, proximal thigh capsule
radius `0.050 m`, and nominal hip center `z=0.062 m`.  The capsule starts at
the fixed hip, so `g_proximal = z_hip - 0.050 - 0.012` and no q motion removes
a negative gap.  For this new version only, registered legal installation
heights are `g_proximal ∈ [0.0001, 0.006] m` (0.1–6 mm), with x placement and
other physical variation unchanged.  The upper bound is the original +6 mm
installation bound; the 0.1 mm lower bound is deliberately much smaller than
the existing 2 mm shank static screen, yet strictly beyond floating roundoff
and the nominal tangency that produced a nonzero 195 N simulated thigh force.
It is a setup construction margin, not a new controller clearance threshold,
clinical safety margin, or contact-compliance parameter.  A separate `1e-9 m`
numerical tolerance only classifies computation-scale signed-distance error;
it does not make tangency a valid no-contact installation.  Before full
controller outcomes, static MuJoCo contact checks must confirm this margin
eliminates the initial fixed-overlap load.

For old-case *development counterparts*, a legal existing gap at or above
0.1 mm stays byte-equivalent.  An illegal negative z shift is reflected to an
equal positive installation gap; this preserves its displacement magnitude
and does not collapse all invalid cases onto zero.  A tangency or sub-margin
placement is moved only to +0.1 mm.  The only altered hidden input is
`physical.hip_translation_xz_m[1]`; normal model construction re-derives the
Human transform, cuff target, CR12 initial IK, interface state and physical
commissioning from that new assembly.  No old fitted geometry, beta, residual,
robot q or cuff preload is imported.  These are physically different paired
DEVELOPMENT assemblies, not exact matched-state causal branches.

The versioned validator checks proximal and full thigh/shank capsule signed
gaps over start, goal, commissioning nodes and sampled start↔goal line; actual
MuJoCo initial signed distances include thigh, shank, sleeve, cuff bar,
adapter and articulated CR12 against the table, plus robot-to-Human.  It
records collision masks so excluded pairs are not called protected.  It
separately labels invalid fixed geometry, registered shank-screen failure,
robot initialization/IK-search failure, and dynamically failed control.
MuJoCo plane collision is unbounded although its visual size is finite.  An
IK-search failure is not proof of physical unreachability.

The physical plant, bed/capsule shapes, collision pairs, contact stiffness,
CR12 base and actuators, compliant cuff, Human dynamics, sensor boundary,
controller, estimator, DEV-A recovery, force/motion limits, 100 ms stale-plan
contract, and zero value hook remain unchanged.  `dev_c_bumpless_transfer`
remains `False`; `dev_a_recovery=True`.  Hidden geometry is used only in the
simulator builder and evaluation-side screen, not deployed estimation/control.

Acceptance for *assembly repair* requires no persistent fixed proximal
penetration/load in repaired tested setups, transparent full-assembly checks,
and independent audit.  Moving shank/thigh surface contact is recorded and
interpreted separately; no claim of universally contact-free motion is made.
Controller completion is reported separately and is not an assembly gate.
