# iHEAR Lab — Research Storage Audit & Cleanup v1

状态：**CLEANUP_COMPLETE_VERIFIED / STOP**。2026-10-09（Asia/Shanghai）。本轮实际清理，先盘点、冻结 dry-run、保护核验，再逐文件删除；未开展新研究。

共删除 **4,350** 个文件：Windows 918 个、Linux 3,432 个。Windows 删除文件原分配空间 **4.474 GiB**；Linux 删除缓存原分配空间 **26.07 MiB**。Windows 研究目录逻辑大小 **5.511 → 1.038 GiB**。Linux 科学原始数据、模型、源码和原报告全部保留。

## 资源结算与计量边界

| 项目 | 清理前 | 清理后 | 单位/说明 |
| --- | --- | --- | --- |
| C: 可用 | 4.370 | 8.746 | GiB；系统净变化 4.376 |
| D: 可用 | 234.639 | 234.639 | GiB；未删除 D: 文件 |
| Linux / 可用 | 803.790 | 803.809 | GiB；df 净增加 19.14 MiB |
| side-studies 文件逻辑 | 37.000 | 36.989 | GiB；后值包含清理记录，最终记录写入另有小量增量 |
| side-studies 分配 | 37.130 | 37.111 | GiB；唯一 inode + 目录 + link 本身，不跟随软链接 |
| Windows 副本逻辑 | 5.511 | 1.038 | GiB |
| Windows 副本实际分配 | 5.538 | 1.064 | GiB；NTFS 文件 ID 去重/真实 AllocationSize |
| 主 Ubuntu VHDX | 155.229 | 155.322 | GiB；未收缩；期间增长 96.00 MiB |
| Windows 可用物理内存 | 3.733 | 1.625 | GiB；没有承诺磁盘清理提升 RAM |
| Windows commit 余量 | 6.735 | 1.562 | GiB；CIM Total/FreeVirtualMemory 口径 |
| Windows pagefile 使用 | 1712 | 4238 | MiB |
| WSL MemAvailable | 6.750 | 6.886 | GiB；含可回收缓存 |
| WSL Cached | 0.182 | 6.556 | GiB；哈希读取后文件页缓存增加 |
| WSL Swap 使用 | 4.76 | 15.01 | MiB |

资源快照为 2026-10-09T03:32:49.0088255+08:00 / 2026-10-09T03:58:58.3893960+08:00，Linux 为 2026-10-09T03:35:48+0800 / 2026-10-09T03:59:03+0800。Windows 副本后值在清理报告副本写入前测量。最终报告和清单替换会消耗少量空间；C: 净变化还受 VHDX 增长、系统后台活动及临时审计文件影响，不能等同逐文件释放量。临时完整盘点/哈希记录会在交付前删除，不永久保留大量 CSV/日志。

RAM 结论：WSL MemAvailable 仍充足，无研究遗留 physics/training worker；Windows 可用物理/commit 余量比前值下降，pagefile 使用增加。vmmemWSL 工作集由前值约 0.745 GiB 变为 4.605 GiB，同时 WSL Cached 明显增加、计算进程均结束，**与哈希遍历产生的文件页缓存相符（推断，不能全部归因于本任务）**。未发现活跃研究 worker 泄漏；没有把 C: 磁盘不足报告成 RAM 不足，也没有修改内存/swap/电源或执行 drop_caches。

## 真实存储位置与主仓库

Canonical side-studies：`/home/hank/coding/adaptive-traction-mpc-side-studies`，ext4；Windows 副本：`C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc`，NTFS。`/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc` 与 Windows 路径是同一存储，不计两份。side-studies 根本身不是软链接；研究子路径共有70条软链接，主仓库有2505条，全部有效。链接到 D: 归档的 raw 仅计 link 自身占用，不把目标重复计入 ext4。

主 Git：`/home/hank/coding/adaptive-traction-mpc-learning`，分配约 74.442 GiB（含约 2.013 GiB `.git`，du 实测总值 74.451 GiB）。主 working tree、全部历史、原有 dirty/staged 状态保护。另一 Git 为 human-closeout；direct-RL worktree 约 0.601 GiB，也未清理。Windows 根没有自身 `.git`，不会将其父目录 Git 状态当成主项目状态。

