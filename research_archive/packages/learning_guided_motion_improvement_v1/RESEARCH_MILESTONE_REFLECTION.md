# 2026-10-21 — Learning研究方向反思：从算法试错到物理机制驱动的学习优化

记录UTC：2026-10-21T14:26:25.990267+00:00。研究身份：learning_guided_motion_improvement_v1；固定源码起点：`1adb1de177d6f5f32de6d01c4e629cbfae9ce121`。本条为事前追加记录；后续结果只可增补注释，不回写本条假设。新包：`/home/hank/ihear-lab/learning_guided_motion_improvement_v1`。

## 背景与始终不变的目标

最初目标不是证明某种Learning算法能训练，而是在机器人辅助被动康复运动中，保证安全、完整任务和运动质量，进一步降低患者交互负担，并希望通过少数重复运动实现患者自适应改善。研究先后涉及传统MPC与协调优化，E/CEM/COBYLA及10D/18D/H150，Q与Neural Q，IL/DAgger/SAC，ILC/BO/History-conditioned Value，以及scratch PPO、H2、Reward迭代和STD探索。各阶段的患者、初态、动作权限、执行链、目标和评价合同不同，百分比不能直接横向排序。

## CONFIRMED — 可定位的直接证据

- 正式B保留估计Human状态、有限候选MPC、quintic scheduler/governor、current-state admission、FAST反馈及allocator、robot torque与真实cuff/Human动力学的因果执行链。5ms服务、0.25ms native、40ms bridge、100ms lifecycle是不同合同。
- 历史18D开发条件完整JF为1400.697221，相对该条件B的1438.613498 N·s降低2.635613%；新合法prefix原motion为0/4。后续T/H150另有有限合法状态资格与失败，不能覆盖此负结果。D01R历史H150/B为1402.643211/1436.456498 N·s，不能与前一分母混用。
- force_mechanism_waypoint_v3对已执行estimated q/requested torque进行allocator重算，得到−36.527540 N·s，对应实测−37.916277 N·s；这是事后代数机制核算，不是新轨迹事前预测准确率。不可将36.53/37.92写成96%预测准确率或已识别因果中介比例。
- 原Q结构Q(s,p)=a(s)+b(p)的公共state项在候选比较中相消；Neural Q的两个历史测试state未优于linear。动作覆盖、条件交互、V_commit/V_replan标签与数据量仍有缺口。
- History-to-next-trial报告包含有限患者上的history-enabled优于固定B和history-disabled的正证据，也明确未证明超过冻结H150、广泛患者泛化或临床收益；BO/Value只有B首轮到第二轮条件优化，不能称多轮收敛。
- 最新PPO真实完成训练120集、冻结开发24次和最终流12次。选定R1/STD_INIT_0p2在两个既有成功父、相同nominal物理初态各观察6/6；PPO稳定改善、force/moment改善均NOT_ESTABLISHED。R4未获得两父mean共同的JF/JM改善。G4、live matched、Stage2及最终Campaign仍未就绪。

## SUPPORTED — 有限实验支持

- Learning能获得任务能力，某些历史决策产生有限额外改善，传统搜索也能找到低force运动；这些是不同合同内的证据，不是统一算法排行榜。
- 姿态相关gravity与elastic需求是18D降力的重要解释；仅优化smoothness不是主要降力机制的充分解释。局部shape干预有可重复小收益，同时存在motion、moment与离散时序响应的取舍。
- 原执行门与运动资格、动作表达、数据覆盖、优化稳定性和Reward都会影响学习表现。执行成功、低force和完整合格是独立问题。

## HYPOTHESIS — 待检验解释

- 过去偏向更换算法、训练、观察结果；不同算法往往同时改变动作权限、目标与评价合同，使收益难归因。
- Learning潜力大不证明当前可行集合必有大收益；已有小收益也不证明学习存在天然上限。尚不能判断限制主要来自算法、数据、动作表示还是当前物理与约束。
- Q/Value困难可能来自动作覆盖、状态条件排序、价值目标和数据不足。PPO另涉及任务获取、策略退化、探索分布、奖励目标与真实执行不一致。
- 名义物理模型或能解释部分姿态负荷，但闭环tracking、allocator/contact响应、离散准入与motion余量可能需要学习残差。必须用执行前合法输入的验证检验，不能预设。

