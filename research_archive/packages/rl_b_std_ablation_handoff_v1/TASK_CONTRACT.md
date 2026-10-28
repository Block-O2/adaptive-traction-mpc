
# iHEAR Lab — PPO Exploration STD Ablation & Autonomous Research Handoff v1

你现在担任iHEAR Lab机器人强化学习研究Agent。

执行环境：
德国Hetzner CCX33，Ubuntu 24.04，
8 dedicated vCPU，32GB RAM，CPU-only。

本轮为有人值守阶段A。
用户之后会安排7–8小时无人值守研究，
本轮必须为其准备可信的科学基线、
实验方向和可恢复执行方案。

预计2–3小时，硬上限T0+3小时。

允许自主：
- 审查历史训练与物理记录；
- 分析checkpoint及动作分布；
- 编写隔离测试和分析工具；
- 修复明确的工程测试缺陷；
- 运行有限真实MuJoCo冻结评价；
- 确定下一轮PPO及Reward研究方向；
- 准备持久化实验调度与交接材料。

本轮不得启动新的PPO训练、
执行梯度更新或修改历史checkpoint。

不要因某项实验失败就提前STOP。
完成一个分支后应继续其他有价值的工作。

━━━━━━━━━━━━━━━━━━
一、恢复最新研究事实
━━━━━━━━━━━━━━━━━━

研究根目录：
/home/hank/ihear-lab/

最新研究包：
rl_b_autonomous_stability_reward_v1/

此前研究：
rl_b_matched_recovery_stability_v1/
rl_b_autonomous_replication_v1/

首先读取：
REPORT.md
REWARD_CANDIDATES.md
REWARD_VERSION_MANIFEST.json
CHECKPOINT_COMPARISON.json
CHECKPOINT_POLICY_DIAGNOSTICS.json
FROZEN_EVALUATION_RESULTS.json
FINAL_FROZEN_SELECTION.json
FINAL_NEXT_RESEARCH_DECISION.md
PACKAGE_VERIFICATION.json

以实际文件及manifest为准，不猜测路径。

最新已确认：

1. 自主研究运行约9.11小时。
2. 390次真实训练attempt、52次冻结评价。
3. 42,865,780 native steps、1760真实Adam更新。
4. H1降低LR仅部分缓解退化。
5. H2跨完整episode聚合rollout，
   两个成功050父策略在已测30/60
   deterministic mean评价中均保持成功。
6. R1在H2基础上修改Reward，
   两父60集mean完整任务均为19.030s。
7. R1/60相对各自原050的完整JF：
   约-0.579%、-0.543%；
   但JM分别增加约1.552%、1.668%。
8. 两个R1/60冻结策略在四条新的
   随机动作流上各3/4完成。
9. 随机失败发生在OUTBOUND初期和RETURN，
   属于原几何准入拒绝，不是实际碰撞。
10. 原Gaussian STD约为1，
    mean+clip与sample+clip执行不同。
11. G4_STRICT_PASS仍FAIL。
12. 新PPO live matched与正式Stage2仍NOT_READY。

这些是历史事实，不是本轮已复现结论。

原成功checkpoint050、
H2/R0 checkpoint060、
R1 checkpoint060全部保留。

━━━━━━━━━━━━━━━━━━
二、建立本轮隔离研究包
━━━━━━━━━━━━━━━━━━

创建：

/home/hank/ihear-lab/
rl_b_std_ablation_handoff_v1/

如果已存在则采用新版本名。

历史研究包、原始checkpoint、
Human/robot/cuff物理、正式B/H150、
原执行合同及GitHub冻结源码只读。

所有新代码、实验、raw和报告放入本轮目录。

禁止：
- 修改原物理和任务；
- 修改原ROM/torque/clearance安全约束；
- 修改planner/certificate/admission规则；
- 覆盖历史checkpoint或raw；
- 修改原B/H150 scorer；
- Git commit/push/reset/stash/clean；
- 自动租赁或升级服务器。

━━━━━━━━━━━━━━━━━━
三、工作A1：Gaussian STD真实消融
━━━━━━━━━━━━━━━━━━

本轮最高优先级。

固定最新R1/60两个checkpoint：

父seed：
1495656323
1630784693

先验证：
- checkpoint SHA；
- policy/critic/Adam/RNG身份；
- Gaussian分布实现；
- log_std及实际各动作维std；
- mean、sample、clip和bounded action语义；
- policy输出与planner实际applied action；
- 冻结评价器的mode与初始化状态。

不要直接假定std一定精确等于1。
报告实际加载的数值。

针对同一固定策略比较：

