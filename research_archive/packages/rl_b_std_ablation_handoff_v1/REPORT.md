# iHEAR Lab — PPO STD 真实消融与自主研究交接 v1

**本轮结果与交接已完成；不启动下一轮训练。**

T0：2026-10-21T04:42:42+00:00（北京时间 2026-10-21T12:42:42+08:00）；硬截止：2026-10-21T07:42:42+00:00。本轮28次真实MuJoCo冻结attempt：pilot2、C身份回归2、正式配对24；native steps 3,056,220，训练0、梯度/Adam0。另有2个物理启动前工程失败，未占用物理attempt，均保留。实际关闭时间与总wall见END.json/RESOURCE_USAGE.json。

## 正式配对结果

|父seed|A 原STD complete|B STD=.2 complete|A全部准入拒绝 OUT/HOLD/RETURN|B全部准入拒绝 OUT/HOLD/RETURN|配对 A-only/B-only|
|---|---|---|---|---|---|
|1495656323|4/6|5/6|[5, 0, 13]|[0, 0, 4]|0/1|
|1630784693|3/6|6/6|[3, 0, 10]|[0, 0, 0]|0/3|

|父seed/arm|几何拒绝 OUT/HOLD/RETURN|参考回退拒绝 OUT/HOLD/RETURN|其他拒绝 OUT/HOLD/RETURN|
|---|---|---|---|
|1495656323/A|[0, 0, 5]|[5, 0, 8]|[0, 0, 0]|
|1495656323/B|[0, 0, 4]|[0, 0, 0]|[0, 0, 0]|
|1630784693/A|[1, 0, 5]|[2, 0, 5]|[0, 0, 0]|
|1630784693/B|[0, 0, 0]|[0, 0, 0]|[0, 0, 0]|

35条全部准入拒绝中，15条是geometry、20条是emitted-reference回退拒绝；两类均保留原规则与标签。6个正式runtime失败的终末原因全部是geometry。不能把非致命回退拒绝计为几何拒绝。

每父独立报告；pilot不计入正式成功率。两父C均精确复现历史完整19.030秒mean轨迹。所有新流202610213101–106已在pilot前保存，旧2191–2194未重用为未见测试。

## 十四问

1. **原R1/60真实STD？** 149父为[0.9865387678, 0.9812663198]；163父为[0.9984146357, 0.9717715383]。不是精确1。完整log_std、actor/critic/Adam/RNG/ZIP身份见ACTION_DISTRIBUTION_AUDIT与CHECKPOINT_IDENTITY。

2. **STD=.2是否减少几何拒绝？** 在本次已测动作流中两个父均减少了准入拒绝，但没有消除。上表将几何拒绝、emitted-reference回退拒绝分别列出；完整率与非致命拒绝也分开。此为固定actor mean函数/权重与原物理合同下的冻结闭环对照。每对pre-TASK完整物理hash一致、噪声索引一致，之后状态允许分歧。只描述实际计数，不宣称唯一控制失败根因。

3. **两个父的任务完成？** 见上表与逐条表；C两父完整。任何失败保留FAILED_PARTIAL_TASK、原reason与真实native/raw，不用partial低JF/JM争优。

4. **deterministic/stochastic差距？** mean身份回归保持完整；A/B已测随机完成数如上，判定为`SUPPORTED_SMALL_N_PAIRED_NOMINAL_ONLY`。每父仅6对，不能外推总体可靠率或跨患者泛化。逐父配对探索性双侧exact p为1.0、0.25；不能视为总体可靠性提升的统计证明，也不能合并不同父为单一策略。

5. **JF/JM与Human motion取舍？** 完整任务时长、JF/JM、tracking、native速度/加速度/jerk和RETURN overshoot逐条保存。只有同父A/B均完整且任务等时才列直接JF/JM差；其余差值设null。不按幸存完整子集的均值宣称总体优越。下表与tables/std_attempts.csv可复核；图中灰线只连接等时完整pair。

