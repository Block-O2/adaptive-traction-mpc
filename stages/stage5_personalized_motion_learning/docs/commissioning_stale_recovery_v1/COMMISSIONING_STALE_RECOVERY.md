# COMMISSIONING stale-command recovery — read-only architecture gate

**Status: `COMMISSIONING_RECOVERY_ARCHITECTURE_NOT_JUSTIFIED`.** The requested moving-commissioning recovery cannot be made a bounded local retry using the existing execution primitives. No production code, config, scorer, task, safety threshold or scientific assumption was changed. No new MuJoCo run was started. The previous 49-case failure remains FAIL.

## Exact failed command

The failed payload was a per-5 ms loaded CR12 `TRACK` torque command, not a commissioning planner future or identification result. It followed segment 2 of the low-ROM commissioning rest-to-rest quintic. At source sample **4.095 s**, reference q/dq/ddq was `[0.3533334137392453, 0.42858419664082886]` rad / `[0.10804731927358313, -0.06966723447095992]` rad/s / `[-0.2782151155627292, 0.17938878835296337]` rad/s². The Human estimated q/dq was `[0.35831450988035973, 0.4542691773378806, 0.12217345689083284, -0.09334670433929758]`; simulation truth is separately recorded for evaluation only in `ROOT_CAUSE_RECONSTRUCTION.json`. CR12 q/dq and the six commanded torques are there as well. Human, CR12 and reference velocities were all nonzero.

Source capture host ns `1295201270309666`; command construction finished `1295201311362583`; command ready `1295201311434750` (**41.125 ms** after capture); effective grid activation would have been `1295201311559666`. The write guard rejected it before plant write once age exceeded 100 ms. The exact rejection clock was **not logged**; it must be later than `1295201370309666` ns. The last commissioning selection request had already finished and activated at age 5.687 ms; there was no worker future for this 5 ms command.

Prior receipt `803` remained the active applied command. `WallPhysicsSession` advanced old control while catching up; the failed attempt progressed physics from 4.0975 to 4.1362 s and never wrote the stale torque. The exception rose through `_execute_interval` and the commissioning loop to the case runner, yielding TASK_FAILURE. This is not a setup nonstart.

## Recovery gate

The stationary hold case does not apply. The commissioning quintic ends at rest, but during this failure it was still moving. Continuing old control until its endpoint, or simply catching the exception and retrying, would violate the requested moving-case safe-stop and fresh-observation boundary.

The existing Safe Fallback latch and certified braking suffix are created only for High-ROM TASK pass-through **after** commissioning fit and belief creation. They do not cover this low-ROM commissioning segment or arbitrary mid-segment nonzero ddq. The loaded `BRAKE` supervisor computes a reactive candidate from a new observation; it is not a prevalidated commissioning stop, has no bounded hold-to-fresh-retry transition, and cannot execute independently during a host stall. A valid repair would require a new prevalidated moving-commissioning stop/hold path with C2 stitching and an execution path that remains available when command construction is late. That exceeds the task's one local recovery implementation boundary and cannot be claimed by changing exception plumbing alone.

A separate audit finding: the command pre-write guard currently compares **>100 ms**, whereas the requested prohibition is **>=100 ms**. The exact-boundary behavior is untested for commissioning commands. No threshold was changed.

## Stopped work

No recovery implementation or local repair was attempted; deterministic and controlled 0/100/150/200 ms delay tests were not run. No representative regression or fresh 49-case v2 was preregistered or run. No 30-repeat, value learning, RL, fresh qualification, hardware actuation, or Auditor call. Historical runtime and functional FAIL artifacts remain unchanged. ACCOUNT-WIDE quota: 30% at start and last check.
