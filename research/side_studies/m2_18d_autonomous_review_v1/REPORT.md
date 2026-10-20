# iHEAR Lab 自主研究与验证 v1

本轮未建立新的可靠协调策略；已完成可复核的机制干预与失败边界诊断。 新额外降力里程碑：未成立。本轮改进是固定参数的机制分离检验，没有修改正式B、物理模型、安全执行链或门限。

## 1. 最重要瓶颈与选择理由

主要瓶颈是完整运动资格对合法状态敏感，而不是开发参数不可复现。原B=1438.613498467、冻结18D=1400.697221153 N·s，2.635613%收益已从本轮新物理精确复现。最近N2虽降力仍因膝最大加速度比1.249192>1.10失败；历史0/4另存。Waypoint局部能改变运动，但既有18D+S全程力效应微小、正负抵消，不能优先把它当降力主机制。优先级及来源见PRIORITY_AUDIT。

一个关键诊断边界：N2原18D膝峰约90.059°/s²，反而低于若干通过prefix的绝对峰；它相对匹配B的72.093°/s²超限。原门是逐状态非劣等研究合同，并非跨状态统一临床阈值。因此既不能以“别的状态峰更大也通过”取消N2失败，也不能仅凭该失败宣称N2绝对临床风险最高。绝对安全与relative motion资格分别报告。

## 2. 修改及原理

C仅将OUTBOUND速度common/differential/tilt三个系数（零基3/4/13）归零；其他位置系数、全部RETURN和两个native plateau保持。测试“终端速度偏置引起去程运动负担”的假设，同时争取保留姿态降力。若C科学失败，按事前合同最多使用R：全部9个OUTBOUND系数减半。完整参数见CANDIDATE/BOUNDED_REPAIR；原18D永不覆盖。控制器仍从因果B目标与当前reference生成轨迹，实际目标/时序会通过闭环变化；没有声称所有waypoint或真实运动不变。

原rich_planner、matched fork、analyze_matched与安全链源码只迁移根路径；改动是隔离campaign的候选表示与验证编排。数学18组直接生产公式测试通过；完整参数、plateau、RETURN和motion协议身份通过；imports与源码闭包通过。辅助加入tracking/torque/参考/真实运动诊断，保存独立计算路径。不训练任何RL/Q/Neural Q。

## 3. 完整物理结果

全部JF为完整TASK、原5ms force左积分；相对B为同完整live父状态的匹配B；相对E为同组冻结18D。确定性repeat不增加状态分母。

|组/臂|完整JF N·s|对B降力%|相对E ΔJF N·s|motion|失败项|
|---|---:|---:|---:|---|---|
|reproduction / B|1438.613498467|0.000000|+37.916277|PASS|无|
|reproduction / E|1400.697221153|2.635613|+0.000000|PASS|无|
|N2 / B|1444.351653542|0.000000|+34.790044|PASS|无|
|N2 / E|1409.561609567|2.408696|+0.000000|FAIL|acceleration_deg_s2/max_abs|
|N2 / C|1418.783724255|1.770201|+9.222115|FAIL|acceleration_deg_s2/max_abs|
|N2 / C_repeat|1418.783724255|1.770201|+9.222115|FAIL|acceleration_deg_s2/max_abs|
|N2 / R|1416.545092087|1.925193|+6.983483|FAIL|acceleration_deg_s2/max_abs|
|N2 / R_repeat|1416.545092087|1.925193|+6.983483|FAIL|acceleration_deg_s2/max_abs|

N2主要数值：

|臂|膝加速度最大值°/s²|对B比值|完整moment Nm·s|hip/knee tracking RMS°|
|---|---:|---:|---:|---|
|B|72.093488|1.000000|98.691239|0.480696 / 0.456821|
|E|90.058623|1.249192|105.574975|0.472985 / 0.516925|
|C|95.813413|1.329016|106.397810|0.470932 / 0.526299|
|C_repeat|95.813413|1.329016|106.397810|0.470932 / 0.526299|
|R|88.223119|1.223732|105.375421|0.473131 / 0.515854|
|R_repeat|88.223119|1.223732|105.375421|0.473131 / 0.515854|

所有phase积分/时长、raw velocity/acceleration/jerk、剂量/ROM、tracking、moment、clearance、torque/contact与绝对安全细项、task与receipt/causal在EXPERIMENT_RESULTS、原MEASURED与独立INDEPENDENT文件。motion FAIL保留，不能以降力晋级。对应的issued reference、actual command和native Human q/dq分层存档。

