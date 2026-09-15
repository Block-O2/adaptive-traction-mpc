# Stage-5 Interface Robustness final campaign：剩余问题根因审计

> 范围：只读分析 frozen campaign 与小型、非正式、同快照离线诊断。
> 本审计没有改变控制器、阈值、margin、CEM、interface model、task
> contract、runtime 实现或任何 Stage-3/4 文件。

## 结论

- **Part A 主分类：A1 — startup interval/constraint semantics mismatch。**
  MPC 只约束未来完整 `20 ms` 的 `Δdq/0.020`，而在线 monitor 在启动不足
  `20 ms` 时分别对已有 `5/10/15 ms` 因果窗口执行同一个 `600 deg/s²`
  判据。seed `20260824` 选出的首动作产生更大的 executable-wrench 阶跃，
  使 truth q2 在 `5 ms` 窗口达到 `633.7/642.8 deg/s²`；其反事实完整
  `20 ms` 平均却只有 `466.7/466.5 deg/s²`。seed 差异是触发条件，首要
  缺陷是 MPC 与 monitor 没有检查同一组启动窗口。
- **Part B 主分类：B6 — unresolved。** frozen 30-episode 数据中的所有主要
  数值 kernel 几乎同比例变慢约 `16%`，但同快照 benchmark 无法复现该幅度；
  将 diagnostic-only `plant.interface_history` 从 `21` 扩展到 `660,000`
  条目没有造成减速，GC 和 wall-minus-process 也不能解释 campaign 的
  `+2.91 ms`。B1/B2/B3 缺乏支持；机器/CPU throughput 是当前最合理假设，
  但没有 CPU frequency/thermal telemetry，故不能升级为 B4。
- frozen campaign 的科学结论保持不变：
  **`EXIT C — STOP THIS IMPLEMENTATION`**。本审计不重命名、不补救、也不
  改写既有 25/27 core 结果。

## Part A：启动加速度

### 同 plant 的 pass/fail 比较

下表的 `u` 是 t=0 CEM 选出的 total Human generalized input；`ΔWcmd` 是
相对加载 support command 的六维 executable-wrench 跳变范数；`â20` 是
MPC 预测；`atruth,5` 是评估真值；`atruth,20 CF` 是只把同一已选首动作
继续到首个 20 ms 边界的离线反事实，未计入 campaign。

| plant | seed | campaign | u [Nm] | Δu 相对 t=0 support [Nm] | ‖ΔWcmd‖ | â2,20 | atruth,2,5 | atruth,2,20 CF |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| low_low_high | 20260824 | ABORT | `[42.226,-4.946]` | `[+1.686,+2.550]` | 14.572 | 547.1 | **633.7** | 466.7 |
| low_low_high | 20260825 | COMPLETE | `[39.942,-4.543]` | `[-0.598,+2.953]` | 10.662 | 569.1 | 546.4 | 412.5 |
| low_low_high | 20260826 | COMPLETE | `[40.115,-5.033]` | `[-0.425,+2.463]` | 9.061 | 473.8 | 474.6 | 349.5 |
| high_low_high | 20260824 | ABORT | `[42.217,-4.960]` | `[+1.687,+2.549]` | 14.535 | 551.3 | **642.8** | 466.5 |
| high_low_high | 20260825 | COMPLETE | `[39.933,-4.557]` | `[-0.597,+2.952]` | 10.626 | 573.5 | 560.3 | 411.3 |
| high_low_high | 20260826 | COMPLETE | `[40.106,-5.047]` | `[-0.424,+2.462]` | 9.031 | 478.2 | 470.2 | 346.1 |

单位：wrench 跳变用混合六维诊断范数，仅作 paired comparison；加速度均为
`deg/s²`。六个 5 ms setup replay 的已选 action 与 frozen trace 逐元素误差
为 `0`。

### first-divergence timeline

| 时刻 | 共同/不同量 | low_low_high 失败 vs 两个通过 seed | high_low_high 失败 vs 两个通过 seed |
|---:|---|---|---|
| t=0 solve 前 | Human q/dq、robot cuff pose/twist、loaded interface、explicit predictor、previous command、测量与 monitor 初史 | 保存的所有数值字段 seed 间 norm 差 `0` | 同左，差 `0` |
| t=0 CEM 后 | **第一个实质差异：selected action** | q1 motion increment `+1.686`，通过为 `-0.598/-0.425 Nm` | `+1.687`，通过为 `-0.597/-0.424 Nm` |
| t=0 command | executable command step | force/moment step norm `13.755/4.810`，通过为 `9.854/4.070`、`8.384/3.437` | `13.714/4.817`，通过为 `9.813/4.076`、`8.349/3.442` |
| t=5 ms | physical response | force `91.17 N`；actual Human input `[42.83,-6.76] Nm`；truth q2 `633.7`，online `504.4` | `91.51 N`；`[42.90,-6.79] Nm`；truth `642.8`，online `518.9` |
| t=10 ms | monitor decision | truth 10 ms `593.9`，online causal mean `610.5`，因此 ABORT | truth `594.0`，online `625.6`，因此 ABORT |
| t=15/20 ms | 实际 campaign | 不存在；运行已在 10 ms 终止 | 不存在 |
| t=20 ms CF | 同一首动作的反事实完整 hold | truth `466.7`、online `492.6`、MPC predicted `547.1`，三者均低于 600 | truth `466.5`、online `508.8`、predicted `551.3`，均低于 600 |

