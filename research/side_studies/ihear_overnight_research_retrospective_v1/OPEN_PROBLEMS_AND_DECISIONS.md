# 当前未解决问题与教授需要决定的方向

## 1. 治疗任务到底允许怎样改变中间髋膝姿态

已有证据：保持endpoint、ROM、phase时长和累计运动量仍可能出现明显phase-shape变化；上轮合格自由参考最大中间姿态差约14.24°。因此“同样到达终点”不自动意味着同样治疗动作。

可选路径A：继续限制原B单值相对进度，接口和已有证书容易审核，但动作族较窄。路径B：允许bounded common-progress及独立pass-through velocity，在已有完整动力学中已有LEVEL1收益，但需教授明确中间姿态范围并重新做接口与执行资格。路径C：更一般连续时间参考，表达更丰富，现有quintic证书未直接覆盖，工程和验证成本明显增加，不能静默增加权限。

需要教授确认：动作治疗意图是具体路径、特定hip/knee协同关系，还是允许一定姿态带宽的完整ROM任务？先定该问题，再谈最优force和动作学习。

## 2. 力、力矩和运动负担怎样权衡

已有证据：旧M2约6%–9%force收益同时提高膝速度、加速度、excursion；强低force约15%仍motion FAIL。上轮2.457489%运动PASS也有部分指标增大并贴近行程上界。这里moment是力矩，不是momentum；不能用力矩积分替代动量。

现10%速度/加速度/指定jerk非劣、0.5°行程差、累计角位移±5%等是冻结比较协议，不是临床阈值。历史FAIL保留；也不据此宣称临床不安全。需要临床/康复依据决定实际速度、加速度、jerk持续暴露、剂量、力矩和phase-shape的优先级。

代价：严格路径/平顺性限制可能缩小force收益；只优化J_F可能增加其他负担；加权单值cost会掩盖指标交换。因此现阶段保存多指标与Pareto候选，选择合格teacher及低force失败代表，避免只报一个百分比。

## 3. 是否把更自由参考迁入正式B

已有证据：原quintic已支持endpoint velocity，但原residual对外主要提供反对称进度delta，不能独立调common/dq。本轮只在隔离side-study使用更丰富意图，物理执行仍保留原B安全链。LEVEL1通过不能直接称LEVEL2，host qualification另需证明。

最低候选接口：在原请求中显式有界common shift和独立hip/knee pass-through velocity，附当前state/model/reference身份、source age、合法范围及拒绝记录。必要工作包括zero等价、全原生command/receipt、current admission、fallback、连续reference证书与host耗时。正式B变更需要用户审阅后另行工作包，本轮不合并。

## 4. 学习器是否真有状态相关的选择空间

已有证据：120D additive linear固定池排序不变；32×32 neural有交互但test仅两个state且regret较差；多数ordinary candidate池未显示ranking inversion。HOLD会抹平很多RETURN状态差，三次注册条件不等于三种有意义decision state。

下一证据应是：在不同合法前向状态中，用同一candidate定义、同一mask/carry和continuation合同，实际测出最佳计划变化；同时包括force与完整motion标签。若没有这种证据，固定偏好加B feasibility是合理强baseline，不能先假设深网必有收益。

代价：前向合法prefix生成新state增加物理attempt；相同状态counterfactual需live-state fork，当前不是durable checkpoint；真正host-clock同状态fork尚未成立。不能只设置Human qpos/qvel“扩数据”。

## 5. 学什么值：V_commit、V_replan还是完整策略值

历史remaining-repetition标签通常是提交合法masked suffix、之后回B。rolling Q可在后续请求改选，执行合同不同。已有OUTBOUND诊断差20.646403N·s，但只有selected action的rolling轨迹，缺全部候选滚动反事实，不能推断真实replan ranking或host误差界。

可先固定V_commit做离线teacher学习，问题清楚但不能承诺rolling personalization；也可设计V_replan反事实，需冻结后续policy并完整前向执行，成本更高。教授需帮助明确论文科学问题和学习目标，避免训练一个cost却评价另一个policy。

## 6. 实时工程贡献与科学主线如何取舍

B已经让plan/source/command/physical step关系可以审计，并获得有限host研究执行；原strict55/R2/FAST qualification仍没有统一通过。微秒Q推理不解决较大native validation/准入开销，不能把毫秒优化流水账作为教授主线。

三个可能主线：可验证的在线执行架构、完整动力学下低力协调优化、少repetition个体化。前两者有实测结构与有限结果；第三者目前尚未证明。建议教授讨论先确定主贡献，再把工程必要机制、动作优化与学习数据作为连贯支撑，而不是同时承诺全部目标已实现。

## 7. 2D Human/cuff与硬件之间的差距

当前是平面髋膝被动Human与冻结robot/cuff/contact模型。真实患者可能主动参与、肌张力/阻抗时变、软组织与袖套滑移、关节轴偏离、三维运动，以及传感器噪声/延迟与真实motor安全约束。仿真模型参数、材料关系和已通过motion protocol都不能推导患者舒适或临床效果。

需要教授确认将来的实验对象、测量和可辨识变量，以及与真实硬件有关的首个受限验证任务。本轮没有硬件控制、患者实验或提交教授，不制造硬件资格。

## 决策顺序与一个下一步

先让教授确认“治疗任务允许的姿态自由度”和“运动质量评价依据”，再设计冻结合同下的不同合法state证据与最小接口迁移验证。当前唯一推荐下一步：用户阅读PROFESSOR_BRIEF.md，用上述两项确认形成下一轮研究合同。本轮结束后STOP，不自动派发新包。


<!-- OVERNIGHT_CONCLUSION_START -->
## 本轮冻结后的结论

原完整动力学中18D开发最好下降2.635613%，新合法prefix条件合格0/4；事先冻结secondary开发下降2.310981%，新条件合格1/4。未用测试改选primary；这是同一Human剩余策略的LEVEL1证据，未迁移原B接口或完成host/临床资格。

下一步仍应先确认治疗允许的中间姿态和motion依据；新状态的速度/加速度/阶段端点失败说明名义开发优化不能直接当可靠teacher。完整逐条件结果见REPORT与VALIDATION_RESULTS，接口变化与负担修复诊断见MECHANISM_ANALYSIS。本轮已停止，不继续训练或自动开启下一包。

<!-- OVERNIGHT_CONCLUSION_END -->
