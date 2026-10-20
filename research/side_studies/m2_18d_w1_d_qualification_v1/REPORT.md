# iHEAR Lab — W1 Motion Failure Diagnosis & Frozen D Qualification v1

**结论：冻结 D 在 W1 已真实执行，原完整资格失败；不升级为新基线。** W1 D 完整 J_F=1402.234611439 N·s，相对同条件 B 降力2.382382%，相对 T ΔJ_F=-1.222098322 N·s。低力与完整资格分别报告。

## 七个问题

1. **失败最早在哪里？** 历史 W1 T 的共同加速度高值首见1.715s，但 B 同时也有；T 超完整 B 参照而 B 未超的新增负担最早是 OUTBOUND 3.12525s。速度新增高值从 RETURN 11.99225s 开始，早于 D 首个请求12.790s。完整 p95 门仍在任务结束评价；不是新增瞬时失败门。T 膝 excursion 到16.48950s才超过完整 B 的+0.5°参照。
2. **OUTBOUND/RETURN 背景有哪些可验证影响？** W1 将两者同时改变，旧记录不能单因素归因。本轮 R0 固定 W1 OUTBOUND、移除 RETURN0；O0 固定 W1 RETURN、换成 V1 OUTBOUND。下表给出各自匹配 B 的结果和条件效应；这些控制识别背景规则及其后续闭环响应，未识别 allocator/contact 的唯一中介，也没有缺失第四角的交互分解。
3. **D 是否在 W1 执行并通过？** 已执行，两个原姿态意图实际执行=True；完整 task=PASS、绝对安全=True、causal receipt=PASS、motion=False。失败项=['velocity_deg_s/p95_abs', 'acceleration_deg_s2/max_abs', 'acceleration_deg_s2/p95_abs', 'jerk_deg_s3/rms', 'excursion']。
4. **是否保留18D-T降力优势？** W1 数值上对 B 保留2.382382%降力，对 T 的完整增量是-1.222098322 N·s。本次完整资格失败，因此不能把低 J_F 称为合格改进。
5. **新状态验证是否成立？** 本轮完整合格 D 条件=['R0_D']。仅适用于记录中的同一 Human、精确合法背景；R0 与 W1 共享 OUTBOUND fork 入态，O0 使用已见 V1 的 OUTBOUND，因此它们是受控背景资格，不能计成两个独立新 OUTBOUND 状态。W2执行=False；W1 已暴露，不能称新盲测。
6. **能否成为新基线？最小下一步？** 不能据本轮升级广泛基线。本轮 W1 D 失败，保持原 D 身份与失败，另立有界 motion 修复合同；先处理已定位的干预前 RETURN 负担与终末响应，再以新合法 prefix 检验。禁止按 W1 结果调整后仍称原 D。若局部控制合格，它只给出有限背景条件证据。
7. **何时重开18D+Waypoint第二轮优化？** 先冻结可覆盖目标合法背景的 task/safety/motion/receipt 合格基线，并用独立新 prefix 完成资格与合法重复。若修复合同改变，应返回开发并用未用于调参的新条件验证；在此之前不恢复稠密姿态/Waypoint搜索，不训练Q-learning。

## 冻结与研究事实

原始 B=1438.613498467 N·s；历史18D=1400.697221153 N·s，开发降力2.635613%。开发 D=1407.803235337 N·s，相对当时匹配 T 下降1.267775436 N·s。它们是历史事实，不替换本轮各条件 B 分母。18D18参数、RETURN plateau、T1.5/5ms向上对齐、D的RETURN2/3各[+0.3,-0.3]°、原选择规则及原执行/安全/运动门保持冻结。

先完成历史诊断，再冻结 FROZEN_EXPERIMENT_PROTOCOL.md、四个合法条件和执行manifest，之后才开始新 physics。本轮新合同按用户要求允许在 T motion失败后评价 D；历史 harness 与其停止记录完全保留。T失败不是本轮放宽门槛的理由，所有 D 仍逐项通过原门才算合格。

## 完整配对物理结果

|条件/臂|完整 J_F N·s|OUT/HOLD/RETURN N·s|对自身匹配 B 降力%|原motion|完整资格|
|---|---:|---|---:|---|---|
|W1_B|1436.456498145|719.868084/54.394340/662.194074|0.000000|PASS|PASS|
|W1_T|1403.456709761|706.697255/54.394331/642.365124|2.297305|FAIL|FAIL|
|W1_D|1402.234611439|706.697255/54.394331/641.143025|2.382382|FAIL|FAIL|
|R0_B|1432.655804346|719.868084/54.394340/658.393380|0.000000|PASS|PASS|
|R0_T|1400.293954479|706.697255/54.394331/639.202368|2.258871|PASS|PASS|
|R0_D|1399.026179051|706.697255/54.394331/637.934593|2.347363|PASS|PASS|
|O0_B|1447.597429652|731.009040/54.394315/662.194075|0.000000|PASS|PASS|
|O0_T|1412.233766056|715.474310/54.394332/642.365124|2.442921|FAIL|FAIL|
|O0_D|1411.011667734|715.474310/54.394332/641.143025|2.527344|FAIL|FAIL|

