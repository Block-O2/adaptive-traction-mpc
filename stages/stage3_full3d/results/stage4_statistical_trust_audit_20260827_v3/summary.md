# Stage-4 statistical L4 offline audit

No setting is production-default. Oracle data was appended only after each online-style decision.

## Primary pre-registered setting

Rollout-level familywise alpha: 0.05; maximum candidates: 48; looks: (8, 12, 16); per-bound/per-look alpha: 0.000173611.

| case | P/R/S/Pending | first promotion s/phase | longest no-promotion s | promoted oracle worse | oracle improvement promoted/decided-nonpromoted median Nm | prior->final full-trace oracle Nm | beta truth prior->final |
|---|---:|---:|---:|---:|---:|---:|---:|
| ideal_200hz | 2/0/26/8 | 10.880/0.473 | 10.880 | 0 | 0.332/0.406 | 4.325->3.641 | 0.460->0.401 |
| noise_200hz | 1/0/25/10 | 17.900/0.778 | 17.900 | 0 | 0.297/0.411 | 4.430->4.143 | 0.460->0.482 |
| noise_bias_drift_200hz | 1/0/25/10 | 17.900/0.778 | 17.900 | 0 | 0.326/0.437 | 4.430->4.119 | 0.460->0.470 |
| noise_bias_delay_200hz | 0/0/0/16 | none | 13.310 | 0 | nan/nan | 5.408->5.408 | 0.460->0.460 |
| noise_bias_delay_100hz | 0/0/0/18 | none | 12.790 | 0 | nan/nan | 5.145->5.145 | 0.460->0.460 |

## Pre-declared sensitivity settings

| setting | case | P/R/S/Pending | first promotion s | promoted oracle worse |
|---|---|---:|---:|---:|
| sensitivity_hac_lag3_12_to_20 | ideal_200hz | 1/0/24/11 | 17.400 | 0 |
| sensitivity_hac_lag3_12_to_20 | noise_200hz | 1/0/30/5 | 20.880 | 0 |
| sensitivity_hac_lag3_12_to_20 | noise_bias_drift_200hz | 1/0/30/5 | 20.880 | 0 |
| sensitivity_hac_lag3_12_to_20 | noise_bias_delay_200hz | 0/0/0/16 | none | 0 |
| sensitivity_hac_lag3_12_to_20 | noise_bias_delay_100hz | 0/0/0/18 | none | 0 |
| sensitivity_moving_block_bootstrap_l2 | ideal_200hz | 2/0/26/8 | 10.880 | 0 |
| sensitivity_moving_block_bootstrap_l2 | noise_200hz | 1/0/25/10 | 17.900 | 0 |
| sensitivity_moving_block_bootstrap_l2 | noise_bias_drift_200hz | 1/0/25/10 | 17.900 | 0 |
| sensitivity_moving_block_bootstrap_l2 | noise_bias_delay_200hz | 0/0/0/16 | none | 0 |
| sensitivity_moving_block_bootstrap_l2 | noise_bias_delay_100hz | 0/0/0/18 | none | 0 |
