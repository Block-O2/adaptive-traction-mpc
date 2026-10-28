# 家族C：完整Trial、历史与动作因果合同 v1

状态：`PROPOSED_FOR_ORCHESTRATOR_REVIEW`。唯一激活文件为本研究根 `ACTIVATION.json`；T0 为2026-10-27 03:25:40 UTC，硬截止15:25:40 UTC（北京时间23:25:40），恢复不得重置。家族目录外只读；不直接启动MuJoCo、训练或后台进程。主Agent批准具体运行合同并统一登记后才能执行。

## 已核查的接口与数据身份

历史 `ihear_history_to_next_trial_learning_v1` 只剩服务器GitHub快照中的报告、源码与冻结决策。其大raw、完整患者T1 history、模型NPZ、TRAINING_DATA、结果总表、计数和PACKAGE_VERIFICATION均未发现；不能从报告恢复原生状态或重新训练原模型。历史性能只能标记`SUPPORTED`，冻结决策内容和本轮代数诊断标记`CONFIRMED`。

旧 `continuous_runner.py` 会写历史P、检查旧80 START和旧截止，并依赖缺失资产，禁止直接执行或修改。旧膝中点动作和v8 modal recipe权限不同，不能混池训练或横向排名。

本轮物理接口由主Agent统一提供：复用v7 `v7_worker_v8.py` 的OUT0完整地址空间父fork、原B/任务/guard/证书/admission/activation/receipt、完整raw scorer及motion门。只从冻结合法recipe菜单选择，不输出torque。离散tag、完整recipe JSON、slot override、基础T/H150组件和菜单SHA共同构成动作身份，名字或向量索引不足以说明动作权限。

## 可运行的纯接口

`trial_interface.py` 仅含stdlib，提供：

1. `capture_boundary(b)`：读取因果boundary allowlist；不访问plant或native真值。
2. `summarize(rows,..., public_phase_targets)`：要求完整OUTBOUND/HOLD/RETURN、首末boundary、单调≤6ms间隔；按实际phase左积分测得force/moment，公开reference progress分五箱，输出两个中段窗口的估计actual−reference误差。
3. `feature_vector(history)`：测得JF/JM、去回中段force及髋膝lag，共8个命名特征。运动资格真值不作为部署输入。
4. `ilc_target(...)`：固定增益/两phase/双关节有界误差更新；这不识别force梯度。最大值≤0.3°仅为目标幅度上界，实际动作必须继续投影到冻结菜单，不扩大modal box。
5. `project_to_menu(target, descriptors, menu_sha256)`：只返回已有tag。描述符需由主Agent按确切recipe给出；modal坐标不是直接膝位移。若recipe无法给出可信的局部参考效果描述，记`NOT_APPLICABLE`，不能凭名字手填映射制造ILC。
6. `verify_trial2_inputs(...)`：检查患者、紧邻上一Trial、源码/任务/scorer/menu身份和完成时间≤冻结时间；活对象连续性仍由统一物理runner证明。

该模块没有文件写入、模型fit或physics。纯接口fixture不能升级为LEVEL1物理实现通过。必须在原worker中捕获TASK首boundary和终末因果boundary；不外推缺末样本。summary JF/JM须与相同区间原积分闭合，浮点误差按现有原合同核验。

## 连续重复与同父对照

Trial1完整执行B，产生当前患者真实因果历史。Trial2在该患者所有Trial2结果产生前冻结enabled、disabled、强固定小扰动及B动作。所有臂从同一个活Trial2父串行fork，before/after父manifest必须相同；冻结文件引用T1 raw SHA、summary SHA和菜单SHA。逐臂真实native、失败、准备边界和对照费用全部计入。

Trial3必须从各自真实Trial2选择臂继续，经原inter-repetition boundary，不重写Human qpos/qvel、belief或observer，不拼接其它方法分支。比较B、KEEP（保留该臂T2已执行动作）、冻结T3学习动作；若用T2反馈更新，必须先冻结，且其它T3结果不能进入。对独立患者，学习器/超参/菜单/特征预处理先于该患者T1冻结。

