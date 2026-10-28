# Next research decision

TRAINING_PILOT_READY = false。下一轮唯一建议：修复并重新验证 G4/原始统计合同。

预算：最多 10 个真实物理 episodes、一个 development seed 20261021、单环境起步、至少 6GiB 可用 RAM；物理与审计预计 20–30 分钟，工程修复与复核合计 45–90 分钟，硬上限两小时。正式 PPO Pilot 为 0 episodes，未授权自动训练。

先复现 slow-policy 同时间边界的 interval force 重复计入，版本化修复日志统计而不改物理、奖励系数、安全或任务；然后补齐关键自然失败路径可达性证据，并调查 fixed-seed random 20.165s 与封存19.03s回归的差异。无法自然到达的 deadline/安全失败继续明确 NOT_RUN；TEST_ONLY 不能替代。所有门通过后再执行随机初始化、真实 gradient update、训练 checkpoint、退出/恢复和有限真实评价，不得从静态检查直接进入 Pilot。

双物理进程评价的吞吐提升约1.93倍；下一轮资格诊断维持单环境以便因果归因。PPO 仍使用原单环境实现，双环境 PPO 需独立集成/资格验证。
