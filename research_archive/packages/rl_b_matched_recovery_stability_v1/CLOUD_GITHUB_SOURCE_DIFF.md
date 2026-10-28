# 云端与 GitHub 真实源码差异

240集/3-seed 的实际入口是 `rl_b_autonomous_replication_v1/replication_run.py`，不是 GitHub 封存 `train.py`。240条训练记录、51代 checkpoint 和各 RESUME/START 将它们绑定到实际源码；447项 FROZEN_CONTRACT 全部重新 SHA 通过，合同 `98d11513df9eaff3d13e4fe640916c47183e38fe3d4236947c860af18dda3372`。训练配置/seed/阶段来自该包 PPO_TRAINING_CONFIG 和 REPLICATION_PROTOCOL，不能用 GitHub 示例训练命令代替历史身份。

|范围|相同|云端修改|云端新增/同路径缺于GitHub|GitHub独有|
|---|---:|---:|---:|---:|
|414项科学/配置/模型闭包 vs GitHub sealed source|412|2|0|0|
|同414路径 vs GitHub active main|411|2|1|0（仅交集范围）|
|根目录 Python 包装代码|13|5|27|10|

414项包括161份Python、222 JSON、3XML、20OBJ、7STL和1份AGENTS。真正 Python 源码共216个对照路径：172相同、7修改（2科学+5包装）、27云端新增、10GitHub独有。云端参与对照的206份Python、GitHub封存189份Python；该数字不包括整个GitHub其他历史研究，也不把生成报告当训练源码。未发现当前447项中来源hash不明项；历史生成commit未知另列，不伪装已知。

两份科学修改：`activation_validation.py` 将原 HOLD-only超时优先检查扩展到 OUTBOUND/HOLD/RETURN；`runtime_sac_expert_v1.py` 只按实际拥有的native区间计force（拒绝前零时长零积分）、保留失败边界，并修复moment积分的边界范围。它们来自 cloud_v1→g4_repair_v1；其后 readiness→pilot→3-seed 的414项树hash一致。`rl_native_proposal.py` 已在 GitHub capsule，未在 active main 的对应位置，不能因“源码都在GitHub”就遗漏长期主树对接。

native_rl_env/ready_env/pure_rl_env、41D因果观测、两个native事件进度分数、planner/certificate/admission、governor/bridge/lifecycle以及全部模型/vendor均已逐字节对照；这些在 capsule 对照中相同，只有上述两份科学修复不同。根包装层5修改为 checkpoints.py、audit_reward_physical.py、independent_physics_audit.py、resource_guard.py、stream_json.py。云端新增 pilot_env 的v3失败cost floor、replication_run的单完整episode更新、原始rollout/真实Adam计数及冻结评价；这不是 GitHub 原train.py的默认rollout配置。

|文件|分类|精确 diff / 身份|
|---|---|---|
|audit_checkpoint.py|GITHUB_ONLY|逐文件 SHA 清单|
|audit_policy_change.py|CLOUD_ADDED|逐文件 SHA 清单|
|audit_reward_physical.py|CLOUD_MODIFIED|source_diff/wrapper__audit_reward_physical.py.diff|
|build_reports.py|CLOUD_ADDED|逐文件 SHA 清单|
|campaign_manager.py|CLOUD_ADDED|逐文件 SHA 清单|
|checkpoints.py|CLOUD_MODIFIED|source_diff/wrapper__checkpoints.py.diff|
|cloud_case_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|cloud_motion_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|evaluate.py|GITHUB_ONLY|逐文件 SHA 清单|
|force_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|freeze_protocol.py|CLOUD_ADDED|逐文件 SHA 清单|
|functional_smoke.py|CLOUD_ADDED|逐文件 SHA 清单|
|g4_natural_evidence_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|host_observer.py|CLOUD_ADDED|逐文件 SHA 清单|
|independent_physics_audit.py|CLOUD_MODIFIED|source_diff/wrapper__independent_physics_audit.py.diff|
|matched_evaluator_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|native_boundary_motion_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|package_campaign.py|CLOUD_ADDED|逐文件 SHA 清单|
|pilot_env.py|CLOUD_ADDED|逐文件 SHA 清单|
|preflight.py|GITHUB_ONLY|逐文件 SHA 清单|
|preflight_replication.py|CLOUD_ADDED|逐文件 SHA 清单|
|qualification_status.py|CLOUD_ADDED|逐文件 SHA 清单|
|qualify.py|GITHUB_ONLY|逐文件 SHA 清单|
|replication_analysis.py|CLOUD_ADDED|逐文件 SHA 清单|
|replication_run.py|CLOUD_ADDED|逐文件 SHA 清单|
|resource_guard.py|CLOUD_MODIFIED|source_diff/wrapper__resource_guard.py.diff|
|run_rollout.py|GITHUB_ONLY|逐文件 SHA 清单|
|smoke_sequence.py|GITHUB_ONLY|逐文件 SHA 清单|
|stage2_decision.py|CLOUD_ADDED|逐文件 SHA 清单|
|stage2_env.py|CLOUD_ADDED|逐文件 SHA 清单|
|stage2_manager.py|CLOUD_ADDED|逐文件 SHA 清单|
|stage2_report.py|CLOUD_ADDED|逐文件 SHA 清单|
|stream_json.py|CLOUD_MODIFIED|source_diff/wrapper__stream_json.py.diff|
|test_evaluation_semantics.py|CLOUD_ADDED|逐文件 SHA 清单|
|test_g4.py|GITHUB_ONLY|逐文件 SHA 清单|
|test_guard.py|GITHUB_ONLY|逐文件 SHA 清单|
|test_pilot_reward.py|CLOUD_ADDED|逐文件 SHA 清单|
|test_safety_authority.py|CLOUD_ADDED|逐文件 SHA 清单|
|timing_audit.py|CLOUD_ADDED|逐文件 SHA 清单|
|train.py|GITHUB_ONLY|逐文件 SHA 清单|
|verify_campaign.py|CLOUD_ADDED|逐文件 SHA 清单|
|verify_package.py|GITHUB_ONLY|逐文件 SHA 清单|

全路径SHA256、active-main对照和两版本精确diff见 `source_diff/FILE_SHA256_COMPARISON.csv/json`；五包的逐文件科学树、配置原文与28 vendor复核见 `CODE_LINEAGE_AND_CONFIG.json`；相邻包装代码的diff见 `source_diff/lineage__*.diff`。仅复制差异/隔离运行必要闭包；没有覆盖云端训练目录，没有把云端代码提交GitHub。

## 配置层的真实差异

|项目|GitHub sealed pilot模板|云端实际240集|
|---|---|---|
|rollout|固定64 native decisions/SB3收集|每完整episode，变量N，含N=1；替换初始化的128步buffer|
|batch_size / n_epochs|32 / 5|16 / 4|
|训练episode上限|100/seed模板|20→50→80/seed，共240|
|seed|20261021、20261022、20261023|1106823814、1495656323、1630784693|
|reward|failure_cancels_progress_v2|pilot_v3_failure_cost_floor|
|最低available RAM|3GiB|6GiB|
|状态|enabled=false且原READINESS关闭|本地冻结LEVEL_A只授开发范围|

网络[32,32]、LR3e-4、gamma1、lambda.95、clip.2、entropy_coef0、vf_coef.5、max_grad_norm.5保持相同。逐参数语义对照与两配置原hash见`source_diff/CLOUD_CONFIG_SEMANTIC_DIFF.json`。相同Python文件不意味着由它们组成的训练配置与数据组织相同。
