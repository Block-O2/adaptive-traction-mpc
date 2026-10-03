# Human Size Contrast v1: parameter and feasibility audit

Synthetic height scaling; not a claim about real adult distributions. Only height changes; body mass 75 kg, passive stiffness [10,10] Nm/rad, damping [5,5] Nms/rad, rest [5,10] deg, cuff fraction .72, scales 1, COM fractions .433/.430, inertia radius fractions .30 and hip offset [0,.0001] m remain fixed. No double scaling.

| height m | thigh m | shank m | cuff m | geometry bounds | beta bounds | shank prior | 120 sampled IK | start contacts |
|---|---|---|---|---|---|---|---|---|
| 1.60 | 0.40640 | 0.37280 | 0.2684160 | True | True | True | 129/129 | [] |
| 1.72 | 0.43688 | 0.40076 | 0.2885472 | True | True | True | 129/129 | [] |
| 2.00 | 0.50800 | 0.46600 | 0.3355200 | True | True | False | 129/129 | [] |

All 3 physical mass matrices have positive minimum eigenvalues over sampled knee 0–125 deg; all inertias positive and triangle-valid (original diagonal [.51 I,I,.51 I]). Compiled shank arrays/site positions verify parameter changes reach MuJoCo; original hip inertial XML declaration retained separately. Robot-base/table/hip placement unchanged.

The static screen checked synchronous OUTBOUND configurations, reverse geometry for RETURN and endpoint for HOLD. It did not execute dynamics, commissioning, HOLD dwell or true RETURN. All 129 samples per height had zero penetrating contacts; sampled minimum robot-table distance about 28 mm. Geometric passage is necessary, not full safety proof.

2.00m shank = .466m > unchanged .460m structural upper bound by 6 mm. Geometry estimator bounds and dynamic beta bounds contain the synthetic truth, but full shank is structurally assumed, not individually identified. This is a prior-domain boundary, not adaptive-control failure.

Existing lower task [20,35] deg was screened before any arm results; its sampled geometry also passed. It cannot repair an anatomy-prior violation, so no common three-height pilot protocol was frozen. Retain 120-degree uncertainty; do not lower targets or expand bounds to produce a win.

Force 200 N, moment 60 Nm and all original ROM/velocity/acceleration/clearance/robot/HOLD/RETURN criteria are retained in JSON limits and frozen scorer. Static checks cannot establish dynamic load limits. No plant setup or production algorithm changed.
