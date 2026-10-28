# 最终大规模训练前决策

**NOT_READY_FOR_FINAL_CAMPAIGN**。本轮没有启动最终campaign；READY即使将来成立，也不是自动训练授权。

精确50集预算只有2/3 seed复现；延长至80集后，未达到预注册3/3条件；只有0/3 seed达到初始失败→最终2/2成功；有2个seed由50集冻结2/2成功退回80集0/2，继续训练没有带来单调改进。正式scorer与G4缺口仍阻碍公平资格；没有依据把reward上涨、单seed或nominal重复当正式性能优势。

建议保留41维因果观测、2维有界协调意图和原执行保护作为研究架构；当前Gaussian PPO（MLP32×32）仅作为诊断对照基线，尚未获最终campaign推荐。Stage1复现reward为pilot_v3_failure_cost_floor；PPO lr=.0003、γ=1、GAE=.95、clip=.2、4 epochs、batch16、vf=.5、entropy=0、max_grad_norm=.5。每episode一个完整rollout，128是单episode决策上限，不是固定训练rollout。Stage2不冒称scratch。

三个预注册训练seed：[1106823814, 1495656323, 1630784693]。至少三训练seed全部保留；真正跨患者推广须另冻结患者/初态划分，当前没有证明。明天不能直接启动百万decision训练。可执行准入顺序：

1. 找回原B/H150 manifest、scorer、基准raw与state恢复；逐SHA确认依赖，复现至少一个原条件和已知PASS/FAIL fixture。
2. 补齐剩余G4矩阵（HOLD失败、绝对安全终止及global TASK timeout等）；本轮OUTBOUND/RETURN自然timeout已有证据；恢复完整原motion/fairness/causal门；scientific与host realtime/strict55分别判定。
3. 预注册独立训练/验证/最终测试患者与配置选择规则；通过有界3-seed runtime及配对性能门后，再审批正式episode/decision/native预算。
4. 只有用户批准正式方案后才开始；本包没有可自动启动正式训练的命令。

实测训练程序均摊约62.56s/episode（含审计/checkpoint，含commissioning/recovery）。按本轮长度分布，仅供计划的150集约2.61h，240集约4.17h，不保证更长/更难任务吞吐。决策较稀疏，不能把native步数当RL decision。150集控制上限为19,200 decisions、24,750,000 native预算；加评价需另留24次，每次预留165,000 native。正式大规模预算当前未批准。另给出不可执行的条件草案：3 seed×200集=600集，分50/100/200复核，最多76,800 decisions、99,000,000训练native；另48次评价及7,920,000 native预留。原scorer SHA、基准身份、未见患者划分与性能reward仍为空，execution_allowed=false，不能启动。按当前失败/成功混合成本约10.43h，按完整任务实测成本加10秒开销约15.80h；评价和报告另留约3.26h。这是未来重新授权与准入后的资源草案，不是本轮扩大训练。

CCX33当前单环境最低可用RAM 28.31GiB，未观察到容量瓶颈；没有证据支持现在扩容。若准入完成后确有wall预算需求，应先独立短测最多双环境，保证6GiB余量，再决定是否换机器。没有购买或调整实例。

正式评价必须使用原冻结完整合同与B/H150同mode对照，保留完整JF/JM、实际velocity/acceleration/jerk、tracking、excursion、terminal overshoot、dose、source-age和native receipt。缺任一权威门不晋级。主要风险见FINAL_CAMPAIGN_PLAN.json。
