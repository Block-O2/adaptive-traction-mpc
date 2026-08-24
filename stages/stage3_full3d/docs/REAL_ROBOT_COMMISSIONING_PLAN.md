# Real-robot commissioning gates

This is a concise engineering sequence, not a clinical protocol or experiment
matrix. A gate advances only after its evidence is reviewed; no threshold is
called clinical.

1. **Connection/state-read only.** Confirm exact robot/controller/SDK identity,
   establish a read-only session, and record state/fault/stop/watchdog fields.
2. **Joint ordering, signs, units and time.** Cross-check every joint against
   the pendant and physical labels; verify radians/rad-s conversions, timestamp
   monotonicity, sequence behavior, latency and feedback rate.
3. **Flange/TCP pose.** Compare reported flange and active TCP poses against
   known physical configurations and independent measurements; resolve all
   base/tool frame conventions.
4. **Zero/disabled path and faults.** Demonstrate that disabled/zero commands
   cannot create motion, then verify documented watchdog expiry, disconnect,
   fault, protective-stop and emergency-stop observation and recovery with the
   manufacturer/integrator procedure.
5. **Unloaded low-speed motion.** Only after independent safety mechanisms are
   active, use the highest-level documented command mode at reviewed engineering
   limits and with no cuff, fixture or person attached.
6. **Software and hardware limits.** Verify command rejection, controller
   limits, workspace limits, stop behavior and logging without borrowing any
   UR10e simulation limit.
7. **Rigid fixture/dummy limb.** Add a low-energy non-human test fixture and
   repeat state, stop, disconnect and bounded-motion checks.
8. **Cuff frame and sensing.** Calibrate and independently verify
   `BASE -> FLANGE -> ADAPTER -> CUFF`; validate any F/T sensor axes, signs,
   zeroing, sampling and saturation with known loads.
9. **Loaded human interaction consideration.** Proceed only after independent
   hardware safety mechanisms, supervision, application risk assessment,
   approved operating procedures and the unresolved cuff-moment question are
   addressed. This plan does not authorize human testing.
