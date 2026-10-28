# 学习辅助优化与动力学模型

SUPPORTED：过去历史、共同OUT0直接目标和完整时间域覆盖提供了预测信息，部分改变了开发候选排序。冻结新参数已实测：D4 paired RAW0/2、DFull paired RAW1/2、DFull配A3 risk0/2；合格动作与固定H相同，个体化与强基线增量未建立。当前家族为NOT_FULLY_EXPLORED。

本轮从44条已有完整因果轨迹构建6个整context开发折，保留完整motion失败作为动力学观测；1条partial不参加完整成本排名。依次检验绝对next-observation、已知运动学加学习残差、过去3个boundary历史残差，再直接预测0.5/1/2秒终点变化与JF/JM分量。自由展开不回灌未来reference、wrench或Human真值，未来观测只作监督标签。

|自回归模型|一步hip q RMSE / rad|自由展开窗口JF MAE / N·s|非有限窗口|
|---|---:|---:|---:|
|绝对状态|0.03171675|9.79772|0|
|运动学＋学习残差|0.000002990|13.2416|0|
|过去历史＋残差|0.000001144|1.64477|0|

简单运动学一步hip q RMSE为0.000004811 rad。残差的一步状态误差降低，并未自动降低自由展开成本误差；历史版本改善了展开JF，但未一致改善全部动作效应误差。这直接排除了“低一步RMSE即可进行控制”的推论。

|直接时域 / s|JF MAE|持久值JF MAE|JM MAE|持久值JM MAE|终点hip q MAE / rad|
|---|---:|---:|---:|---:|---:|
|0.5|2.18037|1.85900|0.063824|0.296536|0.007573|
|1.0|5.03254|7.49158|0.272252|1.14210|0.038539|
|2.0|12.0119|27.3023|1.27207|1.79556|0.090116|

直接目标在1–2秒改善JF窗口预测，在0.5秒弱于简单持久值；JM窗口预测三个时域均改善。40个非平凡相对B动作窗口的方向正确数为绝对38、残差23、历史残差38，对比MAE分别0.669553、0.553363、0.659446 N·s。方向与幅值必须并列，不能只选择更好的指标。

首个测量点已处于动作后的boundary，可能包含动作造成的状态差异。因此这些窗口动作对比不能称OUT0反事实排序，不能直接将其梯度交给planner。原planner未来reference/phase结构、概率ensemble、可靠模型不确定性、模型梯度控制和共同动作前独立控制验证均为NOT_RUN。PETS仅提供先检验模型响应与展开误差的参考，未复现其概率ensemble/trajectory sampling/CEM。

实际两轮共36个ridge求解，约7.99＋3.15秒wall、8.07＋3.23秒CPU，峰RSS约598MiB；0新物理、0策略更新、0实际省试。开发数据、过程START/END与源码身份见[家族结果](families/learning_assisted/RESULTS_V1.md)和[方法矩阵](families/learning_assisted/METHOD_EXPLORATION_MATRIX.md)。本轮先优先解决真实新状态采样、可执行动作与持续Trial接口，不据这些局部结果否定World Model家族。

## 共同 OUT0：F1

从48条原完整任务、10个case构建精确相同动作前起点；39D当前因果状态和第一TASK的14项状态/reference/wrench逐项一致。未来轨迹仅作标签，17条完整motion失败保留，缺失的两个phase格不填。原5ms左积分闭合。实际253次多RHS求解/3982头、508预测API，0新物理。

比较action-blind、action-only、context×action、运动学残差、paired相对B，以及锚定时间曲线。paired 0.5/1/2/4s的ΔJF MAE约.0594/.2198/.5670/2.5244；4s强action-only为1.4185，排序82/93优于paired78/93。用4s成本挑选的完整资格仅5/10，B为10/10。短期成本信息不能代替完整运动资格。

4s曲线外推16s出现严重误差；该观察同时受训练时间域限制，因而单独否证“加大网络即可修好”或整个World Model都不成立。

## 匹配训练时点数量：E2

完整19.03s/3807节点数据一次扩展构建成功，原48输入、菜单、顺序和F1标签前缀均校验。D4与DFull各用8个训练时点：D4到4s，DFull覆盖到19.03s。11训练范围（全开发+10整case LOCO），比较四类knotwise ridge和三类tanh16、固定200步Adam；两个时间域同模型初始权重相同。dense节点仅用于评价，不偷增监督点。

