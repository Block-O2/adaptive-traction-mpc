# B/H150 原评价器就绪度

| 项目 | 状态 | 证据 |
|---|---|---|
| OFFLINE_SCORER_REPRODUCIBLE | PASS | 真正 GitHub clone + 新 Python3.12 CPU 环境 + 旧目录读取禁止，原 parent/B/H150 重算通过 |
| FULL_FORK_REPLAY_REPRODUCIBLE | UNVERIFIED | 本轮未运行 cold commissioning/prefix/fork；没有可移植完整父 checkpoint |
| PORTABLE_FROZEN_PARENT_CHECKPOINT | FAIL | 未定位完整原父进程地址空间序列化资产 |
| D01R_parent_CAUSAL_STATE.json | FAIL / MISSING | Linux、Windows 原库存和 Git 历史搜索未找到；摘要也不等于checkpoint |
| 纯 GitHub clone 即全量 raw 评分 | FAIL | 大型native raw在独立版本化归档，下载URL尚未发布 |
| 原合同与 scorer 源码身份 | PASS | 九项合同 + 恢复索引16项 + 原v6依赖；未近似、未改门限 |

规范来源为 `research/side_studies/ihear_overnight_control_learning_transition_v1`。恢复的真实历史索引来自 Windows `ihear_cross_patient_b_h150_v1/audit_execution/FROZEN_SOURCE_CHAIN_HASHES.json`，文件 SHA `21c72a6081bda991928a07fb5ede5c606ac0807d56c14c55ddcc3245de8e9274`；上轮库存已记录同一 SHA。本轮复制原文件并逐项比对16项，九项合同 SHA 保持原值，详见 manifests/FROZEN_SOURCE_CHAIN_VERIFICATION.json。

原 `analyze_matched.py`、`explore_common.py`、`control/independent_recompute.py`、`attribution.py`、`stream_runtime_evidence.py` 和真实 `task_bootstrap.py` 原字节保留。stream reader 的 bootstrap 来自原 EXECUTION_CODE_MANIFEST_v6，并非新替代实现。执行依赖实际 `deps/fork_core.py`，SHA `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4`；不要求虚构 code/fork_core.py。

新入口 `deployment/score_b_h150.py` 只验证/复制原件、按依赖顺序显式导入原文件、清除历史搜索路径、将 S/P 绑定到新工作目录，调用原 measure、compare 和 independent measure。原 promotion assert、5 ms 左积分、0.25 ms native、完整 TASK prefix+suffix、100 ms age、receipt/torque/step ownership、运动资格门全部保持启用。没有调用移除 assertion 的跨患者 adapter，没有新增近似 scorer。

| 输入 | 原 J_F N·s | 离线原算术 / receipt / motion |
|---|---:|---|
| D01R_parent | 1436.456498145051 | PASS |
| D01R_B | 1436.456498145051 | PASS |
| D01R_H150 | 1402.6432114861727 | PASS |

H150/B gain `2.353937394034738%`；原比较 acceptance_pass=true。数值与原冻结报告逐字段比较，绝对容差 1e-8；仅 sources / execution_lineage_path 位置元数据随新目录变化。新的输出模块来源也全部记录并核实位于工作目录。

该 B 是冻结 D01R/W1 prefix 条件 B，不是零 prefix 开发 B；H150 保留完整 FROZEN_18D、RETURN plateau、T/D/ER/RETURN5 hip timing。B candidate `5908d9453a12b2aae83c88d46d4926979b223ff4732a3984eda43ec3ca9af60b`；H150 `255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931`。

## 最小离线输入与额外状态

32项真实输入覆盖 B/H150/parent trace、summary、runtime native/receipts、config、native_reference、metric、DATA、可用因果摘要、MEASURED、receipts报告和motion_series。小型文件直接由Git提供；3项runtime_artifacts.json.gz体积较大，由完整归档提供。原输入每文件大小与 SHA 位于 deployment/b_h150_fixture_manifest.json。

完整归档 `/home/hank/research_archives/repository_cleanup_v2_2026-10-21/b_h150_original_fixture_v1.tar.gz`，129608743 bytes，SHA `4d57c25005da7ac02c6f9d206c661399b8babd229066c2d468e07fc1234c8001`。原件及归档均保留；restore脚本拒绝覆盖和身份不符。离线评分无需完整父checkpoint，已用真实归档验证。

完整原 fork 是冷 commissioning + 合法 prefix + 同一 live `os.fork` 继承 MuJoCo、模型/估计器、planner、任务、传感历史、RNG、证书和不透明原生句柄。哈希清单、qpos/qvel、因果摘要不能替代这些字节。以后若从源码重新生成父状态，必须另行授权物理重演并做原相同性门，本轮没有执行，也不预判PASS。

原科学时间执行归属通过不代表 host realtime 或硬件/临床资格；服务器部署、最近云端结果身份、full fork全部保持UNVERIFIED。


## 完整 v6 执行包身份

本轮又逐项核对整个 EXECUTION_CODE_MANIFEST_v6：1426/1426 原件匹配历史 SHA，1426/1426 已在 GitHub 副本中匹配。补回42项小型原件，包括冻结 weights/DATASET、历史 graph JSON、原校验/说明、历史 source_history 和 manifest 明确包含的包元数据。没有通过排除条目或降低身份门取得PASS。完整结果见 manifests/EXECUTION_V6_FULL_AUDIT.json。

两份原 _prefix_native 库分别是 CPython3.10 Linux x86_64 ELF 与 Darwin arm64 Mach-O；原 C 源文件、setup.py 和原包说明也在相同 source 树中。这两份二进制仅作为原身份资产保存，未加载，不能当作 Python3.12 的可用扩展。原离线 scorer 不需要这些原生库；Python3.12 RL-B CPU 封存包单独通过导入预检。完整fork的原生ABI/构建与物理执行仍未验证。
