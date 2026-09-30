# Best-known reference search

Absolute matched previous/best costs include ALL prior VALID matched paths, including timing-confounded paths. The previously highlighted timing-isolated reference is retained separately. This prevents claiming improvement over an artificially restricted prior best.

Primary objective is completed-task measured cuff-force integral with hard safety validity. Native and matched scheduling have different achievable costs. The matched learner study is conditional; its reference is never an unrestricted performance limit.

|Condition|Matched previous|Matched best|Native previous|Native best|Matched evals|Native evals|
|---|---:|---:|---:|---:|---:|---:|
|sync_120|1488.972118|1468.421258|1180.562198|1180.000018|64|44|
|variable_start_120|1482.176759|1473.789827|1176.574504|1176.574504|64|44|
|balanced_high|1196.030462|1184.415952|938.997031|936.677211|64|44|
|hip_ordinary|756.721369|756.721369|621.738501|618.076149|64|44|
|low_ordinary_early|592.649264|588.319268|500.513571|499.067101|56|44|
|low_ordinary_late|588.414532|587.790992|501.390874|500.031160|56|44|

Units N·s. Level-wise envelopes retain earlier levels and prior references; an unchanged envelope with sparse/missing evaluations is not a plateau. Restart results, feasibility, completed generation counts, phase timing residuals and descriptors are in the JSON tables.

Directed CEM evaluates real frozen Scientific Simulation. Every rejection remains recorded. Population/restart and finite wall-time budgets limit coverage; no lower bound or global-optimality evidence is claimed. Level 4 was not exercised in this bounded campaign. Separately independently confirmed offline-Q-selected paths can update the best-known table; they are labelled as non-CEM discoveries and do not change the CEM-only convergence/complexity curves.

New winning paths are independently re-executed from their exact frozen discovery starting state. Deterministic agreement does not establish Human-subject generalization. Native cost changes are not called timing-isolated coordination gains.
