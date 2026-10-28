# 离线研究图说明

本目录是已有指标的可重建快照，标签：**final-frozen**。没有运行环境、模型rollout、训练或新物理；未重算积分、导数、滤波或裁剪信号。开发图不等于最终报告或独立验证。

1. 名义S1图合并指定三组同实际native父/同prefork轨迹。灰x为完整但原资格失败，只作成本诊断，不入前沿；空心菱形为原资格通过但额外quality失败，B与BLEND保留。蓝色前沿只使用原资格和额外quality均通过的观测点；不构造加权分数，不把连线解释成已测试连续解。GP和quadratic是同一proposal/物理点；TRAD combo单独标记。所有attempt均保留CSV，只有完整action JSON、父状态、资格、精确成本和physical trace一致才合并绘图别名，不按成本近似合并。局部zoom的微小差异不代表统计显著、误差界或独立学习增量。

2. Heavy图只画B/LATE_H150/EARLY_H150三个原资格通过方案的既有native raw jerk及wrench norm-rate RMS。JF与JM分列，不能概括为所有指标改善。两个NO_T5完整失败的动作、成本和失败原因保留CSV，未作低成本成功排名。

3. Past burden直接读取封存的三Human B摘要。左图是support-safe fork前sum-of-squares份额，cross-fork与future在CSV另列；右图仅把已有同N条件RMS floor除以已有full RMS以显示比例。原floor数值、不同物理单位、native N和cutoff完整保留CSV。下界仅在相同N、past保持不变及原导数support划分下成立；不是可达到的控制最优、安全/舒适证明，也不能证明guard导致峰值。

可选资格矩阵只读取调用者明确列出的组，缺失结果为NOT RUN，partial/原资格失败分别标记。额外/冻结测试组默认拒绝读取；必须主Agent最终显式列出组并使用allow开关。此builder不自动打开PFXV或short_segments。

source/input SHA和PID身份在绘图库导入前记录于PRECOMPUTE_MANIFEST；输入变化会使封包失败。实际读取的JSON另存input_snapshot，执行source存source_snapshot.py，便于重建本次开发快照；这不把后续变化中的输入冒称最终数据。CSV的ranking_eligible仅适用于名义组额外quality前沿，其他组留空并明确NOT_APPLICABLE；complete_original_qualification_eligible单独保留所有组的完整原资格。所有文件位于新输出目录，重复目录一律拒绝。

本次exact groups：`DEVRT03,DEVRC02,DEVPC02,HUMANLS01,HUMANHS01,H150H01,H150L01,H150N01,HSAPP01,LSREP01,LSTIM01,EARLYH01,EARLYN01,EARLYL01,PFXV01,PFXV02,EARLYABL01,EARLYPH01,HOLDSS03,CFACTORH01,CFACTORL01,LSTF01`。

输入快照限制：
- DEVRT03: paired analysis status ONGOING (snapshot only)
- LSTF01: paired analysis status ONGOING (snapshot only)
