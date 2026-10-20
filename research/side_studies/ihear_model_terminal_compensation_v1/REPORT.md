# iHEAR Lab — Model-Based Terminal Compensation & Lightweight Feedback Study v1

本轮获得一个侵入较小的合格研究候选H150：仅将ER的RETURN5髋终末时长乘1.5并向上量化到5ms（W1为0.440→0.660s；W2为0.515→0.775s），保持膝参考意图和完整19.030s任务。W1真实膝下冲减少0.074349°（5.830%），excursion差从+0.548596°降到+0.474247°，通过原B+0.5°门；降力2.353937%基本完整保留。确定性重复逐字段一致。在此前未消费的W2合法prefix上，H150也通过全部原资格：J_F=1397.727675N·s，相对匹配B降2.337103%；下冲1.209812°，excursion差+0.115465°。

这是一项有限幅度的修复，不是消除过冲：W1仍有1.201029°下冲，而原B为0.577911°。W1的excursion门余量只有0.025753°。H150没有新增PD或FF，也没有证明现有模型能够准确预测完整耦合系统的停止位置。

## 关键定义与设计

所有下冲按RETURN期间“最终issued膝reference 9.5°−真实最低膝角”定义，截断至非负。注册任务目标10°仍保留；若改按10°计，下冲会增加0.5°。reference自身运动、actual−reference误差、actual越过目标、全程max−min excursion、相对B excursion差是五个不同量。

W1 ER最低膝角8.224622°，发生在17.166000s；reference于16.895s停稳。停稳时已下冲1.169896°，其后继续0.105483°，约91.7%的下冲在reference停止前形成。不能把1.275378°下冲当成+0.548596° excursion差。

W1先复现冻结B/T/D/ER，再做H150和受限阻尼/PD/FF/PDFF；仅一次接口缺陷修复，参数不变。H150在第一次开发合格后即冻结，随后fresh cold parent完整重复，再运行此前未消费的W2配对。重复比较所有trace字段、native body/contact/torque/ownership和科学receipt/reference/source字段；host墙钟profiling不要求一致。开发数据不是盲测；确定性重复也不是鲁棒性证据。W2只测试同一Human的新合法prefix。

W1 seed=2026102001，prefix为OUTBOUND [0.08,0.04,0.03]、RETURN [0.04,0.02,0.03]；W2 seed=2026102002，prefix为OUTBOUND [0.11,−0.035,0.045]、RETURN [−0.04,0.025,−0.035]。这些是冻结接口中的合法协调动作，不是重放或直接设置Human qpos/qvel。

## 完整物理结果

|方案|J_F (N·s)|相对B降力|膝下冲 (°)|excursion−B (°)|全部资格|
|---|---:|---:|---:|---:|---|
|B|1436.456498|0.000000%|0.577911|+0.000000|PASS|
|T|1403.456710|2.297305%|1.261666|+0.534884|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/p95_abs, excursion|
|D|1402.234611|2.382382%|1.270505|+0.543723|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, jerk_deg_s3/rms, excursion|
|ER|1402.644193|2.353869%|1.275378|+0.548596|FAIL: excursion|
|H150|1402.643211|2.353937%|1.201029|+0.474247|PASS|
|KD120|1402.644214|2.353868%|1.275742|+0.548960|FAIL: excursion|
|PD|1402.640699|2.354112%|1.278128|+0.551346|FAIL: excursion|
|FF|1402.666530|2.352314%|1.287990|+0.561208|FAIL: excursion|
|PDFF|1402.664470|2.352457%|1.290707|+0.563925|FAIL: excursion|


W1中的T、D和ER仍保留原FAIL。KD120/PD/FF/PDFF都完成任务、安全和receipt检查，但未修复excursion，不升级为合格方案。仅比较完成的任务积分，失败partial没有参与排名。

![力、运动及moment完整对照](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/figures/05_force_motion_moment.png)

## 对12个研究问题的回答

1. **B已有反馈与补偿。** 外层估计状态waypoint重规划，Human PD（Kp=[180,140]、Kd=[28,22]），Human逆动力学/重力/科氏/被动/软ROM/残差，增量加速度和clearance投影，robot笛卡尔/姿态/零空间反馈及bias torque都已存在。没有发现该活跃路径的积分项；Human跟踪律没有直接+ddq_ref项。详见[CONTROL_ARCHITECTURE_AUDIT.md](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/CONTROL_ARCHITECTURE_AUDIT.md)。

