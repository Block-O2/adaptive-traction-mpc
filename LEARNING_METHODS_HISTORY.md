# Learning 方法历史：实际实现、结果与重启条件

归档结论是：Learning 学到了部分任务、成本、资格和历史响应信息；目前没有证据表明它在同权限、完整原门和强传统对照下稳定胜出。此结论限定于已运行变体，不是否定PPO、Value、ILC、BO、SAC或World Model整个家族。

`CONFIRMED` 表示可由现存源码/冻结工件支持的事实；`SUPPORTED` 表示原报告支持但缺完整raw或仅有限机制支持；`NOT_RUN/NOT_TESTED` 保留未实施范围。历史审计 PASS 不等于本次从远端重建 PASS；后者见 [ARCHIVE_VERIFICATION.md](ARCHIVE_VERIFICATION.md)。本文件引用的实验均为 MuJoCo 仿真，没有真机训练、真实患者试验或临床结论。

## 1. 版本地图

|阶段|研究目的与实际新工作|实际结果及边界|
|---|---|---|
|早期cloud/G4|建立native-event两fraction Gym/PPO与终止/receipt合同|初始cloud为部署/功能验证，不能将零更新写成训练；后续独立pilot才真实训练|
|first PPO pilot / multiseed|检验从随机策略学会完整原任务；继续训练稳定性|50集pilot有任务信号；三seed后续训练非单调退化；完整强B/H150评价桥有缺口|
|更早overnight / history-to-next-trial|七特征ridge Q、early-value、连续kernel memory；history ridge/ILC/约束BO|有真实实现与冻结决策；部分主要weights/raw缺档，报告性能不可冒充本次复算|
|v1 learning_guided_motion_improvement|固定H150附近2D，同预算pattern/physics prior/GP residual|三臂都找到局部合格降力；GP未严格超过传统|
|v2 autonomous_coordination_learning|新增modal8、响应模型、GP选择及scratch PPO|真实改变参考与决策；PPO有合格均值；GP/PPO未超本轮强传统|
|v3 representation_execution|判断新权限还是新算法；原guard非光滑机制|有源码/物理构造证据；无新学习训练，不应当作另一RL失败|
|v4 constraint_geometry_learning|双端点解析约束、L/D权限因子、传统/学习分支判断|新guard未物理替换；传统显式分支模型已有局部预测力；无学习额外收益|
|v5 smoothness_critic_research|HANDOFF/PATTERN/COMPOSE；真实短窗/完整tail；首次长期成本Critic|传统平顺性有效且有JF/JM取舍；critic局部纠正0.5s排序但不胜固定动作/1s|
|v6 smoothness_critic_integration|累计历史、量纲缩放、风险/OOD、匹配后续策略|主四prefix critic原门4/4，相对强phase实际决策差异0/4|
|v7 autonomous_learning_smoothness|强传统继续收束；GP vs二次面；commissioning stump；旧PPO梯度/奖励桥接|小型真实拟合与离线Adam诊断；0 fresh RL rollout；没有新可部署PPO续训|
|v8 deep_learning_method_exploration|五家族机制对照、新categorical rollout、Beta、真实连续ILC、terminal SAC/Q、BC、长时代理|有实质实现与两新参数条件；仍无独立强传统增量或净省试；各家族NOT_FULLY_EXPLORED|

入口：[v1](research_archive/packages/learning_guided_motion_improvement_v1/REPORT.md)、[v2](research_archive/packages/autonomous_coordination_learning_v2/REPORT.md)、[v3](research_archive/packages/representation_execution_v3/REPORT.md)、[v4](research_archive/packages/constraint_geometry_learning_v4/REPORT.md)、[v5](research_archive/packages/smoothness_critic_research_v5/REPORT.md)、[v6](research_archive/packages/smoothness_critic_integration_v6/REPORT.md)、[v7](research_archive/packages/autonomous_learning_smoothness_v7/REPORT.md)、[v8](research_archive/packages/deep_learning_method_exploration_v8/REPORT.md)。下述数值沿各原包评价合同，不能跨权限拼成排行榜。

## 2. PPO 与策略梯度

### 2.1 native-event 41D PPO：确实学过任务

目的：让actor在原planner request时选择两关节合法推进比例，减少手工协调。输入41D因果状态，动作两fraction，经原planner/certificate/admission执行；初始随机32×32 MLP，无教师权重。奖励使用进度势能、完整成功/失败、JF和估计加速度积分；pilot v3在训练前冻结失败成本下限，避免失败通过少做动作少扣成本。

