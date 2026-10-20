# H150冻结研究基线

H150仍可用于指定条件下的PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION研究对照。它不是所有状态的实际Human motion保证。全部参数、18D来源、T/ER/RETURN5 hip timing与原5ms量化保持冻结；动作定义见ACTION_SET.json、FROZEN_18D.json、FROZEN_SELECTION.json及执行manifest v2/v3/v4及序列化修复v5/v6。

W1/W2在本轮均为已暴露开发条件，不能再次称未见验证。D01R的B/H150与历史Ctrl全trace、native状态和科学receipt复现见audit/H150_REPRODUCTION.json；D02与历史W2相同范围的逐raw复现见audit/W2_FULL_RAW_REPRODUCTION.json。其余prefix、seed、split在任何相应物理结果之前登记于*_PLAN.json。一个Human模型不等于多个独立受试者。

| 状态 | split | J_F / N·s | 对B降力% | 膝下冲° | 膝excursion−B° | 门余量° | 完整资格 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D01R | train | 1402.643211 | 2.3539 | 1.201029 | 0.474247 | 0.025753 | PASS |
| D02 | train | 1397.727675 | 2.3371 | 1.209812 | 0.115465 | 0.169036 | PASS |
| D03 | train | 1407.619115 | 2.4280 | 1.200755 | 0.503992 | -0.003992 | FAIL: excursion |
| D04 | train | 1400.997173 | 2.3762 | 1.212162 | 0.040321 | 0.245800 | PASS |
| D05 | train | 1400.560740 | 2.3528 | 1.207232 | 0.225299 | 0.202215 | PASS |
| D06 | train | 1403.249981 | 2.4241 | 1.212179 | 0.024403 | 0.135688 | PASS |
| V01 | validation | 1407.432342 | 2.4009 | 1.198528 | 0.603349 | -0.103349 | FAIL: excursion |
| V02 | validation | 1399.234251 | 2.7312 | 1.214568 | 1.063103 | -0.563103 | FAIL: excursion |
| U01 | test | 1402.539930 | 2.3769 | 1.200753 | 0.484103 | 0.015897 | PASS |
| U02 | test | 1401.751387 | 2.3935 | 1.212164 | 0.039925 | 0.210669 | PASS |
| U03 | test | 1403.708688 | 2.3878 | 1.205801 | 0.297959 | 0.202041 | PASS |

RETURN膝下冲定义为max(0,9.5°−RETURN真实最小膝角)：9.5°是实际最终发出参考，不是名义10°。excursion为完整任务真实max−min；原门为两个关节相对matched B的绝对差均≤0.5°。门余量为0.5−max(abs(两关节excursion差))。负余量就是FAIL，即使只差几千分之一度；没有调宽门或追着W1阈值调参。

D03的H150膝下冲1.200755°与W1的1.201029°几乎相同，失败不能简单解释为下冲突然更严重。D03 matched B自身膝excursion为111.269980°，H150为111.773972°，差0.503992°；ZERO只把下冲缩小约0.004265°，留下约0.000273°的门余量。它在该确定性条件下PASS，但余量极窄，不代表稳健修复。完整候选与B极值分解见derived/EXCURSION_EXTREMA_DIAGNOSTIC.json。

| 状态 | moment相对B% | hip tracking RMS° | knee tracking RMS° | force峰值 N | moment峰值 Nm |
| --- | --- | --- | --- | --- | --- |
| D01R | 5.747 | 0.4531 | 0.5229 | 113.782 | 15.516 |
| D02 | 5.427 | 0.4502 | 0.5362 | 113.855 | 15.534 |
| D03 | 5.844 | 0.4575 | 0.5086 | 114.689 | 15.711 |
| D04 | 5.552 | 0.4536 | 0.5283 | 114.713 | 15.723 |
| D05 | 5.572 | 0.4522 | 0.5274 | 114.090 | 15.578 |
| D06 | 5.633 | 0.4557 | 0.5265 | 115.079 | 15.816 |
| V01 | 5.813 | 0.4570 | 0.5084 | 114.406 | 15.642 |
| V02 | 6.164 | 0.4525 | 0.5338 | 114.628 | 15.703 |
| U01 | 5.661 | 0.4530 | 0.5229 | 113.759 | 15.517 |
| U02 | 5.585 | 0.4543 | 0.5275 | 114.837 | 15.754 |
| U03 | 5.667 | 0.4548 | 0.5184 | 114.541 | 15.684 |

低force不是全面更优。moment、tracking、真实过冲与native平顺性仍须单独评估。完整字段（velocity max/p95/RMS、acceleration max/p95/RMS、jerk p95/RMS、TV、acceleration variation、dose、phase）见EXPERIMENT_RESULTS.json。原门见MOTION_ACCEPTANCE_PROTOCOL.json：motion burden 1.1、travel±5%、endpoint/phase boundary 0.5°、duration 0.1s、moment integral 1.25、force/moment peak 1.05及tracking+B0.5°均未改变。

![终末运动与力](figures/07_terminal_response.png)

![资格与成本分开评价](figures/08_qualification_cost.png)

保留原B planner、证书、current-state admission、机器人反馈/allocator和被动Human物理。不重开PD/FF/阻尼增益网格。下一步需要研究资格余量的状态依赖和终末传力响应；无需先把所有过冲消到零才允许Learning。
