# Development Roadmap

[Home](../README.md) · [Overview](overview.md) · [Architecture](architecture.md)

This roadmap describes open development work as of 2026-11-04. It does not
schedule experiments or authorize hardware execution. Individual archived
studies keep their original completion, pause and failure states.

| Area | Current starting point | Next reviewable step |
| --- | --- | --- |
| Stage-5 integration | Source and portable tools exist in the 2026-10-28 archive; `main` contains Stage 1–4 | Select one complete source/model/config closure, audit imports and dependencies, then propose a bounded integration PR |
| Execution timing | Scientific and host-clock studies have different qualification scopes | Define one runtime contract covering feedback service, planning latency, source age, activation, fallback and complete-task behavior |
| Motion generation | Waypoint/quintic scheduling and coordination variants are retained | Separate reference transition effects from closed-loop response; evaluate posture, timing, interaction load and smoothness together |
| Learning–MPC connection | Isolated interfaces and selected learned artifacts exist | Freeze causal inputs/actions and equal-budget baselines; test independent value beyond a strong traditional alternative |
| Reproducible development | Stage package metadata and a platform-specific archive lock are available | Choose a supported platform and document a fresh environment for the selected integration closure |
| Hardware preparation | UR10e surrogate and provisional robot/cuff studies | Resolve geometry, sensing and calibration, then review a non-actuating integration and safety-interface plan |

## Near-Term Priorities

1. **Choose a portable development baseline.** Preserve the archive and review
   only the source/config/model subset needed for the next implementation.
   Do not merge the full archive merely to make Stage 5 appear on `main`.
2. **Make timing part of the design.** Track host latency and rejected/stale
   work alongside task completion. Keep scientific-time and host-time modes
   distinct rather than using offline success as runtime qualification.
3. **Improve useful motion.** A lower force integral alone is insufficient if
   task duration, posture, tracking, moment or smoothness changes unfavorably.
   Inspect complete outbound/HOLD/return behavior under explicit motion bounds.
4. **Give learning a precise role.** Define what it sees, what it proposes and
   how its proposal reaches execution. Preserve strong non-learning controls,
   held-out conditions and negative results before claiming added benefit.

## Decisions Still Open

- Which Stage-5 closure and development environment should be maintained next?
- Which motion and human-model conditions should define the next comparison?
- Which runtime budget and target host are appropriate for the next prototype?
- Which project-wide license can the owner grant after considering ownership
  and third-party notices?
- Which robot/cuff and hardware-safety interfaces are prerequisites for any
  future physical work?

There are no promised completion dates or claims of patient readiness. Hardware
actuation and human testing require separate authorization and validation.

The [archive reproduction guide](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/REPRODUCTION_GUIDE.md)
and [verification record](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/ARCHIVE_VERIFICATION.md)
describe what was retained and checked. The
[next-generation discussion](https://github.com/Block-O2/adaptive-traction-mpc/blob/11af82a7ee35ae3c8e41e4b84d235a494b117d8d/NEXT_GENERATION_ARCHITECTURE.md)
provides hypotheses for future review. These links do not change the original
studies' status.
