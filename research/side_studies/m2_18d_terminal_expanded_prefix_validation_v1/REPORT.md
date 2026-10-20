# iHEAR Lab — 冻结18D末段修复：扩展prefix验证 v1

**时间合同已解释；新合法prefix中冻结T motion通过2/2，保留降力2/2。** 本轮无调参、无倍率搜索。

## 六个明确答案

1. **duration与phase/task时长已解释。** suffix真实延长，而原MATCHED非HOLD phase至少9s的执行规则不变。延长占用原终点TRACK等待区间；N2为0.220→0.330s，实际参考6.830–7.050→6.830–7.160s，终点carry1.955→1.845s。没有BRAKE切换、progress延迟或任务缩短。详见T_EXECUTION_CONTRACT_AUDIT.md。
2. **新状态motion通过率：2/2（100.0%）。** 只有V1/V2计入分母；N2/U1及全部重复均为历史/重复证据。两状态均为同一Human的合法prefix后remaining-suffix验证。
3. **每条件内部配对的力收益见下表。** 完整积分包含共同prefix；同时报告T对匹配B降力和T−18D，不把不同状态绝对J_F相互比较。
4. **状态依赖：** 本轮无T失败，无法建立稳定失败状态依赖；也不能据此排除未测状态失败。
5. **保守基线：** 可在本轮及历史已测的同Human有限适用域内作为冻结研究比较基线；尚不足升级为广泛有效基线或直接启动第二轮优化。
6. **唯一下一步：扩大合法状态验证。** 本轮STOP，不自动开始18D+Waypoint或Q-learning。

## 完整配对结果

|条件/臂|完整J_F N·s|对匹配B降力 %|T/臂−18D N·s|motion/fairness|task/安全/causal|
|---|---:|---:|---:|---|---|
|V1_B|1443.796735858|0.000000|+34.702115484|PASS|PASS/PASS/PASS|
|V1_E|1409.094620374|2.403532|+0.000000000|FAIL: acceleration_deg_s2/max_abs|PASS/PASS/PASS|
|V1_T|1409.071010773|2.405167|-0.023609601|PASS|PASS/PASS/PASS|
|V1_T_repeat|1409.071010773|2.405167|-0.023609601|PASS|PASS/PASS/PASS|
|V2_B|1445.129907597|0.000000|+34.981615475|PASS|PASS/PASS/PASS|
|V2_E|1410.148292123|2.420655|+0.000000000|FAIL: acceleration_deg_s2/max_abs|PASS/PASS/PASS|
|V2_T|1410.128216732|2.422045|-0.020075391|PASS|PASS/PASS/PASS|
|V2_T_repeat|1410.128216732|2.422045|-0.020075391|PASS|PASS/PASS/PASS|

T相对18D的微小J_F变化只用于确认收益保留，不能当作额外降力突破。匹配B自比motion PASS是参照，task/安全另审。

|条件/臂|OUTBOUND JF|HOLD JF|RETURN JF|OUT/HOLD/RETURN s|完整task s|
|---|---:|---:|---:|---|---:|
|V1_B|731.009040149|54.394314718|658.393380992|9.005000/1.020000/9.005000|19.030000|
|V1_E|715.497919276|54.394332715|639.202368383|9.005000/1.020000/9.005000|19.030000|
|V1_T|715.474310316|54.394332057|639.202368400|9.005000/1.020000/9.005000|19.030000|
|V1_T_repeat|715.474310316|54.394332057|639.202368400|9.005000/1.020000/9.005000|19.030000|
|V2_B|732.342212526|54.394314073|658.393380998|9.005000/1.020000/9.005000|19.030000|
|V2_E|716.551591148|54.394332588|639.202368387|9.005000/1.020000/9.005000|19.030000|
|V2_T|716.531516260|54.394332072|639.202368400|9.005000/1.020000/9.005000|19.030000|
|V2_T_repeat|716.531516260|54.394332072|639.202368400|9.005000/1.020000/9.005000|19.030000|

积分为原5ms force左积分并按真实phase边界切分；完整与phase闭合经独立实现重算，native导数来自0.25ms真实qvel，非数学参考。

## 运动、tracking与补偿代价

|条件/臂|vmax hip/knee °/s|amax hip/knee °/s²|jerk RMS hip/knee °/s³|tracking RMS hip/knee °|moment Nm·s|clearance m|force/moment peak|
|---|---|---|---|---|---:|---:|---|
|V1_B|23.784934 / 26.048980|85.115049 / 72.100223|316.391055 / 694.924744|0.480381 / 0.456008|98.799523|0.011888026126332604|116.112097 N / 15.908800 Nm|
|V1_E|23.530733 / 23.985586|77.563960 / 92.406356|329.820946 / 693.325950|0.472760 / 0.516763|105.683433|0.012330171393131747|115.351483 N / 15.908800 Nm|
|V1_T|23.530733 / 23.985586|77.563959 / 75.514435|329.784750 / 681.092800|0.472759 / 0.515517|105.674985|0.012330171408296755|115.351483 N / 15.908800 Nm|
|V2_B|23.784934 / 26.048980|85.115049 / 72.066461|317.716620 / 693.772947|0.481414 / 0.458727|98.365004|0.011888026130640921|116.272391 N / 15.968799 Nm|
|V2_E|23.530733 / 23.985586|77.563960 / 83.236791|330.056235 / 693.310093|0.473761 / 0.517511|105.253069|0.012330171396673428|115.519181 N / 15.968799 Nm|
|V2_T|23.530733 / 23.985586|77.563959 / 75.673107|330.026211 / 682.699137|0.473760 / 0.516528|105.246629|0.012330171408330617|115.519181 N / 15.968799 Nm|