完整每 5 ms 数据见 `startup_timeline.jsonl`，包括 q/dq、online/truth
acceleration、MPC prediction、support/motion、Human/robot-site allocation、
position/velocity/orientation feedback、executable/physical wrench、actual Human
input、interface state/velocity、explicit predictor state、previous command 与
increment。由这些量重建的 executable command 与 frozen command 的最大
六维 residual 为 `2.4e-5`，属于数值重建误差。

注意：frozen trace 没有序列化 robot joint q/dq 或完整 CEM population
margin；它保存了 robot cuff pose/twist、首个 selected horizon 及其首步
acceleration/force/moment margin。相同 deterministic loaded initialization
与逐位一致的首动作复现支持初态等价，但不虚构未保存的 population 数据。

### H1/H2/H3/H4 判定

| 假设 | 判定 | 证据 |
|---|---|---|
| H1 insufficient model-error margin | **不是 20 ms 根因**；存在短瞬态预测误差 | 失败动作的 counterfactual truth 20 ms 比 MPC prediction **低** `80.4/84.8 deg/s²`；通过 seed 低 `124.3–162.2`。但在 5 ms 处 online model 低估 truth `129.3/123.9`，说明短瞬态并不精确。 |
| H2 startup time-window mismatch | **确认，主因** | candidate constraint 只在 20 ms state grid 计算 `Δdq/20 ms`；monitor 在历史不足 20 ms 时检查 5/10/15 ms causal mean。失败动作 5 ms 超限、20 ms 合规。 |
| H3 seed-dependent first action/slew | **确认，为触发因素** | 初态完全相同；失败 seed 首动作 q1 increment 方向相反，六维 command step 比通过 seed 大约 `36–61%`，差异先于任何 plant-state 差异。现有 contract 没有 hard total-command slew limit，因此不能单独称其违反既有约束。 |
| H4 initial state/history inconsistency | **排除（在可保存/可复现边界内）** | 同 plant 三个 seed 的 t=0 Human、cuff、interface、predictor、previous command 全部逐位一致；estimator/monitor 均从同一单样本历史开始；setup replay 精确复现 selected action。 |

### Part-A 最小建议（未实现）

先统一 acceleration 约束语义：若在线启动阶段要在没有 exemption 的情况下
检查 `5/10/15/20 ms`，MPC candidate screening 也必须对同样的子区间和同样
的 acceleration 定义检查。不要用统一 margin 掩盖 interval mismatch。
完成语义统一后，再把 total-command/executable-wrench slew 作为独立 contract
选择评估；当前证据尚不足以直接注册一个新阈值。

## Part B：30-episode runtime

### frozen timing 的增长位置

| section（mean ms/solve） | first 5 | last 5 | Δ | 相对变化 |
|---|---:|---:|---:|---:|
| solve total | 18.039 | 20.937 | +2.897 | +16.1% |
| candidate population | 14.995 | 17.409 | +2.414 | +16.1% |
| dynamics propagation | 14.644 | 17.001 | +2.357 | +16.1% |
| first-action screening | 1.634 | 1.891 | +0.257 | +15.7% |
| other Python/NumPy | 1.303 | 1.512 | +0.209 | +16.0% |
| Human dynamics | 4.987 | 5.793 | +0.806 | +16.2% |
| interface propagation | 2.395 | 2.777 | +0.381 | +15.9% |
| loaded transforms | 2.271 | 2.634 | +0.363 | +16.0% |
| cuff allocation | 1.274 | 1.478 | +0.204 | +16.0% |
| geometry | 1.240 | 1.438 | +0.198 | +16.0% |
| cost/constraints | 0.296 | 0.344 | +0.048 | +16.3% |
| sampling / elite update | 0.041 / 0.067 | 0.047 / 0.078 | +0.006 / +0.011 | +14.9% / +16.0% |

总 slope 为 `+0.170 ms/episode`。增长并不集中在某个 candidate-dependent
分支，而是所有不同 NumPy/Python kernel 近似同比例缩放。这与“某个容器被
逐项遍历”或“某一 phase 算法越来越复杂”的形态不一致。

frozen evidence 只有每 episode 的 section mean/p95/max；没有保存逐 solve
timing、RSS 或 GC event。`trace.npz` 虽有 5 ms phase 序列，却不能与不存在的
逐 solve runtime 对齐。因此不能从旧文件诚实恢复 phase-specific runtime 或
solve-index spike。episode/section/phase-count 表均保存在审计 CSV/JSON 中。

