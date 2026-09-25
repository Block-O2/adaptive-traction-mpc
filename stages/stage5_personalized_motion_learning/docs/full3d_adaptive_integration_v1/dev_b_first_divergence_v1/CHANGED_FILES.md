# DEV-B 文件所有权与复现边界

所有路径以下述仓库为根：
`/Users/hankli/Desktop/coding/adaptive-traction-mpc`。
本阶段没有编辑任何此前存在的 production source/config/模型/历史结果。
592 个入口 dirty/untracked 路径完整保存在 `GIT_ENTRY.json`，不可归为 DEV-B 改动。

## DEV-B 新文件（显式清单）

Stage-5 根目录为 `stages/stage5_personalized_motion_learning/`。

- `scripts/dev_b_matched_diagnostics_v1.py`
- `scripts/run_dev_b_selected_v1.py`
- `scripts/summarize_dev_b_first_divergence_v1.py`
- `scripts/dev_b_contact_load_probe_v1.py`
- `scripts/run_dev_b_recovery_counterfactual_v1.py`
- `tests/full3d_adaptive_integration_v1/test_dev_b_matched_diagnostics.py`
- `configs/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/study.json`

文档目录 `docs/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/`：

- `DEV_B_REPORT.md`
- `CAUSAL_BRANCH_MATRIX.md`
- `DEV_C_DECISION.md`
- `AUDIT_REPORT.md`
- `STATUS.md`
- `COMMANDS.md`
- `CHANGED_FILES.md`
- `DIAGNOSTIC_EXTENSION.md`
- `GIT_ENTRY.json`
- `GIT_EXIT.json`

结果目录 `results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/`
全部为 DEV-B 新的、Git ignored 的本地诊断证据：初次失败捕获、capture_v2、
capture_v3、summary_v1、contact_load_probe_v1.json、full_recovery_v1/v2/v3。
包含失败工具检查、完整模型 checkpoint、分支物理/command trace、hash、
配对一致性和图；没有覆盖 DEV-A/DGN/formal results。

## 未提交依赖和复现限制

这些新增文件均未 stage/commit/push。当前 full-3D 工作依赖入口已存在的
未提交 runtime、DEV-A lifecycle、Stage-3/4/5 helper、模型/assets、历史
case bundles 与 traces；逐文件 SHA256 在每个 capture manifest 的
`source_sha256`，原始 case/trace hash 与 checkpoint hash 也保留。
测试确认捕获清单中的生产 `/src/` 文件与捕获时完全一致。

`GIT_ENTRY.json` 是入口状态，不代表都与 DEV-B 有关；其中 Stage-4 和其他
历史研究工作保持原样。`GIT_EXIT.json` 保存出口状态及与入口差异；本阶段
新增 allowlist 之外没有改动所有权。**不声称从已发布 HEAD clean clone
即可复现**：还需要当前未提交依赖和 ignored results。保存 checkpoint 也不能
替代模型文件/环境与原始捕获命令的完整 provenance。

未 stage、commit、push、reset、stash、切换分支、删除历史或清理无关文件。
