# A2：实际覆盖与原资格风险分头（待主 Agent 审预算）

状态 `DATA_PREPARED_SOURCE_ONLY_TRAINING_NOT_APPROVED`。不修改 A1 bundle、API、旧结果、正式 controller/scorer/阈值；本轮新物理为 0。唯一激活沿用 `deep_learning_method_exploration_v8_20261027T032540Z`，硬截止 `2026-10-27T15:25:40Z`，不能重置。

## 可证伪的问题与明确边界

A1 在已冻结 CTX03 选择 phase，但完整任务因原 `jerk_deg_s3/rms` 门失败。A2 检验增加真实动作覆盖后，**原资格风险头**能否修正这种选择；同时检验收益是否可以被相同历史权限的固定动作、单层 if、最近 context 规则解释。改变的是离线开发覆盖，不是原运动资格，不能把完整但失败的低 JF 写成成功。

四 CTX 已暴露，全部改列开发。CTX01 四个非 B 因 excursion 失败，CTX02 EARLY_PHASE 因 velocity max 失败，CTX03 两个 phase 因 jerk rms 失败，CTX04 全合格；这些观察用于提出机制，不能再作 A2 独立 test。两个后续插值 validation 条件保持 sealed，主 Agent 应在打开其任何结果前冻结 A2 的所有 checkpoint/API/strong rules/预测规则。

## 实际数据身份

`data/ACTUAL_COVERAGE_DATASET_V1.json` SHA256 `e7a54dd7d3d39f0ab94cec45ceea284d6efec51d186ab74e46ff2335e82b79e0`。

旧 V2（SHA `ea35953cf6e8775a7331a80febf1219b2d2d047677fb2cc57db6e8baf0773ed5`）实际兼容五 recipe 完整行 28，加四 CTX 的完整唯一五 recipe 20 行，共 48 行、10 个 context、原资格合格 31 行/失败 17 行。B、LATE_H150、EARLY_H150 各 10 条，LATE_PHASE、EARLY_PHASE 各 9 条。旧 EARLYH 缺两个精确 phase recipe，保持缺失；未用其它 tag/recipe 补标签。17 个旧异 recipe/无兼容行排除；HISTORY_B 和冷 parent 不进入训练。

五 recipe 来自 A1 已冻结菜单，完整 action JSON、resolved base candidate、18D、terminal repair/modal/retimed/参数映射 SHA 逐值一致。四个 WORKER_DONE、supervisor STOP/exit0/survivors[]、EXIT 全先验关闭后才打开其结果。结果保持原完整 JF/JM、motion 原门及失败项，完整失败仍可训练独立成本头，成功排名只允许原完整合格。

输入只允许现已审 OUT0 commissioning25 及 QA 完整性证明：前 11 个 estimated beta，4 个 estimated geometry，10 个 residual weight。25D 模型用全部数值；15D 仅前 15 个；action-only 不用 context 数值。QA33 保存在 context，但本轮不作为额外可调 actor 特征。不能输入 case、真参数、插值坐标、parent/group/hash、当前完整资格、未来 JF/JM、已知最优动作。真实 parent hash 仅作整组切分/去重。原77D仍无效，不补缺失运动历史。

每 row 的训练前可见字段为 `context.feature_names/features/quality/checks` 和完整 `action_recipe`；`labels_evaluation_only` 包含 JF_N_s、JM_Nm_s、delta_JF_vs_B_N_s、delta_JM_vs_B_Nm_s、complete、original_qualified、motion_worst_ratio/failed_requirements、原 axes/phase 等；`identity_evaluation_only/parent_evaluation_only/split_parent_group_evaluation_only` 仅作数据审计和分组。模型设计只用确定的 context 数值与固定 action one-hot/交互，不让评价元数据进入设计矩阵。

## 机制与切分

两个数据 cohort 使用相同新 source：`OLD_ONLY`（旧 28 行）与 `MERGED`（48 行）。不是把重新拟合的 OLD_ONLY 改称原 A1 冻结物；A1 物理结论和成本原样保留。

每个训练集拟合三个表示（25/15/0D），分别有：绝对 JF、绝对 JM；相对同 context 完整 B 的 ΔJF、ΔJM；原资格失败的独立 logistic risk。成本采用 A1 的 action×context ridge、固定 λ=.1/1/10，两个分量独立标准化和输出，不混成标量。risk λ=.3，阈值 .5 固定，risk ON/OFF 消融不重拟合成本。spread 仅是三个 ridge λ 的敏感性，不能称校准置信区间。该全任务一步结构是监督 episode value/cost，不冒充 multi-step TD/Q/RL。

