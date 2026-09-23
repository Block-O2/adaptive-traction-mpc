# Phase 1B Mechanics Provenance V1

## Separation of responsibilities

The deployable adaptive controller is not given simulation-truth anatomy or bed
geometry. It receives the measured cuff observation/history and the supplied
Human-joint reference/task. The simulation-only generator may use hidden truth
to construct and evaluate a mechanics-valid study population, exactly as it may
use hidden truth to generate plant dynamics.

For a future physical deployment, the source of a clearance-certified task is
an upstream session setup/calibration process, not the adaptive controller:

| Quantity | Simulation-study source | Intended deployment source | Controller access |
|---|---|---|---|
| Bed plane/height | `HIDDEN_ORACLE` in generator/evaluation | `MEASURED` during bed/session setup | Not required for tracking the certified reference |
| Full shank length | `HIDDEN_ORACLE` in generator/evaluation | `MEASURED/CALIBRATED` anthropometry or conservative registered bound | Withheld from adaptive model; individual length is not inferred from cuff kinematics |
| Hip/leg placement | hidden continuous setup | not assumed known; effective cuff geometry is `ONLINE_ESTIMATED` | Effective geometry only |
| Cuff attachment | hidden continuous setup | not assumed known; effective knee-to-cuff distance is `ONLINE_ESTIMATED` | Effective distance only |
| Pre-probe generator reference screen | `HIDDEN_ORACLE` evaluation of the hypothetical reference beginning at hidden initial state | upstream proposal screen only; not a certificate of the post-commissioning reference | Never used for action selection |
| Exact post-probe constructed-reference clearance | `HIDDEN_ORACLE` evaluation-only audit of the arm-specific reference beginning at estimated handoff state | upstream mechanics-valid task planner must certify the exact issued reference | Supplied task/reference, not anatomical truth |
| Actual simulated clearance | `HIDDEN_ORACLE` evaluation | requires an independently validated physical safety layer before hardware use | Never used for simulated action selection |

This split does not claim that the present simulator implements the future
physical calibration workflow. It freezes the scientific boundary: Phase 1B
distinguishes proposal screening from certification of the exact issued
post-commissioning reference, while actual hardware clearance assurance remains
an explicit transfer limitation. Evaluation-only instrumentation and formal
adaptive/oracle zero-violation gates now exist for the exact constructed
reference, but no new campaign was executed after the contract-budget stop.
Phase 3 was not entered.

## Versioned bounded knee-led task

`knee_led_clearance_constrained_v1` is not a silent reinterpretation of legacy
`knee_lead`.

- Outbound duration: 40% of total task duration.
- Hold: 12%.
- Return: 40%.
- At 52% of outbound time, normalized hip progress is 0.65 and normalized knee
  progress is 0.72.
- Both joints move during both outbound segments.
- Return traverses the same midpoint in exact reverse segment order (48%, then
  52% of return duration).
- Each segment uses a quintic with zero endpoint velocity and acceleration.

The `0.07` normalized knee-progress lead is deliberately the smallest tested
nonzero lead. The proposal audit showed that stronger tested leads did not
improve endpoint-limited clearance, while they require higher reference speed.
