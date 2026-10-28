# 原开发条件的固定连续轴能力诊断（Heavy035 / Light065）

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


## 原轻型开发条件闭合补充：V8DEVCAP01L

同一原已曝光 DevLight065、seed2026102752 与原 V8BETA01L prefix 完成独立固定轴诊断；没有新参数或新患者。B 完整合格；H、独立付费 λ1、λ.5/.25/.75 均完整但运动不合格；λ0 为原工程 partial，完整 JF/JM 与完整 motion 评价为空。两个开发条件都没有在已观察固定点与旧各两 unique draw 中发现合格非 B support；λ0 的 partial 限制 L 的完整资格覆盖，不能把所有点统称 complete motion failure，不能据此证明连续域不可行。

### 实际身份与源闭包

L case SHA `cf2b735402009a7a15f6b8aff01c759579c4cfb93ac0301cc0f18803407d1ece`；config SHA `05ccedb17b49cc0d7c6b44ca63734f7fe53d742f6d73a18153945d20da2f8b73`；实际 job source manifest SHA `c0bc5561c9252c4e9556e9e1342483693ca32210ce07abd3e52a5b86385e565e`。1408 config pins、1408 actual source 文件逐项相同并重核当前 hash。原 seed/payload、B/H150、OUTBOUND `[[0.068,0.042,0.024]]` / RETURN `[[0.047,0.026,0.019]]` prefix 与原 V8BETA01L 一致；cold OUTBOUND slot0、任务/原阈值/5λ轴/600s child/1800s job/global15:25:40 均不变。

原 before-B 顺序仍为 B→H→独立付费λ1→λ.5→λ.25→λ.75→λ0；5 map entered/returned、7 physical proposals、0模型/采样。最终 `NOT_RUN=[]` 仅因为 partial 位于最后，`stop=ENGINEERING_PARTIAL_REST_NOT_RUN` 必须保留，不能读成任务全部成功。两 case 的 pure-map 是 root 原已付费操作，本次没有再调用 mapper。

### 原实际结果全部并列

|原实际 L 分支|完整|原完整资格|原 motion 失败或工程状态|完整 JF (N·s)|完整 JM (N·m·s)|原 fresh native 步|
|---|---|---|---|---|---|---|
|B|true|true|无|1293.1180212524823|91.16822044535617|76120|
|EARLY_H150|true|false|velocity_deg_s/max_abs；excursion|1256.7226985879745|96.74976355940196|76120|
|独立付费 λ1 repeat|true|false|velocity_deg_s/max_abs；excursion|1256.7226985879745|96.74976355940196|76120|
|λ.5|true|false|excursion|1266.3256332536673|95.93482164825927|76120|
|λ.25|true|false|excursion|1271.705791629818|95.7051664722749|76120|
|λ.75|true|false|excursion|1261.2141485261116|96.32476375030964|76120|
|λ0|false|false|工程 partial：KNEE_REFERENCE_MUST_BE_CONSTANT|null|null|68140|

λ0 原错误为 `NATIVE_PHYSICAL_FAILURE:V8DEVCAP01L_AXIS_L0`，protected abort 为 `NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT`；`partial_JF_unranked=1131.04144933385` 只保存在 partial 范围，不能补成完整 JF 或与完整动作排名，JM 不补。λ0 不是 B 或 zero-noop，仍为 base T 的映射。所有不合格动作的低 JF 都不算成功或优化收益。

L 的 7 个原 joined receipt 均记录11个硬安全条件全true、true_hard_safety_violation=false；完整 motion 资格失败、工程 partial 和这个硬安全子集分列。完整分支的原 physical/scientific/legacy 三轴 PASS、HOST NOT_EVALUABLE；λ0 原 row 没有这些完整轴字段，不补成 PASS。该新鲜条件的硬条件记录绝不回填旧 Beta02L 父prefix三个 UNKNOWN，旧 pending、CURRENT/训练和安全审计保持原样。

H/λ1/.5/.25/.75 各6条原 execution，状态仍为4 ACCEPTED→1 REJECTED→1 ACCEPTED；B与partial λ0的execution=[]。actual EXECUTION_BINDING.action/prediction 与原请求逐项相同，所有拒绝/fallback、空记录原样保留。

