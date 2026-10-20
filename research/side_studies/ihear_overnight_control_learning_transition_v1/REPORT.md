# iHEAR：控制巩固与Learning过渡 v1

本轮完成控制复现、新prefix完整配对、因果预测审查、实际value训练、冻结策略测试及真实连续重复反馈pilot。H150在部分条件保持约2.3%降力，但存在新状态motion退化。学习是否成功由以下分立标志决定，不能由“模型已训练”推导。

| 验收标志 | 结果 | 精确范围 |
| --- | --- | --- |
| CONTROL_BASELINE_PASS | 8/11 H150条件通过 | 仅逐行指定同一Human/prefix |
| LEARNING_DATA_READY | PASS | 11父状态，44动作行 |
| Q_TRAINED | PASS | 6训练父状态；2验证父状态；终端成本回归 |
| Q_GENERALIZATION_PASS | NOT_DEMONSTRATED | 见冻结规则及实际U策略分支 |
| FEW_REPETITION_LEARNING_PASS | NOT_DEMONSTRATED | 见实际持续plant重复报告 |
| RL_BASELINE_TRAINED | NOT_RUN | 0 P2 episode / 0更新 |
| RL_BASELINE_QUALIFIED | NOT_RUN | 无RL checkpoint资格 |

仅PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION。没有跨患者、硬件、临床、正式Native LEVEL2或host实时LEVEL3结论。SCI模式中的墙钟plan age不构成实时资格；完整原科学因果/receipt链另行检查。全部正式B与历史包只读，无自动Git提交/推送/合并。

## 十七项研究回答

**1. H150是否仍合理？**

是，作为指定条件的冻结研究基线。本轮8/11个cold条件H150完整通过；逐状态资格见下表，不宣称普适回退。

**2. 新状态是否资格退化？**

有。D03的H150/HIP/KNEE excursion失败而ZERO通过；所有后续失败按原门保留，低force不覆盖FAIL。

**3. 请求与预测差异主要证据？**

原PD请求、测得cuff映射和native真实加速度不同；100/200ms原模型及因果残差预测误差已量化。模型没有完整机器人闭环和候选动作输入，不能直接预测完整停止结果。

**4. 哪些控制问题继续，哪些暂放？**

继续关注真实终末响应、资格余量和持续重复执行；暂放没有新假设的增益网格和“全部过冲先归零”的要求。

**5. 是否真正开始Learning？**

是。实际6训练父状态的完整物理数据训练了显式交互value与资格余量模型，并在3个未消费测试状态实时选择并执行。

**6. 合法状态与动作是什么？**

主模型使用七维在线tracking q/dq、测得force/moment、phase elapsed，选四个有界RETURN2/3姿态动作。补充QE在共同OUTBOUND prefix后选择B或四个完整剩余方案，另纳入三个已知处方RETURN-prefix系数。未来truth/B结果只作离线标签。

**7. 是否学到状态相关偏好？**

直接Q测试动作=['H150', 'H150', 'H150']，保守实际动作=['H150', 'H150', 'H150']。Q_GENERALIZATION_PASS=NOT_DEMONSTRATED。补充早期QE选择=['B', 'B', 'B']，EARLY_CONDITIONAL_BENEFIT_PASS=NOT_DEMONSTRATED；资格头切换与force排序分开解释。

**8. 是否真实跨重复改进？**

真实连续plant完成第一次H150、原settle/hold边界、第二次任务的同父B/H150/MEMORY分支。第一次测得force积分用于一次有界value记忆更新，online kernel weight=-1.553142 N·s；第二次选择=H150，实际动作改变=False，相对合格固定H150收益=0.000000 N·s。 首次REP在第二次调用的序列化所有权检查中失败，未推进第二次physics；另保留一次零物理启动日志命名失败。随后以新代码身份修复并完整重跑，原失败、权重与门槛均保留。详见REPETITION_SERIALIZER_REPAIR.md。 FEW_REPETITION_LEARNING_PASS=NOT_DEMONSTRATED。

**9. 相比H150有完整合格收益吗？**

对合格H150取得>0.01 N·s收益的测试父状态=[]；资格恢复状态=[]，二者分开解释。

**10. 哪些失败/数据不足限制结论？**

只有一个Human、少量独立prefix，窗口/动作数不能代替独立状态数；excursion门余量窄，经验误差缓冲不等于形式安全证明，候选存在状态资格失败，跨重复pilot仅是已暴露条件。

**11. 是否启动纯RL？**

NOT_RUN；交付同约束最小PPO baseline合同。

**12. RL是否同约束完成任务？**

未执行，RL_BASELINE_TRAINED与RL_BASELINE_QUALIFIED都不能通过。

**13. 性能与物理样本成本如何？**

P1共83 START，实际新增native steps=6038480，P2=0。固定与value完整结果同父可比；没有RL经验性能排名。

**14. 下一轮最值得研究？**

观测状态/上一运动反馈如何预测资格余量，并在有真实动作差异时选择比全局固定动作更好的方案。

