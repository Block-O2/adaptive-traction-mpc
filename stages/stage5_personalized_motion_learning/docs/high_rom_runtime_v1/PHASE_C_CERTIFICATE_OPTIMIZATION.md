# High-ROM Stage C: certificate 热点优化

**状态：`RUNTIME_DEVELOPMENT_PASS`，仅指冻结开发门槛。** C08 的 8/8 代表闭环和同源码低 ROM 23/23 通过；未做 fresh qualification、RL 或硬件动作。保守 certificate 历史快照仍有约 **1.28 s** 计算长尾，因此不能称作硬实时或连续安全合格。

## 冻结版本与修改

工作区 `/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-runtime-v1`，分支 `codex/full3d-cr12-high-rom-runtime-v1`，本地 HEAD `89798cb83af7c8da20e63963495ebbc068489e20`。C07 与 C08 各有 173 项冻结源码/配置；本轮唯一生产源码差异是 `src/traction_mpc_stage5/human_waypoint_scheduler.py`。本地 C08 未提交，旧 C07 证据、确认版工作区与原仓库均保留；没有 stage、commit、push、merge、reset、stash、clean 或删除。

根因是同一规划 request 的 duration/candidate 搜索中反复求取**相同任务起点/phase goal 的 clearance floor**。历史快照有 1,873 次 certificate 调用，其中被拒的 `outbound_dq_09` 尝试 1,854 个时长；1,873 个完整 certificate 输入彼此不同，不能安全地做整证书命中缓存。C08 仅在纯 `CombinedRigidTableClearanceV1` evaluator 上，每个 request 计算一次同值 task floor，以局部标量传给原来的 sampled 与 continuous clearance 检查。其他 evaluator 沿原路径计算；下一个 request 重新读取起点、goal、几何与约束，没有跨 request 缓存。候选数量、搜索空间、cost、阈值、125° 工程模型、任务、原安全规则和 100 ms stale 规则均未变。

## Fixed-snapshot 等价与长尾

C07/C08 使用同一冻结 snapshot。120° outbound 的 21 次，以及历史慢例各两轮 1,873 次 certificate 的输入 SHA、clearance lower 和 proof SHA 逐项相等；完整最终 decision SHA 相等。120° 的 OUTBOUND/HOLD/RETURN 决策亦与 C07 一致。此为有限快照等价证据，不是对所有状态的形式证明。

| 历史慢例 | C07 | C08 | 结论 |
| --- | ---: | ---: | --- |
| 第 1 轮 request wall | 1509.295 ms | 1286.211 ms | 同决策 |
| 第 2 轮 request wall | 1561.136 ms | 1272.661 ms | 同决策 |
| 两轮平均 | 1535.215 ms | 1279.436 ms | 降低 16.7% |
| certificate 调用/轮 | 1,873 | 1,873 | 未减少搜索 |
| certificate 内计时，第 1/2 轮 | 527.226/542.617 ms | 532.585/525.146 ms | 证书本体无确定提速 |

trig/endpoint/grid 既有缓存累计命中数在两版本各轮完全相同（首轮 3,745/3,717/1,872；第二轮 7,491/7,463/3,745）。本轮没有新缓存命中，收益来自消除证书调用之间重复的 endpoint-floor 求值。剩余约 1.28 s 长尾未解决，不能以常态 p95 通过掩盖。所有快照和逐调用证据见 `CERTIFICATE_C07_*`、`CERTIFICATE_C08_*` JSON。

## 冻结 runtime gate 与功能

`BENCHMARK_SPEC.json` 不变；8 例包括低 ROM 两例、100/100、110/110、120/120 同步与髋领先，以及 120/120 变起点 (6°,11°)、(8°,13°)。

| 指标 | C07 | C08 | 开发门槛 |
| --- | ---: | ---: | ---: |
| planning compute p95 | 31.034 ms | **28.644 ms** | ≤30 ms |
| planning compute max | 31.965 ms | 29.784 ms | ≤100 ms |
| sample→activation p95 | 52.230 ms | **49.342 ms** | ≤55 ms |
| control miss | 9.524% | **11.171%** | <冻结基线 11.818% |
| stale activation | 0 | **0** | 0 |

C08 compute mean/max 为 16.025/29.784 ms；activation mean/max 为 28.404/54.660 ms。142/142 个 request activated，dropped/stale 0；control miss 4817/43121 个 grid，最长连续 19 个 grid（95 ms）。**C08 miss 高于 C07 的 9.524%，不能声称逐代改善**；冻结开发基线比较仍通过。

8/8 代表例原生任务与安全评分通过：最短逐物理步有效 dwell 0.515 s、最小 monitor clearance 8.247 mm、最大力 114.606 N、最大力矩 16.105 Nm；实际 arrival→HOLD→RETURN，接触、ROM、phase 违反与 stale activation 均为 0。同一 C08 源码加载**原低 ROM plant**另跑原登记 23 例，23/23 `COMPLETE` 并确认；其中两例复用同源码 gate 原始结果，另外 21 例新跑。低 ROM 最短 dwell 0.515 s、最小 monitor clearance 5.951 mm、最大力/力矩 131.151 N/18.079 Nm、stale 0。高 ROM 的 125° plant 与原低 ROM plant 分开统计；本轮没有重跑完整固定 10 + 变起点 16 矩阵。

逐物理步 q/dq 节点为 0.25 ms；安全 monitor 的极值是累计记录，袖套/部分几何量约 5 ms 采样。不能把累计极值称为逐点独立复算，或推断步间连续安全。新 diff 没有引入仿真真值到在线控制；只读审计确认了该差异的 truth-firewall 路径，但未扩大为全系统独立资格。

## 审计、额度与复现

独立只读 Auditor 接受 **`RUNTIME_DEVELOPMENT_PASS`**，核对 173/173 哈希、逐证书等价、最终决策、8/8 与低 ROM 23/23、stale 0；明确指出 C08 miss 比 C07 变差及长尾仍在。指纹在 `PHASE_C_CERTIFICATE_FINGERPRINTS.json`，包含 173 项源码/配置、7 个脚本、13 个关键 JSON 与 8+23 原始结果；本轮重新验算均无漂移。

真实 Codex 周额度同一 10,080 min 窗口、reset Unix `1790917420`：本轮 **20%→21% used，新增 1 个百分点**；停止扩大方向点为 21.5%，22% 开始收尾、23% 最大授权，另有 45% 项目停止和 50% 硬保留。未把小时/token 当额度，未启动无人值守长 worker，未验证在途强制中断能力。

关键命令入口：`scripts/high_rom_v1/certificate_snapshot_audit.py` 复放两个 pickle；`runtime_benchmark.py --mode candidate --candidate-root results/high_rom_runtime_v1/candidate08_gate --output docs/high_rom_runtime_v1/CANDIDATE08_BENCHMARK.json`；`score_runtime_gate.py --candidate 08`；`run_certificate_low23_batch.py` 依预登记 `CANDIDATE08_LOW23_PLAN.json` 分批运行；`score_certificate_low23.py` 汇总。完整每例命令在各 `HIGH_ROM_CASE_RESULT.json`。原始目录 `results/high_rom_runtime_v1/candidate08_gate`、`candidate08_low23`，本地前置试跑在 `candidate08_local`。以上命令均以 `stages/stage5_personalized_motion_learning/` 为基准目录。

**到此停止阶段 C 本轮开发。** 尚存秒级证书搜索尾部风险；未来若要处理，需要单独定义新工作及验证。此轮不进入 qualification 或 RL。
