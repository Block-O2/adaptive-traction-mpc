# Learning baseline provenance

状态：**simulation research / learning development baseline**。本文件只定义后续研究工作区，不是runtime、连续安全、硬件或临床资格。

- 工作区：`/Users/hankli/Desktop/coding/adaptive-traction-mpc-learning`；分支：`codex/adaptive-traction-learning-baseline`。
- Git起点：`b45712829ae356eee11a950b359611001a776e88`，包含已验证的scorer-v2。最终本地checkpoint SHA见canonical consolidation报告和Git HEAD。
- 精确选用：原 `codex/full3d-cr12-waypoint-smoothness-v1` 早期 RSS 功能候选，冻结源为 `ORIGINAL_RSS_FUNCTIONAL_FREEZE.json`，SHA256 `28fb83285c68411fef597c720659c81e480e9c5a7ec201a0a61e9c8188383cf1`。178个源码/配置/评分文件逐个SHA256匹配；实际重建的6项见 `LEARNING_BASELINE_SOURCE_FINGERPRINTS.json`。
- RSS 功能证据：既有120/120单例真实到达、连续dwell、RETURN、安全、C2与0次stale activation；reference near-stop约0.140 s。原8例只执行3例、2例通过，100/100的control miss失败保留，不宣称8/8。
- scorer-v2：原生physical COMPLETE commit取样；既有online/offline一致性及历史影响审计已保留。项目原100 ms stale rejection仍是硬执行规则。
- 排除最终失败实验：最后的split-revalidation候选只变更了 `online_planning.py`、`activation_validation.py`、`runtime.py` 并新增 `prepared_activation.py`。前两项中的`online_planning.py`在本起点已等于实验前哈希；后两项使用`source_before`原始文件的已验证SHA256；新模块**不存在**。失败原始记录保存在canonical archive及consolidation provenance中。
- 冻结 protocol v4副本SHA256 `8693eb5e038fc603665ba35b86b8be1a1cdeaf19ef288960a45c094384b09283`，保留55 ms activation限制和全部旧失败。该RSS baseline **NOT runtime-qualified**；最终架构尝试已正式接受simulation activation tail limitation。
- 125° High-ROM工程模型、任务/安全约束、100 ms stale规则未因consolidation调整。本轮未跑新的MuJoCo任务矩阵，因此不提升任何功能或安全主张。
- 后续value/RL只能异步参与合法candidate ranking；inference不能阻塞active trajectory，过deadline要drop或退回no-value ranking，并接受独立safety/revalidation。rep内value版本固定。该接口尚未实现或训练。
- raw trajectory在canonical `local_evidence_archive/`，路径与哈希映射在 `LOCAL_EVIDENCE_ARCHIVE_MANIFEST.json`。历史docs/source归档见 `WORKTREE_PROVENANCE.md` 与 `ARCHIVED_WORKTREE_FILES.json`。

此baseline适合受控离线simulation research的下一步开发；**NOT hard-real-time、NOT hardware/clinical qualified**。
