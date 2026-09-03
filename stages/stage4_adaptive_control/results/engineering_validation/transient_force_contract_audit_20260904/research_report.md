# Simulation Engineering Transient Force Contract Audit

This is a simulation-engineering audit, not a clinical safety claim.
Historical artifacts were read only and were not relabeled in place.

## Retrospective classification

| Status | Cases |
|---|---:|
| STRICT_PASS | 66 |
| TRANSIENT_ENGINEERING_QUALIFIED | 1 |
| HARD_PHYSICAL_VIOLATION | 0 |
| NUMERICALLY_UNRESOLVED | 2 |

| Evidence group | Cases | Strict pass | Transient qualified | Hard violation | Unresolved |
|---|---:|---:|---:|---:|---:|
| original_low_medium_rom_validation | 50 | 50 | 0 | 0 | 0 |
| phase5_high_rom_lying_bed | 3 | 2 | 0 | 0 | 1 |
| retained_negative_evidence | 9 | 8 | 0 | 0 | 1 |
| suspended_high_rom | 7 | 6 | 1 | 0 | 0 |

## Fine-timestep confirmation

| Event | Final status | Peak N | Max contiguous ms | Rolling excess impulse N s | Max trailing 20 ms mean N | Open at replay end |
|---|---|---:|---:|---:|---:|---|
| Phase-5 90/120 | NUMERICALLY_UNRESOLVED | 218.441035116 | 4.890122897 | 0.080101114 | 175.877744320 | yes |
| Time-scale 90/120 | TRANSIENT_ENGINEERING_QUALIFIED | 200.352461830 | 0.795996766 | 0.000140208 | 185.086442034 | no |
| Retained PD gain event | NUMERICALLY_UNRESOLVED | 204.130357349 | 0.062376171 | 0.000128818 | see CSV | no exact snapshot |

## Event distributions

| Metric | Count | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| Peak force N | 3 | 200.352461830 | 204.130357349 | 217.009967339 | 218.441035116 |
| Contiguous duration ms | 3 | 0.062376171 | 0.795996766 | 4.480710284 | 4.890122897 |
| Case rolling excess impulse N s | 3 | 0.000128818 | 0.000140208 | 0.072105024 | 0.080101114 |

The registered 218.441 N event is numerically unresolved: its fine
0.25 ms replay satisfies every threshold through the exactly replayable
command interval, but the event is still open at that interval's end and
the snapshot cannot exactly resume the next closed-loop cycle.

The 200.352 N time-scale event closes in its 0.25 ms local replay and
is transient-engineering-qualified. The original strict-gate termination
and incomplete-task conclusion remain unchanged.
The 204.130 N retained PD gain-selection event has no exact replay snapshot
and is therefore unresolved rather than guessed from its single saved spike.

No controller, allocator, Reference Manager, BRAKE, trust, gain, command
limit, or capability-envelope rollout was changed or run.
