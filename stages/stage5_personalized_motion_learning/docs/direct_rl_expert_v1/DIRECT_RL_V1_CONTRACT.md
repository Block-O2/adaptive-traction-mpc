# Direct RL Expert Search v1 contract

Frozen before compatibility probes or training. USER_REQUEST.txt contains the complete authoritative request. DIRECT_RL_V1_CONTRACT.json records gates and SOURCE_FINGERPRINTS.json pins physics, controller, safety, configuration and historical evidence.

Primary score is the existing measured cuff-force integral over a real COMPLETE OUTBOUND/HOLD/RETURN task. Task and safety validity are hard gates. Moment, intensity, duration, clearance and smoothness stay separate. Both conditions are previously studied development cases. CPU MuJoCo and CR12 physical execution remain unchanged.

A continuous 2-D target-change interface must preserve authoritative safety. A failure of expanded-action screening stops main training, as explicitly required by user section 18. Policy rate and reward are not selected before their validation. CUDA is required for main SAC; no CPU fallback. One environment initially.
