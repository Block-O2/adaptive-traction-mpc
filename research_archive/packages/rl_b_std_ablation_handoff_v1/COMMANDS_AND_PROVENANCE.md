# 命令与溯源入口

本轮所有写入仅在本研究包及/tmp；历史科学包只读。原Git HEAD通过HEAD文件直接读取，未运行Git命令。全部物理由一个环境执行，使用既有cpu-env Python：

`/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/cpu-env/bin/python`

主要实际执行入口：

- `scripts/prepare.py`：零物理身份恢复和噪声/配置预注册；现有协议存在即拒绝重建。
- `python3 scripts/evaluate_plan.py pilot`：最小pilot；两次物理启动前工程失败另存，实际有效pilot使用interfacefix2新ID。
- `scripts/check_pilot.py`：独立噪声/clip/冻结身份核验。
- `python3 scripts/evaluate_plan.py identity` 与 `scripts/check_identity.py`：两个mean与历史raw精确回归。
- `python3 scripts/evaluate_plan.py preregistered`：按STD_PLAN_v3执行固定24次A/B。v1→v3仅修复物理前缺失audit依赖和辅助NumPy seed范围，正式配置/已保存noise未改变。
- 每个物理worker真实命令为上述venv Python + `source_versions/<bundle SHA>/worker.py --config <configs JSON>`；具体bundle和config SHA见jobs/<id>/SOURCE_IDENTITY与START，physical START/END见runtime/jobs/<id>/episode_061。
- `scripts/compare_history.py`、`scripts/cuff_mechanism.py`：保存raw的历史六轨迹独立复算与接口测量点/方向剂量分析，零物理/梯度。
- `scripts/analyze_attempts.py`、`scripts/render_results.py`：保存raw/receipt/动作/状态配对分析及CSV/PNG/PDF。
- `scripts/recheck_frozen.py`：新进程从保存raw重算全部冻结native、receipt、force、motion及R1总式；输出重定向到audit/independent_recheck。
- `scripts/test_unattended_control.py`、`scripts/test_unattended_campaign.py`、`scripts/test_unattended_watchdog.py`、`scripts/test_future_worker_config.py`：纯工程控制/真实一次性进程测试，零物理和梯度。
- `scripts/test_reward_proposal.py`：R4在52条历史causal measurement上的算术重放，仅提案验证。
- `scripts/prepare_next_plan.py`、`scripts/version_future_configs.py`：准备inactive next-stage计划、配置和源码manifest；不会启动训练。
- `scripts/protect_history.py start/end`：87,733个历史保护文件SHA；end为本轮独立结束核验。
- `scripts/build_reports.py` 与最终封存/核验程序：报告、账目、资源、精确文件manifest与退出证据。

上述未标python3的分析/审核入口使用既有venv Python执行；PPO训练、learn/train/backward/Adam step在本轮冻结worker内明确禁止，账本只允许evaluation预留。

`unattended/template`中的worker/campaign/close/watchdog等是经审查的未来源码，不在本轮执行训练。`prepare_unattended_templates.py`仅记录初始构建；已存在审阅模板时会拒绝覆盖，恢复应使用权威TEMPLATE_IDENTITY和next_launch入口。
