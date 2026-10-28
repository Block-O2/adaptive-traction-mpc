# 冻结策略独立对照

|策略|runtime|TASK s|完整JF N·s|partial JF N·s|JM Nm·s（同完整/partial身份）|tracking RMS °|
|---|---|---:|---:|---:|---:|---|
|initial_deterministic|ABORTED|16.590|—|1262.834|73.519|0.5835, 0.6089|
|fixed_legal_plus_one|COMPLETE|19.030|1449.840|—|98.407|0.4674, 0.4332|
|final_deterministic|COMPLETE|19.030|1451.717|—|100.680|0.5112, 0.4729|
|final_deterministic_repeat|COMPLETE|19.030|1451.717|—|100.680|0.5112, 0.4729|

相同原nominal物理初态、任务、安全、candidate/admission权限；初始和训练后均deterministic，固定动作为[+1,+1]。固定策略仅为合法动作对照，不称原B/H150。训练策略使用最终checkpoint，不选择最佳瞬时episode。没有教师轨迹。

partial积分只描述实际已执行区间，不能与完整任务的较大JF/JM相减后宣称获益；tracking/jerk同样受已执行区间及速度影响。正式motion非劣/匹配fairness因原scorer缺失NOT_EVALUABLE。每phase积分、实际q/dq、速度/加速度/jerk/overshoot、完整receipt/native归属见audit/FINAL_INDEPENDENT_RECOMPUTATION.json与FINAL_EVALUATION_NATIVE_OWNERSHIP.json。

## 各phase独立积分

|策略|phase|实际时长s|JF N·s|JM Nm·s|
|---|---|---:|---:|---:|
|initial_deterministic|OUTBOUND|9.005|723.192457|48.173669|
|initial_deterministic|HOLD|1.020|54.394350|1.218710|
|initial_deterministic|RETURN|6.565|485.247535|24.126449|
|initial_deterministic|ABORTED|0.000|0.000000|0.000000|
|fixed_legal_plus_one|OUTBOUND|9.005|725.825779|46.498437|
|fixed_legal_plus_one|HOLD|1.020|54.394339|1.218708|
|fixed_legal_plus_one|RETURN|9.005|669.619943|50.689472|
|fixed_legal_plus_one|COMPLETE|0.000|0.000000|0.000000|
|final_deterministic|OUTBOUND|9.005|731.984415|45.016013|
|final_deterministic|HOLD|1.020|54.394336|1.218710|
|final_deterministic|RETURN|9.005|665.338082|54.445777|
|final_deterministic|COMPLETE|0.000|0.000000|0.000000|
|final_deterministic_repeat|OUTBOUND|9.005|731.984415|45.016013|
|final_deterministic_repeat|HOLD|1.020|54.394336|1.218710|
|final_deterministic_repeat|RETURN|9.005|665.338082|54.445777|
|final_deterministic_repeat|COMPLETE|0.000|0.000000|0.000000|

## 实际Human运动诊断

所有向量依次为hip/knee；partial与完整任务身份沿用上表。jerk仅诊断，不作为新资格门。

|策略|速度峰值°/s|加速度峰值°/s²|5ms jerk RMS°/s³|终点返回误差°|
|---|---|---|---|---|
|initial_deterministic|25.837, 25.242|102.689, 151.374|524.224, 856.529|9.359, 15.129|
|fixed_legal_plus_one|23.641, 23.166|56.646, 118.050|247.175, 494.029|0.499, -0.501|
|final_deterministic|25.449, 23.061|86.106, 117.376|372.352, 615.811|0.501, -0.500|
|final_deterministic_repeat|25.449, 23.061|86.106, 117.376|372.352, 615.811|0.501, -0.500|