现v7冷父fork本身不能证明连续重复。若主runner仅支持cold重复，输出`COLD_REPLAY_HISTORY_CONDITIONED_SELECTION`，不称连续Trial适应、跨repetition收敛或少数实际患者运动。`TrialSession`纯JSON检查也不能补足活物理连续性。

## 公平对照与评价

每个状态分别报告：动作proposal、证书/activation、receipt-owned native、history是否改变tag、与history-disabled的差值、与同父B差值、与最强固定recipe/固定小扰动差值、JF/JM/平顺性完整分量和原资格。不得把模型margin拒绝当真实物理失败；不得把partial低成本排名。

disabled保持完全相同模型、候选库、选择规则和当前原控制反馈，仅替换上一Trial context为训练患者均值；不能把disabled=B自动当作公平强固定对照。强固定小扰动须在开发数据中选定，再冻结于独立测试。原H150失败逐状态保留，不能用不合格H150作收益分母。

升级门沿用户LEVEL1–7逐层记录。LEVEL5要求超过同权限最强固定/传统；LEVEL6要求冻结后独立合法患者/状态；LEVEL7计入历史标签采集、失败、准备、对照、训练、代理查询成本，只有净物理尝试或净计算成本减少才可声称效率。无预注册临床最小收益阈值，不把历史0.01 N·s工程报告门当原资格或统计显著性。

## 不同机制的变体合同

|变体|改变机制|训练/在线输入与目标|最小可证伪实验|失败后解释|
|---|---|---|---|---|
|C1B 双phase投影ILC|旧最高force窗口单膝改为去/回phase误差，投影合法菜单|已完成Trial局部estimated lag、公开recipe效果；固定gain；不fit|同父比较强固定、旧单窗口规则、双phase投影、population-disabled；审计是否同tag|同tag→LEVEL3未通过；改变且不增益→局部tracking目标不代表完整负担|
|C1C 灵敏度/自适应gain ILC|从实际动作变化估计局部动作→误差/负担响应，可信域抑制反号|至少两个同患者实际applied动作及其完整反馈；不能以未执行提案估计梯度|冻结secant gain，独立下次Trial对KEEP及固定gain；所有探索负担入账|初态漂移>信号→不可辨识，不增加网络可解决|
|C1D 低维norm-optimal ILC|目标由tracking误差改为合法负担分量；约束参考更新范数|实际完整轨迹+独立合法局部动作响应；Q过滤只作用下一Trial参考参数，不滤评估raw|对固定gain和传统局部最小二乘同权限比较|响应模型缺失则NOT_RUN；不宣称原ILC收敛保证适用|
|C2B 配对相对收益GP|目标由T2−T1绝对漂移改为同父action−强固定收益|训练父状态配对完整JF/JM；分头motion余量/qualification；不混partial|冻结模型后盲测动作排序，CEI对保守相对LCB及固定最优|无排序异质性→强固定足够；误差大→数据/校准未闭合|
|C2C contextual GP|context×action乘积核与仅相加核比较|相同已完成数据，同患者整组split，fold内标准化；相对收益目标不变|互换历史/均值历史，检查action−baseline排序变化及独立收益|纯状态项抵消→目标表示问题；交互不改变决策则LEVEL3失败|
|C2D 分量约束采集|EI探索改为保守收益LCB或信息量采集，JF/JM/motion分开|成本/余量独立头；先登记风险阈值，保持原门|相同开发起点与真实增量尝试曲线；每臂只消费本臂反馈|不确定性门全部拒绝→校准/样本不足，不判整个BO无效|
|C3B 相对收益history×action|显式交互回归/配对ranking代替完整下一Trial成本|同父action−固定完整标签，8维因果history；独立患者fold预处理|action-only、history-additive、interaction、history-disabled、强固定同库盲测|交互学到信息却同tag→无独立决策；同tag重复不多计样本|
|C3C 多Trial状态输入|加入上一实际applied recipe和完整history窗口，避免仅B→T2外推|只有实际上一动作与已完成本臂history；从不同先前动作覆盖训练|真实T3/T4从各自T2分支继续，KEEP对照|缺其它前动作标签→适用域不足，NOT_FULLY_EXPLORED|

这些是不同研究机制，不是改几个学习率；除纯接口及离线历史诊断外均待主Agent批准、尚未训练或物理执行。不能据准备代码把家族标为已充分探索。