6. **新实际安全或Reward漏洞？** 28次保存raw经新进程复算原native ownership/receipt、ROM/速度/加速度/torque/force/moment/clearance/接触审计均通过；failed Reward为负且R1总式独立一致。未观察到新的实际安全违规或Reward漏洞。几何准入拒绝为执行前拒绝，不当作实际碰撞；不将有限观察升级为所有路径安全。

7. **H2/R0与R1贡献？** H2主要支持两成功050父在已测30/60 mean保持，不能唯一归于更少Adam。R1相对H2跨父无一致额外JF/JM优势；149 JF+0.171779%/JM−0.372914%，163 JF−0.229365%/JM+0.812868%。R1两父减小RETURN knee overshoot，tracking/jerk取舍仍在。六条raw独立复算且执行/任务合同一致；训练更新后的轨迹/样本已分离，不是严格同轨迹Reward因果对照。

8. **Reward下一步？** 首选可证伪R4：R1的moment权重.005→.020，其余项/floor不变；R1/R4同父分叉各10集×2父。备选R5合法状态/停止误差potential、R6 causal运动与RETURN超调成本，最多3方向。R4算术已在52条保存因果轨迹重放通过；没有训练性能证据。固定R1成本在两个R1 mean上并未比原050更低，不能声称当前Reward目标已被优化或moment不足是唯一根因。

9. **能安全执行7–8小时无人值守？** 控制准备状态为`READY_FOR_EXPLICITLY_AUTHORIZED_BOUNDED_DEVELOPMENT`，下一轮未启动。本轮只验证源身份、控制器fake-job场景、预算/关闭与密度算式；新STD/R4训练没有端到端运行。采用旧9.11小时实测机制，加每次更新前分布归属guard、每episode完整pending checkpoint与有界关闭。发生完整性/安全/资源控制失效将停止，不保证全部optional分支完成或科学收益。

10. **会导致过早STOP的调度缺陷？** 旧campaign收尾的`dict(**state,status=...)`重复键TypeError已在新模板中修复；正常/普通分支失败与全局停止路径均经实际控制器fake-job验证。另移除会阻断新Reward分支的旧cohort协议依赖，纠正累计episode标签，并让独立reviewer和reporter受硬截止控制；watchdog已做真实一次性进程测试。普通ABORTED与失败screen继续下一预定假设；已确认物理前恢复拒绝局部跳过；未知安全/身份异常保守全局停止。预算窗口正常关闭保留结果并使用最终评价预留，不无限追加实验。

11. **下一轮实验和episode？** 推荐方法 `['CHECKPOINT_STD', 'STD_INIT_0p2']`：2方法×2父×10=40，达门者各延长20至30（最多80）；选定方法下R1/R4各父10=40。总训练最多160集；开发评价24，最终锁定后12条保留流；36评价、33M native、8小时硬限。按历史实测吞吐，历史混合约3.89h计算；全部attempt按165k最坏native估约6.52h，再留45分钟。

12. **用哪些父checkpoint/hash？** 固定当前两R1/60，ZIP SHA见下节；完整policy/critic/Adam/RNG/metadata SHA及原050、H2/R0/60保留路径见NEXT_PARENT_CHECKPOINTS.json。B冻结不覆盖checkpoint。下一阶段STD初始化是显式新policy身份，不能沿用旧log_prob或跨分布pending。

13. **哪些仅nominal/开发证据？** 本轮全部A/B/C、历史六条mean、H2/R1收益/运动权衡、Reward算术和mock调度。新动作流只改变动作噪声，物理初始化仍是原nominal，不是独立患者/初态。后续7–8h也是开发研究，不能转正。

14. **G4/live matched/Stage2缺口？** G4严格全矩阵及自然极端失败链未闭合；新PPO缺原同父prefix完整可移植fork和原B/H150同链live matched；独立合法初态/跨患者验证、长窗口随机稳定性仍缺。原scorer离线PASS不等于新PPO正式收益。G4=FAIL，live matched/Stage2/final Campaign均NOT_READY。

