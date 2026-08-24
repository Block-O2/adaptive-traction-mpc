# CR12 local hardware/API audit

Audit date: 2026-08-24. This audit used only local repository history and
locally accessible files. No network service or robot was contacted.

## Evidence and classification

`CONFIRMED` means directly established for the laboratory unit by matching
local evidence. `UNKNOWN` means the capability may or may not exist, but the
exact hardware/API evidence is absent. `NOT SUPPORTED` means the inspected
local artifact itself cannot provide that function; it is not a claim that the
physical robot lacks the feature.

Current findings:

- No ROKAE/CR12/xCore/RCI SDK, API reference, controller export, driver,
  library, example, license, or matching hardware manual exists in the current
  repository.
- A fresh filename search under the current `Desktop`, `Documents`, and
  `Downloads` found no matching ROKAE/CR12/xCore/xMate SDK or manual.
- Historical commit `853551d975f8034c0d8f659d01d69ef77cd6024d`
  contains `linkage/docs/ROBOT_INTERFACE_AUDIT.md`. That read-only audit also
  found no matching local SDK or controller identity and stopped at its
  identity gate.
- Historical repository material included
  `assets/robots/cr12_12_pending/urdf/CR12-12.urdf`, SHA-256
  `322071518a7229f31eeb9d4582d4e6725b3c32959f668ede2d1c83839dfe8bd4`.
  It was an Onshape visual export with one link, zero joints, zero inertials,
  zero transmissions, and no control interface. It is not present in the
  reorganized current tree and cannot establish hardware identity or API
  behavior.

## Laboratory capability table

| Question | Status | Local evidence |
|---|---|---|
| Manufacturer | UNKNOWN | “ROKAE CR12” appears in retained project history, but there is no current nameplate, serial number, or purchase configuration. |
| Exact commercial robot model/suffix | UNKNOWN | Historical `CR12-12` filename is not a hardware identity record. Prior audit noted multiple materially different possible products. |
| Controller/cabinet model | UNKNOWN | No controller nameplate, photograph, or configuration export. |
| Installed controller/xCore/HMI version | UNKNOWN | No version screenshot or export. |
| Installed API/SDK and license | UNKNOWN | No SDK package, API manual, release notes, example, library, or authorization record. |
| External joint torque control | UNKNOWN | No matching API evidence. The Stage-3 UR10e torque interface is simulation-only evidence. |
| External joint velocity control | UNKNOWN | No matching API, streaming, rate, interpolation, or watchdog contract. |
| External joint position control | UNKNOWN | No evidence distinguishing waypoint/program execution from streamed external control. |
| Cartesian pose/velocity command | UNKNOWN | No matching external-control API. |
| Cartesian force/impedance command | UNKNOWN | No matching licensed API or parameter/limit semantics. |
| Command/update frequency | UNKNOWN | No controller-specific cycle specification. |
| Joint position/velocity feedback | UNKNOWN | No externally readable state schema, units, ordering, timestamps, or rate. |
| TCP/flange pose feedback | UNKNOWN | No frame definitions or state schema. |
| Measured joint torque/current | UNKNOWN | No signal availability, units, calibration, or API exposure. |
| Flange or external F/T sensing | UNKNOWN | No sensor model, installation photograph, calibration, frame, or data interface. |
| Joint/velocity/torque limits | UNKNOWN | No hardware/configuration export; UR10e and old CR12-like simulation limits are inadmissible. |
| Emergency-stop state access | UNKNOWN | No controller-specific state API. |
| Protective-stop/fault access | UNKNOWN | No fault schema, acknowledgement, reset, or recovery contract. |
| Watchdog/heartbeat | UNKNOWN | No packet, timeout, required rate, or timeout action. |
| Communication protocol/transport | UNKNOWN | No evidence selecting SDK, RCI, TCP socket, fieldbus, or controller-resident program. |
| Disconnect/fault semantics | UNKNOWN | No documented stop category, ramping, latching, or restart sequence. |
| Historical visual URDF as driver/model | NOT SUPPORTED | The artifact has no joints, inertials, transmissions, or control declaration. |
| Repository-provided active CR12 backend | NOT SUPPORTED | This branch intentionally provides only a non-networked dry-run skeleton. |

Therefore, **joint torque control is not confirmed available**. It must not be
selected as the real action space until the exact controller and matching API
explicitly document it.

## Evidence required to resolve UNKNOWN items

1. Manipulator nameplate photograph with complete model suffix and serial.
2. Controller/cabinet and teach-pendant nameplates and photographs.
3. Teach-pendant electronic-nameplate, controller, software-version,
   installed-option and license screenshots/exports.
4. The unit-matched hardware, controller, safety and external-control manuals.
5. Actual SDK/RCI archive, API reference, release notes, examples, supported
   OS/language/ABI matrix, and license/authorization details.
6. State and command schemas with joint ordering, signs, units, coordinate
   frames, timestamp source, update rates and interpolation behavior.
7. Watchdog/heartbeat and communication-loss behavior, including stop category
   and recovery/reset sequence.
8. Configured joint/workspace/velocity/torque/force limits and safety export.
9. Emergency-stop, protective-stop and external safety-I/O state definitions.
10. Any F/T sensor model, mounting location, calibration, frame, sampling rate,
    accuracy and interface documentation.
