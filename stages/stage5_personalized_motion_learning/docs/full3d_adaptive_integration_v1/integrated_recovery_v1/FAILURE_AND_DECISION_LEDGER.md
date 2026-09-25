# Failure and decision ledger

## Entry: integrated baseline

Historical evidence preserved: fresh three arms 0/24; DEV-A 24 commissioning,
15 task entries, 2 completions; DEV-B causal local dynamics switch; DEV-C v2
four matched local passes but old-24 still 2 completions, later output-step
violations; DEV-C v3 first-edge refusal at zero action step / 5.059 N desired
force step; unresolved 33.35 kN bed-thigh contact. Versions are not pooled.

Initial falsifiable mechanics hypothesis from source inspection: the varied
hip z offset can lower the fixed hip-centered proximal thigh capsule sphere
below the unchanged infinite bed plane. Because that sphere center is the
fixed hinge, changing task q cannot remove its vertical overlap. This is a
hypothesis until contact geometry/constraint/force is independently recomputed.

## Mechanics V1 — hypothesis confirmed; not a controller cure

Static actual-MuJoCo audit: exactly 11/24 admitted cases have negative fixed
proximal sphere gap. Strongest -4.819128 mm matches the hidden hip shift, at
initial state and every static q1=0/5/15/40/80 deg. Same checkpoint force
rotation and mj_applyFT match qfrc_constraint [15.363881,0] Nm; normal Jacobian
is effectively zero. Unit/frame/extraction-error hypothesis rejected for this
record. A fixed-hinge/capsule/bed setup issue is supported.

Three real-physics prefix replays retain original wait intervals and produce
identical final integration states. Strongest thigh contact starts at t=0,
lasts all 7.025 s and yields 234306.898 N s normal impulse. Ordinary has no
thigh contact, nominal has intermittent grazing contact; both have transient
shank contact. Thus not every contact is the same, and not every failure is
explained by proximal overlap. Independent Auditor recomputed the raw metrics.

Decision: no unique documented assembly repair is supported. Moving hip,
changing proximal collider, adding pelvis motion, changing bed or rejecting
negative z setups introduce distinct physical/domain assumptions. No arbitrary
choice is made and no current-domain qualification is claimed. New campaign
terminal status BLOCKED_MECHANICS_OR_DEPLOYMENT_INFORMATION.

## Diagnostic tooling and figures

First diagnostic launch hit installed MuJoCo mj_fullM signature mismatch;
changed diagnostic call to `(model,data,dst)` and reran successfully. This is
not a physical/scientific failure. The initial plotting autoscale obscured the
constant 33.35 kN level; new `review_v2/` uses a zero-origin y axis. Original
`review_v1/` remains; numerical results are unchanged. No failed physical
run was discarded or replaced.
