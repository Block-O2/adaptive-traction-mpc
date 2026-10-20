# Learning 执行证据与原始安全门审计

范围：只读检查已结束、子进程已 join 的原始运行；未启动物理仿真，未更改 frozen runner、原始 trace、控制器或阈值。下列相对路径基于 canonical 新包 `/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1`；审计 JSON 同步到 Windows 新包。

## 观测和参考的实际语义

`source/.../traction_mpc_stage5/task_observation.py:70` 的 `ControllerTaskObservation.as_array()` 直接返回 `state_rad_rad_s`，顺序为 hip q、knee q、hip dq、knee dq，单位 rad、rad、rad/s、rad/s。`cross_runner.py:78–81` 保存的 `estimated_q_dq` 没有归一化。P00 各分支所有紧凑记录与对应原始 trace 的估计状态逐项相等。

`output/{run_id}_DECISIONS.json::rows[*].observation` 是另一种格式：`deps/coordination_adapter.py:42–43` 和 `code/interfaces.py:25–26` 构建 55D，然后使用 `sac_env.py:27–30` 的 `(raw/SCALES).astype(float32)`。前两维缩放为125°（转为rad），速度两维为45°/s、75°/s。P00 初始 `[.0439987443,.0759980530]` 解码约为 `[.0959903694,.1658020311]rad`，即约 `[5.5°,9.5°]`，并非单位错误。反归一化有 float32 舍入，精确原始值应取因果 trace/request。K3 的55D历史槽49、50实际来自 `previous[[0,2]]`，即第一、第三结点；`richer_previous_residual` 才保留全部三个。

`runtime_coordination_residual_v2.py:3238–3256` 在 prefetch 时将 handoff bridge 的未来终点作为 `current_reference_state`。它在决策时已经因果可用，但未必是该时刻实际发出的参考。故紧凑 `tracking_q_dq` 是请求参考误差。`derived/{run_id}_CAUSAL_SCHEMA_VERIFICATION.json` 保留原字段，并明确分开 trace 同时刻估计状态、已发出参考和两者误差；未把 evaluation-only truth 加入这些派生学习特征。

分支 fork 后紧凑记录清零，因此 P00 B/H150 各13条，parent14条；原始 summary/legacy decisions 各14条。不能声称子分支紧凑文件单独覆盖共享前缀。`LEARNING_DATA_SCHEMA.json` 已作上述说明，原始字节保存在 `audit/LEARNING_DATA_SCHEMA_BEFORE_REFERENCE_CLARIFICATION.json`，第二次 K3 名称说明前备份亦保留。

## 字段映射与已观察证据

| 要求 | 原始权威字段 | P00 H150 已观察结果 |
|---|---|---|
| 请求、来源版本、来源年龄 | runtime `requests`；source/receipt/activation simulation version；source_sample_time_s；各host ns |20请求，TASK14，全部ACTIVATED；科学时钟和host profiling分别保存 |
| 准入及certificate | summary `learning_records[].selected_plan.execution_screen`；runtime `activation_validations` |16项activation validation均feasible、C2且truth_consumed=false；含模型力/力矩筛查和几何证书 |
| future handoff与splice | runtime `future_handoff_bridges`、`rolling_splice_events`，request_id、activation/splice物理与host时钟、revalidation |10 bridge、10 splice，均SPLICED |
| 备用动作 | runtime `safe_fallback_events`，逐event类型；实际command receipt mode和positive native_steps |10 ESCAPE_ADMITTED（5OUTBOUND/5RETURN）；这是备用动作证书/准入，不代表执行10次备用停止 |
| 实际命令 | runtime `execution_attempts` 和 `wall_physics.command_receipts`：applied_robot_tau_nm/command_torque_nm、selected_command_force/moment、source age、参考及robot target |5816 attempts、5817 receipts；多出的第0个是零native步装配/预载支持；全部mode TRACK |
| native归属 | runtime `wall_physics.native_states_evaluation_only`：command_id、command_torque_nm、物理区间 |独立算术检查每一步唯一归属连续positive receipt区间，并逐命令比较力矩及步数 |
| CR12力矩及分配器 | trace `cr12_actuator_command_nm`、robot_torque_component_{base,position,velocity,allocator,clipping}_nm、allocated_wrench_world、applied_generalized_action_nm |原始列及形状保留；实际XML控制上限[436,436,194,102,66,66]Nm，TASK最大fraction=.3904959259873553 |

