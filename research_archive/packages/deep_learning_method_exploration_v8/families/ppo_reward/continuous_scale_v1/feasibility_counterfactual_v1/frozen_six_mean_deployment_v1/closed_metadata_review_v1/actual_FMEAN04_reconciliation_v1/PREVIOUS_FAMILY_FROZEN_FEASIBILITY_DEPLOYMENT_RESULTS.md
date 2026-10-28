FMEAN03 的六个冻结 feasibility 模型已在原 cold OUT0、B 前各真实返回一次 mean；均无数值拒绝。原 B 完整合格，原 EARLY_H150 为工程 partial，因此 λ1 repeat 与六个模型 TASK 均未执行。该记录既不把 NOT_RUN 当模型失败，也不授予控制收益或泛化结论。

|原证据|状态/实际计数|
|---|---|
|六模型选择|6 logical copies、6 mean entered/returned、6 internal forwards、0 数值拒绝；七角色 proof、causal39、25D projection 各1，fixed λ1 map1|
|原 B|complete+qualified；JF 1587.100832423440 N·s，JM 109.908685005448 N·m·s；76,120 新 native steps；原 hard violation=false|
|原 EARLY_H150|complete=false；NATIVE_PHYSICAL_FAILURE；69,300 新 native steps；JF/JM 保持 null；原 hard violation=false|
|λ1 repeat / raw gate|NOT_RUN / 无 gate，不能补 PASS|
|六模型 TASK|六项均 NOT_RUN，原 alias 指向 MEAN_01..06；不是六次控制失败|
|原物理投入|2 个独立 child proposals；parent END 116,320 steps 单列；child END 未给 steps，采用原 receipt 的逐 child steps，不补0或编造总量|

Global RF/PPO、context LOO RF/PPO、span geometry RF/PPO 全部保留，policy/weights 身份见原报告。只有原 pre-B 调用已有6次 forward；本次与 V2 metadata 核查均为0新模型/训练/物理，不得重复记成新的6次推理。原冻结源、模型、配置与 clock 均未改变。

原 V2 核查 START 为 2026-10-27T12:13:07.728577+00:00，实际 Python PID 1227712/startticks 63085925。main 的 outer child 1227710/start63085925 与 launcher1227709/start63085922 分列；三者当前均已退出。core wall 0.035767794s / CPU 0.035764s / peak RSS 20856KiB；main 报告外层 wall .07810s / inclusive-child CPU .07763s，不能混成 core 资源。原核查计数17 JSON、6 event JSON、158 hashes、6 policy digests、6 weight digests、2 receipt checks。

V1 的预算拒绝保留在 `audit/ROOT_PREFLIGHT_ERRORS_1214_PRESERVED_V1.json`，SHA `add0d858e153fdc84d11b5bc49b70c1ec5fb16a4c1c9ca6472ff19acc198bbf8`；该文件实际 recorded_unix=1793102928.4834003，不用文件名历史时间标签推断时间。原V1 authority/external refs和exit1保留；它在输出前拒绝，0模型/物理。V2按新主批准一次完成，修正原 END 无group的schema关联，没有放宽预算或物理guard。

原 REPORT SHA `e73f04fef59d982c5e55b2bc0e0d93e3e84f21f9b812768cc6232bdbf725c115`，DONE SHA `02eb5e5d62bcfb4805c00e4e500ad568933c4b9791686c58bf87af5d031d977f`。未读取活动 VAL04、原raw/scorer或real_runs。DevCap仍为未运行source提案，等待mandatory six闭合及独立root授权，不因本次结果调网格、模型或阈值。

完整metadata reconciliation：`families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/actual_FMEAN03_reconciliation_v1/REPORT.json`。
