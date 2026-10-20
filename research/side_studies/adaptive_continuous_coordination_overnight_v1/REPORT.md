# iHEAR 连续协调夜间研究报告

**结果：基线与数学原型通过，新增非零曲线的物理接口未过门，按条件分支停止降力搜索。没有发现新的合格低力运动。** 本轮没有为耗尽8小时或160次预算继续无资格搜索。

## 明早的十个回答

1. **waypoint密度受什么限制？** 首先是原请求处“一目标/通过速度→单段2×6 quintic→路径证书/当前状态准入”的合同，以及端点触发时机。不是数学上不能加点。当前同条件B/18D各14次TASK请求、14个ACTIVATED、10次实际suffix splice，不能和candidate count、K3 knots或FAST steps混用。SOURCE_CONFIRMED / TRACE_VERIFIED。
2. **更多控制点增加实际运动自由度了吗？** 数学上增加了：28段冻结schedule的等价加密通过，局部点更新产生约.005299rad变化且支撑外差约6.11e-16rad。但非零多段曲线被旧2×6载荷合同拒绝，实际新增非零曲线执行0次；只验证零修改精确折回旧曲线。MATH_VERIFIED；新增物理权限UNRESOLVED。
3. **速度起伏主要怎么解释？** reference本身分段加减速、固定通过速度与内部端点a=0是源码线索；终末另有真实tracking响应。原C2不等于恒速或jerk连续，尚无消融量化各机制份额。SOURCE_CONFIRMED / CORRELATIONAL / UNRESOLVED。
4. **force与运动变化哪些区间相关？** OUT/RETURN收益18.725259/19.191012N·s；最大1s收益15–16s为9.996502N·s。4–6s收益10.099746N·s，但部分区间TV_a增加。完整TV_v下降10.633%左右，TV_a仅下降.332%左右。高力也出现在较低加速度区间，不能仅优化jerk。TRACE_VERIFIED，因果未分解。
5. **哪种连续表示值得继续？** 选显式内部q/dq/ddq的局部C2 quintic链，B-spline保留备选。理由是原曲线精确限制、相邻两段局部更新、可复用degree5约束数学核；没有声称物理上优于B-spline。MATH_VERIFIED / INFERRED。
6. **只改速度、只改协调、联合优化各怎样？** 数学原型已证明路径与clock可分开改变；S/P/J三个方向物理搜索均为NOT_RUN、0次，因为M6/P1未满足。不会把旧18D混合作用归成新S/P/J实验。
7. **有优于1400.697221N·s的完整合格运动吗？** 没有。本轮新完整复现B=1438.613498467、旧18D=1400.697221153N·s，均开发评价PASS；旧18D相对同条件B下降2.635613%。这是已知单一开发状态的数值复现，不是新的改进。PHYSICAL_LEVEL1（旧路径复现）。
8. **新状态验证保住收益与motion了吗？** 本轮没有新的合格冻结策略，新验证0/0，至少30次预留未使用。旧PRIMARY历史四个合法prefix仍完整4/4、正降力4/4、正降力且motion合格0/4；旧SECONDARY为1/4，均同一已暴露Human。HISTORICAL_REPORTED；本轮不重选、不升级泛化。
9. **跨重复改进可测试了吗？** 尚不具备本请求的先决条件：新非零物理接口和新合格改进未建立。实际跨重复0次，仅交付接口设计。UNRESOLVED。
10. **下一步优先做什么？** 优先完整多段路径物理接口/证书，之后再运动优化；当前不应优先扩参数或训练学习模块。本轮不自动启动下一包。INFERRED，见NEXT_RESEARCH_DECISION。

## 本轮实际做了什么

T0登记：2026-10-15 03:42:21 Asia/Shanghai（UTC 2026-10-14 19:42:21）。最晚新START截止10:42:21、最终截止11:42:21；本轮提前在接口门处结束物理工作，最终实际结束时间见STATE。最长8小时是上限，不是必须运行时长。

环境实际确认：Ubuntu-Research-Verify；主仓库`/home/hank/coding/adaptive-traction-mpc-learning`；Side Studies目录与指定Python存在。指定Python解析到既有基础环境解释器，未重装依赖；MuJoCo3.10.0、NumPy2.2.6。启动可用内存约6.7GiB、32逻辑CPU、Linux磁盘余约822GiB。物理串行、BLAS线程1，无CPU/WSL/系统参数修改。

新包：`/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1`。只从已核验1376文件manifest选择隔离源码，路径迁移有原/新hash；模型/配置/native/权重249项另列。实际初始import129个研究模块，外部研究源码导入0。主Git起始branch为`codex/expert-strength-value-adequacy-v1`，HEAD `8bb04662b1578b72c097f546be9e836167e280e8`；没有创建或切换分支。

首次只读git状态保存为逐文件2293行，不能将旧报告的332 staged/39 untracked目录口径代替本次实际逐文件分母。启动后、任何物理运行前还记录6141个主仓库文件/链接字节hash；这个较晚内容快照不冒充T0完整字节镜像。

## 新物理工作与基线门

|新attempt|完整J_F N·s|任务/绝对安全/receipt/motion|性质|
|---|---:|---|---|
|baseline_parent|1438.613498|PASS|合法冷父，完整前向动力学|
|baseline_B0_original|1438.613498|PASS|同完整父状态fork、原B零修改|
|baseline_frozen18D_identity|1400.697221|PASS|旧冻结18D身份/参数复现|
|baseline_zero_exact_refinement|1438.613498|PASS|数学加密后严格collapse，返回原不可变schedule/证书|

