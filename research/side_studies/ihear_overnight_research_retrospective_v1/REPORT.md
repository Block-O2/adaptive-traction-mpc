# iHEAR夜间研究探索与完整研究史复盘

## 给用户的十个核心回答

1. 最初要解决什么：让机器人完成康复运动，安全、平顺地降低人与机器人累计交互力；最终希望少数重复运动后适合该患者。早期先用Spring2D和独立Human模型建立控制/辨识基础，完整robot+cuff+被动Human是后来逐步形成的。
2. 最重要的研究转变：从外部规定整条运动，变成系统在线决定下一段协调目标，并证明计划怎样由真实仿真中的机器人执行。上次教授实际汇报时间/内容仍LAST_PROFESSOR_UPDATE_UNCONFIRMED，因此给出完整历史供用户裁剪。
3. 为什么走到在线关节目标：仅跟踪预定运动不能回答怎样协调更省力；goal-only torque MPC又暴露预测/执行、HOLD/RETURN和motion问题。后来直接选择下一对hip/knee路点，原quintic仍负责中间轨迹，机器人通过cuff推动实际Human；没有直接设置人体角度。
4. B完成什么：commissioning/state-model估计、在线waypoint、scheduler/governor、current-state admission、source age、bridge/fallback与command/native-step归属已有有限科学/host证据。正式strict55/R2/FAST资格仍分包分轴保留，不能统称部署完成。
5. 学习为何没有预期收益：120D native linear固定池的state项相消，形成有用固定偏好却没学会state-conditioned排序；32×32 Neural Q的两个test state上regret较linear差。状态/候选覆盖与V_commit/V_replan监督合同都存在问题，少repetition个体化没有证明。
6. 为什么先做自由协调优化：强低force方案常以更快膝运动、更大行程或更高moment换收益。应先找完整原动力学中值得学习的运动，再决定动作接口、监督与个体化。本轮18维扩展只是隔离意图，原执行与安全底座保持。
7. 今晚实际找到什么：冻结开发最好`development_repair2_quality_NATIVE_SCALAR_18_063`的J_F=1400.697221N·s，对同完整父B=1438.613498N·s下降**2.635613%**，开发全部冻结运动/任务/安全比较PASS；比上轮2.457489%增加约0.178124个百分点。冻结新条件motion通过0/4，完整限制见下表。只声明LEVEL1，不升级原B LEVEL2、host LEVEL3或临床效果。
8. 最大未解决问题：治疗任务允许多少中间姿态/时间分配变化，力收益怎样与真实运动负担权衡，以及这些运动在更不同合法状态/患者中是否可靠。当前工程比较标准不是临床阈值。
9. 需要教授决定：中间髋膝姿态带宽；速度/加速度/jerk/剂量依据；原native离散协调还是最小自由参考接口；执行架构、低力优化与few-repetition学习的贡献优先级；2D被动Human/cuff与硬件患者之间的差距。
10. 明早怎样整理：先读PROFESSOR_BRIEF与CURRENT_SYSTEM_EXPLAINED，再用详细研究史和证据表核实理解；确认上次实际汇报边界后裁剪成15–20分钟正式PPT。本轮只提供底稿和图，不制作PPT/PDF，不发送教授。

## 本轮新运动、物理证据和范围

新增共同进度倾斜/曲率、差分进度曲率和hip/knee速度倾斜，两个方向各自独立，共18维。数学参数、发出的quintic参考、真实Human运动分开记录。原Human/robot/contact/gravity/ROM/actuator/任务合同、40ms bridge、100ms lifecycle、安全和fallback均未改变。原B零调整全数据PASS；旧10维最好嵌入18维的116320native行、5817receipts及全部物理trace精确复现，独立积分误差0。

OUTBOUND减少18.725259N·s；HOLD减少0.000006N·s；RETURN减少19.191012N·s。完整TASK原左积分与实际phase边界闭合；任务目标和HOLD保留，真实excursion/累计剂量在冻结比较容差内，不能称运动严格相同。实际完整时间B/最好=19.030000/19.030000s；B阶段={'HOLD': 1.0200000000048703, 'OUTBOUND': 9.005000000000718, 'RETURN': 9.005000000042997}，最好阶段={'HOLD': 1.0200000000048703, 'OUTBOUND': 9.005000000000718, 'RETURN': 9.005000000042997}，差值按冻结±0.1s规则检查。phase内的运动时间分配可变化，不能因此宣称治疗等效。

