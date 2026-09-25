# DEV-C 开发连续性判据，实施前冻结

冻结时间：2026-09-24；尚未运行任何 DEV-C 输出分支。输入均为 DEV-A 已消耗
development 轨迹与 DEV-B 最大跳变同态检查点。此判据只用于模型激活的
控制输出连续性开发验收，不是硬件安全阈值或新鲜资格门槛。

## 样本与基线

取 `dev_a_recovery_v1/regression_v2` 中 near-upper/ordinary/middle 三例，
以及 `nominal_development_v2`。每例 commissioning 最后 1.5 s 中，排除
terminal boundary，保留相邻、时间差 0.005 s 的 304 对，共 **1216 对**。
用同一物理时间线的实际已施加 Human action、CR12 命令及 `trace.npz`
的 total desired wrench（历史键 `allocated_wrench_world` 实为 total）。
向量先作相邻差再分别求 L2；force N、moment Nm 分开，不对六维混合单位求范数。

| 量 | 四例基线最大相邻差 | DEV-B 同态旧模型在新估计/几何的不可避免重锚差 |
|---|---:|---:|
| Human generalized action | 0.09660809 Nm | 1.10293682 Nm |
| total desired cuff force | 0.52337991 N | 1.64111532 N |
| total desired cuff moment | 0.10378095 Nm | 0.36689500 Nm |
| CR12 actuator torque | 0.34350449 Nm | 1.37154936 Nm |

DEV-B 原直接切换 CR12 同态差 **34.83387191 Nm**，实际相邻差
**34.78044489 Nm**。重锚列只替换状态估计和当前控制几何，仍使用旧动力学；
它没有证明几何/估计永远正确，但可分离本阶段要修的动力学作用量替换。

## 冻结的局部验收

从共同匹配检查点，覆盖首次激活至过渡完成后一个 5 ms 控制区间。
相邻输出变化须分别不超过 **重锚差 + 2×上述普通最大差**，向上舍入：

- Human generalized action ≤ **1.30 Nm / 5 ms**；
- desired total cuff force ≤ **2.69 N / 5 ms**；
- desired total cuff moment ≤ **0.58 Nm / 5 ms**；
- CR12 actuator torque ≤ **2.06 Nm / 5 ms**。

2× 是为正常物理状态变化、估计噪声和参考曲率预留一个普通最大步的
附加量，不是工程力/矩限制的放宽。四个绝对门槛同时记录相对各自基线最大值。
若已有 `TRACK/BRAKE` 切换或外部 safety abort，可独立报告并按原因分类；
不得将违反局部门槛的受控转移说成连续。参考 q/dq/ddq、cuff pose/twist
继续按 DEV-A 原连续性合同核对；不允许以新跳变换掉扭矩跳变。

首次 200 ms 物理窗口的 Human substep qacc 峰值必须低于各自直接切换支
（最大例 9.918176，middle 6.962879 rad/s²）；nominal 近零变化应无
无谓新脉冲。实际 cuff 力、矩、20 ms 注册 acceleration monitor、clearance
及所有 guard 照旧，出现失败应保留，不以降峰值单独判 PASS。

## 预选机制与时间依据

在 Human inverse-dynamics action 层作有限输出混合，随后仍经过原
allocation、filter、supervisor、CR12 torque mapping。旧/新模型在**同一
可部署估计 q/dq 与同一 PD 请求**下求作用量；有效几何仍为已接受的
session 几何。整个过程只改变候选模型作用量被应用的比例，不插值 beta。

采用 zero-slope quintic `alpha(s)=10s³−15s⁴+6s⁵`。最大导数为 1.875/T。
由 DEV-B 最大同态总变化与 5 ms 控制率，若 T=0.25 s，估算模型项峰值
CR12 变化 `34.834×1.875×0.005/0.25≈1.306 Nm`，加普通最大
0.344 后低于 2.06 Nm；force 对应约 `49.666×1.875×0.005/0.25
≈1.862 N`，加普通最大 0.523 后低于 2.69 N。0.25 s 为初始
预选持续时间，约为现有最短 1.5 s recovery 段的 1/6；不是照搬 DEV-B
诊断 100 ms。该估算是局部线性上界启发，不保证受控物理验证通过。

无需大范围扫描。如 0.25 s 在冻结门槛下失败，允许一次有因果说明的
0.35 s 开发候选对照，同时记录 tracking lag、force、接管时间；门槛不改。
若仍不满足，停止并报告局部机制失败/范围问题，不靠继续拖慢混合求 PASS。

## 连续更新和终止语义

活动过渡期间新有效模型被接受时，**锁定本次过渡目标**；新接受的
模型进入 latest-wins 待处理槽，同槽更晚版本可取代较早版本，所有
supersede 均记录。`start_time` 和 `alpha` 不重置，锁定目标在有限终点
精确请求。若该拍被 BRAKE、force filter 修改、torque clipping 或禁止
actuation，则仅记录 `COMPLETE`（数学过渡到期），持续请求锁定目标，
直到一个无改动 TRACK 区间记录 `FULLY_REALIZED`；之后的下一控制拍才
对待处理的最新目标判断是否需要新过渡。不能把 COMPLETE 误称为物理接管。
因此连续 20 ms 更新也不能无限推迟本次已开始过渡的接管。
此处根据独立 Auditor 在任何 DEV-C 输出前指出的 `alpha·Δtarget`
潜在跳变，修正了初稿“活动期直接更换目标”的设计；数值验收门槛、
预选时长及科学限制未变。完成后的新更新，在同一状态与 PD 请求下，若
相对当前有效模型的 action 差 ≤ **0.19321618 Nm**（普通最大 action
步的 2×），直接生效并记录；否则启动新有限过渡。数值完全相同为 no-op。
此阈值只判断是否需要另一次过渡，不改变原 estimator、beta 或 residual。

非有限/形状无效的新模型候选不能成为控制目标；当次执行按已有低层
错误路径中止而不向旧模型瞬时跳回。所有转移开始/目标更新/完成/
拒绝事件与 active fraction 必须可追踪。控制管理器不读取 true Human
状态、真实床接触或其他 evaluation-only 量。
