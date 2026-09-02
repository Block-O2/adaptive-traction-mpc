# Phase-A High-ROM Interaction Diagnosis

Status: engineering diagnosis, not formal or authoritative scientific evidence.
This audit does not establish physiological or clinical realism, choose a new
force margin, or redesign the controller.

## Checkpoint and scope

The existing Phase-5 engineering pilot and its unfavorable outputs were
committed unchanged as `5d7af7a` (`record integrated high-rom pilot`). Phase A
is left uncommitted on `codex/high-rom-interaction-audit`.

The preserved Phase-5 `knee_high_folding_90_120` trace was the primary source.
An instrumented deterministic reconstruction stopped at the same force gate and
matched all 16,047 saved physical cuff-force norms exactly (maximum absolute
difference `0 N`). Short replays then restored the captured pre-event MuJoCo
integration state and held the same already-issued joint-torque command. No new
full High-ROM pilot was run.

## Scenario contracts

The exact contracts are defined in
[`STAGE4_PHASE_A_HIGH_ROM_SCENARIOS.md`](STAGE4_PHASE_A_HIGH_ROM_SCENARIOS.md).

- `lying_bed` is the unchanged default: thigh and shank retain the existing
  unilateral frictional contact with the fixed bed plane.
- `suspended_seated_like_high_rom` is opt-in: the same bed remains visible but
  its collision type and affinity are zero, so it supplies no thigh/shank
  support. No replacement seat, strap, backrest, or other contact is invented.

Human dynamics, high-ROM limits, fixed hip pivot, controller, allocator, rigid
cuff mechanics, robot model, and 140 mm engineering adapter are unchanged. The
second scenario is only a contact counterfactual, not a seated-person model.

## Exact 90/120 event

The command was issued at `t=16.045 s`; the saved event sample is
`t=16.046 s`, on the 1 kHz physics grid.

| Quantity | Value |
|---|---:|
| Executable force, world `[x,y,z]` | `[-123.422149, 3.611229, 157.333824] N` |
| Executable force norm | `199.9999999996 N` |
| Physical cuff force, local `[x,y,z]` | `[-177.220440, 44.674373, -119.639466] N` |
| Physical cuff force, world `[x,y,z]` | `[-210.871768, 44.752336, -35.310219] N` |
| Physical cuff force norm | `218.441035 N` |
| Physical norm minus command norm | `+18.441035 N` |
| Physical-minus-command vector, world | `[-87.449620, 41.141107, -192.644043] N` |
| Vector residual norm | `215.526690 N` |
| Command/physical force direction angle | `61.818644 deg` |
| Executable moment norm | `43.478831 Nm` |
| Physical cuff moment, local `[x,y,z]` | `[20.941224, -49.288471, -1.283546] Nm` |
| Physical cuff moment norm | `53.568048 Nm` |
| Safety Filter | `SAFE_FILTERED`, lambda `-50.064586` |
| Filter force / moment intervention | `50.064586 N` / `18.131230 Nm` |
| Reference Manager alpha | `0.5` |

The large vector residual is reported using the repository's stored world-frame
command and reconstructed physical-wrench sign conventions. It must not be
collapsed into the much smaller norm-only difference.

At the event, MuJoCo directly reported Human `q=[59.488842, 84.111476] deg`,
`dq=[-20.205689, 14.752921] deg/s`, and
`qdd=[1388.652016, -2290.828690] deg/s^2`. Robot state was
`q=[-52.241100, -42.249770, 87.242914, 29.351386, -109.143544,
-40.421814] deg`, `dq=[0.582378, 13.636548, 0.642855, -38.180967,
-24.033938, -8.437731] deg/s`, and `qdd=[-361.620926, -1454.306328,
468.071486, 3707.135989, 2594.701426, 1178.641059] deg/s^2`.

The preserved trace alone contains no full-rate Human `dq` or any `qdd`; its
finite-difference values are retained only as derived diagnostics. The values
above come directly from the exactly reproducing instrumented MuJoCo replay.

## Duration and decomposition

The preserved run contains one over-limit 1 ms sample because the gate stops at
the first event. Continuing only the same already-issued command from the saved
state kept the physical force above 200 N at all five 1 ms samples of the full
5 ms control interval, ending at `215.979323 N`. With a 0.5 ms physics step it
was above 200 N at all ten samples and ended at `215.786543 N`. Thus the event
is sustained for at least that command interval; it is not merely one isolated
physics sample.

