# 原 B/H150 冻结 scorer 云端独立复核

**OFFLINE_SCORER_READY=PASS；HISTORICAL_MATCHED_REPRODUCTION=PASS。** 这是原 D01R/W1 历史 raw 的新云端算术复核。

原 `analyze_matched.measure/compare` 与 `control/independent_recompute.measure` 分别执行；只在维护入口重绑定 S/P 和输出路径。原 5ms TASK 左积分、0.25ms native Human、prefix+suffix、motion/dose/边界、receipt/实际 torque/step ownership、100ms 科学时钟 source age 和 promotion assert 均保持启用。独立模块来源记录在 `scorer/original-001/OFFLINE_SCORER_RESULT.json`。

|原 fixture|JF N·s|JM Nm·s|tracking RMS ° hip/knee|TASK s|raw jerk RMS °/s³ hip/knee|
|---|---|---|---|---|---|
|D01R_parent|1436.4564981450510|101.25369459130|0.473481/0.461755|19.030000000|305.077/714.727|
|D01R_B|1436.4564981450510|101.25369459130|0.473481/0.461755|19.030000000|305.077/714.727|
|D01R_H150|1402.6432114861727|107.07227190726|0.453090/0.522946|19.030000000|319.305/675.350|

H150 相对 B 的 JF 改善 **2.353937394034738%**，JM 增加 **5.74653333830843%**；原 motion acceptance_pass=true，failed_requirements=[]。原 burden_sensitivity 的1.0门不通过而1.05门通过，也完整保留，不把“force下降”表述为所有指标均改善。tracking、原始/SG5/SG21 motion、dose、阶段代价和所有诊断字段见 `HISTORICAL_MATCHED_REPRODUCTION.json`。

逐字段与原冻结 MEASURED、原 receipt 报告比较；全部 motion_series key/数组逐元素相等；comparison 全部字段相等。数值绝对容差1e-8，只允许 sources/execution_lineage_path 元数据随新路径变化。32 fixture、23 scorer来源、16恢复锚点、完整v6的1426项、九合同、90模型身份全部通过；未因 JF 接近而跳过任何门。

三个原件的 PHYSICAL_TASK_VALID、SCIENTIFIC_EXECUTION_CAUSAL_VALID、LEGACY_R2_MATCHED 均为 PASS；HOST_EXECUTION_CAUSAL_VALID 均为 NOT_EVALUABLE。原 raw_scorer_v2 的 host plan_age/历史 RSS_RUNTIME_QUALIFICATION_NOT_MET 记录仍保留；原 mode-aware 科学执行绑定 PASS 不将其改为 host实时通过。该绑定来自恢复的原冻结 scorer，不是本轮改阈值。

本轮历史重算新增物理步=0。完整父进程 checkpoint/parent_CAUSAL_STATE 缺口影响 full fork，不影响已经验证的历史离线评分。8个新 PPO 开发评价没有原同父 prefix/B/H150 条件，因此 NEW_LIVE_MATCHED_EVALUATION=NOT_RUN，NEW_PPO_MATCHED_EVALUATION_READY=NOT_READY。