真实pilot为50个已终止训练episode、519个RL决策、272次Adam更新；最终确定性nominal重复2/2完成19.030s，训练采样11/50完成。固定同接口 `[+1,+1]` 亦可完成，PPO未在力或运动质量上胜出。原完整B/H150 scorer当时缺失，不能把runtime COMPLETE写成完整motion资格。[报告与数字](research_archive/packages/rl_b_first_ppo_pilot_v1/REPORT.md)、[冻结奖励合同](research_archive/packages/rl_b_first_ppo_pilot_v1/REWARD_AND_TASK_CONTRACT.md)、[真实训练入口](research_archive/packages/rl_b_first_ppo_pilot_v1/pilot_run.py)

后续三seed各80集，总240训练attempt；两个seed由50集冻结2/2退到80集0/2，最后三seed均0/2。退化并非“训练越久越好”；执行拒绝、reference回退、采样STD、有限rollout和优化/奖励因素分开分析，唯一优化根因未识别。[multiseed原表](research_archive/packages/rl_b_autonomous_replication_v1/REPORT.md)、[050/080诊断](research_archive/packages/rl_b_matched_recovery_stability_v1/REPORT.md)

后续H1/H2_AGG64、STD、R1–R4和retention做过真实继续训练与固定回放，不能统称未训练。`rl_b_std_ablation_handoff_v1` 本身是28次冻结物理评价、0梯度；`rl_b_training_stability_reward_v1` 是120集训练和524次Adam。统计单位分别是episode、native-event决策、update epoch和Adam step，不可相加。[STD对照](research_archive/packages/rl_b_std_ablation_handoff_v1/REPORT.md)、[reward/稳定性](research_archive/packages/rl_b_training_stability_reward_v1/REPORT.md)、[自主390训练attempt及各分支](research_archive/packages/rl_b_autonomous_stability_reward_v1/REPORT.md)

v7 证实旧R1两条raw的physical/scientific评分和NATIVE指标可桥接，但完整fullmotion analyzer缺legacy executed-residual receipt后停止，compare未完成。空reference记录不能补造ACCEPTED行。新41D完整公平评价和fresh续训仍不能自动宣称通过。[桥接与原失败](research_archive/packages/autonomous_learning_smoothness_v7/LEARNING_CONTROL_INTERFACE_GUIDE.md)

### 2.2 v2 modal8 PPO：不同问题与权限

在一个固定合法context上，每个完整任务只选择一次8维tanh Gaussian。真实训练64任务/64高层决策、31个epoch；mean/std/value三个Adam参数组共93次更新。reward对完整合格任务为 `5*tanh((JF_strong−JF)/5)`，强锚约1400.089728，不能错用约1436的B制造“reward饱和”解释。精确变换logprob、批behavior和RNG均保存。

末次mean `PPO_SCRATCH_MEAN_0064` 完整合格JF=1399.918272、JM=107.492306；训练sample最好合格JF=1398.995849。sample极值不是部署mean，mean小幅胜旧strong不等于胜本轮传统最佳1398.034615。[源码](research_archive/packages/autonomous_coordination_learning_v2/source/acl2_ppo.py)、[合同/结果](research_archive/packages/autonomous_coordination_learning_v2/REPORT.md)

v5只评价冻结旧PPO，没有新训练；它在两个预登记prefix原门均通过，说明旧策略有有限作用，但出程modal建议会被certificate屏蔽，存在参数不同执行相同。[执行机制](research_archive/packages/smoothness_critic_research_v5/PPO_FROZEN_EXECUTION_MECHANISM.md)

### 2.3 v8 categorical 与 Beta

OUT0 commissioned25选择完整recipe：离线168个小fit与fresh on-policy分账；fresh categorical四臂比较REINFORCE/PPO、gain1/20，32个付费新policy rollout、16次参数更新。gain20放大成功收益但失败floor固定−1，不是纯全局尺度变换；RF1 epoch与PPO3 epochs的差异不能全部归于clip。[实际分支](research_archive/packages/deep_learning_method_exploration_v8/PPO_REWARD_RESULTS.md)、[纯实现](research_archive/packages/deep_learning_method_exploration_v8/families/ppo_reward/categorical_policy.py)

