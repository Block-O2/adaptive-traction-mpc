# iHEAR Lab — RL-B First PPO Learning Pilot v1

本轮完成独立CPU PPO开发训练与冻结物理评价并STOP。LEVEL_A=PASS；G4_STRICT_PASS=FAIL；LEVEL_C未授予。初始冻结0/1到最终冻结2/2、同一nominal初态下均19.030s完成，提供真实任务学习信号；单seed重复不构成泛化、统计稳定性或正式性能收益。

报告时间：2026-10-20T16:46:06.073564+08:00（Asia/Shanghai）。T0为2026-10-20 15:43，硬截止20:43；19:58后禁止新增训练/大型physics。本轮约63.1分钟，预算未用满不自动扩展。

1. **是否获准独立开发训练**：是，修复后DEVELOPMENT_TRAINING_ALLOWED。旧v2同失败低JF少扣分在准入复核中判FAIL；唯一隔离修复在正式记账前冻结为v3失败成本下限。25组独立reward算术、因果动作接口、原deadline和安全优先检查PASS；414份原物理源码与最近封存包一致，复用已有自然拒绝/fallback/reset及真实物理证据。详见TRAINING_ADMISSION_AUDIT.md。原train.py严格门没有改判，使用独立pilot_run.py开发入口。
2. **G4未解决项**：自然TASK/phase timeout、HOLD失败、绝对安全触发仍NOT_EVALUABLE；原TEST_ONLY协议链PASS不能替代自然证据，也不证明全动作安全不变性。本轮不重定义G4。实际停止原因和所有失败保留在JSONL/ATTEMPT_ACCOUNTING。
3. **实际训练量**：50个已终止并封存的训练episode，1个训练seed，519个真实RL决策，3,502,540个native steps（含原commissioning/recovery；TASK为1,492,540），50次PPO训练调用、200个epochs、272次真实Adam更新。另4个冻结评价episode、76个决策、455,520个native steps；总native 3,958,060。所有训练transition都进入更新，audit tail为0。不是million决策训练。
4. **PPO是否改变动作**：PASS。在595个相同因果观测上，确定性动作平均绝对差[0.28584176301956177, 0.3553462326526642]，最大差[0.37127357721328735, 0.46486803889274597]；冻结actual proposal及native torque receipt另存。权重变化不单独替代实际动作证据。
5. **训练前后runtime任务成功率**：初始冻结0/1；最终冻结2/2；训练采样11/50。最终两次为相同nominal初态重复，不是独立泛化状态，不能声称统计稳定性。初始TASK16.590s，最终[19.03, 19.03]s；PASS。
6. **安全/reward/终止漏洞**：训练前发现并修复上述奖励问题；修复后所有54个episode独立reward/终止/物理安全/causal审计通过=True，未观察到新漏洞或真实超限。自然执行拒绝是保护正常生效，不等同安全违规。安全与奖励完全独立；资源/异常partial不得当任务失败。没有在训练中改配置、缩短任务或用fallback刷分。没有证明未触发边界全状态安全。
7. **原完整匹配资格**：可追溯19.030必要时长通过；完整匹配NOT_EVALUABLE，未授予。PPO_MATCHED_TASK_PASS=NOT_EVALUABLE_FULL_CONTRACT_MISSING；原完整B/H150 scorer缺失，不能以runtime COMPLETE或19.030时长代替task/safety/motion/causal全资格；PPO_FULL_QUALIFIED=NOT_GRANTED_G4_FAIL_AND_MATCHED_EVALUATOR_MISSING。
8. **JF、moment、tracking、motion变化**：初始partial JF=1262.834、JM=73.519；最终首测完整 JF=1451.717、JM=100.680。tracking RMS从[0.5835, 0.6089]°到[0.5112, 0.4729]°。实际速度峰值从[25.837, 25.242]到[25.449, 23.061]°/s，加速度峰值从[102.689, 151.374]到[86.106, 117.376]°/s²，5ms jerk RMS从[524.224, 856.529]到[372.352, 615.811]°/s³。执行区间/phase不同的partial指标不作完整收益或motion非劣宣称。实际q/dq、native/5ms/20ms加速度、native/5ms jerk、terminal误差与overshoot全量数值见BASELINE_COMPARISON及audit/FINAL_INDEPENDENT_RECOMPUTATION.json，未自造jerk门。
9. **与对照相比**：随机初始化冻结失败0/1；固定合法[+1,+1]成功1/1、TASK19.030s、完整JF=1449.840、JM=98.407；最终checkpoint按上述冻结评价。与同条件完整固定策略相比，PPO的JF高0.129%、JM高2.311%；tracking及5ms jerk RMS也更高，未显示力/运动质量胜出。改善属于任务完成能力。固定策略不是B/H150，历史20.165s随机策略与旧功能smoke仅作历史证据，不并入本轮成功率。
10. **学习曲线与继续扩大依据**：PPO_LEARNING_CURVE.md/PNG/PDF和JSONL保留所有采样rollout、entropy、loss、梯度及失败；PASS_EXPLORATORY_RUNTIME_SUCCESS_ONLY。初始冻结0/1到最终冻结2/2、同一nominal初态下均19.030s完成，提供真实任务学习信号；单seed重复不构成泛化、统计稳定性或正式性能收益。 reward上升不能单独证明控制改善。stage5/20/50门均按预先规则保留。
11. **B/H150评价器是否部署**：否，MATCHED_BASELINE_EVALUATION_NOT_READY。已从原ZIP450载荷、三个历史414源文件包与实际manifest审查；缺权威Master/scorer/原motion非劣门及基准身份，最小缺失与迁移方案见MATCHED_EVALUATOR_AUDIT.md。不运行手写近似scorer回归。
12. **下一轮扩大还是先修**：下一轮开展3 seed分阶段CPU PPO开发复核：先验证本轮50 episode结论可重复，再按预注册阶段门有条件延长；保持原任务/安全/资源硬预算。完整scorer与G4未闭合期间仍不得授予LEVEL_C或宣称优于B/H150。
13. **是否值得3 seed×更长CPU训练**：有条件值得开展有界开发复核：真实任务学习与冻结2/2成功提供依据，但应先复现再延长，不直接跳到百万决策；尚不能当正式性能campaign。本轮已STOP，不自动启动下一campaign。单seed小样本不证明统计稳定性。PPO_GENERALIZATION_PASS=NOT_TESTED。

