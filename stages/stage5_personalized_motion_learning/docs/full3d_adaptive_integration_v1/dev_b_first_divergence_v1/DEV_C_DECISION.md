# DEV-C 单一建议：模型激活时的控制作用连续迁移

建议只修复 **commissioning 模型首次应用的 generalized-action / executable-command
连续迁移**，先以版本化开发实现验证；本 DEV-B 没有修改生产实现。

## 当前行为与因果依据

OBSERVED：位姿 reference 已有 C2 bridge，但 candidate beta+residual 在一个
5 ms 边界全量替换 prior。最大的相邻 robot torque 跳变 34.780 Nm。
CAUSALLY_SUPPORTED：同一物理/观测/参考状态下变化为 34.834 Nm；约 97.01%
沿总变化方向来自动力学替换，状态贡献约 2.68%，几何不是主要放大源。
新 residual 的 hip 分量已经在 −12 Nm 输出边界。

CAUSALLY_SUPPORTED：仅让初始 generalized-action 差值在诊断 100 ms 内退出，
保留模型、几何和所有已有约束，最大案例的瞬时 Human acceleration 峰值
9.918→0.813 rad/s²；无床接触的 complete 案例也出现 6.963→1.572 rad/s²。
因此局部冲击有可干预的上游命令来源，不能归因于 CR12 Jacobian 突变。

OPEN：此修复不能被承诺解决后续恢复超时。完整恢复配对中两支仍于
9.055 s 同样停止。还有显著 contact-conditioned 模型问题；在最大案例中
床–大腿支撑贡献 15.364 Nm hip generalized load，拟合模型不能解释为
无接触 Human 的独立动力学。

## 建议的架构原则与改动边界

在模型激活瞬间同时保留“当前已执行的命令”与“候选模型计算的目标命令”，
建立有限期、显式记录的转移状态。修复应作用于已经证明产生突变的
Human generalized-action 应用路径，并经过现有 geometry allocation、
完整 force filter 和 CR12 realization 检查；应明确几何变化造成的剩余
输出差异，而不能只宣称 qref/pose 连续。不要直接复制诊断用的 100 ms
常数作为最终设计，也不要靠无处不在的 torque clipping 掩盖问题。

beta/residual 更新方程、拟合方法、模型含义、力/矩/ROM/加速度/clearance
限制、100 ms planner deadline、task candidate/cost、CR12+cuff+床模型都保持。
任何改变这些内容的建议应另列科学范围，不能混入这一个 DEV-C 修复。

## DEV-C 验收测试

在查看 DEV-C 开发结果前冻结具体转移与终止条件。至少验证：

1. 相同检查点，无干预路径继续逐样本复现 DEV-A；模型、几何与 estimator
   历史不被重置；任务与参考不缩减。
2. 记录并闭合 Human action→Human/robot cuff wrench→每个 robot torque
   分量。切换当刻的连续性应有数值合同和完整 feasibility 证据；若无法
   在原约束下连接旧/新命令，应明确拒绝而不是隐藏不连续。
3. 转移退出后恢复候选模型原始控制律，没有永久补偿、隐形旧模型混合或
   更新速率修改；三个 varied 开发检查点与 nominal 都覆盖。
4. 用相同物理初态比较 substep 瞬态、20 ms 已注册 motion monitor、cuff
   峰值/积分、clearance、任务进入和失败原因；不能只用加速度峰值降低验收。
5. 保留有接触和无接触对照、所有未解决的超时与 runtime 失败，不把此修复
   升格为新鲜资格验证。

主要风险：转移减弱局部冲击却延迟必要纠正；普通案例 force peak 已从
100.069 小幅升至 100.502 N。更重要的是，模型可能包含床支撑有效项，
接触状态变化后其控制充分性仍未验证。命令连续性修复不能消除这些模型
与物理有效域限制；它的验收结论必须限定在这一个已定位缺陷。
