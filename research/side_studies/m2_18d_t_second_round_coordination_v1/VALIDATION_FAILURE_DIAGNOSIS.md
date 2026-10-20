# 扩展状态motion失败：冻结停止门诊断

W1的完整B/18D/T已实际执行。T在原motion门失败，原task、绝对安全和causal执行仍通过。冻结harness要求T先合格才运行新D，因此D未在W1启动；W2按同一停止门未启动。不修改验证代码、不降低门槛，也不按失败结果换primary。

失败项：['velocity_deg_s/p95_abs', 'acceleration_deg_s2/p95_abs', 'excursion']。匹配T仍保留降力2.297305%，低力不替代motion资格。

逐joint/full/phase指标、超全程B限的样本数和不可逆prefix下界见audit/VALIDATION_BASELINE_FAILURE_DIAGNOSIS.json。phase近零比值不当作主要失败机制。若已完成的prefix自身超过全程允许excursion，或已超过固定任务可容许的5%高值样本计数，则更晚的RETURN2/3动作不能消除已经发生的负担；仅在JSON明确下界成立的项作此结论。其余项不作不可修复断言。

这暴露了T末段时间修复的适用域边界：末段变缓不能自动约束整条状态相关轨迹的p95/剂量。它不是未执行D的负物理结果；也不排除未来预注册修复研究。下一步优先扩大合法状态与motion准入机制验证，而不是把本轮小幅降力方案升级为通用基线。

本轮执行门未变，全部失败与partial父计算均入账；不因预算仍充足而绕过冻结停止门追加物理。