## 4. 真正通过的测试与证据范围

新B/E复现包括全部trace字段、每条116320 native状态/contact/torque行与5817 receipts的物理/来源字段；host profiling不作为物理同一性。每组完整live fork继承隐藏状态，所有臂full hash相同，父在每臂后不变并继续完成原B。独立脚本不导入controller/plant，从原raw重算完整及phase积分、tracking、native导数/剂量和逐步receipt所有权；每个已完成组的独立复核均PASS。具体通过数量以VALIDATION_RESULTS和ATTEMPT_ACCOUNTING为准，不把数学结果代替物理资格。

本轮未见prefix新配对=0，选定候选motion PASS=0/0；联合原task/safety/motion/causal与>=1%B降力PASS=0/0。选择仅依据已暴露N2开发，不按U结果重选。若未触发U，分母为0，不能声称通过或失败的泛化率。

## 5. 是否有可重复进步及适用范围

本轮未建立新的可靠协调策略；已完成可复核的机制干预与失败边界诊断。 候选/备选失败属于有信息的科学负结果，不能命名为新基线。 本轮没有把微小JF差异包装为实质性降力。确切repeat资格见audit/*REPEAT；重复只说明确定性，不证明新状态泛化。

仅同一已暴露Human/model、PHYSICAL_LEVEL1 scientific simulation；prefix是实际原native执行后fork，完整JF包括共同前史，OUTBOUND0已消费。不是不同患者、未见完整初态、正式Native LEVEL2、host-clock LEVEL3、真机或临床资格。原strict/R2/FAST/plan_age负结果保留，scientific模式不覆盖host-clock资格。

## 6. 下一阶段

继续传统协调方法：先针对去程终末重规划/制动与实际闭环响应建立小型配对合同，保留位姿/速度分离表示和全部原motion门。暂不扩大Waypoint力搜索或训练Q-learning。 Waypoint作为局部可认证shape能力仍有价值，但平顺性需独立目标/约束，不能当累计force的单一代理。本轮尚不能直接启动无边界的18D+Waypoint联合优化。可以准备因果state/action/feedback schema与失败保留规则；需要先稳定传统协调方法的适用域，再讨论Q-learning数据采集和训练。

## 7. 保护、计时与退出

T0=2026-10-17 13:26:19北京时间；硬截止17:26:19。报告生成时约0.395小时。物理START/END=10/10，上限40；实际新增native步=805240，继承前史不重复计。所有失败、repeat和异常保留，不为耗尽时长扩大搜索。最终owned进程、Git/历史保护、执行manifest、磁盘与交付文件核验见PACKAGE_VERIFICATION；只有该文件PASS才视为交付完成。Windows为审阅镜像，完整source/raw在canonical WSL新包。无commit/push/merge。完成后STOP，不自动开启下一研究包。

## 8. 相位积分、边界结构与停止理由

|N2臂|OUTBOUND JF|HOLD JF|RETURN JF|完整TASK s|绝对安全|causal receipt|
|---|---:|---:|---:|---:|---|---|
|B|731.563958536|54.394314010|658.393380995|19.030000|PASS|PASS|
|E|715.964908490|54.394332693|639.202368384|19.030000|PASS|PASS|
|C|725.187027258|54.394328470|639.202368526|19.030000|PASS|PASS|
|C_repeat|725.187027258|54.394328470|639.202368526|19.030000|PASS|PASS|
|R|722.948393613|54.394330017|639.202368456|19.030000|PASS|PASS|
|R_repeat|722.948393613|54.394330017|639.202368456|19.030000|PASS|PASS|

N2原E与C的末段结构见MECHANISM_FINDINGS.md：在hip已到goal、knee尚未到goal时，额外协调意图被原范围门拒绝，原B继续在改变后的状态上选目标、通过速度与终末时长。C去除显式去程速度偏置后，下一native膝通过速度反而从约8.862增至10.036°/s；全程issued膝加速度峰下降，实际膝峰却上升。它支持继续研究目标饱和/末段停止几何与闭环响应，不能唯一归因于任一分量。参考C2与certificate PASS并不自动保证逐状态motion非劣等。

![N2完整物理比较](figures/N2_full.png)

已按预注册有限分支完成或触发停止门，因此未为填满3–4小时目标继续低信息量physics。实际耗时另见PACKAGE_VERIFICATION；四小时是绝对上限，不将提前结束伪称达到时长目标。未触发的新prefix没有消耗，也没有宣称其验证通过。失败记录与未见验证状态均保留。