## 下一轮父模型

|父seed|R1/60 ZIP SHA256|
|---|---|
|1495656323|a2fb5efe642b460ee19ebd0997052997e5157bc21d7931299b2fa10eee8f3132|
|1630784693|0f559270cdad9ad4a8bbbdb3820713ae38ec516579b09d1c3e4fc8e760a74992|

## 保留的几何失败反例

- 父1630784693 / A / 流202610213103：0.00500s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-37.005716 mm)；末决策noise_index=0，mean=[0.6684557199478149, 1.0796456336975098]，raw=[-0.3967764377593994, 0.8207951784133911]，clip=[-0.3967764377593994, 0.8207951784133911]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。
- 父1495656323 / B / 流202610213104：15.96000s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-72.658517 mm)；末决策noise_index=16，mean=[0.481439471244812, 0.44597163796424866]，raw=[0.5769091248512268, 0.29737645387649536]，clip=[0.5769091248512268, 0.29737645387649536]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。
- 父1495656323 / A / 流202610213104：16.90000s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-258.063683 mm)；末决策noise_index=20，mean=[0.4464893341064453, 0.43041160702705383]，raw=[1.5904754400253296, -0.8500304222106934]，clip=[1.0, -0.8500304222106934]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。
- 父1630784693 / A / 流202610213104：17.16000s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-206.262273 mm)；末决策noise_index=20，mean=[0.41138598322868347, 0.6973475217819214]，raw=[1.5691434144973755, -0.5707048177719116]，clip=[1.0, -0.5707048177719116]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。
- 父1495656323 / A / 流202610213105：16.17500s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-141.663804 mm)；末决策noise_index=18，mean=[0.5039344429969788, 0.4241926074028015]，raw=[0.5614960193634033, 0.02865394949913025]，clip=[0.5614960193634033, 0.02865394949913025]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。
- 父1630784693 / A / 流202610213105：15.77000s，NO_FEASIBLE_WAYPOINT:state-feedback Human-waypoint MPC has no feasible candidate: target waypoint enters existing shank-table geometry (-56.009225 mm)；末决策noise_index=15，mean=[0.4037768244743347, 0.6815253496170044]，raw=[1.1491663455963135, 0.3979557752609253]，clip=[1.0, 0.3979557752609253]。JF/JM为FAILED_PARTIAL_TASK，不参与完整收益。

B=.2在RETURN内仍可失败，且已观察到末次raw完全在边界内；减小噪声不能保证两个独立进度fraction产生几何合法协调。当前闭环轨迹已分歧，无法从末步数值唯一识别原因；未来若研究协调参数化，必须保留原planner/certificate/admission，先设计有限机制试验，不能放宽准入。

## 逐条正式评价（partial独立列身份）

