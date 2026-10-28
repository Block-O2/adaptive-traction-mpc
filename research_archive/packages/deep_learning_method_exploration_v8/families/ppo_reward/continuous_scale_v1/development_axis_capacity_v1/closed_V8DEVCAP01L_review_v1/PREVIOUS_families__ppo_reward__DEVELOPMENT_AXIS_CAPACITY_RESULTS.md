# 原重型开发条件的固定连续轴能力诊断

V8DEVCAP01H 在原已曝光 DevHeavy035 条件完成：B 通过原完整资格；原 EARLY_H150、独立付费 λ1 重复及 λ.5/.25/.75/0 均完整执行，但全部未通过运动资格。五个固定 λ 加上旧两个 unique heavy draw，没有在这些已观测点找到合格非 B 支持。此结论不覆盖整个连续区间，不是新验证，也不是整个方法家族失败。

本报告只复核已闭合元数据；新 model/init/restore/forward/score/fit/RNG、mapper、数学诊断、scorer、raw compare 和 physics 调用均为 0。轻型 V8DEVCAP01L 与 POSTAPP02 未读取。所有原 frozen source/model/config/阈值/任务及原时钟保持。

## 固定条件、权限与闭合

- 原 case SHA `305b90192d653a234f2375e23d99ee98fe9ed9030239a05c767a8133d90164e9`，seed `2026102751`；与原 V8BETA01H 相同。原 prefix：OUTBOUND `[[0.068,0.042,0.024]]`、RETURN `[[0.047,0.026,0.019]]`，cold OUTBOUND slot0。
- Config SHA `22f1ed3ad1e462235d9ffe26fc89cdaeec38135cc8eac2143fe056368f582488`，实际 job source manifest SHA `2c7fbd3dac0b39002246313bdc6d96c1265083341161705b260440b7ed7a3a2e`；1408 config pins 与 1408 actual job files 逐项绑定。
- 分支为 `EXPOSED_DEVELOPMENT_CAPABILITY_NOT_NEW_VALIDATION_NOT_TRAINING`。原 condition.scope 中保留的“continuous Beta sampling only”是继承文字；实际注册分支与计数明确为固定动作，不读取策略或进行 sampling。
- 原序列为 B→EARLY_H150→独立付费 λ1→λ.5→λ.25→λ.75→λ0。原 BEFORE_B 记录已完成 5 次纯映射后才提出 B，无结果/策略参与选择。最终 5 map entered/returned、7 physical proposals；模型相关调用 0，NOT_RUN=[]、stop=null。
- 原 8 START/8 END 按原 START id 关联 END；7 child 全部 joined，父状态检查全部 unchanged。12 个实际已知 PID/startticks 身份均已退出；SUPERVISOR_END 无 survivor，worker exit0，WORKER_DONE=`PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS`。原全局截止不变，未续期 Beta 训练窗口。

## 原完整结果全部并列

所有 7 child 的原 physical/scientific/legacy 轴 PASS、HOST 轴 NOT_EVALUABLE，11 个 hard_safety_conditions 全 true，true_hard_safety_violation=false。完整运动门与这些硬条件分开：λ0 的 acceleration p95 运动失败不能改写成原 hard human_acceleration 违规。

|原实际分支|完整|原完整资格|原运动失败项|JF (N·s)|JM (N·m·s)|
|---|---|---|---|---|---|
|B|true|true|无|1518.6079264083894|105.80146265999815|
|EARLY_H150|true|false|excursion|1479.0382721353728|112.01135684413885|
|独立付费 λ1 repeat|true|false|excursion|1479.0382721353728|112.01135684413885|
|λ.5|true|false|excursion|1489.3704262703434|111.04367691330602|
|λ.25|true|false|excursion|1494.8338681805233|110.74475341780676|
|λ.75|true|false|excursion|1484.0390862979589|111.51255104374856|
|λ0|true|false|acceleration_deg_s2/p95_abs；excursion|1500.5864763464049|110.42629786886867|