force peak最好/B=113.876625/115.479119N；moment积分=107.478395/100.417251N·m·s（比值1.070318）；moment peak=15.630045/15.711377N·m。最小true shank clearance最好/B=0.012330171/0.011888026m，保守session clearance=0.006963075/0.006455226m。完整绝对安全/ROM/contact/current admission/实际torque和receipt归属通过原评价，不能由reference合格直接推断physical合格。

|实际原生指标|Hip最好/B|Knee最好/B|规则|
|---|---:|---:|---|
|velocity_deg_s/max_abs|23.53073/23.78493|23.98559/26.04898|比值≤1.1|
|velocity_deg_s/p95_abs|22.81016/22.85747|22.46321/20.51200|比值≤1.1|
|velocity_deg_s/rms|15.01085/14.77572|14.58852/14.03989|比值≤1.1|
|acceleration_deg_s2/max_abs|77.56396/85.11506|116.29688/112.52679|比值≤1.1|
|acceleration_deg_s2/p95_abs|40.44759/39.90724|31.47962/29.74445|比值≤1.1|
|acceleration_deg_s2/rms|20.21255/21.89245|16.86264/17.78794|比值≤1.1|
|jerk_deg_s3/max_abs|6696.55251/5548.47008|17578.68394/18188.90376|max仅诊断|
|jerk_deg_s3/p95_abs|395.51408/400.70214|901.60226/895.49518|比值≤1.1|
|jerk_deg_s3/rms|331.50605/308.66582|688.61261/703.13716|比值≤1.1|

原45/75°/s、300/600°/s²工程限同时用于task/scheduler与原A scorer；scheduler另用原fraction .5/.25，A人体保护基于TASK采样true dq及有效因果20ms monitor窗口。这不是统一0.25ms瞬时true dq导数硬阈值。上表另按完整0.25ms真实运动raw导数比较B，两种口径不混写，均不是已认证临床阈值。

行程差Hip/Knee=[0.22516645028046867, 0.46198388627009024]°；累计角位移比=[1.0018010515232025, 1.0042065662757806]；phase/endpoint最大差=0.000730275°；phase-shape最大差=15.218600°。jerk max和phase-shape按原规则诊断，不偷改历史FAIL。完整raw统计、超阈持续时间及跟踪见EXPLORATION_RESULTS与INDEPENDENT_SELECTED_METRIC_CHECKS。

## 冻结验证与不重选

|条件|冻结方案|本条件B J_F|方案 J_F|下降%|motion|失败项|
|---|---|---:|---:|---:|---|---|
|V1|frozen_best|1428.194910|1396.465447|2.221648|FAIL|velocity_deg_s/p95_abs|
|V1|frozen_secondary|1428.194910|1400.835327|1.915676|PASS|无|
|V2|frozen_best|1449.625118|1413.323905|2.504179|FAIL|acceleration_deg_s2/p95_abs, endpoint_phase_boundary|
|V2|frozen_secondary|1449.625118|1417.807449|2.194889|FAIL|acceleration_deg_s2/p95_abs, endpoint_phase_boundary|
|V3|frozen_best|1435.397179|1404.105028|2.180034|FAIL|velocity_deg_s/p95_abs, acceleration_deg_s2/p95_abs, excursion|
|V3|frozen_secondary|1435.397179|1408.015350|1.907613|FAIL|acceleration_deg_s2/p95_abs|
|V4|frozen_best|1438.142636|1402.016641|2.511990|FAIL|acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, jerk_deg_s3/rms, excursion|
|V4|frozen_secondary|1438.142636|1405.448143|2.273383|FAIL|acceleration_deg_s2/max_abs, acceleration_deg_s2/p95_abs, excursion|

固定四条件primary分母：实际attempt 4/4，完整任务4/4，正降力4/4，正降力且全部motion/物理/因果比较合格0/4。未完成时full J_F不可评价，不用partial力排名。

事前冻结secondary `development_repair2_quality_NATIVE_SCALAR_18_056`的开发下降2.310981%，选择规则为开发合格且降力≥1%中最小最大约束比；四条件合格1/4。它是独立事先声明的保守参考，不能因测试较好而重新命名为primary或新未见最优。两个冻结方案的实际测试收益都逐行报告。

开发参数在2026-10-14T05:16:39.347658+08:00冻结，之后不根据验证重选或修复。四条件均同一已暴露Human、合法原native前缀前向生成状态，不能冒称跨患者。共享prefix消费的原slots不属于整串原策略的未见验证。primary和secondary均事前冻结，secondary结果不用于改选primary。真实OUT/RETURN边界状态、配对完整初态与pre-intervention negative control见VALIDATION_RESULTS。