### persistent-state inventory

| 对象 | 增长 | 是否在 MPC timed hot path |
|---|---|---|
| `plant.interface_history` | 跨 session 无界；估计末尾约 671,390 条 | 否；最终 plant metric 汇总才读取 |
| 三个 `CausalMeasurementLayer._processed` | 跨 session 无界；末尾各约 33,598 条 | 否；measurement update 在 solve timer 前，solve 只收 current measurement |
| measurement `_pose_history` | derivative window 有界；本 ideal case 禁用 preprocessing | 否 |
| acceleration monitor samples | 约 trailing 20 ms 有界 | 否 |
| MPC `candidate_audit_history` | Stage-5 强制空 audit indices，因此为空 | 否 |
| MPC last sequence/diagnostics/safest sequence/RNG | persistent、固定尺寸、覆盖写 | 是 |
| first-action `_screen_cache` | 最多 4 条，且每 solve 新建 | 是 |
| trace/timing/status result lists | 每 episode 重置 | 否，append 在 solve timer 外 |
| Safety Filter/supervisor state | 固定尺寸 counter/last command | 否 |

### 同快照与 history ablation

固定的是同一个 loaded OUTBOUND snapshot、同一个 RNG/MPC state、15×32×2
production 配置；每次 timed solve 前都恢复相同 state，并重建 production
per-solve cache。60 次窗口结果：

| 窗口 | wall mean / p95 | process mean / p95 | wall-process mean | GC stop events |
|---|---:|---:|---:|---:|
| fresh | 18.099 / 18.682 | 18.045 / 18.619 | 0.054 | 2 |
| diagnostic history 21→660,000 | 18.194 / 18.633 | 18.147 / 18.594 | 0.047 | 1 |
| 删除该 non-control history | 18.330 / 18.801 | 18.279 / 18.735 | 0.051 | 0 |
| 600 次相同 solve 后 | 18.604 / 18.889 | 18.545 / 18.795 | 0.058 | 0 |

所有重复 selected action 逐位相同。大 history 的影响为 `+0.095 ms`
（`+0.52%`），删除后反而出现普通 timing noise；因此该容器虽应作为工程
卫生问题处理，却不是 observed `+16.1%` MPC 增长的原因。600 次 stress 后
同快照只增长约 `2.8%`，远小于 campaign；wall 与 process 同步变化、GC 很
少、最大 RSS 从 `542,736,384` 增至 `553,402,368` macOS bytes（主要包含
660k diagnostic list 的驻留分配，但该分配未造成配对 runtime 增长）。没有证据
支持 GC pause、Python object count 或 scheduler wait 为主因。

### Part-B 判定与最小建议（未实现）

主分类为 **B6 unresolved**：

- B1 被 static inventory 与 660k-history paired benchmark 反驳；
- B2 未获 RSS/GC/同快照证据支持；
- B3 与各 section 同比增长、同快照等价结果不符；
- B4 是剩余首要假设，但当前没有 frequency/thermal/系统负载 telemetry，且
  同快照 stress 只复现约 2.2%，故不能宣称 thermal throttling 或 OS effect
  已确认。

最小下一步是**只增加诊断观测，不优化**：在独立、受控、固定 snapshot
benchmark 中同步记录每 solve wall/process time、CPU frequency/thermal（若
平台可用）、system load、RSS 与 GC callback，并在新进程/长进程之间交错
测量。不要在根因未确定前改 horizon、candidate、pacing、GC policy 或 NumPy
实现。

## Part C：单一决策表

| issue | confirmed root cause | 类型 | 最小下一步 | controller mathematics | 旧 EXIT-C |
|---|---|---|---|---|---|
| startup q2 overshoot | A1：MPC 20 ms-only screening 与 monitor 的 5/10/15/20 ms 启动判据不一致；seed 首动作/command step 是触发因素 | software/constraint-semantics bug；不是 20 ms model-margin 不足 | 统一 candidate 与 monitor 的 causal interval 集合；之后再独立决定是否注册 total-command slew hard constraint | 需要改变离散 constraint evaluation，不改变架构、action space 或 objective | 保持有效 |
| long-session runtime | B6：具体机器级原因尚未解析；history/GC/state-dependent 分支没有证据 | runtime-engineering issue | 先做带 CPU/system telemetry 的受控同快照诊断，不做优化 | 不需要 | 保持有效 |

## 审计产物

- `results/interface_robustness_final_campaign_v1/root_cause_audit_v1/audit_summary.json`
- `startup_comparison.csv`、`startup_timeline.jsonl`、
  `counterfactual_first_action_hold.json`
- `runtime_by_episode.csv`
- `startup_q2_acceleration.png`、`runtime_by_episode.png`、
  `runtime_components_by_episode.png`、`same_snapshot_benchmark.png`

这些均为 diagnostic-only 派生证据；没有覆盖 frozen campaign trace，也没有
改变其统计或最终 `EXIT C — STOP THIS IMPLEMENTATION`。
