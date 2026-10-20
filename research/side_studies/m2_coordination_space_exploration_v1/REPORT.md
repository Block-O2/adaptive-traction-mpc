# iHEAR Lab — Executable Coordination Space Exploration v1

终态：**DISCOVERY_NOT_VALIDATED**。唯一主要方向：**E. 证据不足，完成特定下一项诊断。**

搜索中 **3/12** 表候选通过主比较条件；选定0.10倍RETURN表，发现阶段J_F下降 **4.1077%**。两个保留seed的J_F收益分别 **+0.1491%** 与 **−2.3865%**（负值表示变差），主接受条件 **0/2 PASS**。两组均未通过加速度条件，第一组另未通过jerk；不得宣称VALIDATED或优于旧M2。Stage D新增物理运行0。

实际新增物理attempt **22/24**（包括失败/无效），完整密集测量 **22**，搜索候选总数 **12**；全部串行，没有内部完整任务rollout、Q/Neural Q训练或persistent Human session。

| attempt | J_F N·s | physical / causal | nonzero native plans | acceptance versus B |
| --- | ---: | --- | ---: | --- |
| 001_search_B | 1499.011395 | PASS / PASS | 0 | baseline |
| 002_search_frozen_M2 | 1355.191763 | PASS / PASS | 7 | velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion |
| 003_return_history_scale_0.025 | 1464.187417 | PASS / PASS | 4 | jerk_deg_s3/p95_abs, jerk_deg_s3/rms |
| 004_return_history_scale_0.05 | 1458.619186 | PASS / PASS | 4 | excursion |
| 005_return_history_scale_0.1 | 1437.436483 | PASS / PASS | 3 | PASS |
| 006_return_history_scale_0.2 | 1451.529516 | PASS / PASS | 3 | PASS |
| 007_return_history_scale_0.35 | 1463.526966 | PASS / PASS | 3 | jerk_deg_s3/p95_abs, jerk_deg_s3/rms, force_peak_N |
| 008_return_history_scale_0.5 | 1464.134764 | PASS / PASS | 4 | velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, excursion |
| 009_both_history_scale_0.05 | 1491.956124 | PASS / PASS | 5 | acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms |
| 010_both_history_scale_0.2 | 1470.783648 | PASS / PASS | 5 | acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion |
| 011_return_flat | 1480.671838 | PASS / PASS | 3 | acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs |
| 012_return_early | 1449.449156 | PASS / PASS | 3 | acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion |
| 013_return_late | 1458.523212 | PASS / PASS | 3 | PASS |
| 014_return_tent | 1474.934655 | PASS / PASS | 3 | acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion |
| 015_validation_2026100902_B | 1492.062899 | PASS / PASS | 0 | baseline |
| 016_validation_2026100902_candidate | 1489.838510 | PASS / PASS | 3 | acceleration_deg_s2/p95_abs, jerk_deg_s3/p95_abs, jerk_deg_s3/rms |
| 017_validation_2026100902_M2 | 1324.332339 | PASS / PASS | 6 | velocity_deg_s/max_abs, velocity_deg_s/p95_abs, velocity_deg_s/rms, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, jerk_deg_s3/p95_abs, jerk_deg_s3/rms, excursion |
| 018_validation_2026100903_M2 | 1401.718362 | PASS / PASS | 3 | velocity_deg_s/max_abs, velocity_deg_s/p95_abs, acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, acceleration_deg_s2/rms, excursion |
| 019_validation_2026100903_candidate | 1498.786257 | PASS / PASS | 3 | acceleration_deg_s2/p95_abs |
| 020_validation_2026100903_B | 1463.851563 | PASS / PASS | 0 | baseline |
| diagnostic_B_repeat_1 | 1484.590114 | PASS / PASS | 0 | baseline |
| diagnostic_B_repeat_2 | 1472.943886 | PASS / PASS | 0 | baseline |

## 历史失败与预注册评价