## 低力负结果与优化局限

本轮最低力代表`development_repair2_repair_C2_pair_1_2_116` J_F=1196.685445N·s，降低16.816751%，motion=FAIL，失败项['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'RETURN_duration', 'excursion', 'cumulative_dose', 'task_duration', 'moment_integral_Nm_s', 'tracking']。失败方案保留，不能称高质量teacher或临床舒适。不同真实运动区域包括旧合格teacher附近、B0无原residual起点及C2强低force修复，不只是单一旧参数缩放。

- QUALITY：完整实际候选45，motion通过9；最小最差约束比候选下降2.310981%，最差比0.968732，失败[]。
- ALTERNATE：完整实际候选24，motion通过2；最小最差约束比候选下降0.000000%，最差比0.952381，失败[]。
- REPAIR：完整实际候选28，motion通过0；最小最差约束比候选下降16.545288%，最差比2.464332，失败['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/max_abs', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'excursion', 'cumulative_dose', 'endpoint_phase_boundary', 'moment_integral_Nm_s', 'tracking']。

区域最小约束比仅是负担修复诊断，不是冻结primary的替换选择；完整具体约束与16个新增轴probe见MECHANISM_ANALYSIS。单轴probe和共同优化结果不能等同于最终参数逐轴ablation，因此不声称某一个自由度独自贡献全部新增收益。

有限COBYLA终态和实际调用保留OPTIMIZER_STATUS；预算终止不等收敛，全局最优或物理收益上限未证明。≥2%是研究里程碑，上轮已达到；本轮未找到满足全部开发motion规则的≥5%方案，不能用motion失败的低力方案代替。

## 分母、失败、资源与保护

实际新physical START=148/200，END=148；包含冷父、fork、optimizer真实rollout、失败/中断及验证，不计数学拒绝为physics，也不漏首次commissioning失败。完整评价140，本有效开发新候选113，其中motionPASS=23；实际完整运动序列去重数=128，重复不增加患者或独立state分母。已知真实新增native步=11457340，总量精确=True。

两轮有界physics包装修复及原代码/错误/partial均保留：成员名遮蔽；标签不一致。后者数值物理完全相同也未直接放宽严格门限，恢复标签后重新通过。非零returncode事件2个，不隐藏失败。另有数学越界提案仅在LEVEL0拒绝，不调用physics。

主Git初始branch/HEAD/index/已暂存与未暂存diff保持；晚捕获tracked/untracked字节与symlink名称另列，不能冒充t0全部字节快照。原复用源码/模型/权重和历史报告保护范围见PACKAGE_VERIFICATION与独立审计，不宣称所有旧raw仍存在。普通本包raw仅在完整原评价、motion/receipt/积分核验后报告化；关键B/最优/强失败representative的完整raw保留。无旧数据删除、Git mutation、系统配置/存储维护或新定时任务。

包核验状态=PASS；大小GiB=3.4359032809734344；D真实剩余GiB=90.01573181152344。核验PASS仅表示保护/预算/文件/退出等合同，不等于科学问题全部解决。最终以PACKAGE_VERIFICATION.final与owned退出为准。

## 阅读与下一步

详细研究史不是REPORT拼接：原模型/权限、固定参考、高ROM失败、两次运动架构转变、B、E/Q/Neural、负担、counterfactual/fork与自由参考按问题因果组织。80条证据各附source、分母、等级、验证范围与明确的INFERRED因果解释。上次实际教授汇报边界仍未确认，不编造教授已知内容。

唯一推荐下一步：用户审阅8页教授底稿，与教授先确认治疗姿态自由度和运动质量评价依据，再冻结下一轮不同合法state证据/最小接口迁移合同。本轮不自动开始新包。

图表阅读见[FIGURES.md](FIGURES.md)，参数与16个新增轴probe、真实reference/torque/Human变化见MECHANISM_ANALYSIS.json，最小只读重算与历史physics命令见REPRODUCTION.md。

本次物理工作已停止；最后physical END与退出、时限合同见PACKAGE_VERIFICATION。停止不表示临床或学习目标已经完成，保留所有负结果供明早讨论。

根目录PHYSICS_STOP.json保留的是早期包装失败的历史事件；最终关闭以STATE.json、各LAUNCH/WORKER_EXIT及PACKAGE_VERIFICATION为准，不删除历史错误来制造全程无失败。
