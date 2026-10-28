# B-CONTINUOUS-SCALE-V1（待主Agent逐阶段批准）

当前状态：CODE_ONLY_NOT_RUN。新增训练、policy forward、Beta采样、密度测试、环境构造、物理均0；只做源码阅读、原论文核验及AST/内容SHA。全局T0与15:25:40Z截止不重置，未因本候选另起时钟。冻结V1 API及onpolicy driver V2均不改。

## 有限假设

离散recipe可能跨原motion边界，沿已有18D/H150干预的合法小幅度轴或存在未观测的完整合格范围。本假设尚未证实；原五recipe边界不能推出该轴可行，参数box合法也不自动证明任务/安全/motion合格。若连λ0/λ.5/λ1工程门都不通过，应先定位残余底层干预与真实拒绝原因，不以Beta名字证明新动作有效。

## 真实接口审查结论

1. v8_worker对`family='old18d'`接收exact18向量，核对原PARAMETER_MAP逐维`abs(parameter)<=scale+1e-12`。FROZEN_18D本身在对称box中，故λ∈[0,1]的`parameters=λ*free_parameters`在box内，无需clip；legacy严格[0,0]，不额外加两坐标偏移。
2. H150原posture为RETURN2/3各[.3,−.3]°，源码许可每维≤.3°；映射乘λ合法。early原RETURN1 factor1.1、RETURN4 factor1.2，原界[1,1.3]；timing RETURN5 factor1.5，原界[.75,1.5]；`1+λ*(factor−1)`均在界内。多segment changes必须原为空，不作未定义缩放；未知candidate字段、controller/policy或其他权限直接拒绝，而不是猜含义。
3. `family='old18d'`仍通过T底层Round→TerminalRepair→RichFree→NativeResidual执行。**λ0不是原B**：hardcoded OUTBOUND terminal duration×1.5仍保留；FROZEN_18D的RETURN1/2 −.020/−.022 native residual plateaus仍由base_campaign.choose安装，未随18D向量缩放。
4. 零posture/单位factor的列表项仍保留，仍可能触发原POSTURE/INTERNAL/constant-knee前提、fixed-duration重新认证、5ms量化与fallback；不能删项后称同一λ0。尤其RETURN5原constant-knee断言不因factor1而消失。
5. v8_worker先调用继承control再覆盖old18d.parameters；继承的advisory context/clone可能先使用完整OLD18D参数，再安装本次原native residual。这是现有old18d流程的一部分。只有保存实际参数/参考/receipt才能说明最终执行；不能把本轴叫“所有协调强度从B连续线性变化”。

因此本轴**结构可表达但执行资格未知**。即使λ连续，实际参考/费用仍可能因ceil(5ms)、candidate选择、断言、certificate及guard而不连续。REINFORCE/PPO采用score-function梯度，不声称已获得物理映射的可微梯度。

`axis_mapping.py`只生成原action JSON及完整轴/recipe身份，不构造环境。axis嵌入原FROZEN、PARAMETER_MAP、H150 candidate与source hashes，逐次验证实际内容，不只相信hash metadata。candidate_hash按去id/旧hash的新内容重算；完整轴recipe身份与原H150不同，不能凭candidate_hash相同/不同认定执行等价。λ1只可声称对应同值干预，原参考/receipt等价要实际复核。

## Gate 0：数学/密度（仅提案）

主Agent先批准单CPU20秒局部数学检查，0env/physics/actor初始化/参数更新。执行入口拟为`math_validation_proposal.py --main-agent-approved-math-only`，用实际冻结源对象生成axis，在λ0/.5/1和非法输入上核对映射、参数box、legacy0、保留列表项与残余plateau身份；该测试通过只授予数学/接口结构层。

直接Beta公式归一化、raw-shape score有限差分、初始ratio1、PPO clipped/inactive分支、RNG恢复以及抽样矩检查分别计数学函数次数；不调用learned policy forward，不把密度测试称新学习。所有结果、随机数状态与源码SHA在新唯一输出目录保存，失败不覆盖。

## Gate 1：原B与λ0/.5/1工程物理（仅提案）

主Agent选一个已合法开发context、冻结source/axis/task/QA后，沿原单owner/full-state fork先原B fullqual，再λ0、.5、1各独立实际attempt。局部wall建议30分钟，每attempt沿主闭包原300秒上限；是否派下一项由前项实际工程/safety结论与全局剩余时间决定。另保留已知H150值的对照，用实际q_ref/dq_ref/ddq、accepted/activated计划及positive-native command receipt核对λ1；不能仅比较参数JSON或累计JF。