80条历史行来自13snapshot/4source groups；其中13zero、67nonzero，74ordinary+6历史G-head。严格层速度/加速度/剂量/phase-shape失败数为67/60/67/67；moderate为51/49/59/67；wide为48/47/40/67。分类重叠，不相加作为分母。逐行失败及组合已导出，历史PASS/FAIL不改。

新协议在首attempt前冻结：保留原native安全、force/moment absolute peak、ROM、clearance、任务目标/终点、scheduler/governor、40ms bridge、100ms expiry、current-state admission、ownership及fallback。新增10% raw speed/acceleration/jerk非劣条件（knee/hip），excursion绝对差≤0.5°、累计角位移±5%、端点/phase boundary≤0.5°、整体及各phase时长差≤0.1s；bounded moment integral≤25%、tracking RMS增量≤0.5°、峰值补偿≤5%，同时必须原安全PASS。Phase-shape单独诊断；没有将原历史失败改成新PASS。缺乏绝对临床界，故采用历史moderate比较档并报告0/5/10/25%敏感性；新结果后未变阈值。

## 搜索与验证的科学层级

12个固定注册K3候选覆盖RETURN historical design缩放0.025/0.05/0.1/0.2/0.35/0.5、双phase缩放0.05/0.2，以及RETURN flat/early/late/tent。原始B zero及冻结M2在相同host协议和nominal seed下运行。搜索用实际完整物理任务，不优化旧Q分数；旧Q只作为未更新基线。历史E的1360.602793 N·s仅作不同科学时钟/commissioning参考，未相减。未穷尽30D空间，不能将有限负结果升级为空间无解。

保留seed2026100902/2026100903只在搜索选择冻结后运行；已完成两个三臂比较，结果见VALIDATION_RESULTS.json。 这是完整初始条件比较，不是同中间state counterfactual。各次commissioning模型/初态差异保留；未强行共享不可恢复完整state，也未宣称V_commit=host V_replan。

## 最终十问

1. 现有接口表达相位内、空间进度上的反对称目标分配；raw v2支持任意有限PWL图，K3前端固定三个剩余进度结点、每phase最多五个issued slots；不直接控制物理时长、速度或加速度。

2. 旧ordinary候选库覆盖稀疏，存在尚未搜索的合法连续幅度/阶段/slot/结点组合。是否遗漏有价值方案，只能由本轮实际结果限定回答：本轮未取得可独立验证的成功证据，不能断言不存在。

3. 降低J_F的结果见逐attempt和同seed比较；没有足够证据证明比旧M2更合理的可执行协调策略。

4. 真实knee/hip密集q/dq及导数决定运动结论；独立运动非劣验证未成立。 jerk原始及SG5/21敏感性保留，均非临床阈值。

5. 原moderate筛查67非零行：速度51、加速度49、剂量59、phase-shape67、多类61；可选jerk失败33。Phase-shape使所有非零被完整profile排除，但其余条件也造成大量失败。

6. 反对称归一化目标分配具有真实结构边界；但当前有限候选搜索失败不能证明这些边界是主要性能瓶颈。原生接口比固定K3库更广，需区分候选覆盖和接口表达。

7. 没有引入或运行新自由度；Stage D不具备足够必要性证据，NOT_RUN，不宣称新空间有较好物理解。

8. 合法执行只按native接受、lifecycle ACTIVATED、实际command receipts及对应native steps确认。Proposal、局部feasible或选择日志均不单独证明执行。本轮完整合法执行证据见lineage。

9. 候选覆盖、表达、执行和物理权衡分别保留；当前证据不足以唯一归因，尤其不能将研究motion失败变成人体不安全结论。

10. 本轮没有Q训练。ordinary历史池fixed regret=0与稀疏候选覆盖不支持仅扩大同一库的评分网络；受约束参数生成是可研究的覆盖方向，但没有被本轮验证为成功。先解决比较与收益可重复性，再决定训练目标。

