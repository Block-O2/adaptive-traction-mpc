# iHEAR Lab — Full Repository Deep Cleanup v2

**实际文件清理已完成，保护与轻量数值读取核验通过。** 删除1,381个明确历史文件，释放45.516453 GiB分配空间；三处Git状态与保护hash不变。20个历史研究范围完成部分REPORT_ONLY（main14、side6，其中1个为嵌套audit）；整包仅余报告的数量0。本轮没有删除整包、没有新D迁移、没有新实验/训练/控制器修改。

## 空间实测

Windows before：2026-10-09T16:37:59.3267886+08:00；after：2026-10-09T17:24:21.7057117+08:00。Linux before为dry-run冻结后的statvfs，after为删除及保护验证后的statvfs；不同时间点的背景写入会影响净变化。

| 指标 | 前 GiB | 后 GiB | 变化 GiB |
|---|---:|---:|---:|
| C可用 | 8.169014 | 8.085831 | -0.083183 |
| D可用 | 234.638580 | 234.638451 | -0.000130 |
| WSL ext4 available | 803.817924 | 849.329578 | 45.511654 |
| WSL ext4已用（total-free） | 151.820385 | 106.308731 | -45.511654 |
| VHDX NTFS实际分配 | 155.322266 | 155.322266 | 0.000000 |
| VHDX逻辑长度 | 155.322266 | 155.322266 | 0.000000 |
| main路径实际分配（WSL lstat口径） | 74.451256 | 43.871994 | -30.579262 |
| side路径实际分配（WSL lstat口径） | 37.108612 | 22.176617 | -14.931995 |
| windows路径实际分配（WSL lstat口径） | 1.063881 | 1.064346 | 0.000465 |

明确删除的逻辑大小：45.513801 GiB；已分配块释放：45.516453 GiB。主库与side目录净减少略有报告/元数据开销；最终Markdown及JSON封存的增加不等于误删。Windows研究文件删除0；NTFS API聚合数据见PACKAGE_VERIFICATION的host snapshot。

**C盘净可用变化为 -0.083183 GiB，不能把45.52 GiB Linux文件删除计为C盘已恢复。VHDX实际分配变化 0.000000 GiB。** 本轮没有shut down/compact/trim/export/import或迁移发行版；WSL中的空块仍在原VHDX文件内。D可用变化来自采样区间背景活动，本轮迁移/删除D内容均为0。

## RAM、swap与执行边界

| 指标 | 前 GiB | 后 GiB |
|---|---:|---:|
| Windows available RAM | 2.442245 | 4.107018 |
| WSL MemAvailable | 6.651390 | 6.897781 |
| WSL swap used | 0.014904 | 0.015148 |

RAM/swap/pagefile配置未改变；Windows pagefile用量原始MiB字段保存在JSON。只做文件hash、摘要解析、NPZ读取和静态检查，无物理任务、Q训练、B修复、全局电源/调度设置改变或无关进程终止。

## 审计与删除依据

先读取v1报告/清单/保护与候选，但重新按当前Neural Q、B及协调研究依赖分类。三根目录全量lstat盘点、按inode去重，检查2,575个有效软链接及hardlink；main tracked/untracked/ignored分别审计。交叉检索17,860份文本/引用文件及32条训练来源schema。没有把未知文件默认当垃圾。

最大的安全清理来自best_known搜索、旧SAC/DAgger/evidence诊断、direction prior与旧B runtime包。每包原科学报告保持；main14个范围先生成完整带来源REPORT，20个范围先写STORAGE_RETENTION_V2补充，核对摘要分母、单位、失败与保留原件，再冻结manifest。清单SHA见DELETION_MANIFEST；每个文件先验证身份/hash、realpath、无打开使用、无链接别名、单hardlink及Git忽略，再用具体parent dirfd + basename unlink。20批后均复核三处Git基线相同。没有通配递归删除。

## 科学snapshot分类

删掉direction-prior中9个113–284 MiB历史SNAPSHOT：每个逐类解析branch_kind、native count/mask、interface/candidates/counts/labels、state hash与opaque例子，写进manifest后删除。它们声明Linux fork complete address-space / process-scoped only；包含数组/原生积分hash和不可重建锁/handle，需要原存活地址空间，不是可独立恢复checkpoint。已结束父进程下不能靠JSON重建完整状态。保留代表expanded regression、全部streaming/v3小manifest、fork_core实现、DATA训练标签、目前live-state replay与所有durable `.pkl.z`/061/062输入。main配套大型manifest并未按同一逻辑删除。

## 保护、数值与能力损失