## 独立标志

- PPO_TRAINED: PASS
- PPO_ACTION_CHANGED: PASS
- PPO_RUNTIME_TASK_SUCCESS: PASS
- MATCHED_19_030_TIMING_NECESSARY_PASS: PASS
- PPO_MATCHED_TASK_PASS: NOT_EVALUABLE_FULL_CONTRACT_MISSING
- PPO_FULL_QUALIFIED: NOT_GRANTED_G4_FAIL_AND_MATCHED_EVALUATOR_MISSING
- PPO_IMPROVEMENT_SIGNAL: PASS_EXPLORATORY_RUNTIME_SUCCESS_ONLY
- PPO_GENERALIZATION_PASS: NOT_TESTED
- LEVEL_A: PASS
- LEVEL_B: REAL_PPO_TRAINING_COMPLETED
- LEVEL_C: NOT_GRANTED
- G4_STRICT_PASS: FAIL
- MATCHED_BASELINE_EVALUATION: MATCHED_BASELINE_EVALUATION_NOT_READY
- HOST_REALTIME_QUALIFICATION: NOT_EVALUABLE

## 复核、资源与保护

最后独立重算全部54个TASK完整已执行区间JF/JM与phase积分，通过=True；全部54个episode再次逐native核对q/dq、torque receipt归属、source age及executor关闭，通过=True。训练每episode均在更新前完成独立native/causal/actual Human motion审计。失败区间保留partial身份。最终checkpoint为`checkpoints/episode_050`；每代模型/Adam/RNG hash及跨进程恢复均核对=True。

最低可用RAM 28.44GiB，最低磁盘剩余205.58GiB；单核/单线程/单环境，未租新服务器或改规格。训练摘要与逐episode raw/native/receipt均保留，较大JSON/JSONL无损gzip，独立reader透明读取，未丢弃失败。

70个attempt START/70个END，54个physical episode START/54个END，缺失[]；所有owner join并清理capture。原ZIP与2405份历史受保护文件hash全保持=True；冻结执行合同保持=True。目录无Git checkout，branch/HEAD不可用，未stage/commit/push/merge/reset/stash/clean，没有覆盖历史。最终owned PID退出见PROCESS_EXIT_AUDIT.json。

科学变量仅在记账前更换reward v3并冻结本轮PPO网络/超参数；原physics/目标/ROM/HOLD/deadline/controller/certificate/admission/governor/bridge/lifecycle未更改。正式匹配实验0，未见状态泛化测试0。命令见各guard START.json，实际源码与hash见SOURCE_MANIFEST/FROZEN_CONTRACT_MANIFEST，完整输出见OUTPUT_MANIFEST。

最终状态：STOPPED_PILOT_COMPLETE_UNQUALIFIED。完成后STOP，不启动下一campaign。