共4/160 physical START、4 END、returncode均0，包含父状态与三个fork。3/3配对baseline arm完整PASS，父状态另1次；数学reject不算physics，pre-START包装失败也不冒称物理运行。真实新增native步=344680，实际新增仿真时间=86.170000s。不能把每个fork中继承的commissioning前缀重复计入新增steps。

原B与零修改折回方案、原B与父：全部trace字段、116320个native行和5817条receipt逐字段精确等价。新B/旧18D与各自历史raw另独立核验：每对116320行身体qpos/qvel/contact/applied torque、5817条receipt精确相同。SCI wall profiling时戳有意不作物理身份字段，不据此声称host-clock同状态。完整fork恢复hash与父状态未变记录均PASS。

独立脚本重新计算4次完整J_F、phase积分/时长、moment积分、tracking、native dq的raw acceleration/jerk与运动统计。没有导入runner/plant/optimizer；这是独立核算脚本，不是独立人员或独立agent审核。

18D的moment积分从B的100.417251增加到107.478395N·m·s（+7.031803%）。force降低并不意味着其他交互负担同时降低；motion是冻结工程比较门（包括10%非劣等），不是临床阈值或严格治疗等效证明。

## 数学成功与物理接口失败的边界

A/B两种原型对28个冻结多项式通过M0/M1；A的M2/M3/M4/M5通过。M0范围明确是选中的原quintic多项式，不把采样trace拟合称整个governor/bridge连续链精确恢复。

首次M0 exact系数断言发现8.88e-16差，保留失败，仅修复一次浮点减法顺序，门限不变。一次有限旧schema适配把内部加速度强制归零，产生.001774082rad位置、.018061431rad/s速度、.656758031rad/s²加速度误差，M1失败。不能为过门放宽精度。

原构造器对4×2×6多段系数拒绝；保持外部q/dq/ddq与总时长时单段quintic边界矩阵满秩，压回端点会丢失新增内部.3°变化。原当前准入、tracking-offset clearance及fallback证书绑定单段coefficients。只改sample却保留旧proof会认证另一条路径，这个捷径未实现、未执行。

**P0仅“精确折回原曲线的零修改baseline”通过；不是多段对象直接物理执行成功。M6/P1对非零曲线未通过，P2新曲线不可评价。** 原pickle传输并不强制端点压缩，原rolling composite也有已认证prefix/suffix功能；缺的是任意多段曲线完整载荷与同路径证书合同。不能宣称扩展不可能，也不能无资格继续force优化。

## 负结果、冻结纪律与科学限度

历史强低力代表J_F=1196.685445N·s，仍因速度/加速度/jerk、时长、行程、剂量、moment、tracking等FAIL；完整历史raw已复制、独立重算保留，不是本轮新候选或高质量teacher。

PRIMARY/SECONDARY均为null，没有命名虚假赢家。S/P/J optimizer真实调用0；新状态验证0/0、跨重复0。30次验证预算完整保留。旧PRIMARY的0/4不因本轮复现开发PASS而被改写。1000N·s/约30%只是远期目标，本轮未证明可达，也未证明全局收益下限。

工程包装/检查错误与数学修复分列audit/ENGINEERING_ERRORS，初次baseline缺配置发生在START前、原日志保留；4次实际物理运行无错误。原Human/robot/contact/gravity/ROM/torque/task/HOLD、安全阈值、truth firewall、40ms桥、100ms生命周期、fallback及receipt/native ownership未修改。没有训练RL/Q/MLP，没有硬件动作，没有外部发送、Git变更命令或历史证据删除。

## 图表与交付

- figures/cumulative_force_motion.png：原B/18D force、完整积分、moment。
- figures/force_benefit_vs_velocity_variation.png：actual/reference TV_v、actual TV_a与force收益对齐。
- figures/reference_actual_and_events.png：真实/参考速度与request/activation/splice。
- figures/refinement_equivalence.png：数学加密等价。
- figures/local_control_effect.png：局部路径、时间与B-spline数学效应。
- figures/development_and_historical_validation.png：本轮开发条件复现与明确标为历史的0/4验证；不是新held-out图。

新非零运动真实q/dq/force图及密度—motion—J_F关系图未绘制，因为新非零物理样本0；不会用数学曲线暗示已经执行成功。

运行/门/冻结/验证/预算见RUN_PLAN、STATE、ATTEMPTS、CODE_MANIFEST、MATH_VALIDATION、PHYSICAL_INTERFACE_GATE、EXPLORATION_RESULTS、FROZEN_SELECTION、VALIDATION_RESULTS、PACKAGE_VERIFICATION。可复现命令见REPRODUCTION。

PACKAGE_VERIFICATION的PASS仅代表保护、文件、预算、已声明核验和owned退出合同；不等于连续协调科学假设成立。最终工程核验PASS：Git HEAD/branch/status/index/diffs和6141个主仓库文件/链接快照一致，1376个选定原源码/模型/权重文件未变；本包约0.37GiB，4 START/4 END，owned物理进程0。PASS不扩展科学资格。本轮唯一建议见NEXT_RESEARCH_DECISION。STOP。