| WSL/VHDX | 位置 | 逻辑/实际占用 GiB | 状态 |
| --- | --- | --- | --- |
| Ubuntu-20.04 | `C:\Users\HankL\AppData\Local\wsl\{7baff685-a62e-4a0e-b45d-5e5814a4150c}\ext4.vhdx` | 33.213/33.213 | Ubuntu 运行；其余发行版清理前停止，未启动/卸载 |
| docker-desktop | `\\?\C:\Users\HankL\AppData\Local\Docker\wsl\main\ext4.vhdx` | 0.133/0.133 | Ubuntu 运行；其余发行版清理前停止，未启动/卸载 |
| Ubuntu | `C:\Users\HankL\AppData\Local\wsl\{c1fb01f5-3f3d-499f-8ecc-8db9c7ff390b}\ext4.vhdx` | 155.322/155.322 | Ubuntu 运行；其余发行版清理前停止，未启动/卸载 |
| docker-data | `C:\Users\HankL\AppData\Local\Docker\wsl\disk\docker_data.vhdx` | 27.859/27.859 | 独立 Docker data，范围外 |

Ubuntu-20.04 与 docker-desktop 为停止状态，仅核验宿主 VHDX，未挂载检查其内部文件系统。Ubuntu VHDX 没有 sparse/compressed 标志，宿主物理分配等于文件大小。本轮未 shutdown、fstrim、compact、导出/删除发行版、重建磁盘或修改系统配置。155 GiB 宿主分配不能减去 804 GiB guest 可用得出可回收量；guest 总容量约1 TiB，宿主未实际分配全部容量。guest used约152 GiB，与VHDX约155 GiB接近，当前没有证据支持巨大空洞；可回收上界不精确，粗略量级仅数 GiB，需单独授权离线评估/compact，实际可能更少且要考虑 ext4 元数据与碎片。

## 研究包占用排序（清理前）

| Linux 包 | 文件数 | 文件逻辑 GiB | 唯一文件分配 GiB |
| --- | --- | --- | --- |
| direction-prior-value-v1 | 8622 | 15.516 | 15.534 |
| b_native_learning_matrix_v1 | 4450 | 5.669 | 5.679 |
| b_native_q_realtime_integration_v1 | 20644 | 4.071 | 4.117 |
| b_fast_runtime_completion_v1 | 4641 | 4.104 | 4.114 |
| b_hold_return_critical_path_v1 | 2643 | 2.025 | 2.031 |
| m2_coordination_space_exploration_v1 | 2147 | 1.527 | 1.531 |
| b_multirate_realtime_v1 | 1849 | 0.928 | 0.932 |
| b_fast_jitter_m2_host_v1 | 1904 | 0.895 | 0.899 |
| m2_matched_bidirectional_exploration_v1 | 1658 | 0.696 | 0.699 |
| m2_host_generalization_attribution_v1 | 1649 | 0.516 | 0.520 |
| m2_motion_counterfactual_ranking_v1 | 289 | 0.461 | 0.462 |
| m2_neural_q_motion_v1 | 71 | 0.251 | 0.251 |
| b_runtime_qualification_decoupling_v1 | 1460 | 0.231 | 0.235 |
| lab-human-adaptation-contrast-v1 | 644 | 0.082 | 0.083 |
| commissioning-to-recovery-geometry-compatibility-v1 | 241 | 0.017 | 0.017 |
| human-size-contrast-v1 | 172 | 0.011 | 0.012 |
| human-side-studies-closeout-v1 | 25 | 0.001 | 0.001 |

目录块和链接块在目录总量单独计入，因此包文件分配列之和与 du 目录总量存在小差值。重复内容仍实际占用不同 inode；只有硬链接/挂载别名不能重复计实际占用。

