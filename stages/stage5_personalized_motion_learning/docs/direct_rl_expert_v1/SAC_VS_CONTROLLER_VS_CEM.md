# Reference inventory — no SAC comparison

Historical measured J_F in N·s; these are frozen references, not new replays. Full force/moment/duration/clearance records with hashes are in JSON. The universal fixed comparator selected by cross-condition coverage is neutral; the preregistered hip-leading fixed comparator is beneficial on sync_120, adverse on ordinary low-ROM. Its ordinary MATCHED result was not timing-isolated. Both are preserved instead of calling the neutral fixed comparator universally strongest.

|Condition|Arm|Controller|Fixed hip-leading|Universal fixed|CEM best-known|SAC|
|---|---|---:|---:|---:|---:|---|
|low_ordinary_early|MATCHED|599.082773|600.505039|599.082773|598.414598|not trained|
|low_ordinary_early|NATIVE|501.521818|510.697915|501.521818|497.020323|not trained|
|sync_120|MATCHED|1529.600078|1488.972118|1529.600078|1465.626365|not trained|
|sync_120|NATIVE|1236.980854|1222.018306|1236.980854|1165.753400|not trained|

No direct RL policy exists. No known-benefit capture, superiority, global optimality, coordination/timing separation or seed reliability is claimed. Future direct comparisons require genuine condition/start/task and timing protocol equivalence; cross-arm minima must not be compared as isolated coordination gains.
