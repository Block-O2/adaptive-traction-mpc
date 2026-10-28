# Critic模型审计

CONFIRMED：旧模型未覆盖。原B后续Critic修订模型见models/LEGACY_B_REVISED_V5_FROZEN.json；平顺性后续模型见models/COMMON_COMPOSE_FROZEN.json。后者不使用旧B尾部成本标签。主回归保留时间/阶段/remaining budget、当前估计、参考、scheduler/governor、接口与执行记忆，以及新增因果累计历史。contract_time_remaining为原run_executed_case的30秒task timeout减去已用TASK时间，并非提前获知实际终点；真实remaining duration仅为结果标签。

CONFIRMED：每个整父状态交叉验证训练折内独立拟合center/scale。标准化尺度取训练std与按量纲设置下限的较大者；时钟下限0.5s，未删除全部时间信息。v5约15ms变化在0.001缩放下形成异常距离；旧分布逐字段见analysis/V5_FEATURE_DISTRIBUTIONS.json，新分布见analysis/V6_TRAIN_FEATURE_DISTRIBUTIONS.json。

| 阶段 | 时间字段 | train min | train max | 冻结scale |
| --- | --- | --- | --- | --- |
| OUTBOUND | phase_elapsed_s_0 | 2.2050 | 2.2200 | 0.5000 |
| OUTBOUND | task_elapsed_s_0 | 2.2050 | 2.2200 | 0.5000 |
| OUTBOUND | contract_time_remaining_s_0 | 27.7800 | 27.7950 | 0.5000 |
| RETURN | phase_elapsed_s_0 | 2.1250 | 2.1600 | 0.5000 |
| RETURN | task_elapsed_s_0 | 12.1500 | 12.1850 | 0.5000 |
| RETURN | contract_time_remaining_s_0 | 17.8150 | 17.8500 | 0.5000 |

CONFIRMED：小型三lengthscale RBF ensemble分别输出绝对tail分量和菜单中心化tail分量。score类型只按整父状态留一验证选择，未使用新测试结果。成本与完整资格风险头分开；主策略训练若没有失败类，则明确不拟合该风险头。观测到的原门失败标记为吸收性条件，不能以低尾部成本清除；但精确native原motion在线监视器尚未暴露，不能将evaluation-only真值用作在线flag。

CONFIRMED：最初五个历史峰值失败都属于同一个TAILOT状态族，TAILRESCUE是同父重放。初版按job名划分的5/5交叉验证已废止；正确留出该父状态后，原小数据训练折没有失败正例。随后仅用v5已公开raw扩充完整过去历史窗口，形成1281个相关窗口、12个实际父状态族，其中3族含失败。operative风险头为WHOLE_HISTORY_RISK_V5_FROZEN，24个observer/wrench/time/phase及已完成guard/refusal/fallback历史字段。不同后续策略只可共享“截至H已发生风险”标签，不共享cost-to-go标签。

CONFIRMED：误把jerk max_abs当作原门的临时V3标签已经封存，未进入测试；原门对jerk使用rms/p95，没有jerk max_abs门。修正后逐窗口断言：完整原合格轨迹不得标作已经不可逆失败。见audit/INVALID_RISK_V3_LABELS.json。最终整父状态族留出CV仍有漏检和误拒，不能把模型分数当原完整门。CV明细与计算开销见WHOLE_HISTORY_RISK_V5_FROZEN；12族经实际执行prefix指纹再次核验，没有仅按job名制造独立样本。

CONFIRMED：LEGACY_B_REVISED_V5中的描述字段risk_positive_independent_state_families仍保留初版的1，实际嵌入风险权重与WHOLE_HISTORY_RISK_V5完全一致，覆盖3个失败族/12族；单独澄清见audit/FROZEN_LEGACY_RISK_METADATA_CLARIFICATION.json，未改冻结文件。v6_model.py保留的旧select辅助函数未用于实际冻结选择；operative入口为v6_selection.select，无支持候选时ABSTAIN。

