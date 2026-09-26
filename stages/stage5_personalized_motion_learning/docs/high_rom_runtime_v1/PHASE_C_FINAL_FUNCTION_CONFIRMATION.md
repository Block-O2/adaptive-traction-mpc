# High-ROM Stage C-close：C08 最终同版功能确认

**状态：`HIGH_ROM_RUNTIME_CANDIDATE_FROZEN`。** 在工作区 `/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-runtime-v1` 的 `codex/full3d-cr12-high-rom-runtime-v1` 分支，从原 HEAD `89798cb83af7c8da20e63963495ebbc068489e20` 封存 C08。原固定起点 **10/10**、原变起点 **16/16** 都由当前 C08 源码重新运行且逐例通过；同一 173 项冻结源码/配置对应此前原低 ROM **23/23**。本轮没有调参、修后重跑、替换案例或修改生产源码。

## 冻结与执行

`CANDIDATE08_FINAL26_PLAN.json` 在运行前固定原 10+16 案例、完整 case payload SHA、评分规则和 runner/scorer SHA；10 例逐项取自原 `CANDIDATE03_REGRESSION_PLAN.json`，16 例逐项对应 `HIGH_ROM_FUNCTION_FRESH16_SPEC.json`。每次执行前核对 C08 的 173 项源码/配置哈希与 case SHA；26 次都从本工作区加载真实 MuJoCo CR12–柔顺袖套–Human V2 闭环，使用原 125° 工程模型和各自登记起点。`CANDIDATE08_FINAL26_PROGRESS.jsonl` 保留逐例进度；`CANDIDATE08_FINAL26_RESULT.json` 有完整 26 例分母和逐例指标。原始轨迹保留在 `results/high_rom_runtime_v1/candidate08_final26/`，约 5.7 GB；`PHASE_C_FINAL_FINGERPRINTS.json` 记录 173 项源码/配置、6 个评分/运行脚本以及 26×6 个原始文件的 SHA-256。无漂移。

结果：26/26 `COMPLETE`，实际 120°/120° 到达时进入 HOLD，连续原生有效 dwell 最短 **0.515 s**，实际 RETURN 回到每例登记起点。原采样任务/安全评分与原生 arrival、dwell、RETURN、计数、力/力矩、ROM、接触、间隙、phase 规则均通过；过期激活 **0**。最小原生小腿间隙 **8.247 mm**，最小采样袖套间隙 **6.613 mm**，最大原生界面力 **128.596 N**，最大原生界面力矩 **17.907 Nm**。逐例失败数 0；没有隐藏删除或排除。

| 同版功能证据 | 完成/分母 | 说明 |
| --- | ---: | --- |
| 原低 ROM | 23/23 | C08 源码、原 80°/100° plant；本轮引用已冻结结果，未重跑 |
| 固定起点 High-ROM | 10/10 | 本轮重新执行原十例 |
| 变起点 High-ROM | 16/16 | 本轮重新执行原十六例；是已暴露 payload 的开发确认 |

## Runtime 与剩余限制

冻结的 8 例 C08 runtime gate **保持 PASS**：planning compute p95 **28.644 ms**（≤30）；sample→activation p95 **49.342 ms**（≤55）；control miss **11.171%**（<11.82% 冻结功能基线）；stale activation **0**。本轮没有重新定义该 gate。

新增 26 例的描述性计时：442/442 requests activated；compute mean/p95/max **17.117/29.121/30.550 ms**；activation age mean/p95/max **30.194/49.911/55.155 ms**；control miss **14440/156864 = 9.205%**，最长单次连续 miss 38 个 5 ms grid（190 ms）。这些数据不取代原 8 例 gate，也不能证明硬实时。

原历史 certificate 快照在 C08 仍需 **1.286/1.273 s**。C08 gate 的 control miss **11.171%** 高于 C07 的 **9.524%**；26 例中也出现 190 ms 连续 miss。旧 125° 硬限仍是工程假设。原生 q/dq 节点间隔 0.25 ms，安全 monitor 极值是逐步累计记录，袖套/部分几何量约 5 ms 采样；本证据不覆盖物理步之间的连续安全，也不构成硬件、临床、fresh qualification 或 RL 结论。

## 独立审计、额度与封存

一位独立只读 Auditor **接受**同版开发确认：复核 173 项哈希、6 个脚本哈希、26 个登记 payload、156 个原始文件 SHA，全部 26 例紧凑评分与一次固定/一次变起点原生节点独立抽查；同版低 ROM 23/23 和正确 C08 gate 也已核对。Auditor 未重算全部 5.7 GB 节点，且明确保留上述长尾与安全限制。未运行仿真、修改文件或操作 Git。

真实 Codex 周额度窗口 10,080 min，reset Unix `1790917420`：本轮起点 **21% used**，最终收口读数 **23% used**，新增 **2 个百分点**；+2 即 23% 是开始封存线，24% 是不可主动越过的最大授权，45% 是项目停止线，50% 为硬保留。一次自动审批曾把 22% 误判成起点 +2；凭同一真实窗口及 21→22 的读数复核后，原命令获准继续，没有绕过监测或另起实验路径。无付费服务、Astra、并行仿真 worker 或硬件动作。

复现入口：`scripts/high_rom_v1/run_final26_batch.py --start <0..25> --count <1|2>`，runner 的确切命令、源码/配置 SHA 和 host 耗时在每例 `HIGH_ROM_CASE_RESULT.json`；汇总命令为 `scripts/high_rom_v1/summarize_final26.py`。26 例合计 host 执行 **1457.1 s**。原低 ROM 与 8 例 gate 的原始证据和摘要仍在 `results/high_rom_runtime_v1/candidate08_low23/`、`candidate08_gate/` 及本目录相应 JSON。

本地 checkpoint 仅逐项 stage 本 runtime/High-ROM campaign 的源码、评估脚本、配置/报告与紧凑证据；约 5.7 GB 原始轨迹继续保留在本工作区，由指纹关联，未放进 Git。实现与证据的本地 checkpoint SHA 为 `534d59ba3c31b28bf4acc7ab65c2850e810ae22a`；其后的额度/SHA 元数据更正另做本地收口提交，最终 HEAD 见交付记录。未 push、merge、reset、stash、clean 或删除。

**阶段 C-close 到此停止。** 不进入 fresh qualification、进一步优化或 RL。