较低 JF 不让不合格分支获得控制收益资格；此处不排序、不选 best、不变 reward。λ0 仍保留底层 T/native residual/terminal repair 语义，不能当作原 B 或 zero-noop。

原 H 与 λ1 是两次独立付费任务，不能静态 alias。已存原 full raw gate 为 PASS，全部 48 个 trace 字段一致，116320 native states、5817 command receipts 及原 applied/reference/source/ownership 记录覆盖一致；本次只核对 gate 元数据，没有再读 raw 或重跑 compare。原 parent→B 同范围 gate 也 PASS。

原 parent 与 7 child 的 8 份原 scorer replay 均 `SCORER_REPLAY_PASS`、original_result_exact_reproduced=true，完整复现原资格、JF/JM 和 motion requirements，case/seed/config identity chain PASS。本次未调用 scorer。原每个实际 child receipt 的 fresh native steps=76120；父 native steps=116320 单列。原 child END 未填 native_steps，继续保留 null，不用 gate 的整轨迹步数补造 child 成本。

H 与 λ1/.5/.25/.75 的原 execution 各有 6 条记录，其中顺序为 4 ACCEPTED、1 REJECTED、1 ACCEPTED；B 与 λ0 的 execution=[] 原样保留。实际 EXECUTION_BINDING.action 与原 action 一致。拒绝、fallback、空记录都保留，不能补造每条请求全部 activation 的证据。

## 与旧真实采样的关系

旧 G0 heavy RF_RAW 的两个 unique λ=.4954206827630028/.7027323475410143，在已闭合 GateD 与原 result 中均 complete、原资格 false、excursion 失败。原四臂为重复付费身份，不能把它们计作八种独立 λ 覆盖。旧 exact-proposal 导出中的 physical_receipt=null 没有被当作资格证据；此次使用已有闭合 result/GateD 元数据，不读真实 run 或重算 reward。

## 资源与证据层次

|原已付费阶段|原 wall|原 CPU|原 peak RSS|范围|
|---|---|---|---|---|
|物理 supervisor|996.10027551651 s|未在 supervisor 单独隔离|未在 supervisor 单独隔离|FINITE_REGISTERED_MENU_COMPLETED，exit0、survivors=[]|
|物理 GNU time 外层|16:36.13|user985.27 s / system22.88 s|1507876 KiB|原 parent+7 child，exit0|
|原 worker|993.8756144046783 s|未单独隔离|未单独隔离|7 child joined|
|原 8 项 scorer replay 外层|1:05.22|user56.44 s / system8.77 s|902420 KiB|exit0、0新物理；原 replay 未记录 PID/startticks，保留 UNKNOWN，不用 session ID 冒充 PID|

这些资源是原主线程已付费执行，不是本次 metadata 复核新增调用。复核通过 3050 checks，核对 1465 个唯一文件 hash、55 JSON、16 条目标原事件。复核 START 未单独记录 CPU/RSS/PID，不填 0 或捏造身份。

七层结论分别是：源码与映射身份通过；before-B 固定决策成立；原完整执行与硬安全成立；有限非 B 点位运动资格失败；此分支未训练 learner；在本条件的已测集合中仅 B 合格；全连续区间、独立泛化及净效率均未证明。该结果支持重新检查动作轴的可行支持，不能据此给整个 RL/IL 家族下失败结论。

独立证据：[REVIEW.json](continuous_scale_v1/development_axis_capacity_v1/closed_V8DEVCAP01H_review_v1/REVIEW.json)、[DONE.json](continuous_scale_v1/development_axis_capacity_v1/closed_V8DEVCAP01H_review_v1/DONE.json)。REVIEW SHA `918950785a526f9f52913e35fa9e28da0122d276fb728a4541ade2e6b619f2f5`，DONE SHA `5a7e36ffd3182024ad51417e2607cd7d012369086cb05c2e2b240d81d5036dc0`。原 FINAL SHA `594c227032c59c00f7046000431121ce1ecaf1bdcb2a40dbe52d9eeb3b899a74`；原 λ1 gate SHA `24a86f4a20bc3a709525779042063791ea1b2948c510dbc0374c41c83e3f2005`。