A：原checkpoint实际STD。
B：仅在冻结评价中临时使用STD=0.2。
C：确定性mean动作，不采样。

STD=0.2为动作分布采样尺度消融，
不是修改网络权重、reward或训练配置。

实际应用时必须区分：
Gaussian原始动作、
边界裁剪动作、
planner接受动作、
实际applied action。

对B不得覆盖checkpoint，
不得改变actor mean、critic或模型参数。

A/B尽可能使用相同预生成标准正态噪声，
通过a=mean+std*z进行配对。

闭环状态不同后，
应继续使用配对的噪声索引，
记录实际状态差异。

不能把相同RNG理解为相同物理轨迹。

冻结评价采用新的预注册动作流，
不能重复把历史2191–2194当作未见测试。

建议每父A/B各4–6条新动作流。
C执行必要的身份回归，
已有完全同身份raw可以复用。

全部新增完整物理attempt上限32次。

先运行最小pilot确认评估接口正确，
再执行已冻结的配对计划。

记录：
- runtime COMPLETE；
- phase时长；
- OUTBOUND/RETURN拒绝；
- completed/partial；
- actual source-age与receipt；
- raw mean/std/sample；
- clip比例；
- applied action；
- cuff JF/JM；
- Human hip/knee q/dq；
- tracking、速度、加速度、jerk；
- terminal overshoot；
- native steps与wall time。

失败partial的JF/JM
绝不可与完整任务直接比较收益。

若完整任务时间不同，
单独报告时长，
不以直接JF差值宣称控制效率改善。

A/B共享物理、安全和任务配置。

注意：
本轮是在评估时改变STD，
不能据此直接证明训练时减小STD更好。

不得从少量试验推断跨患者泛化。

如果STD=0.2仍然失败，
不要调整成0.1、0.3、0.5
进行事后尺度网格搜索。

保留失败反例并继续其他工作。

━━━━━━━━━━━━━━━━━━
四、工作A2：H2/R0与H2/R1对照
━━━━━━━━━━━━━━━━━━

复用已有真实物理证据。

比较：
原checkpoint050
H2/R0 checkpoint060
H2/R1 checkpoint060

要求按相同父seed分别比较，
并核对各自实际任务身份。

重点：
1. 任务保持能力；
2. H2所引入的改善；
3. R1相对于H2是否有额外改善；
4. force降低伴随moment上升的原因；
5. knee tracking与RETURN overshoot；
6. 实际Human jerk与在线运动代理差异；
7. Gaussian采样和mean部署的不一致。

不得把H2/R0和H2/R1
视为只差Reward的严格同轨迹因果对照，
除非实际训练配置、样本及实验设计支持。

不得用不同长度partial积分争优。

输出：
- 逐父策略比较；
- JF/JM及motion trade-off；
- 有直接证据支持的机制；
- 尚无法区分的因素。

判断：
下一轮应优先研究探索尺度、
PPO更新、Reward修改，
还是动作准入附近的协调参数化。

━━━━━━━━━━━━━━━━━━
五、工作A3：自主Reward研究准备
━━━━━━━━━━━━━━━━━━

为之后7–8小时无人值守Agent
准备可执行的Reward研究方向。

允许设计但本轮不训练新的Reward。

现有版本：
R0、R1、R2、R3。

根据真实失败及性能权衡，
提出最多3个有机制依据的候选方向。

优先考虑：
- 更好的合法任务进度信用分配；
- 降低cuff force同时限制moment恶化；
- 改善knee tracking与RETURN overshoot；
- 实际Human速度/加速度/jerk；
- 减少不必要的几何拒绝；
- task success retention。

Reward可以改变训练优化目标，
但不能改变真实任务目标、实际安全执行、
成功身份或正式评价器。

特别注意：
拒绝动作不能通过虚构物理进度获得奖励；
短失败任务不能凭低累计JF晋级；
不能利用未来Human truth或未发生结果。

不得凭不同Reward的总数值大小直接排序。

每个候选方案写明：
- 公式或代码设计；
- 修改动机；
- 与原R1的差别；
- 预期改善指标；
- 可能引起的副作用；
- 最小训练实验；
- 独立评价方法；
- 失败与停止条件。

这部分是下一轮研究提案，
不是本轮科学改善证据。

━━━━━━━━━━━━━━━━━━
六、工作A4：为7–8小时无人值守准备
━━━━━━━━━━━━━━━━━━

复用上一轮已成功运行9.11小时的
持久化campaign/watchdog/failsafe机制。

先只读审查其实现，
不盲目复制旧PID、时间戳、队列或状态。

准备下一轮独立的：

