# 本轮自然G4路径证据更新

历史G4_STRICT_PASS=FAIL保持；本轮完整G4仍FAIL，不晋级。新证据来自正常PPO动作、原任务与原物理，无TEST_ONLY注入，没有修改deadline。

|seed|episode|自然终止|TASK s|原phase elapsed s|审计|
|---:|---:|---|---:|---:|---|
|1630784693|15|TIMEOUT_RETURN|20.025|10.000|True|
|1106823814|55|TIMEOUT_OUTBOUND|10.000|10.000|True|
|1630784693|52|TIMEOUT_RETURN|20.025|10.000|True|

已观察OUTBOUND与RETURN原10秒deadline自然触发，失败奖励、absorbing terminal、native ownership与观测运动审计通过。训练临时native大raw按预注册统一规则在原逐native审计通过后移除，compact trace/receipt、摘要、奖励/运动/ownership审计及hash仍保留；不冒称新增独立冻结完整raw评价。

自然HOLD失败、绝对安全触发以及完整原矩阵尚未闭合；global TASK timeout证据未建立。几何不可行候选被拒绝属于保护生效，不冒称实际绝对安全触发。不能因为新增两个timeout路径就把G4改为PASS。最初沿用历史“缺自然timeout”概括不完整，最终报告以本表为准。
