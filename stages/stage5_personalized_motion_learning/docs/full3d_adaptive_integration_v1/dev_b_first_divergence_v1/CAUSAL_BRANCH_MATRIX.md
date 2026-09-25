# DEV-B 因果分支矩阵

所有分支都是已消耗案例上的 NONDEPLOYABLE / DIAGNOSTIC；没有正式资格推广。
`capture_v3/` 保存最终检查点。四个案例分别是最大突变
`balanced_near_upper_current_rom_r01`、恢复成功但任务失败
`balanced_ordinary_r01`、任务完整成功 `balanced_middle_r01` 和原 nominal。

## 同一时间点的代数干预

机器人测量、interface inversion 缓存、q/dq reference、robot cuff pose/twist、
机器人 Jacobian、bias、reference history、supervisor 状态固定。
O/N 表示旧 prior / commissioning 后候选。动力学指 beta+state residual；
本实现的 inverse dynamics 不直接使用 effective geometry。

| 记录名 | 动力学 | 状态估计 | allocation geometry | 目的 |
|---|---|---|---|---|
| old_model_old_estimate | O | O | O | 同时刻旧控制基准 |
| new_model_old_estimate_old_allocation | N | O | O | 仅动力学作用 |
| old_model_new_estimate_old_allocation | O | N | O | 状态作用，包括分配在新 q 上求值 |
| new_model_new_estimate_old_allocation | N | N | O | 2×2 交互项 |
| new_model_new_estimate | N | N | N | production 首次命令 |
| old_model_new_estimate | O | N | N | 在新状态/几何下保留旧动力学 |
| new_model_old_estimate | N | O | N | 新动力学与旧估计的交叉对照 |
| old/new_model_true_state | O/N | evaluation-only true q/dq | O/N | 非部署状态误差检查 |
| new_beta_zero_residual | N beta，残差零 | N | N | 拆分 beta 与残差贡献 |
| old_beta_new_residual | O beta，N residual | N | N | 验证动态分量拆分 |

数值向量分解：令 f00、f10、f01、f11 固定旧 allocation geometry，
动力学项=f10−f00，状态项=f01−f00，交互=f11−f10−f01+f00；
几何项=f11_new_geometry−f11。四项向量之和等于完整变化。
表中的范数不能直接相加；投影百分比只表示沿总变化方向的贡献。
force N、moment Nm、Human torque Nm、robot torque Nm 分别计算，
不对混合单位的六维 wrench 范数作物理解释。

另外固定 q 与 Human generalized action，只替换 allocation geometry；
单独替换 COMMISSIONING/ACTIVE_RECOVERY context，检验零 twist 起点的影响。

## 真正物理分支

| 分支 | 动力学 | 估计/分配几何 | 物理执行/参考 |
|---|---|---|---|
| retained_model | O | O | 同一候选模型已经认证的 reference/pose bridge |
| activated_model | N | N | production 同步延迟回放后的首段执行 |
| activated_duplicate | N | N | 独立克隆重复，检查确定性 |
| new_model_old_estimate | N | O | 混合干预，同时保留旧估计/分配 |
| old_model_new_estimate | O | N | 混合干预，保留旧动力学 |
| diagnostic_action_transfer_100ms | N + 初始作用量 offset 衰减 | N | 同一参考、原有分配/filter/supervisor |

每例 6×200 ms；最大案例另外执行 4 个 1.5 s 首段分支。所有命令经 CR12
actuator、compliant cuff、Human 和床接触物理 stepping；没有 Human 状态赋值。
每 5 ms 命令包含 20 个 0.25 ms 物理区间，N 区间记录 N+1 边界。
retained_model 的 1.5 s 分支实际在 0.810 s 因 SESSION_CLEARANCE_LIMIT
停止；它的终点不能与其他分支的 1.5 s 终点直接作等时比较。

检查点位于生产首个新模型命令之前、当次新估计和 guard 之后。旧估计分支
共享这个已经激活后的 acceleration-monitor 历史；第一个间隔不重新声称
旧估计的加速度 authority 有效。这些是受控反事实，不是未经改变的旧生命周期。
当次 q/dq、clearance 检查仍执行，后续执行原阈值的监测/filter/supervisor。
activated/duplicate/transfer 三支的状态、geometry 和监测历史一致，因此
最重要的 transfer vs production 对比不受旧估计监测历史问题影响。

## 完整恢复后果

`full_recovery_v3/` 仅对最大案例重建完全相同的 activation checkpoint，
然后运行原 DEV-A 恢复逻辑：production 与最初 100 ms action-offset 两支。
两支都在任务入口之前停止。待执行参考和后续反馈/重规划可由各自真实状态
驱动；没有脚本化 Human 运动。所有历史恢复规划都是一个 5 ms 等待区间，
这里控制等待区间相同，同时单独记录实际 compute，超过 100 ms 就阻断诊断。
这是固定历史延迟的因果实验，不是新的 measured-latency 资格证据。

检查点匹配包括 integration state、qacc warmstart、measurement+RNG、observer
cache、reference history、monitor、authority 和 supervisor 的全部作用状态。
supervisor 两项 wall-time metadata (`computation_ms` 和
`last_safety_filter/computation_ms`) 逐项保存，但不作为作用状态相等条件。
第一次/第二次严格字节与完整值比较因这些 wall-time 字段失败；输出保留在
`full_recovery_v1/` 和 `full_recovery_v2/`，未执行新物理分支，也未算成科学失败。
