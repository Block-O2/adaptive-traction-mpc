# Adaptive Human Inheritance + RL-Compatible Online Action Interface v1

**ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_COMPLETE**

Question A: **CURRENT_HUMAN_ADAPTATION_CONFIRMED**，限本次四个继承的 development Human 条件。Question B: acceleration-aware 在线参考接口在测试的 scientific simulation 域通过。Gym smoke 和 CUDA 可用；正式 SAC campaign 尚未资格化。

## Human adaptation：问题 1–5

1. 当前完整链是否更新 effective Human 参数？是。四个 continual task 分别接受 31/30/29/29 次 beta 更新，residual 均改变；参数变化由实际模型消费证据支持。
2. 是否被 planner/mechanics/execution 使用？是。worker 输入 belief 数值哈希、mechanics sequence、实际 command 调用的 beta/residual 哈希与源代码调用链对应。原 TASK 字符串 model tag 为空，明确作为日志缺口保留，不作为证据。
3. continual 是否优于 fixed/commissioning-only？没有统一优势。commissioning-only 与 continual 均 4/4 物理通过；fixed 只有 nominal 通过。light/soft fixed 虽 COMPLETE 但真实 RETURN 不通过，heavy/short 失败。continual 对 light/soft、heavy/stiff 的 J_F 分别比 commissioning-only 高约 2.16%、0.58%；nominal/short 差异很小。这证实有效更新与不同执行，不证明每次在线更新有净性能收益。
4. 实际测试哪些扰动？下表给出继承配置；全部任务起点 5/10°、终点 120/120°，每组三臂的物理 truth 相同。

| fixture | height m | mass kg | stiffness pair | damping pair | length scales | cuff fraction | hip X/Z m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| high_rom_nominal_sync_120_v1 | 1.72 | 75.0 | [10.0, 10.0] | [5.0, 5.0] | [1.0, 1.0] | 0.72 | [0.0, 0.0001] |
| high_rom_matrix_light_soft_sync_v1 | 1.68 | 68.0 | [8.0, 8.0] | [4.0, 4.0] | [1.0, 1.0] | 0.72 | [-0.003, 0.002] |
| high_rom_matrix_heavy_stiff_sync_v1 | 1.75 | 82.0 | [12.0, 12.0] | [6.0, 6.0] | [1.0, 1.0] | 0.72 | [0.003, 0.003] |
| high_rom_matrix_short_segments_sync_v1 | 1.72 | 75.0 | [10.0, 10.0] | [5.0, 5.0] | [0.98, 0.98] | 0.7 | [-0.004, 0.002] |


5. 不支持哪些泛化？任意 Human、全部 120° 变体、独立 held-out population、统计显著收益、长期多重复继承、在线几何辨识以及硬件安全均未被本次数据支持。

| Human | arm | runtime | physical | J_F (N s) | F peak (N) | M peak (Nm) | duration (s) | task beta accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| matrix_heavy_stiff_sync | commissioning_only | COMPLETE | PASS | 1424.23 | 131.12 | 17.69 | 15.910 | 0 |
| matrix_heavy_stiff_sync | continual_adaptive | COMPLETE | PASS | 1432.45 | 131.12 | 17.75 | 15.970 | 29 |
| matrix_heavy_stiff_sync | fixed_population | ABORTED | FAIL | 982.09 | 143.20 | 15.27 | 10.000 | 0 |
| matrix_light_soft_sync | commissioning_only | COMPLETE | PASS | 1020.89 | 100.17 | 13.59 | 15.455 | 0 |
| matrix_light_soft_sync | continual_adaptive | COMPLETE | PASS | 1042.95 | 100.09 | 13.58 | 16.010 | 30 |
| matrix_light_soft_sync | fixed_population | COMPLETE | FAIL | 1000.36 | 89.42 | 16.42 | 16.235 | 0 |
| matrix_short_segments_sync | commissioning_only | COMPLETE | PASS | 1220.52 | 114.65 | 15.14 | 15.510 | 0 |
| matrix_short_segments_sync | continual_adaptive | COMPLETE | PASS | 1220.26 | 114.72 | 15.14 | 15.490 | 29 |
| matrix_short_segments_sync | fixed_population | ABORTED | FAIL | 0.00 | 87.32 | 14.17 | 0.000 | 0 |
| nominal_sync_120 | commissioning_only | COMPLETE | PASS | 1237.49 | 115.48 | 15.71 | 16.000 | 0 |
| nominal_sync_120 | continual_adaptive | COMPLETE | PASS | 1236.98 | 115.48 | 15.71 | 15.995 | 31 |
| nominal_sync_120 | fixed_population | COMPLETE | PASS | 1237.22 | 115.54 | 15.70 | 15.990 | 0 |