### 原等效、回放与 owner 闭合

原 H 与独立付费 λ1 全 raw 等效门 PASS：48字段、116320 native states、5817 command receipts及原 receipt/reference/source/ownership 覆盖，H运动不合格不妨碍等效核查。原 parent→B 同范围门也 PASS。λ1 是另一份实际付费 child，不能 alias 或当作未花成本。L gate SHA `3c227bdc1fab4101718c78112169d504908e051dedb336fd5e08a87ab37bfa64`。

原 parent+7child 的8份回放均 `SCORER_REPLAY_PASS`、original_result_exact_reproduced=true、case/config identity chain PASS。但其精确含义不同：parent与前6child重现原完整结果；λ0重现原 `original_mode_result=FAIL / original_physical_result=FAIL / original_scientific_result=FAIL`，motion_replay=null、qualified_replay=false，无 independent 完整JF/JM。回放自身 PASS 不将 partial 升级为成功。本次只读既有回放，不执行 scorer 或 raw comparison，也不读取 raw 文件。

原8 START/8 END全部唯一相配，7child joined、returncode0、parent_hash_equal=true；PHYSICS_DONE rows 与 FINAL/原 RESULT 相同。原已知12个 PID/startticks 全退出，worker active_child=null、SUPERVISOR survivors=[]、worker exit0。sup早期RUNNING记录保留为历史，不与最终STOP混淆。每个完整child原receipt76120步、partial68140步单列，原parent116320步另列；child END未填写native_steps不补。

旧已闭合 GateD 的light RF_RAW两种唯一 λ=.36964000897973537/.3466687202905016 均complete、原资格false、excursion失败，原 RESULT hash重新绑定；四臂付费重复不制造更多 unique 动作覆盖。本次不打开 real_runs，不读取 Beta02L 或其活跃历史来补安全状态。

### L 原资源与独立复核

|原已付费 L 阶段|原 wall|原 CPU|原 peak RSS|范围|
|---|---|---|---|---|
|supervisor|969.2984607219696 s|未单独隔离|未单独隔离|exit0、survivors=[]|
|物理 GNU time 外层|16:09.33|user958.90 s / system21.86 s|1511804 KiB|parent+7child，exit0|
|worker|967.2087631225586 s|未单独隔离|未单独隔离|全部7 child joined，包括partial|
|原8项回放外层|1:01.53|user53.76 s / system7.76 s|903264 KiB|exit0、0新物理；未记录 replay PID/startticks，保留UNKNOWN|

独立 metadata review 用1464个唯一文件hash、56 JSON、16条目标原事件，5941 checks PASS（包含读路径scope断言，不能与H的3050数值作算法效率比较）。本次review自身wall .19081926345825195s、CPU .19022139300000002s、maxRSS25000KiB、PID1253786/start63858912，已退出；这些是复核进程资源，不替代上表原执行成本。新 model/mapper/math/helper/scorer/rawcompare/physics 全0；未读活动 POSTAPP02，原冻结模型/源码/配置/阈值/clock不变。

[L独立REVIEW.json](continuous_scale_v1/development_axis_capacity_v1/closed_V8DEVCAP01L_review_v1/REVIEW.json) SHA `4dbdbd4062953676be9307fb9c0b6870c885318449ed9eb13b8305a7426e3e96`；[DONE](continuous_scale_v1/development_axis_capacity_v1/closed_V8DEVCAP01L_review_v1/DONE.json) SHA `2aaef6fcf55b5f220e6fcdedb8d0d072c43972779254fefed804ba6aabfce5da`。原 FINAL SHA `eb69326a3cbda2e391da0fcae98984be65dc0cd8e417040911d317d35ebcee6a`。H证据和先前报告保留，不以L覆盖H。

两开发条件的七层边界不变：源/映射身份成立；固定before-B决策成立；实际完整/partial工程状态与安全scope分别保留；未找到合格非B支持；无新learner训练；合格对照仅B；全轴不可行、泛化或净效率未证明。此后由主线程基于既有闭合产物绘图/封包，本分支完成最终回执后停止文件写入。
