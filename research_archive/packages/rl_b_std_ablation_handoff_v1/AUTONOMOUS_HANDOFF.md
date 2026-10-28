# 自主研究交接

本轮28冻结attempt、3,056,220 native、0训练/Adam；正式A/B每父6条新流，C精确身份回归。结果与限制从REPORT.md开始读取。

继续前读取：REPORT.md → STD_ABLATION_PROTOCOL.md / STD_ABLATION_RESULTS.json → ACTION_DISTRIBUTION_AUDIT.md → H2_R1_COMPARISON.md → REWARD_RESEARCH_PROPOSALS.md → UNATTENDED_CAMPAIGN_PLAN.md → UNATTENDED_EXECUTION_READINESS.json → NEXT_PARENT_CHECKPOINTS.json → PACKAGE_VERIFICATION.json。

本轮所有动作流已见，不可重新当未见holdout。下一轮已预留2026102301–2306，每父6条；只在模型锁定后打开，届时若已有其他任务使用它们必须版本化替换并重锁计划。

只读核验入口：`python3 unattended/next_launch.py --inspect`。它默认不创建未来包、不启动进程。下一轮明确训练授权后，才可 `python3 unattended/next_launch.py --prepare-authorized --start-authorized`；请先检查所有hash与resources。现有目标目录会拒绝，不能覆盖。

断线后查看未来包内 `python3 scripts/status.py`，以及PROGRESS_REPORT/RESEARCH_STATE/LEDGER/JOB_RESULTS/owned/START-END。PID+start_ticks匹配仍活着时不要重复启动；时间预算从实际ACTIVATION起算且恢复时不能重置。

普通task ABORTED保留后继续其他预定假设；Reward失败不得争用低partial JF晋级。未知安全/身份/receipt/资源失控全局停止。partial-Adam或未闭合reservation不能盲目继续，需显式恢复或跳过分支，历史数据不覆盖。完整pending按episode原子保存，所有更新前密度归属必须通过。

模板已做真实控制器fake-job与预算测试，尚未训练新STD/R4，也未测试partial-Adam实际故障重放。运行准备不等于研究成功保证；所有最终科学结论须独立复核。

严格禁止：改变真实Human/robot/cuff物理、ROM/torque/clearance、planner/certificate/admission、原任务成功身份、正式B/H150 scorer；自动Git变更/服务器扩容/Stage2/正式Campaign；无授权后台新实验生成。

本轮完成后STOP，不自动启动7–8小时训练。
