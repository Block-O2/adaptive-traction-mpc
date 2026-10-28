# 当前有界研究交接

用户已明确授权本轮模拟开发训练，原授权全文见 audit/USER_AUTHORIZATION.txt。原 ACTVATION 与 deadline 绝不能重置。

- 研究包：/home/hank/ihear-lab/rl_b_training_stability_reward_v1
- ACTIVATION UTC：2026-10-21T06:07:13.137817+00:00
- 硬截止 UTC：2026-10-21T14:07:13.137817+00:00
- 6h 后不再准入新训练；7h15 起不再启动新物理；最后45分钟用于关闭。
- STD 路线最多80训练episode；全部最多160；开发冻结24、最终预留12、总36；native 33,000,000。
- 原交接包 /home/hank/ihear-lab/rl_b_std_ablation_handoff_v1 的2300个manifest文件、447运行合同及两份R1/60父身份全部只读继承。

队列已独立启动，`python3 scripts/status.py` 只读查询。先检查 LAUNCHED_SERVICES.json / CAMPAIGN_PROCESS.json 的 PID+start_ticks；仍活着时不能重复启动。所有源SHA在ACTIVATION.json、audit/ISOLATED_TEMPLATE_IDENTITY.json及source_versions/。所有训练worker先验证原checkpoint完整状态，每次更新前密度归属必须通过，完整pending每episode写原子generation。

修订队列先比较两种STD各两父10集，再只延长入选方法到每父30集；R1/R4严格共同checkpoint分叉各两父10集。若STD screen均失效，R1/R4仍从原两父开始，统一一次初始化STD=.2。所有普通任务ABORTED保留并继续；未知实际安全/完整性异常全局停止，不能靠跳过guard获得READY。

最终候选与所有SHA先锁，再使用2026102301–2306，每父6条。最终流后不能继续调参。已用开发流2026102201，若余量允许只额外用2026102202做4次固定R1/R4配对开发，不改主选择规则。

断线后 campaign/watchdog/failsafe/reporter 继续有界运行。close_campaign先回收物理owner并独立审查冻结raw，之后启动 analysis_tools/finalize.py；finalizer等待四项服务退出，运行所有训练/冻结/完整/partial raw与checkpoint的独立审计，生成中文报告与图、封存manifest。独立分析脚本不会reset物理或调用Adam。

如会话继续，下一步是持续监控真实分支结果；出现普通工程问题先封存证据再隔离恢复，不修改ACTIVATION、旧PID、父checkpoint或历史失败。最终检查 FINALIZATION_END.json、PACKAGE_VERIFICATION.json，并用全量manifest重算确认精确覆盖、finalizer PID退出；PACKAGE_VERIFICATION和OUTPUT_MANIFEST有自引用排除合同。最后STOP。

所有正式资格继续：G4_STRICT_PASS=FAIL；NEW_LIVE_MATCHED_READY/STAGE2_READY/FINAL_CAMPAIGN_READY=NOT_READY。本轮不授权最终大规模Campaign、Stage2、Git写入、服务器扩容、物理硬件动作或下一研究包。
