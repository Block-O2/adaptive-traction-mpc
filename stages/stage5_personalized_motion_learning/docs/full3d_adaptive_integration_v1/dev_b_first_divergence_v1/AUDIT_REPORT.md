# DEV-B 独立审计

日期：2026-09-24。结论：**PASS — 有界匹配状态诊断与局部因果结论成立**。
这不是生产修复验收、完整任务成功或新鲜资格通过。历史
`FULL3D_FRESH_FAILED_WITH_EVIDENCE` 不变。DEV-C 仅是范围受限的下一步建议，
本审计不授权或推广其实现。

审计者以独立上下文检查 AGENTS.md、DEV-A 文档和生产调用链，先提出检查点、
状态/动力学/分配分解与 frame 要求，再检查 DEV-B 脚本和保存数据。终审读取
`DEV_B_REPORT.md`、`CAUSAL_BRANCH_MATRIX.md`、`DEV_C_DECISION.md`，并直接
重算原始 JSON/NPZ 数值；没有只依赖 summary 或 Builder 的口头结论。

## 验证结论

| 项目 | 判定与独立证据 |
|---|---|
| 检查点完整性 | PASS，限本地重放。整体 deepcopy/pickle 保留 MjModel/MjData、integration state、warmstart、measurement/RNG、observer、reference history、supervisor、monitor/authority、模型与恢复计划状态。捕获点明确在新模型/guard 之后、首次命令之前；pending 等待已经耗尽。四例与历史初态一致，200 ms activated 克隆终态 integration hash 相同。 |
| 原路径重放 | PASS。四例各 40 区间的保存验证为精确零差。终审另外直接读取最大例历史 trace.npz，将 full_recovery_v3 的 1810 个 fitted-command 行逐时间匹配，重算 torque、true q/dq、qhat 的最大差，三者均精确 0。总恢复区间为 1811，另一个区间是拟合模型激活前的 5 ms 等待；不能混淆两个计数。 |
| supervisor 例外 | PASS。独立比较两支的 supervisor_state_comparison.json：不同字段恰好只有 computation_ms 和 last_safety_filter/computation_ms。其余全部命名值相同。排除这两个不参与动作选择的计时元数据合理；原始差异和失败尝试被保留。不是宽泛忽略 supervisor 状态。 |
| 同态命令分解 | PASS。最大例完整差 34.8338719093 Nm；allocator-wrench 经 Jᵀ贡献相同，所有 feedback/bias/clipping 变化为零，posture 差仅 2.85e-14 Nm。生产首命令和诊断链一致。独立重算动力学/状态/交互/几何向量投影为 97.0108867%、2.6779843%、0.3119144%、−0.0007853%，向量闭合误差精确 0。投影百分比有明确基准，不能推广为普遍贡献率。 |
| 干预因果解释 | PASS，局部。只改变最初 action 应用过程的 transfer 对照与 activated 对照具有相同初态、估计、几何、参考和 guard 历史。最大例 200 ms true qacc 峰值 9.918176→0.812736 rad/s²，cuff peak 90.584917→87.121832 N。普通例 force peak 略增也被披露。因此支持局部瞬态来自作用量突然应用，不支持普遍降低 interaction cost。 |
| 完整恢复后果 | PASS，负结果保留。两支原生命周期继续后都执行六个 1.5 s CAPTURE 段，并在 9.054999999983 s 以 ACTIVE_RECOVERY_TIMEOUT 停止：剩余注册 10 s 时间不足以再安排 1.5 s 段。减弱首次冲击没有修好这个病例的恢复失败。不能据此断言冲击对后续轨迹毫无贡献。 |
| 规划时间语义 | PASS，固定历史延迟的诊断。所有重放等待均为历史一个 5 ms 区间，实际计算另记且 >100 ms 阻断；终审读到两支最大实际计算分别 2.500375 和 2.513750 ms。它们不是新的 measured-latency 或硬件实时资格证据。 |
| 真值隔离 | PASS，source-bound。物理分支控制由 measurement/interface 和旧/新模型给出；true q/dq、真实接触和 qacc 用于代数 oracle 检查及评估。无真值反馈或 Human 状态赋值进入干预。测试中的 truth_consumed 标志本身不能证明隔离，本结论还基于代码数据流检查。 |

## 接触提取与模型解释

`dev_b_contact_load_probe_v1.py` 将指定 contact 的约束行乘子经
`mj_mulJacTVec` 映射到广义力，其接触索引和符号语义正确。审计者另从
`mj_contactForce` 读取 contact-frame 力/矩，用 contact.frame.T 转为 world，
在 contact.pos 对两个 geom 所属 body 用 `mj_applyFT` 施加等大反向载荷。
独立得到完整 generalized vector `[15.363881245866, 0, …, 0]` Nm，
与保存的 qfrc_constraint 精确相同，最大差 0。重新调用 probe 也一致。

