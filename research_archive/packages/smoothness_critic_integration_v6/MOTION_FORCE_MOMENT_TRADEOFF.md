# Motion、force与moment取舍

CONFIRMED：v5 COMPOSE相对强固定约+8.058633 N·s JF、−1.904880 Nm·s JM，不能称全面低负担。新增BLEND仅试图减少该JF代价，可能回升JM且损失少量平顺性收益；精确配对结果见analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json和SMOOTHNESS_BASELINE_COMPARISON.md。

CONFIRMED：原任务、native未滤波motion、force/moment峰值、tracking、excursion、累计运动、端点/阶段边界、phase/HOLD时长和ownership条件共同保留。full与remaining成本、jerk/wrench分量单列。原门FAIL或partial不进入正式低成本成功排名。

HYPOTHESIS：运动与力变化率改善可能与提前降低rolling交接速度及局部时序有关；本轮没有新增独占中介比例或临床舒适度证明。

SUPPORTED：传统单一RULE状态=NOT_RUN。未运行部分不制造结果；原因见ADAPTIVE_FIXED_RULE_RESULTS。

| 状态 | 原门 | 90%保留 | 髋/膝/力变化率收益保留 | RULE少JF vsCOMPOSE | RULE多JM vsCOMPOSE | RULE少JF vsBLEND | RULE多JM vsBLEND |
| --- | --- | --- | --- | --- | --- | --- | --- |


CONFIRMED：配对复用在任何SMOOTH_A1/A2结果揭示前登记，要求新完整B身份锚与既有raw/native/receipt精确匹配；原初未执行RULE配置保留source/versions，不冒充结果。计划由15降到9个START为边界留预算，但若RULE未触发，这6次只是预算减少，绝不计实际节省。动作与90%标准未因测试调整。实际筛选省略7个唯一候选另算，不归因于Critic。

SUPPORTED：固定阶段方案追加复核=COMPLETED_TWO_PAIRED_CONFIRMATIONS。2组配对中2组通过原门及额外代价上限；相对COMPOSE平均ΔJF=-1.309722 N·s、ΔJM=-0.152900 Nm·s。

| 配对状态 | 原门 | 全JF | 全JM | ΔJF vsCOMPOSE | ΔJM vsCOMPOSE | 髋/膝jerk与力变化率比值 | 额外界通过 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PHASE_RULE_S1 | True | 1405.990071 | 105.481425 | -1.314003 | -0.152203 | 1.000481/0.999953/1.003069 | True |
| PHASE_RULE_S2 | True | 1403.733763 | 106.198484 | -1.305442 | -0.153598 | 1.000473/0.999948/1.003112 | True |

CONFIRMED：此为固定OUT1 HANDOFF后共同COMPOSE，不是整段HANDOFF。原任务/门完全相同，额外冻结研究界为髋/膝jerk≤COMPOSE1.001倍、力模长变化率≤1.004倍且JF/JM同时不增。主测试效果已知、参照状态部分暴露，故只称自适应配对复核；不是独立模型选择或新的未见Critic状态。scope澄清见audit/FIXED_PHASE_BOUND_REGISTRATION_SCOPE.json。

CONFIRMED：逐阶段原左积分满足delta J=(T_new−T_ref)*mean_ref+T_new*(mean_new−mean_ref)，闭合误差<1e-8。实际差异主要是平均力/力矩变化，并不是延长或缩短原任务换积分。见analysis/FORCE_MOMENT_DOSE_DECOMPOSITION.json；该式是代数分解，不是机制独占或因果中介证明。

| 状态 | D相对COMPOSE ΔJF | ΔJM | 髋/膝jerk和力变化率Δ% |
| --- | --- | --- | --- |
| TEST_O1 | -1.312819 | -0.152397 | 0.0481/-0.0048/0.3077 |
| TEST_O2 | -1.307640 | -0.153242 | 0.0475/-0.0051/0.3102 |
| TEST_R1 | 0.000000 | 0.000000 | 0.0000/0.0000/0.0000 |
| TEST_R2 | 0.000000 | 0.000000 | 0.0000/0.0000/0.0000 |