| Human continual | beta delta L2 | task updates | residual changes | actual execution models | planner numeric models | torque residual RMS (Nm) |
| --- | --- | --- | --- | --- | --- | --- |
| high_rom_matrix_heavy_stiff_sync_v1 | 1.8942 | 29 | 727 | 727 | 13 | 0.7044, 0.1960 |
| high_rom_matrix_light_soft_sync_v1 | 1.7999 | 30 | 732 | 732 | 13 | 0.5938, 0.1502 |
| high_rom_matrix_short_segments_sync_v1 | 0.8954 | 29 | 739 | 739 | 13 | 0.2509, 0.0588 |
| high_rom_nominal_sync_120_v1 | 0.7104 | 31 | 765 | 765 | 14 | 0.1010, 0.0195 |


## Online interface：问题 6–17

6. 能否接受 moving q/dq/ddq？能。16 个原/扩展 blocker 状态携带真实非零初始 ddq，新分支从当前拥有的完整状态开始。
7. 同目标是否重置加速度？不会，保留原轨迹；所有 16 行相同目标 acceleration jump 为 0。
8. 5/10/20/50 ms 指令多久影响参考？本次四个实际 local-switch 首个命令均在 5 ms 后改变参考；按 1e-7 rad 检测阈值，人体响应差异在 10 ms 后出现。不是目标到达时间或 host 推理延迟。

| command period ms | first changed receipt task s | reference effect ms | physical difference ms | physical pass |
| --- | --- | --- | --- | --- |
| 5 | 0.505 | 5.000 | 10.000 | PASS |
| 10 | 0.505 | 5.000 | 10.000 | PASS |
| 20 | 0.505 | 5.000 | 10.000 | PASS |
| 50 | 0.505 | 5.000 | 10.000 | PASS |


9. 是否仍需旧 waypoint endpoint？不需要。16 行 changed-command 采样均在旧端点前生效。饱和共享前缀可延迟小改动；far switch 物理输入被后续命令取代而未显效，不能把 acceptance 当作逐指令即时响应保证。
10. q/dq/ddq 是否连续？是，显式 1e-10 handoff 比较、原 scientific-mode 边界检查与实际新参考记录通过。
11. 活跃限制是什么？继承 reference v=0.6×task limit、a=0.5×task limit；新增明确 jerk=a/20ms。高 ROM 为 [27,45]°/s、[150,300]°/s²、[7500,15000]°/s³；物理 Human [45,75]°/s/[300,600]°/s²、力 200 N、力矩 60 Nm、robot/ROM/clearance/HOLD/RETURN 判据不变。
12. 能否更丰富 lead/lag？48 个 matched reference streams 中，switch 16/16、reverse-alternating 14/16 出现累计位移 lead 指标符号改变；实际 local-switch 参考和物理响应也改变。OLD 为原 endpoint ownership 的重建 comparator，未对全部 changed streams 新跑 OLD 物理模拟；不能据此断言历史小优化收益源于 RSS。
13. 哪些修改/拒绝？无穷/非法形状拒绝，目标或 OTG 极值越 ROM 拒绝，clearance/mechanics/phase deadline/C2 不合格拒绝。Gym/stream generator 的 ROM 修改显式记录。一个低 ROM 方向切换被完整 continuation 拒绝；近边界或远软目标只有通过完整验证才接受。
14. Safety 看多远？看完整 stationary-target continuation，clearance ≤2 ms cells + Lipschitz intersample bound，原 geometry/body margin/shank prior，原 21-sample adaptive mechanics screen，以及模型改变后的剩余 continuation 再验证。它不是 nonlinear physical invariance 或硬件证书。
15. 晚到/不可行 fallback？保留仍有效的 certified continuation；晚到从下一合法 5 ms 边界激活，不回写已执行 prefix。模型变化使旧路径失效则明确 research abort，不能宣称已资格化硬件 emergency braking。
16. 实际 CR12–cuff–Human 是否有效？9 个最终 online run 全部通过继承的物理与 scientific-mode 评分；另外 2 个 Gym smoke 同样通过。Human 由 robot/cuff 物理作用产生，原 plant/actuation 文件无变化；没有 direct Human torque。
17. 力/力矩/clearance 是否退化？新 constant J_F 从 1236.98 降至 904.73 N s，时长 15.995→11.840 s；但 force peak 增 9.07%，moment peak 增 15.27%。局部切换 force peak 增约 14.7–15.0%。这是材料性峰值退化，虽仍在原限制内。deployable shank clearance 约 6.50–6.52 mm，true 约 11.80 mm，没有观察到显著 minimum-clearance 退化。不同 reference 时序混杂，不能宣称控制算法统一更优。

