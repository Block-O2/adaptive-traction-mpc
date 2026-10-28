# PPO 050→080 稳定性诊断

**结论：执行层直接原因已定位，唯一学习根因尚未确定。** 两个曾成功的deterministic策略在继续30集后，均值动作及两关节协调发生漂移，改变了被准入的参考和实际torque，最终在RETURN提出原shank-table几何不可行waypoint，被保留的原门拒绝并ABORTED。不能据此预先命名catastrophic forgetting，或把所有退化都归因于单一stochastic/deterministic mismatch。

## 1. 原冻结050/080的事实

|seed|checkpoint episode|runtime|TASK s|accepted/rejected|第一个bounded mean|terminal reason|
|---|---|---|---|---|---|---|
|1106823814|50|ABORTED|15.535|20/2|[0.7888177633285522, -0.14672411978244781]|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-72.850526 mm)|
|1106823814|80|ABORTED|15.435|17/2|[0.9080299735069275, 0.25241371989250183]|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-58.974716 mm)|
|1495656323|50|COMPLETE|19.030|18/1|[0.7268764972686768, 0.5315635800361633]|完整完成|
|1495656323|80|ABORTED|16.265|15/2|[0.9560142755508423, 0.7051965594291687]|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-5.799079 mm)|
|1630784693|50|COMPLETE|19.030|17/0|[0.5823203325271606, 0.9226795434951782]|完整完成|
|1630784693|80|ABORTED|15.580|12/2|[1.0, 1.0]|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-35.988372 mm)|

每个原050/080都有两次相同nominal重复；对应episode的actions由权重重新forward复现，真实native准备prefix/config一致。六条原轨迹的独立ownership/torque/step/source-age/force/moment复核PASS。在TASK **10ms**时reference和实际receipt torque首次分叉，在**15ms**的5ms边界Human实际状态已可测分叉；这证明权重漂移经过执行层施加了实际物理影响，不止是模型权重不同。具体值与逐request准入见 `HISTORICAL_NATIVE_EXECUTION_AUDIT.json`。最后的负mm为候选预测几何，不是已发生物理碰撞；实际观测安全审计通过不能升级为全动作安全。

## 2. 更新强度、分布及信用分配

|seed|51–80成功/30|decisions|Adam更新|最后epoch KL均值/最大|value loss均值|explained variance均值|1-transition集数|singleton minibatch集数|
|---|---|---|---|---|---|---|---|---|
|1106823814|7|447|196|0.0004119 / 0.0016541|160.846|0.0465|6|8|
|1495656323|19|561|220|0.0001473 / 0.0012509|286.433|0.0522|2|3|
|1630784693|11|424|188|0.0006233 / 0.0051963|234.820|-0.0527|7|12|

相同预存causal观测上，1495656323的050→080平均绝对raw mean变化为[0.177006,0.147412]，Gaussian KL均值0.028598；1630784693为[0.634878,0.138427]，KL均值0.216017。control seed1106823814也漂移[0.063288,0.223793]、KL0.035114，但050/080一直失败。该KL由两份冻结分布离线计算，不是重建历史更新KL。两退化seed的std始终约0.98–1.00；050成功mean仍位于高随机探索分布中，80的1630784693起始mean被clip到[1,1]。

1495656323的随机训练完成从21–50的8/30升至51–80的19/30，仍未保住确定性最终能力；1630784693为8/30→11/30。训练正在优化带大量噪声和边界clip的动作分布回报，部署检查的是mean闭环完成，两个目标没有单调等价保证。小的单次记录KL和全零surrogate clip_fraction没有阻止30集累计漂移。没有target_kl，也没有成功checkpoint保护门；这些是实现事实，未证明设置target_kl即可修复。

240份独立reward重算全部通过；172失败总回报−11.5，没有失败正总回报漏洞。65个single-transition episode、76个singleton minibatch episode，加上弱value explained variance，支持“局部advantage/小rollout梯度噪声”候选机制；107失败有正中间reward、48失败有正raw advantage。它们不证明reward公式本身错了。没有对loss/梯度做训练消融，也没有可用裁剪前梯度曲线，不能给出确定统计归因。

## 3. 8次有界新冻结评价

