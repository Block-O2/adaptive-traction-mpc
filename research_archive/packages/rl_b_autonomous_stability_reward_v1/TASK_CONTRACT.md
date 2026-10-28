
# iHEAR Lab — Autonomous RL Stability & Reward Discovery v1
# 10小时无人值守：PPO稳定性、自主Reward迭代、受控训练与科学评价

你现在担任iHEAR Lab的自主机器人强化学习研究Agent。

运行位置：
Hetzner德国CCX33，Ubuntu 24.04，
8 dedicated vCPU，32GB RAM，CPU-only。

用户将在接下来约10小时内离线。

本轮授权你自主：
- 阅读和分析历史实验；
- 提出并验证研究假设；
- 修改隔离实验源码；
- 调整PPO超参数和rollout机制；
- 自主生成、测试和迭代Reward Function；
- 在合理证据下研究动作参数化；
- 进行真实MuJoCo训练、冻结评价和对照；
- 根据实验结果选择下一研究分支；
- 修复普通工程缺陷；
- 保存checkpoint并恢复；
- 否定失败假设并尝试替代方向。

不需要每次普通科研决策都向用户申请。

本轮不是最终大规模RL Campaign，
而是为其寻找可靠的训练方法和Reward设计。

核心目标：

在原真实robot–cuff–Human MuJoCo物理和
不可变硬安全执行合同下，

1. 改善PPO任务学习稳定性；
2. 防止成功checkpoint继续训练后退化；
3. 自动探索更合理的Reward；
4. 在完整任务成功的前提下改善cuff force、
   moment与Human运动平顺性；
5. 选出下一轮更大规模训练的可信候选。

━━━━━━━━━━━━━━━━━━
一、时间与自主运行原则
━━━━━━━━━━━━━━━━━━

目标研究时间：T0+9至10小时。
硬停止时间：T0+10小时。

T0必须记录实际服务器时间及UTC时间。

不要因为单个实验FAIL、
某个seed失败、某个假设被否定、
某个测试NOT_EVALUABLE，
就提前结束整个研究包。

必须区别：

BRANCH_FAILURE：
仅停止当前失败实验，转向下一候选。

GLOBAL_BLOCKER：
继续运行会造成不可接受的安全、
数据完整性或资源风险，停止受影响操作。

HARD_STOP：
达到T0+10小时，立即停止新任务，
完成安全收尾。

预留最后45分钟进行：
- 停止新训练；
- checkpoint保存；
- 独立评价复核；
- 资源和进程检查；
- 报告及manifest封存。

如果提前完成主要假设，
不要直接STOP。

应在剩余预算内按优先级开展：
1. 候选跨seed复核；
2. checkpoint稳定性与退化边界测试；
3. Reward候选的必要消融；
4. 已支持合法初态的独立评价；
5. 训练/冻结策略一致性诊断；
6. 代码回流准备与科学审计。

这些工作必须有实际信息价值。
不得为了耗满10小时而无意义重复训练。

如果所有安全、可执行且有价值的分支
均已穷尽，允许提前STOP，
但必须解释为什么无法继续，
而不是因普通FAIL直接退出。

━━━━━━━━━━━━━━━━━━
二、现有研究事实
━━━━━━━━━━━━━━━━━━

研究目录：
/home/hank/ihear-lab/

最新研究包：
rl_b_matched_recovery_stability_v1/

历史：
rl_b_autonomous_replication_v1/
rl_b_first_ppo_pilot_v1/
rl_b_g4_closure_ppo_readiness_v1/
rl_b_cloud_g4_repair_v1/
rl_b_cloud_v1/

实际文件位置以manifest为准。

GitHub长期研究源码：

git@github.com:Block-O2/adaptive-traction-mpc.git

固定基线：
1adb1de177d6f5f32de6d01c4e629cbfae9ce121

原B/H150离线scorer已从该commit
在云端独立复现PASS。

历史D01R/W1：

B JF=1436.456498145051 N·s
H150 JF=1402.643211486173 N·s

