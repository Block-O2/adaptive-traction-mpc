# B HOLD → RETURN Critical Path v1

STATUS: 完成 focused work package，结果 **NOT_FROZEN**。42 次新 START 均有唯一 END；19 次 host 全任务完成，**0 次 complete + original R2 PASS**。未降低任何任务或安全门槛，未创建 B_RUNTIME_BASELINE_V1。本包在原 t0 的预计 2–4 h 范围内结束；这不是“预算耗尽”或“不可能通过”的证明。

原 t0：2026-10-07 15:05:30 UTC；dispatch cutoff：19:35:30 UTC；hard stop：20:05:30 UTC；最多 80 次尝试。历史封存包只读。当前包 canonical 路径：`/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1`。Windows 报告及只读入口：`C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1`。

## ROOT CAUSE

原假设“RETURN request/result/validation 导致 scored HOLD 额外延迟”不符合实际程序顺序：**原 guarded HOLD exit 先记录，随后才创建 RETURN request**。提前 RETURN 工作能减少之后的写入延迟，但无法缩短已经记录的 scored HOLD。

真正的 scored HOLD 临界路径是：第一段原始 0.5 s HOLD 的 actual reference start，第一段真实 endpoint receipt，第二段原始 HOLD request/collection/current admission/actual reference start，第二段真实 endpoint receipt，下一次原始 guarded phase 检查。两个 reference 起点都受真实 worker/feedback/admission/physics catch-up 串行工作影响。实际 endpoint 写入前，原 governor completion 不能为 true。

以下各行都来自**同一次 transition**。后三列与两段 0.5 s 相加闭合该行 scored HOLD；不相加跨 run median。第二列间隔包含第一 endpoint 迟到及第二次交接，不再另外重复加这些费用。

| Historical run | Case | HOLD s | Entry→first reference ms | First nominal endpoint→second reference ms | Last nominal endpoint→scored exit ms |
|---|---|---:|---:|---:|---:|
| 082_N13_S2_C5_host_nominal | nominal | 1.025 | 10.250 | 13.500 | 1.250 |
| 088_N13_S2_C5b_host_nominal | nominal | 1.030 | 10.750 | 14.750 | 4.500 |
| 095_N13_S2_D2_C5c_host_nominal | nominal | 1.035 | 16.000 | 17.250 | 1.750 |
| 099_N13_S2_D2_C6_host_nominal | nominal | 1.030 | 10.500 | 13.250 | 6.250 |
| 103_N13_S2_D2_C6_handoff_host | nominal_tail | 1.035 | 10.250 | 18.000 | 6.750 |
| 079_N13_S2_C4_host_deviation | legal_deviation | 1.030 | 10.250 | 15.250 | 4.500 |
| 101_N13_S2_D2_C6_host_deviation | legal_deviation | 1.030 | 10.750 | 14.250 | 5.000 |

完整事件、source/request/actual write/first native ownership 在 `reports/HOLD_CRITICAL_PATH_EXISTING.json`。旧 traces 没有保存每次 dwell/minimum 函数调用的 host timestamp；这些缺口明确标记，1 s 阈值的派生位置不冒充观测事件。新增 `_CRITICAL_TRACE.json` 和 `_EXACT_TRANSITION.json` 给出实际 guard 调用证据。

具体新增 041 实例：HOLD entry 19.225 s，first actual reference 19.2375 s，first endpoint physical 19.7435 s，second reference 19.75325 s，second endpoint physical 20.258 s，scored exit source 20.255 s。source 20.250 s 的检查中 reference progress 仍为 0.4975 s，`active_segment_complete=False`。sensor dwell 约 0.505 s 已提出 RETURN；shared minimum 采用原短路顺序，只在 reference ready 后才实际调用。原 completion 在真实 endpoint commit 后达到 0.5 s，随后原 guard 允许 RETURN。该 run scored HOLD=1.030 s；之后 RETURN request→actual write=44.874106 ms。

最终安静 C13 nominal 047：scored HOLD=1.035 s。entry→first reference=14.0 ms，first nominal endpoint→second reference=16.5 ms，last nominal endpoint→scored exit=4.5 ms，共 35.0 ms。合法偏差 048：对应 11.0、12.75、1.25 ms，共 25.0 ms。原始 sensor dwell、minimum 和 completion 都保留。

