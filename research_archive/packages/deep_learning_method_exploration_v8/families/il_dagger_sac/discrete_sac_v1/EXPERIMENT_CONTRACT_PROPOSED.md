# D-SAC-TERMINAL-V1：合法真实replay上的终末一步离散SAC候选

状态 **PROPOSED_REAL_TRAINING_NOT_RUN / REPLAY_NOT_GENERATED / SYNTHETIC_MATH_PASSED**。本合同尚未批准真实训练、真实初始化、真实forward或物理；root单独批准的合成数学检查已通过，fixture运算另记。唯一全局T0与15:25:40Z硬截止继承根ACTIVATION；不得重置。源码、文献和合成校验不构成真实训练执行授权。

研究问题：未来B_ONPOLICY真实新物理产生的相同OUT0 commissioning25、相同五完整recipe replay，是否能被离散最大熵actor/Q更有效地复用，改善冻结完整任务选择？本分支不额外采集同一菜单physics，不将旧连续SAC、41D/PPO、旧IL/DAgger或旧表数据混入。数据尚未生成，当前不存在已训练SAC模型。

## 一步结构与目标

一次动作是B/LATE_H150/EARLY_H150/LATE_PHASE/EARLY_PHASE中一个完整承诺recipe，后续原planner/guard/receipt不变；任务结束后进入终止状态。严格 `done=True, next_state=None`，终末Q训练标签为完整单任务return `y=r`，**没有**下一状态Q或熵bootstrap。不能为表现出TD而虚构多步或把中途receipt当新MDP动作。

canonical reward统一重算为：完整且原资格通过时 `clip((JF_B-JF)/max(JF_B,1),-.9,.9)`，正常保护任务失败或完整但原motion失败为−1；JF/JM单列，不标量加权，partial成本不作成功排名。B基准是相同数值输入/真实父的已完成合格真实B。raw/scaled来源arm的原reward保存作身份，但不混合其gain1/20给SAC监督；所有SAC变体使用同一gain1 canonical return。此新目标不覆盖旧双成本或benefit失败。

理想离散actor为 `pi(a|x) proportional exp(min(Q1,Q2)/alpha)`。固定Q、alpha>0时，其argmax与直接Q-greedy相同；自适应温度主要改变分布，无法凭名称创造额外时序信息。本研究是终末上下文决策中的SAC机制候选，不是旧连续机器人SAC/DAgger问题的充分探索。

## 三种机制及强对照

| 变体 | 机制 | 预登记差别 |
|---|---|---|
| VANILLA_FIXED_ENTROPY | 双终末Q＋精确5-action entropy actor | 固定alpha=0.01 |
| ADAPTIVE_TEMPERATURE | 同Q/actor，调整log alpha | 初始alpha0.01；目标熵0.5*log5；log-alpha精确dual梯度；界限[1e−4,1]。此目标是本任务假设，不是作者默认0.98*log5的复现 |
| CONSERVATIVE_SUPPORT | 与vanilla同固定alpha，只允许过去replay有数值邻域支持的动作进入actor期望/部署选择 | 同action在标准化25D RMS半径1.0内至少2条真实反馈；包括已知失败动作的支持计数，绝不借未来资格mask。无支持ABSTAIN，主runner事前登记B回退。它不是CQL理论或实现复现 |

三者从相同BC3→5 actor父、normalization、双Q初始化seed开始，共享同一已冻结合法replay和更新次数。actor固定父logits前三行逐bit保留，两个phase行取两H150行均值；概率因5-action分母改变明确报告。父五recipe本体逐项重算SHA，不信任action_sha元数据自证。

双Q分别MSE拟合canonical terminal return；独立qualification-risk logistic头及完整JF/JM监督分量头，不用风险分数替代原门。线性25D头作为首个可核验实现，容量与目标、状态消融单列；没有偷称深神经SAC。精确枚举actor期望，手写梯度和全局norm裁剪，单步更新函数无自动循环/调度/物理。

必须同replay比较：共同BC父、同双Q直接greedy、同Q直接softmax分布、常数B、开发锁定best fixed、if stump、nearest。Q-greedy/softmaxQ可揭示actor优化是否只是多余近似；SAC若与它们等效，明确报告等效而不宣称独立算法增量。

## Replay准入与身份

只接收未来主物理owner产出的B_ONPOLICY_V1 **DEVELOPMENT_ONLY**真实新attempt，每条保留source policy/version/old logprob、RNG身份、完整recipe及canonical SHA、原25D输入/QA、真实父、START/END、新native步、原ownership/receipt/applied流及原完整资格/终止原因。不同来源policy是合法off-policy行为，不能声称SAC自身采集的on-policy数据。相同attempt跨臂/重复文件只能计一次。

主runner先验证原始文件和所有hash，再冻结白名单record SHA；本纯模块验证白名单行的canonical hash、唯一attempt、split、数值输入和recipe一致。布尔`genuine=True`本身不能代替主owner真实回执核验。固定B控制只用于每条反馈的已完成baseline，不自动扩充SAC训练样本；如需将B控制作为replay action，须另行登记。

工程失败、证据不全、资源中断进入显式excluded ledger，不给−1假任务失败标签；硬安全违规先停分支。正常保护任务失败可以入return/risk，但不能伪造完整JF/JM。manifest应覆盖admitted与excluded实际attempt及各自成本，不能悄悄删除不利记录。新验证条件与4stock V1结果不进入此replay；任何加入都须先改变合同和独立验证身份。

## 审批后才可执行的合同

数据出现后主Agent先审核并批准具体replay/父policy/normalization/5recipe/case/source SHA、开发切分和新冻结验证。先做最小数学机械校验（见MATH_CHECK_PLAN.md），再批准有限单CPU前台训练窗口，建议每轮180s/≤1GiB，全局截止优先。当前不设自动训练轮数或物理额度，不因候选失败判断SAC家族无效。

每次更新记录Q/risk/分量/actor梯度次数与norm、alpha与熵、数据manifest、checkpoint/RNG/源版本、wall/CPU/RSS及错误；同dataset/seed/更新强度公平比较。所有early和endpoint预登记，不能事后选最好checkpoint。仅开发回放不证明控制收益；只有冻结argmax或明确stochastic选择在相同原资格和强传统下通过，才逐级讨论任务、增量、泛化与效率。

replay重用可减少新增模型专属采集，但不能把同一次物理重复计作多个独立rollout，也不能把“本可少做”写成已实现净省试。旧连续SAC/DAgger、真正多步SAC、广域状态充分性、风险校准及硬件均保持NOT_RUN/NOT_FULLY_EXPLORED。
