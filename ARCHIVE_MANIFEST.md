# 归档清单与依赖边界

本分支基于原远端研究提交 `1adb1de177d6f5f32de6d01c4e629cbfae9ce121`，保留原 Git 历史、Stage3/4/5控制与模型资产、重要更早研究源码和证据。新的独立分支为 `archive/research-closure-20261028`；最终远端commit与可访问性以 [FINAL_HANDOFF.md](FINAL_HANDOFF.md) 为准。未合并、未force push、未reset/clean、未改仓库可见性。顶层原README另保留于 [历史副本](research_archive/historical/README_before_closure.md)。

## 三层保留对象

|层|实际保存|可恢复范围|
|---|---|---|
|既有Git源码与资产|`stages/`、`research/side_studies/`、`research/rl_b_cpu_handoff_v1/`、既有deployment工具及历史证据|保留原对象，避免重复上传；原B/H150 D01R full raw与原scorer继续可读|
|新增版本化包|17个原包中的实际源码、完整模型/mesh/XML依赖、参数/动作/任务合同、训练wrapper和代表结果|代码/小配置按原路径选取；不是17个完整实验目录备份|
|综合知识与验收|14份主Markdown、原数据PNG/SVG/PDF/CSV、可移植运行/核验工具、逐文件hash与遗漏清单|供搭建、检查、分析与教授讨论；所有新增研究假设与历史实验证据分开|

新增选定原文件当前为 **23,756 项 / 1,214,474,476 bytes**（以机器清单为精确值）。复用快照中的相同文件与已有对象由Git内容寻址去重，不为缩小文件数而删除安全底座。机器清单 [selected_files.json](research_archive/manifests/selected_files.json) 记录source相对路径、归档路径、bytes、SHA256和角色；`research_archive/packages/** -text` 保证包括旧CSV换行在内的字节身份。文件可执行权限沿原副本保留，运行示例均显式调用Python/bash。

## 传统控制优先保留

原B为V=0、因果测量/commissioned belief到估计Human状态、有限候选waypoint MPC、quintic scheduler/governor、certificate/current-state admission、FAST feedback/allocator和robot-cuff-Human接触动力学的完整闭包。40ms bridge、100ms lifecycle、版本/phase/source age、rolling/replan、carry/brake/fallback、guard、native ownership与原任务/评分保留。源码不是仅提取上层优化脚本。

保留H150/T/D、18D与旧10D适用边界、fixed phase、HANDOFF、PATTERN、COMPOSE、bounded/anticipatory及其负结果；具体参数、调用关系与资格条件见 [TRADITIONAL_CONTROL.md](TRADITIONAL_CONTROL.md)、[传统选择清单](research_archive/manifests/TRADITIONAL_SOURCE_SELECTION.json)。主要动态复现入口为 `deployment/reproduce_trad_combo.py`，D01R B/H150为 `deployment/reproduce_traditional.py`；每个新运行只复制并重定位源码、更新机械执行时限及生成真实hash，不更改plant、控制参数、任务、原motion或安全阈值。

## Learning知识与代表接口

保留更早及v1–v8的真实训练/预测/提案代码，特别是早期包根目录41D PPO wrapper、modal PPO、GP/BO、Critic/Value/Q、ILC、BC、OUT0 context aggregation/DAgger局限、终末SAC、时间域模型等。保留真实已训练JSON Value checkpoint和v7GP/stump/v8 PPO代表性冻结权重；不假定模型一定是 `.pt`。

已训练Value接口依赖见 [Learning选择清单](research_archive/manifests/LEARNING_SOURCE_SELECTION.json)，实际原predict可在25D已保存训练context调用。它只是接口smoke，不能当作未见患者验证或真实控制增量。[LEARNING_METHODS_HISTORY.md](LEARNING_METHODS_HISTORY.md) 明确各家族训练和完整物理验证范围及未探索方向。

## 代表性证据与缺档

精确代表性证据清单为 [evidence_selection.json](evidence_selection.json)。它包括两条现代完整B/组合raw/scorer材料、8份完整native运动数组、传统及Learning代表图/表、少量已训练checkpoint。另有原Git D01R raw、历史Stage证据，已在对象中保留，无需另传zip。

本次生成图由真实数组重建，脚本为 [rebuild_archive_evidence.py](figures/rebuild_archive_evidence.py)，数据来源及合同见 [EXPERIMENTAL_EVIDENCE.md](EXPERIMENTAL_EVIDENCE.md)。有些历史报告引用的raw、checkpoint或绝对路径没有保留；保留报告不等于那些对象已归档。更早History/ILC/BO的 `history_models.npz`、`TRAINING_DATA.json` 等在这台机器/既有Git中本来缺失，不能补造。所有模型权重、Adam/RNG状态和每个历史运行不能完整恢复。

旧 `deployment/verify_repository.py` 对当前模型/源码身份可通过，但单独标记 **legacy Stage1 的40项模型文件引用缺失**；它们不是本轮现代Human/robot/cuff闭包依赖。旧工具中的 `BLOCKED_NO_PORTABLE_PARENT_CHECKPOINT` 指恢复历史活父状态；新入口是重新commission冷父并现场fork，不声称磁盘checkpoint恢复。这两种范围必须分开。

## 不上传对象与公开审查

不上传大规模raw、全部motion重复包、训练中间状态、zip整包、虚拟环境、缓存、主目录/编辑器文件、云/SSH/Git凭据和非必需用户原文。不制作整盘备份或Snapshot。 [omitted_research_assets.csv](research_archive/manifests/omitted_research_assets.csv) 与 [盘点汇总](research_archive/manifests/server_research_inventory_summary.json) 记录原具名研究包内未按该相对路径选取的资产；这不是文件独有性的证明，部分重复内容可能在既有Git别处。

公开凭据模式扫描覆盖当前Git树与新增payload，并对模型/二进制按路径、格式、用途审阅。一个旧公开导出脚本内的PEM标准header是扫描器字符串，已按精确源码SHA做单条误报审阅，见 [public_review_allowlist.json](research_archive/manifests/public_review_allowlist.json)。无未审阅高置信密钥发现不能保证穷尽全部历史敏感数据。

新树排除既有 `SAC_WORKTREE_BASELINE_PRIVATE.json` 和非必需用户原文，精确来源/理由见 [public_exclusions.json](research_archive/manifests/public_exclusions.json)。其中PRIVATE工作树状态及一个USER_REQUEST早已在旧公开提交中；本轮没有改写历史，无法撤回那些公开副本。原本地研究包没有因此删除或修改。未发现必须新建Private仓库才能保存的本轮科研源码或选中仿真数据；若以后要保留真实参与者、凭据或其他非公开资料，应另设受控存储，不能直接放入本公开分支。

## 身份、时间和最终验收

历史包各有原SOURCE/EXECUTION/OUTPUT manifest，描述原完整包而不一定只描述本次选取子集；不要要求这些全包manifest在稀疏归档副本中逐项都存在。本次机器清单才是上传范围的合同。文档中历史数值保持原实验身份/单位/合同；新运行另写scratch，不覆盖原证据。

本轮用户面向日期为Asia/Shanghai的2026-10-28，机器日志保留UTC时间戳与原unix值。干净clone的实际核验、未执行范围和失败修复记录见 [ARCHIVE_VERIFICATION.md](ARCHIVE_VERIFICATION.md)；删前风险和可能持续费用见 [DELETION_IMPACT.md](DELETION_IMPACT.md)。