R2 clock audit：这是 reference 实际完成与串行交接/服务成本导致的真实时序开销。5 ms 服务机会会影响什么时候重新读取状态，但整数倍本身不是量化误差证明。dwell 在约 0.505 s 已满足，不是 1 s 后的主要阻塞；原 reference completion 在上界附近仍为 false。未发现可以通过改 timestamp、backdate 或给未来 completion 记账修复的 bookkeeping bug。

## FIX / A–B–C dependency

详表：`reports/HOLD_TRANSITION_DEPENDENCY_TABLE.md`。

A 可提前：固定 task endpoint、存储、消息结构、不可变几何。B 可准备但必须刷新：精确值和 model/reference 绑定的 mechanics/schedule context。C 保留在当下：最终 q/dq、reference completion、terminal/stationary 条件、sensor dwell、shared minimum、freshness、phase ownership、current mechanics/native admission、feedback command 和真实写入。

实现保持的最小 C13 链：C7 在原真实 HOLD endpoint commit 后请求一次当前 service；C8a 在已有 OUTBOUND worker 工作之后准备无 actuation authority 的纯 HOLD mechanics context，advisory decision 丢弃；C9 复用精确原 HOLD schedule，但每次保留原请求验证及当前剩余时间 budget；C10 用完整原系数/时长识别原 sample 序列，避免重复生成 key samples；C11a/C12 在实际发出 HOLD request 后进行有界 collection-only service，原旧 command 继续承担真实 physics，下一原循环重读当前状态并完整审查；C13 将同一实际不可变 TASK payload 的两次 decode 合成一次，原 execute/prepare AST 除 decode assignment 外相同。

没有提前执行 RETURN、提前切 phase、复用过期 native certificate 或推测未来 q/dq。保留 0.5 s dwell、1 s shared minimum、R2 upper 1.020000001 s、1e-12 completion、5 ms service 和 0.25 ms native dt。

RETURN base-plan dependency probe：两个保存输入按原路径重算一致；当 deployable current q 和 tracking_snapshot.source_state 一起改变 1e-6 rad，原 RETURN target、polynomial、cost/terms 和 execution screen 均改变。单独只改 q 会被原 snapshot 一致性检查拒绝。因此固定 task endpoint 不足以把原完整 RETURN base plan 当静态计划。

仅 source/deps 中一处实现改变：runtime_coordination_residual_v2.py 的 HOST-only 已发出 HOLD request collection callback。其余原 controller/physics/safety/task 源码及原生源/二进制保留 hash。source 注册修复采用新的版本化 generated-runtime 文件名，并保留原 `INSTALLED_RUNTIME_VERSION_CHANGED` 断言。早期 START manifest 未包含 source/deps；保留 end imported-source hashes、C11 patch 和 compiled-owner 版本历史，不伪造过去的 START source hash。自 043 起 START 已包含 source/deps。

## SCIENTIFIC

20 个完整 SCI gates PASS，native qpos/qvel/command/contact 和 trace errors 为零；原选定计划、参考 q/dq/ddq、J_F/force/moment/tracking/clearance/safety/fallback 保持一致。最终恢复的 C13 使用 035/036 gate。HOST-only scheduling 的 scientific 路径按原 no-delay 语义运行；未修改 scientific HOLD duration。

005/006 的 C8 cache 未在 scientific mode 开启，明确不能作为 cache validation；009/010 重新启用 cache 并通过完整 gate。023 在 source-registration startup 前失败，没有 SCI 结果，也没有实际 native step。所有 substantive 已进入 host 的版本都有先行保存输入 gate 和两个完整 SCI gate；C16 系列只有局部数学 PASS，速度无收益，因此没有新物理尝试。

| SCI ID | Gate | Scope |
|---|---|---|
| 001_C7_science_nominal | PASS | full native/trace gate |
| 002_C7_science_deviation | PASS | full native/trace gate |
| 005_C8_science_nominal | PASS | cache bypass; excluded for C8 validation |
| 006_C8_science_deviation | PASS | cache bypass; excluded for C8 validation |
| 009_C8a_science_nominal | PASS | full native/trace gate |
| 010_C8a_science_deviation | PASS | full native/trace gate |
| 014_C9_science_nominal | PASS | full native/trace gate |
| 015_C9_science_deviation | PASS | full native/trace gate |
| 019_C10_science_nominal | PASS | full native/trace gate |
| 020_C10_science_deviation | PASS | full native/trace gate |
| 023_C11_science_nominal | None | full native/trace gate |
| 027_C11a_science_nominal | PASS | full native/trace gate |
| 028_C11a_science_deviation | PASS | full native/trace gate |
| 031_C12_science_nominal | PASS | full native/trace gate |
| 032_C12_science_deviation | PASS | full native/trace gate |
| 035_C13_science_nominal | PASS | full native/trace gate |
| 036_C13_science_deviation | PASS | full native/trace gate |
| 039_C14_science_nominal | PASS | full native/trace gate |
| 040_C14_science_deviation | PASS | full native/trace gate |
| 043_C15_science_nominal | PASS | full native/trace gate |
| 044_C15_science_deviation | PASS | full native/trace gate |

