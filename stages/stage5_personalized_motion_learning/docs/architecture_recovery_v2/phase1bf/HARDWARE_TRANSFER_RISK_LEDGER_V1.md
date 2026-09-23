# Phase 1B-F Hardware-Transfer Risk Ledger V1

Status: **SIMULATION FREEZE INPUT ONLY — NOT HARDWARE READY**

| Risk | Current evidence | Transfer consequence |
|---|---|---|
| Cuff moment semantics | Peak 50.24 Nm is a WORLD-frame free sagittal moment at the modeled cuff reference point | It is not an OnRobot HEX sensor-frame moment; sensor offset adds `r x F` and frame rotation |
| Force semantics | Peak 159.89 N is commanded/allocated cuff wrench, dominated by probing | Not a measured contact force, pressure, comfort, tissue-load, or safety result |
| Narrow probe clearance | 5.205 mm in combined qualification; 3.955 mm in retained 96-case audit | Model/frame/compliance error could erase the margin |
| Simplified collision model | Flat bed plus analytical shank capsule only | Omits thigh/body/cuff collision, bed compliance and contact dynamics |
| Ideal cuff twist | Noiseless twist is available to state estimation and settle logic | Real sensing/filter delay may corrupt ddq and online identification |
| Model authority switching | Up to 13 conditional-frozen-set transitions and nine increment sign reversals; beta remained bounded | Noise could increase switching/chattering; needs noisy-sensing validation |
| Near mass floor | Minimum accepted predicted mass margin 0.030384 vs 0.03 floor | Small modeling/numerical margin; must be stress-tested under noise and discretization |
| Robot abstraction | Human-space generalized action only | No CR12 reach, joint torque, collision, bandwidth or real-time validation |
| Physical calibration | Generator uses hidden bed/anatomy truth for evaluation | Deployment needs measured bed plane, frames, anthropometry/bounds and certified planner |
| High-ROM scope | Validated high goals q1 68.46–74.21 deg, q2 82.18–92.11 deg under verified q1<=80/q2<=100 plant | 120–130 deg claims require a separately verified physical/model ROM; current plant cannot support them |

The current force and moment gates remain unchanged at 200 N/60 Nm. Zero
force/moment objective weights mean these are feasibility gates, not an
optimized comfort or hardware-load objective. No current result supports
hardware, clinical, or patient-safety claims.