但当前PPO nominal实验没有原同父prefix
完整matched执行链，
不得直接宣称优于B/H150。

原系统：
MuJoCo robot–cuff–passive Human，
hip/knee双关节，
OUTBOUND→HOLD→RETURN。

原native physics dt=0.25ms。
包含5ms controller、
planner/certificate/admission、
governor、40ms bridge、
100ms lifecycle及causal receipt。

现有PPO：
41D因果观测、
有界连续协调动作、
随机初始化任务学习，
原底层控制和安全执行保留。

历史三seed：
1106823814
1495656323
1630784693

每seed训练80 episodes。

50集冻结成功：
0/2、2/2、2/2。

80集冻结成功：
0/2、0/2、0/2。

两个曾经成功的seed在继续训练后退化。

已确定的执行因果链：

策略均值发生漂移
→ 准入参考发生变化
→ 实际torque和Human运动改变
→ RETURN候选进入预测几何禁区
→ 原合法性检查拒绝
→ TASK ABORTED。

尚未确定唯一优化根因。

历史训练：
LR=3e-4，
target_kl=None，
训练动作Gaussian sample+clip，
冻结确定性评价使用mean+clip。

短episode及singleton minibatch较多，
value解释能力偏弱。

最新诊断表明：
随机采样策略与确定性mean策略
可能具有不同完成能力，
但不能用少量随机成功证明泛化。

历史reward/GAE和已有积分已经复核，
没有发现明确的失败正总回报漏洞。

G4_STRICT_PASS仍为FAIL，
部分极端自然失败路径缺完整证据。

工程开发训练LEVEL_A历史曾通过，
但每个新实验版本仍须检查受影响部分。

Stage2正式资格尚未授予。
最终Campaign未获授权。

━━━━━━━━━━━━━━━━━━
三、独立研究包及保护
━━━━━━━━━━━━━━━━━━

新建版本化目录：

/home/hank/ihear-lab/
rl_b_autonomous_stability_reward_v1/

如目录已存在，使用新版本名。

所有训练、修改、checkpoint、raw、
图表和日志保存在新研究包。

历史包、原始训练checkpoint、
GitHub固定checkout、原ZIP、
正式B/H150及414份科学源码只读。

不修改：
- Human/robot/cuff原物理；
- native/control/bridge/lifecycle时间定义；
- ROM、torque、clearance、contact保护；
- 原planner/certificate/admission安全含义；
- 原任务目标、HOLD和期限；
- 正式冻结scorer及评价阈值；
- 历史控制器及原始研究证据。

不自动Git commit/push/merge/rebase/
reset/stash/clean。

允许研究包内新建隔离源码、
测试、实验版本和可恢复训练工具。

有科学含义的修改必须有独立hash和版本，
不能覆盖旧版本。

━━━━━━━━━━━━━━━━━━
四、启动前安全与工程检查
━━━━━━━━━━━━━━━━━━

先复用历史通过的检查，
不要重新执行没有必要的大型全量审计。

确认：
- 真实MuJoCo耦合物理；
- 硬安全执行仍有效；
- actor没有未来Human truth；
- reward与真实物理dt一致；
- partial失败不因短积分获得虚假优势；
- terminated/truncated/reset正确；
- 安全拒绝和fallback具有正确归属；
- checkpoint/Adam/RNG能够恢复；
- 训练资源和超时保护有效。

如果仅有历史G4自然极端路径NOT_EVALUABLE，
但工程开发训练门具有充分现有证据，
可继续隔离开发实验，
同时保留G4_STRICT_PASS=FAIL。

如果发现新的实际硬安全漏洞、
严重reward漏洞或因果泄漏，
停止受影响训练并修复、重验。

修复失败后可以转向其他安全的离线分析，
不必立即结束整个研究包。

不允许通过放宽安全门获得训练成功。

━━━━━━━━━━━━━━━━━━
五、实验A：H1 PPO稳定性
━━━━━━━━━━━━━━━━━━

