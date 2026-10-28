# 小型非线性terminal-Q表示诊断：待主审，未训练

只写neural_q_v2私有目录，原A/SAC/Beta/root源码、数据、checkpoint不改。当前只准备source/schema/合同与零模型可得性；数学fixture和所有模型初始化/fit/forward必须另获主Agent批准。唯一ACTIVATION/T0及2026-10-27T15:25:40Z硬截止不重置。本候选是监督terminal contextual value，不是新SAC机制或Bellman多步RL。

## 可证伪假设

H1表示：同数据/输入/目标/尺度/优化器/步数，TANH16比action-specific LINEAR改善训练与整case开发的return/risk误差及选择后原资格。训练误差改善但held-case不改善，支持过拟合/覆盖限制；不判一般神经网络失败。H2尺度：物理cost头中心化后LINEAR或ridge已足够，改进应归于尺度/截距/优化，不能归于非线性。H3目标：即使回归/Brier改善，按return选出的动作仍可能原motion失败、JM增加或UNKNOWN，说明目标与覆盖未修复。H4输入：另批39D若改善而25D容量不改善，支持输入信息假设；不把维数/距离变化当因果证明。

## 固定数据、输入和切分

始终同SAC64、同五个完整recipe SHA、同64个实际row及其原失败。12个case SHA整体leave-one-case-out，重复case/action全部在同折，另ALL_DEVELOPMENT。64行保持原empirical权重，12次重复不算12个新context；同时评估按52unique cell和12case等权的误差，报告重复对指标的影响。不把缺动作训练标签或失败低JF补为teacher。

25D主法是原commissioned25，主模型随机初始化、不继承BC权重。每折只用训练case的唯一causal向量拟合一次mean/std，std<1e-6的字段scale置1并列出实际极小std/常量字段；这不是对输入值clip。13次input normalizer fit，held-case不参与。由于全12条件与目标早已研究曝光，整case分折仍仅开发诊断。旧BC曾见6个context，其冻结normalization/weights不是新Q的未见先验；源可得性已明确标记，不用旧BC的LOCO成绩声称独立测试。

39D已经逐字段/source核验可恢复全部12case，但不自动纳入此次拟合：额外8项估计q/dq+请求reference q/dq，6项当刻测量wrench。无native truth、TASK积分、emitted reference、case ID、原JF/JM或未来motion输入。39D若另批，完全同64/同5recipe/同折/同目标/同seed和预算单列。

## 独立目标、模型和尺度

每个模型只有一个目标，不共享return/risk/JF/JM隐藏层，不混目标梯度，也不使用JF+JM加权总分。目标六stream：RETURN（原canonical gain1 return：合格clip相对JF增量，完整失败−1）；RISK（原资格失败0/1，稳定logit BCE）；JF_FIXED/JM_FIXED（物理完整成本，固定μ0、scale1500N·s/100N·m·s）；JF_CENTERED/JM_CENTERED（同物理目标，μ与std只取训练实际rows，scale=max(std,1原单位)）。return/risk始终μ0 scale1；其模型不因cost尺度条件重复构造。

容量主对照：每seed每stream一个LINEAR(D→5, D25时130参数)与一个TANH16(D→16 tanh→5, D25时501参数)。五个输出只在实际已观测action上有监督梯度，未观测输出可由模型外推但没有补标签；报告UNKNOWN。两模型均手写NumPy float64、同full-batch Adam lr.01、β=.9/.999、eps1e-8、weight_decay .001仅W、global gradient norm上限1、200固定步。没有actor/温度/target network/bootstrapping、mini-batch随机重排、dropout或隐式超参搜索。

三个固定seed20261027101/102/103，全保留逐seed结果、均值与范围，不选最好seed。固定parent step0、early25、final200，最终决策只用final200；早/父是诊断端点，不按validation挑best或早停。超时/数值失败保留实际已付费梯度/私有更新并终止，不延长步数追效果。

强优化参照：同输入/实际rows/目标、无bias正则的闭式ridge RETURN/JF_CENTERED/JM_CENTERED（λ=.001，overall-N MSE口径与learned linear一致），每折三个确定性fit，无seed搜索。Ridge不伪装logistic风险模型；其风险受限selector配合同seed LINEAR logistic risk，只用于明确的混合参照。JF/JM fixed与centered若闭式affine等价，仅记录解析/数值等价，不重复当独立fit。

## 选择、强控制与失败口径

预指定primary=25D TANH16 final200 RETURN_GREEDY，三seed逐个报告，不投票/挑best；linear/ridge同selector为容量与优化对照。secondary固定RETURN_RISK_LE_0P1_ELSE_B：只在预测failure≤.1中最大return，没有候选则原B fallback。风险分数未校准，阈值事前登记不是原资格证书，不使用当前case未来标签作mask。JF/JM头只做误差/分量分析，不进入policy加权评分。

同五recipe强控制：原B独立物理锚、过去训练case observed-return最佳常数、单阈值stump、nearest；缺训练支持时规则弃权，不用未来标签填动作。为缩小初次拟合预算，冻结SAC64已有规则/actor/soft-Q的保存开发预测只作背景，不能把不同fold/优化目标的保存数字当严格本轮容量对照。必要的新规则重fit若主审要求，要另列具体source/阈值数与预算，不包含在当前提案的模型budget中。

评估同时报告return MSE、risk BCE/Brier/漏判/误判、JF/JM MAE（原单位，合格与失败分列）、52cell pairwise排序/observed regret、12case选择完整原资格/失败/UNKNOWN/fallback、支持覆盖和原门motion失败项。不可只报合格子集平均收益；对缺动作保留UNKNOWN或上下界，不插值。SAC64 baseline对象中的独立原B证据可作为单独控制证明，不能悄悄增加训练row或把原policy表UNKNOWN覆盖。

## CPU局部预算与拟议精确账

先另批GateM合成数学检查≤30s、单CPU、0真实fit/physics；计划文件MATH_FIXTURE_PLAN_V1.json。通过不自动授权真实拟合。

GateR只25D真实离线拟合，拟≤120s wall/CPU、1CPU affinity/BLAS1、AS≤1GiB、原venv Python3.12.3/NumPy2.2.6；开跑前实际binary/module/source/dataSHA、AST、START/PID/startticks/CPUwallRSS及local_deadline冻结。13scopes×3seed×2arch×6独立stream=468随机初始化，固定200步共93600 Adam参数组更新、同数梯度API和训练forward，5,529,600实际observed-row梯度样本。39 ridge fits、195个每action线性solve；不存在未计的twin或actor模型。

按parent/early/final在训练和held partition各一次head预测，ALL无held：2700 learned-head predict API、89856 observed-row forward；ridge仅final 75 predict API/2496 rows。全部phase/seed实际初始化、数组normal输出数、前向/梯度/clip/update、失败私有计算、normalizer13与cost-target normalizer26次、序列化/restore次数另账。数学fixture、开发fit与未来物理分账。当前这些全部为拟议，实际模型调用0。

39D GateS是独立可选另批≤120s、同计数的输入机制实验；不能在25结果之后未经批准挑39D或加宽网络。任何新验证case、冻结deploy adapter或物理选择都由root后续先审再派发，先模型/source/策略冻结再开新结果。现阶段不创建真实授权、模型、checkpoint、训练clock或环境。
