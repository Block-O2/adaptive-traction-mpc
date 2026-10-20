# iHEAR Lab — 18D末段响应诊断与受控修复 v1

**找到N2可重复的合法运动修复，并保留18D降力优势。** 一个此前未执行的新合法prefix配对也通过，适用范围仍限同一Human。 本轮未改正式B，不修改18D参数，不训练学习器。

## 六个明确答案

1. **最早实质差异**：N2对N1 PASS从合法prefix本身已不同；0.010s issued/command分叉，描述性native q差超过0.01°在0.12850s、dq差超过0.1°/s在0.08675s。N2内部E/B共享prefix，18D在1.515s请求，bridge后1.565s参考/命令开始不同。末段不是差异的起点。T/E则严格保持此前运动，6.830s最终splice后才分叉。上述量级是描述阈值，不是新资格门。
2. **直接机制与推断**：源码确认范围拒绝、通过速度规则、网格quintic、40ms bridge和100ms scientific lifecycle；存档确认目标不同步与参考先停、实际仍运动及随后膝峰。T的配对结果建立末段参考时间形状的总效应；具体FAST/allocator/contact中介仍不能唯一归因。
3. **合法且可重复改善**：N2 T膝完整amax由90.058623降至75.571947°/s²，对B比值由1.249192降至1.048249。所有原motion/fairness、task、安全及causal门PASS；确定性重复逐字段PASS。末段自身amax降至52.141225°/s²，完整峰已转移到此前的前段。
4. **降力保留**：T JF=1409.539442142N·s，对匹配B降力2.410231%；与E仅差-0.022167424N·s，不称新降力突破。
5. **新状态验证**：U1原完整live父状态配对，T综合资格PASS 1/1；不是不同患者，重复不计新状态，不能升级为广泛泛化资格。
6. **下一步**：在新的独立协议中保持T=1.5冻结，扩大合法prefix的末段规划资格验证，检验其适用域；本轮不启动。 现有参考接口够用，正式B保持冻结。

## 诊断与唯一干预

存档诊断没有重跑physics。N2 18D髋先进入目标附近，膝后到；最后非终末target约[120,117.7845]°，空间意图越界拒绝，膝通过速度约8.8623°/s。最终request=6.785s、composite activation=6.790s；40ms bridge之后quintic实际执行6.830–7.050s。膝issued负加速度样本峰在6.995s，真实峰在7.07225s，届时参考dq=0而实际膝仍约5.918°/s。

N1 PASS也有先后到达、范围拒绝和相近参考加速度峰，所以事件共现不是充分因果解释。N2 B的全程膝amax=72.093488，N1 B=128.347787；冻结motion相对匹配B，不是跨状态统一绝对阈值。原N2绝对安全一直PASS。

T只在原18D已经选出最终OUTBOUND goal后，用原fixed-duration contract将suffix时长乘1.5、向上对齐5ms；N2为0.220→0.330s。原选目标、最终通过速度、所有此前schedule和物理运动不变。数学接口重建原0.220s完全一致，新参考精确峰约52.322°/s²；原连续几何、mechanics通过后才运行真实physics。全部current-state admission、source age、bridge、lifecycle、native ownership、carry/fallback原样执行。协议在第一START前冻结，未按结果改primary或门槛。

详见[N2诊断](N2_TERMINAL_DIAGNOSIS.md)、[事前干预协议](INTERVENTION_PROTOCOL.md)、[受控机制证据](MECHANISM_FINDINGS.md)。

## 全部完整物理候选

|条件/臂|完整 J_F N·s|对B降力 %|对E ΔJF N·s|膝amax °/s²|对B膝比|motion|task/安全/causal|
|---|---:|---:|---:|---:|---:|---|---|
|N2_B|1444.351653542|0.000000|+34.790043975|72.093488|1.000000|PASS|PASS/PASS/PASS|
|N2_E|1409.561609567|2.408696|+0.000000000|90.058623|1.249192|FAIL: acceleration_deg_s2/max_abs|PASS/PASS/PASS|
|N2_T|1409.539442142|2.410231|-0.022167424|75.571947|1.048249|PASS|PASS/PASS/PASS|
|N2_T_repeat|1409.539442142|2.410231|-0.022167424|75.571947|1.048249|PASS|PASS/PASS/PASS|
|U1_B|1444.756386942|0.000000|+34.898491691|72.081167|1.000000|PASS|PASS/PASS/PASS|
|U1_E|1409.857895251|2.415528|+0.000000000|87.619295|1.215564|FAIL: acceleration_deg_s2/max_abs|PASS/PASS/PASS|
|U1_T|1409.836483114|2.417010|-0.021412137|75.624592|1.049159|PASS|PASS/PASS/PASS|
|U1_T_repeat|1409.836483114|2.417010|-0.021412137|75.624592|1.049159|PASS|PASS/PASS/PASS|

B自比PASS只表示参照，安全与task另审。原E的FAIL如实保留。历史C/R及其重复失败没有重跑、没有覆盖。父运行各自与匹配B全trace/native/receipt物理字段精确一致，单独计入账本，不当额外候选或状态。

