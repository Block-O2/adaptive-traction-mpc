# Neural Q离线对照

终态 **EXPLORATORY**；当前测试实际决策优势 **FAIL / NOT_DEMONSTRATED**，进入host条件 **NOT_READY**。保留两个权重及负结果，没有test驱动追加搜索。

A=冻结native120D linear/fixed masked ranking；B=同一冻结NPZ中的历史120D MLP；C=joint120D→32ReLU→32ReLU→1 challenger。候选、observed合法mask、实际完整snapshot与分支标签、测试预算完全相同。尚未形成受运动资格约束的可部署选择器。

## 训练与选择

固定seed2026100803、CPU single thread、Adam lr0.001/weight_decay0.001、600epochs；loss=normalized absolute MSE+10×同完整snapshot的pair-difference MSE；每10epochs按validation regret再RMSE保存最佳。仅比较16×16/32×32，未训练G/P与辅助head。两者validation regret0；32×32的RMSE13.1024优于16×16的16.1091，故选32×32。Best epoch 590；Torch/NumPy inference parity误差0.000122N·s。所选weight SHA256 `2f242e87218063fc22ced59434aa85efafc3691e53a718b60b1bdb5fd939716d`。

## 预测、排序与真实selection regret

| 模型 | split | 状态组 | RMSE N·s | MAE N·s | pair准确率 | top1 | mean regret N·s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_frozen_linear | validation | 3 | 10.6034 | 8.5829 | 0.9429 | 1.0000 | 0.0000 |
| A_frozen_linear | test | 2 | 7.3311 | 5.5835 | 0.9531 | 0.5000 | 1.6207 |
| B_historical_MLP120 | validation | 3 | 11.6887 | 9.9333 | 0.8571 | 0.6667 | 1.4187 |
| B_historical_MLP120 | test | 2 | 28.9956 | 23.7899 | 0.8438 | 0.0000 | 16.6014 |
| C_neural_challenger | validation | 3 | 13.1024 | 10.1919 | 1.0000 | 1.0000 | 0.0000 |
| C_neural_challenger | test | 2 | 25.7824 | 19.9929 | 0.9062 | 0.5000 | 9.9306 |


Test2个state、17个候选、64个非tie pair，不能当作64个独立样本。Challenger mean regret9.9306，冻结linear1.6207，差值+8.3099N·s；历史MLP16.6014。新模型比历史MLP部分改善，但没有超过旧固定排序。Top1同为0.5不能掩盖错误选择的实际cost差。

| 模型 | snapshot | 候选数 | 真实cost spread | 所选计划 | regret N·s |
| --- | --- | --- | --- | --- | --- |
| A_frozen_linear | 4144eeb5de | 8 | 106.3195 | v1_committed_attribution_OUTBOUND_2_candidate1 | 3.2413 |
| A_frozen_linear | 4a5c0e6361 | 9 | 85.7569 | v1_committed_attribution_RETURN_1_candidate1 | 0.0000 |
| B_historical_MLP120 | 4144eeb5de | 8 | 106.3195 | v1_committed_attribution_OUTBOUND_2_candidate7 | 19.8612 |
| B_historical_MLP120 | 4a5c0e6361 | 9 | 85.7569 | v1_committed_attribution_RETURN_1_candidate2 | 13.3416 |
| C_neural_challenger | 4144eeb5de | 8 | 106.3195 | v1_committed_attribution_OUTBOUND_2_candidate7 | 19.8612 |
| C_neural_challenger | 4a5c0e6361 | 9 | 85.7569 | v1_committed_attribution_RETURN_1_candidate1 | 0.0000 |


OUTBOUND状态真实best为candidate6，而challenger选candidate7产生19.8612N·s regret；RETURN选candidate1为正确。当前两个state的candidate集合/issued mask不同，不能把这种跨phase best身份变化当作“同固定候选集下最优随state变化”的充分证明；相关能力仍UNRESOLVED。冻结方案在RETURN确实最优，保持排序是正确行为。

## state×plan能力与有效学习必须分开

固定±0.2合成候选、固定mask/carry/count，仅交换真实state/history的结构probe：linear candidate score差随state的范围约2.27e-13N·s；历史MLP40.063、新MLP18.019N·s。支持两MLP存在交互表达且本checkpoint有非加性响应；这些合成feature组合没有真实rollout标签，**不是决策优势证据**。没有把ranking inversion数量作为成功指标。

## 真实运动与其他物理代价

每个test candidate导出remaining任务的sampled运动速度/加速度/jerk、force peak、moment、true-reference tracking、clearance、实际幅度/时长、原native qualification；每模型的选择附同样labels。没有把所有代价随意加权为reward。原native安全与完成有效，但不能自动承认额外运动代价可接受。

预注册B-relative ratios=1.0/1.1/1.25的敏感性筛选同时比较真实速度/加速度/jerk max,p95,p99：1.0和1.1下三个模型都回到两个state的B候选；1.25下OUTBOUND选candidate8、RETURN仍B，三者相同。ratio是描述性分析，不是临床阈值、也不是“+25%自动可接受”。筛选使用真实未来label，是**outcome-oracle analysis**，不可部署，未参与模型选择。它提示严格B负担约束下当前候选空间的力收益选择有限，但不足以证明空间根本无解。

本轮并未改善force/真实平顺性权衡。候选安全硬mask不能用future真值实时构造，未来要有可信的前瞻性筛选/辅助预测合同。样本不足以训练并验证motion辅助head，所以未这样做。

## 推理、内存和特征可用性

| 模型 | batch | p50 ms | p95 ms | score所需bytes | loaded bundle bytes |
| --- | --- | --- | --- | --- | --- |
| A_frozen_linear | 9 | 0.0038 | 0.0039 | 1944 | 304900 |
| B_historical_MLP120 | 9 | 0.0237 | 0.0327 | 129492 | 304900 |
| C_neural_challenger | 9 | 0.0107 | 0.0110 | 20820 | 20820 |


单线程NumPy、9候选batch、20warmup/300 measurements。Loaded old bundle含G及未使用Q权重；score所需bytes才是可抽取部署权重大小。上述是CPU评分微基准，未包括native candidate构造、admission、bridge、lifecycle、host contention，不能推断40ms路径资格。现有native TASK已可提供120D feature，新scorer只读Nx120、不导入plant、无actuation/update；mask与安全仍是原caller责任。

## 失败归因与下一轮条件

主要瓶颈SUPPORTED为数据有效覆盖小（8train snapshot、3validation、2test且历史暴露），而非已证明容量不足；增加容量尚无依据。Observed排名失败保留；labels有合法历史完整fork证据，但committed suffix监督与重复host replanning不同，泛化及continuation-policy mismatch UNRESOLVED。候选空间与motion资格同样有瓶颈迹象，不能将其全部归咎MLP。

下一轮先补充独立来源、完整state分支、dense运动标签及同固定候选下真实state-dependent最优的离线数据；冻结B参考与平顺性接受口径，再按预注册模型选择比较。只有独立test的regret优于linear、任务/幅度/时间/原native安全公平、运动负担规则满足、feature/scorer parity与影子评分链完整、原FAST资格轴单独记录后，才考虑新的host-clock工作包。本轮没有启动或激活新控制器。
