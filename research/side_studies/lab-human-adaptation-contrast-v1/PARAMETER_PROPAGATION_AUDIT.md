# Parameter propagation audit

Seven OFAT fixtures; full original MuJoCo models compiled with zero integration. Compiled mass/inertia/stiffness/damping/ROM/rest/sleeve arrays matched existing HiddenHumanV2 properties.

| condition | thigh mass kg | shank mass kg | thigh inertia kg m² | shank inertia kg m² | K pair | damping pair | sleeve distance m |
|---|---|---|---|---|---|---|---|
| C0 | 7.425 | 4.500 | 0.12754496 | 0.06504647 | [10.0, 10.0] | [5.0, 5.0] | 0.2885472 |
| C1 | 5.940 | 3.600 | 0.10203597 | 0.05203718 | [10.0, 10.0] | [5.0, 5.0] | 0.2885472 |
| C2 | 8.910 | 5.400 | 0.15305395 | 0.07805577 | [10.0, 10.0] | [5.0, 5.0] | 0.2885472 |
| C3 | 7.425 | 4.500 | 0.12754496 | 0.06504647 | [7.0, 7.0] | [5.0, 5.0] | 0.2885472 |
| C4 | 7.425 | 4.500 | 0.12754496 | 0.06504647 | [13.0, 13.0] | [5.0, 5.0] | 0.2885472 |
| C5 | 7.425 | 4.500 | 0.12754496 | 0.06504647 | [10.0, 10.0] | [5.0, 5.0] | 0.2404560 |
| C6 | 7.425 | 4.500 | 0.12754496 | 0.06504647 | [10.0, 10.0] | [5.0, 5.0] | 0.3085852 |

Lengths and COM locations fixed; mass/inertia synthetic scaling only. Inertia diagonal [.51I,I,.51I] follows unchanged builder. Stiffness is not accompanied by damping changes. Cuff changes physical sleeve/site position, not a metadata label. Full truth is retained in JSON only for setup/evaluation. No anatomical population/clinical equivalence claim.
