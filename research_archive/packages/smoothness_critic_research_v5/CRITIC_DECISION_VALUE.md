# Critic是否具有决策价值

| 模型 | test父 | H | short | critic | actual tail | critic vs short ΔJF | 训练固定动作 | critic vs fixed ΔJF | tail RMSE | 合格集合排序r（事后） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COSTO8 | TAILOT | 0.5 | TAILOT_SPEEDP FAIL | TAILOT_SPEEDP FAIL | TAILOT_RELATIVEP | 主选择FAIL | TAILOT_RELATIVEP PASS | 主选择FAIL | 2.107992 | 0.964 |
| COSTO | TAILOT | 0.5 | TAILOT_SPEEDP FAIL | TAILOT_SPEEDP FAIL | TAILOT_RELATIVEP | 主选择FAIL | TAILOT_RELATIVEP PASS | 主选择FAIL | 1.883798 | 0.964 |
| COSTR8 | TAILRT | 0.5 | TAILRT_SPEEDM PASS | TAILRT_RELATIVEM PASS | TAILRT_RELATIVEM | 1.555516 | TAILRT_RELATIVEM PASS | 0.000000 | 0.115201 | 1.000 |
| COSTR | TAILRT | 0.5 | TAILRT_SPEEDM PASS | TAILRT_RELATIVEM PASS | TAILRT_RELATIVEM | 1.555516 | TAILRT_RELATIVEM PASS | 0.000000 | 0.090384 | 1.000 |


主选择使用实测短期费用+冻结Critic，不使用未来资格mask；只有完整观察所有offered候选时才可评价无mask结果。原合格集合内的条件排名另列并明确是事后资格诊断。预测更准但不改变选择，不认定决策价值；改变但真实更差保留负结果。固定训练动作在新test前冻结，用于检验是否更简单的动作库即可解决。所有菜单为独立真实物理全续跑，实际节省尝试NOT_ESTABLISHED/0。本轮C_short与z_H也来自真实分支执行，尚无廉价短期候选状态/成本预测器；Critic尾部排序检验不能直接称实时控制器。


CONFIRMED：COSTO主模型在TAILOT未改变无mask选择SPEEDP，原motion FAIL；事后合格集合内的排名/收益不能替代此主结果。原加速度峰值门已在H前失败：guard事件发生于决策后0.18秒，H为0.5秒；尾部force成本无法抹去已发生极值。predicted worst_ratio约0.956，actual约1.986。训练只有合格样本，且未显式记录累计运动极值/guard历史。

输入域也变化：train剩余时间恒15.490秒，test为15.505秒；重复的phase/task elapsed字段在训练中为常数，以0.001缩放，15ms偏移带来主要核距离，最近训练RMS距离约2.5。raw tail误差RMSE约1.884 N·s，去菜单共同误差后仍约1.301 N·s，明显大于约0.04 N·s的关键选择差。ensemble分歧约0.07 N·s未校准。SUPPORTED：状态覆盖、核外推与缺失历史风险共同限制此版本；完整模型修复的盲验证未做，查询敏感性另列，不能把全部误差唯一归因某一字段。只修共同状态费用偏差会在排序中相消，不能当新的决策价值。原模型、选择和test均保持冻结。详见analysis/CRITIC_COSTO_HELDOUT_DIAGNOSIS.json。


已暴露test的查询敏感性诊断：训练常量clock字段置训练均值后，主出程最近训练距离约2.527→1.372，tail RMSE约1.884→1.547、去共同误差RMSE约1.301→0.965，但主选择仍SPEEDP且motion FAIL；处理所有训练近恒定字段也未改变选择。确认时钟影响算法距离，但不足以修复决策；未重训或改主模型/原test。完整风险状态修复和新盲验证仍NOT_TESTED，见[查询敏感性](CRITIC_FEATURE_SENSITIVITY.md)。


最终冻结验证、失败分母与补充反事实见[冻结验证汇总](FROZEN_VALIDATION_SUMMARY.md)、[补充执行反事实](SUPPLEMENTARY_EXECUTION_COUNTERFACTUALS.md)和[力／力矩波动分解](WRENCH_COMPONENT_TRADEOFF.md)。主结果不使用未来资格mask，不改变原积分、原阈值或开发固定预算。
