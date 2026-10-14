# Velocity Smoothness Diagnostic

本诊断复用本页 Baseline B 与 18D development best 的完整保存记录；新增物理运行 **0 次**。图见 `assets/velocity_smoothness_diagnostic.png`，精确事件、receipt ID、原始指标与来源哈希见 `evidence/VELOCITY_DIAGNOSTIC_DATA.json`。

## 速度变化集中在哪些时段？

去程、回程的分段加速/减速都可见速度起伏；HOLD（TASK 9.005–10.025 s）接近静止。对当前18D方案，最大膝速度偏差出现在去程终末制动 **7.000 s（9.542°/s）**，最大髋速度偏差出现在回程终末制动 **16.900 s（4.963°/s）**。Baseline 的对应最大偏差分别在7.430 s、17.055 s。这里“偏差”是同一5 ms时刻的true减reference，不把正常方向切换或设计加减速直接叫控制抖动。

## 更像参考变化，还是执行/接触响应？

两者都有，但应分两个尺度解释。较宽的速度波峰/波谷同时出现在参考与真实运动中：当前18D去程 hip/knee 相关系数0.994/0.983，回程0.990/0.991，支持主要运动形状与分段reference相关。相关系数不分解因果贡献。

终末制动时仍有明显true-reference偏差；18D膝最大偏差发生在最近suffix生效后 **230 ms**，髋最大偏差在suffix生效后 **360 ms**。这支持存在执行链、接触及闭环跟踪的动态响应，而不只是reference瞬时跳变。未做消融，不能把具体比例归因给cuff、动力学估计、低层控制或其他单一模块。

## 与handoff/scheduler切换有什么关系？

每组有14个已ACTIVATED计划、10个实际suffix splice。复合计划activation与suffix实际生效相隔约 **45 ms**，图中分别标注；request单独放在事件条。现存每组14份边界记录的q/dq jump为0，ddq最大绝对残差仅3.285×10⁻¹⁵ rad/s²（浮点舍入量级），满足原C2接续检查；这不要求速度在整段内恒定，也不保证实际Human同样平滑。

全程raw jerk峰值与5 ms命令receipt邻近：当前18D hip在3.0255 s、knee在5.6055 s，均在最近receipt后 **0.50 ms**，同时在最近新计划activation前 **9.50 ms**、suffix生效前 **54.50 ms**。因此不能把这些峰值解释为该新suffix生效时的瞬时抖动。每5 ms都有receipt，单次邻近不是因果证明；局部放大图只显示采样/命令时间结构与raw导数尖峰的关系。

## 能否说这是必须接受的结构代价？

**证据不足。更合适的表述是：部分跟踪指标改善，速度平滑性仍待优化。** 18D回程hip/knee速度误差RMS从Baseline的1.483/1.464降到1.234/1.270°/s；但去程hip RMS从0.943升至0.969°/s，膝最大偏差从9.166升至9.542°/s，hip raw jerk峰值从5548升至6697°/s³。不能称为全面改善或已解决。现有一对开发轨迹没有证明不可避免性、临床可接受性或其他结构无法更平顺。

## 当前18D最小时间关系表

所有时间均为TASK elapsed simulation time，Δt=峰值时刻−最近事件时刻；负数表示峰值在事件之前。“最近receipt”是实际command receipt，不是新计划事件。

| 指标 | 峰值 | TASK时刻 / s | 最近activation / Δt | 最近suffix / Δt | 最近receipt / Δt |
|---|---:|---:|---|---|---|
| 最大 \|true − ref\| · hip | 4.963 °/s | 16.9000 | 16.4950s / +405.00ms | 16.5400s / +360.00ms | 16.9000s / +0.00ms |
| 最大 \|true − ref\| · knee | 9.542 °/s | 7.0000 | 6.7250s / +275.00ms | 6.7700s / +230.00ms | 7.0000s / +0.00ms |
| 最大 \|raw acceleration\| · hip | 77.564 °/s² | 16.9475 | 16.4950s / +452.50ms | 16.5400s / +407.50ms | 16.9450s / +2.50ms |
| 最大 \|raw acceleration\| · knee | 116.297 °/s² | 7.0275 | 6.7250s / +302.50ms | 6.7700s / +257.50ms | 7.0250s / +2.50ms |
| 最大 \|raw jerk\| · hip | 6696.553 °/s³ | 3.0255 | 3.0350s / -9.50ms | 3.0800s / -54.50ms | 3.0250s / +0.50ms |
| 最大 \|raw jerk\| · knee | 17578.684 °/s³ | 5.6055 | 5.6150s / -9.50ms | 5.6600s / -54.50ms | 5.6050s / +0.50ms |

## 数据与微分口径

- 每组真实q/dq完整覆盖19.03 s，76,121个native样本，步长0.25 ms；参考与共同时间的速度偏差使用3,807个5 ms trace样本，native true dq与同时间trace逐点吻合。
- 加速度从raw true dq用 `np.gradient(..., time_s, axis=0, edge_order=2)` 得到，jerk再用同一微分求得；两组数组与历史存档精确一致。它们是**数值导数暴露指标**，不是直接测得的加速度/jerk，不单凭尖峰大小宣称真实控制抖动或临床问题。端点使用单侧差分；表中峰值均不在端点差分区。
- 没有滤波、平滑或新插值。参考以5 ms采样的ZOH阶梯展示，不能据此把每个采样台阶说成连续quintic不光滑；raw真速度使用全部native点绘图。
- 记录边界的C2成立，不等于整个物理/执行链处处满足C2。图表只做解释性对齐，不修改原冻结motion规则；不重算/改选方案。科学仿真的simulation time与wall-clock source age严格分开，不用继承父运行的monotonic时钟冒充物理时间。
- 每组图中可读取的3,805条receipt来自原执行记录中因果命令baseline的contributions（含实际receipt index/time）；不是根据5 ms时钟人工生成，也不宣称完整导出了每个末端command。距离表使用这批可核验的实际receipt。
