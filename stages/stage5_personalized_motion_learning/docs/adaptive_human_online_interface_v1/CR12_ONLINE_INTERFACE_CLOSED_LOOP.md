# Full CR12–cuff–Human validation

Nine final online runs pass unchanged mode-aware physical/scientific scoring: constant target 50 ms, far switch at 5/10/20/50 ms, local switch at 5/10/20/50 ms. A scalar task COMPLETE flag alone is not the acceptance criterion. All required true endpoint dwell (≥0.5 s), RETURN (1°/2°s⁻¹ tolerances), phase order, phase/global deadlines, robot torque/speed, Human speed/acceleration/ROM, shank/sleeve clearance, zero shank-table contact, finite native states and reference C2 checks pass. No native physics advances during scientific host catch-up. Original actuation and plant source fingerprints remain unchanged; Human is driven by CR12/cuff interaction only.

| path | J_F N s | F peak N | M peak Nm | duration s | deployable clearance mm | robot cuff peak error mm | physical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old nominal continual | 1236.98 | 115.48 | 15.71 | 15.995 | 6.335 | not collected | PASS |
| new constant 50ms | 904.73 | 125.95 | 18.11 | 11.840 | 6.501 | 0.0425 | PASS |
| new local switch 5ms | 931.79 | 132.55 | 18.11 | 12.100 | 6.515 | 0.0425 | PASS |
| new local switch 10ms | 932.50 | 132.65 | 18.11 | 12.105 | 6.515 | 0.0425 | PASS |
| new local switch 20ms | 934.22 | 132.77 | 18.11 | 12.120 | 6.519 | 0.0425 | PASS |
| new local switch 50ms | 937.27 | 132.42 | 18.11 | 12.150 | 6.522 | 0.0425 | PASS |


| command period ms | first changed receipt task s | reference effect ms | physical difference ms | physical pass |
| --- | --- | --- | --- | --- |
| 5 | 0.505 | 5.000 | 10.000 | PASS |
| 10 | 0.505 | 5.000 | 10.000 | PASS |
| 20 | 0.505 | 5.000 | 10.000 | PASS |
| 50 | 0.505 | 5.000 | 10.000 | PASS |


Constant-endpoint comparison shares identical nominal truth, commissioning, endpoints and causal model inputs. The old controller realizes its native scheduler decisions; the new controller realizes the same endpoint intention continuously. This is an interface-semantics comparison, not a matched motion-speed/algorithm-cost efficacy trial. New reference shaping is faster. J_F drops about 26.86% and duration about 25.98%, while peak force rises 9.07% and peak moment 15.27%. Local switching raises force peak to 132.42–132.77 N, about 14.7–15.0% over old nominal; these are material regressions within the unchanged 200 N / 60 Nm limits. Deployable shank clearance stays about 6.50–6.52 mm and true clearance about 11.80 mm; sleeve gaps remain >4.14 mm. No material minimum-clearance regression is observed in these nominal runs.

Two earlier new-interface attempts abort explicitly because an integration diagnostic required an unowned future sample, then because recertification included an already executed prefix under a current offset. Both remain in results. Their fixes do not relax thresholds. Far switch paths equal the constant control because intermediate intentions were superseded while both trajectories shared saturation; only local switch provides recorded immediate-action evidence.