优先从两个成功的checkpoint050出发：

seed1495656323
seed1630784693

保留父checkpoint和完整optimizer/RNG。

对比：

Control：
原LR 3e-4。

H1：
LR 1e-4。

如果原历史Control满足相同条件和身份，
优先复用已有真实运行，
不无意义重复计算。

若不能构成严格配对，
记录差异并进行必要的有界Control。

H1每seed首先延续最多30 episodes。

每10 episodes冻结checkpoint。

独立比较：
- deterministic runtime COMPLETE；
- stochastic runtime COMPLETE；
- RETURN rejection；
- actor mean drift；
- policy std/entropy；
- approximate KL；
- clip fraction；
- value loss；
- accepted/applied action；
- 真实Human q/dq；
- force/moment；
- tracking与motion；
- gradient updates及样本成本。

checkpoint050的任务成功不能因
后续失败而被覆盖。

不能通过挑选某一个成功episode，
声称训练稳定。

若H1提供明确正信号，
可以追加有限复核。

若H1失败，
保留反例并继续实验B。

━━━━━━━━━━━━━━━━━━
六、实验B：PPO更新与信用分配
━━━━━━━━━━━━━━━━━━

根据H1结果动态决定是否启动。

重点研究：
- per-episode更新噪声；
- singleton minibatch；
- 短episode advantage；
- critic拟合；
- rollout聚合；
- target KL和更新强度；
- stochastic与deterministic策略差异。

允许自主选择一项主要机制进行修订，
例如跨完整episode聚合rollout，
或者明确的KL约束。

必须有实验假设和对应证据，
不能同时无控制地修改所有PPO超参数。

建立一个明确对照：

BASELINE_CONFIG
vs
STABILITY_CANDIDATE

尽可能保持父checkpoint、
seed、模型、Reward和动作语义一致。

如果发现问题并不来自学习率，
应允许Agent修正研究假设，
不必固守H1。

如果需要修改动作参数化，
只能在独立开发分支中进行，
并重新审查因果、安全和执行接口。
新动作空间与旧空间不可直接宣称同实验。

━━━━━━━━━━━━━━━━━━
七、实验C：Eureka-inspired Reward Discovery
━━━━━━━━━━━━━━━━━━

本轮明确授权Agent自主研究Reward Function。

采用循环：

失败分析
→ 提出Reward候选
→ 编写隔离reward代码
→ 数学/因果/安全审计
→ 真实MuJoCo小规模PPO训练
→ 冻结策略评价
→ reward reflection
→ 下一候选。

允许改进：
- progress shaping；
- phase completion奖励；
- task completion bonus；
- failure/abort penalty；
- cuff force代价；
- cuff moment代价；
- Human运动速度/加速度/jerk代价；
- 合法动作与协调进度的信用分配；
- 奖励归一化与时间积分形式。

可以修改函数表达和权重，
但每一项必须有物理或学习机制解释。

鼓励有意识探索，
不局限于微调原reward系数。

不得修改：
- 真实任务判定；
- 原硬安全；
- 原物理；
- 原正式scorer；
- 实际执行事实和失败身份。

Reward的计算只允许使用该决策时
合法可获得的状态、动作、receipt，
及该转移结束后已发生的真实结果。

不能使用未来轨迹、未来Human truth、
未发生的成功结论或隐藏测试结果
为当前动作提供非因果奖励。

如研究potential-based shaping，
正确处理时间折扣、终止状态和phase边界，
避免循环刷进度奖励。

force/moment基于实际物理积分。
平顺性优先依据实际Human运动，
不是只让网络输出看起来平滑。

失败partial的低JF不能获得完整任务优势。

每一代Reward必须：
- 保存完整源码；
- 保存权重与公式；
- 独立版本ID及SHA256；
- 记录父checkpoint；
- 记录训练配置和seed；
- 保留完整失败和成功样本；
- 保留冻结评价指标。

建议最多3个主要Reward候选版本，
最多2轮有证据支持的反思修订。

