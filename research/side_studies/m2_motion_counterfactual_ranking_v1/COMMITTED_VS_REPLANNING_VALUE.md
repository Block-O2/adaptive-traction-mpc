# Committed 与重复规划的价值合同

**合同不同；真实host同完整state价值/排序差 NOT_EVALUABLE，历史SCI rolling诊断有有限数值差。** 不能将已有80条remaining cost称为真实host-replanning policy value。

`V_commit(s,p)` 是原进程内完整fork状态开始、执行完整masked K3表的剩余force integral。`TableInterface.choose`在每个原B请求按OUTBOUND/RETURN count取当前slot；后续继续消耗同一表，slot5后zero。B仍重新构造并认证各段schedule、保留拒绝/fallback及HOLD/terminal规则。因此committed是固定residual后缀，不是整个物理command开环、不重新规划。

`V_replan(s,p)` 必须明示p的干预单位，以及随后冻结的策略。当前slot之后zero-residual B，与随后继续Frozen M2候选生成/Q排序，是不同continuation。两者都由B负责本地重复规划/认证；不能因都调用B就把价值合同视为相同。原标签p影响后续所有未issued slots，不是当前slot之后立即zero-B。

Frozen host M2的`QFirstInterface.choose`重新生成candidate、计算Q、做原生certification，更新table/carry/count；`host_adapter`在真实source年龄超时后可能执行prior carry，保留40ms bridge、100ms native lifecycle与current-state admission。Scientific fork数据的物理时钟在计算期间不推进，保留simulation-version因果检查；原wall plan_age失败仍存在。这会改变后续状态及动作机会，但本轮没有相同完整状态下两合同的对照，差值范围、方向、排序变化均不可测。

不能拿历史全任务host配对与另一个prefix/state的committed分支相减。当前0个可恢复父状态、0个同完整host state V_replan配对；本轮新增物理/host运行0。没有制造模拟host时钟或跳过原生admission来补表。

## 已存在的scientific rolling诊断：有限数值差可测

| phase | issued index | commit remaining N·s | archived rolling remaining N·s | commit−rolling N·s |
| --- | --- | --- | --- | --- |
| OUTBOUND | 2 | 989.427237 | 968.780834 | 20.646403 |
| RETURN | 1 | 511.657835 | 511.657835 | 0.000000 |

来自原DIAGNOSTIC_ANALYSIS_v1和060_v1...REPLAY_GATE；本轮重新核验原initial applied table与selected branch表完全相同、remaining=原终值−同prefix integral，原replay gate记录所有trace字段精确相等和causal context相等。OUTBOUND固定后缀高20.646403N·s，RETURN为0，已支持continuation差别不能忽略。全部为 **SCIENTIFIC_SIMULATION** 的已暴露历史诊断，不是本轮新增实验。

这个gate未证明replay接口/对象、完整RNG、lifecycle及host时钟等与原rolling进程的完整可执行state相同；它证明物理trace和可见causal context匹配。每个state只存在原selected action的一个rolling结果，没有其他candidate的rolling反事实，因此不能计算V_replan候选排序或用20.646403作为host偏差界。真实host同完整状态下的价值差仍NOT_EVALUABLE。本包没有重新运行replay；hash和重新计算在HISTORICAL_ROLLING_CONTINUATION_AUDIT.json。

下一代Q首先应保持单一、清楚命名的 **V_commit约束有限表排序目标** 作为探索性参考，记录force与真实运动/剂量等完整标签；当前结果不支持开训v2。若要声明改善重复host策略价值，必须先建立同完整state、明确当前干预单位和冻结continuation的V_replan标签及合同转移证据。即使commit预测误差小，也只能支持有限候选committed排序，不支持online personalization、跨Human泛化或临床结论。

代码路径、准确行号、hash在JSON的source_evidence；保留原执行合同，不修FAST、不改R2/strict55。