**15. 需要扩展状态/Human吗？**

需要先扩展有科学目的的合法prefix；跨Human必须另建开发/保留Human划分，目前无此证据。

**16. 需要回头改原控制器吗？**

不因本轮负结果自动修改正式B；只有可定位的执行或可行集合缺陷才在新隔离版本修复并重新资格。

**17. 最有希望贡献是什么？**

传统控制提供可执行、安全筛选基础，资格不确定性value利用真实反馈提议协调动作，完整物理证明收益；必须实证超越固定和简单规则。

## 关键完整结果

| 状态 | split | J_F / N·s | 对B降力% | 膝下冲° | 膝excursion−B° | 门余量° | 完整资格 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D01R | train | 1402.643211 | 2.3539 | 1.201029 | 0.474247 | 0.025753 | PASS |
| D02 | train | 1397.727675 | 2.3371 | 1.209812 | 0.115465 | 0.169036 | PASS |
| D03 | train | 1407.619115 | 2.4280 | 1.200755 | 0.503992 | -0.003992 | FAIL: excursion |
| D04 | train | 1400.997173 | 2.3762 | 1.212162 | 0.040321 | 0.245800 | PASS |
| D05 | train | 1400.560740 | 2.3528 | 1.207232 | 0.225299 | 0.202215 | PASS |
| D06 | train | 1403.249981 | 2.4241 | 1.212179 | 0.024403 | 0.135688 | PASS |
| V01 | validation | 1407.432342 | 2.4009 | 1.198528 | 0.603349 | -0.103349 | FAIL: excursion |
| V02 | validation | 1399.234251 | 2.7312 | 1.214568 | 1.063103 | -0.563103 | FAIL: excursion |
| U01 | test | 1402.539930 | 2.3769 | 1.200753 | 0.484103 | 0.015897 | PASS |
| U02 | test | 1401.751387 | 2.3935 | 1.212164 | 0.039925 | 0.210669 | PASS |
| U03 | test | 1403.708688 | 2.3878 | 1.205801 | 0.297959 | 0.202041 | PASS |

| 测试状态 | 实际Q选择 | 完整资格 | 对合格H150收益 / N·s | 合格最优 | regret / N·s | 直接Q最优 |
| --- | --- | --- | --- | --- | --- | --- |
| U01 | H150 | PASS | 0.000000 | H150 | 0.000000 | H150 |
| U02 | H150 | PASS | 0.000000 | H150 | 0.000000 | H150 |
| U03 | H150 | PASS | 0.000000 | H150 | 0.000000 | H150 |

补充的早期方案选择对照（预注册，仅增加三个测试分支）：

| 测试状态 | 实际QE选择 | 完整资格 | 对B收益 N·s | 恢复H150失败 | regret N·s |
| --- | --- | --- | --- | --- | --- |
| U01 | B | PASS | 0.000000 | False | 34.148093 |
| U02 | B | PASS | 0.000000 | False | 34.373705 |
| U03 | B | PASS | 0.000000 | False | 34.337084 |

完整状态、晋级条件与主实验区别见EARLY_VALUE_STUDY.md。

![完整运动、力与力矩](figures/01_control_motion_force.png)

![Learning与原执行链](figures/05_learning_structure.png)

## 审计与交付索引

原始积分和native运动由独立算术进程重新计算，非独立人员复核；历史19个完整任务也重新计算。所有新完整任务、receipt、command torque与native步归属见derived/*_INDEPENDENT.json和audit/RAW_*.json。保护审计、split/model identity、START/END闭合、进程停止及文件manifest见PACKAGE_VERIFICATION.json与ATTEMPT_ACCOUNTING.json。

控制细节见FROZEN_CONTROL_BASELINE.md；耦合预测见COUPLED_RESPONSE_IDENTIFICATION.md与PREDICTION_VALIDATION.json；数据/方法见LEARNING_PROBLEM_DEFINITION.md、LEARNING_DATASET_AUDIT.md、STATE_ACTION_REWARD_SCHEMA.json、Q_VALUE_EXPERIMENTS.md；跨重复见FEW_REPETITION_EVALUATION.md；RL见RL_BASELINE_STUDY.md；下一步见NEXT_RESEARCH_DECISION.md。LEARNING_RESULTS.json保留原冻结策略评价，LEARNING_RESULTS_FINAL.json补充真实重复结论，不改写原实验结果。

完整逐分支成本、平顺性、moment、tracking、剂量及FAIL在EXPERIMENT_RESULTS.json。随机种子/prefix和候选身份见*_PLAN.json/ACTION_SET.json；训练权重见models，实际命令/日志见*_OWNER.json及logs。最终Windows交付与WSL canonical文件哈希一致性单独记录于DELIVERY_VERIFICATION.json。

数值口径保持原合同：完整force/moment采用实际5ms trace时钟的左积分；加速度为0.25ms native真实速度的原二阶边界梯度，jerk为其再梯度，未用平滑压低峰值。独立复核覆盖全任务及各phase指标，不把局部曲线平顺等同整体motion资格。