如候选存在共同缺陷，
允许适当调整候选数量分配，
但不得变成无界搜索。

不得只根据训练Reward数值选优，
因为不同Reward的数值尺度不可直接比较。

使用共同的不可变评价指标筛选候选。

━━━━━━━━━━━━━━━━━━
八、Reward候选的晋级与淘汰
━━━━━━━━━━━━━━━━━━

按字典序优先级评价：

第一层：
硬安全、合法执行、完整任务完成。

第二层：
任务完成的稳定性及训练后保持能力。

第三层：
完整合格任务中的JF、JM、
Human tracking、velocity、
acceleration、jerk及terminal overshoot。

同一层内可以分析性能权衡，
但低层改善不能抵消高层失败。

候选出现：

A. Reward上涨、实际任务失败增加：
拒绝晋级，分析reward hacking。

B. force降低、moment明显增加：
报告trade-off，不宣称全面改善。

C. 完成率提高、force尚未改善：
可以作为稳定性候选。

D. 完成率保持且force/motion改善：
可以晋级下一轮验证。

E. 所有Reward版本均失败：
保留原Reward作为有效对照，
研究失败机制。

不得为了获得正结果而降低标准。

━━━━━━━━━━━━━━━━━━
九、训练与评价安排
━━━━━━━━━━━━━━━━━━

整轮优先利用已有checkpoint，
避免所有候选从零重新训练。

默认：
- CPU PPO；
- 单物理环境；
- 必要时最多2个环境；
- 小型MLP；
- 正确保存optimizer/RNG。

建议预算动态分配：

H1与稳定性：
约60–120训练episodes。

Reward搜索：
约120–220训练episodes。

候选复核：
根据剩余时间安排。

整轮新增训练：
目标约250–350 episodes。

硬上限450训练episodes。
独立冻结评价最多60次完整物理尝试。
全部attempt，包括提前失败，都计入预算。

native physics总步数设置硬上限
50,000,000，训练和评价合并计入。

训练episode和native步预算是上限，
不是必须耗尽的KPI。

任何运行必须同时受：
- wall-clock；
- native steps；
- episode数；
- RAM；
- 磁盘；
- 异常退出；
- checkpoint周期
约束。

只有安全、科学上有价值的实验才可消耗预算。

每个重要checkpoint评价：
- 真实runtime任务；
- task duration；
- absolute safety；
- applied action及receipt；
- JF和JM；
- Human q/dq；
- tracking；
- velocity/acceleration/jerk；
- terminal overshoot；
- 完成/失败原因。

必须严格区分：
完整任务JF
与
失败partial JF。

不能将不同TASK时长的JF直接比较收益。

B/H150原离线scorer保持只读。
如果新的live matched链仍不完整，
不能赋予FULL_QUALIFIED。

━━━━━━━━━━━━━━━━━━
十、初态与泛化
━━━━━━━━━━━━━━━━━━

优先审查当前runtime是否支持
合法、可重复的初始状态变化。

如果支持：
建立冻结的开发评价初态集合，
并保留独立未见状态。

所有候选遵守相同划分，
不能根据未见测试结果反复修改Reward。

如果不支持：
保持nominal评价，
报告独立初态BLOCKED，
不得用不同RNG的相同确定性nominal
冒充患者或初态泛化。

本轮不擅自改变Human物理或任务定义
来制造所谓泛化。

━━━━━━━━━━━━━━━━━━
十一、自主实验决策机制
━━━━━━━━━━━━━━━━━━

Agent每完成一个实验分支，
更新一次研究状态和剩余预算。

判断：
1. 当前假设是否获得支持？
2. 是否发生任务退化？
3. 是否值得延长训练？
4. 应当修改PPO还是Reward？
5. 是否需要额外seed？
6. 是否存在独立评价污染？
7. 剩余时间最值得执行哪项实验？

决策必须写入：
RESEARCH_DECISION_LOG.jsonl