- 实验状态文件；
- job配置模板；
- 版本化reward与PPO配置；
- checkpoint原子保存；
- native steps与episode预算；
- CPU/RAM/磁盘保护；
- wall-clock硬截止；
- START/END账本；
- 阶段性报告机制；
- 最终独立复核；
- 断线后恢复与状态查看入口。

特别避免过去无人值守研究
因普通分支失败而提前STOP。

要求支持：
分支FAIL → 保留证据 → 自主转向下一假设。

只有全局安全、完整性、
身份、资源或停止机制不可控，
才整体阻断执行。

如果Codex推理会话中断，
已经授权的有界job应能安全完成或停止。

但不得让后台程序在无人决策时
无限生成新实验。

准备下一轮约7–8小时的资源预算，
使用上一轮实测吞吐估算，
不要只按理想episode/s计算。

下一轮应优先：
1. 本轮STD结果支持的训练稳定性实验；
2. 最有价值的Reward改写；
3. 候选跨父seed复核；
4. 独立冻结开发/预留动作流评价；
5. 完整JF/JM/motion权衡与失败分析。

即使STD缩小有效，
也必须重新研究训练时的log_prob、
探索分布、PPO ratio和采样归属，
不能直接修改std后沿用旧policy日志概率。

如果STD无效，
下一轮优先探索H2更新与Reward机制。

不要提前开启7–8小时campaign。

━━━━━━━━━━━━━━━━━━
七、自主执行与时间分配
━━━━━━━━━━━━━━━━━━

T0记录UTC与本地时间。

目标2–3小时，
硬截止T0+3小时。

参考分配：
- 0–20min：恢复身份、实验冻结；
- 20–100min：STD真实消融；
- 100–140min：H2/R1对照与Reward准备；
- 140–165min：无人值守调度准备；
- 最后15min：独立复核与交付。

时间可动态调整。

若STD试验提前完成，
不要直接STOP。
继续H2/R1、reward方案和夜间调度准备。

若STD试验受阻，
转向其他可执行工作，
不要反复运行相同失败命令。

最后15分钟不启动新物理。
到硬截止必须停止所有owned新计算。

默认单物理环境，
确有依据最多双环境。

保持至少6GiB可用RAM。
全部新物理attempt纳入START/END。

严禁自动开始新的PPO训练。

━━━━━━━━━━━━━━━━━━
八、最终交付
━━━━━━━━━━━━━━━━━━

至少包含：

REPORT.md
STD_ABLATION_PROTOCOL.md
STD_ABLATION_RESULTS.json
ACTION_DISTRIBUTION_AUDIT.md
H2_R1_COMPARISON.md
REWARD_RESEARCH_PROPOSALS.md
UNATTENDED_CAMPAIGN_PLAN.md
UNATTENDED_EXECUTION_READINESS.json
AUTONOMOUS_HANDOFF.md
ATTEMPT_ACCOUNTING.json
RESOURCE_USAGE.json
PACKAGE_VERIFICATION.json
NEXT_RESEARCH_DECISION.md

最终中文报告回答：

1. 原R1/60真实STD是多少？
2. STD=0.2是否减少几何准入拒绝？
3. 两个父seed的任务完成情况如何？
4. deterministic与stochastic差距是否缩小？
5. JF、JM和Human motion有什么权衡？
6. 是否发生新的实际安全或reward漏洞？
7. H2/R0与H2/R1各自主要贡献是什么？
8. Reward下一步最值得修改什么？
9. 能否安全执行7–8小时无人值守？
10. 是否存在会导致过早停止的调度缺陷？
11. 下一轮推荐哪些实验、各多少episode？
12. 下一轮应使用哪些父checkpoint及版本hash？
13. 哪些结果只是nominal或开发证据？
14. G4/live matched/Stage2还有哪些缺口？

独立报告：
STD_ABLATION_COMPLETE
STOCHASTIC_RELIABILITY_SIGNAL
H2_R1_COMPARISON_COMPLETE
REWARD_NEXT_HYPOTHESES_READY
UNATTENDED_EXECUTION_READY
G4_STRICT_PASS
NEW_LIVE_MATCHED_READY
STAGE2_READY
FINAL_CAMPAIGN_READY

不能把开发评价PASS
升级为正式科学资格。

最终核验：
历史研究包、原checkpoint、
原物理、正式合同和scorer不变；
新实验源码与模型身份明确；
全部native/receipt及JF/JM可复核；
新增START/END全部闭合；
owned训练/物理/观察进程退出；
全部交付及manifest完整。

完成后STOP。

不得自动启动下一轮7–8小时训练，
不得自动开展Stage2或最终Campaign。