每组均从真实 commissioning + OUTBOUND0父进程进行完整活状态 fork；组内 B/T/D 全状态hash相同，父进程在每个子臂后保持不变并完成任务，与自身 B 子臂全部物理trace字段、native状态和receipt关键字段精确相同（排除host profiling）。完整积分包含共同 prefix，partial不排名。所有完整 task 的时长及各phase时长见下表；没有缩短任务。

|条件/臂|TASK s|OUT/HOLD/RETURN s|膝速度p95/B|膝加速度p95/B|膝excursion差°|D相对T ΔJ_F N·s|
|---|---:|---|---:|---:|---:|---:|
|W1_B|19.030000|9.005000/1.020000/9.005000|1.000000|1.000000|+0.000000|—|
|W1_T|19.030000|9.005000/1.020000/9.005000|1.115366|1.130897|+0.534884|—|
|W1_D|19.030000|9.005000/1.020000/9.005000|1.105474|1.131300|+0.543723|-1.222098322|
|R0_B|19.030000|9.005000/1.020000/9.005000|1.000000|1.000000|+0.000000|—|
|R0_T|19.030000|9.005000/1.020000/9.005000|1.083251|1.088300|+0.324948|—|
|R0_D|19.030000|9.005000/1.020000/9.005000|1.082855|1.081546|+0.361391|-1.267775428|
|O0_B|19.030000|9.005000/1.020000/9.005000|1.000000|1.000000|+0.000000|—|
|O0_T|19.030000|9.005000/1.020000/9.005000|1.075307|1.091366|+0.571923|—|
|O0_D|19.030000|9.005000/1.020000/9.005000|1.065770|1.087794|+0.580761|-1.222098322|

## 运动、剂量与补偿

|D条件|相对T velocity TV Δ%|acceleration variation Δ%|jerk RMS Δ%|tracking RMS hip/knee °|moment integral Nm·s|min clearance m|
|---|---:|---:|---:|---|---:|---|
|W1_D|+0.684220|+17.404654|+178.154241|0.465208/0.527000|108.383202|0.012367365|
|R0_D|+0.005044|+0.041292|-0.046321|0.464194/0.538586|109.302134|0.011977966|
|O0_D|+0.687404|+17.304879|+179.181992|0.473217/0.511284|104.925595|0.012367365|

原完整指标均保存：每joint/full/phase的velocity、acceleration、jerk（raw及SG5/SG21敏感性）、excursion、累计travel、endpoint、phase boundary、tracking、moment、ROM、clearance、force/moment peak与absolute safety；详见 EXPERIMENT_RESULTS.json 的 complete_metrics。原门与额外对 T 的variation比较分开，不因局部改善称为综合改进。

W1 D 相对 T 的真实 q 最大差 hip/knee=0.624634/0.613630°、dq最大差=3.255767/1.048760°/s；首个干预前 q/dq 精确相同=True。请求/激活、原reference、Human响应和每个native步的positive receipt归属另行核验。receipt原格式中部分路径无直接plan_request_id，本轮没有伪造该字段；沿用原source/version、活跃时段、reference和torque/step归属关联。

## 背景归因与证据边界

直接观测：W1 T 的速度高值全部在 RETURN；加速度高值1698个在OUTBOUND、2706个在RETURN。首个D请求前分别已有1922/2364个高值样本，但均未达到固定任务原时长容差下的不可逆p95计数下界，前缀excursion亦未必失败。因此新D物理实验有意义；旧T失败没有证明D必然失败。

源码/合同：合法prefix优先于冻结18D各槽动作；OUTBOUND0共同真实执行后fork，RETURN0各臂在活态下通过原证书执行。T仅在原18D最终OUTBOUND goal选中后改变suffix duration。本次W1原suffix0.300→0.450s，激活6.790s、40ms bridge后suffix约6.830–7.280s，和6.98275–7.278s的加速度负担重叠。E/T的RETURN q差约1.9e-8°，不能把T末段修复称为RETURN失败已修复。

相关性：tracking、moment、allocator分量、clipping、clearance、接触及issued reference变化均可查 audit/W1_COMPENSATION_SIGNALS.json 和统一时间轴。这些是闭环的相关响应；没有独立中介干预，不能断言某一分量是根因。

