# iHEAR Lab — Motion-Aware Neural Q v1

终态：**EXPLORATORY_TRAINED / OFFLINE_ADVANTAGE_NOT_DEMONSTRATED / HOST_NOT_READY**。阶段A真实运动审计完成；阶段B两条历史MLP恢复完成；阶段C合法历史分支数据审计完成；阶段D两个小型challenger完成并仅用validation选择；阶段E直接对照完成，保留负结果。Package verification是证据/保护检查，不是科学或实时资格。

旧M2的力收益伴随真实knee速度/加速度负担上升：八组配对knee max速度、p95速度、p95加速度与RMS加速度均更高，轻度滤波不改变主要方向；真实knee excursion亦增加1.109–2.834°。Hip速度RMS略降、jerk结果混合。不能从moment integral推断momentum，也不能宣称临床不适。

新32×32 joint Neural Q具有state×plan交互，但在2个历史诊断测试state上的mean selection regret **9.9306N·s**，冻结linear为 **1.6207N·s**，历史128×128 MLP为 **16.6014N·s**。新模型没有显示超过固定排序的实际优势。80条合法branch-start row（47/16/17）来自8/3/2snapshot与2/1/1父轨迹，不能按行数宣称大数据或跨Human泛化。

## 执行边界与交付

独立Linux目录 `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_neural_q_motion_v1`；Windows交付副本 `C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_neural_q_motion_v1`。Python `/home/hank/envs/adaptive-online-rl-v1/bin/python`，与用户指定一致。Wall cap2.5h，新增离线rollout **0/12**，host-clock run **0**，无新persistent Human session、无plant重建、无G/P训练、无online adaptation。全部训练CPU单线程；无重型物理实验。

主要文件：MOTION_BURDEN_AUDIT.md/json及16条dense派生series/逐run审计；HISTORICAL_MLP_RECOVERY.md；DATASET_AUDIT.md/json与BRANCH_LABELS.json；TRAINING_MANIFEST.json与NEURAL_DATASET.npz；NEURAL_Q_EVALUATION.md/json；MODEL_AND_FEATURE_CONTRACT.json；两个models权重、offline_score.py；PREREGISTERED_PROTOCOL.json、保护快照、PACKAGE_VERIFICATION.json。所选模型 `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_neural_q_motion_v1/models/Q_32.npz` SHA256 `2f242e87218063fc22ced59434aa85efafc3691e53a718b60b1bdb5fd939716d`。原Q SHA256 `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9`，不变。

只增加本研究目录中的代码、数据派生与报告；原B/controller/commissioning、40ms bridge、100ms lifecycle、admission、causal ownership、native安全、carry/fallback与全部旧权重/结果未修改。未进行Git stage/commit/push/reset/branch变更；Git保护与历史hash核验见PACKAGE_VERIFICATION。原FAST未正式资格化，旧R2/strict55失败继续保留。

## 最终八问

1. **旧M2是否真的让人体运动更猛烈？SUPPORTED（限定指标）**：真实knee速度、加速度分布更高；jerk和hip表现混合。不能升级为普遍或临床结论。真实shank代表点与临床舒适性NOT_EVALUABLE。
2. **force收益是否符合新的目标优先级？UNRESOLVED/尚不能接受为整体成功**：第2层force收益成立，但第1层knee运动代价及第0层实际幅度差需先处理；原native安全PASS不等价于新平顺性目标满足。没有把所有正代价自动视作可接受。
3. **历史MLP当时表现如何，为何最终linear？CONFIRMED**：native120D MLP dev regret0.851245、RMSE11.21944，linear regret0、RMSE8.523668，所以按dev规则选linear。早期96D short MLP有优于ridge的test FULL regret，不能笼统说MLP必然差；早期ridge含显式交互，当前native linear没有。
4. **训练数据是否支持state-conditioned candidate ranking？SUPPORTED（探索性）**：真实同完整state多个候选、actual remaining cost、fork恢复证据存在；80rows仅13个snapshot与少量来源，独立泛化与同固定候选跨state变优证据不足。按来源/轨迹隔离，cross-split近重复为0。
5. **新Q比固定排序有实际优势？CONFIRMED（此样本负结果）**：未显示。Mean regret9.9306 vs1.6207，pairwise accuracy0.90625 vs0.953125，top1均0.5；不能用交互probe或validation loss称成功。
6. **是否改善force与平顺性权衡？UNRESOLVED / NOT_DEMONSTRATED**：B-relative future-label敏感性下三模型落到相同计划；不存在已验证可部署的smoothness gate。无法宣称更佳权衡。
7. **主要瓶颈是容量、数据还是计划空间？SUPPORTED：有效独立数据覆盖不足；UNRESOLVED：计划空间与continuation价值合同**。当前更大历史网络并未更好，容量不足未被证明。Motion约束下可选获益计划有限，不能宣称空间无解。
8. **具备下一轮原生host-clock验证条件？CONFIRMED：本challenger尚不具备**。先补独立来源的合法完整state分支及dense运动标签，冻结B-relative接受口径并完成直接优于linear的离线决策验证。保留接口与EXPLORATORY权重供复用；不启动下一包。

## 验证与负结果

源数据合法COMPLETE筛选、同snapshot feature equality、cross-split causal58 overlap=0、K3 mask重构、remaining integral与value_row闭合、Torch/NumPy parity、有限输入输出与错误输入拒绝、native q/dq映射、native时间严格增加、16run/8pair完整性、原Q identity与旧数据hash、Git保护、进程退出全部在独立验证脚本检查。原始失败DATA保留，历史坏结果未重写。两个容量候选及完整validation histories全部导出；未根据test再训练。

方法限制包括有限已暴露Human仿真、候选/phase mask变化、host commissioning差异、sampled force与branch辅助运动label分辨率、finite-difference jerk端点敏感性，以及committed suffix监督不等于host反复replanning policy价值。Observed host收益的原RETURN/平均力描述性归因保留，未重新作因果证明。

STOP：完成导出、校验、进程退出和Git保护检查后停止，不自动启动下一工作包。唯一建议下一步：另行有界补充独立完整state的离线候选数据与dense运动标签，先解决资格与排序证据。
