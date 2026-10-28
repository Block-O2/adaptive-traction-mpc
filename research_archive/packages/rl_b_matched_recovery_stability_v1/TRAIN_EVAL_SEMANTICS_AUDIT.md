# PPO 训练/冻结执行语义审计

**已复核240训练rollout、51代checkpoint、19历史冻结评价及8新增冻结开发评价。新增训练/gradient update均为0。** 真实代码身份来自447项冻结合同，原始tensor/Adam/RNG及文件SHA均再次核对通过。

训练用未截断对角Gaussian sampled raw action；环境收到 clip(raw,−1,+1)。PPO RolloutBuffer存raw action和其原始Gaussian log_prob，240/240与实际有界proposal一一一致；未发现“用clip动作却配raw log_prob”的身份错配。冻结执行用Gaussian mean后同样clip，不随机采样；policy mean不是施加torque。动作是每个原native planner事件的两关节最大进度分数 `(a+1)/2`，不是50ms或物理步，HOLD动作不允许跳过强制HOLD。

链条为41D因果观测 → raw mean/sample → clip proposal → 单个native waypoint候选 → 原证书/当前态准入 → reference/40ms bridge/governor → 实际6轴torque receipt → 每0.25ms native步。planner拒绝后可能沿旧合法参考/fallback继续；ACTIVATED次数、policy proposal和applied torque必须分别读。完整证据在 `stability/FROZEN_ACTION_EXECUTION_AUDIT.json`、`HISTORICAL_NATIVE_EXECUTION_AUDIT.json` 以及新run的POLICY_SAMPLES/native_rl_requests/runtime_artifacts/native_journals。

三个seed所有历史冻结起始41D观测的SHA相同：`24a9d24aa053acbd1c174ecbac4209f94d6bba66a1f5389cc9d47af61c85a820`。六条050/080轨迹（3个配对）的原native数值准备prefix和config分别完全相同；18次PPO确定性proposal由对应checkpoint重新forward全部复现，另1次固定合法[+1,+1]基线单列核验。没有VecNormalize/running observation normalization；手动单位归一化源码相同。网络没有dropout/BatchNorm，train/eval模式差异不能解释均值策略变化。历史训练reset seed递增但nominal物理初态确定，不能把seed数字不同当独立物理初态。

每完整episode建立变量长度RolloutBuffer；gamma=1、GAE lambda=.95、terminal last_value=0；240份GAE逐元素重算最大误差0，return=advantage+value恒等式核对。有限任务deadline为terminated，不是truncated；资源异常不伪装任务失败。全失败172集总回报均约−11.5，成功回报约35减已测成本。失败potential归零、cost floor1.5已独立按online ticks重算。107个失败episode有正中间reward，48个有正raw advantage；这是局部信用分配的诊断信息，不能等价为失败总目标为正或已证明reward hacking。

训练LR恒3e−4，n_epochs=4，batch_size=16，target_kl=None。65/240集只有1个transition；76/240集的N mod16=1，因此每epoch出现singleton minibatch。SB32.6.0源码仅在len(advantage)>1时标准化；这带来不同rollout长度的梯度权重/噪声差异。实际mini-batch置换、分actor/critic梯度和裁剪前范数均UNAVAILABLE，没有重放训练来伪造。记录的gradient_l2在clip_grad_norm之后测量，接近0.5不能证明裁剪前梯度爆炸。

`train/approx_kl`真实有记录，但该SB3实现每epoch重置列表，输出只聚合最后epoch；`clip_fraction`聚合已执行minibatch且本轮240条全为0。它与“raw action被Box clip”的比例是不同指标。`train/explained_variance`在singleton return方差为0时为NaN，被原runner有限值筛选省略，按实际可用n报告，不补曲线。现有log含entropy、policy/value loss、std；原记录与本轮离线Gaussian 050||080 KL严格分开。

新增随机评价加载并校验原checkpoint RNG后，显式重设两组预注册evaluation RNG；环境仍用同一nominal seed20261020。内存RNG随抽样前进是预期行为，原rng.pt文件/weights/Adam均不变；PPO.learn/train、backward和Adam.step被封锁。每次都保存真实初态hash、raw/mean/std/bounded proposal、准入、force/moment、native/decision数和完整START/END。

随机结果：seed1495656323/cp050=1/2；seed1495656323/cp080=0/2；seed1630784693/cp050=2/2；seed1630784693/cp080=2/2。这仅补充部署语义证据，n=2且已知nominal，不是稳定完成率或独立泛化估计；已观察到的一次成功也不替代冻结门。
