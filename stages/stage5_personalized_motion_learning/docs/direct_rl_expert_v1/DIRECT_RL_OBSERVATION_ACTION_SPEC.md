# Proposed observation/action spec — NOT IMPLEMENTED

Action: float32 Box[-1,1]^2, independent hip/knee target changes at 20 or 50 ms. A candidate design maps each coordinate to a bounded target increment using registered per-joint motion limits and maintains the executed target. Independent signs/magnitudes allow synchronous, hip-leading, knee-leading, pause, catch-up, and distinct phase coordination without H1–H4/lattice projection. Exact scale is NOT selected. This expressivity has not been validated physically.

Zero requests no target change; it is not a claim that the Human or CR12 stops immediately. A conservative completion policy must still demonstrate outbound arrival, real HOLD dwell and RETURN settling.

Proposed normalized causal actor groups: estimated Human q/dq; receipt-owned q/dq/ddq reference; measured cuff force/moment; robot joint state and command state needed to realize reference; phase; original start/goal; normalized estimated progress; sensor-supported remaining time; previous RAW and EXECUTED action; deployable estimated geometry/dynamics belief, confidence, validity and source age. Use immutable observation-ready snapshots and fixed physical scales or training-only running normalization frozen at evaluation. Feature dimensions/scales await implementation audit. No RNN or history stack selected.

Excluded: physical-case hidden parameters, evaluation-only Human state, future state/wrench, oracle geometry, reference-winner identity, rewards or evaluation labels as actor inputs. Historical case/checkpoint ids remain reproduction metadata only.

Constraints to retain: registered Human ROM, task q bounds, velocity/acceleration, CR12/interface feasibility, continuous nonpenetrating clearance, causal source ages, phase deadlines, completion boxes and real HOLD/RETURN. Same official evaluator. v9 reference velocity fraction 0.5 and acceleration fraction 0.25 are conservative execution/pacing choices, not fundamental plant limits; they remain frozen for this attempted workflow and are disclosed separately.

Old planner preferences: candidate lattice, normalized coordination directions, maximum waypoint fraction, monotonic-progress candidate rejection, waypoint ranking penalties, endpoint-only action activation, zero-initial-ddq schedule convention. Do not relabel those preferences physical laws. The action design should remove the lattice/pattern preference, but the authoritative activation/escape certificates currently depend on the old segment contract. No preference or safety check was removed in this run.

Required next interface work: versioned current-q/dq/ddq reference origin; explicit raw proposal -> full polynomial safety certificate -> accepted/rejected command; safe fallback on rejection; log both raw/executed actions and exact rejection reason; verify causal clearance, mechanics, terminal/time/fallback validity through the same CR12 CPU-MuJoCo pathway before any reward or training gate can pass.
