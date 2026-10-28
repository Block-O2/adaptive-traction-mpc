# E common OUT0：F1实际结果

一次批准执行成功，253/253 multihead solve、3982 scalarhead、11次训练集normalizer、508次预测API/923808 query，均与冻结合同一致。外部wall4.16s、user3.49s+sys0.34s、峰值205684KiB；内部wall4.104563s/CPU3.783877s。0梯度、0physics、0sealed，未执行F2，也未按结果重拟合或选超参数。

数据为48条已关闭物理轨迹、10同父context/10 distinct case SHA；9组五完整recipe，EARLYH01仅3条，缺失两条保持unknown。共同输入是各组真正动作前OUT0的39维原因果字段，未来仅作label。下面均为整case LOCO开发诊断，不能称临床独立患者效果。每时域38个非B对比、93个观测recipe pair；资格只在窗口选择后回顾，未作为选择mask。

## 动作效应、符号与排序

0.5s和1s各有19/38个非B对比是真tie；93个pair中28个真tie。主要是尚未激活的late动作。真tie不计入sign/rank分母；预测tie不获正确分。2s/4s各38个非B对比、93个pair均为真非tie。

|时域s|Action-only ΔJF MAE Ns|Paired context×action ΔJF MAE Ns|Action-only ΔJM MAE Nms|Paired ΔJM MAE Nms|Paired JF/JM正确符号|Action-only/paired正确排序|
|---:|---:|---:|---:|---:|---:|---:|
|0.5|0.09659|0.05942|0.01972|0.01265|17/19；16/19|56/65；54/65|
|1|0.22554|0.21983|0.04595|0.02908|16/19；17/19|56/65；51/65|
|2|0.55450|0.56699|0.15655|0.07608|33/38；34/38|75/93；74/93|
|4|1.41852|2.52436|0.46812|0.38689|36/38；34/38|82/93；78/93|

Paired对零效应基线的ΔJF MAE skill为34.35%、32.92%、32.79%、35.26%；ΔJM为33.61%、30.84%、36.55%、34.52%。它恢复部分动作响应，尤其JM误差优于仅recipe；JF在2s/4s没有超过action-only，排序各时域也未超过action-only，尚无全面个体化优势证据。

Action-blind与固定kinematic/persistence对同父所有recipe给相同cost，动作效应一律预测0；4s ΔJF/ΔJM MAE=3.89922/0.59087，非tie正确符号与排序均0。该结果说明action-conditioned响应有信息，不能把action-blind的B tie-break和全资格10/10解释成动作识别。

4s absolute context×action ΔJF/ΔJM MAE=4.04178/0.71080；kinematic residual=3.28775/0.49813。直接absolute的LOCO动作效应甚至差于零效应。Paired改善同父相对量，不意味着绝对终点、积分成本或完整任务已被准确预测；in-sample paired4s MAE=1.93098/0.29271，明显好于LOCO，必须保留差距。

4s窗口选择后的原完整资格：action-only5/10、paired5/10、absolute6/10、residual6/10、B tie-break10/10。action-only窗口JF regret仅0.02483Ns，却有5/10所选原任务不合格；paired regret0.17574Ns且同为5/10。窗口低成本不能代替完整motion/hard门，也没有新的物理部署许可。

## 固定OUT0长展开失败

三种query-curve仅训练0..4s、不读未来状态/ref/wrench，8/12/16s为外推。它们不是Markov simulator。动作条件的anchored与kinematic-residual curve对wrench预测相同：kinematic差异只进入q/ref基线，不影响相同wrench拟合目标。

|时域s|动作条件curve ΔJF/ΔJM MAE|绝对积分JF/JM MAE|q1/q2终点MAE deg|JF正确符号；排序|
|---:|---:|---:|---:|---:|
|4|39.85695 / 2.44599|35.50495 / 2.88751|16.56 / 15.43|32/38；71/93|
|8|252.31280 / 24.92531|338.94320 / 64.85121|87.54 / 73.89|6/38；23/93|
|12|927.14981 / 94.90632|2508.38246 / 345.53026|270.10 / 249.83|6/38；24/93|
|16|2371.73497 / 265.02270|7897.76254 / 939.74767|538.03 / 518.61|6/38；34/93|

连4s curve积分动作响应也远差于直接cost头。4s direct residual与其wrench积分的ΔJF/ΔJM平均绝对不一致=38.57506/2.75986。16s action-blind curve绝对JF MAE也达7567.19Ns；共同的低阶time基外推失效，不能归因成“已学会但仅动作选择差”。本F1不支持长展开或直接planner控制。可考虑机制修正须另立源码/审批，当前不自动加F2或扩大数据。

## 冻结证据

- 审批SHA `a1e2e055062465ce572688003c3d2c80b45f1499ddfaed0f767493db3a1b94ab`；source manifest `5b1a7a9ec9bbdb0ebededf7f90b2b93c08ab990b9f9c02bcf23b83aae9cc04cb`。
- 实际dataset manifest `3fc5c804158de7d1424e274058f0dd4ab62bd1f9d7f1410b92b57670b85506c7`；冻结全开发bundle `96a1123461db7ee420243001cbafc4a3a9f783cabb5bc07eea21000aaaafbfcc`。
- `F1_ACTUAL_OUTPUT_MANIFEST_V2.json` SHA `8a025df2b33fbd700be5569e37749d40267d2d54a024c42d3674003dc44ea878`；逐项摘要 `F1_ACTUAL_RESULTS_SUMMARY_V2.json` SHA `d29e0b4b5b71d911c68cebc6c0b1b837f72ce35f2762966bdad7487b8496e33d`。

V1补充的逐动作真label数组误配为排序后的recipe ID；V2按原INDEX顺序纠正。原fit、原预测/评分、全部数值聚合不变；V1和其manifest保留。两次纯JSON摘要共0.42s外wall、约0.42CPU，0额外预测/fit/raw。所有拟合中间snapshot/事件保留；没有复跑。