## HOST R2 / FAST

正式 cold nominal VALID=0；正式 same-interpreter nominal VALID=0；正式 legal-deviation VALID=0。正式 ladder **未 dispatch**，不能把 cold-process development smoke 计作 formal VALID。先行 nominal 均 FAIL，因而没有无依据地扩展 4+4+2 qualification。

21 次 host 尝试，19 次全任务完成；所有 complete original R2 均 FAIL。完整 host HOLD min/p50/p95/max：1.025/1.030/1.0355/1.040 s；19 个值完整保存在 `reports/PACKAGE_RESULTS.json`。013 同时有 service protocol failures；该次还发生大体积 Git baseline 文本读取，不能作为安静性能对比，但其失败不会删除。011 和 021 不计入 complete HOLD 分布。

| HOST ID | Export/worker status | Complete task | HOLD s | Original R2 | Legacy strict55 |
|---|---|---|---:|---|---|
| 003_C7_host_nominal_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 004_C7_host_deviation_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 011_C8a_host_nominal_diagnostic | FAILED | no | not reached | None | None |
| 013_C8a_host_nominal_diagnostic_retry | COMPLETE | yes | 1.040 | False | FAIL |
| 016_C9_host_nominal_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 017_C9_host_deviation_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 018_C9_hold_handoff_attribution | COMPLETE | yes | 1.035 | False | FAIL |
| 021_C10_host_nominal_diagnostic | COMPLETE | no | 0.000 | False | FAIL |
| 022_C10_host_deviation_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 029_C11a_host_nominal_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 030_C11a_host_deviation_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 033_C12_host_nominal_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 034_C12_host_deviation_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 037_C13_host_nominal_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 038_C13_host_deviation_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 041_C14_host_nominal_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 042_C14_host_deviation_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 045_C15_host_nominal_diagnostic | COMPLETE | yes | 1.030 | False | FAIL |
| 046_C15_host_deviation_diagnostic | COMPLETE | yes | 1.025 | False | FAIL |
| 047_C13_host_nominal_quiet | COMPLETE | yes | 1.035 | False | FAIL |
| 048_C13_host_deviation_quiet | COMPLETE | yes | 1.025 | False | FAIL |

最终安静 C13：

| Metric | 047 nominal | 048 legal deviation |
|---|---:|---:|
| OUTBOUND s | 9.010000 | 9.010000 |
| HOLD s | 1.035000 | 1.025000 |
| RETURN s | 9.006500 | 9.011250 |
| FAST feedback gap p50 ms | 5.003868 | 5.004861 |
| p95 ms | 5.399078 | 5.427369 |
| p99 ms | 5.931350 | 6.228496 |
| max ms | 29.490669 | 49.304719 |
| RETURN actual request→actual write ms | 49.492701 | 46.545199 |
| RETURN source→actual write ms | 50.802240 | 50.738326 |
| Maximum physics backlog ms | 13.366519 | 14.075257 |

最终两次所有 functional checks 中只有 original_R2 FAIL；physical/safety/current admission、meaningful plans、bounded age/backlog、FAST service 条件和 actual native command ownership 均 PASS。Legacy strict55 独立 FAIL，不作为唯一 promotion criterion。

每次 RETURN 的 request/snapshot/enqueue/queue/compute/ready-collect/current validation/actual write 都有 non-overlapping 分解且相加闭合实际 request→write。actual write 的 receipt `apply_ns` 与 lifecycle activation return 不是同一事件；first native step 由真实 write availability 向上取 0.25 ms grid，迟到前的每个 native interval 使用旧 receipt command。全部有完整证据的 host 无 causal ownership violation。

FAST gap 统计只测量原 `_execute_interval` feedback service。C11/C12 collection-only iterations 不是 feedback/actuation service，begin/socket-ready/finish 和旧 command native steps 单独保存；没有把 collection 通知充作 FAST 写入。all-actual-write command age 分布、TASK source→lifecycle activation、misses、meaningful plans、backlog 和 causal 原始审查在各 `_FUNCTIONAL.json` 及 `_TRANSITION_METRICS.json`。