|父seed|流|arm|runtime|task s|JF N·s|JM Nm·s|积分身份|knee tracking °|knee jerk °/s³|RETURN knee overshoot °|
|---|---|---|---|---|---|---|---|---|---|
|1495656323|202610213101|A|COMPLETE|19.03000|1417.370186|90.979612|COMPLETE_TASK|0.76130|946.693|0.981023046218218|
|1495656323|202610213101|B|COMPLETE|19.03000|1432.210108|104.638080|COMPLETE_TASK|0.51025|885.036|1.152351061154639|
|1630784693|202610213101|A|COMPLETE|19.07500|1399.155444|92.193862|COMPLETE_TASK|0.79790|891.686|3.7771328594460014|
|1630784693|202610213101|B|COMPLETE|19.03000|1421.066861|106.538748|COMPLETE_TASK|0.68456|823.756|2.433003120522704|
|1495656323|202610213102|B|COMPLETE|19.03000|1427.263073|105.640709|COMPLETE_TASK|0.52565|880.293|1.502844790714006|
|1495656323|202610213102|A|COMPLETE|19.13500|1340.986760|105.326062|COMPLETE_TASK|1.00079|984.856|2.383283567808955|
|1630784693|202610213102|B|COMPLETE|19.03000|1417.421997|106.367436|COMPLETE_TASK|0.70730|811.121|2.5317721162657456|
|1630784693|202610213102|A|COMPLETE|19.03000|1352.200239|102.083163|COMPLETE_TASK|1.04818|967.068|4.032073165037009|
|1495656323|202610213103|A|COMPLETE|19.03000|1476.691267|93.542532|COMPLETE_TASK|0.98462|1125.077|2.2818094390408654|
|1495656323|202610213103|B|COMPLETE|19.03000|1424.287200|105.694469|COMPLETE_TASK|0.52995|863.991|0.9895218230101005|
|1630784693|202610213103|A|ABORTED|0.00500|0.394471|0.063241|FAILED_PARTIAL_TASK|0.00044|0.132|未到RETURN|
|1630784693|202610213103|B|COMPLETE|19.03000|1423.864963|104.444768|COMPLETE_TASK|0.71224|809.019|2.4642551613446573|
|1495656323|202610213104|B|ABORTED|15.96000|1209.544712|65.491376|FAILED_PARTIAL_TASK|0.53962|996.037|0.0|
|1495656323|202610213104|A|ABORTED|16.90000|1318.725224|63.357926|FAILED_PARTIAL_TASK|0.72479|1089.577|0.0|
|1630784693|202610213104|B|COMPLETE|19.03000|1441.445929|101.260683|COMPLETE_TASK|0.62117|822.741|2.4535947221253407|
|1630784693|202610213104|A|ABORTED|17.16000|1342.655559|63.038039|FAILED_PARTIAL_TASK|0.63553|1040.294|0.0|
|1495656323|202610213105|A|ABORTED|16.17500|1243.982362|65.359556|FAILED_PARTIAL_TASK|0.63574|998.409|0.0|
|1495656323|202610213105|B|COMPLETE|19.03000|1448.829345|100.727557|COMPLETE_TASK|0.50577|931.653|0.0|
|1630784693|202610213105|A|ABORTED|15.77000|1204.665127|63.134338|FAILED_PARTIAL_TASK|0.60640|922.026|0.0|
|1630784693|202610213105|B|COMPLETE|19.03000|1429.903238|104.393371|COMPLETE_TASK|0.61564|757.782|3.314928652695029|
|1495656323|202610213106|B|COMPLETE|19.03000|1420.608463|107.750730|COMPLETE_TASK|0.63784|1027.560|0.7331776202819352|
|1495656323|202610213106|A|COMPLETE|19.33500|1343.364546|125.676357|COMPLETE_TASK|1.05603|1156.225|2.4390917039745883|
|1630784693|202610213106|B|COMPLETE|19.03000|1402.830422|110.647822|COMPLETE_TASK|0.69007|865.058|2.4633626972366156|
|1630784693|202610213106|A|COMPLETE|19.62500|1292.961373|119.359765|COMPLETE_TASK|1.08142|1161.719|2.5514764635418334|

## 等时完整配对差（B−A）

|父seed|动作流|JF差 N·s|JM差 Nm·s|
|---|---|---|---|
|1495656323|202610213101|+14.839923|+13.658468|
|1495656323|202610213103|-52.404068|+12.151938|
|1630784693|202610213102|+65.221758|+4.284273|

这些pair只是被观察为均完整且等时的子集，不能借条件筛选宣称总体效率冠军。不同时间和partial全部保留，未列直接收益。

## 独立状态

|状态|结果|
|---|---|
|STD_ABLATION_COMPLETE|PASS|
|STOCHASTIC_RELIABILITY_SIGNAL|SUPPORTED_SMALL_N_PAIRED_NOMINAL_ONLY|
|H2_R1_COMPARISON_COMPLETE|PASS|
|REWARD_NEXT_HYPOTHESES_READY|PASS_PROPOSALS_ONLY|
|UNATTENDED_EXECUTION_READY|READY_FOR_EXPLICITLY_AUTHORIZED_BOUNDED_DEVELOPMENT|
|G4_STRICT_PASS|FAIL|
|NEW_LIVE_MATCHED_READY|NOT_READY|
|STAGE2_READY|NOT_READY|
|FINAL_CAMPAIGN_READY|NOT_READY|