整 parent/context LOCO：10 个实际父状态块，每次全部移除 heldout 父的所有动作；OLD_ONLY 对新 CTX 的开发预测只从旧六 context 拟合。normalization 与 target scale 每 fold 仅用训练数据。同训练行集合缓存一次，不因四个新 heldout 的 OLD_ONLY 完全相同而重复拟合。真实父 recipe 重复去重为 0 个，25D exact alias 为 0 个；这些哈希不能证明患者 IID，近似相同输入或缺失状态仍可能导致原资格不可辨识。

强对照从同 cohort 的真实训练反馈独立构造 CONSTANT_B、BEST_FIXED、单层 IF_STUMP、NEAREST，并对 JF_QUALIFIED、JM_QUALIFIED、STRICT_JM 分别固定评价标准。训练规则可用训练结果；部署不看当前结果，不把当前资格作 mask。缺失反事实在训练规则评分中记 unsupported，LOCO 若选到缺失动作记录 UNKNOWN，不偷偷改选已知合格动作。

主分析预指定 `MERGED/ABS_25/RISK_ON/JF_QUALIFIED`，不以本轮 LOCO 挑 best。其余 ABS/DELTA×25/15/0、risk ON/OFF 全保留。JM 单目标和 STRICT_JM 独立呈现；现菜单“非 B 的 JM 代价”不被新的 JF 目标覆盖。support≥2 个训练 context、标准化 RMS 距离≤3，均沿 A1 固定；predictive abstain 可回退 B，并单列回退，但 B 仍需原完整资格，不补授未来资格。

## 拟合资源与审批入口

拟申请一次前台、单 CPU、wall ≤180s、地址空间硬上限 1GiB、0新物理/0 native step、无后台任务。固定唯一输出 `fit_run_v1/`，存在即拒绝重启，原硬截止优先；内部留 5s 审计。BLAS/OMP/MKL 各 1 线程。仅使用已存在 offline-env（numpy2.2.6/scipy1.15.3）；不安装依赖。

按当前 10 个 parent 块与缓存，预计 18 个唯一训练行集合（旧七集合，合并十一集合），三个表示共 54 次 risk logistic；324 次 ridge 二 RHS 求解（648 个独立标量输出头）；54 组 objective-specific stump 搜索。保守上界不依缓存为 66 次 risk、396 次二 RHS ridge。LOCO 720 次模型 predict +240 次 control predict=960 次；这些均为获批后的真实离线模型运算，必须计账。当前这些调用全部尚未运行。

记录 PID/start_ticks、唯一 start/local/global 时钟、每次 risk 迭代/nfev/njev 与每个 ridge 求解、预测次数、wall/user/system CPU/RSS/依赖版本及异常。异常保留 owner/fit账，不自动重试，不写成功 checkpoint。输出 bundle、LOCO 原逐条 prediction/真实评价、资源账；不选择 best checkpoint、不产生新物理、不声称省试。

训练必须等主 Agent 另行明确批准。入口要求独立批准 JSON：`status=APPROVED_BY_MAIN_AGENT`，精确绑定 contract/data/source-manifest SHA；未批准之前不执行 run_training_candidate、model、predict。最终合同和源 manifest 的具体 SHA 见同目录 JSON。

## API 与尚未运行的核验

`source/causal_api.py:to_context25(raw_or_scoped)` 只做已审因果数值转换。`source/predict_api.py:predict(bundle, causal_context, method='ABS_25', objective='JF_QUALIFIED', risk_mode='ON', cohort='MERGED')` 返回五动作独立成本、risk/support、choice_tag/完整 recipe SHA/action；不接受数据行标签或当前B结果。`predict_control` 返回同权限冻结传统选择。

候选 source 仅做 AST 语法检查，A2 数学拟合/API forward 尚 `NOT_RUN`。真实拟合获批后，需先核对 shape/finite、纯 API 与保存 bundle 的再现；不能把 A1 已审实现的信用直接转成新代码全部动态通过。学习家族仍 `NOT_FULLY_EXPLORED`，模型有效性须以原门、强传统与后续封存验证分别报告。
