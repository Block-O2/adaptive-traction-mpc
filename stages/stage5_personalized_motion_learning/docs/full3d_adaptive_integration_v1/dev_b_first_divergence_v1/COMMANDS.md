# DEV-B commands / provenance

运行目录 `/Users/hankli/Desktop/coding/adaptive-traction-mpc`；branch
`codex/stage5-architecture-recovery`，HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`。以下均为本地诊断，不涉及硬件。
没有 Git 写操作。生产源文件不改动；原有未提交依赖仍是运行前提。

## 环境与可重放调用

每个 Python 调用使用下列前缀；为简洁，下方命令中的脚本参数接在 `python` 后：

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn python ...
```

每例 `capture_manifest.json` 保存完整实际 `command`、Python/NumPy/SciPy/
MuJoCo/platform 版本、源码 SHA256、历史输入 hash、checkpoint hash。
`analysis_*/command.json` 保存分析调用和诊断脚本 hash；输入 checkpoint hash
见上级 `capture_manifest.json`。pickle 包含当前 MjModel
与 MjData；应只加载本研究受信本地文件，不能视作跨软件版本可移植格式。

四例捕获与 200 ms 分支批处理：

```bash
stages/stage5_personalized_motion_learning/scripts/run_dev_b_selected_v1.py
```

脚本固定映射四例到 DEV-A `regression_v2` / `nominal_development_v2`，
输出 `results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3`。
批次逐例保存 `BATCH_STATUS.json`；最终 COMPLETE。此 runner 的已完成跳过逻辑
适用于该版本恢复执行，不要删除完成文件或覆盖已存证据来重新运行。

最大案例延长物理分支（参数完整列出）：

```bash
stages/stage5_personalized_motion_learning/scripts/dev_b_matched_diagnostics_v1.py analyze \
  --checkpoint-dir stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3/balanced_near_upper_current_rom_r01 \
  --duration 1.5 \
  --branches retained_model activated_model activated_duplicate diagnostic_action_transfer_100ms

stages/stage5_personalized_motion_learning/scripts/summarize_dev_b_first_divergence_v1.py \
  --root stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/summary_v1

stages/stage5_personalized_motion_learning/scripts/dev_b_contact_load_probe_v1.py \
  --root stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3 \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/contact_load_probe_v1.json

stages/stage5_personalized_motion_learning/scripts/run_dev_b_recovery_counterfactual_v1.py \
  --checkpoint-dir stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3/balanced_near_upper_current_rom_r01 \
  --arm production_replay \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/full_recovery_v3/production_replay

stages/stage5_personalized_motion_learning/scripts/run_dev_b_recovery_counterfactual_v1.py \
  --checkpoint-dir stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/capture_v3/balanced_near_upper_current_rom_r01 \
  --arm action_transfer_100ms \
  --output stages/stage5_personalized_motion_learning/results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/full_recovery_v3/action_transfer_100ms
```

后几个工具拒绝覆盖已有输出。未来复现应使用新的版本化输出路径，不要删除旧证据。
完整恢复两支在 task 之前停止；没有重跑 24-case regression。

## 保存的失败/工具修订

- 最初 `balanced_near_upper_current_rom_r01/` 捕获物理 checkpoint 成功，
  manifest 构造误用了 `truth_state` key，`CAPTURE_FAILURE.md` 保留。
- `capture_v2/balanced_near_upper_current_rom_r01/` 第二次误用 `robot_q_rad`
  key；保留 checkpoint 和早期分析。修复的是诊断序列化，不是控制器。
  `capture_v3` 为最终完整 manifest 和历史 replay 验证证据。
- `full_recovery_v1/production_replay` 的 supervisor pickle 比较失败；
  `full_recovery_v2/production_replay` 完整 JSON 比较也失败。均在匹配检查
  停止，没有执行新的分支 action。检查显示只有两个计时 telemetry 不确定。
  v3 仅排除 `computation_ms` 和 `last_safety_filter/computation_ms`，保留
  原始逐值比较文件和其余 action state 全等要求。Auditor 独立复核。
- 诊断 action-transfer、1.5 s 延长和完整恢复不是初始冻结 protocol；
  是允许的有动机 development extension，见 `DIAGNOSTIC_EXTENSION.md`。
- 文档收尾一次无环境前缀的 `python` 读取命令返回 command-not-found；
  改用现有 `conda ... mpc_learn` 后读取成功，没有文件或实验受影响。

## 聚焦检查

```bash
env MPLCONFIGDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=stages/stage5_personalized_motion_learning/src:stages/stage5_personalized_motion_learning/scripts:stages/stage4_adaptive_control/src:stages/stage3_full3d/src \
  conda run --no-capture-output -n mpc_learn pytest -q \
  stages/stage5_personalized_motion_learning/tests/full3d_adaptive_integration_v1/test_dev_b_matched_diagnostics.py
git diff --check
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all
```

最终聚焦测试 **16 passed**：四例匹配/重复克隆、代数命令重构、物理边界数与
truth-firewall 声明、生产依赖 hash、完整恢复反事实与失败保留、contact dynamics
平衡及 cuff/contact 区分。它们是 artifact/source-integrity 回归，不是新鲜
资格验证；truth firewall 还由 Auditor 阅读诊断与生产源码独立核查。
