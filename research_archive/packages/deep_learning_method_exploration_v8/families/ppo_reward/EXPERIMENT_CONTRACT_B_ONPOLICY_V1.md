# B-ONPOLICY-V1：未知合法recipe结果上的真实策略梯度（待主Agent批准）

状态：PROPOSED_CODE_ONLY；未启动新物理、未执行初始化/更新。本合同只针对新episode级categorical表示，旧41D native-event PPO桥接仍未闭合。唯一T0与15:25:40Z硬截止沿用全局ACTIVATION，不重置。

## 可证伪问题与数据隔离

历史表已经证明qualified-JF可分，但RF/PPO没有超teacher，并且scale20反而使开发资格下降；严格JM不增和JM目标无当前菜单增量。新研究检验：**真实当前policy采样→未知完整任务回执→更新→冻结argmax**，能否在新增开发条件保持原资格、降低JF，并在两个未见合法条件优于同权限强传统/初始父策略。

主Agent预先登记两个**新开发case**与两个后续**独立验证case**，包括精确JSON/SHA、原方程/任务、causal capture/QA与合法初始状态。可以对已允许虚拟参数包作物理合理插值，但不能给actor插值坐标、case名或真参数。现四case V1迁移结果一经打开即暴露开发，不能拿来改V1后仍称原holdout；若进入V2训练必须重新登记并与V2未见两条件分离。

每开发context先运行原B，原完整资格不通过则保留并停止该case的学习准入，不换容易case补成功。B的完整JF/JM只在其任务完成后作baseline反馈。其余强传统的完整结果不作为当前选择输入。策略仅OUT0 commissioned25，固定顺序及原QA；normalization沿共同父策略固定，不用验证case重估。

## 五recipe动作、共同父及算法对照

由主Agent统一冻结B、LATE_H150、EARLY_H150、LATE_PHASE、EARLY_PHASE五个**完整可执行recipe**，包括底层candidate、原18D、planner/参数映射SHA、early/late权限和后续COMMIT。全部算法与传统得到同权限；actor只采样索引，不插值、不改controller/scorer/guard。真实reject/fallback依原原始语义保存；proposal与applied stream分列。

共同父建议：以V1 `qualified_force_raw/BC_linear_commissioned25` 的冻结三动作policy作同一初始化。确定性lift到五动作时前三logit参数逐bit保留，两个新增phase logit参数各取两个H150行的逐坐标平均；这只是预声明初始化，不注入新case结果。旧三动作概率会因新增分母而变化，须原样报告。若主Agent选择uniform五动作scratch，应在任何新采样前锁定，并保留与lift的机制区别；不同时改初始化、normalization和reward再称单一原因。

四臂：RF-raw、PPO-raw、RF-scaled、PPO-scaled；从相同父权重/normalization/seed开始，各臂独立RNG、rollout、checkpoint。RF每batch单epoch，PPO每batch3epoch、ratio clip .2；manual linear softmax LR=.15、gradient norm≤1；无critic和Adam，不能称解决旧actor/value联合clip。一个batch轮转两个开发context，每context采样两次独立action draw，生成四个真实完整物理attempt；每臂只使用其自己的当前policy数据。各臂首次动作draw可使用相同seed，但分叉后不强求相同后续sample/state/episode长度。

新完整rollout必须真实执行；任何历史表查值、兄弟候选或同recipe前次raw都不能充作本条新on-policy outcome。相同真实fork状态允许串行full-state恢复，但只能称重复同状态的采样，不是新患者。一个物理attempt不同时灌入多个policy arm；原B/强传统控制另列评价，不回流训练。不同selector同动作共用一次执行可用于冻结选择评价，不能为四臂重复记作四个on-policy训练样本。

## Feedback与失败处理

单目标JF：原完整合格时`clip(gain*(JF_B-JF)/max(JF_B,1),-.9,.9)`，否则−1；gain仅1或20，JM不相加。原JM≤1.25等motion/安全资格不变，JM实际增量与所有motion项分别报告；不称双成本改善。当前batch均值作advantage baseline，不对单样本做零方差标准化。

正常原保护任务失败与完整但motion不合格都以原终止原因入训练floor，partial成本不作成功排名。工程失败、丢失原ownership/receipt、资源中断或证据不完整不能冒充任务失败：保留并取消该batch更新，完整记录已消耗物理；不得挑替代好sample。真实硬安全违规依主合同立即停分支。

每条on-policy回执绑定：采样前policy/file行为SHA与version、确切25D输入SHA、RNG before/after、latent categorical action/index/logprob、完整recipe SHA；执行后原attempt START/END、结果文件SHA、native新步数、完整性、原资格及原因、真实activation/receipt/实际applied流摘要SHA。原action即策略选择的proposal，guard作用属于环境转移，不把实际动作改写成另一个actor sample。

## 检查点、验证与资源

四臂按完整batch轮转，主Agent为本实验设置有限local wall（建议90分钟，按实测物理吞吐可审查调整；不是固定episode/梯度上限），每次新batch须有足够剩余时间完成所有四臂、最终冻结验证与封包。实际训练量按已完成对齐batch计；不能让更短失败臂多更新后混称等量对照。若剩余不足，不启动新batch并保存pending。

early为第一次真实completed update后的原样checkpoint；primary endpoint为完整对齐batch序列的最后更新，不能挑best sample/best checkpoint。梯度全零或权重未变如实记录，不延迟early直到“学会”。如果初始batch全失败，先检查回执、目标信号/动作覆盖；不把增加episode当通用修正。已批准的后续机制分支可由主Agent另登记继续，不因本局部窗口结束宣布家族充分否定。

冻结全部early/endpoint及共同父后，在两个预先锁定未见条件上保存全部argmax预测，**然后**运行B及同权限五recipe强传统；任何原B失败保留并停止该case推论。每个独特recipe可共享一次冻结评价物理供selector比较，但不是独立重复、不能声称省试；冻结策略在未知条件的sample稳健性是另一个资格，argmax成功不自动授予。

报告原资格、完整JF/JM、phase时长、tracking、native jerk/wrench等、拒绝/回退、applied差异及baseline增量。未超过B/五recipe开发锁定常数/固定if/nearest或验证时最强合格传统，不能仅凭relative-JF improvement宣称新独立收益。所有训练失败/partial/cold commissioning/新步数/API/资源全记账。

单物理owner、单CPU优化、原模型/原scorer；主Agent统一物理锁、START/END/PID、有限attempt超时及停止。driver模块不启动进程、不构造env、不写旧目录、不自行派发；只有主Agent批准此合同并冻结case/menu/source后可调用其采样/更新函数。
