# Stage-4 single incumbent--challenger L4 offline audit

No setting is production-default. Oracle data was appended only after each online-style decision.

## Primary pre-registered setting

Anytime familywise alpha: 0.05; challenger spending: alpha_j=alpha/[j(j+1)]; looks: (8, 12, 16); two fixed references per look.

| case | challengers P/R/Pending | first promotion s/phase | decided validation durations s | longest no-promotion s | promoted oracle worse | rejected oracle better | prior->final oracle Nm | beta truth prior->final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal_200hz | 3 2/0/1 | 10.880/0.473 | 5.500,8.500 | 10.880 | 0 | 0 | 4.325->3.641 | 0.460->0.401 |
| noise_200hz | 2 1/0/1 | 17.900/0.778 | 12.520 | 17.900 | 0 | 0 | 4.430->4.143 | 0.460->0.482 |
| noise_bias_drift_200hz | 2 1/0/1 | 17.900/0.778 | 12.520 | 17.900 | 0 | 0 | 4.430->4.119 | 0.460->0.470 |
| noise_bias_delay_200hz | 1 0/0/1 | none | none | 13.310 | 0 | 0 | 5.408->5.408 | 0.460->0.460 |
| noise_bias_delay_100hz | 1 0/0/1 | none | none | 12.790 | 0 | 0 | 5.145->5.145 | 0.460->0.460 |

## Pre-declared sensitivity settings

| setting | case | challengers P/R/Pending | first promotion s | promoted oracle worse |
|---|---|---:|---:|---:|
| sensitivity_single_challenger_hac_lag3_12_to_20 | ideal_200hz | 2 1/0/1 | 17.400 | 0 |
| sensitivity_single_challenger_hac_lag3_12_to_20 | noise_200hz | 2 1/0/1 | 20.880 | 0 |
| sensitivity_single_challenger_hac_lag3_12_to_20 | noise_bias_drift_200hz | 2 1/0/1 | 20.880 | 0 |
| sensitivity_single_challenger_hac_lag3_12_to_20 | noise_bias_delay_200hz | 1 0/0/1 | none | 0 |
| sensitivity_single_challenger_hac_lag3_12_to_20 | noise_bias_delay_100hz | 1 0/0/1 | none | 0 |
| sensitivity_single_challenger_moving_block_bootstrap_l2 | ideal_200hz | 3 2/0/1 | 10.880 | 0 |
| sensitivity_single_challenger_moving_block_bootstrap_l2 | noise_200hz | 2 1/0/1 | 17.900 | 0 |
| sensitivity_single_challenger_moving_block_bootstrap_l2 | noise_bias_drift_200hz | 2 1/0/1 | 17.900 | 0 |
| sensitivity_single_challenger_moving_block_bootstrap_l2 | noise_bias_delay_200hz | 1 0/0/1 | none | 0 |
| sensitivity_single_challenger_moving_block_bootstrap_l2 | noise_bias_delay_100hz | 1 0/0/1 | none | 0 |
