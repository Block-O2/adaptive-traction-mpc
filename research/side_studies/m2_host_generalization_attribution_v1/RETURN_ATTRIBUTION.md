# RETURN 收益归因

状态：PASS。完整 TASK trace 按实际 OUTBOUND/HOLD/RETURN 转换边界分区，以原 left-endpoint quadrature 计算。保留 phase-clock 与 integrated-trace durations；无 HOLD 裁剪。

| Pair | ΔJ_F N·s | ΔRETURN N·s | 时长贡献 N·s | 平均力贡献 N·s | RETURN 非零计划 / OUTBOUND 非零计划 |
|---|---:|---:|---:|---:|---:|
| deviation_P1_seed1 | -81.566332 | -87.654100 | -0.266631 | -81.299702 | 3 / 1 |
| deviation_P1_seed2 | -130.050643 | -77.737676 | 0.129229 | -130.179872 | 3 / 4 |
| deviation_P2_seed1 | -91.435895 | -92.857196 | -0.170197 | -91.265697 | 3 / 0 |
| deviation_P2_seed2 | -96.952976 | -84.068114 | 0.155926 | -97.108902 | 3 / 2 |

合并 ΔJ_F=-400.005846126 N·s；时长项 -0.151673419，平均力项 -399.854172707 N·s。RETURN 占合并差值比例 0.8557802086053091，平均力项占 0.9996208219939315。各阶段满足 ΔJ=(T_M−T_B)(F̄_M+F̄_B)/2+(F̄_M−F̄_B)(T_M+T_B)/2，阶段积分闭合误差均 <1e−8 N·s。各阶段分解、完整时钟、真实 hip/knee/reference/force/moment/clearance 边界状态与真实 commissioning fit 差值在 PAIRED_HOST_RESULTS.json。

Q decision source time、raw ranking、所选 K3 与 native Δd、admission/lifecycle、真实 receipt 与 native steps、开始/结束物理状态在 EXECUTION_LINEAGE.json 逐请求对齐。OUTBOUND 与 RETURN 各自执行数和 native steps 明确区分。当前接口不对 HOLD 发 Q 选择。旧4对结果独立存储，不能扩充本轮 n。

机制判断：线性 Q 对固定 masked plan 的偏好不具有状态交互；重复 residual 与 RETURN 效应更符合固定 residual 偏好经过 native feasibility、mask 与 carry 筛选的解释。进入 RETURN 的真实状态差值已测量；OUTBOUND 残余、commissioning fit 与 host timing 的贡献没有被独立随机化，不能将阶段分解或平均力下降宣称为严格因果识别。B/M2 配对保留同一合法 prefix；比较的是公共扰动后 residual coordination 的附加价值。

逐实际 receipt window 与 B 同阶段相对时间窗口的描述性对照：

| phase | 非零 window数 | 较低 J_F window数 | window ΔJ_F合计 N·s |
|---|---:|---:|---:|
| OUTBOUND | 7 | 6 | -59.193991 |
| RETURN | 12 | 12 | -148.354342 |

这些窗口不覆盖完整任务，且起点状态、commissioning 和先前残余不同；window 差值不能解释为独立处理效应。全阶段收益仍以对称乘积分解为准。实际 native Δd 的分布及按所选 source 的重复频率在 reports/RETURN_EXECUTION_WINDOWS.json，允许固定计划在不同 native 状态下实现不同 Δd，不能将此误称为 Q 的条件化排序。共同 prefix 的所有 activated native metadata 独立保留；Q-only 非零执行分母不包括公共 prefix。receipt 非重复核验 PASS。