SUPPORTED：OOD阈值来自训练父状态留一距离并设定界限；不确定/被筛候选按冻结规则回退。ensemble差异与logistic分数都不是校准置信区间或安全证书。数值拟合/推理开销见RESOURCE_AND_ATTEMPT_ACCOUNTING.json，初次import/I/O与纯数值推理分开说明。

CONFIRMED：实际准入为全特征RMS标准化最近距离不超过冻结阈值、已发生风险分数<0.5、可用的完整资格风险分数<0.5；全部不支持时ABSTAIN。ensemble std仅报告，没有校准拒绝阈值；没有失败类而未拟合的资格头返回None，不是“已证明安全”。全局距离可掩盖单字段外推，独立OOD拒绝可靠性NOT_TESTED。当前完整资格仍由原raw门评价，不能以此门后审计冒充事前安全证书。

NOT_TESTED：可部署的廉价H状态预测、完整原motion资格概率校准、硬件实时资格或一般患者域外可靠性。

CONFIRMED：冻结V5风险头整父状态族CV窗口混淆计数：{'TP': 18, 'FN': 32, 'FP': 14, 'TN': 1217}。同轨迹多窗口相关，这不是1281个独立验证样本；失败窗口漏检不能由较高总体正确率掩盖。

CONFIRMED：成本累计历史消融只删除history_前缀输入，保留upstream上下文与两个风险头。不能称为完整历史消融或将差异归因于某单个历史量。各折与各未见状态动作记录在主freeze和evaluation中。

| 阶段 | 总字段 | 恒定字段 | std低于量纲floor字段 |
| --- | --- | --- | --- |
| OUTBOUND | 126 | 45 | 126 |
| RETURN | 126 | 42 | 125 |

CONFIRMED：下表来自H时已落盘预测，绝对tail误差与相对排序分开；ensemble spread不是校准区间。主score_index3为菜单中心化tail JF，共同偏置不影响同菜单排序。

| 状态 | tail JF RMSE N·s | tail JM RMSE Nm·s | 剩余时长RMSE s | 唯一合格pair数 | Critic排序正确率 |
| --- | --- | --- | --- | --- | --- |
| LEGACY_BOUNDARY_O2 | 1.306169 | 0.050304 | 0.007784 | 3 | 0.667 |
| LEGACY_BOUNDARY_O3 | 1.324291 | 0.050424 | 0.007489 | 1 | 1.000 |
| LEGACY_NEW_O | 0.890442 | 0.040125 | 0.007487 | 28 | 0.929 |
| TEST_O1 | 0.506758 | 0.033550 | 0.005808 | 3 | 1.000 |
| TEST_O2 | 0.457213 | 0.080898 | 0.006925 | 3 | 1.000 |
| TEST_R1 | 0.053065 | 0.049211 | 0.000872 | 6 | 1.000 |
| TEST_R2 | 0.088111 | 0.092534 | 0.003757 | 6 | 1.000 |

CONFIRMED：上表O3属于已暴露训练父状态重放，仅作回归诊断；7个评价对象不是7个独立新状态。主4状态、旧B真正新状态2个、已封存重放1个严格分开。原始别名FAIL审计未删除。

CONFIRMED：整父状态族CV按阶段计数={'OUTBOUND': {'TN': 351, 'FN': 12}, 'HOLD': {'TN': 150, 'FN': 6}, 'RETURN': {'TN': 716, 'FN': 14, 'TP': 18, 'FP': 14}}。出程12个失败窗口全部漏检，HOLD6个全部漏检，18个TP全部在RETURN；这些是相关窗口。最终模型对已包含训练样本仍漏掉8个接近excursion边界的窗口，不把训练误差当验证。

HYPOTHESIS：阶段/父状态覆盖、summary压缩及logistic线性/正则化可能共同限制风险头；最近异标签summary并不证明完整因果历史不可辨识。见analysis/RISK_FAILURE_MECHANISMS.json。
