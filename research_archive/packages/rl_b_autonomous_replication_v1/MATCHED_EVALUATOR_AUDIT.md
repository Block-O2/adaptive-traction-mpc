# B/H150正式匹配评价器审查

结论：**MATCHED_BASELINE_EVALUATION_NOT_READY**。本轮未部署原完整scorer，也未冒称完成B/H150原条件复现。

原CPU ZIP SHA256为`9ab8622703a84a71501bc7fcd24c665ff0bc2262979cb2857c88e146a2bc638d`，450/450载荷hash与bytes均复核通过。四个历史包各414源文件；cloud初版与后续在两处有已登记差异，当前复制的是first pilot实际source身份。唯一source docs为在线接口development合同，source_commit `41cdddef117caa4b191a52129c4ff83e481fd5a8`，并非B/H150 Master。详见audit/MATCHED_EVALUATOR_INVENTORY.json。没有把其他Stage的matched_branch、baseline_replay或matched_pacing认作本任务scorer。

|审查项目|可用证据与缺口|
|---|---|
|task/phase/runtime duration|原runtime、completion_evidence、10s/phase与30s/task可核对；正式matched合同缺失|
|19.030s与容差|历史verify_physics.py必要回归使用abs(t−19.03)<.05；不是完整task合同|
|OUTBOUND/HOLD/RETURN|原转换链与causal return commit可核对|
|absolute safety / ROM / torque / clearance / contact|原runtime监控与逐native实际物理审计可用；全动作和未触发边界没有新证明|
|B-relative motion / fairness|原B/H150身份、完整基准raw与motion非劣标准缺失|
|velocity / acceleration / jerk|原45/75°/s与300/600°/s²可按native核对；实际jerk作诊断，不能从reference jerk限制推导Human正式门|
|excursion / terminal overshoot|可独立计算实际轨迹数值；原基准相对门和terminal容差版本缺失|
|cumulative dose|完整JF/JM及phase积分可重算；正式dose定义/门槛身份缺失|
|force / moment / tracking|左端5ms完整已执行TASK区间积分与实际Human相对owned-reference tracking可核对|
|native ownership / causal receipt|0.25ms网格、每步唯一torque receipt、请求/证书/bridge/模型epoch/source-age可核对|
|source age / execution mode|100ms原始样本有效期、40ms桥和SCIENTIFIC_SIMULATION可核对；host实时/strict55不评定|

最小缺失：

- Authoritative original B/H150 complete task/safety/motion/fairness/causal contract and manifest naming precise frozen scorer files
- Original B/H150 scorer implementation/dependency closure and original baseline motion/dose normalization with version/hash
- Original B and H150 controller/config identities, complete raw, state restoration or deterministic initial-state generator
- Known original PASS and FAIL fixtures, exact tolerances, native ownership/receipt/source-age semantics and scientific-vs-host/strict55 qualification requirements

下一步迁移应按原manifest精确名称与SHA复制完整scorer依赖，先复现原B/H150已知PASS/FAIL条件和state恢复，再消费冻结PPO raw。当前接口仅分开报告runtime、必要时长和正式NOT_READY状态，不执行手写近似门。固定合法对照只可核对历史固定策略物理数值，不能填补B/H150复现结果。