全部当前B/native/safety/harness源码与环境、冻结权重、Neural Q数据、密集标签来源、近期M2非零原生执行及matched科学fork保留。93,261个原文件元数据相同，50,448个保护文件SHA相同，2,575个链接可用，三处branch/HEAD/status/index/staged diff/untracked/worktrees/refs完全一致，错误0。原报告hash未变。4个当前NPZ CRC/有限值读取通过。621个最优搜索attempt仍有539 VALID、80 INFEASIBLE、1 INVALID、1 INTERRUPTED；10个winner从保留TASK trace重算N·s，与header和原comparison table误差均0。

独立读取核验不等于重做实验或独立科研复验。第一次轻量数值checker误把rep路径固定为rep_01；已有winner实际为rep_02，修正为发现唯一retained rep trace后全部通过；未修改研究结果。此检查失误记录在PACKAGE_VERIFICATION.numeric_read_verification。

删除后，已删histories的逐native步轨迹、全部receipt、dense衍生量与旧process树的完整法证展开不能逐步复算；sampled task积分、摘要、配置、原结论和关键对照仍可审核。某些旧post-hoc raw消费者需要独立归档恢复或新授权run。历史FULL_PACKAGE_MANIFEST是当时记录，不能再宣称完整镜像验证。旧失败、科学分母/资格门槛、负结果、权重版本均不重写。

## 未清理范围与分类

116个候选因缺完整summary/trace/config或被近期harness引用而排除。当前dense标签、唯一durable states、配套manifest、Git受保护文件、Windows独有review、小型尚未逐包认证历史目录均原位保留；详见REVIEW_REQUIRED。所有目录已完成空间与文件盘点，但没有声称全部历史包已完成深层科学语义认证。REPORT_ONLY是部分文件范围，源实现与关键证据保留；ACTIVE/KEY_EVIDENCE见保护表；ARCHIVE_D仅记录既有7个归档；直接DELETE研究文件0（本轮1381个全部在REPORT_ONLY）；本任务临时账本另按明确归属清理。

## VHDX只读可行性与需另行授权的方案

现VHDX为常规Archive文件，未启用Sparse/Compressed；宿主未发现Optimize-VHD/Mount-VHD cmdlet。D有足够空间容纳当前约155.32 GiB VHDX备份，但这不证明一份磁盘文件在线复制一致。本轮不自动执行任何离线操作。

后续单独授权后：确认所有WSL研究/编辑会话停止且保存；确认D实时余量和备份目标新空路径；有序关闭WSL，使VHDX离线；复制完整VHDX到D独立备份，核对size/SHA256/可读性并保留发行版注册与恢复信息；然后使用当前宿主受支持的离线compact工具对正确VHDX回收，完成后启动验证发行版、文件与关键权重。若需trim，必须作为独立方案明确授权并评估工具；不能在活跃发行版下直接attach/compact。遇工具不可用就保留备份/源，不改注册、不unregister、不重建、不做自动迁移。真正C盘可回收量须以offline回收后的NTFS/volume实测为准，不保证等于本轮删文件大小。

## 后续默认轻量存储规范

- 核心源码、冻结权重、必要训练集/合法标签来源和durable恢复合同长期保留。
- 正式有效实验保留科学报告、START/END及有效分母、compact指标/config/version、基线/最优/独立确认/安全失败最小原证。
- 探索失败先报告化，记录问题、方法、控制、单位、安全、失败原因、独立验证和局限；完成依赖审计及冻结精确清单后清理冗余raw。
- Dense标签来源在证明下游可复用替代前保留；process-scoped hash不能伪称durable checkpoint。
- 默认不建Windows全镜像，仅留报告/审查入口；冷归档用D新目录且hash/read验证后才处理源，避免把symlink当独立副本。
- 不为形式可追溯永久保存每个attempt所有重复产物；同时不可删除当前数据、负结果分母或唯一证据。上述为政策建议，本轮不改控制器/研究框架。

## 交付与停止

canonical目录仅含要求的7个文件；包内新增REPORT/存储补充均为轻量Markdown。统一入口RESEARCH_ARCHIVE_INDEX，精确永久删除依据DELETION_MANIFEST，保护/读取证据PACKAGE_VERIFICATION。本轮自身临时SQLite/依赖列表/脚本在完成封存后按明确文件清除，不留大临时清单；没有新的调度或自动续研究。完成终态核验后STOP。

最终封存补充：删除本任务约0.13 GiB暂存账本（最大为约80 MiB的引用检索结果及约52 MiB SQLite；均为本轮自行产生，未计入1381个研究文件）。最终C/D采样在大账本移除后；Windows仅新增5份轻量Markdown审查副本，没有完整数据镜像。最终目录数字含报告封存，JSON最后少量元数据写入使末位块数可能变化。已核对冻结计划可从完成清单重建同一SHA，main新REPORT包含原报告全文，原报告与补充hash不变；未观察到遗留研究worker或旧清理helper。总墙钟约1小时，3小时上限内完成后STOP。
