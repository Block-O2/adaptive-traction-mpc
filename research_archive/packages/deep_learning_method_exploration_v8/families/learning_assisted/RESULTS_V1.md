# 学习动力学与辅助优化：阶段结果

结论：在44条已有完整因果轨迹、6个整context开发折中，历史残差改善一步预测，直接多时域模型在1–2秒改善部分窗口成本预测；尚无共同动作前起点的可靠候选排序或真实控制增量。家族为 **NOT_FULLY_EXPLORED**。

数据与身份：所有未来观测只作监督标签；自由展开不回灌未来reference、wrench或Human真值。完整motion失败保留用于动力学预测，1条partial不进入完整成本排名。首个测量起点已在动作后，可能含动作造成的状态差异；动作响应对比不能解读为OUT0反事实控制资格。

|自回归机制|一步hip q RMSE(rad)|展开窗口JF MAE(N·s)|非有限窗口|
|---|---:|---:|---:|
|absolute|0.03171675|9.79772|0|
|residual|2.9901925e-06|13.2416|0|
|history_residual|1.143599e-06|1.64477|0|

运动学基线hip q一步RMSE为 4.811348925009918e-06 rad。一步拟合与自主展开的误差是不同门。

|直接时域(s)|JF MAE|持久值JF MAE|JM MAE|持久值JM MAE|终点hip q MAE(rad)|
|---|---:|---:|---:|---:|---:|
|0.5|2.18037|1.859|0.063824|0.296536|0.00757253|
|1.0|5.03254|7.49158|0.272252|1.1421|0.0385389|
|2.0|12.0119|27.3023|1.27207|1.79556|0.0901157|

相对B的40个非平凡动作窗口成本对比：
- absolute：方向正确38/40，对比MAE 0.669553 N·s。
- residual：方向正确23/40，对比MAE 0.553363 N·s。
- history_residual：方向正确38/40，对比MAE 0.659446 N·s。

已实施修正：由绝对next-observation改为运动学加残差；加入合法3-boundary过去历史；随后直接预测0.5/1/2秒终点变化及JF/JM分量，避免反复一步传播。未改变原物理、planner、任务或评价门。

机制判断：CONFIRMED——一步状态误差不能授予控制有效性；SUPPORTED——过去历史和直接多时域目标在当前整context开发诊断中有信息；HYPOTHESIS——未来合法reference生成器/phase结构与足够动作覆盖可能改善模型；NOT_TESTED——模型梯度控制、概率ensemble、planner内反事实rollout及独立新条件控制收益。

资源：两轮共36个ridge求解；0新物理、0策略更新。E1 wall约7.99s/CPU8.07s，直接时域wall约3.15s/CPU3.23s；各进程峰值RSS约598MiB。原结果、进程START/END及源/数据SHA均保留。

后续决定：优先真实新条件策略采样与连续Trial接口闭合。当前数据不足以批准复杂World Model驱动策略；不作World Model家族否定。未运行的E4/概率模型、原planner未来reference条件化与共同动作前验证明确保留为NOT_RUN。

证据：[汇总](analysis/DYNAMICS_DIAGNOSTIC_SUMMARY_V1.json)、[原自回归结果](analysis/CAUSAL_DYNAMICS_RESULTS_V1.json)、[直接时域结果](analysis/DIRECT_HORIZON_RESULTS_V2.json)。