每次包括：
- 当前证据；
- 被接受或拒绝的假设；
- 下一实验目的；
- 预算；
- 风险；
- 停止条件。

不要因为某个局部研究结论为FAIL，
将整个项目标记STOP。

尤其禁止：

某一Reward候选失败
→ 直接结束10小时工作。

正确行为是：

候选失败
→ 保存数据
→ 分析原因
→ 选择下一个有价值的候选或诊断。

如果没有合格的训练分支，
继续执行不改变科学合同的离线分析、
工具测试、稳定性诊断或数据复核。

不应以无依据的超参数搜索消耗时间。

━━━━━━━━━━━━━━━━━━
十二、无人值守执行可靠性
━━━━━━━━━━━━━━━━━━

启动长训练前，
建立或复用服务器端持久化运行机制。

要求：
- SSH/VS Code断开不导致中间数据丢失；
- 每项job有独立身份与配置；
- checkpoint原子保存；
- 支持断点恢复；
- 支持重新读取研究状态；
- 有wall-time、episode、native步硬限制；
- 有停止和清理机制；
- owned子进程可以被可靠识别。

不要求用户夜间输入sudo或进行人工确认。

如Codex对话无法持续十小时，
已启动的有界实验应尽量通过服务器端
可恢复调度继续运行。

注意：
服务器端训练可持久化，
不代表Agent推理会话一定能持续。

因此必须提前准备：
- 明确的实验队列；
- 各分支的参数及停止条件；
- 可读的状态文件；
- 自动checkpoint；
- 在无人继续决策时安全收尾的机制。

不要让失去监督的程序自动无限训练，
也不要在Agent停止后无限生成新Reward。

如果持久化调度不可用，
仍应执行当前可安全完成的研究，
并准确报告未完成部分。

━━━━━━━━━━━━━━━━━━
十三、资源与故障处理
━━━━━━━━━━━━━━━━━━

CCX33：
8 vCPU，32GB RAM。

保持至少6GiB可用RAM。
监控磁盘余量与增长。

避免不必要的full raw持续写入。
训练保留摘要、transition、
周期checkpoint及必要receipt。
关键评价保留完整无损raw。

不可逆原始研究证据不得删除。

允许删除本轮新产生且可证明
可再生成的临时cache，
但不得删除checkpoint、失败记录
和支持实验结论的唯一原始数据。

一般异常：
记录、诊断、修复或切换分支。

局部实验失败：
仅停止局部分支。

全局立即停止条件：
- 不可控制的物理/安全执行漏洞；
- 未来Human truth泄漏；
- checkpoint或历史证据破坏风险；
- 无法可靠停止训练进程；
- 资源保护持续失效；
- 关键源码身份无法核实；
- 研究运行失去可恢复性且无法修复。

如果是可修复的普通依赖或脚本错误，
不属于全局停止条件。

禁止：
- 修改正式B/H150；
- 修改原硬安全门；
- 覆盖旧checkpoint；
- 自动Git写操作；
- 自动租赁/调整服务器；
- 自动Isaac Lab迁移；
- 自动百万步长期Campaign。

━━━━━━━━━━━━━━━━━━
十四、GitHub源码回流准备
━━━━━━━━━━━━━━━━━━

利用已完成的云端差异审计，
识别适合长期仓库的通用改动：

- force/moment native积分修复；
- phase期限处理；
- checkpoint/Adam/RNG合同；
- PPO记录和恢复工具；
- G4及物理审计；
- 有价值的训练工具改进。

允许在本轮研究包中制作
最小可审阅patch和测试。

但不直接覆盖GitHub主科研源码，
也不自动commit或push。

Reward候选与稳定性实验代码
必须保留独立研究身份，
不自动成为新的正式主线。

━━━━━━━━━━━━━━━━━━
十五、阶段性报告与防提前终止
━━━━━━━━━━━━━━━━━━

在约T0+2h、4h、6h、8h，
分别保存内部阶段性报告：

PHASE_2H.md
PHASE_4H.md
PHASE_6H.md
PHASE_8H.md

