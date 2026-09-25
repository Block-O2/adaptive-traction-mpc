# DEV-B 最终状态 / restart-safe checkpoint

`DEV_B_DIAGNOSIS_COMPLETE` — 2026-09-24。独立 Auditor PASS，有界诊断结论。

## 已完成

- 四个既有开发案例的匹配 checkpoint；各六条 200 ms 物理分支。
- 最大跳变案例四条 1.5 s 首段分支；保留旧模型支 0.810 s clearance abort。
- 固定物理状态的 state/dynamics/allocation 代数拆分与六轴 torque 分项闭合。
- evaluation-only 接触广义载荷提取及独立验证。
- 最大案例完整恢复 production/100 ms diagnostic transfer 两支；
  1810 个新模型控制区间（含激活前等待共 1811 区间），都在 9.055 s 超时。
- 16 个聚焦测试 PASS；`git diff --check` PASS。
- 独立审计：历史命令、true q/dq、qhat 全程零差；supervisor 仅两项
  wall-time telemetry 不同；其他作用状态完全相同。

## 结论

首个主导变化位于 Human beta+residual 模型的 generalized-action 应用，
同态 CR12 torque 变化 34.834 Nm，经原 allocation/Jᵀ传递。不是新的
Jacobian/feedback 突变。局部瞬态的因果干预成立，但减弱它不足以修复后续
恢复超时。最大案例存在 33.353 kN 模拟床–大腿反力，约 15.364 Nm 髋广义
支撑；contact-conditioned model 含义及后续失败机制仍 OPEN。

唯一下一建议：DEV-C 模型激活作用量连续迁移开发，见 `DEV_C_DECISION.md`。
**本阶段停止；不得自动实现 DEV-C 或运行新资格/大 ROM/RL。**

## Git / evidence

入口与出口分支 `codex/stage5-architecture-recovery`，HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`。
入口 592 个 dirty/untracked 路径在 `GIT_ENTRY.json`；出口在 `GIT_EXIT.json`。
仅新增 DEV-B scripts/test/config/docs/ignored results。没有生产源文件改动；
所有旧 formal / DGN / DEV-A 证据不改写，历史正式结论仍失败。
未 stage/commit/push/reset/stash/切换分支/删除历史或无关文件。

结果根：`stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/`。
最终证据：`capture_v3/`、`summary_v1/`、`contact_load_probe_v1.json`、
`full_recovery_v3/`。失败的 capture 和 recovery v1/v2 也保留。
无需继续任何挂起实验。若恢复本会话，只应阅读报告及审计，不要重复已完成
分支。详细命令和文件所有权分别见 `COMMANDS.md`、`CHANGED_FILES.md`。
