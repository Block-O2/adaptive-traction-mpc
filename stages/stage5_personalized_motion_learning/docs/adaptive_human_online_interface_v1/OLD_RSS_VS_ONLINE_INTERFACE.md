# Old/new action freedom comparison

48 matched high-level intention streams: sync_120/low-ROM × OUTBOUND/RETURN × 5/10/20/50 ms × identical/switch/reverse-alternating. The OLD comparator is reconstructed endpoint-bound ownership from the original saved schedule, with deferred effect at its endpoint; this is not a new old-RSS physical replay of every changed stream. NEW uses the same input intentions and current model safety screens. Status counts: {'IDENTICAL_CONTINUATION': 2076, 'ACCEPTED': 192}; all active handoffs explicitly compare q/dq/ddq.

| stream family | streams | realized lead sign changes | changed command acceptances |
| --- | --- | --- | --- |
| identical | 16 | 4 | 0 |
| switch | 16 | 16 | 96 |
| reverse_alternating | 16 | 14 | 96 |


The old represented suffix remains deferred until the inherited endpoint for 45.45–100% of commands, depending on period/context. That minimum-endpoint calculation is a representation-level deferral bound, not measured old actual acceptance/rejection after the endpoint. New changed-command reference effects range 5–60 ms in these streams, with no rejected targets in this bounded set. Explicit ROM bounding is in the stream generator; adversarial out-of-ROM rejection is tested separately. Lead sign change means a sign reversal of cumulative hip-minus-knee displacement relative to the stream origin; it is a reference metric and does not prove the same physical lead-switch count. Identical paths can naturally cross that metric too (4/16).

| path | J_F N s | F peak N | M peak Nm | duration s | deployable clearance mm | robot cuff peak error mm | physical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old nominal continual | 1236.98 | 115.48 | 15.71 | 15.995 | 6.335 | not collected | PASS |
| new constant 50ms | 904.73 | 125.95 | 18.11 | 11.840 | 6.501 | 0.0425 | PASS |
| new local switch 5ms | 931.79 | 132.55 | 18.11 | 12.100 | 6.515 | 0.0425 | PASS |
| new local switch 10ms | 932.50 | 132.65 | 18.11 | 12.105 | 6.515 | 0.0425 | PASS |
| new local switch 20ms | 934.22 | 132.77 | 18.11 | 12.120 | 6.519 | 0.0425 | PASS |
| new local switch 50ms | 937.27 | 132.42 | 18.11 | 12.150 | 6.522 | 0.0425 | PASS |


The table gives actual full physical force/moment/completion for the equivalent constant endpoint intention and separately tested local-switch sequence. Force outcomes for all 48 reference streams were not simulated; OLD force outcomes for changed streams remain unmeasured. Thus immediate richer legal reference realization and actual local-switch influence are supported, but a complete paired physical efficacy matrix is not. No conclusion about historical small optimization gain, SAC, PPO or TQC is drawn.
