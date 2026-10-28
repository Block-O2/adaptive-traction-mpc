# v8 方法家族覆盖矩阵

五个家族均完成机制层面的实质探索，整体均为 **NOT_FULLY_EXPLORED**。历史、开发、冻结新条件与后验开发诊断分开解释；合理未测方向保留 NOT_RUN/NOT_TESTED。七层逐家族审查见 [独立科学复核](families/critic_value/analysis/final_scientific_consistency_review_v1/FIVE_FAMILY_SCIENTIFIC_REVIEW_V1.md)。

|家族与核心假设|失败动机与本轮机制变体|数据、接口与公平对照|实际证据、限定否证和未测范围|
|---|---|---|---|
|A Value：成本、排序和风险信息能改善选择|A1完整JF/JM、相对收益、ranking；A2新增覆盖；A3合法25/33/39D；A4原45margin；A5新增partial操作资格标签。历史后续policy标签分库|完整续跑与整case开发留出；冻结后两个新参数。相同五recipe、B/H/phase、stump/线性/nearest。77D缺字段仍INVALID，不补未来数据|开发A3 10/10、A4 9/10，误放减但误拒增，A5主LOCO不变。新A1/A2/A3/A5 JF主各0/2；A4各B2/2零增量。风险校准、TD/Bellman、其他后续policy和更多独立条件未充分探索；不能否证价值学习家族。|
|B PG：奖励、信用分配和共享优化决定有效梯度|三动作离线/五动作fresh分开；RF/PPO×gain1/20；parent/first/last；标量Beta轴；失败floor→余量奖励；global→条件LOO→范数匹配上下文核几何|categorical32fresh/16更新；Beta25started、24完整运动失败/1partial，首批8调用零梯度；旧4unique行为draw的C/L/G12私有步。B/H、初始化半轴、同轴固定网格和全部端点对照，不选best|奖励常数使本批advantage/梯度零已确认；跨条件干扰和有限span迁移有实际分解。六mean heavy门控TASK NOT_RUN、light各自付费合格但JF不胜H，半轴原已合格。categorical12逻辑端点light全B、各1/2。external9pending三scope UNKNOWN隔离；多方向、更多fresh支持与更广条件仍未充分探索。|
|C History：自身过去Trial应改变有价值的动作|冷history action-only/相加/交互/disabled/commissioned；真实T1→T2→T3与boundary；ILC .25/.1；固定±.25；JF/JM和45margin分开的六类BO|冷B历史与同对象持续Trial分开；同阶段B/H/zero、disabled/固定动作/异质prior。known14TASK合格；冻结C4实际两条件。自身早期Trial拟合另计，不称冻结权重|新heavy H/zero partial阻断更新/BO；light14TASK合格、2boundary、reference确有非零变化。ILC小降JF伴随JM增，JF不胜disabled/固定−.25；BO42solve后ABSTAIN、0候选；V2另要求相对H的JM保守不增，弃权不能与ILC混合目标排名。局部作用受支持，历史独有个体化/效率未证；高维历史/更新/增益与更多条件未充分探索。后验heavy持续草案因必要H运动资格不足NOT_RUN。|
|D IL/SAC/Q：覆盖、目标、优化与表达能力可解释退化|BC教师/覆盖、旧新归一化、神经/树/nearest；终末离散SAC actor/Q/soft-Q/保守/温度；精确critic；matched linear/tanh16/ridge、三seed、RETURN/PHYSICAL/RISK、0/25/200|BC48观测10case；SAC合法64row12case offpolicy。相同五动作、同Q greedy/actor/softmax与简单规则；所有seed/端点保留。OUT0外生聚合非真正逐步DAgger；done=True y=r非多步SAC|BC开发10/10与树/nearest同；精确Q拟合更好但7/3/2弱于actor11/1。新BC预登记OLD_NORM主1/2、NEW变体0/2；SAC主与NQ final三seed各1/2。早期B/B不替final。拟合/容量并不足以保证资格；真正逐步DAgger、完整连续/多步SAC、风险校准仍未充分探索。|
|E 学习辅助：合法动作响应和时间域可提供排序/规划信息|绝对/运动学残差/历史、自由展开；共同OUT0动作盲/动作/上下文/paired；窗口/时间曲线；matched8时间点D4/DFull ridge/MLP；真实schema canary|44因果轨迹诊断；48完整TASK同OUT0。未来B轨迹和native仅作监督/评价，不入推理；action-only/强固定H对照。原raw LOCO与live A3-risk组合分开|完整时间域改善部分误差/排序，但DFull paired开发十case同选H、6/10。新D4 raw0/2、DFull raw1/2、DFull+risk0/2，无个体化/省试。真实schema失败与修正保留。合法长时推理、概率ensemble、sampling/CEM与闭环模型优化NOT_RUN，不称PETS复现。|

初期四stock-case仅对事前frozen模型构成测试；后来用于训练的方法视其为开发数据。两个原新参数的全部端点、简单对照和程序在首物理START前冻结，payload此前结构解析，非字节盲测。master七容器、49模型引用、91程序引用不等于独立训练或患者样本；六VAL/FMEAN/C4作业仍是两个条件。

后验开发诊断单列：POSTAPP仅增加因果可选timing适用性标志，旧配方/标签/选择不转移；DEVCAP用原旧开发case/seed及固定B/H/λ1重复/.5/.25/.75/0顺序，完整motion失败继续、partial或true/UNKNOWN hard停止。它们不替代冻结验证，不增加独立条件。

全量变体、动机、接口和缺口：[A](families/critic_value/METHOD_EXPLORATION_MATRIX.md)、[B](families/ppo_reward/METHOD_EXPLORATION_MATRIX.md)、[连续B](families/ppo_reward/continuous_scale_v1/METHOD_EXPLORATION_MATRIX.md)、[C](families/history_conditioned/METHOD_EXPLORATION_MATRIX.md)、[D](families/il_dagger_sac/METHOD_EXPLORATION_MATRIX.md)、[Neural Q](families/il_dagger_sac/neural_q_v2/METHOD_EXPLORATION_MATRIX.md)、[E](families/learning_assisted/METHOD_EXPLORATION_MATRIX.md)。

状态：实际实现/数据/逐动作结果为CONFIRMED；有限机制解释SUPPORTED；未验证修复HYPOTHESIS；未实施NOT_TESTED/NOT_RUN；全部家族NOT_FULLY_EXPLORED。无全局仿真、episode、梯度或模型额度。原滚动矩阵已逐字保存在audit/METHOD_EXPLORATION_MATRIX_BEFORE_FINAL_CONSOLIDATION_V1.md。
