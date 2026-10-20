# Early RETURN Motion Repair v1 — 研究报告

**结论：早期 RETURN 时间调整能显著改善 W1 真实运动负担，但本轮没有完整合格候选。** RETURN1 ×1.10/×1.20修复速度p95、加速度峰和jerk RMS；一次追加RETURN4 ×1.20修复加速度p95，仍留下膝excursion失败。因此不提升为新基线，不启动独立prefix验证。

## 来源、冻结身份与证据等级
最近W1包、第二轮协调包、扩展prefix验证包的执行/证据manifest已逐文件核对。120,494个旧文件的初始大小、mtime及SHA见audit/HISTORY_BEFORE.json；最终保护结果以PACKAGE_VERIFICATION.json为准。原B、18D、T、D及所有失败保持。D仍是T基础RETURN2/3各[+0.3,-0.3]°，原选时长和通过速度保持；本轮新组合有独立名称。
证据等级为PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION，同一固定Human/robot模型。没有硬件、临床、跨患者或host实时资格。原p95门是相对同条件完整B的统计门，不能解释为绝对临床阈值。

## 开发配对物理结果
每组完整冷commissioning及合法W1 OUTBOUND0后完整live address-space fork，父等待、子串行。B/T/D每组逐字段复现旧W1，组内full state hash完全相同，父状态保持。正式motion/task/safety/receipt门未修改。

|候选|完整J_F N·s|相对本组B降力|膝v95 °/s|膝a95 °/s²|膝amax °/s²|膝jerk RMS °/s³|膝excursion−B °|原motion|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|W1dev_B|1436.456498145|0.000000%|20.225905|25.247850|132.216831|714.727364|0.000000|PASS|
|W1dev_T|1403.456709761|2.297305%|22.559290|28.552719|72.880957|685.971947|0.534884|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/p95_abs, excursion|
|W1dev_D|1402.234611439|2.382382%|22.359217|28.562887|267.010807|1920.131547|0.543723|FAIL: velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, jerk_deg_s3/rms, excursion|
|W1dev_ER110|1401.221128161|2.452937%|21.310584|28.509736|72.880957|684.644529|0.562763|FAIL: acceleration_deg_s2/p95_abs, excursion|
|W1dev_ER120|1400.242912711|2.521036%|21.305298|28.506620|72.880957|684.446766|0.558489|FAIL: acceleration_deg_s2/p95_abs, excursion|
|repair_ER110_R4_120|1402.644192729|2.353869%|20.673195|25.903085|72.880957|679.781446|0.548596|FAIL: excursion|

以上是各自完整匹配比较；repair组B/T/D与W1dev及旧W1的原始科学轨迹逐字段一致，不用不同背景绝对J_F拼接排名。ER120虽J_F最低仍不合格，不按降力挑选。

## 八项研究回答
1. **能改善，未完全修复。** RETURN1时长干预先消除早期高速度区，完整原速度p95/峰值加速度/jerk门通过；追加RETURN4时长后加速度p95通过，但excursion仍失败。
2. **参考调整真实影响了Human。** 两个RETURN1候选均在11.695s splice前q/dq与D精确一致，11.7005s开始有实际差异；正native steps的receipt-issued reference与独立重建quintic匹配。追加RETURN4的条件对照在15.380s前共101,720个native行的全body qpos/qvel、扭矩、接触、command ID和step index完全一致；其后才出现差异。跨冷父不声称完整地址空间hash相同，组内fork才作该断言。
3. **p95及终末加速度已修复，excursion未修复。** 最后候选膝v95=20.673195、a95=25.903085，分别低于原完整B×1.1参照22.248496/27.772635。全程amax仍在OUTBOUND且不变72.880957；终末请求至任务结束膝amax由D267.010807降至33.740313。膝excursion=111.844568442，B=111.295971976，差0.548596467°，超过原0.5°门0.048596467°。
4. **保留主要降力收益。** 最后候选相对B降力2.353869%，保留冻结D同条件节省量的98.803160%；J_F比T少0.812517032 N·s，比D增加0.409581290 N·s。它是运动修复证据，不是完整合格或最低力候选。
5. **仍有局部代价。** RETURN1单独干预的excursion比D略大；追加RETURN4后仍比D大0.004873644°。最后候选完整velocity TV/acceleration TV/combined jerk RMS相对D变化分别-6.377%/-17.961%/-64.349%。moment integral 107.118048 N·m·s，低于D 108.383202，仍高于B 101.253695。tracking RMS hip/knee=[0.45645400251757623, 0.5260514217326028]°；无新增tracking/absolute safety/causal失败。终末膝amax相对ER110的30.147升至33.740，仍过原门，不能称每个局部峰都单调改善。
6. **没有独立合法状态通过证据。** W2只在开发阶段提前注册并审计此前START未使用；因为没有primary合格，确定性重复与W2均未启动。B/T/D重跑复现不替代新候选的重复或新状态验证。
7. **继续有界时间/速度与停止响应研究，暂不恢复18D+Waypoint联合优化。** 需先在冻结新合同下补齐excursion，全部原门通过、一次确定性重复、至少一个未用于开发的合法prefix配对通过，再考虑在该有限范围恢复联合优化。本轮停止，不自动启动下一包。
8. **为未来Q-learning提供状态、动作和失败反馈定义。** 状态应保留phase/slot、剩余时间、deployable belief与参考q/dq、tracking、可用加速度/历史运动负担、source age、证书/准入和ownership状态。累计范围与高负担记忆不能只用瞬时末段峰代替；实际Human真值仅作离线评价，在线running extrema需来自合法估计并标记不确定性。动作应是现有接口可重新认证的有界时长/内部通过速度因素；不增加planner频率或改gain。反馈先区分非法/未激活、task/safety/causal失败、完整motion失败，再比较完整J_F；保留“峰值已好但excursion仍失败”的分项反馈，不奖励partial或未合格低力。匹配B的未来完整p95只用于离线配对资格，不能作为在线已知临床阈值。本轮未训练。