连续Beta仅控制标量λ。首批16条完整样本全motion失败，reward均−1，减批均值后advantage/梯度/权重位移均0；8次更新调用不是8次有效学习。余量奖励、条件LOO、上下文核几何修正采用同四个旧行为样本的私有离线反事实，恢复非零梯度，不是新on-policy或控制收益。第二批partial、三项安全scope UNKNOWN和external pending保留，未提交第二批更新。

新轻载六个余量mean端点全部完整合格，但固定λ=.5本就合格；其JF约1333.01–1333.06仍弱于同条件固定H150的1323.213957，JM另列。不能以训练梯度变化替代独立增量。[新端点与失败源](research_archive/packages/deep_learning_method_exploration_v8/PPO_REWARD_RESULTS.md)

未充分探索：多方向连续策略、真正多决策credit assignment、完整41D公平桥接、独立患者/状态覆盖、可行域丰富的on-policy数据、校准风险的约束策略。当前结果不授权新训练。

## 3. GP、BO 与学习辅助优化

v1假设：名义inverse-dynamics prior能排序大方向，局部GP学习闭环差值，可能在相同真实预算下更快找到合格低JF。每臂独立完成反馈，GP目标为JF/JM残差和worst motion ratio修正，固定same-parent context。共同四点分别真实执行，不能归于学习。

每臂20次，固定前12为主比较；GP与physics prior同最佳JF=1400.089728，均未严格超过彼此；H150为1402.643211。GP预序JF RMSE=0.324837，小于锚定名义0.941323 N·s，却没有额外控制收益；motion有错误接受，区间未校准。[实现](research_archive/packages/learning_guided_motion_improvement_v1/source/optimizers.py)、[合同](research_archive/packages/learning_guided_motion_improvement_v1/EXPERIMENT_CONTRACT.md)、[结果与候选ID](research_archive/packages/learning_guided_motion_improvement_v1/REPORT.md)

v2在modal8自己的历史上选动作，GP改变14/16次同池选择，确有决策能力；同32候选预算，GP最佳1399.188323、pattern最佳1398.549121。传统motion-margin backoff得到1398.034615，不归于GP/PPO。v5四维同12次预算，pattern12/12原合格，BO11/12，冻结平顺性S最优分别约.953545/.964078；BO最佳等于共享HANDOFF规则。v7 GP与二次面同选，前瞻JM方向错，不能凭拟合误差声称学习独有价值。[v2](research_archive/packages/autonomous_coordination_learning_v2/REPORT.md)、[v5同权限优化](research_archive/packages/smoothness_critic_research_v5/OPTIMIZATION_COMPARISON.md)、[v7审计](research_archive/packages/autonomous_learning_smoothness_v7/LEARNING_METHODS_AUDIT.md)

未来重建应保留同权限pattern/physics-only/quadratic/history-disabled、完整失败标签、逐提案事前预测、真实native和候选计费。核方差是模型内部量，不能直接等同motion安全概率。

## 4. Critic、Cost-to-go、Q/Value

### 4.1 更早Value与history模型

`ihear_overnight_control_learning_transition_v1` 有七因果特征、action interaction的ridge Q/value，单nominal六开发parent；不是深度TD。Q在三测试状态均选H150，无固定H150外增量；early-value另因保守buffer退B。连续kernel memory有真实更新结构，但仍同选H150。

`ihear_history_to_next_trial_learning_v1` 使用上一完整trial的四个局部force/tracking摘要、两action及平方/交互，17维ridge预测J2−J1、motion margin和execution/task。训练3个模拟Human×5动作，患者信息仍只有3；没有在线权重更新。报告V12/U14/U15收益.636836/.580099/.639314 N·s，均选择固定RETURN slot3−.3°，未证明胜固定该动作或H150。

**重要缺档：** 当前归档原位置缺 `history_models.npz`、`TRAINING_DATA.json`、`POPULATION_HISTORY.json` 与主要raw/完整ledger。源码和freeze可确认机制，性能只能SUPPORTED，不能声称本次独立重算。完整可得性与精确旧路径见 [历史专项审计](research_archive/packages/autonomous_learning_smoothness_v7/agent_reviews/rl_history/HISTORY_VALUE_ILC_BO_AUDIT.md)。

### 4.2 v5/v6长期Critic

v5先用同父真实分支证明0.5s short与完整剩余成本有差异，才训练每相位16条标签、两父状态的三lengthscale RBF ensemble。输出tail JF/JM/time/motion ratio，gamma1，指定后续B；无Bellman、无BPTT。回程Critic纠正short，完整JF1429.726061→1428.170545，但1s short和训练固定动作也能做到；出程仍选motion失败。H前已有失败峰值，未来value无法抵消。