## 交付与复核入口

- 协议/动作：STD_ABLATION_PROTOCOL.md、ACTION_DISTRIBUTION_AUDIT.md、STD_ABLATION_RESULTS.json；tables/含attempt、policy action与pair CSV。
- 历史对照：H2_R1_COMPARISON.md、audit/H2_R1_COMPARISON.json、ONLINE_PROXY_VS_ACTUAL_MOTION和CUFF_TRADEOFF_MECHANISM。
- 提案/无人值守：REWARD_RESEARCH_PROPOSALS.md、UNATTENDED_CAMPAIGN_PLAN.md、UNATTENDED_EXECUTION_READINESS.json、AUTONOMOUS_HANDOFF.md、unattended/源码与版本定义。
- 账目/关闭：ATTEMPT_ACCOUNTING.json、RESOURCE_USAGE.json、PACKAGE_VERIFICATION.json；全部原native/receipt及JF/JM由audit/FINAL_FROZEN_RECHECK.json关联。
- 447个执行/任务/安全/scorer合同文件保持；87,733个历史保护文件SHA前后核验。全部owned新计算退出证据及manifest精确覆盖见最终PACKAGE_VERIFICATION。

本轮未执行Git commit/push/reset/stash/clean、原物理/任务/安全/准入/scorer修改、历史checkpoint覆盖、服务器租赁/升级、Stage2或下一轮训练。最终终态为STOP，具体关闭证据以PACKAGE_VERIFICATION为准。

## 完整等时pair的Human运动与执行年龄

仅下面3个同父、均完整且等时的pair可直接比较剂量。差值均为B−A；负tracking/jerk/overshoot代表该指标较小，不据此推断总体优越。

|父seed|流|ΔJF N·s|ΔJM Nm·s|Δhip/knee tracking °|Δhip/knee jerk °/s³|ΔRETURN knee overshoot °|
|---|---|---|---|---|---|---|
|1495656323|202610213101|+14.839923|+13.658468|+0.0016/-0.2510|+13.0717/-61.6568|+0.1713|
|1495656323|202610213103|-52.404068|+12.151938|-0.0408/-0.4547|-82.2926/-261.0861|-1.2923|
|1630784693|202610213102|+65.221758|+4.284273|-0.0071/-0.3409|-26.1872/-155.9471|-1.5003|

这3个等时完整pair中B的JM均增加，JF方向不一致；因此“拒绝减少/完成数增加”不能解释为force、moment和Human运动的全面改善。

|父seed/arm|planner实际source-age最大 ms（仿真时钟）|receipt实际source-age最大 ms（仿真时钟）|planner host activation-age最大 ms|receipt host apply-age最大 ms|TASK applied receipts|
|---|---|---|---|---|---|
|1495656323/A|5.000000|0.000000|46.505846|24.815444|21921|
|1495656323/B|5.000000|0.000000|57.754804|27.720363|22222|
|1630784693/A|5.000000|0.000000|58.206593|37.392023|18133|
|1630784693/B|5.000000|0.000000|45.767246|25.793751|22836|

年龄来自保存request/receipt的不可变source sample与实际activation/apply时间戳，未用刷新样本伪装较低age。仿真与host时钟明确分开；以上不构成主机100ms硬实时或机器人硬件资格。全部实际6D torque和native归属留在各run的TASK_APPLIED_RECEIPTS_v2.npz及原raw。

两父C以及所有B完整任务均为19.030秒；A完整任务另有19.075、19.135、19.335、19.625秒。其JF/JM全部列原值，未以跨时长差值宣称效率改善。

准备过程还修正过零物理的路径、序列化和报告插入问题；2个实际物理job在native启动前失败的END另计，不算MuJoCo attempt。工程事件见audit/ENGINEERING_CORRECTIONS_LEDGER.json。