工程失败/partial全保留且不进成功成本排名。原guard、HOLD、端点、ROM、torque、clearance、constant-knee、admission/scorer/motion不变。True hard safety先停，不能被engineering censor吞掉。若原B不合格，停止该context准入；不能换容易状态补成功。若某λ原任务失败但硬安全保护正常，先分类；不直接给整个轴/方法家族失败结论。

λ0与B的差异必须按T修复、固定native plateaus、单位intent重评分别描述，不能把λ0视作无干预对照。若需要拆开这些机制，须主Agent另登记新轴/源码，不在本映射中偷偷删除。

## Beta policy、密度与部署

行为分布为一维`λ~Beta(α,β)`，`α=1+softplus(uα)`、`β=1+softplus(uβ)`；u可为commissioned25固定归一化后的两行linear head（常数为其简单对照）。完整25D/QA沿已审schema，不输入case/path/真参数/未来结果。相同父、独立arm/RNG，初始化α=β=2只在获准后执行。

`log p(λ)=(α−1)log λ+(β−1)log(1−λ)−lgamma(α)−lgamma(β)+lgamma(α+β)`。直接在λ∈(0,1)采样，无Gaussian后clip、无静默重采样。有限精度若产生0/1或非有限密度，记录耗用RNG为数值no-proposal，不发物理。物理工程端点0/1由固定传统规则直接执行，不伪造为Beta随机sample。

λ区间固定[0,1]，scalar affine Jacobian为1、log为0；shape logit→α的导数用于score梯度，不是action-density Jacobian。18D参数及附加intent落在一维曲线上，**没有18D环境Lebesgue密度可供本policy使用**；PPO ratio始终比较同一实际λ样本的scalar Beta密度，不虚构18维Jacobian。

冻结部署取`λ_mean=α/(α+β)`，并真实执行其映射、完整原评价；均值λ不是平均物理轨迹/期望成本。deterministic mean没有training old_logprob资格，不冒充随机sample。代码只提供密度、score与surrogate系数，目前没有optimizer/physical-dispatch实现；离散5menu的v2不能原封套到连续λ，后续driver需按冻结axis SHA+实际λ/recipe重新独审。

数学参考：[Beta policy原论文](https://proceedings.mlr.press/v70/chou17a.html)、[NIST Beta–Gamma恒等式](https://dlmf.nist.gov/5.12)、[NIST digamma渐近式](https://dlmf.nist.gov/5.11)、[Python betavariate官方定义](https://docs.python.org/3/library/random.html)。Beta避免当前候选的proposal越界clip，但不据论文宣称旧Gaussian latent+clip实现密度有误，旧正确score-density证据仍保留；也不把论文benchmark效果迁移为本任务收益。

## Gate 2：若存在原合格响应，再审新训练

四臂RF/PPO×raw/gain20分列：合格完整`clip(gain*(JF_B−JF)/max(abs(JF_B),1),−.9,.9)`，原保护任务/原motion失败floor−1；工程partial整组取消，JM不相加、各motion指标和实际JM增量单列。raw与scaled是不同目标量级，不混reward/replay；所有fresh on-policy数据各臂单独真实采样，保存exactλ/αβ/logprob/axis/recipe/RNG与原物理回执。目标仍JF且原资格约束，不称双成本改善。

先检验合格λ范围与force/JM/资格排序信息；如果仅一个固定λ已解决全部开发选择，Beta的独立学习价值前提不足。受控常数/conditional25、mean/sample差异与raw/scaled失败floor分别诊断，不靠增加episode通用修正。

后续训练窗口建议由主Agent按实测吞吐登记约2h有限局部wall，无固定episode总上限，完整batch轮转保对齐，第一次update为early、最后完整对齐generation为primary endpoint。该项当前**未获准、未运行**，还需主Agent审查数据/连续receipt driver与实际剩余时间。

## 强传统与独立验证

同一合法λ轴、同样OUT0权限给传统1D grid/pattern：B分开；gate端点0/.5/1与工程成本全部计入；开发时可在实际合格区间内进行预声明的1D局部pattern/保守细网格，不能只比不合格λ1。固定传统最佳在新验证前锁定；若selector使用25D，另保留开发锁定常数λ、最多一个因果if/nearest与teacher压缩对照。所有新增物理尝试/commissioning/失败/模型数学成本全记，物理grid已完整执行后不宣称Learning省试。

主Agent另预登记至少两个真正未见合法验证条件，不使用已打开四stock/新dev结果同时当holdout。所有actor、traditional选择、axis/source/normalize及mean部署在打开新结果前冻结；B仍先原合格。方法有效、原任务/motion、强传统外增量、跨条件保持与效率分开授予。没有充分变体覆盖时保持NOT_FULLY_EXPLORED。
