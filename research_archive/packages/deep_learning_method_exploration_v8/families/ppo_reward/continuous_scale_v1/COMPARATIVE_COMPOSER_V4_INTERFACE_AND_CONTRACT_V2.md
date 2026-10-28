# Comparative composer V4 V2 source candidate

仅新增私有 `comparative_composer_v4_candidate_v2.py`，入口仍为 `sequence(study, config)`。V1 全部 bytes、root V3、worker、Beta mean 和其它已冻结 API 均保留。此次只做文本、AST 和 SHA 校验，未 import 候选、调用 generator、初始化/restore 模型、forward、采样、训练或物理执行；未创建 actual config/inventory，未读实际 Beta run、活动 raw 或 sealed outcomes。

V2 把原 55 个 core pre-B selector 作为固定子集。`COMPARATIVE_ORIGINAL_55_CORE_LABELS_V1.json` 从已 closed 的 V8COMPENG03 配置标签，以及冻结 A3/A4/SAC6/SAC7 adapter 的 SELECTORS 字面量恢复：8+3+12+9+6+9+8=55。未读取任何预测或结果值。配置必须冻结此文件的精确 SHA。

新增 core 模型沿用 V3 的 `comparative_validation.parallel_selector_adapters`，不另造 hooks。每个 adapter 使用原 `predict_before_B(P, config, study)` 接口，V3 原有逻辑防止标签覆盖并核对实际五 recipe hash/tag/action。V4 只核对返回全集中原 55 标签全部存在、每个决策绑定真实五动作，以及 `len(decisions) == comparative_composer_v4.expected_core_pre_B_decision_count`。这个 required integer 至少 55，表示该次实际全部 core pre-B 逻辑决策数；不含 C-after-B、Beta 12 mean 或五个固定轴点。未来若主审单独批准并配置 Neural 的 68 个追加 selector，该数才是 123；Neural 的 63 次 forward 仍是独立的实际调用数。以后 E2 同样由既有接口追加，并在冻结配置中给精确总数。V2 明确拒绝 V1 的 `future_frozen_core_extensions` 字段。

时间顺序保持：V4 先 next 原 V3，让其完成全部配置的 core pre-B adapters、保存原决策记录并交出尚未执行的 B；此时 metrics 为空。V4 再运行独立冻结 Beta mean extension，核对同一实际合法 commissioned25，保存连续计划，最后才 yield 原 B。其后原 B、C5 after-B、条件 HISTORY_B、LATE_H150、EARLY_H150、LATE_PHASE、EARLY_PHASE 的相对顺序不变。V3 原记录不重写；wrapper/nested A/每个 extension_records 的真实计数在 V4 输出中保留，禁止把逻辑标签数冒充 forward 数。C5 仍是原三个 recipe 权限。

正常新增 Beta 工作仍为 extension entry/return 各 1；12 次纯 deploy_mean forward、12 份 policy copy、5 次 fixed map 和 mean 内 12 次 map，以及一次 A3 seven-role live proof、39 子集准备和 25 投影。parent/first-completed/last-actual-updated 四臂 checkpoint 必须由未来实际 immutable inventory 冻结，不选 best，不读 CURRENT/PENDING/sampling 动态状态。mean 只由冻结 policy 与本次 OUT0 合法25D决定，不能拼接未来真实 B 结果。原 B 不在轴上，λ0 不是 B/noop。

连续 schema 与 core5/C3 分开。原 core 流程后首先新付费执行 `BETA_AXIS_L100_REPEAT`，显式 `repeat_of=EARLY_H150`；必须在其余连续候选之前。EARLY_H150 只要求 complete 且原硬安全为 false，motion-qualified=false 仍能做 raw equivalence 与 Beta 评价。λ1 必须 complete、新原始 raw repeat 门 PASS、原 JF/JM/axes/qualified 与 H 相同，才允许其余 λ0/.25/.5/.75 与 mean 的真实 recipe。root 最终仍审核完整 parent/raw/scorer replay、activation、receipt、拒绝/fallback 和成本。H 或 λ1 partial 时连续余项 NOT_RUN；safe core PHASE partial 保留错误和实际步数后按原 V3 次序继续，其余 continuous partial 停剩余 continuous。任何 true hard 或 UNKNOWN 停所有后续；11 个原 hard_safety_conditions 全 true 才表示 violation=false，不补成功。

λ1 永不与原 H 静态 alias，每条各付费 START/END。其余冻结部署只按实际完整 recipe SHA 去重评价，父四 mean=.5 可 alias grid.5，但 12 次 mean forward 仍逐项计数。共享 core 或连续轨迹不算新独立 replication、不宣称省 attempt；训练新 rollout 永不去重。core5、C3 与连续轴的结果不能混成同权限排名。

owner PID 在 generator 入口锁定，所有 shared 写、legacy.next 与显式 legacy.close 只允许 owner。child GeneratorExit 静默退出且不写父 snapshot/error、不 close 父 generator。owner 取消或 worker repeat 异常保留最后 yield、原回执/事件/硬三值和已耗工作，partial/NOT_RUN 绝不补成功。

未来 root wrapper 仅导入这个新候选的 sequence；本次不创建 wrapper 或实际 job。未来配置保留全部 V3 配置、actions 原五条、history_snapshot、已审 sources/models/所有 dependencies，新增 `comparative_composer_v4.schema=v8.comparative_composer_v4_job.v2`，status=APPROVED_BY_MAIN_AGENT，no_training/no_outcome_reselection/root_postclosure_raw_and_scorer_review_required 全 true，exact expected_core_pre_B_decision_count，以及 pinned preserved_v3/beta_mean_extension refs。完整精确字段在 INTERFACE_SCHEMA_V2.json。候选自身、固定55文件和所有 runtime dependencies 均须列入实际 config.frozen_artifacts；actual source approval 与物理授权由 root 另审。

输出仍分为新的 V4_ALL_PRE_B_DECISIONS、各原 child V4_BRANCH、CONTINUOUS_MAPPING_GATE、V4_SELECTOR_EXECUTION_LINK 以及 owner/error 证据。pre-B 和 final schema 升为 v2，记录 exact actual/expected core 总数、固定55子集及原 V3 nested API 证据。SOURCE_MANIFEST_V2.json 绑定新增文件与未变依赖。无需 CLI 直接执行此 generator；静态审阅只用 AST/sha，实际 root worker 调用需另批。
