# 合法动作合同 v1

正式 B、18D、H150 参数和原执行器只读。本包扩展的是隔离参考意图，不是安全控制器。每个提案均经过原 `_evaluate`、固定 duration quintic certificate、当前状态 admission、activation/splice 与 receipt/native 所有权校验。

| 家族 | 本轮状态 | 限制与理由 |
|---|---|---|
| A0 固定 B | 执行基线 | 原 W1 prefix；无学习修改 |
| A1 hip 小姿态 | 暂不开放 | 限制维度，先独立检验 knee |
| A2 knee 小姿态 | 本轮主要方向 | OUTBOUND slot 1 或 RETURN slot 3；零基 slot；±0.3°；保持 hip 目标、原段时长与 pass velocity |
| A3 segment duration | 审计通过但不搜索 | 旧接口 5 ms 量化，适用前提需原证书；本轮不混入姿态因果对比 |
| A4 internal velocity | 暂不开放 | 旧 18D 已有受限接口，但不重新开放 18D |
| A5 H150 | 冻结完整对照 | 不修改 T/D/ER/H150；包括其终末 knee-constant 前提，失败保留 |

`HistoryPosturePlanner` 继承原 NativeResidualPlannerV2，仅在原 B 已选中中间 waypoint 后增加 knee 位移。为零或无 intent 时直接返回原决定；端点不支持时记录 REJECTED。原固定时长证书拒绝时返回原合法动作，不改门、不绕过检查。相对于原 B 每次只有一个局部位置偏移。

可证伪假设：第一次运动的中段高力与 knee lag 可识别一个值得尝试的局部顺应修正。ILC 将目标向上次估计 actual 靠近，增益 0.25、幅度 ±0.3°，以减小人机位移负担。方向只是一项先验假设；耦合动力学、后续时序与 tracking 可能使完整 J_F 反而升高。开发试验同时包含相反方向，不能把首次高力窗口直接解释成已识别的最优梯度。

每动作保存 phase、slot、deg/rad、幅度、原父 waypoint、参数界、原/新目标、原 duration/velocity、action hash、history hash、证书结果、实际 activation 与 native steps。真实 applied command 为最终 receipt 的六轴 torque，仅作观测，学习器不输出 torque。