最大例的 bed–thigh 法向反力确为 **33,353.295 N**，穿透 **4.819 mm**；
同期 cuff force norm 为 **67.704611 N**，二者不同。Human 方程
`M qacc + bias − passive − applied − actuator − constraint` 残差不超过
1.8e-15 Nm，Human actuator 项为 0，noncontact constraint 项为 0。
所以 33.35 kN 不是把 cuff 力误读成接触力，也不是提取符号造成的假象。

new inverse dynamics 相对 cuff-only 的 hip 误差仅 +0.181411 Nm，但相对
cuff+contact 为 −15.182471 Nm；old 相对总输入为 +2.014427 Nm。
这支持接触条件下的有效输入拟合，不能证明自由 Human intrinsic dynamics
被正确辨识，也不能把 residual −12 Nm 输出边界解释为已收敛的物理参数。
33.35 kN 本身仍是重要 plant/setup 有效域限制，数值方程闭合不能证明这种
反力具有物理合理性。报告已正确披露；本审计没有调整接触参数或重分类历史
cuff-force 标签。ordinary/middle 无接触检查点仍出现激活瞬态，故床接触
不是所有观测到的激活瞬态的必要条件。

## 必须保留的限定与 DEV-C 范围

1. 历史 allocated_wrench_world 实为总 command wrench；本诊断区分 allocator
   和 feedback 是必要更正。Human-site 与 robot-site moment 使用同一参考点
   后才能比较；当前 world/base 轴平行的兼容性不能推广到任意 base rotation。
2. 旧估计物理分支共享激活后的 monitor 历史，首步不重新宣称旧估计 acceleration
   authority 有效；它们还联动 allocation geometry。矩阵已披露，因此这些支
   不能称为未修改的旧生命周期或纯 state-only 干预。主要 transfer 对照不受
   此问题影响；完整恢复 v3 则直接沿原 guard/lifecycle 执行。
3. “突变通过 allocator channel 传播”不等于“allocator 算法或几何放大有缺陷”。
   当前报告用动力学/状态/几何分解避免了这种错误归因。
4. DEV-C 连续迁移是恰当的单一、局部建议：应在看结果前冻结连续性、feasibility
   与退出合同，沿原 filter/supervisor 检查，不将诊断 100 ms 任意常数直接当成
   最终设计。仅 generalized-action 连续仍不自动保证 executable torque 连续。
   当前建议明确需要整条输出链闭合，且不承诺消除超时或接触有效域问题。

当前三份科学报告没有必须修改的因果结论文案；上述限定应继续保留。
`COMMANDS.md` 和 `CHANGED_FILES.md` 已交付并经 Auditor 阅读，列明环境、
确切调用、版本化输出、失败尝试、新文件所有权及未提交依赖边界。初读时缺失
两份文档的问题已关闭。Auditor 另指出一个细小 provenance 文案更正：
analysis_*/command.json 保存诊断脚本 hash；输入 checkpoint hash 位于上级
capture_manifest.json，不应声称前者直接保存输入 hash。此处不要求新实验。

## 检查与操作边界

独立执行最终 16 个 DEV-B artifact/source-integrity 聚焦测试：**16 passed**。
在原 13 项基础上，新增两支完整恢复匹配/失败保留和接触平衡三项检查。
这些测试检查保存证据和源码 hash，不是又一次物理实验。`git diff --check`
通过。production 依赖源码与 capture manifest 中记录的 hash 一致。
当前 branch 为 `codex/stage5-architecture-recovery`，HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`；仍不声称仅靠此 HEAD 能
clean-clone 重现尚未提交的本地依赖和结果。

读命令包括 rg、sed、cat、shasum、git 只读检查；Python 只读取保存数据并
重算代数/接触映射，未积分新的物理轨迹。测试用
`pytest -q -p no:cacheprovider tests/full3d_adaptive_integration_v1/test_dev_b_matched_diagnostics.py`
和已有 mpc_learn 环境、Stage-3/4/5 PYTHONPATH。一次早期只读计算命令出现
SyntaxError 后修正；一次导入触发临时 matplotlib 字体缓存，均未影响证据。

Auditor 只新建本 AUDIT_REPORT.md；没有编辑生产源码、配置或历史结果，没有
运行新仿真，没有改变科学变量、假设、参数、阈值；无 stage、commit、push、
reset、stash、branch switch 或删除。唯一建议下一步：按 DEV_C_DECISION.md
批准并冻结一个有界的模型激活作用连续迁移开发合同；继续将恢复超时和接触
模型有效域保留为独立未决问题。
