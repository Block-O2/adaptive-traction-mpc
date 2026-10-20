# Track D — 力、力矩与跟踪代价

## 完整配对结果
|运行|force RMS/peak N|moment integral/peak Nm·s/Nm|tracking RMS hip/knee °|min clearance m|
|---|---|---|---|---:|
|Adev_B|77.481390/114.607215|101.253695/15.515712|0.473481/0.461755|0.012758228|
|Adev_T|75.729012/113.781950|108.211827/15.515712|0.465747/0.520882|0.012970389|
|Adev_D|75.659791/113.781950|108.383202/15.515712|0.465208/0.527000|0.012367365|
|Adev_ER|75.679143/113.781950|107.118048/15.515712|0.456454/0.526051|0.012464890|
|Adev_AV090|75.704197/113.781950|107.090672/15.515712|0.455803/0.516728|0.012496625|
|Adev_AV080|75.729646/113.781950|107.062046/15.515712|0.455288/0.509490|0.012528875|
|Bmap_B|77.291450/114.607215|102.353134/15.515712|0.473868/0.470892|0.011888026|
|Bmap_T|75.578574/113.781950|109.132592/15.515712|0.464742/0.531108|0.012330171|
|Bmap_D|75.507197/113.781950|109.302134/15.515712|0.464194/0.538586|0.011977966|
|Bmap_ER|75.516166/113.781950|108.052936/15.515712|0.455384/0.536276|0.012026077|

W1 ER比匹配B降低J_F 2.353869%，moment integral却由101.253695升到107.118048 Nm·s（+5.791742%）。降低force不能解释为全部交互负担下降。moment仍通过原1.25工程比例门，不由此得到临床舒适性。

两个速度候选相对ER的完整J_F增加，不能称降力改进；Tracking RMS、moment peak/integral、clearance及原absolute safety均单独检查。各phase积分和峰值见EXPERIMENT_RESULTS.json/complete_metrics/phase_cost，力与力矩均按原left quadrature闭合。force RMS为原5ms采样TASK序列的均方根，单列为描述统计。

## 补偿与因果限制
终末误差、allocator、position/velocity torque、force和moment存在共同时间响应；这些分量是同一闭环中的后处理变量。norm大小不能当可相加的力矩贡献，相关峰先后也不能证明唯一中介。R0与W1之间只解释整个背景规则的条件效应，不把模型重力/弹性项代数分解叫作独立物理因果贡献。

## 决策
本轮没有找到一个同时具有明确可控机制和显著预计收益的独立力矩干预，因此完成配对审计，不重定义comfort阈值或改plant/allocator gain。下一轮可沿髋终末时序受控实验检查force/moment/跟踪是否共同改变；完整原门仍先于力排名。

![force_motion_moment_tradeoff.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/force_motion_moment_tradeoff.png)

![force_and_cumulative_cost.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/force_and_cumulative_cost.png)
