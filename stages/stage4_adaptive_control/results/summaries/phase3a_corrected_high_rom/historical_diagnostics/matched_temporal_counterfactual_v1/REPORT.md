# Phase 3A matched temporal semantics 离线反事实

证据类别：**offline causal diagnostic / algebraic single-event counterfactual**。只读取冻结 Rigid evidence，未运行 trajectory、MPC 或 MuJoCo dynamics。reference cuff pose 从 `t=0` 起经过与 measurement 相同的 200 Hz sampling、8 Hz pose low-pass 和 120 ms causal quadratic differentiation。

## 方法边界

- CURRENT：`140 * (v_target_raw - v_measured_processed)`。
- MATCHED PROCESSING：`140 * (v_target_processed - v_measured_processed)`。
- INSTANTANEOUS TRUTH：`140 * (v_target_raw - v_robot_truth)`，只作离线诊断。
- reconstructed nominal executable 仅替换 translational velocity-feedback vector；Human allocator、position feedback、orientation/angular feedback和其余项全部保持该事件保存值。
- 结果回答“同一保存状态下是否仍越过 200 N”，不等同于新的 Safety Filter mode 或闭环 trajectory outcome。

## 紧凑比较

`velocity force` 单元为 `norm / projection on saved final executable-force direction`，单位 N。

| case | CURRENT velocity force | MATCHED velocity force | INSTANTANEOUS velocity force | CURRENT executable | MATCHED executable | INSTANTANEOUS executable | MATCHED >200 N |
|---|---:|---:|---:|---:|---:|---:|---|
| 40/80 | 83.14 / +65.72 | 83.13 / +65.74 | 15.01 / +14.76 | 213.38 | 213.40 | 169.43 | YES |
| 120/120 | 135.49 / +116.20 | 135.52 / +116.22 | 94.36 / +86.36 | 237.79 | 237.80 | 210.34 | YES |
| 90/120 | 65.48 / +55.83 | 65.50 / +55.82 | 9.97 / -0.78 | 199.79 | 199.78 | 149.84 | NO |

## 事件向量（WORLD frame，cuff center）

| case | definition | target v (m/s) | measured v (m/s) | error v (m/s) | 140*error (N) |
|---|---|---|---|---|---|
| 40/80 | CURRENT | [+0.032, +0.000, -0.004] | [-0.125, +0.000, -0.577] | [+0.157, -0.000, +0.573] | [+21.93, -0.01, +80.19] |
| 40/80 | MATCHED | [+0.032, +0.000, -0.004] | [-0.125, +0.000, -0.577] | [+0.156, -0.000, +0.573] | [+21.89, -0.01, +80.20] |
| 40/80 | INSTANTANEOUS | [+0.032, +0.000, -0.004] | [+0.054, +0.000, -0.109] | [-0.022, -0.000, +0.105] | [-3.14, -0.03, +14.68] |
| 120/120 | CURRENT | [-0.086, -0.000, +0.033] | [+0.134, -0.001, -0.909] | [-0.220, +0.001, +0.942] | [-30.84, +0.08, +131.93] |
| 120/120 | MATCHED | [-0.086, -0.000, +0.033] | [+0.134, -0.001, -0.909] | [-0.220, +0.001, +0.943] | [-30.82, +0.08, +131.97] |
| 120/120 | INSTANTANEOUS | [-0.086, -0.000, +0.033] | [+0.148, +0.001, -0.599] | [-0.234, -0.001, +0.632] | [-32.80, -0.11, +88.48] |
| 90/120 | CURRENT | [+0.070, +0.000, -0.047] | [+0.141, +0.002, -0.509] | [-0.071, -0.002, +0.462] | [-9.97, -0.26, +64.72] |
| 90/120 | MATCHED | [+0.071, +0.000, -0.047] | [+0.141, +0.002, -0.509] | [-0.071, -0.002, +0.462] | [-9.92, -0.26, +64.74] |
| 90/120 | INSTANTANEOUS | [+0.070, +0.000, -0.047] | [+0.121, +0.000, +0.003] | [-0.051, -0.000, -0.050] | [-7.08, -0.00, -7.02] |

完整 angular twist 与 `12 Nms/rad` diagnostic moment 收录在 `summary.json` 和 CSV；本反事实没有替换 angular feedback moment。

## DIRECTLY DERIVED

- 40/80：matched-processing 后 velocity force 从 83.14 N 变为 83.13 N；reconstructed executable 为 213.40 N，仍高于 200 N。
- 120/120：matched-processing 后 velocity force 从 135.49 N 变为 135.52 N；reconstructed executable 为 237.80 N，仍高于 200 N。
- 90/120：matched-processing 后 velocity force从 65.48 N 变为 65.50 N；reconstructed executable 为 199.78 N，低于 200 N。
- INSTANTANEOUS TRUTH 的 velocity force分别为 15.01、94.36、9.97 N。这是当前时刻真实 robot tracking lag 对冻结 140 Ns/m 映射的代数值。
- 三个事件的 current-force 和 matched nominal vector 闭合误差均低于 1e-9 N；measurement 与 processed target 在事件时刻均是 200 Hz 新样本、0 ms age。

## SUPPORTED BY CURRENT EVIDENCE

- 三个事件中，reference 的 raw 与 processed velocity几乎相同；因此只匹配 target preprocessing 没有抵消 measured robot pose history所产生的差异。
- 40/80 和 120/120 的 matched reconstructed executable仍分别高于 200 N 达 13.40 N 和 37.80 N；同一保存状态下，单独匹配 target preprocessing不足以移除 force-budget crossing。90/120 仍低于目标，但 margin 仅 0.22 N。
- 40/80 的 INSTANTANEOUS executable 为 169.43 N，说明该事件对 measured pose-history derivative高度敏感；120/120 的同一诊断仍为 210.34 N，说明其真实瞬时 tracking lag本身已足以越过 200 N。
- INSTANTANEOUS TRUTH 与 MATCHED 的差异反映了“当前时刻 tracking lag”与“双方历史滤波后的相对运动”是不同诊断量；二者都不是新的 closed-loop evidence。

## UNRESOLVED

- 单事件代数替换不会更新后续 robot state、measurement history、MPC action 或 Safety Filter history，不能宣称原 `FILTER_INFEASIBLE` 会被闭环消除或推迟。
- 本审计没有证明 matched processing 是优于现有语义的 controller design；也没有确定应该处理 target、修改 estimator，或改变 gain。
- 只有 preregistered matched-processing rollout 才能回答 mode transition、tracking、physical force和完整任务结果。

## 建议

**目前不建议把 preregistered matched-processing rollout 作为下一项实验。** 三个事件的 velocity-force norm变化均小于 0.04 N，两个 boundary crossing均未改变，90/120 也保持在目标下方。现有 evidence 已表明“只处理 target”不是有力的 rescue mechanism。若后续为了实现验证仍要运行，应把它定义为单变量语义确认，而非预期改善任务的实验；更有信息量的下一步应继续调查 measured pose-history derivative与 instantaneous robot motion之间的差异，之后再决定是否需要预注册 measurement-path 或 gain sensitivity study。