所有velocity/acceleration/jerk完整与phase max/p95/RMS、jerk max诊断、ROM excursion、cumulative travel、endpoint与phase边界dose、tracking、force/moment peak及完整native安全逐项指标均在EXPERIMENT_RESULTS.json的measured和delta_vs_B/delta_vs_frozen_18D。motion比值1.10、dose±5%、边界0.5°、duration0.1s、moment integral1.25及其余原门完全保留；不宣称多指标Pareto优势。

## 合法状态、前史与执行合同

- V1：seed=2026101901，prefix={"OUTBOUND": [[-0.045, -0.075, -0.055]]}；fork task=1.520000s，完整父hash=7037e1c3099159d313e98fa8661ac0e4a7e08015cf8b82b8589aae2fb9daff47，native hash=c227c938a0ed03a16a09d32ac0a5166d3ec3d2dc4a0b3fdce51e19e528af1878。共同prefix J_F=148.643950587N·s，真实prefix native steps=6060。
- V2：seed=2026101902，prefix={"OUTBOUND": [[-0.09, -0.03, -0.065]]}；fork task=1.495000s，完整父hash=62f90314d0449e319686f722a4a107fb0dba777e8b90e8faa01949f7f3dfc64f，native hash=81f4573555ad9ca0468d212ccb7f30a17d0c64ada33e7210563f551f293ca175。共同prefix J_F=146.787776820N·s，真实prefix native steps=5960。

每个新状态来自真实cold commissioning及合法prefix，随后完整地址空间os.fork，未直接设置或回放Human qpos/qvel。B/E/T的fork restored hash、fork前完整trace、prefix执行receipt及父不变检查全部精确通过，完整父结束与B raw逐字段一致。两新native状态彼此不同，也不同于N2/U1；数值差仅用于evaluation，不进入控制。OUTBOUND index0已被prefix消费，18D/T从index1开始比较remaining行为，不能称完整18D整串从未见初态执行。

T源码与上一轮字节一致，倍率1.5，原18D参数/RETURN plateau与motion协议字节一致。仅一个最终OUTBOUND干预被原certificate/mechanics/current admission和执行链接受；所有此前schedule、参考及真实运动在splice前一致。每个T真实duration、request、activation、splice、reference receipt/native归属和carry详见audit/EXPANDED_EXECUTION_TIME_AUDIT.json与audit/INTERVENTION_EXECUTION_AUDIT.json。

|新条件/臂|suffix时长 s|splice task s|suffix结束 task s|终点TRACK carry s|
|---|---:|---:|---:|---:|
|V1_E|0.225|6.825|7.050|1.955|
|V1_T|0.340|6.825|7.165|1.840|
|V2_E|0.215|6.825|7.040|1.965|
|V2_T|0.325|6.825|7.150|1.855|

冻结的是1.5倍率及5ms向上对齐规则，不是统一0.330s。V1原0.225s→0.340s，V2原0.215s→0.325s；差异由各状态原合法duration及同一冻结取整规则产生，未重选倍率。

## 证据层级与未解决问题

- **本轮PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION**：V1/V2各匹配B/18D/T，合格后T确定性重复。重复证明确定性，不是新状态。
- **历史证据**：原B JF=1438.613498467、开发18D=1400.697221153（降力2.635613%）；N2/U1有限合法prefix与重复原样保留，原18D motion FAIL及旧host/strict/R2/FAST资格结果不改。
- **数学证据**：原fixed-duration接口重建、连续几何certificate与mechanics；不能替代真实Human运动或native安全。
- **独立重算**：单agent下独立算术源码路径，不导入controller/plant；不是独立人类或第二agent审计。
- **未解决**：更广prefix/通过速度和更远状态的适用域、具体FAST/allocator/contact中介、跨患者、host实时/LEVEL2/LEVEL3与硬件/临床资格均未建立。历史receipt没有直接plan_request_id，已有明确间接时序/参考/torque/步数证据，不伪造字段。

## 预算、保护与关闭

T0=北京时间2026-10-17 14:47:58；硬截止18:47:58；18:02:58后禁止新START。START/END=10/10，上限30；新增native steps=793360。父、fork、失败与重复全部计入；无partial。提前取得两条件有限结论后停止，不为填满预算追加实验。

新修改仅在本版本Side Study与对应Windows审阅镜像。起始Git、旧历史metadata/SHA、冻结execution manifest、owned进程退出及最终计数见PACKAGE_VERIFICATION.json。无Git commit/push/merge/reset/stash/clean/branch切换。正式B、plant、安全执行链和历史证据均保持。

canonical：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1
Windows审阅镜像：/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_18d_terminal_expanded_prefix_validation_v1

**STOP。**

最终保护核验：PASS。旧历史metadata 112504 项、SHA 109760 项及上一轮Windows镜像 141 项全部未变；主仓库Git逻辑状态完全一致，全部owned物理进程退出、native executors关闭，START/END闭合。最终耗时 28.67 分钟。