v6引入126字段、量纲floor、菜单中心化成本、累计历史和独立风险。严格绑定B/COMPOSE后续与upstream；真实主四新prefix4/4原合格，相对强训练phase选中轨迹变化0/4、JF额外收益0。风险CV仍漏检，不能替代原native门。[v5源码](research_archive/packages/smoothness_critic_research_v5/source/v5_cost_critic.py)、[v6操作入口](research_archive/packages/smoothness_critic_integration_v6/source/v6_selection.py)、[v6模型审计](research_archive/packages/smoothness_critic_integration_v6/CRITIC_MODEL_AUDIT.md)

### 4.3 v8目标/状态/覆盖分解

A1–A5比较绝对成本、相对B/strong差值、pairwise rank、合法25/33/39D、完整失败和partial支持、45项margin与risk。A4假可行由6/48降到2/48，却增加假失败至17。两个新条件，A1/A2/A3/A5的JF主法各0/2；A4均选B、2/2原合格但无增量。训练数据后来包含早期四stock-case时，这四例不能再称后训练模型的独立测试。[结果](research_archive/packages/deep_learning_method_exploration_v8/CRITIC_VALUE_RESULTS.md)、[纯API](research_archive/packages/deep_learning_method_exploration_v8/families/critic_value/API_GUIDE.md)

未充分探索：真正多步Bellman/TD/FQI、可部署廉价候选H状态、独立风险校准、失败吸收态的在线可观测充分性、超固定规则的排序翻转。把完整JF监督标签改名Q并不会自动形成长期决策学习。

## 5. History、ILC 与连续 Trial

更早ILC按OUT/RETURN高force窗口的膝tracking误差更新 `delta_next=clip(previous_delta+.25*error,±.3°)`。有有限正结果也有U15/U16、P05/T3反向结果；未识别force梯度、没有单调收敛保证。旧BO是独立cost GP、motion GP和Beta平滑execution估计，EI×Pmotion×Ptask；U16唯一改选后JF增加.330361、JM减少.096051，须保留取舍。[历史源码核查与缺档](research_archive/packages/autonomous_learning_smoothness_v7/agent_reviews/rl_history/HISTORY_VALUE_ILC_BO_AUDIT.md)

v8真实连续链保留同一plant/updater/observer，经原boundary继续Trial；同父fork用于受控比较，不把outer B重建当成本臂末态。用T2已完成H150、实际activated RETURN slot的 `estimated−issued-reference` 误差投影到modal x3，gain .25/.10；disabled读取冻结population，不接本患者历史；固定±.25保持强对照。公式与真实执行接口见 [modal projection](research_archive/packages/deep_learning_method_exploration_v8/families/history_conditioned/modal_ilc_projection_v1.py) 和 [持续实现v4](research_archive/packages/deep_learning_method_exploration_v8/families/history_conditioned/continuous_ilc_worker_v4.py)。

轻载第三Trial，同父H150 JF=1323.983165；ILC .25为1323.902035、.10为1323.950724，disabled=1323.786407、固定−.25=1323.510984。ILC有实际小降力且JM增加，但不胜disabled/固定，历史独有价值未建立。heavy因必要H资格不足未继续更新。

v8冻结V2 BO要求各模型相对H150的ΔJM上界不增加、JF保守改善超过已测最佳固定点至少.01及motion余量，严格于原JM/B≤1.25。±.125未尝试点三门均失败而ABSTAIN；0新提案不等于模型省试，未执行点不等于实际motion失败。[持续结果](research_archive/packages/deep_learning_method_exploration_v8/HISTORY_CONDITIONED_RESULTS.md)、[目标澄清](research_archive/packages/deep_learning_method_exploration_v8/families/history_conditioned/audit/CONVAL02_BO_ABSTAIN_OBJECTIVE_CLARIFICATION_V1.json)

未充分探索：高维ILC、多次真实repeat稳定性、学习/识别force响应、多患者少次适应、累计探索负担下净收益。当前投影是参考误差校正，不是norm-optimal force ILC。

## 6. IL、BC、DAgger、SAC、Neural Q

v8 BC从已完成菜单的教师动作监督OUT0上下文，比较覆盖、归一化、树/nearest/神经分类；真实context aggregation不等于在learner逐步访问状态向expert查询的DAgger。两个新条件，预登记OLD_NORM主法1/2；NEW_DEV_NORM为0/2，不得用滚动面板的错误主法标签改写原合同。[IL/DAgger/SAC结果](research_archive/packages/deep_learning_method_exploration_v8/IL_DAGGER_SAC_RESULTS.md)