| 类别 | Linux side 逻辑/分配 GiB | Windows 逻辑/分配 GiB | 本轮 Windows 删除 MiB |
| --- | --- | --- | --- |
| raw_trace | 28.558/28.562 | 2.428/2.428 | 2382.39 |
| json | 7.405/7.439 | 2.409/2.422 | 1636.56 |
| array_data | 0.644/0.646 | 0.548/0.548 | 560.19 |
| source_script | 0.200/0.264 | 0.064/0.076 | 0.00 |
| other | 0.139/0.140 | 0.036/0.037 | 0.00 |
| python_cache | 0.018/0.026 | 0.002/0.002 | 2.19 |
| model_weights_or_model_candidate | 0.017/0.017 | 0.005/0.005 | 0.00 |
| archive | 0.013/0.013 | 0.000/0.000 | 0.00 |
| compiled | 0.003/0.003 | 0.001/0.001 | 0.00 |
| image_animation_pdf | 0.003/0.003 | 0.011/0.011 | 0.00 |
| log | 0.000/0.003 | 0.001/0.001 | 0.00 |
| report_markdown | 0.001/0.001 | 0.001/0.001 | 0.00 |
| csv | 0.000/0.000 | 0.005/0.005 | 0.00 |

分类仅用于盘点。array_data 包括 NPZ/NPY/MAT；raw_trace 包括 trace 和 runtime_artifacts，优先于扩展名；model_weights_or_model_candidate 还包含某些模型相关序列化候选，不能把该分类文件数都视为神经权重数。没有因扩展名、年龄或大小自动删除。

| 最大的原始文件（Linux side） | 逻辑 MiB | 保留判断 |
| --- | --- | --- |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_train_0_RETURN_1_SNAPSHOT.json | 284.31 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_dev_0_RETURN_1_SNAPSHOT.json | 254.02 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_train_0_OUTBOUND_4_SNAPSHOT.json | 202.69 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_dev_0_OUTBOUND_4_SNAPSHOT.json | 182.57 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_train_0_OUTBOUND_2_SNAPSHOT.json | 166.20 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_dev_0_OUTBOUND_2_SNAPSHOT.json | 150.26 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/parent_train_0_OUTBOUND_0_SNAPSHOT.json | 125.86 | PROTECTED：父状态/fork 科学快照，不报告化删除 |
| /home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/output/branch_smoke_OUTBOUND_0_SNAPSHOT.json | 125.86 | PROTECTED：父状态/fork 科学快照，不报告化删除 |

## 实际清理

| 平台/类别 | 文件数 | 逻辑 MiB | 分配 MiB |
| --- | --- | --- | --- |
| windows/json | 322 | 1635.98 | 1636.56 |
| windows/array_data | 275 | 559.67 | 560.19 |
| windows/raw_trace | 144 | 2382.14 | 2382.39 |
| linux/python_cache | 3432 | 18.77 | 26.07 |
| windows/python_cache | 177 | 1.84 | 2.19 |

| Windows 被精简包 | 删除文件数 | 之前逻辑 MiB | 之后逻辑 MiB | 实际分配释放 MiB |
| --- | --- | --- | --- | --- |
| m2_coordination_space_exploration_v1 | 159 | 1563.31 | 78.55 | 1485.05 |
| b_multirate_realtime_v1 | 126 | 948.85 | 40.88 | 908.20 |
| m2_matched_bidirectional_exploration_v1 | 102 | 712.73 | 35.66 | 677.25 |
| m2_host_generalization_attribution_v1 | 57 | 528.96 | 44.39 | 484.67 |
| m2_motion_counterfactual_ranking_v1 | 165 | 472.27 | 16.91 | 455.66 |
| m2_neural_q_motion_v1 | 30 | 256.64 | 1.21 | 255.49 |
| b_native_q_realtime_integration_v1 | 95 | 269.97 | 37.69 | 232.46 |
| b_fast_jitter_m2_host_v1 | 13 | 95.56 | 20.05 | 75.55 |
| b_runtime_qualification_decoupling_v1 | 2 | 7.16 | 3.84 | 3.32 |

严格 REPORT-only 实验包：**0**。旧科学报告和失败结果仍保留，Windows 变为报告/代码/模型/紧凑证据优先的瘦副本；Linux raw 均保留。没有将当前 Frozen M2、Neural Q 来源、Motion/counterfactual、coordination-space 或完整 matched-state fork 的唯一证据改为不可复核报告。对不能证明无价值的失败 attempts 不自动删。

Windows 删除前每个数据文件都核验当前目标路径、祖先 reparse 标志、文件 ID、mtime/大小、Linux canonical 真实可访问和双侧 SHA256。每个缓存都要求原 `.py` 源码存在且哈希不变；sourceless、硬链接或非标准 bytecode 未入清单。只 unlink 明确文件，不递归删目录、不删整包、不移动到同盘回收区。原有历史 Windows self-relative output 包（如 expert-strength、action-representation）保留输入，不能把所有 Windows 目录都认作纯镜像。

