# Current research and reproduction

## Scope of the next design

The proposed single-rate design would update feasible two-dimensional directions,
project toward minimum interaction force, and use exponential progression and a
double-exponential dynamic waypoint. Controlled stopping is intended to use the
same dynamical system. Recursive safety judgment and finite-time stationary
takeover still require design. No implementation or 200 Hz closed-loop qualification
is claimed for this proposal. Scientific simulation, measured host-clock qualification,
hardware deployment and clinical qualification each need their own evidence.

## Code and offline checks

| Location | Contents and input boundary |
| --- | --- |
| `stages/stage3_full3d`, `stages/stage4_adaptive_control`, `stages/stage5_personalized_motion_learning` | Plant, identifiers, controller, model/configuration assets and tests. The deployment manifests pin the original evaluation code and assets. |
| `deployment/` | Repository and model checks, original B/H150 fixture verification and offline scoring. The root README gives the tested deployment commands. |
| `research/local_studies/ihear_lab_stage1_rt2_v1` and `ihear_lab_stage1_bg_v1` | Frozen B field-by-field scorer and offline governor/replay implementations. Full RT2/BG replay requires access to the matching lab evidence. |
| `research/local_studies/ihear_lab_stage1_fgdw_v1` | Analytical direction law and original interface probes. |
| `research/local_studies/ihear_lab_stage1_fgdw_interface_v1` | Exponential reference, geometry/mechanics certificates and the original interface study. |
| `research/local_studies/ihear_lab_stage1_fgdw_interface_revision_v1` | Matched-B worker, exact reuse, fixture construction and timing diagnostics. The historical gate inputs belong to the study that generated them. |
| `research/local_studies/ihear_lab_stage1{d,e,g,k}_v1` | Supporting mathematical kernels, fixtures, certification and metric code. Only selected implementations are included. |

From the repository root, run the standard-library repository and original
fixture checks:

```bash
python3 -B deployment/verify_repository.py
python3 -B deployment/verify_b_h150.py --config deployment/configs/b_h150_original_v1.json
```

For a full RT2 B rescore, obtain read-only access to both inputs from the lab
archive custodian. Set `RT2_EVIDENCE` to the archived RT2 study directory containing
`B/native/trace.npz`, `B/native/runtime_artifacts.json`, `B/RESULT.json` and
`B_score.json`. Set `B_BASELINE_NATIVE` to the native directory of the matched
Stage1G baseline, with its own `trace.npz`. In an environment with NumPy:

```bash
python -B deployment/verify_rt2_offline.py --rt2-evidence "$RT2_EVIDENCE" --baseline-native "$B_BASELINE_NATIVE"
```

The wrapper invokes the preserved scorer, captures its output in memory and compares
every field against the archived B score. For the historical probes, additional
inputs include BG replay, RT2 aligned windows, the commissioning summary in the
sibling `adaptive-traction-mpc-side-studies` archive, and the earlier stage's gate
packets. Those archive layouts and frozen input hashes must be verified before
replay. The published source preserves the study logic. Six machine-specific input
locators are expressed relative to the checkout or its sibling evidence archive.
Historical closeout scripts and raw study folders are available only within their
retained evidence scope. No complete physical trial is required for these
repository checks.