terminal discrete SAC使用五recipe、25D、twin Q、entropy、risk/JF/JM独立head；replay强制 `done=True,next_state=None`，目标 `y=r`。它有真实off-policy训练与冻结推理，但无多步bootstrap。对同一凸拟合目标精确求解后目标约下降98.17%，控制选择仍不如原actor：优化不足真实存在，却不足解释全部控制差距。actor、greedy Q、soft-Q、温度和保守变体需按相同Q分别比较。[源码](research_archive/packages/deep_learning_method_exploration_v8/families/il_dagger_sac/discrete_sac_v1/source/terminal_discrete_sac.py)

Neural Q以matched linear/tanh16/ridge、物理成本/terminal return目标、risk ON/OFF、固定三seed和训练长度分解机制。主端点tanh16 RETURN+riskON E200三seed各1/2；早期E0/E25的B/B 2/2不能事后替换最终主法。选B更保守是一个现象，不能用资格率单独证明学习优化成功。[冻结API及主法](research_archive/packages/deep_learning_method_exploration_v8/families/il_dagger_sac/neural_q_v2/FROZEN_LIVE_GUIDE_V3.md)、[v8总结果](research_archive/packages/deep_learning_method_exploration_v8/REPORT.md)

未充分探索：真正在线DAgger、完整连续多步SAC、更多独立context、非有限recipe动作、teacher本身和可行域的系统覆盖。BC模仿强传统也不能凭训练准确率宣称超越teacher。

## 7. World Model、直接轨迹与动力学诊断

v8先对44条既有完整因果轨迹作整context划分，比较absolute next-observation、运动学+residual、历史residual及0.5/1/2s直接目标。一步误差降低不保证自由展开JF误差降低；首个样本在动作后，不能作为OUT0反事实选择能力。

F1改为共同动作前OUT0的39D，48条完整任务、10case；完整motion失败保留。E2在同模型初始化和同8训练时点数量下比较D4（到4s）/DFull（覆盖19.03s）、ridge和tanh16，避免把更多标签数混作时间覆盖作用。DFull paired MLP开发排序89/93，但十case全选EARLY_H150，只有6/10完整原合格；说明学到成本信息不等于个体化与资格。

冻结新条件D4 paired RAW0/2、DFull RAW1/2、DFull+A3risk0/2；合格动作等于固定H。模型为conditional trajectory surrogate；没有复现PETS的概率ensemble/trajectory sampling/CEM，没有模型梯度闭环MPC或BPTT控制。[实际研究与表格](research_archive/packages/deep_learning_method_exploration_v8/LEARNING_ASSISTED_OPTIMIZATION.md)、[因果自由展开源码](research_archive/packages/deep_learning_method_exploration_v8/families/learning_assisted/source/causal_dynamics_study.py)

未充分探索：合法候选未来reference生成、模式切换和receipt记忆、不确定性校准、较长自由展开、部署计算与稳定性、模型辅助控制相对强简单方案的真实增量。不能从4s模型16s外推差推断所有World Model无效。

## 8. 未来重新实现的共同最小合同

1. 从固定传统复现通过的环境开始，绑定模型/任务/编译器/安全/scorer身份。
2. 选择一个明确的合法输入与动作权限；先证明至少存在两个合格动作的状态相关排序差。
3. 冻结teacher、reward/标签、continuation、normalizer和主端点；分开offline/fresh、sample/mean、开发/新条件。
4. 完整保留拒绝、partial、失败及physical/compute成本。候选raw共享只去重评价，不制造独立样本或已实现省试。
5. 同时报告学习信息、真实动作变化、完整原门、强传统增量、新条件与净成本；每层独立给证据。

本次归档仅保存与验证，不运行上述新研究。后续架构问题见 [NEXT_GENERATION_ARCHITECTURE.md](NEXT_GENERATION_ARCHITECTURE.md)。

旧native linear Q的四个frozen_Q_v1权重/训练数据/训练与部署记录已在既有Git canonical路径保留；它们与旧m2缺位置的原SHA完全一致，见 [别名恢复清单](research_archive/manifests/historical_alias_recovery.json)。这不补齐另一个History/ILC/BO包缺失的history_models等对象，也不宣称旧Q动态重新验证。
