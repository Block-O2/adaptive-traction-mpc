# Direct RL environment validation — BLOCKED

No Gymnasium adapter has passed the A–I gates. Main SAC training is forbidden. No new physical rollout was performed.

Eight executable probes reconstructed the first OUTBOUND and RETURN schedules from two frozen VALID NATIVE baseline runs, using the authoritative quintic constructor and sampler. At each requested policy period, reissuing even the same endpoint preserves q/dq but resets reference acceleration to zero. The authoritative rolling splice rejects every such suffix because it joins at the ORIGINAL prefix endpoint. A control suffix starting at that endpoint is accepted, demonstrating that the exception is a boundary-semantic failure, not a general constructor failure.

|Task|Phase|Period ms|ddq jump rad/s²|Endpoint wait s|
|---|---|---:|---:|---:|
|sync_120|OUTBOUND|20|0.076487698|1.575|
|sync_120|OUTBOUND|50|0.181262373|1.545|
|sync_120|RETURN|20|0.076495029|1.575|
|sync_120|RETURN|50|0.181279657|1.545|
|low_ordinary_early|OUTBOUND|20|1.046015050|0.425|
|low_ordinary_early|OUTBOUND|50|2.070380550|0.395|
|low_ordinary_early|RETURN|20|1.041163735|0.425|
|low_ordinary_early|RETURN|50|2.060778329|0.395|

Immediate arbitrary replacement: q/dq-only scheduler cannot preserve ddq. Delayed replacement: the certified old schedule remains active for 0.395–1.575 s in these first-segment probes, so the requested 20/50 ms action cannot take effect. These are reference-time deferrals, not host inference latency. Other segments were not exhaustively probed.

The live handoff validator explicitly requires new ddq = old ddq and also imposes zero new initial ddq. A general acceleration-aware C2 polynomial would fail the zero-initial-ddq predicate. Standard non-handoff activation does not compare the old ddq, so calling that path directly during a moving reference could conceal the discontinuity. Bypassing that check is not an allowed adapter repair.

Sources: human_waypoint_scheduler.py:180; full3d_adaptive_integration_v1/rolling_suffix_splice.py:21; activation_validation.py:144–149 and :212; runtime.py:3140–3152. See SOURCE_EVIDENCE.json for exact file hashes/line excerpts. This establishes a current integration incompatibility, not impossibility of safe direct RL or an observed learned-policy intervention fraction.

User section 18 explicitly requires stopping main training when existing safety is tied to the old action representation. Retaining the same physical/safety thresholds is mandatory. No safety thresholds, physical models, production code, historical evidence, or task endpoints were changed.