## ROBUSTNESS

条件性真实 RETURN delay/stale/model-version/current-mismatch/reject suite **NOT RUN**：nominal primary success 未满足。保存输入测试证明改变 model/reference/screen/budget 时原重算或原拒绝、无效 advisory preparation 会丢弃；这些不冒充真实 transition robustness qualification，也不声称未来/过期 RETURN 已通过物理故障测试。

## B STATUS / M2 READINESS

**B_FROZEN = FALSE；B_RUNTIME_BASELINE_V1 = NOT_FROZEN。** 本包研究结束并封存，不代表 B baseline 冻结。最终可复核实现为恢复后的 C13，不是被拒绝的 C14/C15/C16。

M2 readiness：未启动，兼容性未判定。冻结 Q weights SHA256 `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` 与旧包保护快照一致。无 Q/G 修改、无 Q inference readiness smoke、无 M2 physics、无 adaptation/retraining、无 Human matrix 扩展。

## NEGATIVE RESULTS

1. C7–C13 的合法 endpoint/collection/context/decode 优化未使原始 R2 通过；关闭详细 transition 诊断的 C13 smoke 也失败。
2. C14 完整 mapping key 因逐周期 label 改变而无实际 hit；C15 去除非数值 label 后 SCI 只有少量 hit，原微小非零 dq 仍变化。没有把这些原值归零，也没有得到 host R2 PASS；最终恢复 C13。
3. C16/C16a/C16b 的精确几何/allocator partial reuse 局部逐位一致，但典型原 prepare 约 0.33–0.36 ms，复用约 0.34–0.42 ms，未获得速度收益。无 host dispatch。
4. 011 原 motion/commissioning safety 路径失败；021 actual first TASK IPC queue 约 366 ms 后原任务 ABORT；023 generated-source consistency startup 失败。全部保留原输入、日志、失败记录与预算身份，没有丢弃或当完整任务成功。

## Accounting / preservation / reproduction

42 个 START/END 一一对应，20 个 SCI completed gates 加 1 个 SCI startup failure；21 个 host attempts。所有实际 native steps：4,617,682（1154.4205 s）；023 原 counter 未导出，但 traceback 证明在物理入口前失败，native=0。主模型已报告 API calls 933,771；native worker 已报告 114,345；advisory preparation 1,680 次从每 run 最后累计 snapshot 单独取一次，未相加重叠 snapshots。warm/import/failed-partial 未完整导出的 model counters 明确 UNKNOWN，不能据此声称完整 model 总数。成功离线和一个已导出失败离线测试的已知 model calls 下界 9,210；未导出失败 counter UNKNOWN；保存输入测试 native steps=0。

资源检查 123 条，physical run 中每45s及 dispatch 前后采样，analysis 不声称连续45s采样。完整 resource/headroom/PSS/swap/OOM 在 `reports/RESOURCE_SUMMARY.json`。未改变 power/memory/swap/WSL 设置，未终止无关进程。所有观察到的 TASK owner JOIN 及 commissioning close 已核对。

旧封存包 10 个保护文件及 frozen-Q 文件逐位 hash 保持，原 Linux 主 repo branch/HEAD/status/index/staged binary diff 均一致；主 Git 状态未写入。`preservation/FINAL_PRESERVATION.json` 保留校验证据。native source/build binary 与本包初始值一致。

只读复核：Windows `run_readonly.ps1 -Mode Check`，或 `-Mode Review -TaskId 047_C13_host_nominal_quiet`。它只核对 ledger/manifest 或读现有结果，不启动物理。原历史 runner/reproduce 脚本的继承入口不作为本包复跑授权。封存后 dispatcher/cohort guard 拒绝新增 physical attempt。

原始 outputs/inputs/results/logs、version snapshots、作者脚本、源代码和 manifests 保留在 canonical 包；Windows 镜像仅复制本报告和紧凑审查文件。`FULL_PACKAGE_MANIFEST.json` 对全部本包非缓存常规文件记录 SHA256；只读历史 symlink 单独记录 target。排除 manifest 自身、生成后的 verification 文件和 `__pycache__`，避免自引用。gzip 全量解压 CRC 检查记录在 `reports/FULL_PACKAGE_VERIFICATION.json`。

## NEXT

对已封存的两段 HOLD request→实际 reference activation 链做独立实现审查，再决定是否值得继续 B 优化。

REPORT PATH: `C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1/REPORT.md`；canonical `/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1/REPORT.md`。

STOP.