唯一下一方向：E，建立并验证包含commissioning、完整native初态、scheduler/lifecycle与RNG的合法初始状态恢复门限，再对本轮冻结候选与B做匹配完整任务比较；不得拼接近似状态或绕过admission。目标是分离冷启动波动与residual作用，原运动接受协议保持不变。 本轮STOP，不开始训练、接口合并或下一包。

## 执行与保护

指定Python -B依次执行bootstrap.py、preflight_explore.py、campaign_explore.py（内部run_one/review_attempt）、close_explore.py。新增harness只在独立side-study中，host_adapter唯一功能增加是选择registered table coordinator；原B源码仅路径迁移，调度/准入/安全合同无功能改动。Native certificates仍通过原准备及激活路径。Git stage/commit/push/reset/stash/branch切换0；全球RAM/swap/电源/调度改变0，未终止无关进程。曾中断本包只读Git清单，因为Windows目录无自身.git且解析到用户根目录；该失败保留，之后Windows状态限定工作区路径。正式主Git保护与8363文件hash核验见PACKAGE_VERIFICATION.json。

原R2、strict55逐run独立保留，observed FAST不是正式实时资格。本轮无硬件测试。最终报告、原始trace、失败log、候选mask/实际native execution、派生motion和完整任务积分均保留。

![Registered discovery force–motion tradeoff](COORDINATION_TRADEOFF.png)

## 保留seed逐对结果

| seed | candidate gain vs B | acceptance | knee p95 speed / B | knee p95 acceleration / B | candidate J_F − M2 N·s |
| --- | ---: | --- | ---: | ---: | ---: |
| 2026100902 | 0.1491% | acceleration_deg_s2/p95_abs, jerk_deg_s3/p95_abs, jerk_deg_s3/rms | 1.0102 | 1.3073 | 165.506171 |
| 2026100903 | -2.3865% | acceleration_deg_s2/p95_abs | 1.0161 | 1.1657 | 97.067895 |

发现候选005_return_history_scale_0.1相对B的J_F下降61.574911 N·s；各phase delta为{'OUTBOUND': -53.240123768954504, 'HOLD': -0.27694577367254425, 'RETURN': -8.057841915471158}。RETURN-only方案的OUTBOUND差不能归因于尚未发生的残差；commissioning参数最大绝对差为{'model_beta': 0.189438156336023, 'model_residual': 0.0025298752241264336, 'initial_estimated_state': 9.536990059287407e-07, 'initial_reference': 0.0}，真实TASK入口q/dq差亦导出。该混杂限制不能被完整任务PASS消除。

同discovery seed的三次B-zero冷启动J_F为[1499.0113949347622, 1484.5901136146686, 1472.9438855567455] N·s，range=26.067509 N·s，phase ranges={'OUTBOUND': 25.32090625246292, 'HOLD': 0.016389573211490926, 'RETURN': 7.076995779616141}。这两次新增对照在运行前单独注册，使用剩余预算；由已暴露发现结果触发，属于归因诊断，未重选候选、未修改容差或改用最好B作为比较基线。n=3描述性范围不是误差界或统计显著性。

配置中的performance_context沿用旧描述性字符串；本轮新runner没有旧45s资源采样器，不能将该字符串作为资源采样证据。仅保留实际read-only资源观测，不进行资源资格推断。

本轮独立资格轴分母22：{"PHYSICAL_TASK_VALID": {"PASS": 22}, "HOST_EXECUTION_CAUSAL_VALID": {"PASS": 22}, "LEGACY_R2_MATCHED": {"FAIL": 22}, "LEGACY_STRICT55": {"FAIL": 22}}。R2/strict55结果不是研究motion接受条件，也不是正式实时资格。

图表标签经可读性修订，只标记合格发现候选及M2；完整13个非B点及所有排除原因保留在SEARCH_RESULTS。final_polish.py仅更新展示、机械导出清单和资格轴摘要，不修改科学结果、阈值、选择或原始数据。