细节与每个字段路径见 `audit/{run_id}_LEARNING_EXECUTION_EVIDENCE.json`。数组`present`与`count`分开保存；reference_governor_records在P00存在但为空。`audit/{run_id}_RECEIPT_MODE_EVIDENCE.json` 另统计applied/unapplied、positive-step receipt数以及各mode的native步数，防止把未应用的命令算作执行。

已确认的缺口：

- `cross_analysis.py` 的紧凑 `fallbacks` 读 `summary.get('fallback_events',[])`，而实际summary没有该字段。空列表不是“无备用事件”的证据。最终汇总应引用上述原始事件类型和实际receipt。
- 紧凑STATE_ACTION本身没有装入全部certificate、admission、splice、robot torque及native归属；这些保存在同run原始runtime/summary/trace及lineage文件，需要按request、时间、receipt和已验证身份连接。
- 现有receipt未逐行直接保存 `reference_version`、`plan_request_id`、`command_kind` 这些逻辑契约字段。不得补造；使用实际存在的source/validation/reference字段及原始lineage证据，并保留未知。
- 证书限定于deployable模型参考几何/采样力学，并不证明真实患者物理不变性。纯科学仿真没有host实时资格。
- P06 的实际反例进一步限定了mode解释：receipt的TRACK表示底层跟踪控制，也可以跟踪已经提交的escape/stop参考。因此TRACK不能单独证明“未执行fallback”；必须并读FALLBACK_COMMITTED/STOPPED/HOLD事件和参考轨迹。

## 原始门覆盖

`audit/P00_ABSOLUTE_GATE_COVERAGE.json` 对照原始 `summarize_phase_b.py:47` 与实际scorer common conditions，确认没有遗漏的原始共同门。Task包括summary完成、转换顺序、目标连续dwell、真实返回及超时。Absolute safety包括200N、60Nm、Human速度45/75°/s、加速度300/600°/s²、robot速度120/120/180/234/240/240°/s、robot torque fraction≤1、Human硬ROM0–125°、shank-table接触为0、session/真实/measured sleeve clearance≥0，以及有限性。Case身份、certificate、C2和科学版本/年龄及receipt归属单列因果执行轴。

原始科学模式只从共同门移除host wall plan_age；模拟source→activation年龄仍须严格小于100ms，且核对source/receipt/activation版本和catchup不推进物理。主审计保留该scientific_validity，而不是用receipt计数替代。

共同门以外另有一项task元数据核对：原始 `evaluate_execution_mode.py:45` 也要求 `HIGH_ROM_CASE_RESULT.status == COMPLETE`。split task没有独立命名这个launcher-status门，故最终汇总已经额外核对launcher和summary均COMPLETE；不能仅由共同门覆盖推断launcher状态也已通过。

加速度有两种用途：原始绝对安全门使用 `trace.actual_human_acceleration_rad_s2` 的 valid causal monitor 样本；0.25ms native dq数值微分用于保留原motion比较。不得把两者互换或据此悄悄改变门。B的self-motion从来不是绝对安全资格；B无效时H150相对motion不可评价。

## 部分运行和关闭

`independent_batch.py` 仅对完整且integral可验证运行执行原始独立算术；部分/缺失保持PARTIAL_PRESERVED，不能升级为完整PASS。`failure_receipt_audit.py` 的EVIDENCE_PRESERVATION_PASS仅表示START/END、已保留文件、partial J_F=null、无虚构qualified gain等证据检查通过；不代表科学/安全通过。没有运行的分支为NOT_STARTED；缺失finalization证据为MISSING_FINALIZATION_EVIDENCE。

