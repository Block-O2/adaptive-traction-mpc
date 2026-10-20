# 强低力连续协调修复

以下均为真实完整任务执行；收益保留只相对本轮同条件种子，未修改运动阈值。

|候选|完整收益%|种子收益保留%|最严重约束比|失败条件|
|---|---:|---:|---:|---|
|M2_fixed_actions_remove_entry|6.474926|83.91|2.591928|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion|
|M2_fixed_actions_distributed_return|7.211341|93.46|4.543931|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s, tracking|
|M2_fixed_actions_distributed_outbound|5.396073|69.93|5.095346|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion|
|M2_fixed_actions_alternating_exit|6.668310|86.42|2.034925|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s|
|C2_pair_1_2_remove_entry|10.561662|69.99|2.416179|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, jerk_deg_s3/rms, excursion, tracking|
|C2_pair_1_2_distributed_return|13.933816|92.34|4.625038|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/rms, RETURN_duration, excursion, task_duration, moment_integral_Nm_s, tracking|
|C2_pair_1_2_distributed_outbound|13.583719|90.02|4.581603|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, jerk_deg_s3/rms, RETURN_duration, excursion, task_duration, tracking|
|C2_pair_1_2_alternating_exit|14.988237|99.32|3.250000|velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, RETURN_duration, excursion, cumulative_dose, task_duration, moment_integral_Nm_s, tracking|
|repair2_2_0_remove_entry|1.469633|63.93|1.117779|acceleration_deg_s2/max_abs, excursion|
|repair2_2_0_distributed_return|2.286986|99.49|1.709872|acceleration_deg_s2/max_abs, excursion|
|repair2_2_0_distributed_outbound|2.346031|102.06|1.515373|acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion|
|repair2_2_0_alternating_exit|2.127254|92.54|1.468272|acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, excursion|

各候选真实velocity/acceleration/jerk的max/p95/RMS、行程及原native accepted delta与首次执行时刻见 SEQUENTIAL_BRANCH_RESULTS.json。不以统一缩小到近零作为修复；分别删入口、按slot重新分配原累计幅度、调整去程分配和补偿退出。

局部修复是否成功以冻结全部条件判断；运动代价改善或保留高降力不能单独取得可行资格。

部分强去程重分配前缀已经不可由后续回程动作修复：
- repair_M2_fixed_actions_distributed_outbound 的 OUTBOUND 最大速度相对完整B峰值 [0.9909811566819332, 0.9876921259372446]，最大加速度相对完整B峰值 [0.6522498702486978, 1.3368002624821638]；已有峰值超过1.1后，未来RETURN不能消除过去的峰值。因此未派发沿这些完全相同前缀的纯RETURN组合修复。这仅排除这些固定前缀，不排除修改更早OUTBOUND的其他运动。
- repair_C2_pair_1_2_distributed_outbound 的 OUTBOUND 最大速度相对完整B峰值 [0.996433563907255, 1.2846539023822163]，最大加速度相对完整B峰值 [1.013697152650023, 1.3680928066444402]；已有峰值超过1.1后，未来RETURN不能消除过去的峰值。因此未派发沿这些完全相同前缀的纯RETURN组合修复。这仅排除这些固定前缀，不排除修改更早OUTBOUND的其他运动。

## M2_fixed_actions：较低最严重违反的代表 M2_fixed_actions_alternating_exit

原收益 7.716337% → 6.668310%；最严重约束比 4.905696 → 2.034925。

|真实人体指标/统计|髋：原→修复|膝：原→修复|
|---|---|---|
|velocity_deg_s/max_abs|23.972831 → 25.161582|37.169334 → 36.750612|
|velocity_deg_s/p95_abs|22.930077 → 22.994883|33.846213 → 31.484486|
|velocity_deg_s/rms|14.789182 → 14.841147|16.530946 → 15.907841|
|acceleration_deg_s2/max_abs|53.829408 → 81.333534|117.041222 → 113.033520|
|acceleration_deg_s2/p95_abs|37.893627 → 41.759698|63.453961 → 61.630577|
|acceleration_deg_s2/rms|20.832392 → 22.743721|30.527133 → 28.842631|
|jerk_deg_s3/max_abs|6180.704718 → 6180.704718|21272.428625 → 21272.428625|
|jerk_deg_s3/p95_abs|351.750533 → 410.601057|1066.948402 → 986.552969|
|jerk_deg_s3/rms|279.194981 → 290.687090|764.698544 → 749.691282|

仍失败：velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion, moment_integral_Nm_s。jerk max仍仅诊断。

## C2_pair_1_2：较低最严重违反的代表 C2_pair_1_2_remove_entry

原收益 15.090469% → 10.561662%；最严重约束比 4.554095 → 2.416179。

|真实人体指标/统计|髋：原→修复|膝：原→修复|
|---|---|---|
|velocity_deg_s/max_abs|24.431311 → 23.591529|37.717745 → 37.440206|
|velocity_deg_s/p95_abs|22.918455 → 22.840398|35.361264 → 34.494971|
|velocity_deg_s/rms|14.291677 → 14.476014|16.849696 → 16.366028|
|acceleration_deg_s2/max_abs|75.436009 → 80.750943|151.920550 → 151.920550|
|acceleration_deg_s2/p95_abs|37.487032 → 35.838291|67.545011 → 55.490971|
|acceleration_deg_s2/rms|21.247064 → 21.606202|29.895543 → 28.283368|
|jerk_deg_s3/max_abs|7002.887792 → 6419.065379|20904.212731 → 20431.802731|
|jerk_deg_s3/p95_abs|371.123262 → 410.493966|950.316869 → 1003.714720|
|jerk_deg_s3/rms|284.302706 → 293.013820|797.711970 → 777.780792|

仍失败：velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, jerk_deg_s3/rms, excursion, tracking。jerk max仍仅诊断。

## repair2_2_0：较低最严重违反的代表 repair2_2_0_remove_entry

原收益 2.298702% → 1.469633%；最严重约束比 1.515372 → 1.117779。

|真实人体指标/统计|髋：原→修复|膝：原→修复|
|---|---|---|
|velocity_deg_s/max_abs|23.818633 → 23.641185|27.217744 → 22.972128|
|velocity_deg_s/p95_abs|22.914451 → 22.870086|22.322093 → 21.940158|
|velocity_deg_s/rms|14.843123 → 14.804271|14.446703 → 14.330700|
|acceleration_deg_s2/max_abs|141.879110 → 91.319715|129.479186 → 129.479186|
|acceleration_deg_s2/p95_abs|41.674441 → 39.083825|33.241676 → 30.584959|
|acceleration_deg_s2/rms|23.732756 → 21.815707|19.529291 → 18.030746|
|jerk_deg_s3/max_abs|5548.470080 → 5548.470080|18188.903758 → 18188.903758|
|jerk_deg_s3/p95_abs|428.169278 → 384.987292|958.912720 → 909.388365|
|jerk_deg_s3/rms|335.494118 → 306.651323|740.001180 → 721.655923|

仍失败：acceleration_deg_s2/max_abs, excursion。jerk max仍仅诊断。