## 剩余失败与下一项最小实验
最后候选在终末请求16.900s时膝excursion=111.739970225°，尚未超过最终B+0.5°=111.795971976°；到17.066250s才不可逆，实际最小膝q在17.166000s形成。此时终末参考膝通过速度为0，且参考膝位置保持；真实响应仍下冲。新证据把下一缺口收窄到停止/跟踪瞬态，而不是继续单纯延长RETURN1。不能把该相关性进一步断言为唯一allocator原因。
下一包最小实验：先离线核验一个内部通过速度因素（例如末段减速前的膝通过速度缩放），同时保持原D姿态规则与T/18D身份，重建原数学/几何/力学/escape/current-admission证书；只做该因素与当前复合候选的完整同父配对，并保留matched B。若未通过则停止，不降低0.5°门；若通过再冻结、重复并用未使用prefix验证。具体速度数值仍需数学预检，不从当前失败直接宣称已修复。

## 完整积分、时长与其他资格
所有9个候选/对照完整run的task、absolute safety及科学causal receipt均PASS；完整资格由原motion门否决。完整raw与SG5/21敏感性、velocity/acceleration/jerk max/p95/RMS、累计travel、phase boundary/endpoint、ROM、clearance、force/moment峰及tracking均保存在EXPERIMENT_RESULTS.json的complete_metrics和reports/*_MEASURED.json。

|候选|OUTBOUND J_F|HOLD J_F|RETURN J_F|完整moment integral N·m·s|
|---|---:|---:|---:|---:|
|repair_B|719.868083928|54.394340089|662.194074127|101.253694591|
|repair_T|706.697254908|54.394331147|642.365123706|108.211827259|
|repair_D|706.697254908|54.394331147|641.143025384|108.383201881|
|repair_ER110_R4_120|706.697254908|54.394331147|641.552606674|107.118047641|

所有这些run的OUTBOUND/HOLD/RETURN时长为9.005/1.020/9.005s，完整19.030s。phase积分按原left quadrature在实际phase边界裁分，与完整积分闭合；详细force/moment峰及clearance数据保存在完整JSON。

## 尝试、保护与复核
13 START包含两个完整配对组（6+5次）、首组命名/收集错误产生的一个完整B与一个partial父（2次）。partial J_F从未排名；失败报告、START/END和恢复注册保留在audit/INFRASTRUCTURE_RECOVERY.json及audit/dev_INFRASTRUCTURE_STOP.json。该修正只令group与condition显示名一致，seed/prefix、参数、代码manifest不变。
独立复核是同一agent中的分离算术实现，未导入physics/controller/planner，不代表另一个人或agent；已核对全部12个成功END的积分、native导数、dose/ROM/boundary、tracking、receipt扭矩/唯一step归属及来源SHA。最终START/END、owned退出、Git逻辑状态、120,494旧文件元数据/SHA及执行manifest检查见ATTEMPT_ACCOUNTING.json、PACKAGE_VERIFICATION.json。
共同时间轴：figures/W1_early_return_timeline.png（历史）、figures/W1dev_early_return_timeline.png（首组）、figures/repair_early_return_timeline.png（一次修复）；晚段放大见figures/RETURN_deceleration_zoom.png。

原始完整证据位于本Linux包source/results/、motion_series/、output/；Windows目录为review镜像，原始数据保留在canonical路径。

**STOP：无合格primary、无独立验证或基线提升；不训练Q-learning，不自动开始下一轮。**
