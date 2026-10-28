# 长期成本Critic

状态：ALL_FROZEN_MODEL_TESTS_COMPLETED。先以完整C1菜单诊断真实短视，再以小型三lengthscale RBF ensemble预测remaining JF/JM、剩余时间及原motion最差比。H处输入含因果估计、参考、active suffix、governor及接口记忆；不只是q/dq，也不输入未来Human/receipt。固定任务gamma=1，不对MuJoCo反向传播。

fit_only只打开training父状态，保存source/config/weights SHA；test START必须晚于权重冻结。evaluate_only不更新模型。按完整父状态分组，不随机拆同分支horizon。主模型COSTO/COSTR每阶段拟合16条真实候选标签；COSTO8/COSTR8为在test执行前预登记冻结的8条标签次要消融，不能按test后最佳替代主模型。失败不以低积分进入cost训练胜利；failure/safety classifier未建立，ensemble差异也不当校准区间。当前100字段未显式包含完整native累计剂量/历史极值，worst_ratio分量不能作为原全任务motion资格的充分因果预测器。

门控见analysis/CRITIC_GATE_DECISION.json，冻结模型见models/CRITIC_*_FROZEN.json，训练和test群组见对应配置。全候选short与tail已经实际执行时，新增物理节省是0；预测准确不能替代选择收益。

| 模型 | test父 | H | short | critic | actual tail | critic vs short ΔJF | 训练固定动作 | critic vs fixed ΔJF | tail RMSE | 合格集合排序r（事后） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COSTO8 | TAILOT | 0.5 | TAILOT_SPEEDP FAIL | TAILOT_SPEEDP FAIL | TAILOT_RELATIVEP | 主选择FAIL | TAILOT_RELATIVEP PASS | 主选择FAIL | 2.107992 | 0.964 |
| COSTO | TAILOT | 0.5 | TAILOT_SPEEDP FAIL | TAILOT_SPEEDP FAIL | TAILOT_RELATIVEP | 主选择FAIL | TAILOT_RELATIVEP PASS | 主选择FAIL | 1.883798 | 0.964 |
| COSTR8 | TAILRT | 0.5 | TAILRT_SPEEDM PASS | TAILRT_RELATIVEM PASS | TAILRT_RELATIVEM | 1.555516 | TAILRT_RELATIVEM PASS | 0.000000 | 0.115201 | 1.000 |
| COSTR | TAILRT | 0.5 | TAILRT_SPEEDM PASS | TAILRT_RELATIVEM PASS | TAILRT_RELATIVEM | 1.555516 | TAILRT_RELATIVEM PASS | 0.000000 | 0.090384 | 1.000 |


已暴露test的查询敏感性诊断：训练常量clock字段置训练均值后，主出程最近训练距离约2.527→1.372，tail RMSE约1.884→1.547、去共同误差RMSE约1.301→0.965，但主选择仍SPEEDP且motion FAIL；处理所有训练近恒定字段也未改变选择。确认时钟影响算法距离，但不足以修复决策；未重训或改主模型/原test。完整风险状态修复和新盲验证仍NOT_TESTED，见[查询敏感性](CRITIC_FEATURE_SENSITIVITY.md)。