## DECISION — 本轮研究决策

1. 不继续单纯增加PPO episode或Reward候选。先明确物理能解释什么、接口能改变什么、哪些剩余响应值得学习，以及预测能否帮助实际优化。
2. 保留物理与受约束控制框架，以Learning补充闭环预测误差和约束余量，优化产生新的协调方案，再交给原真实物理与原安全/motion/task门验证。
3. 先做零新物理的机制/事前预测闭包诊断；分清事后重算、准静态预测与完整闭环预测。缺口按实际证据报告。
4. 在相同合法父状态、参数权限和新增物理预算下比较DIRECT_NATIVE、PHYSICS_GUIDED和LEARNING_RESIDUAL_GUIDED；逐臂隔离未公开反馈，登记历史数据优势与代理计算成本。
5. 仅完整合格运动进入正式JF收益。保留所有拒绝、partial、失败及其预算；不放宽原motion门，不按结果更换分母或强父baseline资格。
6. 学习辅助优化若没有超过传统搜索，保留负结果并分析原因；本轮不能预先宣布新方向必然成功。
7. 坚持教授的两个最终问题：单周期能否降低完整合格受力；同一患者少数重复周期能否利用历史进一步改善。几十次仿真试错不能写成新患者两三次即能学会。
8. 这次改变的是研究问题与实验设计，不是宣布PPO、Q或ILC失败或放弃学习。没有自动启动Stage2、长程PPO、最终Campaign或Git推送。

## OPEN_QUESTIONS — 尚未解决

- 新参考执行前，能否准确预测phase/full JF、JM、tracking及原motion门余量？完整闭环预测输入是否可获得，是否存在合法full-state live fork？
- 相同权限、相同新增真实物理预算下，学习残差是否比直接搜索和纯物理代理带来额外完整合格收益？
- 小样本下如何校准不确定性、防止优化器利用模型误差，如何区分新动作收益与学习贡献？
- 不同合法初态、患者和重复周期是否一致，累积探索负担如何计入，论文和真实硬件还缺何种验证？

## 研究时间线与引用

2026-10-14的canonical总结冻结B及18D证据边界；2026-10-17机制研究将重点从单一smoothness移向姿态需求—allocation/feedback—contact；2026-10-19历史到下一trial研究给出有限history因果收益；近期PPO恢复、稳定性、STD/R4开发则区分任务能力与科学收益。以上时间来自现有报告而非推测实际运行时长；本轮不重写旧结论。

- [CURRENT_RESEARCH_BASELINE.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/CURRENT_RESEARCH_BASELINE.md)；SHA256 `ff2547a069c1c8fc5a700746881f5731841b99b019589c69c931820594d1f1d7`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/force_mechanism_waypoint_v3/REPORT.md)；SHA256 `a40867807e70f6319343df5e5166e4e81f6d111bc04931ef70ea53f29e2ccee1`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_overnight_research_retrospective_v1/REPORT.md)；SHA256 `8bf1a534230e71ff6fd910f07d905b5fb64d1a6e807b270ba486d74812c64948`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_history_to_next_trial_learning_v1/REPORT.md)；SHA256 `e3f589633a582f3014530e442454a0022f59eb13c9180485542c8fd65c2328bf`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_training_stability_reward_v1/REPORT.md)；SHA256 `f5a9cfbab6ebcb77cd6c4844143bba5523dc30df8d367776795e850dc0fae6be`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_autonomous_stability_reward_v1/REPORT.md)；SHA256 `976bdd6526786f410252d8689f37ca32c78cb0d4e812855571452deac1c67690`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/REPORT.md)；SHA256 `ddfa19b4c7cf7c2117af04af64d4355aa34ba36275d82461f9972213f500a479`。
- [REPORT.md](/home/hank/ihear-lab/rl_b_autonomous_replication_v1/REPORT.md)；SHA256 `7e2646dab938168397b89eac674fe50052b98c4c600ebc6715b0379e23a77735`。

本条引用的是已定位报告，具体raw与源码闭包将在本轮恢复审计中另行核验；报告存在不自动等于所有原始轨迹已在云端恢复。
