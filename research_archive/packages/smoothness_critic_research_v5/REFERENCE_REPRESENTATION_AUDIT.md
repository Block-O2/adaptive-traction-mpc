# 已下发参考的表示与交接一致性

CONFIRMED：原5ms参考日志包含独立的q、dq、ddq字段。在相邻q保持而dq非零的交接区间，ddq字段的数值导数并不能代表q样本序列的三阶导数。二者均可描述参考，但不能互相替代。原0.25ms Human motion评价完全不变。

|身份|已下发ddq字段的5ms导数 RMS °/s³ 髋/膝|已下发q样本的三次数值导数 RMS °/s³ 髋/膝|dq字段减q样本导数 RMS °/s 髋/膝|实际native Human jerk RMS °/s³ 髋/膝|
|---|---|---|---|---|
|HANDOFF01_BEST|75.228/62.872|17834.376/25709.761|0.952/1.356|320.151/678.366|
|STRICT01_REF025|75.380/63.105|17892.129/25779.485|0.954/1.358|320.797/680.173|
|HANDOFF01_BOTHLOW|82.032/59.325|16408.327/23762.172|0.877/1.255|299.533/635.530|
|OPT01_PATTERN011|77.369/56.628|16408.679/23762.314|0.877/1.255|297.824/634.251|

q样本在5ms栅格直接用未滤波edge_order=2梯度连续求导；这是离散参考一致性诊断，数值尺度取决于栅格，不能当作重建连续参考的亚毫秒jerk，更不能与native Human jerk数值大小直接比较。JSON逐项保留RMS、峰值与分位数；无原门替换、无尖峰滤除。

SUPPORTED：提前降低通过速度缩小了交接q/dq不一致，以及实际Human jerk与wrench波动。参考字段jerk、离散q序列jerk与Human jerk的变化方向可以不同。因此“局部多项式jerk更低”不是完整issued曲线或真实运动改善的充分条件。

CONFIRMED：25%参考局部优化通过原motion门，但完整issued参考这两个jerk描述量均略升，实际Human jerk也略升。这一方法只改善了所优化的局部解析目标，不能称为已实现完整参考平顺。

HYPOTHESIS：固定完整时长迫使交接减速与段内速度、姿态负荷重新分配，是JF未随局部波动下降的原因之一。分阶段积分证实力/矩取舍，但没有独立识别全部动力学中介。

NOT_TESTED：修改executor/bridge协议以根除q保持与非零dq的形式一致性问题。本轮保持原执行链；没有更换guard，也没有扩大原速度坐标权限。

原始证据：analysis/reference_consistency、analysis/handoffs、analysis/execution与runtime/source/results。生成源码source/v5_reference_consistency.py。