2. **有反馈仍会过冲。** 广义加速度/力矩请求不是实际施加给Human的响应，robot–cuff传递与实际耦合不在2DOF闭环预测内。16.895s膝PD已请求+168.174°/s²制动，真实native加速度只有+5.753°/s²；以实测wrench驱动Human模型预测为+16.049°/s²。终末未发现torque clipping、床接触或增量投影active。证据支持“存在请求—响应差异”，不支持唯一根因归责。

3. **模型能否提前预测？** 因果100ms预测中，实测wrench冻结模型的膝位置RMSE0.038690°、p95误差0.074372°；保持当前广义请求为输入的模型RMSE0.138120°。简单因果恒加速度为0.031145°。200ms风险预测可在首次越过目标前约0.1585s发现趋势，但还不能可信预测完整停止位置或比较候选动作。误差范围是开发轨迹经验误差，不是独立校准的不确定性保证，因此没有部署自动预测补偿器。详见[MODEL_PREDICTION_STUDY.md](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/MODEL_PREDICTION_STUDY.md)。

4. **不新增控制器能否修复？** H150在本轮测试条件能修复原运动资格，同时实际下冲减少；它复用合法reference与完整准入/证书。控制变量证据：W1膝reference最大差5.55e−17rad，所有native机器人/人体状态、输出力矩和接触在干预前完全一致；第一次reference变化后才出现物理分叉。由此确认髋时序可因果改变膝响应，但不能分离人体惯性、robot反馈与cuff传递各自贡献。不是“模型已准确预测所以成功”。

5. **PD有独立价值吗？** 本次有界PD使下冲增加0.00275000°，没有价值；不扩大增益搜索。此结论限定于本次门控、参数与接口。详见[PD_ASSIST_STUDY.md](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/PD_ASSIST_STUDY.md)。

6. **新增前馈有独立价值吗？** 本次不重复重力的半幅reference ddq前馈使下冲增加0.01261148°，J_F也增加，没有采纳价值。

7. **组合更好吗？** PDFF真实下冲1.29070728°，仍FAIL，没有显示有用互补。共享总限幅的非线性作用已公开，未使用隐藏调参。详见[FEEDFORWARD_ABLATION.md](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/FEEDFORWARD_ABLATION.md)。

8. **哪种最小侵入？** H150仅扩展原合法终末quintic时序，不增加执行频率、独立反馈状态或电机力矩入口。KD120仍是改变控制律的新候选，而不是原B正式能力。

9. **是否保留降力并通过全部运动资格？** W1 H150 J_F=1402.643211486N·s，保留ER降力收益100.002902%，下冲确实下降；完整task、原safety/motion/receipt/native ownership均通过，未放宽+0.5°门。合格不意味着恢复到B的下冲水平。

10. **是否在未见状态复现？** 在此前未消费的W2合法prefix上，H150也通过全部原资格：J_F=1397.727675N·s，相对匹配B降2.337103%；下冲1.209812°，excursion差+0.115465°。 验证prefix在候选冻结后登记，扫描33个历史START日志确认未消费；执行后不调参。完整证据见[VALIDATION_RESULTS.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/VALIDATION_RESULTS.json)。

11. **是否存在新代价？** H150相对ER的moment积分降低0.045776Nm·s，最大robot力矩从160.540732降到150.329845Nm；髋/膝tracking RMS也降低。相对B仍保留moment积分+5.747%、膝tracking RMS+0.061191°的代价，但满足原门。没有观察到新的接触/执行安全失败。高频速度能量很小但膝≥20Hz占比相对ER略升，不能写成“完全没有高频增加”，也不以此宣称全局稳定。

12. **最终策略。** 将冻结H150保留为当前最小改动的研究候选；不替换正式B，不把ER单独升级。停止本次KD120、PD、FF、PDFF方向。下一步若另行授权，优先识别因果的robot–cuff–Human闭环输入响应与终末作用传递，再研究更早的减速/补偿；不继续追逐0.5°门边界，也不自动开启新包。

