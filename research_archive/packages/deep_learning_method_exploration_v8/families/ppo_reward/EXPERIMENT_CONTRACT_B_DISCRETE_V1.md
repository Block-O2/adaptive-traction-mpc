# B-DISCRETE-V1：完整任务离散协调策略合同（提案，未批准训练）

状态：PROPOSED_FOR_MAIN_AGENT_REVIEW。全局唯一激活见 `../../ACTIVATION.json`；T0=2026-10-27T03:25:40Z，15:25:40Z硬截止不重置。只有主Agent可批准及派发训练、物理和后台计算。本合同的实现/数据整理不等于训练获批。

## 假设与边界

历史41D native-event PPO曾学到nominal任务能力，但两个父seed不稳定，后期退化与随机探索失败仍存在；v7梯度诊断确认value主导联合clip，却没有证明独立clip改善部署。旧thread-owner、两progress-fraction动作和原fullmotion缺失residual receipt的桥接仍未闭合。本合同明确新建**一次episode级协调recipe的categorical policy-gradient变体**，不能称旧41D PPO已修复或已有新on-policy训练。

可证伪假设：在同一原任务和动作库中，因果commissioning信息与完整任务资格约束可学到优于常数动作/简单规则的离散选择；若教师只提供常数标签，或简单规则完全等效，则只能主张教师压缩/机制诊断，不能主张独立学习增量。

## 数据与输入

第一步只整理v7已付费原 `ALL_RESULTS.jsonl`、`history/*_PREFORK_CAUSAL_CONTEXT.json`、`freeze`配置、`attempts/*_RESULT.json`。只读、`python -B`/`PYTHONDONTWRITEBYTECODE=1`，输入逐文件SHA。保留所有失败、partial、metadata失败，禁止以低partial积分排名。原action JSON完整hash；tag相同但权限或recipe不同不能合并。

OUT0输入严格按已审commissioned25：beta11→geometry4→residual10，并保留33项QA。原77D INVALID标记继续保留；不得填未来信息。原QA是可得性审计而非安全/原资格替代。actor禁止读取case ID、path、父hash、真Human/geometry、未来raw/receipt/PASS/成本。父hash及case只用于split与评价分组；同一commissioning/prefix同组，重复候选不扩大独立样本数。

v7数据全部为已见开发证据，leave-one-context只能称开发交叉验证；新独立合法context需主Agent预冻结、先原B合格、一次性打开冻结策略结果。QA无效直接拒绝研究派发，沿原B，不补零。OUT0控制发生在candidate selection前，特征只捕获一次。

## 动作与部署

动作是主Agent冻结的完整合法recipe列表（含family、x/parameters、slot overrides、early/late权限、terminal applicability、候选override及后续COMMIT语义），只选择不插值。统一通过现有v7 `Study.run_branch` / 原planner、certificate、admission、guard、receipt和原fullmotion+scorer。每个新context的B必须第一项且原资格PASS；强教师控制后才能派发学习臂。所有方法得到同动作库和同激活权限。原18D/H150另列跨权限参考时禁止混排为算法收益。

冻结部署为argmax categorical probabilities；随机训练sample逐条保留logprob/action ID。不得报告训练最佳sample为部署能力。receipt/activation用于事后执行审计，不能回流当前选择。动作别名以真实reference/receipt/trajectory检查，不能仅由参数不同假设改变执行。

## 目标和变体（机制不同，非超参数网格）

1. **B-RF**：完整TASK JF单目标REINFORCE；原完整资格、JM不增和motion作为独立门/约束，绝不把失败partial当低cost。以同context同合法B为已完成baseline，学习反馈可用 `r=clip((JF_B-JF)/max(JF_B,1),-1,1)`；不合格固定`r=-1`，并单列原因。该有界值是训练反馈，正式评价仍分别报告JF/JM/资格/motion。必须先检验这个floor是否掩盖所有合格动作差异；若是则修正可用性而非盲目训练。
2. **B-PPO**：同离散动作、同反馈、同数据准入的clipped ratio PPO；完整新rollout采样后有限epoch更新，保存old logprob。与RF比较只改优化机制。episode级一步MDP无需人为长程critic；可选常数/linear baseline，不能冒充解决旧joint clip问题。
3. **B-COMPONENT**：分别JF目标和JM目标的独立策略/lexicographic约束选择，研究目标定义是否改变真实合格排序。禁止未论证相加。若无足够合格排序差异，标NOT_IDENTIFIABLE而非家族失败。
4. **D-BC（对照）**：只以同接口完整原合格教师示范监督动作ID；教师规则及标签优先级在看新验证前冻结。教师等效常数/if规则必须同时执行/报告。BC不被称PPO，不被称超教师。

纯历史全菜单成本表可做full-information expected reward/supervised选择，它**不是fresh on-policy PPO**。仅当每轮确实按当前policy采样并新增完整物理rollout，才记录新policy-gradient训练；复用旧物理标签须标OFFLINE_TABLE_POLICY_OPTIMIZATION，不计新物理、不计泛化。不得以算法名字改变数据身份。

## 切分、强对照、指标

按causal commissioning/context/prefix family分组；同组各candidate不能跨train/test。先报告上下文数、每动作覆盖、合格率、Pareto/排序变化、teacher label熵和常数/if可替代性。数据不足时MLP25D泛化不能从候选数推出。

同权限强对照：B、原最强完整合格fixed recipe、开发集锁定最佳常数动作、最多一个预声明简单if/nearest-context规则、BC教师、未训练policy、RF、PPO。资格层级独立：implementation→target information→actual selected/executed action→完整任务与motion→强基线增量→冻结新context→总成本效率。JF/JM、原motion各项、失败原因、动作拒绝/回退、完整时长、采样/argmax差异逐项报告。

## 资源、身份和停止

所有计算由主Agent统一START/END/账本。离线表提取局部timeout=120s，单CPU，RAM<1GiB；无env/model/dynamics API。若批准纯离线fit，局部timeout=120s、单Torch/BLAS线程、记录forward/backward/update次数、每方法独立checkpoint和RNG。物理预算由主Agent按实测吞吐派发，单物理owner，每attempt采用主闭包有限timeout且截止前留足完整封包时间。不得在本子目录自行启动训练或后台进程。

不因初次失败否定家族。具体失败触发：动作等价→修动作/权限表示；标签无差异→扩大有科学理由的合法条件；常数完全等效→标无独立决策增量；训练分离/部署失败→检查因果输入与argmax/sample差异；原资格失败→保留失败且停止该candidate准入，不改门。未覆盖旧41D独立clip、合法连续动作SAC、长程reward shaping等变体时，家族结论必须NOT_FULLY_EXPLORED。

## 主来源

[PPO原论文](https://arxiv.org/abs/1707.06347)：on-policy采样与clipped ratio；不能把任意历史表重复优化称新PPO rollout。[DAgger原论文](https://proceedings.mlr.press/v15/ross11a.html)：learner-induced状态上的teacher query是其机制，单次OUT0 BC不改名DAgger。[potential shaping原论文](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf)：本一步MDP不靠未来motion/PASS做shaping；若以后多步，需满足potential与终端约定。[SAC原论文](https://arxiv.org/abs/1801.01290)：off-policy与entropy目标不自动解决接口/任务时间问题。