合成数学门一次通过192个FD坐标、共享A−B梯度、16头物理解码、零锚和独立标量Adam。真实fit一次完成704求解/11264头、66初始化/13200更新、17600训练forward及同数backward，2240预测API/5853696 query vectors；外wall20.38s，内部CPU约11.51s，峰RSS约194MiB。0新物理、0额外控制rollout。

|19.03s开发LOCO direct成本头|ΔJF MAE / N·s|ΔJM MAE / N·m·s|JF排序正确/93|所选原完整合格/10|
|---|---:|---:|---:|---:|
|D4 action-only ridge|13.5719|5.4307|65|5|
|DFull action-only ridge|12.9251|3.1975|65|5|
|D4 context×action ridge|29.7349|6.1076|68|6|
|DFull context×action ridge|26.2651|3.7123|68|6|
|D4 paired MLP|27.9878|4.4033|75|5|
|DFull paired MLP|19.4582|3.8082|89|6|

**CONFIRMED：**DFull的context ridge在0–19.03s区间hip/knee q MAE由D4的123.77/75.91°降为4.59/4.14°，证明时间覆盖是严重外推误差的一个实际因素。MLP context相应仍约48.57/40.16°，容量增加没有自动修复绝对轨迹。

**CONFIRMED：**DFull paired MLP虽达到89/93排序、开发窗口regret0，却在十个case全部选EARLY_H150（该库无资格mask的实际JF最低固定动作），只有6/10完整合格。它不证明context个体化；强action-only的成本幅值MAE仍更好。预测JF/JM直接头和绝对预测wrench积分存在显著分歧，两者分别报告；paired积分为NOT_APPLICABLE，不对delta-wrench取范数当成本差，也不使用未来真实B轨迹重构。

下一步仅拟建立两个域中ridge/paired MLP的纯冻结末端推理，以及同一A3风险门下的固定H-else-B对照；SOURCE_ONLY，不自动授予控制资格。该模型仍是conditional trajectory surrogate，不是Markov动力学、PETS复现或可直接进行梯度规划的安全World Model。

证据：[E2完整开发汇总](families/learning_assisted/common_out0_v2/E2_ACTUAL_READONLY_SUMMARY_V1.json)、[真实fit](families/learning_assisted/common_out0_v2/fits/e2_v1/RUN_END.json)、[数学门](families/learning_assisted/common_out0_v2/synthetic/e2_math_v1/RESULT.json)。全bundle SHA：`56b32083ae55ff1cd5e8dc1f3c4e87c08cf4a7948f21fd4a19f9a12b3922f40e`。


10:35 UTC 实际冷OUT0整合 V8FROZENENG01 在B前停止：E2外层MLP记录实际只有 model/normalizer，旧适配器重复要求外层kind/paired；内层网络字段和权重原本正确。已付2个ridge API/10query，随后KeyError；父前缀40,200 native步、0候选child，原partial不排名，supervisor exit1且无survivor。此前synthetic parity验证的是数学路径，未覆盖真实外层序列化schema，不能称为实际部署接口通过。保留所有原失败/成本；新V2只修外层字段检查，先做真实冻结权重canary，再用新唯一作业组，不改原模型或任务。


11:40 UTC 口径核验：E2的开发5/10、6/10等资格计数来自leave-case-out预测器的原始假设window-JF最小选择，没有使用未来资格mask，也没有套A3风险门。实际冻结接口另包含四个RAW、四个A3风险<.5门及固定H-else-B共九个selector；使用全部开发训练后的冻结模型部署于新条件。两类结果分别报告，不能把开发计数当作含风险门的整条pipeline独立验证。此次仅静态源读取，0模型/数值/物理。


## E2原两新参数结果（未重训）

CONFIRMED：D4 paired MLP raw在两条件均不合格（重载partial、轻载完整motionfail）；DFull paired MLP raw为1/2，分别选择原EARLY_H150，轻载合格但重载KNEE partial，不能给重载补fullJF RMSE。DFull paired叠加原A3 risk门后轻载反改为失败EARLY_PHASE、合计0/2；风险头不是实际资格证明。全九个固定selector保留，raw开发LOCO与live全数据模型+风险部署不混称同一验证。

SUPPORTED：完整时间域训练在预测和这组有限部署中有可见作用，主raw依旧同选固定H，没有个体化/超强固定JF增量。新的适用性recipe与旧标签分开，不把旧E2选择移植到它。原来源/接口schema canary、36macro回执和原scorer回放已闭合；World Model/PETS/MPC系统仍未复现，家族NOT_FULLY_EXPLORED。