Across the instrumented last 50 ms, the world-vector residual norm had
mean/RMS/p95/range `95.4866/109.9882/200.5840/[18.5407,215.5267] N`.
The signed norm residual (physical norm minus command norm) had
mean/RMS/p95/range `-13.0054/31.5004/25.5097/[-82.0565,26.1009] N`.
Across the entire preserved trace, the signed norm residual had
mean/RMS/p95/range `-1.6215/6.8847/1.9154/[-112.8343,26.1009] N`.

The command force norm remained 200 N from the preceding control interval, but
its vector changed by `[-23.722222,-0.249993,-16.001157] N`. Command moment
norm changed from `26.364483` to `43.478831 Nm` (`+17.114348 Nm`). In the same
step, physical force changed by `[-30.621185,0.874839,-32.244652] N` in world
coordinates, physical moment changed by `[1.421214,-16.760950,-0.837635] Nm`,
and Human acceleration changed by `[+194.151830,-167.410297] deg/s^2`.
The six equality multipliers changed materially, while weld reconstruction
residuals remained negligible.

## Bed, timestep, and solver sensitivity

The event and immediately preceding sample had zero bed force and no active
contacts. The preserved preceding 50 ms nevertheless contained eight material
bed-contact samples and a peak bed force of `840.228335 N`; this is evidence
that the lying scene affects the approach history.

From the exact same pre-event state and command, disabling bed contact changed
the spike onset by `0 N`. A later contact within the 5 ms lying replay changed
force norm by at most `3.221840 N` and moment norm by at most `0.514087 Nm`, but
did not create or remove the over-200 N interval. This same-state result does
not claim that a full suspended trajectory would reach the same state.

Halving the timestep changed the 5 ms endpoint by `-0.192780 N` and did not
remove the excursion. Increasing solver iterations from 100 to 200 or tightening
tolerance from `1e-8` to `1e-10` changed the endpoint by exactly `0 N`; the
recorded solve used one iteration and emitted no MuJoCo warning. The evidence
therefore does not support a solver-accuracy artifact classification.

## Classification and safety implication

Primary classification: **C — genuine closed-loop interaction amplification**.

The crossing begins without active bed contact, survives removal of bed contact
from the same state, persists across the full command interval, and is
insensitive to the tested solver settings and smaller timestep. It coincides
with a changed 200 N command direction, a large filtered moment, a jump in rigid
weld equality force, and already-large Human/robot acceleration. Preceding bed
contacts and the 140 mm adapter remain setup-specific secondary factors; their
full-history causal contribution was not isolated, so this is not a claim of
general behavior outside the audited event.

The filter's `18.131230 Nm` moment intervention participates directly in the
`43.478831 Nm` executable moment. The 140 mm adapter maps the event command
force to a `27.995249 Nm` lever moment about the flange and therefore
participates in robot joint loading, but no adapter ablation was authorized, so
its independent causal share is unresolved.

The physical cuff moment reached `53.568048 Nm`. The evaluation-only cylindrical
surface proxy reached a maximum local patch force of `125.961740 N`, versus
`109.595828 N` for the command wrench. These are mathematical equivalent-load
proxies, not pressure, comfort, or tissue-load measurements.

A fixed `200 N - margin` command budget is not supported by this single event:
the required margin is state-, direction-, acceleration-, moment-, constraint-,
and potentially contact-dependent. No new margin is selected. Future safety
design should include actual measured interaction wrench in the low-level
safety/compliance loop, with validated sampling, latency, force rate, moment,
surface-load proxy, and contact confidence, while retaining the executable
command budget as an independent guard.

The recommended next architecture step is a separately approved measured-wrench
low-level safety/compliance specification. Phase A does not implement it and
does not change the Reference Manager, MPC objective, BRAKE recovery, or task
relaxation.

## Replay snapshot and artifacts

`pre_spike_replay_snapshot.npz` stores the MuJoCo `mjSTATE_INTEGRATION` state,
Human/robot state and acceleration, incumbent base model, geometry estimate,
current action/allocation, and previous safe force/moment/joint command.
`pre_spike_replay_snapshot.json` stores the command components, Reference
Manager state, incumbent/trust state, MPC configuration and RNG state,
supervisor state, and exact physical diagnostics.

This is sufficient for exact physical replay of the already-issued
`16.045-16.046 s` event interval, as verified to floating-point precision. It
does not serialize measurement-layer filter/RNG histories, so it is not claimed
to resume a new closed-loop controller cycle after `16.050 s` exactly.

Machine-readable outputs are under
`results/engineering_validation/phase_a_high_rom_interaction_audit_20260902/`:

- `phase_a_summary.json` and `diagnosis.json`;
- `preserved_trace_audit.json` and `reconstruction_check.json`;
- `instrumented_event_window.json` and `sensitivity_summary.json`;
- `pre_spike_replay_snapshot.npz` and its JSON manifest.

