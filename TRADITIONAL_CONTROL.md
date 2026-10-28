# 传统控制：基线、扩展权限与验证边界

本阶段保留 B、历史 E/10D/18D、T/D/H150、modal8、平顺性和固定阶段组合。**不存在跨 Human、介入时点及全部指标统一的赢家，也没有全局最优证明。** 主复现选择 v7 `DEVPC02_TRAD_COMBO` 及同父 B/V6PHASE，原因是它保留完整原门并相对强固定 phase 得到小幅 JF/JM 双降；同时保留 D01R B/H150 的历史对照。它不是比所有方法低 JF，也不是所有指标都降低。

## B 的真实含义

B 是被保护的 robot/cuff 测量—Human 估计—在线 finite waypoint MPC—quintic scheduler/governor—current-state admission—feedback/cuff allocator—六轴 torque—native Human/contact 闭环底座，基础 value hook 为零。它不是固定的 Human 角度轨迹，也不是直接 PD torque 控制器。

历史基准的 commissioning 之后采用冻结 commissioned belief；在线观测更新不能称为 TASK 内持续模型学习。`CURRENT_RESEARCH_BASELINE.md` 保留 2026-10-14 原界定。`b_fast_runtime_completion_v1`、`b_hold_return_critical_path_v1` 等提速路线的失败、资格轴和 NOT_FROZEN 状态都需要保留，不能让新的科学仿真结果覆盖旧 host/R2 失败。

## 历史权限演进

|方案|实际修改位置|必保留的条件/限制|
|---|---|---|
|E/offline teacher、CEM/COBYLA 等|隔离的有限参数/候选搜索|是有限搜索 best-known，不是证明全局最优；搜索预算和失败同样重要|
|10D/18D `RichFreePlanner`|当前原 B 内部 waypoint 的 common/differential 多项式偏移及通过速度倾斜|不改 plant/任务/原认证；不是所有“18”文件名都表示18个自由参数|
|T `TerminalRepairPlanner`|原18D底座上的终末处理|继承原参数和历史状态资格；不能只取低JF忽略motion失败|
|D / `RoundPlanner`|限定内部 RETURN 槽的小姿态改动|±0.3°范围；保持原时长/通过速度，禁止改任务终点|
|H150|T + RETURN内部姿态/时长 + 最后 hip duration×1.5|末端膝 reference 必须已恒定；不满足时原断言中止并保留partial|
|modal8 / modal8_retimed|O/R共同路径、相对路径、局部时间、通过速度八轴|逐关节终点锁和retimed scheduler比旧18D权限不同，不能混成同权限搜索效率对照|
|HANDOFF/PATTERN/COMPOSE/BLEND/固定phase|冻结参数在特定phase/decision slot的部署或组合|完整任务重验；短时 tail 好不等于完整原门合格|
|TRAD_COMBO|固定phase基础上的两个已测 RETURN 时间/通过速度坐标组合|局部微小双降；几何变体双成本反转，原门与额外quality分别保留|

18D 在 `runtime/code/rich_planner.py` 的 common/differential 变化采用 `e=sin²(πm)`、`u=2m−1`，形式为 `c=e(x_j+x_k u+x_{k+1}u²)`、`d=e(x_{j+1}+x_{j+2}u+x_{k+2}u²)`，再将 normalized target 改为 `p+[c+d,c−d]`；通过速度另有 common/differential 倾斜。精确索引/scale 见各包 `runtime/PARAMETER_MAP.json` 和冻结 `FROZEN_18D.json`，不应从归一化表反推四舍五入参数。

modal8 定义在 `source/acl2_modal_planner.py` 与 `acl2_modal_retimed.py`：`[O_common_path,O_relative_path,R_common_path,R_relative_path,O_local_time,R_local_time,O_pass_speed,R_pass_speed]`。原 modal 对非终末目标加 `0.30° × sin²(π(slot+.5)/6)` 加权路径偏移；局部时间与速度约为 `1+.08 x_t w`、`1+.12 x_v w`。retimed 版本还执行逐关节 endpoint lock 和 duration重新编译，实际选择后的 reference/certificate/receipt 才是执行事实。

## H150 精确配方

`D01R_PLAN.json` 的冻结 H150 以 `FROZEN_18D` 和 T 为底座：RETURN 槽2/3的内部姿态为 `[+0.3,-0.3]°`，槽1/4 duration factor 为 1.1/1.2，槽5 hip terminal timing factor 为 1.5。候选 hash 为 `255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931`。源码依次经过 `RoundPlanner -> EarlyReturnPlanner -> TerminalTimingPlanner`，每次重验原可行性，拒绝时取原执行候选。

H150 不是全程变慢50%，不是独立训练得到的 policy。RETURN5 分支要求目标膝位置等于当前膝 reference、起止膝速度为零且保留任务终点；不能在重型失败时删除断言让它继续。v8 的“可选timing适用规则”是另一明确版本：只在原恒定膝前提满足时请求可选 timing，不能把它写成原 H150 的历史行为。

## 历史代表性证据

下表是历史结果，来源与条件分别列出；不能跨行分母排名。

|身份/条件|B JF N·s|方案 JF N·s / JM N·m·s|原结论|
|---|---:|---:|---|
|canonical 18D开发 `development_repair2_quality_NATIVE_SCALAR_18_063`|1438.613498|1400.697221 / 见原包|JF降2.635613%，同条件完整19.03s；新合法prefix原motion 0/4|
|D01R历史W1暴露状态，原B/H150|1436.456498|1402.643211 / 见原MEASURED|有限相同prefix资格，不能与canonical分母混用|
|v6 DEV_O1 BEST|1436.857076|1398.390951 /107.878478|低JF，但JM高于B，平顺性非统一改善|
|v6 DEV_O1 HANDOFF|同上|1402.115273 /107.682017|jerk/force-rate改善与JF/JM权衡|
|v6 DEV_O1 PATTERN|同上|1403.088895 /106.082150|同条件完整原门PASS|
|v6 DEV_O1 COMPOSE|同上|1406.467015 /105.968333|同条件完整原门PASS|
|v7 DEVPC02 V6PHASE|1437.971420|1405.990071 /105.481425|固定OUT1 HANDOFF后共同COMPOSE|
|v7 DEVPC02 TRAD_COMBO|1437.971420|1405.935078 /105.464006|较phase ΔJF−.054993、ΔJM−.017419；相对B仍JM增加|

