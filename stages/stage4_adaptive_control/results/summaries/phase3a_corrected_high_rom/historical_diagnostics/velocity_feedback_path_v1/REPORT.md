# Phase 3A robot Cartesian velocity-feedback path 离线审计

证据类别：**offline deterministic reconstruction**。读取冻结 Rigid mechanics/controller evidence，重放已注册 measurement preprocessing，并进行纯运动学检查。新 trajectory runs：**0**；scientific settings changed：**false**。

## Target / measured twist contract

| 项 | Target twist | Measured twist |
|---|---|---|
| 来源 | Unified Reference Manager 在当前 5 ms low-level boundary 返回 `q_ref,dq_ref`；冻结 `PlanarCuffGeometry.cuff_velocity(q_ref,dq_ref)` | MuJoCo `adapter_cuff_site` pose；200 Hz `CausalMeasurementLayer` 对 pose 做 8 Hz low-pass，再用最近 120 ms 的因果二次最小二乘求导 |
| 与 MPC 的关系 | 不是 MPC first action；MPC first action只进入 Human torque/cuff allocator wrench | 不由 MPC 或 Human state生成 |
| Frame | WORLD | WORLD（`mj_objectVelocity(..., flg_local=0)` 的原始 pose/twist；处理后仍为 WORLD） |
| Reference point | Human model 的 cuff/sleeve center | robot `adapter_cuff_site`，与 rigid Human `sleeve_attach_site` weld 在同一 cuff center |
| 更新与保持 | Reference Manager 连续 clock 在每个 5 ms command boundary 求值；command 在随后 5 ms ZOH | 200 Hz capture，0 ms configured latency；事件均为 new sample、age=0；导数仍含 120 ms 历史 |
| 140 mm adapter | target/measurement 已在 cuff center，无需再做 point transport | site 本身位于 cuff center；140 mm lever arm 只在 cuff wrench→robot joint torque Jacobian 中显式 transport |

## Event reconstruction（WORLD frame）

| case | t | status | v_target (m/s) | v_measured (m/s) | v_error (m/s) | 140*v_error (N) | norm | projection on final F |
|---|---:|---|---|---|---|---|---:|---:|
| 40/80 | 11.935 | FILTER_INFEASIBLE | [+0.0321, +0.0000, -0.0040] | [-0.1246, +0.0001, -0.5768] | [+0.1566, -0.0001, +0.5728] | [+21.93, -0.01, +80.19] | 83.14 | +65.72 |
| 120/120 | 10.410 | FILTER_INFEASIBLE | [-0.0862, -0.0000, +0.0329] | [+0.1341, -0.0006, -0.9094] | [-0.2203, +0.0005, +0.9424] | [-30.84, +0.08, +131.93] | 135.49 | +116.20 |
| 90/120 | 22.185 | SAFE_UNCHANGED | [+0.0702, +0.0000, -0.0468] | [+0.1414, +0.0018, -0.5090] | [-0.0712, -0.0018, +0.4623] | [-9.97, -0.26, +64.72] | 65.48 | +55.83 |

角速度路径同样使用 WORLD frame，冻结系数为 12 Nms/rad：

- 40/80：omega target/measured = [-0.0000, -0.0659, -0.0000] / [-0.0219, +1.2665, -0.0235] rad/s；angular-velocity moment = [+0.26, -15.99, +0.28] Nm。
- 120/120：omega target/measured = [-0.0000, -0.0091, -0.0000] / [+0.0147, +2.3493, -0.0198] rad/s；angular-velocity moment = [-0.18, -28.30, +0.24] Nm。
- 90/120：omega target/measured = [-0.0000, -0.0631, -0.0000] / [+0.0191, +0.7145, -0.0182] rad/s；angular-velocity moment = [-0.23, -9.33, +0.22] Nm。

## Velocity-error source split

使用向量恒等式：`v_target-v_measured = (v_target-v_true) + (v_true-v_clean_processed) + (v_clean_processed-v_measured)`。第二项是 8 Hz/120 ms preprocessing history，第三项仅是 pose noise 对导数的增量。

| case | instantaneous physical tracking force norm / projection | preprocessing-history norm / projection | pose-noise norm / projection | total norm / projection |
|---|---:|---:|---:|---:|
| 40/80 | 15.01 / +14.76 | 71.04 / +51.37 | 0.96 / -0.41 | 83.14 / +65.72 |
| 120/120 | 94.36 / +86.36 | 43.61 / +30.11 | 0.31 / -0.27 | 135.49 / +116.20 |
| 90/120 | 9.97 / -0.78 | 71.47 / +56.74 | 0.74 / -0.13 | 65.48 / +55.83 |