**新增终末失败。** D在16.700000s出现由native dq按原gradient计算的膝加速度峰267.010807°/s²；hip/knee raw jerk RMS=886.376590/1920.131547°/s³。SG5与SG21仍保存明显峰值，未用滤波替代原raw门。16.695s采样allocator力矩分量与实际command出现脉冲，16.700s有Human速度响应；该窗issued knee参考速度约零，positive receipt每个20native步、source age=0ms，已采样clipping为0、接触为空。它说明有终末command/闭环补偿现象，但尚不能从观测确定allocator、上游估计或其他模型机制谁是独立原因。原native绝对安全仍PASS，不等于motion合格。详见derived/W1_D_TERMINAL_WINDOW.json。

**严格后段修复的数学边界。** 实际D在RETURN2请求12.790s前，原p95计数/excursion下界仍未排除更早修复可能；但到终末RETURN5请求16.540s，膝velocity/acceleration高值样本已为4234/4353，均超过保留原完整时长容差后的3827个，prefix excursion也已经越过最终B+0.5°。因此严格从该终末请求以后才开始的修复，不能撤销这三项已累积失败，即使消除了16.700s峰也不能全门合格。下一个最小资格实验须另立候选与事前合同，考虑更早RETURN1的一项有界reference-timing改变，固定背景与原D姿态规则，先通过原证书再配对物理；不保证一定可修复。本轮不执行。完整界限见derived/W1_D_IRREVERSIBLE_PREFIX_BOUNDS.json。

|控制/臂|RETURN前完整q/dq前缀与W1精确一致|OUTBOUND最大q差 hip/knee °|RETURN最大q差 hip/knee °|原完整资格|
|---|---|---|---|---|
|R0_B|是|0.000000/0.000000|0.642/2.67|PASS|
|R0_T|是|0.000000/0.000000|0.421/1.93|PASS|
|R0_D|是|0.000000/0.000000|0.423/1.93|PASS|
|O0_B|否|1.732813/7.959949|2.69e-07/1.99e-07|PASS|
|O0_T|否|1.679058/6.748177|8.97e-09/3.09e-09|FAIL|
|O0_D|否|1.679058/6.748177|8.97e-09/3.09e-09|FAIL|

**实际负担与相对资格必须分开。** O0的T在RETURN相对W1的q最大差仅约9e-9°，膝velocity p95仍为22.559290°/s；匹配B的全程p95却从20.225905变为20.979395°/s，使ratio由1.115366降至1.075307。O0的T膝acceleration p95实际上由28.552719升到32.960832°/s²，而B从25.247850升到30.201439°/s²，相对门仍可通过。R0的T加速度p95=31.915326、excursion=111.862695°也高于W1 T，但匹配B参照同步改变后原门通过。因此不能把R0/O0的通过项称为实际运动负担全面下降；OUTBOUND的完整分布及早期最大q会影响全程p95参照和excursion，RETURN局部几乎相同也可得到不同相对资格。

两个条件效应均保留各自匹配 B，不拼接不同背景的绝对 J_F 排名。缺失第四个factorial角，不能进一步量化交互。N2/U1/V1/V2历史合格T与其18D负结果全部保留；新条件中T失败仍单独报告，不用其他条件D通过来覆盖。

本包沿用原 SCIENTIFIC_SIMULATION 时钟语义，causal/source-age PASS只指该模式；host wall profiling及旧host实时资格失败不被改写。冷父之间的完整hash含不同路径和host时间记录，因此不宣称跨条件完整地址空间完全相同；背景审计核对实际commissioning/native命令历史及初始belief，而每组内部B/T/D才有同父完整hash匹配。详见audit/BACKGROUND_MATCHING_AUDIT.json。

## 数值复核、保护与关闭

独立算术路径（同一agent的分离实现）从raw trace/native重算完整及phase积分、derivatives、dose/boundary、tracking，并核验每个positive receipt的torque与唯一native步数归属，全部PASS。不是独立人类或第二agent审计。历史八份manifest复核PASS，W1 B/T跨包raw精确复现PASS。
START/END=12/12，上限20；partial=0；实际新增native steps=974640。W1重复执行=False，W2执行=False，按冻结分支判定。
Git逻辑状态保持，历史118776文件metadata/SHA不变，冻结执行manifest不变，所有owned物理进程退出。T0北京时间17:34:07；20:49:07后禁止新START，21:34:07硬截止。保护审计完成用时42.39分钟，未耗尽预算追加搜索。

canonical完整raw与receipt：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_w1_d_qualification_v1
Windows审阅镜像：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_18d_w1_d_qualification_v1

**STOP。** 不自动开始Q-learning、下一研究包或18D+Waypoint优化。

![历史W1统一时间轴](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_18d_w1_d_qualification_v1/figures/W1_failure_timeline.png)

![本轮W1冻结D资格](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_18d_w1_d_qualification_v1/figures/W1_D_qualification_timeline.png)