canonical 来源为原 [CURRENT_RESEARCH_BASELINE.md](CURRENT_RESEARCH_BASELINE.md)；D01R 来源为 `research/side_studies/ihear_overnight_control_learning_transition_v1/reports/D01R_{B,H150}_MEASURED.json`；v6 来源为 `research_archive/packages/smoothness_critic_integration_v6/SMOOTHNESS_BASELINE_COMPARISON.md`；v7 来源为 `research_archive/packages/autonomous_learning_smoothness_v7/BASELINE_AND_PAIRED_OPTIMIZATION.md` 和 `MOTION_FORCE_MOMENT_TRADEOFF.md`。所有有效位应以JSON/CSV为准。

v7 DEVPC02 同父完整运动指标为：

|方案|髋/膝 raw jerk RMS °/s³|4kHz force norm rate RMS N/s|4kHz moment norm rate RMS N·m/s|
|---|---:|---:|---:|
|B|305.097 /715.575|20.8754|3.3881|
|V6PHASE|296.249 /635.141|18.2940|2.8469|
|TRAD_COMBO|296.433 /635.566|18.2918|2.8467|

TRAD_COMBO 较phase jerk约增加 .0622%/.0668%，在冻结额外 .1%界内，并非所有运动指标严格下降。两冻结prefix PFXV01/02相对phase分别 ΔJF−.055297/−.060341、ΔJM−.017448/−.017941；short_segments 几何变体通过原门/额外quality但双成本反转。应保留正负迁移，不能只展示两个正例。

v5→v6 的历史 `HANDOFF01_BEST`、`HANDOFF01_BOTHLOW`、`OPT01_PATTERN011`、`COMPOSE01_PAIR01` 与 `STRICT01_ANT` 保留全表：其JF约1398–1406，jerk/力变化率与moment有不同取舍。v6 `SMOOTH_A1` 的 BEST 完整原门失败，COMPOSE合格；BLEND虽原门合格但冻结90%平顺性保留失败。这些是强传统对照的必要失败证据。

## 跨 Human 与时机

v7 的名义/轻型/重型简单 H150 对照显示：名义与 light_soft 完整但膝 excursion 超界，heavy_stiff 完整合格；因此旧H150的历史资格不覆盖新Human。light_soft 的某phase差0.511°超过原0.5°门，不能将低JF当合格收益。重型某些晚启 modal方案在 RETURN5 违反原恒定膝前提而中止，partial无排名。

heavy_stiff 的 OUT0早启 H150 相对同父晚启：JF `1623.978610→1619.095307`，JM `121.893646→122.098966`，髋/膝jerk RMS `1392.404/3864.999→318.960/662.698`，力模长变化率 `65.7073→21.6503`。这是既有传统控制器的部署时机效果，不能记为Learning增量；JM仍高于B。晚启时大部分jerk平方已经发生，任何只预测剩余tail的模型都无法追回过去成本。guard中介是否唯一物理成因尚未证明。

## 完整资格顺序

完整原任务、硬安全、receipt因果有效、matched任务和原motion先决定能否排名。`analyze_matched.compare` 保留原研究阈值：velocity/acceleration 的 max/p95/RMS 与 jerk p95/RMS burden 比例≤1.1，excursion/endpoint/phase boundary差≤0.5°，累计travel在 `[.95,1.05]`，总时长及每phase差≤0.1s，JM≤1.25B，force/moment peak≤1.05B，tracking RMS增加≤0.5°。原绝对安全/scorer还必须通过。额外quality界与原资格分账，不可事后放宽或以加权低cost补偿原门失败。

原TASK积分使用200Hz measured wrench模长左积分，native jerk采用4kHz原qvel二次差分，raw必报、SG5/21为敏感性分析。不删首尾、裁峰、缩窗或替换为平滑后的主指标。参考C2连续、native jerk数值峰和临床舒适度是三个不同结论层。

## 主要便携复现入口

1. `deployment/reproduce_trad_combo.py`：v7 DEVPC02 的B/V6PHASE/TRAD_COMBO三臂，保留同父和原评分闭包，作为本归档的强传统主入口。
2. `deployment/reproduce_traditional.py`：D01R原B/H150两臂，保留历史合法prefix和19.03秒完整任务。
3. `deployment/reproduce_original_b.py`：原m2冻结源码、seed2026101303、无prefix、19.03秒完整B。精确核对现存原源码并恢复三个同hash依赖；不宣称已与旧raw逐字段相同。
4. `deployment/score_b_h150.py`：对已保留D01R fixtures离线复算，不能代替新动态闭环验证。

三个动态入口都只在全新scratch复制源码与配置，重绑定字面本机路径并记录逐文件hash；新的host deadline/timeout只是本轮执行允许时长，不改模拟任务时长、控制参数、plant、scorer或安全层。TRAD_COMBO launcher显式省略原可选跨包历史raw一致审计，保留原完整任务/motion、receipt和同父raw gate，故仅凭它不宣称与旧轨迹逐字段相同。最终实际运行状态见 [ARCHIVE_VERIFICATION.md](ARCHIVE_VERIFICATION.md)。
