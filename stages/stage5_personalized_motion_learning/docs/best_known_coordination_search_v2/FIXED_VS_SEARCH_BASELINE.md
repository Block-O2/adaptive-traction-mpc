# Fixed versus search baseline

All J_F values are in N s. Each arm has its own baseline. The selected fixed descriptor is shared across conditions within that arm.

|Condition|Arm|Original baseline|Preregistered fixed hip-leading|Selected universal fixed|Best-known|Fixed minus best-known|
|---|---|---:|---:|---:|---:|---:|
|low_ordinary_early|MATCHED|599.082773|600.505039 (not isolated)|599.082773|598.414598|0.668175|
|low_ordinary_early|NATIVE|501.521818|510.697915|501.521818|497.020323|4.501495|
|balanced_high|MATCHED|1207.127793|1196.030462|1207.127793|1179.976442|27.151351|
|balanced_high|NATIVE|942.010655|983.230834|942.010655|936.677211|5.333444|
|variable_start_120|MATCHED|1521.938394|1482.176759|1521.938394|1473.621009|48.317385|
|variable_start_120|NATIVE|1231.651956|1217.908788|1231.651956|1172.543336|59.108620|
|sync_120|MATCHED|1529.600078|1488.972118|1529.600078|1465.626365|63.973714|
|sync_120|NATIVE|1236.980854|1222.018306|1236.980854|1165.753400|71.227454|
|hip_ordinary|MATCHED|766.820951|763.391593|766.820951|761.440631|5.380319|
|hip_ordinary|NATIVE|631.130200|623.845813|631.130200|618.076149|13.054052|

Fixed descriptor selection (frozen before final cross-condition reexecution):

```json
{
  "arms": {
    "MATCHED": {
      "coverage_before_reexecution": 5,
      "descriptor": {
        "level": 3,
        "matched_duration_factor": 1.3,
        "parameters": [
          0.0,
          0.0,
          0.5,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      },
      "mean_fractional_benefit": 0.0
    },
    "NATIVE": {
      "coverage_before_reexecution": 5,
      "descriptor": {
        "level": 3,
        "matched_duration_factor": 1.3,
        "parameters": [
          0.0,
          0.0,
          0.5,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      },
      "mean_fractional_benefit": 0.0
    }
  },
  "frozen_before_final_cross_execution": true,
  "selection": "per arm independently: coverage first, mean relative benefit second, in-sample"
}
```

Selection uses previously observed coverage first and mean relative benefit second. It is an in-sample comparison among tested descriptors, not an exhaustive search for the globally best fixed policy. Historical references are retained when stronger; v2-only minima and their independent confirmation are separately recorded in CONDITION_COMPARISON.json. No general fixed-policy sufficiency or personalization necessity follows from these gaps.