每次报告：
- 已完成实验；
- 训练episode；
- native steps；
- gradient updates；
- 已知结果；
- 当前最佳候选；
- 剩余研究预算；
- 下一阶段计划；
- 阻碍及替代路线。

这些阶段性报告不是STOP信号。

不应在2–4小时取得一项负结果后
直接结束全部研究。

如果所有原研究假设提前完成，
在安全与预算允许范围内
优先增加候选稳健性验证，
而不是立即宣布工作结束。

T0+9h15m后不启动新训练。
进入独立复核与交付。

T0+10h必须停止所有owned研究计算。

━━━━━━━━━━━━━━━━━━
十六、最终研究交付
━━━━━━━━━━━━━━━━━━

至少包含：

REPORT.md
RESEARCH_DECISION_LOG.jsonl
AUTONOMOUS_EXPERIMENT_PLAN.md
H1_STABILITY_RESULTS.json
PPO_OPTIMIZATION_DIAGNOSIS.md
REWARD_CANDIDATES.md
REWARD_VERSION_MANIFEST.json
REWARD_SEARCH_RESULTS.json
TRAINING_CURVES/
CHECKPOINT_COMPARISON.json
FROZEN_EVALUATION_RESULTS.json
TASK_FORCE_MOTION_COMPARISON.md
GENERALIZATION_AUDIT.md
RESOURCE_USAGE.json
ATTEMPT_ACCOUNTING.json
SOURCE_RETURN_PLAN.md
PACKAGE_VERIFICATION.json
FINAL_CAMPAIGN_READINESS.md
NEXT_RESEARCH_DECISION.md

每个训练分支保存：
- 源码及SHA；
- Reward完整代码；
- 训练配置；
- 父checkpoint；
- seed；
- PPO更新次数；
- RL decisions；
- native physics steps；
- 成功与失败episode；
- 冻结评价结果；
- checkpoint及optimizer/RNG；
- 必要原始执行证据。

最终中文报告回答：

1. 本轮实际研究运行多久？
2. 为什么选择这些实验分支？
3. H1是否减少PPO退化？
4. H2或其他稳定性方案效果如何？
5. Agent生成了哪些Reward版本？
6. 每个Reward为何被接受或拒绝？
7. 哪些策略保持原runtime完整任务成功？
8. 是否真正降低完整JF？
9. JM和Human平顺性是否恶化？
10. 与父checkpoint相比有什么变化？
11. deterministic和stochastic差异是否改善？
12. 是否存在reward hacking或安全异常？
13. 是否有独立合法初态上的改善？
14. 多seed表现是否一致？
15. 哪个checkpoint、Reward和PPO配置最值得保留？
16. Stage2科学资格是否具备？
17. G4和live matched仍缺什么？
18. 是否值得开始正式大规模训练？
19. 当前CCX33是否仍适合后续研究？
20. 下一轮最值得解决的问题是什么？

独立资格至少包括：

DEVELOPMENT_TRAINING_VALID
PPO_STABILITY_IMPROVED
REWARD_SEARCH_COMPLETED
RUNTIME_TASK_SUCCESS
FORCE_IMPROVEMENT
MOTION_QUALIFIED
G4_STRICT_PASS
NEW_LIVE_MATCHED_READY
STAGE2_READY
FINAL_CAMPAIGN_READY

每项必须有证据和范围，
不能因为开发训练成功就授予正式资格。

最终必须核验：
- GitHub原固定commit不变；
- 原B/H150 scorer及合同不变；
- Human/robot/cuff物理不变；
- 原硬安全不变；
- 历史checkpoint不变；
- reward和训练版本可追溯；
- 完整及partial积分正确；
- native/receipt实际执行一致；
- train/dev/holdout界限清楚；
- START/END闭合；
- 全部owned进程退出；
- 报告与manifest完整。

最后STOP。

即使找到非常优秀的Reward或PPO配置，
也不得自动启动最终大规模Campaign。
不得自动执行下一研究包。
