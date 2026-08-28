# Stage-4 oracle chain audit

Offline replay of saved registered trajectories. Oracle data did not enter the estimator.

| case | age ms | frontend q RMSE deg | F RMSE N | geom state q RMSE deg | dyn A/R | final beta dist/span | E_meas prior->final Nm | E_oracle prior->final Nm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal_200hz | 0.00 | 0.061 | 0.000 | 0.224 | 12/27 | 0.287 | 4.140->1.476 | 4.323->1.326 |
| noise_200hz | 0.00 | 0.181 | 1.266 | 0.242 | 8/31 | 0.359 | 4.347->2.292 | 4.438->2.225 |
| noise_bias_drift_200hz | 0.00 | 0.181 | 1.952 | 0.242 | 1/38 | 0.441 | 4.618->4.256 | 4.438->4.066 |
| noise_bias_delay_200hz | 9.99 | 0.219 | 4.739 | 0.481 | 5/15 | 0.288 | 4.715->3.339 | 5.447->4.211 |
| noise_bias_delay_100hz | 12.49 | 0.227 | 4.563 | 0.702 | 0/18 | 0.460 | 5.104->5.104 | 5.185->5.185 |
