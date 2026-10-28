# 事前物理代理诊断

当前仅一Human/一matched组B/H150，不能按3807个相邻点冒充独立样本。误差和符号见PROXY_MODEL_RESULTS.json；无未见状态泛化资格。完整tracking、native v/a/jerk、excursion/overshoot、原motion余量及contact/task预测无可验证闭包，标UNKNOWN。reference导数只作模型输出。

PHYSICS_PROXY_USABLE=CONDITIONAL_NOMINAL_LOAD_RANKING_ONLY；RESIDUAL_LEARNING_NEEDED=HYPOTHESIS_TO_TEST；FORWARD_PREDICTION_BLOCKED=FULL_CLOSED_LOOP_MOTION_TASK_CONTACT_NOT_CLOSED。后续三臂只用近似作建议，资格由真实执行决定。

## 当前正确模型诊断与版本边界

v1–v3前向构造曾误用库默认ROM，未绑定本任务high-ROM prior及commissioned residual。这些版本已保留并标为INVALID_MODEL_IDENTITY，不能把其极大误差作为物理先验失效证据。v4使用原同型StateResidualHumanModel、high_rom deployable_prior和commissioned beta/residual；修复仅在本轮隔离诊断中，物理controller未改。另保留有限差分与解析空间链式导数的算术诊断，未对heldout调参。

正确v4：B完整名义JF1432.036716、拟议H150近似1424.100990，预测ΔJF=-7.935726 N·s；实际ΔJF=-33.813287，差25.877560。JM预测Δ+0.092151、实际+5.818577 Nm·s。它正确预测该对比的符号，但幅度与moment明显不准；一组数据不能标为预测泛化PASS。

在H150局部二维邻域，另用已完成H150 causal reference构造35次零physics名义算术表，20ms抽样，只对负荷排序作建议。主比较公开同一工程H150锚点以移除常数偏差；原始绝对名义值与锚定差分误差分开报告。该表不是完整closed-loop simulation，OUTBOUND变化对后续RETURN状态和准入的影响留给真实反馈残差。

## 低force但motion失败的历史反例

恢复的m2_free_trajectory_feasibility_v1/REPORT.md列出同条件JF1214.916378的候选相对1438.613498低15.549494%，却因excursion等原门失败；该报告SHA见audit/SOURCE_RECOVERY_AUDIT.json。本轮没有恢复其完整raw，引用为历史报告证据，不冒称本轮独立重算。原18D新合法prefix motion0/4和history-to-next-trial中H150在P05/P08/U16的excursion失败同样保留。不能用完整force预测正确替代motion资格预测。

若本轮小trust domain内没有产生motion失败，C的经验余量预测也不因此取得识别低force不可行方案的能力；缺少失败域和独立状态覆盖须保留为验证缺口。

## 三臂完整轨迹预序验证

完整轨迹分母：{'A': 20, 'B': 20, 'C': 20}；同一优化父状态组，不能按时间步或次数冒充独立患者。每次预测早于其START，且只使用自身先前反馈，见OPTIMIZATION_ANALYSIS.json的feedback_firewall。

C在自己真实执行点上的名义锚定JF RMSE=0.941323146 N·s，学习预序RMSE=0.324837107。该预测比较与C是否找到更好的实际运动独立；固定12次C超过A/B=False，全分配=False。

分phase名义预测误差见PROXY_MODEL_RESULTS.json的current_phase_nominal_prediction_errors；完整JM、收益符号、排序与不确定性经验覆盖见MODEL_RESIDUAL_RESULTS.json。原真实tracking/native derivative/excursion/overshoot/task/contact的完整事前闭包仍未建立，原安全链拥有最终准入权。新前缀仅一Human的另一个合法状态条件，不能授跨患者资格。

## 冻结新前缀的绝对预测与配对差分

模型和候选在新prefix前冻结，没有据新B/H150重新拟合或重选。绝对预测保留原H150锚点；配对差分另列，不能把事后重锚解释成原事前精度。

|候选|实际JF|名义绝对误差|学习绝对误差|冻结学习ΔJF|实际新H150配对ΔJF|原门|
|---|---:|---:|---:|---:|---:|---|
|FROZEN_NEW_PREFIX_LOCKED_A|1401.358816|-0.100567|—|—|-2.540140|True|
|FROZEN_NEW_PREFIX_LOCKED_B|1401.336169|-0.029434|—|—|-2.562787|True|
|FROZEN_NEW_PREFIX_LOCKED_C|1401.336169|-0.029434|-1.180959|-2.488002|-2.562787|True|
|FROZEN_NEW_PREFIX_PRIMARY12_A|1401.387489|-0.218437|—|—|-2.511467|True|

新prefix仍为同一Human且只一状态组；原始绝对成本漂移与动作差分收益分开判断。若新H150不合格，其差值仅为诊断，不授正式强父收益。