|条件/臂|OUTBOUND JF|HOLD JF|RETURN JF|OUT/HOLD/RETURN s|
|---|---:|---:|---:|---|
|N2_B|731.563958536|54.394314010|658.393380995|9.005000 / 1.020000 / 9.005000|
|N2_E|715.964908490|54.394332693|639.202368384|9.005000 / 1.020000 / 9.005000|
|N2_T|715.942741678|54.394332064|639.202368400|9.005000 / 1.020000 / 9.005000|
|N2_T_repeat|715.942741678|54.394332064|639.202368400|9.005000 / 1.020000 / 9.005000|
|U1_B|731.968692079|54.394313848|658.393381015|9.005000 / 1.020000 / 9.005000|
|U1_E|716.261194207|54.394332660|639.202368385|9.005000 / 1.020000 / 9.005000|
|U1_T|716.239782641|54.394332073|639.202368400|9.005000 / 1.020000 / 9.005000|
|U1_T_repeat|716.239782641|54.394332073|639.202368400|9.005000 / 1.020000 / 9.005000|

全部TASK均19.030000s。积分采用原5ms force左积分并在phase边界精确切分，共同prefix积分完整保留；完整/分阶段闭合通过。细节和每臂对B/E差值在`EXPERIMENT_RESULTS.json`。

## 运动、跟踪与绝对安全

|条件/臂|vmax °/s hip/knee|amax °/s² hip/knee|jerk RMS °/s³ hip/knee|jerk max（诊断）|tracking RMS ° hip/knee|moment Nm·s|clearance m|
|---|---|---|---|---|---|---:|---:|
|N2_B|23.784934 / 26.048980|85.115049 / 72.093488|316.960496 / 694.194759|5545.210478 / 18254.154059|0.480696 / 0.456821|98.691239168|0.011888026|
|N2_E|23.530733 / 23.985586|77.563960 / 90.058623|329.814570 / 693.411008|6677.916905 / 17085.654654|0.472985 / 0.516925|105.574974923|0.012330171|
|N2_T|23.530733 / 23.985586|77.563959 / 75.571947|329.780120 / 681.497378|6677.916905 / 17085.654654|0.472984 / 0.515773|105.567140505|0.012330171|
|N2_T_repeat|23.530733 / 23.985586|77.563959 / 75.571947|329.780120 / 681.497378|6677.916905 / 17085.654654|0.472984 / 0.515773|105.567140505|0.012330171|
|U1_B|23.784934 / 26.048980|85.115049 / 72.081167|317.113975 / 693.677206|5545.232664 / 18259.798979|0.480967 / 0.457642|98.525822285|0.011888026|
|U1_E|23.530733 / 23.985586|77.563960 / 87.619295|329.895432 / 693.867187|6678.722658 / 17056.232688|0.473307 / 0.517153|105.412947551|0.012330171|
|U1_T|23.530733 / 23.985586|77.563959 / 75.624592|329.861938 / 682.146554|6678.722658 / 17056.232688|0.473306 / 0.516064|105.405596902|0.012330171|
|U1_T_repeat|23.530733 / 23.985586|77.563959 / 75.624592|329.861938 / 682.146554|6678.722658 / 17056.232688|0.473306 / 0.516064|105.405596902|0.012330171|

velocity/acceleration/jerk的完整max/p95/RMS及各phase、ROM/dose/phase边界、moment/force peaks、tracking、clearance和安全逐项条件均在结果JSON的`measured`中。jerk max为原诊断项，不偷换成新门；实际Human导数来自0.25ms native qvel，不能把数学曲线当真实运动。

每臂request/activation/splice、target/pass velocity、应用命令、原receipt与每个native step的归属已保存并核对。源age、当前状态检查和原安全规则未放宽。受控T在最终splice前的参考/物理一致性、唯一accepted干预和实际输出差异由不导入controller/plant的脚本复核，见`audit/INTERVENTION_EXECUTION_AUDIT.json`；全native独立核算见`audit/INDEPENDENT_N2.json`与`audit/INDEPENDENT_U1.json`。

## 证据层级、保护与预算

新物理属于原MuJoCo **PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION**。原LEVEL2、host-clock LEVEL3/strict55/R2/FAST负结果及未获资格保持；host profiling不作为物理等价字段，也没有变成实时资格。没有真机、临床或跨患者证明。独立复核是单agent下的独立算术实现，不冒称独立人类或第二agent审计。

起始Git branch=`codex/expert-strength-value-adequacy-v1`，HEAD=`8bb04662b1578b72c097f546be9e836167e280e8`，未切分支、stage、commit、push、merge、reset、stash或删除旧文件。新文件仅在本版本Side Study及审阅镜像；原B/plant/Human/robot/contact/gravity/actuator、ROM/torque/task/HOLD/完整duration、安全/motion门、truth firewall、40ms bridge、100ms lifecycle、current admission/source age、native ownership/receipts/carry/fallback冻结。最终SHA、metadata、Git逻辑状态及owned进程退出结果以`PACKAGE_VERIFICATION.json`为准。

T0=北京时间2026-10-17 14:05:15，硬截止18:05:15，17:20:15后禁止新START。本轮START/END=10/10，上限20；新增native steps=793280。无partial，无失败物理尝试；父、fork、重复和验证全部计入。提前得到明确有限结论后停止，不为填满3–4小时追加实验。实际耗时和关闭时间见最终核验文件。

canonical完整执行源及raw：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1`；Windows为可读报告/分析/证据镜像，`ENVIRONMENT.json`和manifest明确来源。`REPRODUCTION.md`给出只读复核入口；已关闭包禁止原地重启physics。

**STOP。** 不自动开始第二轮18D+Waypoint搜索或Q-learning。

![N2局部共同时间轴](figures/N2_terminal_timeline.png)

![N2受控修复](figures/N2_intervention_response.png)

