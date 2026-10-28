# Learning 方法审计

**CONFIRMED：本轮真实拟合局部 GP、二次响应面及两个因果输入 stump，没有建立超过最强传统方法的 Learning 独立增量。** 信息、动作改变、完整合格、传统外收益、效率及泛化分别核验；历史训练和离线诊断不计为新 on-policy 部署。

|方法|本轮真实工作|目标信息与动作|完整任务、强传统与独立效果|
|---|---|---|---|
|局部二维 GP|一个 OUT1 父、九动作、五独立目标，15 次核求解|训练留一有信息，前瞻 JM 符号错误；提出真实新动作，与二次面相同|原门通过；ΔJF−.00287948、ΔJM+.00058720，双成本失败。两冻结 prefix 与 SS 仍 JF 微降/JM 微升，未超传统|
|二维二次响应面|六基函数、10 次最小二乘（含留一）|留一误差更小但与 GP 同选，仅一次物理验证|同一失败；更简单方法等效。残差缓冲修订后均保留 phase，无新物理|
|三维 GP/响应面 v1/v2|源码与静态审查，NOT_TRAINED|跨组完整因果等价未证明，不强混数据|NOT_RUN，不能以代码存在代替训练|
|K、geometry stump|三个 OUT0 context、两个一维拟合、八阈值/极性评估、0 Adam|训练均3/3；CF两标签均0，模型各1/2，常数B为2/2|未部署；V1因CFL metadata拒绝NOT_RUN，V2 benefit gate NOT_MET，未来两case NOT_RUN|
|新长期 Critic、Bellman Q/Value、WM/BPTT|NOT_RUN；只读复核历史|旧Critic相对短窗有用，相对强phase同选4/4|旧额外JF=0；本轮新有效性NOT_TESTED|
|PPO reward/梯度/Adam|120 reward重放；60 forward、48 backward、8私有Adam步骤|JM信息及联合裁剪/Adam机械效应确证，全buffer目标非一致改善|0 fresh rollout、0新部署checkpoint；完整公平motion/ownership桥接未闭合，fresh PPO NOT_RUN|
|History Value、ILC、BO、连续trial|历史源码/冻结决策审计；缺主要raw的性能仅SUPPORTED|历史Value常同选固定−.3°，BO多同选B，memory更新仍同选H150|本轮新连续trial更新NOT_RUN，冷fork不是少次患者学习|
|新SAC、DAgger、约束RL|NOT_RUN|历史与接口范围审查|无本轮新训练/部署/泛化结论|

## GP 的合理迭代与停止

**CONFIRMED：** 输入仅为已知动作x3/x7，输出是相对完整phase的JF、JM、两关节native jerk RMS和力模长变化率RMS，没有新加权reward。九标签来自同一真实fork；三维方案因更强状态等价未闭合收窄二维。局部GP/quad拟合及提案进程CPU约.131秒，不含标签采集，不能直接称整体效率优势。[模型/数据身份](models/LOCAL_RESPONSE_2D_V1/SOURCE_DATA_MANIFEST.json)。

**CONFIRMED：** 前瞻失败后复查坐标、单位、符号、标签、原B/phase及control trace均正确。三speed水平逐动作LOO未验证水平之间曲率，远侧列有5ms时序分层；proposal自身没有新duration/guard切换。二次面JM前瞻误差约为调参LOO RMSE的194.62倍。事后四邻点代数吻合是解释，非新fit/独立成功。[独立诊断](agent_reviews/local_response_residual/REPORT.md)。

**SUPPORTED：** 全局曲面与混合执行时序可解释微增益不可靠，未唯一识别物理机制。共同开发残差缓冲后退phase，当前窄域实现没有独立选择价值；不推广为GP/Value普遍无效。暴露点不能回填后重复称独立验证。

## Stump 的区分性检验

**CONFIRMED：** 同时检验估计K与几何两个信息假设，再以交换anthropometry/placement与K/D包的CF分离原三样本相关性。训练中资格与benefit完全重合；CFL原资格通过而髋jerk变差，打破混淆。保持原benefit的无重训诊断中，K对CF资格2/2，但benefit仅1/2，不能改目标救回原负结果。[诊断与来源](analysis/STUMP_TARGET_IDENTIFIABILITY_DIAGNOSTIC_V2.json)。

**CONFIRMED：** CFH前瞻时间/哈希验收通过：K对、geometry错；CFL因WATCH_START mtime比记录开始早.0007708秒被严格拒绝，保持NOT_TESTED，无容差修改/重试/追认。两CF原本就是开发交叉状态；回溯开发门也失败，未改阈值。有效prospective样本数仅1，K与常数B相同。[身份终审](analysis/CAUSAL_STUMPS_FINAL_IDENTITY_DIAGNOSTIC_V2.json)、[关闭的门](freeze/CONDITIONAL_RULE_DEVELOPMENT_GATE_V2.json)。

**SUPPORTED：** 在原五开发context上继续提高训练准确率不提供独立价值；stump与同if阈值数学等效。实际选择接口仅静态准备，两个未来case未安装、CONTEXT_RULE未执行。[准备](agent_reviews/conditional_rule_driver/REPORT.md)、[独立scope](agent_reviews/conditional_rule_independent_scope_v2/REPORT.md)。更丰富动作库上的真实排序仍NOT_TESTED。

四项结论：部分模型/旧Critic学到目标信息，限定范围**CONFIRMED**；本轮Learning未建立强传统外独立增量，**CONFIRMED**；总体计算效率优势**NOT_TESTED**、实际仿真尝试节省**0**；Learning独立泛化成功和患者级验证**NOT_TESTED**。所有标签费用、失败和partial保留。
