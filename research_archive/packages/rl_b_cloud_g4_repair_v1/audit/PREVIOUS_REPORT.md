# iHEAR RL-B Cloud Deployment & Qualification v1

本轮完成隔离部署和有限真实物理验证，训练资格未通过，已 STOP。开始时间 2026-10-20 14:04:45（Asia/Shanghai），报告生成时间 2026-10-20T14:25:32.283666+08:00。未因预计 2–4 小时而消耗剩余时间做随机试错。

| 资格项 | 结果 | 直接证据 |
|---|---|---|
| DEPLOYMENT_PASS | PASS | 原 ZIP SHA256 一致；450/450 载荷初始匹配；科学 source/ 完整；PACKAGE_VERIFICATION.json |
| G4_PASS | FAIL | 自然关键超时/绝对安全失败路径尚未闭合；slow partial 原 summary 力积分多计 0.555109 N·s；G4_PHYSICAL_VALIDATION.json |
| EXECUTION_PASS | FAIL | 原 random 19.03±0.05s 回归实际 20.165s；原失败审计保留；核心 nominal 执行链及实际 Human 检查通过，不能替代完整回归；RL_EXECUTION_VALIDATION.json |
| PPO_UPDATE_PASS | NOT_RUN | 未满足阶段门；真实梯度更新数 0；负向启动门正确拒绝；PPO_SMOKE_RESULTS.json |
| CHECKPOINT_RESUME_PASS | NOT_RUN | 无训练 checkpoint，未用随机权重冒充恢复证据；CHECKPOINT_RESUME_AUDIT.json |
| TRAINING_PILOT_READY | NO | G4/执行回归门未通过；无正式训练自动启动 |

1. **ZIP 是否完整部署：是。** 原件 SHA256 `9ab8622703a84a71501bc7fcd24c665ff0bc2262979cb2857c88e146a2bc638d`，450 个 manifest 载荷全部在解包前校验。原 ZIP/manifest 未改；source/ 与基准一致。部署修复只涉及隔离 wrapper、资源配置和审计，具体差异有原件、哈希和独立 overlay manifest。
2. **Ubuntu CPU 依赖是否可用：是，当前 headless 研究运行路径已实证可用。** 所有 Python 固定版本匹配，pip check 与模型加载/真实积分通过。未检出的可选 OS 渲染库不声称已安装；见 CLOUD_ENVIRONMENT_AUDIT.md。
3. **G4 真实失败路径是否闭合：否。** 自然零进度拒绝、长期低进度失败、RETURN 零动作失败、fallback 停止及新鲜恢复、失败回报取消、终止语义及真实 reset 均有证据。OUTBOUND/HOLD/RETURN/global deadline 和绝对安全失败并未全部自然触发。TEST_ONLY 与自然物理严格分开，HOLD 注入先触发原不可行终止。另发现 slow trace 重复边界，独立 JF 927.525976、原 summary 928.081085 N·s；wrapper 回报重算正确。
4. **RL-B 原科学执行合同是否保持：观察到的 nominal 核心链保持，完整回归资格未授予。** 原 Planner/Certificate/current-state admission/Governor/40ms bridge/100ms lifecycle/5ms controller/Allocator/source-age/native receipts 未改。所有已保存自然 episode 的实际 q/dq/原生、5ms、20ms 加速度与 torque、force、moment、ROM、clearance 检查通过；每个 native step 有唯一 torque receipt。最大动作 19.03s 完成任务，random 20.165s 完成原任务但未通过封存精确时长回归，标准未放宽。
5. **PPO 是否完成真实梯度更新：否，按门控未运行。** environment decisions / native physics steps / optimizer steps / gradient updates 在 PPO 中均为 0。物理资格验证的计数与训练计数分别记录。
6. **checkpoint 能否可靠恢复：尚不能判定。** 未产生训练 checkpoint，optimizer/RNG/进度恢复均 NOT_RUN；无 checkpoint 哈希可报。
7. **CPU 实测吞吐：** 单环境 guard wall 76.643s/完整 episode，0.1827 native-event decisions/s、1517.7 native steps/s，reset 18.479s；双环境两条完整 episode 总 wall 79.520s，合计 0.3521 decisions/s、2925.5 native steps/s，约 1.93×。计时含 commissioning/recovery/持久化，物理步数也含这些阶段。环境内部 wall 和任务步数另外保留。最大动作仅 14 次、random 30 次 native-event 决策，不能套用历史 50ms 决策数。双进程评价吞吐已测；PPO 本身仍维持原单环境实现，双环境向量 PPO 未资格验证。PPO 更新和 checkpoint 写入成本 NOT_RUN。
8. **资源与稳定性：** 最低可用 RAM 28.472GiB，高于 6GiB 余量；无 swap/OOM/磁盘不足/MuJoCo warning。runs 共 1.488GiB，最终磁盘可用 208.96GiB。所有失败与 harness 错误保留。
9. **正式 PPO Pilot 条件：未具备。** 不用可达性、TEST_ONLY、部署成功或源码静态检查替代 G4/训练/恢复门。
10. **下一轮建议：** 只做 G4/统计修复与资格重验，最多 10 episodes、1 个固定 development seed 20261021；预计真实物理及审计约 20–30 分钟，含修复和复核预留 45–90 分钟，硬上限 2 小时。正式 Pilot episode 数本轮批准为 0；先闭合所有门，再另定 Pilot。

自然与注入真实 MuJoCo共 12 个 episode，6 个 COMPLETE，其余原任务 ABORTED；共有 1218740 个 native steps，包括 commissioning/recovery。PPO 正向启动 0 次。已记录 12 个 guarded START、12 个 END，均 joined；最终进程检查另见 ATTEMPT_ACCOUNTING.json/PROCESS_EXIT_AUDIT.json。

修复记录：提高 RAM 保护；修复报告文件污染 checkpoint code/config 身份的问题；同边界 ABORTED 通知审计修复；补充审计识别正确被拒绝的负例 certificate；qualify.py 增加独立 G4 矩阵门。原物理/任务/安全参数、B/H150、ZIP/原 manifest 无改动；未 git commit/push/merge/reset/stash/clean。完整命令由各 START.json 与 deployment_audit 日志保存。

最终封存检查：PROCESS_EXIT_AUDIT.json = PASS；owned 训练/仿真进程 0；12/12 START/END 闭合，全部 child 与 native executor 已退出；科学 source/ 与原 manifest 一致，独立部署 overlay 校验通过。完整输出哈希见 OUTPUT_MANIFEST.json。
