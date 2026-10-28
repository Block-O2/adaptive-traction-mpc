# 实际物理比较与因果边界

新guard的P2-B/P2-C：**NOT_RUN**。所有本轮物理保留原clearance函数，只增加同次因果输入日志；没有新guard的jerk、force、任务失败率或安全资格结果。以下不是新旧guard对照。

开发固定候选共12条完整分支，冷父单独计账。同一live父地址空间fork；初始parent hash一致不等于后续Human状态相同。8/12通过完整原motion门。

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|DEV_B|PASS|1436.456498145|101.253694591|0|-0.067183|305.077/714.727|
|DEV_H150|PASS|1402.643211486|107.072271907|0|-0.068502|319.305/675.350|
|DEV_OLD_STRONG|PASS|1400.089728260|107.704687851|0|-0.068248|319.568/676.403|
|DEV_BEST|PASS|1398.034615470|107.971017015|0|-0.067785|320.151/678.366|
|DEV_C19|FAIL|1399.857062420|108.090020580|1|-1432.356195|885.967/1955.251|
|DEV_LOCAL_M0p0008|PASS|1399.846141809|108.089349477|0|-0.068248|319.490/675.680|
|DEV_LOCAL_M0p0004|PASS|1399.846384274|108.089323673|0|-0.068248|319.490/675.680|
|DEV_LOCAL_M0p0002|FAIL|1399.856941223|108.090033509|1|-597.744954|885.968/1955.254|
|DEV_LOCAL_P0p0002|FAIL|1399.857183616|108.090007652|1|-896.327494|885.966/1955.248|
|DEV_LOCAL_P0p0004|FAIL|1399.857304812|108.089994723|1|-61.711009|885.965/1955.244|
|DEV_LOCAL_P0p0008|PASS|1399.847111663|108.089246263|0|-0.068248|319.490/675.681|
|DEV_NEG|PASS|1399.849198648|108.032127691|0|-0.068248|319.423/675.554|


六个未见微扰的分类事前冻结，已评价6个，符合预测6个。候选参数和历史因果估计是模型输入，未来Human/native只作标签。每条完整JF/JM均保留；motion FAIL不进入正式收益排名。当前强最佳为历史最佳精确重复，不能称本轮新降力成果。

原guard的巨大负曲率、加速度box角点、post-filter未满足标志和实际receipt/native冲击分开报告。完整指标见analysis/branches/*.json与FULL_RESULTS.csv；原始未滤波q/dq/a/jerk见runtime/motion_series/*.npz，完整native torque/contact和原scorer见runtime/source/results/*。新日志使双端点的gap/rate精确闭包，两个重建误差均0；解析单支曲率约2.15×10⁻⁵，双端点算术诊断correction为0。这仍未物理应用，不推断它实际会减少jerk。

实际物理安全/任务和科学receipt轴按原口径分别审计；host轴为['NOT_EVALUABLE']。guard内部约束未满足不自动等于实际碰撞，也不是安全证明。torque maxima由native receipt join单列；原trace实测为5ms并含terminal重复边界；clipping分量与实际task receipt逐条join、重建torque与覆盖率见audit/ALL_RECEIPT_NATIVE_IDENTITY.json，不能把20ms SAC wrapper当成trace采样周期。原安全检查结果全部保留。


## 全部受保护partial（不排名）

- FACT_BEST_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62540；partial JF=1266.183076411996 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_BEST_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62920；partial JF=1274.327668919538 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62840；partial JF=1273.1658746470823 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62660；partial JF=1270.9221378564696 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