两个owned离线审计helper在campaign DONE且主owner IDLE后退出并已join：算术session43631、Learning session43907均exit0。综合字段审计 `audit/LEARNING_EXECUTION_FIELD_AUDIT.json` 包含全部36个保留运行；完整原始算术证据为 `audit/INDEPENDENT_COMPLETE_{patient_id}.json`，34个完整运行独立通过，P06/P10的H150保持PARTIAL_PRESERVED。它们的未执行部分不能获得完整科学资格。

P06 H150是实际ABORTED而非Python进程崩溃；`audit/P06_H150_PARTIAL_NATIVE_OWNERSHIP.json` 独立核对110380个保留native节点（其中TASK区间70180，17.545s）、5520receipt中的5519个positive区间，逐步command_id、力矩、区间及计数全部一致。观察前缀J_F=1583.5535802116376 N·s，完整J_F和gain仍为空。请求19/20因KNEE_REFERENCE_MUST_BE_CONSTANT失败，activation为null，所以原scientific_validity报告missing_version_vector及request_not_activated；这不等于已执行命令归属损坏。该尝试发生一次FALLBACK_COMMITTED/STOPPED/HOLD和fresh replan，仍全部经TRACK控制。保留全轨迹节点含共享前缀；实际新增物理步63320。T1/D2/ER2各记录激活且对应区间有positive native coverage，H150末段未出现；区间覆盖不冒充独立反事实因果归因。

P10 H150亦为保留的实际ABORTED，独立前缀审计 `audit/P10_H150_PARTIAL_NATIVE_OWNERSHIP.json` 核对108860个保留native节点（TASK区间68660，17.165s）、5444receipt中的5443个positive区间，归属、命令力矩和计数通过；实际新增步61820。观察前缀J_F=1006.7433959850592 N·s。它与P06具有相同的失败请求原因及显式fallback事件；完整J_F、gain和完整资格仍为空/失败。两者的普通命名STATE_ACTION文件也只覆盖观察前缀，文件名不能证明任务完整。

## 全部36个运行的力矩与分配器遥测

最终权威文件 `audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json` 按run和字段保存source hashes、有限行数、缺失的TASK及全trace索引、物理时间、terminal标记、正时长区间覆盖和receipt连接证据。34个完整运行各3806个TASK执行区间；P06/P10 H150分别3509/3433个观察前缀区间。全部区间都与实际applied receipt精确连接，trace实际执行力矩逐值相等。

`cr12_actuator_command_nm` 和 `applied_generalized_action_nm` 在全部TASK行均有限。五类 `robot_torque_component_*_nm` 与 `allocated_wrench_world` 在每个正时长TASK区间均有限；每列仅最后一个无后续执行区间的terminal boundary行为NaN。原始writer在执行区间后向左节点填入已实现分量；末节点没有后续区间，因此没有相应分量。没有将这些未知边界值补成零或重新构造。部分commissioning/session行也缺少分量，不能将TASK覆盖推广为全session完整覆盖。

冻结的普通全数组max/RMS因末行NaN传播而被序列化为null，原值保持不变。新增统计单列为 `applied_interval_peak_abs` 和 `applied_interval_time_weighted_rms`：每分量max(abs(x_i))，RMS=sqrt(sum(x_i²·dt_i)/sum(dt_i))，dt_i为相邻TASK时间差。每个正时长区间全部纳入，最后无后续区间节点权重为零；若任一正时长区间出现非有限值，新统计也必须为空，不能静默丢弃内部缺失。本次36个运行均无此内部缺失。ABORTED两个运行的统计只描述已执行前缀。

全量receipt中的实际command torque及selected force/moment均有限。附加审计还记录分量和与实际力矩差、allocated wrench与receipt选定命令的差；这些核对未替代原来的绝对安全门或科学状态。所有新增统计均为离线派生证据，没有启动物理过程或改动冻结输入。