Windows 11 份 Markdown 只更新存储说明/链接，8 个附件链接重定向 canonical，均可访问。Linux 原 REPORT 字节不变，科学配置、分母、数字、失败原因和资格结论不改。旧 full-export DELIVERY_MANIFEST 验证需要重新导出完整镜像；这项可用性变化明确披露，不能再声称当前 Windows 瘦副本具备全量独立复核能力。

## 重复与保护核验

全部14967个 Windows 文件做 SHA256；14,065 个文件 / 5.212 GiB 找到 Linux 一致 counterpart。902 个 / 306.22 MiB 未匹配，全部保留。已计算的 Linux 哈希中有 1,967 组相同内容；Windows 内有 1,742 组，其中历史清理 manifest 有重复副本。既有来源代码/权重重复及历史归档凭证保留；没有凭哈希相同就删去被引用的 Linux 路径。完整研究目录并非逐目录全量相同，因此不整目录删除。

保护复核：33302 个明确保护文件 SHA256 全部不变；49677 个 retained side 文件的 inode/dev/mtime/大小未变；2575条已有 symlink 目标不变且可访问。Windows 保留 14049 个文件全量 SHA256 验证，6467个源码/脚本/二进制不变，仅允许11个存储说明修改；918个删除项确认不存在。唯一科学 raw 未丢失；无需仿真或重新训练核验。

| Git | branch | HEAD | 原状态/最终 |
| --- | --- | --- | --- |
| /home/hank/coding/adaptive-traction-mpc-learning | codex/expert-strength-value-adequacy-v1 | 41cdddef117caa4b191a52129c4ff83e481fd5a8 | 2288条状态记录；index/status/staged diff/refs/worktrees 完全一致 |
| /home/hank/coding/adaptive-traction-mpc-human-closeout-git | codex/lab-human-adaptation-r2-closeout | 4246c4ea9edb74866ca0ae5946599be913486676 | 0条状态记录；index/status/staged diff/refs/worktrees 完全一致 |
| /home/hank/orca/workspaces/adaptive-traction-mpc-learning/codex-direct-rl-expert-v1 | codex/direct-rl-expert-v1 | 41cdddef117caa4b191a52129c4ff83e481fd5a8 | 0条状态记录；index/status/staged diff/refs/worktrees 完全一致 |

主项目原暂存 diff 为44830557 bytes、SHA256 `3ae02237deadca6c8833cedf8eb4cef59f2933ac471d445b88ac01d0472e2461`；index SHA256 `1bc691b825d8bf3b528ce84dd0384fbbd1b84aace4e45156094b6b60c64208d5`，status SHA256 `cf32a7ccf8e7f2cc2df5f6d6cd1ae72fd249730cb028f8b85ba7348e561581dc`。均未变化，没有 stage/commit/push/reset/stash/branch 切换。重要权重与 canonical 见 PROTECTED_FILES.md；逐文件真实路径、SHA256、原因、影响和保留位置见 DELETION_MANIFEST.json。

## 仍占用的内容、下一步与 STOP

按实际占用排序的保护/待审项目见 REMAINING_CANDIDATES.md。主要是主仓库、direction-prior-value、冻结Q标签来源、历史B执行/回归证据及唯一Windows输入。旧发行版/Docker/Conda/系统目录/D盘归档未清理。任何下一步整包/权重/核心数据/唯一raw删除或离线VHDX compact需要用户另外授权，本轮不自动扩大范围。

没有新仿真、训练、物理实验、Git写操作或系统设置修改。没有终止无关进程；审计/哈希/删除进程均正常结束，无研究遗留worker。清理记录 canonical只保留 CLEANUP_REPORT.md、DELETION_MANIFEST.json、PROTECTED_FILES.md、REMAINING_CANDIDATES.md；Windows只同步CLEANUP_REPORT.md供查看。完成后STOP。

最终交付复查：2026-10-09 04:01:52 Asia/Shanghai；40个本轮临时盘点/哈希/脚本文件已永久移除，未动其他可视化资料；本轮遗留进程0。C/D、Windows RAM及pagefile表已更新到临时文件移除后快照。保守预算起点03:25，完成低于90分钟硬上限。