## 代价和新状态配对

|方案|moment积分 (Nm·s)|moment峰 (Nm)|tracking RMS髋/膝 (°)|最大robot力矩 (Nm)|膝≥20Hz速度能量占比|
|---|---:|---:|---|---:|---:|
|B|101.253695|15.515712|0.473481 / 0.461755|159.168485|7.405e-07|
|ER|107.118048|15.515712|0.456454 / 0.526051|160.540732|6.534e-07|
|H150|107.072272|15.515712|0.453090 / 0.522946|150.329845|6.542e-07|
|KD120|107.118150|15.515712|0.456371 / 0.526152|160.552941|6.535e-07|
|PD|107.117813|15.515712|0.456433 / 0.526343|160.552616|6.534e-07|
|FF|107.117578|15.515712|0.456151 / 0.525066|160.522114|6.533e-07|
|PDFF|107.117354|15.515712|0.456167 / 0.525221|160.528855|6.534e-07|


≥20Hz指标是完整native速度FFT能量占比，含端点/相位转换影响，属于振荡诊断而非独立稳定门。原raw速度/加速度/jerk、phase/dose、moment、tracking及force峰门均保留。运动资格采用冻结的10%负担门；更严的0%/5%敏感性结果在EXPERIMENT_RESULTS中保留。phase-shape是原协议的诊断量，不是后来豁免的门：H150与B同一时间的phase-shape最大差为W1 13.174°、W2 12.898°，不能将“资格通过”理解成全程逐点复制B或临床等效。

W2的T和ER本身均通过原运动门。H150在W2验证的是进一步减少真实下冲并保持原资格，不能描述为又一次将ER从FAIL修到PASS。W2下冲相对ER减少0.147418°，降力收益保留99.989115%；任务、HOLD及各phase时长未改变。

W2 H150相对ER的代价变化：J_F +0.003641N·s，moment积分 -0.066322Nm·s，最大robot力矩 -13.358648Nm，tracking RMS髋/膝分别-0.004890°/-0.004599°。其moment积分仍比匹配B高5.427%，满足原门；不能把力积分降低理解成所有负担都比B低。

|方案|J_F (N·s)|相对B降力|膝下冲 (°)|excursion−B (°)|全部资格|
|---|---:|---:|---:|---:|---|
|B|1431.175730|0.000000%|0.948582|+0.000000|PASS|
|ER|1397.724034|2.337358%|1.357231|+0.262884|PASS|
|H150|1397.727675|2.337103%|1.209812|+0.115465|PASS|


![开发及未见prefix配对](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/figures/08_development_holdout.png)

![髋膝响应与实际控制输出](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/figures/07_coupling_and_control.png)

## 证据、预算和保护

共21次START/21次END（上限80），其中19个完整运行、2个保留的失败/partial；实际新增native steps=1,457,280，不重复计入fork继承的prefix。所有物理串行；父进程等待子fork时不推进物理。原Dev接口失败和父partial未被覆盖，Ctrl/W2均完成完整cold parent。

所有完成记录由独立算术实现重新从raw计算5ms左端force积分、0.25ms真实状态导数和原motion统计，并逐native step关联实际receipt、力矩、ownership及source age。该复核在单独只读进程执行，但仍由同一研究Agent完成，不声称独立人员审计。全部owned进程退出；START/END闭合；历史文件逐个重新SHA256，Git HEAD/branch/status/cached/unstaged逻辑状态保持原样。最终校验结果见[PACKAGE_VERIFICATION.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/PACKAGE_VERIFICATION.json)，具体记账见[ATTEMPT_ACCOUNTING.json](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_model_terminal_compensation_v1/ATTEMPT_ACCOUNTING.json)。

唯一证据等级为PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION。没有正式LEVEL2、host实时LEVEL3、跨Human、硬件或临床资格。两种执行版本已停止；不自动提交Git或启动下一研究包。

canonical完整原始包：`/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1`。Windows交付目录同时保留报告、图、控制/分析源码、JSON、trace/native派生序列及runtime原始记录；完整manifest与逐文件交付SHA核验保证二者一致。运行时临时文件不作为科学证据。