这些是向量分解，不是可相加的标量百分比。

## Gain provenance

- `140 Ns/m` 最初出现在 commit `9d082c3973f07a9544fedb562eb022051546bf89`（2026-08-23，`validate MuJoCo sleeve robot plant V2`），作为 coupled robot-sleeve-Human MuJoCo plant 的注册 Cartesian PD engineering assumption；同一文档明确说明参数在结果后没有调节，且不是硬件接口参数。
- commit `1a2b040801a75c14650ed08bc3ce74cb705d4aaf` 将该公式作为 Stage-2 的 direct semantic port 带入 UR10e rigid-cuff Stage 3。
- commit `185f1739f9771d1d3a9cb1fd02e2e1fd0711fbbc` 把既有公式提取成 single executable-command contract，并保留 legacy equivalence；后续 140 mm adapter、High-ROM 与 Safety Filter 继续复用该值。
- 仓库中未找到 critical-damping derivation、频响设计依据，或针对当前 140 mm High-ROM + 200 N interaction contract 的独立 gain qualification。因此它是**从早期 coupled simulation controller 继承并保留的 engineering gain**，并非只针对 robot-only tracking，也没有证据表明专为当前 High-ROM interaction 选择。

## DIRECTLY VERIFIED

- 三个事件都满足 `F_velocity = 140*(v_target-v_measured)`，最大分量闭合误差低于 1.000e-15 N；没有单位或公式符号错误。
- target 与 measured twist 都在 WORLD、都指向 cuff center。Rigid robot cuff site 与 Human sleeve site 的事件线速度差 norm 分别为 0.0011、0.0029、0.0012 m/s。
- 140 mm offset Jacobian 的事件级 finite-difference error 最大为 1.621e-09 m/s；lever-arm term 存在且符号正确。它只用于 wrench-to-joint mapping，不应再加到已经位于 cuff center 的 target/measured velocity。
- 三个事件 measurement age 都是 0 ms 且 `new_sample=true`；没有 packet-level stale sample 或额外 ZOH delay。最近 high-level MPC solve 的 age 为 15.0/10.0/5.0 ms，但 target twist 并不来自该 action。

## SUPPORTED BY CURRENT EVIDENCE

- 40/80 的 83.14 N velocity term 中，instantaneous target-versus-true tracking component 仅 15.01 N，而 preprocessing/history component 为 71.04 N。该事件的大部分 term 不是当前瞬时 robot lag，而是因果 pose derivative 对此前运动历史的响应。
- 120/120 同时存在真实 tracking lag与 preprocessing history：两部分向量 norm 分别为 94.36 N 和 43.61 N。这里不能把 135.49 N 全部归为 measurement artifact，也不能全部归为瞬时 plant lag。
- 90/120 非 BRAKE 对照也有 71.47 N preprocessing-history component，说明该机制跨轨迹存在；是否触发 gate 仍取决于 Human allocator、position term和向量方向。
- 40/80 与 120/120 共享相同 velocity-feedback implementation path，但贡献比例不同。已有证据支持 history dependence，并指向 target derivative 与历史滤波 measured derivative 没有匹配动态这一具体语义问题。

## UNRESOLVED

- 120 ms derivative window 是此前 sensor-realism engineering assumption；仓库没有给出它与 140 Ns/m gain 的联合相位裕度或 interaction-force qualification。
- 本审计不能仅凭三个事件判定应采用何种 cutoff/window/gain，也不能证明去掉 preprocessing history 后 trajectory 一定完成。
- MuJoCo post-step cached site twist 与由同一保存 q/dq 重新 forward 后的 Jacobian twist存在小量 staging difference；它远小于事件中的 preprocessing-history error，但要完全闭合到 physics substep 仍需专门的 logging-contract audit。

## Recommendation

选择 **c) investigate a specific implementation issue first**：保持 140 Ns/m 不变，先审计并预注册 `target twist ↔ measured twist preprocessing` 的匹配语义，特别是 8 Hz pose low-pass + 120 ms causal polynomial derivative 与未作同等动态处理的当前 Reference Manager derivative之间的相位/history差。完成该检查前，不应把 83–135 N 全部解释为真实 robot tracking lag，也不应直接开始 gain sensitivity。
