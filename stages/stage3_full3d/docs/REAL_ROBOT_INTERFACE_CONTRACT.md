# Hardware-independent robot execution contract

This is a software boundary, not an active CR12 driver. The controller consumes
`RobotState` and emits an explicitly validated `RobotCommand`; a backend owns
all robot-specific state decoding and command dispatch.

## State contract

`RobotState` contains:

- backend-monotonic timestamp and monotonically increasing sequence;
- joint position in radians and velocity in radians/second;
- `BASE_FROM_FLANGE` and `BASE_FROM_TCP` framed poses in metres;
- the 6-by-N TCP geometric Jacobian, mapping rad/s to `[m/s, rad/s]`, with
  wrench dual ordered `[Fx,Fy,Fz,Mx,My,Mz]`;
- optional measured joint torque in N m and motor current in A;
- optional framed TCP F/T wrench in N and N m;
- explicit robot mode, fault code, and watchdog state.

Optional fields remain absent when unsupported. Commanded actuator effort or a
simulation constraint wrench must never be mislabeled as a measured hardware
signal.

## Command contract

`CommandMode` keeps these modes distinct:

- `DISABLED`;
- `JOINT_POSITION` in radians;
- `JOINT_VELOCITY` in radians/second;
- `JOINT_TORQUE` in N m.

Every command includes its mode, vector, monotonic timestamp, deadline,
enable request, and immutable software-limit result. A backend rejects:

- an unconfirmed/unsupported mode;
- wrong dimensions, nonfinite values, or absent documented limits;
- values outside the applicable mode limits;
- motion without an explicit enable request;
- future, expired, or otherwise invalid timing;
- commands while disconnected, faulted, stopped, or watchdog-expired.

Capability metadata is backend-specific. Simulation torque support does not
promote CR12 torque support. The CR12 dry-run skeleton reports every motion mode
`UNKNOWN` and has no transport object or transmission method.

## Timing and watchdog

Timestamps and deadlines share one backend-owned monotonic timebase; wall-clock
time is not used for command validity. The Stage-3 simulation defines a local
20 ms watchdog solely to test expiry semantics. The real watchdog remains
`UNKNOWN` until its controller documentation specifies timing and timeout
action. Simulation timing must not be copied into hardware.

## Calibrated frame chain

The replaceable calibration object is:

```text
BASE_FROM_CUFF
  = BASE_FROM_FLANGE
  * FLANGE_FROM_ADAPTER
  * ADAPTER_FROM_CUFF
```

The Stage-3 simulation explicitly injects its Menagerie flange-to-attachment
site definition and provisional identity `ATTACHMENT_FROM_CUFF`. No controller
logic owns or assumes that identity. A CR12 backend requires a supplied
`FrameCalibration` with provenance and has no implicit default.

Before loaded hardware testing, measure and record:

- robot base pose in the laboratory/world reference;
- controller-defined mechanical flange and active TCP frames;
- flange-to-adapter geometry;
- adapter-to-cuff centre and orientation;
- F/T sensor origin, axes, sign and tool/load compensation;
- uncertainty/repeatability and the calibration date/tooling/configuration.

The measured chain must be independently checked with physical fiducials or a
calibrated metrology procedure before it is used for interaction control.
