# Original blocker retest

16/16 pass all criteria. Reconstructed original saved moving quintic states for sync_120 and low_ordinary_early, OUTBOUND/RETURN, 20/50 ms; extended to 5/10 ms. The inherited nonzero acceleration is carried unchanged into OTG. Original eight historical artifacts are immutable.

| condition | phase | period ms | nonzero initial ddq rad/s² | changed effect ms | old endpoint s | all criteria |
| --- | --- | --- | --- | --- | --- | --- |
| sync_120 | OUTBOUND | 5 | 0.01963, 0.01184 | 5.000 | 1.595 | True |
| sync_120 | OUTBOUND | 10 | 0.03892, 0.02350 | 5.000 | 1.595 | True |
| sync_120 | OUTBOUND | 20 | 0.07649, 0.04632 | 5.000 | 1.595 | True |
| sync_120 | OUTBOUND | 50 | 0.18126, 0.11075 | 5.000 | 1.595 | True |
| sync_120 | RETURN | 5 | -0.01963, -0.01184 | 5.000 | 1.595 | True |
| sync_120 | RETURN | 10 | -0.03892, -0.02350 | 5.000 | 1.595 | True |
| sync_120 | RETURN | 20 | -0.07650, -0.04632 | 5.000 | 1.595 | True |
| sync_120 | RETURN | 50 | -0.18128, -0.11075 | 5.000 | 1.595 | True |
| low_ordinary_early | OUTBOUND | 5 | 0.13745, 0.29079 | 5.000 | 0.445 | True |
| low_ordinary_early | OUTBOUND | 10 | 0.26553, 0.56175 | 5.000 | 0.445 | True |
| low_ordinary_early | OUTBOUND | 20 | 0.49444, 1.04602 | 5.000 | 0.445 | True |
| low_ordinary_early | OUTBOUND | 50 | 0.97864, 2.07038 | 5.000 | 0.445 | True |
| low_ordinary_early | RETURN | 5 | -0.13990, -0.28944 | 5.000 | 0.445 | True |
| low_ordinary_early | RETURN | 10 | -0.27027, -0.55914 | 5.000 | 0.445 | True |
| low_ordinary_early | RETURN | 20 | -0.50326, -1.04116 | 5.000 | 0.445 | True |
| low_ordinary_early | RETURN | 50 | -0.99610, -2.06078 | 5.000 | 0.445 | True |


Every row separately certifies the initial acceleration-aware continuation, preserves exact repeated-same-target acceleration, then accepts a changed target, validates its C2/full continuation and verifies a sampled change before the original endpoint. Initial diagnostic output is retained as ONLINE_INTERFACE_BLOCKER_RETEST_initial.json. The original schedule/state is reconstructed, while certification uses the historical causal commissioning belief; later task-adapted RETURN beta is not reconstructed in these probes. These are reference/safety screen probes, not physical simulations. Actual new physical qualification uses its continually updated current belief separately; low-ROM online task completion was not newly studied.
