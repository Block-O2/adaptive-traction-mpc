# D：episode OUT0 context aggregation / BC coverage correction

状态：SOURCE_AND_DATA_SCHEMA_ONLY，0模型fit、0normalization fit、0forward/backward/update、0physics。物理与训练须主Agent审查最终完整输入SHA和局部预算后另行批准。只写本目录，不改categorical_policy、onpolicy文件、worker、原guard/task/scorer。

## 可证伪机制与范围

此前3recipe BC仅看6个历史context。新闭合工程context可能揭示同recipe原motion失败与教师选择边界；聚合这些已暴露context后，固定因果25D的episode selector可能更准确选择合格recipe。另一候选解释是历史normalization不能有效表示新context范围。两者分别对照，不把训练标签拟合或开发资格当独立控制泛化。

这不是旧55D/20ms native-event DAgger修复。DAgger原方法在learner诱导的状态分布上补expert标签；此接口先完成commissioning并在OUT0采集固定context，随后learner才选一次完整recipe。因此本episode OUT0输入状态不由该learner决定。新增工程条件增加的是外生context覆盖，不能宣称解决多步状态分布漂移。[Ross/Gordon/Bagnell, AISTATS 2011](https://proceedings.mlr.press/v15/ross11a.html)。利用已经观测的完整cost选择teacher也不等于实现需要交互与cost-to-go查询的AGGREVATE。[Ross/Bagnell 2014原论文](https://arxiv.org/abs/1406.5979)。

## 数据与闭包门

历史输入为critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json，实际schema字符串仍v1；保留原45row/6context审计来源，不能误以为45个独立状态。固定5menu来自freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json，顺序B/LATE_H150/EARLY_H150/LATE_PHASE/EARLY_PHASE。旧45row只有28行匹配这5个完整recipe SHA；其余17行保留来源审计、禁止改名塞进5分类。EARLYH01缺两个phase动作，保留missing，不补标签。

新增指定V8CTX01..04。只在该组WORKER_DONE和PHYSICS_DONE都存在，原worker all_children_joined、parent_checks全部unchanged且physics all_parent_unchanged时读取该组任何RESULT/causal payload。首次预检CTX01/02/03已闭合；CTX04两文件缺失，因此不读CTX04任何结果或半raw。草稿输入只能是历史28个菜单row+已闭合15row=43row/9context；历史45row来源仍全保留。第四组闭包后目标为48个menu row/10context（45历史原row+20新增菜单row共65个来源row），最终SHA必须重新冻结，不能把当前草稿SHA当完整训练输入。

每个新组去除HISTORY_B和parent重复；每context每完整recipe只保留一个实际新child记录，重复绑定若cost/资格不一致则停止审查，不能挑好值。真实context保持25数+原QA，原77D仍invalid。case、真human/geometry、group、parent/hash/path、future costs/资格不输入actor。group仅作切分、去重、归属和固定tie metadata。

完整recipe要求实际action、去标签resolved candidate、FROZEN18D以及planner源SHA均与固定menu一致，并校验实际contract digest，不只信自报action_sha。新组RESULT与PHYSICS_DONE对应row、EXECUTION_BINDING的actual action/candidate一致；原SOURCE_MANIFEST绑定的planner/FROZEN源匹配menu。源文件不变不替代实际receipt；每行保留原RESULT、MEASURED、execution lineage与闭包文件路径SHA以及原activation/rejection/fallback证据引用。

教师每context在该固定5menu中实际观测、完整、原合格且JF/JM完整的动作取最小JF；精确JF tie按固定menu顺序。失败、partial、缺失一律不作teacher，不把低partial成本当成功。原45row不限菜单的最优动作另列审计，若在5menu外，只报告动作空间限制，不能偷偷把它重标为五动作之一。JM和原motion资格独立报告；最小JF teacher不保证JM下降。不存在跨context教师oracle部署；teacher只生成已暴露开发训练标签。

## 拟训练与初始化对照（尚未执行）

固定父模型为ppo_reward/offline_fit_v2/checkpoints/qualified_force_raw/ALL_EXPOSED_DEVELOPMENT/BC_linear_commissioned25.json的policy。纯确定性BC3→5 lift保留原前三行logit，新phase两行取原两个H150权重行均值；新增softmax分母会改变概率，不称父概率保持。三个预登记变体均从同lift函数初始化，不根据新增结果换父模型。

1. OLD_ONLY_5_OLD_NORM：历史6context的5menu teacher，保留父normalization；是覆盖对照，动作空间和初始化与新模型相同。
2. AGGREGATE_5_OLD_NORM：历史6+新增4，共10context，同一父normalization；预登记primary，用于隔离覆盖增量。
3. AGGREGATE_5_NEW_DEV_NORM：同10个teacher，只用新增4个开发context计算25D均值/总体标准差，std<1e-12置1；不读sealed验证context；用于尺度对照。normalization本身单列preprocessing fit。将lift权重解析重参数化，训练前保持每个原始25D输入的5个logit函数一致：Wnew_j=Wold_j*snew_j/sold_j；bnew=bold+ΣWold_j*(mnew_j−mold_j)/sold_j。否则尺度变化会同时改变初始策略，不能归因normalization。

每变体全batch交叉熵240次manual SGD、lr=.15、global gradient norm≤1，无Adam/正则/随机batch；同确定性初始化不重复跑伪独立seed。记录每步loss/gradient norm/clip scale/parameter delta、原始输入与标准化输入范围、全部checkpoint/数据SHA/计数。有限步SGD下尺度影响优化几何；仿射normalization不增加线性函数类能力，不据此宣称新表示容量。

同teacher强对照：多数teacher常数（tie固定菜单顺序）；全部25特征阈值穷举stump；最深2的树（根阈值穷举，各子树独立穷举最佳stump/常叶，从而在该深度完全搜索）；标准化25D nearest（父norm、新dev norm各一）；以及完整成本表上的保守强常数，仅在所有训练context均有实际完整标签的共同可用动作内先要求全部原合格、再最小总JF。这个成本表常数比单teacher标签获得更多信息，单列，不和多数常数混为一谈。树/常数监督损失是每context等权0-1误差，tie先少节点、再feature index、threshold、menu index。nearest距离tie用冻结训练顺序，不能输入真case。全部baseline、原B和原5recipe传统控制保持同动作权限、同原最终门。

拟局部预算：单CPU60s，一次normalization preprocessing fit、3个BC fit/720步、6个传统拟合/确定性选择器准备（多数常数/stump/depth2/nearest两套/cost-aware常数）。BC训练forward/backward-equivalent=240*(6+10+10)=6240；每模型在同10个已暴露context训练前后各推理一次，共60额外forward，总拟6300。初始化仅一次BC3→5 lift后3个独立copy，0categorical.initialize调用；数据/参数源SHA与父归属单列。规则枚举的阈值/叶节点评分次数、nearest查询次数另账，不伪装backward。若数据数变化按公式登记实际计数，不为了凑数补context。局部或全局deadline任一到先停并保留全部私有失败工作，硬截止仍2026-10-27T15:25:40Z。此预算只是提案，不是本轮批准。

## 冻结与反证

所有3个BC和baseline输出、API/源/输入完整SHA、归一化、teacher规则、primary、训练checkpoint，在后续两sealed验证任何结果前由主Agent统一冻结。sealed两条件本轮不读取也不生成。父模型原3动作BC和BC3→5未更新lift亦保留参照。

若聚合模型训练标签更准，但两sealed验证资格/合格JF不超过OLD_ONLY同5动作或强规则，只能说覆盖未显示独立价值；若仅newnorm更好而同norm聚合无增益，不能归因覆盖；若训练也学不准，先检查线性可分性/尺度/教师标签而非宣称IL无效。合格JF、原资格率、JM增量、motion/native jerk/force-rate、实际activation/拒绝fallback分别报告。只有两个sealed条件，结果具有有限支持；不得调参后继续称sealed。

## 纯API候选

context_aggregation_api_v1.select_out0(bundle, feature_names, commissioned25, qa_validated=True, expected_bundle_sha256=..., frozen_recipe_sha256=...)只接收因果数与冻结模型，不接收标签、case或当前结果。返回固定argmax recipe和实际完整SHA，不授予原资格。input bundle不变，实际contract必须逐项digest等于外部冻结5menu。原categorical API不改，仅在新的wrapper候选内部可调用其纯predict，源码SHA须绑定。当前只准备代码/AST与数据schema，不初始化或调用任何策略。