为区分“变化中策略的随机训练成功”与“固定checkpoint的随机能力”，先冻结两退化seed×050/080×两个共同RNG。没有添加/替换样本，所有负结果保留。与历史deterministic比较时，只称同nominal开发诊断。

|seed|checkpoint|evaluation RNG|runtime|TASK s|decisions|JF N·s|JM Nm·s|reason|
|---|---|---|---|---|---|---|---|---|
|1495656323|50|2026102101|COMPLETE|19.930|25|1452.439|108.485|完整完成|
|1495656323|50|2026102102|ABORTED|5.725|8|558.681 partial|43.918 partial|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: candidate would regress the emitted reference away from the phase goal|
|1495656323|80|2026102101|ABORTED|14.745|18|1047.242 partial|58.536 partial|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: candidate would regress the emitted reference away from the phase goal|
|1495656323|80|2026102102|ABORTED|8.355|10|773.338 partial|45.882 partial|NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: no quintic schedule satisfies the registered phase and motion limits|
|1630784693|50|2026102101|COMPLETE|19.655|23|1467.015|106.940|完整完成|
|1630784693|50|2026102102|COMPLETE|19.655|24|1497.762|94.740|完整完成|
|1630784693|80|2026102101|COMPLETE|19.060|20|1449.269|96.151|完整完成|
|1630784693|80|2026102102|COMPLETE|19.030|15|1462.560|105.785|完整完成|

汇总：seed1495656323/cp050=1/2；seed1495656323/cp080=0/2；seed1630784693/cp050=2/2；seed1630784693/cp080=2/2。其中seed1630784693的080为mean历史0/2而随机样本2/2，seed1495656323的080两种执行均0/2；这支持采样会改变可达闭环路径，同时反对把统一根因简单归为采样模式。小样本只能证明这些特定随机轨迹的结果，不估计稳定概率；不把随机成功作为deterministic回退已解决。成功时长若与19.030历史不同，不列JF/JM相对改善；失败partial积分也不作为降force收益。新增native总步数 826,220，RL decisions 143；0梯度更新，8次独立物理/奖励审计均通过。原scorer没有给这些新run授予matched资格。

## 4. 候选机制与证据等级

|候选机制|支持证据|反证/未测|置信程度|
|---|---|---|---|
|均值/协调漂移跨过RETURN可行边界|相同准备初态与软件；mean→已准入reference→实际torque→Human路径的直接分叉；最终两次几何规划失败|未做固定中途状态反事实替换；不保证某个单一action独立足以造成终止|高：执行层原因|
|单episode高噪声更新未保护成功mean|固定LR、120epoch继续更新、target_kl=None、Gaussian累计漂移；随机训练成功可升而mean失败|记录单次KL小、clip fraction0；没有LR/epochs/rollout消融|中：学习机制候选|
|训练随机分布与mean部署目标不一致|std约1、实际clip；训练与冻结语义不同；新增两组固定RNG直接证据|Gaussian平均动作不代表分布最佳动作本来就可能；8次不足分离唯一原因/估计成功率|中：贡献因素，非唯一根因|
|GAE/value和singleton梯度信用分配|GAE精确复算；65单transition、76 singleton、value解释力弱；局部正advantage与失败并存|数学实现未发现错配；总failure目标没有正收益；无精确minibatch轨迹/梯度消融|中低：需要最小对照|
|checkpoint/RNG/归一化恢复错误|本轮没有支持证据|51代model/actor/critic/Adam/RNG身份、19评价forward、原resume记录均通过；无VecNormalize|低：已检查范围不支持|
|执行门异常放行或硬安全被放宽|本轮没有支持证据|原拒绝/bridge/lifecycle与native审计通过；失败是拒绝而不是错误施加非法候选；G4全矩阵尚未闭合|低：不能据局部审计排除所有未测动作|

**PPO_STABILITY_CAUSE_IDENTIFIED=PARTIAL**。不声称统计显著性、患者泛化、已完成算法修复或确定catastrophic forgetting。

![已有记录的策略漂移和优化曲线](stability/PPO_STABILITY.png)

![原确定性050/080实际Human运动](stability/RETURN_REGRESSION.png)

源数据及PNG/PDF独立文件均在stability/；图只用真实历史点，没有从最终权重伪造历史loss。唯一下一研究建议见 `NEXT_RESEARCH_DECISION.md`。