| path | J_F N s | F peak N | M peak Nm | duration s | deployable clearance mm | robot cuff peak error mm | physical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old nominal continual | 1236.98 | 115.48 | 15.71 | 15.995 | 6.335 | not collected | PASS |
| new constant 50ms | 904.73 | 125.95 | 18.11 | 11.840 | 6.501 | 0.0425 | PASS |
| new local switch 5ms | 931.79 | 132.55 | 18.11 | 12.100 | 6.515 | 0.0425 | PASS |
| new local switch 10ms | 932.50 | 132.65 | 18.11 | 12.105 | 6.515 | 0.0425 | PASS |
| new local switch 20ms | 934.22 | 132.77 | 18.11 | 12.120 | 6.519 | 0.0425 | PASS |
| new local switch 50ms | 937.27 | 132.42 | 18.11 | 12.150 | 6.522 | 0.0425 | PASS |


## RL readiness：问题 18–20

18. Gym action 现在可物理实现吗？本次 20 ms 两个零奖励 API episode 可实现且通过物理检查。47 维 observation 仅因果测量/估计/reference/phase/time/目标，无真实 Human 参数或真实 Human q。COMPLETE/timeout/safety-abort 终止映射还做了 3 个 API-only 检查。
19. CUDA PyTorch 准备好了吗？有限 smoke 通过：2.7.1+cu128，CUDA 12.8，is_available=True，NVIDIA GeForce RTX 4060 Laptop GPU，GPU tensor 运算成功。专用隔离环境与版本记录保留；MuJoCo CPU 不变。
20. 是否可以直接进入严肃单 Human SAC expert campaign？**还不能判定 ready**。需要先冻结科学 reward、normalization、throughput/episode contract、reset stress 和评估 protocol。本轮训练 0 steps，不评价 SAC/PPO/TQC，不自动开始任何训练或硬件实验。

## 证据、修复与 Git

Base branch codex/direct-rl-expert-v1，clean HEAD `41cdddef117caa4b191a52129c4ff83e481fd5a8`，remote reachability 已核实。研究 branch `codex/adaptive-human-online-interface-v1`。新增 research source 3 个文件，运行脚本/报告位于本 campaign 目录；原 physical/config/cost/measurement seed/threshold/endpoints 与历史证据未改。原 100 ms wall-age 输出保留；scientific physics 冻结 host epoch，不能据此报告 hardware realtime PASS。Short-stream changed-command host median 3.173 ms / max 9.884 ms；实际物理 changed-command host median 7.061 ms / max 87.470 ms。完整 run wall time 另记，未单独归因 identical-command recertification。

修复：multiprocessing main guard、Ruckig enum No、首次 activation diagnostic 的未拥有 future 查询、current offset 下错误重验已执行 prefix；全部失败 attempt 保留。环境 0.15.3 cp310 binary 不可用，选固定 0.12.2；shell rate-loop 空参数错误未运行物理，后续脚本修正。评分器首次调用缺少 case path，修复调用包装，评分器自身未改。详细结果与 negative evidence 均在 JSON/raw manifest。单 agent，无独立 Auditor，属于受限 development qualification；不把自查说成独立审计。

最终 gates：{'human_execution': True, 'bounded_Human_matrix': True, 'online_implemented': True, 'blocker': True, 'closed_loop': True, 'gym_assessed': True, 'source_integrity': True}。原文件 fingerprint 核对 1544 个，变化/缺失 0。资源策略为一个 physics owner、一次一个模拟；规划 worker 为现有 CPU 机制，不增加并行环境。共 12 个 Human 有效三臂运行、3 个 launch exception、11 个 online attempt（9 成功、2 abort）、2 个 Gym episode；25 个有完整 trace 的 attempt 中 20 个物理/scientific PASS，5 个负例保留。未开展正式 held-out/population/RL campaign。

命令和版本：脚本目录可重跑 human_qualification.py、test_online_reference.py、online_probes.py、motion_set.py、closed_loop.py、physical_audit.py、collect_evidence.py、gym_smoke.py、gym_contract_checks.py；均使用 isolated research env、OMP/OPENBLAS/MKL=1。cuda_prepare.sh/cuda_check.py 记录独立环境准备。测试日志和 SHA256 在附属证据。报告/compact evidence/source/scripts 逐文件 staging，raw traces 留在本地 manifest 指向的位置；没有 commit/push/merge/reset/stash，未删除历史证据。Commit/push 需后续显式授权。

本轮到此 STOP。唯一建议下一步：先冻结并验证单 Human SAC 的 reward、normalization、episode/throughput/evaluation contract，再请求新的 bounded training campaign。
