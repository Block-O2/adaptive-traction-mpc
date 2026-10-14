# 详细研究史：为什么控制问题逐渐变成协调运动问题

这份底稿按问题与技术转变组织，而不是按工作包名称排列。长期目标是让机器人完成同样的康复任务，在真实接触和执行约束下减少累计交互力，并最终利用少数重复运动学会适合患者的协调方式。前半句已有有限仿真证据，后半句仍是研究目标。

**LAST_PROFESSOR_UPDATE_UNCONFIRMED。**目前能确认曾制作教授用途材料，不能确认最近一次实际汇报的时间、内容或教授已知范围。另检索当前可访问Gmail：项目关键词与较宽MPC/iHEAR/rehabilitation/组会查询均没有返回相关邮件；这仅描述检索结果，不证明过去没有讨论。用户审阅后应标出实际汇报边界，再裁剪正式汇报。下文保留完整历史。

阅读主线：模型真实性提高，使接触与运动负担开始成为实际困难；预定参考不能回答怎样协调更省力，推动目标驱动和在线路点；新计划必须能在当前状态合法执行，推动B生命周期与命令归属；已有Q显示降力却缺状态条件排序和运动质量优势，推动先寻找值得学习的物理运动。每一步都保留失败与尚未完成的资格。

证据入口是研究归档索引，而不是目录名。清理后部分旧raw已报告化，文档引用与紧凑JSON核验不等于全部历史重跑。分母、source行号与证据等级见MILESTONES_AND_EVIDENCE.md及EVIDENCE_LEDGER.json。今晚实验另见REPORT.md和EXPLORATION_RESULTS.json；历史数字不随今晚结果改写。


# 研究史阶段1–5：从简化对象到B运行底座

状态：历史源码复盘完成，2026-10-14（Asia/Shanghai）。只读恢复历史；本稿未运行物理仿真、未修改主库/WSL源码、配置或Git。

## 汇报边界与阅读约定

**LAST_PROFESSOR_UPDATE_UNCONFIRMED。**主库现存教授材料包括Stage-4的`PHASE3A_RIGID_VS_P1_PROFESSOR_REVIEW.html`、`professor_video_manifest.json`和对应生成器。Git记录2026-09-09 `56eff89`为“Add corrected force traces to professor report”，证明曾制作教授用途材料；它不能证明邮件已发送、教授实际看过、组会实际举行或这是最近一次汇报。2026-07-30 MATLAB intake证明教授原始参考被接收/审计，也不能作为“上次汇报”时间。应把完整研究史交给用户确认边界，不预设教授已知范围。

以下`stage1/stage2/stage3/stage4/stage5`是仓库包名。用户要求的“阶段1–5”是叙事阶段，两者不一一对应。Spring2D内部还存在Stage9/10/11等方法审计，不能误认为后来的Human-V2研究阶段。

证据等级：CONFIRMED为当前源码/可读记录直接支持；SUPPORTED为有限实验支持；INFERRED为因果解释；HISTORICAL_REPORTED为仅能引用历史报告数字；UNRESOLVED为无法确认。报告数字本稿默认HISTORICAL_REPORTED，未逐原raw重算。源码路径均以`/home/hank/coding/adaptive-traction-mpc-learning/`为根，side-study另注明；Git历史引用用`git:revision:path:Lx`。

## 1. 项目起点并非一套模型：Spring2D、教授MATLAB与linked Human的角色

长期目标是在人动力学不确定时，使机器人完成下肢康复动作，并在可重复、公平比较中发展固定MPC、辨识与自适应控制。最初工程练习先采用Spring2D；随后接收教授双臂示意MATLAB并转向有髋膝几何的linked Human。现在追求累计交互力和重复间个体化，不应反向说最初每个阶段已实现这个完整目标。

**Spring2D**是有重力、移动基座的极坐标弹簧杆。状态为`[theta,omega,r,r_dot]`；输入是接触点的切向/径向力`[F_tan,F_rad]`；接触位置是`base + rho*r*e_rad`。源码中质量矩阵、弹性/阻尼、重力和基座运动共同决定角加速度及径向加速度。它没有髋、膝、完整shank、六轴机器人或真实cuff actuator。这套模型用于控制/估计器/安全过滤方法基础，不是患者模型。冻结示例配置含目标角约90°、`omega_des=.9 rad/s`、`dt=.01 s`、最大8 s等；这些是Spring2D自身合同，不能与后来15 s/23 s/9–1–9 s任务直接比较。证据：`stages/stage1/src/traction_mpc/models/spring2d_dynamics.py:81–174`、`stages/stage1/configs/spring2d.yaml:1–40`。

**教授MATLAB `singleArmDual.m`**是2026-07-30接收的独立参考脚本。它提供两刚杆髋膝坐标、示意双臂接触点、余弦参考、computed-torque+PD、等效法向弹簧阻尼和动画。两机器人臂只有几何端点/等效法向力，没有机器人关节、惯性和执行器。脚本的驱动包含直接人体关节跟踪力矩`tau_ctrl`，不是后来的“仅机器人经过cuff驱动被动Human”。预先规定0.2 Hz余弦参考，hip 0–65°、knee 0–70°；12 s、0.5 ms步长，精确状态反馈，没有MPC或online identification。历史capture报告完成且最大跟踪误差hip1.16°/knee1.14°、端点力峰4.4/5.3 N。这些低力数字不能与后来的真实机器人+cuff force比较，因为直接关节力矩和接触定义不同。

MATLAB审计没有把教授源悄悄“修正”。它确认脚本运动学用shank角`q1-q2`，M/C表达式却对应plus-relative坐标；source gravity不等于声明水平零角坐标下势能梯度，且同一gravity在controller与forward dynamics中恰好抵消。因此好看的跟踪并未验证一致物理动力学。报告包含24001 captured states和2000 fixed-grid states的符号/能量审计。这个发现推动独立一致的物理Human plant，而不是把脚本直接包装成正式MuJoCo truth。证据：`git:c3957e8:linkage/docs/MATLAB_CODE_AUDIT.md:53–212,399–434`；`git:c3957e8:linkage/docs/DYNAMICS_CONSISTENCY_AUDIT.md:306–440,474–487`。

**linked Human与Human V2**是接下来独立的物理对象。Git依次记载2026-07-30 `dc8a160` physical human two-link、2026-07-31 `586f8db` ideal endpoint force baseline、`ac5f167` anthropometric Human V2，之后单臂、near-extension、bed-supported load-transfer研究。早期point-force/tendon已由rigid robot-cuff-shank transmission取代，只在历史保存；不能说所有这些是当前可切换正式模型。阶段2 closeout明确早期point-force估计在knee3°约需348 N，承认cuff sagittal moment后静态translational force42.90 N。这是输入传递方式的改变，不能描述成同controller降低87.7%患者负担。证据：`stages/stage2_linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md:5–24,33–44`。

早期linked Human还必须拆成三个权限层。`dc8a160`先统一`q1-q2`坐标与重力/能量关系，建立`Mddq+h+G+B dq=tau_joint+tau_contact`的物理plant，单shank contact只给damping、无spring/hard clipping/hidden safety。它的computed-torque PD是**直接抽象Human关节力矩的oracle plant validation**，18个rollouts完成和15tests通过只验证这个权限下的对象，不证明机器人能够做到同样动作。`586f8db`再把直接joint torque替成理想双向cuff力`[Ft,Fn]`，经`Jcᵀ`映射，组件±300N、slew2500N/s、2ms；9个force-only病例全部数值跑完，却有严重tracking失败。例如nominal coordinated RMSE22.26/60.92°、3458joint-limit samples、transmission condition number1913；相同任务的direct-torque oracle9/9 RMSE<2.6e-8°。因此“oracle容易完成→机器人force-only也应完成”是错误推理。这个负结果直观揭示actuation/transmission限制，后续equilibrium-preserving、conditioning-aware与force/moment接口研究具有必要性。证据：`git:dc8a160:linkage/docs/PHYSICAL_PLANT_BASELINE.md:18–25,67–92,113–136,177–204`；`git:586f8db:linkage/docs/IDEAL_ENDPOINT_FORCE_BASELINE.md:5–23,25–93,95–119,139–153`。

Human V2最初又是**parallel anthropometric/passive-joint plant验证**，未覆盖或修复旧force-only negative baseline。1.72m/75kg名义模型给L1 .436880m、L2 .400760m、m1 7.425kg、m2 4.5kg；早期cuff action位置.90L2。被动K=diag(10,10)Nm/rad、B=diag(5,5)Nms/rad、q_rest5/10°、ROM0–80/0–100°、5°cubic soft-margin和边界25Nm均被明确标为工程假设，非临床常数；无state/velocity hard clipping。V2 direct-torque oracle仅验证model/reference，其接近零tracking error不能证明single-arm contact被解决。后来的Stage5 cuff72%shank与early90%是版本区别，不能混成同几何。证据：`git:ac5f167:linkage/docs/HUMAN_MODEL_V2.md:5–16,41–84,96–152,187–213`；当前`stages/stage2_linkage/matlab/src/human_two_link_v2/human_two_link_v2_parameters.m:22–43`。

## 2. “给定轨迹和速度，controller负责跟踪”的准确范围

这句话最清楚对应Human-V2 Stage2/Stage3及Stage4 tracking分支，而非所有Spring2D控制器。完整参考由外部函数按时间生成，输出`q_ref,dq_ref,ddq_ref`。15 s参考是initial hold1 s → outbound6.5 s → peak hold1 s → return6.5 s，hip/knee共享quintic进度`10r³-15r⁴+6r⁵`，端点和时长均预先规定。`coordinated_posture`固定hip–knee比例40/74；因此速度不是controller随意决定，而是角差与时长和quintic导数共同确定。证据：`stages/stage3_full3d/src/traction_mpc_stage3/reference.py:18–63,91–97`；MATLAB V2 reference `stages/stage2_linkage/matlab/src/human_two_link_v2/human_two_link_v2_reference.m:15–77`。

Stage2/3名义工程smoke使用simulator Human状态与固定nominal模型，不能追认后期Stage4的robot-facing状态重建/在线辨识（stage3c_validation.py:26–27,88–91）。Stage2不是MPC：nominal Human inverse dynamics给需要的generalized torque，cuff allocator分配force/moment，6D pose feedback补tracking误差，机器人Jacobian把wrench转关节torque，MuJoCo执行。Stage3把这条语义移植到完整6-DoF UR10e surrogate，gear1 torque motors、`ctrl[i]`一对一Nm，模型限制`[330,330,150,56,56,56]`；真实CR12未被实机验证。Stage4才在这套plant上形成Human-space MPC、固定/自适应control-effective dynamics与safety层。不能把Stage2 inverse-dynamics+PD、Stage4 torque-sequence CEM-MPC和Stage5 waypoint MPC统称同一MPC版本。

历史Stage2名义3° full-cycle完成，RMSE .081/.195°、peak force109.81 N、peak moment27.19 Nm；mild mismatch完成，moderate/adverse虽然跑满15 s仍未满足terminal tolerance。Stage3单条15 s工程smoke RMSE .06850/.16920°、peak force111.207 N、peak torque fraction.4720，无force/torque/solver/collision事件。这些各自分母单工程case，不能升级跨患者安全。证据：`stages/stage2_linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md:46–100`；`stages/stage3_full3d/README.md:33–48,77–100`；`stages/stage3_full3d/results/final_presentation/summary.md:3–11`。

Stage4的科学贡献还包括仅使用robot-facing测量重建Human状态、有效动力学估计、causal future-block验证后才promote challenger。现存README摘要36个patient-generalization arms完成，12 matched comparisons；crossed replication18/18 promotion/completion/tracking RMSE与prediction RMSE改善，同时2例max error变差。应在阶段4 appendix再对应原报告分母，不能把它们作为当前B/高ROM/自由参考的验证。时间统计saved-trace replay9.42 ms MPC mean、16.52 ms cycle mean仅desktop throughput，不是硬实时。证据：`README.md:12–33,46–58`。

## 3. Human V2、高ROM和真实接触为什么使问题变难

Human两关节给出的cuff几何依赖thigh、shank、hip pivot和shank角`q1-q2`。近伸展会使point-force传递矩阵病态，force与moment的自由度非常关键；运动学端点可达只代表某姿态能被描述，不代表路径每点的gravity/support、运动惯性、cuff moment、robot torque、接触、数值和终末settling均可行。

Stage3 rigid cuff通过六约束weld传递pose，Human有unilateral bed contact，robot self-collision保持。瞬时allocator预测或command安全，无法保证下一native substep的真实interaction：机器人feedback、接触/约束求解、历史状态和已持有command可产生额外瞬态力。2026-09-02的90/120原 lying-bed失败在16.046 s：command199.9999999996 N，physical218.441035 N，direction差61.818644°，physical moment53.568048 Nm；相同held command后续整个5 ms仍>200 N。重演16047 force norms逐值相同。force gate不是“算错了force norm”，而是command和physical channels不同。证据：`STAGE4_PHASE_A_HIGH_ROM_INTERACTION_DIAGNOSIS.md:13–18,35–82`。

去掉bed contact的独立contact counterfactual没有再现218 N crossing，却在16.055 s因BRAKE_INFEASIBLE停止，physical peak197.839 N。故不能把bed contact看成唯一根因，也不能宣称悬空模式成功。局部null-space wrench更新突然跳跃在静态不改变Human generalized torque，动态仍改变耦合state；memoryless安全过滤并非完整physical safety闭环。证据：`STAGE4_PHASE_A1_B0_INTERACTION_AUTHORITY_AUDIT.md:15–45,83–104`。

关键后续发现不是“高ROM物理一定不可能”，而是robot velocity feedback误用history-derived估计速度引入延迟。2026-09-08 `ce72ddf`引入cuff Jacobian即时control velocity，估计器继续使用history velocity；保留MPC、140 Ns/m gain、safety、任务及models。同日corrected Rigid NEW不再有旧BRAKE/200 N瓶颈：40/80 COMPLETE100/100%，90/120 physical progress96.18/100%、120/12099.33/99.99%，后两者仍SAFE_INCOMPLETE，不能把“几乎走完”改成COMPLETE。P1 compliant interface不是highROM可行必需，其更稳定收益是force slew下降，peak/tracking因任务不同而混合。证据：`README.md:59–70`；`CORRECTED_BASELINE_REPORT.md:3–20,32–34`。

这些历史High-ROM 90/120、120/120是专门扩大ROM的工程family；之后Phase3接口沿用Human-V2 80/100°默认domain；对应正式科学claim属于Phase2，当前B/自由参考应以自身frozen Human/task为准。不能拿“以前到120°”推定当前Human ROM也是120°，也不能反推所有旧highROM都失败。

## 4. 从整条参考轨迹到在线目标：实际经历了两次转变

**第一次：Stage5 goal-directed torque MPC。**任务合同不再给全episode的`q_ref(t)`，而给start/goal/allowed region、speed/acceleration/time budgets、OUTBOUND→HOLD→RETURN→COMPLETE条件。controller接收estimated state和active phase，以Human generalized torque序列优化goal距离，首个action依原机器人执行层施加。它不是马上变成“输出一对hip/knee角目标”的版本。

初版Goal-MPC smoke共11次SAFE_ACTION、43次SAFE_UNCHANGED仍于.215 s physical201.533 N abort；Human-only prediction未包含Plant-v1 interface transient，goal-distance objective缺合适speed/time限制。后来的path-free complete episode在4.615 s完成、J_F443.642 N·s，但该历史结果是在motion envelope disabled下取得，后来明确初始acceleration infeasibility，故保留而非当前资格。HOLD→RETURN直接wrench跳62.17 N/10.62 Nm；冻结首RETURN目标经.10 s bumpless transfer后才resume optimization，解决“预测raw command但执行partial blend”的语义失配。这些failed attempts解释为何不能仅通过改reference函数宣布结构完成。证据：`STAGE5_TASK_CONTRACT.md:25–36,67–98`；`GOAL_MPC_V1_ENGINEERING_SMOKE.md:50–73,88–122`；`GOAL_MPC_COMPLETE_V1_ENGINEERING_REPORT.md:8–31,38–91`。

explicit interface prediction state又解决跨solve base-drive/history重建导致的feasible remainder失效：.420 s accepted plan在.440 s重验velocity越界，512候选扩大search仍0 feasible；近一阶pose预测虽准，history drive重置改变后续模型，所以简单“保存旧plan”不能救。证据：`GOAL_MPC_FEASIBILITY_LOSS_AUDIT.md:16–71,73–88`。

**第二次：Architecture Recovery V2.2 Phase3 Human-waypoint。**2026-09-23 `bd7952f`首次把当前`human_waypoint_feedback_mpc.py`及Phase3 evidence加入Git；2026-09-25 `c72760a`引入完整full3D online planning/runtime路径；日期是publication checkpoint，文件实际开发日期若无单独记录不能精确到某次会议。

当前直接state-feedback planner在每次decide用`state[:2]`与phase goal生成两维Δq候选；target=`state[:2]+action`，而不是预定path上固定进度。scheduler从**当前已发reference q/dq**接到target q及endpoint dq，求符合reference motion/ROM/clearance的quintic。mechanics screen检验adaptive model inverse dynamics force/moment，排序deterministic cost+可选value；value默认0且不放松hard masks。源码：`human_waypoint_feedback_mpc.py:214–238,259–302,341–374,394–453`；`human_waypoint_scheduler.py:125–205`。

已直接读取**首个tracked revision `bd7952f`源码**，而非仅用当前源码倒推历史：当时`candidate_actions:178`、`target=state[:2]+action:223`、`plan_reference_contract:248`、fresh deployable/reference states`:305–306`、actions`:333`与排序/greedy`:350–376`均存在。当前源码的pass-through terminal velocity属于后续变更，首版端点dq为零；不能把当前移动endpoint/escape机制追认为Phase3首版已存在。Stage4当前`mpc.py:362–375,883–914`明确query future reference数组，`goal_mpc.py:583–642`把参考替为constant phase goal并显式禁止query prescribed reference，补足三个版本的源码对照。

因此实际高层输出包括**下一对hip/knee waypoint angles、endpoint velocity、duration及quintic schedule**。它既不是直接写Human qpos，也不是取消trajectory planning。轨迹规划从“一开始固定全episode”变成“在线分段规划+确定性执行”。target angles经reference sampling、feedback、cuff allocation、robot torque和原MuJoCo动力学才影响实际Human，reference与actual必须分开记录。

Phase3 V1原13checks曾通过，但独立audit判NO-GO：causal transitions缺next observation/full provenance、source manifest不全、test count stale；V1明确非authoritative。V3修复后14interface checks、47tests、19manifest files通过，只有3planning calls，runtime42.20/64.91/65.48 ms。它当时是interface smoke，未包含完整CR12 reach/collision/torque/physical cuff transport，不能把V3 smoke当当前B完整闭环已验证。full3D后续integration才补机器人执行与运行生命周期。证据：`PHASE3_HUMAN_WAYPOINT_INTEGRATION_V1.md:3–23`；V3`:10–50,59–74,88–97`；`FINAL_ARCHITECTURE_TECHNICAL_DEEP_DIVE.md:12–47`。

## 5. B底座：为什么需要commissioning、准入、命令归属和多速率

B不是单一“trajectory tracker”。在当前family中，commissioning通过合法robot/cuff motion获取可观测geometry与control-effective dynamics；planner使用完整fitted belief；scheduler生成reference并govern进度；FAST feedback+safety+robot command执行；TASK可异步。commissioning估计的是hip位置、thigh length、knee-to-cuff距离，不识别full shank与rho各自真值。11beta动力学及bounded residual是control-effective model，不能解释为识别出患者解剖参数。历史Phase2 commissioning beta是post-probe retrospective batch，continual task update才causal；而冻结当前B commissioning_only不是本轮online personalization。

模型拟合准确仍不能确保handoff合法。rho=.60诊断fit lever误差19.899 µm、352samples，却actual clearance+5.170123 mm对应conservative certificate−1.827095 mm，46candidates全部拒绝、0recovery intervals；full shank .46 m upper未被合法识别为更小，不能注入truth .40076 m放宽。oracle走另一initialization/commissioning轨迹，attachment起点相差47.747426 mm，不能作same-state oracle修复证据。这里失败是state+conservative prior组合，不是fit小误差能解释，也不是整个physical control无效。证据：side `commissioning-to-recovery-geometry-compatibility-v1/REPORT.md:7–35,39–54`。

**scheduler/governor**解决的是“候选目标能否形成满足reference速度/acceleration/continuous clearance的段、当前执行进度能否继续”。**current-state admission**解决的是异步planner完成时state/model/reference已改变：旧snapshot上feasible并不等于现在可应用，必须重验age、phase、goal、ROM、motion、clearance、reference continuity及最终robot command。**immutable causal snapshot**解决worker与main mutation race；worker只读序列化的planner/belief/reference state，不拿plant authority。源码`online_planning.py:1–40`。

**100 ms lifecycle**从原sensor capture计age，`>=100ms`expired；它不是planner compute runtime，不允许在完成/重试时重写source timestamp。**40 ms physical bridge**是8×5 ms经过screen的原bridge，为已有moving endpoint预先附加escape/stop path；它不是“可以把所有proposal拖到100ms”的承诺。primary只有valid/fresh才切入；失败/迟到进入已认证stop→SAFE_FALLBACK_HOLD，再以新state/source replan。代码`online_planning.py:71–74,179–180,200–227`；`safe_fallback.py:35–58,96–123`。

**causal command ownership**回答每个native physics step实际执行哪条robot torque。proposal被选择、收到或attempted不等于真实执行；需要receipt applied=True、有效activation、native_steps>0和逐step command join。否则可出现未来command在actual host write前被固定网格误归属的问题。科学模式是explicit native step驱动，host clock仅profile；scientific scheduler会记录20native steps/5ms，其host timings不能直接当host-clock qualification。源码`scientific_scheduler.py:1–5,24–44,62–111`。

直接source复核还确认`activation_validation.py:144–174`会在当前belief上重新算mechanics、phase/time、C2 reference continuity及continuous clearance；`:175–230`对future handoff再用新deployable state验证ROM/motion/shifted path，并保留**original capture age**。`wall_physics.py:139–153`逐步累加当前receipt的native_steps，`:244–289`actual write前catch-up只使用旧command，failed write在任何physical step前rollback。应注意主库这份源码是历史基线，side-study frozen/native FAST版本可能有编译实现差异；本稿不声称用main源码已认证所有后续side版本。

**FAST/TASK多速率**将5ms service owner与较慢planner分开，commissioning目标/fit replay也可offload；single plant owner持续执行合法carry并保持measurement/safety。offload只消除blocking future等待，snapshot、decode/model handoff、current admission、command construction和真实physics仍花预算。不能把Q inference的微秒时间当完整控制周期。

科学、任务与实时必须分轴。2026-10-07 multirate R1/R2/R3科学回归各名义+合法前缀bit-identical，但host complete VALID0/13，R3原qualification0/8；其中7/8完成OUT/HOLD/RETURN，说明“完整任务motion可发生”不等于strict55/R2/FAST门槛通过。该包strict55为原source→conservative actual activation<55ms；native generic expiry100ms；MATCHED R2每phase9/1/9 s至各+.020s。不能把不同55/100/40ms混称一个deadline。side `b_multirate_realtime_v1/REPORT.md:11–31,44–64,70–84,107–111,201–220`。

2026-10-08 qualification decoupling新合同把physical、causal runtime、FAST分开：旧047/048按新增runtime合同PASS，旧R2 FAIL保留；新4complete host tasks物理/安全/current admission/causal/backlog PASS，FAST尾延迟FAIL，B仍NOT_FROZEN。再后jitter包当前FAST恢复且M2有限host研究可行，但历史变慢根因UNCONFIRMED、无正式deployment资格；17attempts中6fully exported M2 valid、25nonzero native plans/143645associated native steps，这是实际执行证据，非online adaptation。side `b_runtime_qualification_decoupling_v1/REPORT.md:3,53–59`；`b_fast_jitter_m2_host_v1/REPORT.md:3–7,48–74`。

## 初版时间线

| 可核实时间 | checkpoint/工作 | 推动问题与结构变化 | 证据边界 |
|---|---|---|---|
| 2026-06至07 | Spring2D → 2026-07-30 closeout `82e4822` | 在简化elastic rod上研究MPC/辨识/安全/信息可辨识性 | 非Human V2、非机器人执行 |
| 2026-07-30 | MATLAB intake `c3957e8` | 示意双臂脚本需区分model/controller/endpoint，并审计符号/重力一致性 | 教授原参考，非教授最近汇报证明 |
| 2026-07-30至08-16 | physical linked Human、Human V2、single-arm/load-transfer | 直接关节力矩示意转向合法endpoint force与真实物理可行性 | 早期force分支非当前active plant |
| 2026-08-23至24 | sleeve MuJoCo → rigid cuff → Stage3 UR10e | 将cuff force/moment、robot torque与coupled plant写清，固定15sreference | engineering smoke，surrogate |
| 2026-08-24至29 | Stage4 adaptive tracking、robustness | 不确定患者模型影响tracking；有效模型+causal trust+shared gates | 正式有限Human family，不等于当前B |
| 2026-09-01至08 | executable contract、High-ROM与control velocity修正 | command-safe与physical-safe不等；feedback latency是重要结构瓶颈 | 老FAIL保留；corrected仍有SAFE_INCOMPLETE |
| 2026-09-14 checkpoint `e6ea54b` | Stage5 goal torque MPC | 从whole time-reference转phase目标，暴露interface prediction/hold/handoff/motion问题 | 首complete历史motion-envelope disabled |
| 2026-09-23 checkpoint `bd7952f` | recovery V2.2+Human-waypoint V3 | directΔq有限候选、quintic、adaptive screen、causal records | Phase3接口smoke，不是fullrobot闭环 |
| 2026-09-25至29 | full3D、100ms lifecycle、40ms escape、source/ownership | planner迟到与handoff需可验证准入与合法旧command延续 | host/scientific gates各自记录 |
| 2026-10-07至08 | multi-rate、native FAST、qualification decoupling/jitter | compute与task完成/因果/FAST/R2分开；有限host执行 | 无正式deployment资格 |

## 教授主线的因果解释

第一条主线是**真实运动权限**：从简化force对象、教授直接关节力矩示意，转到被动Human只能由robot+cuff真正推动；这使低力结果开始有物理含义。

第二条主线是**谁规定协调运动**：先外部固定整条quintic与速度，MPC优化跟踪的generalized torque；接着goal torque MPC允许path-free motion，但prediction/execute/motion合同暴露；最后高层直接选择下一对joint waypoint，scheduler保留确定性光滑规划，真实robot executor闭环落实。

第三条主线是**计划能否在真实状态及时落地**：fit成功、candidate feasible、plan被选中、physical task完成、causal host与实时资格是不同命题。B工程机制让这些命题可审核，使后续E/Q/自由参考的收益不会来自未执行计划、伪造state、过时计划或未来command归属。

尚不能推出：真实患者舒适、临床安全、硬件CR12实机能力、任意Human泛化、3–5repetitions个体化、当前B正式hard-realtime资格。


# 早期RL路线与复合历史报告的阅读规则

这些研究属于Learning之前/并行的历史尝试，需与当前B-native Q/M2分开。以下数字仅按已保留原报告恢复（HISTORICAL_REPORTED），本轮没有旧模型推理、训练、物理复放或raw重新积分。

## 直接RL并不等于当前残差计划Q

`direct_rl_expert_v1`想让policy定期独立提议两个continuous目标，但原q/dq-only quintic在20/50ms重发同目标会造成ddq不连续，首段probe约.076–2.070rad/s²；已有rolling suffix拒绝，接受的endpoint suffix又要.395–1.575s才生效。moving reference真实ddq不为零，而旧live activation要求零ddq。用户冻结安全合同下不能删除C2筛选，也不能把只在旧endpoint响应称为immediate direct control，因此在expanded-action安全门停止，Gym/SAC训练0。

这是“接口与安全表示不兼容”的证据，不是SAC训练失败或safe direct RL永远不可能。后续acceleration-aware interface的历史演变由总体架构稿解释。源主docs/direct_rl_expert_v1/DIRECT_RL_V1_REPORT.md行3、9–17。CUDA/PyTorch环境问题是次要预检，未安装；不能把GPU可见但CPU包错配说成GPU不存在。

## Scratch SAC300k：学到部分运动，没有获取完整任务

`single_human_sac_seed1_300k_failure_diagnosis_v1`对11checkpoint×NATIVE/MATCHED共22评价审计，10次OUTBOUND timeout、12次Q_BOUNDS，全部没有HOLD/RETURN，VALID0。训练873个completed episode成功0；最后100k replay全部OUTBOUND，completion奖励0。末期rejection已很低（275k/300k deterministic0），实际q大体跟reference，说明并非动作完全未落实或安全层永远拒绝。225k曾经过双关节目标位置，但速度约22.61/36.50deg/s，未满足停稳，位置proxy1.0不能当完成。

同wrapper fixed hip-leading在NATIVE与MATCHED都完整VALID，奖励审计也把成功回报远高于失败；没有证明全局reward错误偏好失败。主要SUPPORTED解释是scratch exploration/长时序task acquisition，稀疏成功信号与absolute target/settle接口是次要困难；网络/Adam有限、当前TD低不能证明成功，亦无数值爆炸positive证据。末期学习到avoid rejection不等于完成phase sequence。诊断新增五短rollout、训练0；300k旧训练与本轮诊断分母不能相加。

source：主docs/single_human_sac_seed1_300k_failure_diagnosis_v1/SAC_SEED1_300K_FAILURE_DIAGNOSIS_REPORT_V1.md:3–15,58,122,128–137。建议teacher/demo replay只是当时下一方向，不自动追认已实施。

## DAgger-to-SAC：学生会做任务，fine-tuning失去能力

因果55D expert通过hip-leading knee-preview与当前robust terminal reference产生label，不读future force或true Human。DAgger第3轮pure student3/3、第四轮再3/3，完整dataset13852state。学生可以完整NATIVE任务，J_F1950.059814、duration29.945s，却MATCHED0/3：三个phase约9.99/9.99/9.965s，HOLD过长，表现不等于强低力协调。

随后SAC在10000与20000两checkpoint NATIVE/MATCHED各0/3，触发预注册ability-loss gate，20000停止，保留last-good初始化，不存在fine-tuned VALID赢家。Actor行为显著漂移只是描述性证据；entropy、critic、replay比例没有经独立ablation证明为唯一原因。报告`SAC_ABILITY_LOST`不代表最初DAgger学生从未取得完整任务。

source：主results/dagger_to_sac_expert_v1/REPORT.md:5,28–40,95–104、docs/dagger_to_sac_expert_v1/DAGGER_TO_SAC_EXPERT_V1_REPORT.md对应主体。

## Anchored SAC50k：预算完成不等于优质协调或匹配资格

`dagger_anchored_sac_v2`最终真的完成50000 total collection（11283 frozen seed/calibration+38717 learning），active actor/critic updates3381/53727；41283能力失败后按原predeclared rescue恢复last-good，但gross consumed更新3881/58727不因restore消失。最好total31283的NATIVE J_F1667.567480，比低效student改善14.486%；final50000为1802.656266，最好优于最后。cold repeats是一个训练seed重复，不是独立seed。

性能改善主要是HOLD从9.990缩到4.740s：总J_F少282.492N·s，HOLD少279.923；对称分解duration term-282.659、mean-force term+.166。这不是在相同治疗时长下纯协调降力；MATCHED全部不合格，invalid数值不排名。最好仍显著高于同scope强fixed reference，不能用14.486%当现阶段M2、free teacher的收益目标或直接排行榜数字。

native major-checkpoint ability没全程保住；最终deterministic再有效也不消去中间失败，stochastic一失败一成功都保留。报告聚合最前是final50000，后又收录36283/21283 pause的历史版本，不应取最后一个pause当终态。resource修复仅日志streaming和owner lifecycle，没有改physics、reward与任务门。

source：主results/dagger_anchored_sac_v2/REPORT.md:3–7,29–41,77,89,91–101；docs/dagger_anchored_sac_v2/DAGGER_ANCHORED_SAC_V2_50000_REPORT.md为final独立原文。

## 这些负结果怎样推动后续E/Q

INFERRED：绝对目标policy同时承担任务获取、phase/settle时序与力优化，失败难区分“动作有物理效果”与“完整治疗任务学会”。保持B拥有HOLD/terminal、原native scheduler与安全链，学习仅选择bounded residual协调计划，可以隔离任务能力与协调力收益；先offline E找强teacher、再Q排名则给学习提供明确非零动作与完整remaining label。这是结构与历史结果支持的因果解释，不把各次不同动作authority实验强行归为同一个算法的递进性能曲线。

## 复合REPORT与索引不能只读第一个status

E results/REPORT行1来源SAC_CANCELLED_CLOSEOUT、行5BLOCKED；行144再标最终docs来源、行148E_SEARCH_COMPLETE。归档索引抽取旧第一status，不能覆盖后续CEM成功。anchored相反，首段是final50000，后段是历史pause。读版本注释、模型checkpoint、contract和真实run记录，才能恢复终态。源数据报告化之后，旧FULL_PACKAGE_MANIFEST不代表现完整镜像，必须按STORAGE_RETENTION_V2逐条范围解释。


# 阶段6–9：从学习排序到优质物理协调运动

本稿是本轮只读历史复盘的独立底稿，覆盖强专家E、Learning Q/M2、力与运动负担、counterfactual状态复制及自由参考。它不包括今晚新探索结果。教授上次汇报边界由主汇总核查；本稿不假定教授已经了解某一阶段。当前已经实现的是：在同一已暴露Human的仿真中，寻找并执行一些降低袖套累计交互力的协调参考。尚未实现的是：通过少数连续repetition可靠学会新患者的协调方式。

## 证据与比较规则

`CONFIRMED`用于直接源码/记录事实，`SUPPORTED`用于范围有限的实验结论，`INFERRED`用于结构解释，`UNRESOLVED`用于没有足够证据的科学问题，`HISTORICAL_REPORTED`用于本轮仅按历史报告引用、未重算旧raw的数字。下述REPORT有保留raw链接并不等于本轮已重算全部raw。报告化的普通历史trace不能承诺逐步复现。

资格另行区分：LEVEL0数学候选；LEVEL1完整原动力学实际可行；LEVEL2经B原生接口合法执行；LEVEL3 host-clock资格。`SCIENTIFIC_SIMULATION`允许计算时物理epoch冻结；`HOST_CLOCK_EXECUTION`受真实计算、异步等待、提交年龄影响；正式部署与临床资格另列。旧native residual有实际positive-step receipt是接口执行证据，不意味着host-clock已合格。自由扩展参考的最新主要声明明确止于LEVEL1。

每个研究包的J_F只能同该包匹配B、同任务和积分口径比较。下文时间线中的百分比是各自包内收益，不能将不同Human、起点、时钟、continuation合同或冻结M2实现的J_F横排为一个排行榜。force收益是一个重要物理指标；它不替代真实运动剂量、力矩、clearance、完成及安全指标。

## 6.1 为什么先寻找强专家E

在E/Q之前还存在直接绝对目标SAC、DAgger-to-SAC及anchored SAC试验，失败机制与本节native residual Q不同。scratch300k没有取得完整任务、DAgger学生取得任务后SAC又失去能力、anchored50k保住部分能力但主要减少过长HOLD，均不能叫患者个体化成功。完整区分见reports/RL_PRECURSORS_AND_REPORT_VERSION_NOTES.md；其中anchored确有50000采集步，不能与下面E包“取消50000要求”混同。

学习需要一个值得学习的运动，以及可解释的比较上限。若B候选库本身只有相近或低质量动作，即使Q将它们正确排序，也未必产生有意义的康复收益。E阶段先以高预算离线物理搜索建立best-known benchmark，区分“没有学会”与“给定动作族中本来没有更好运动”。这里E是搜索专家，并非自动等同于训练成熟的RL策略。

`single_human_expert_e_v1`冻结K=2 remaining-progress chunk：结点比例[.1,.7]，归一化残差边界[-.2,.2]，起点使用当前因果公共进度，阶段两端残差为零。只有B原生interior目标请求处更新chunk；HOLD、terminal、settle仍由B拥有。搜索按phase与native interior decision index查表，十次机会二十参数。它不直接设置人体qpos/qvel，也不绕过B运动调度、机器人执行器、原安全筛选。

该包bounded CEM共92次新增search attempt，92次完整且valid，确认`E_SEARCH` J_F=1360.602793 N·s，相对同条件B=1438.613498降低5.422631%。力矩积分却提高22.177817%，因此不是多指标全胜。原SAC 50k要求被用户修改预算取消：49条返回transition及49次gradient update保留；checkpoint0为BC mean，冷复验2/2有效。不能把预算取消称为SAC失稳，也不能宣称E是已完成50k训练的RL专家。来源：主库docs/single_human_expert_e_v1/SINGLE_HUMAN_EXPERT_E_V1_REPORT.md，行3–13、25–35、45–60；本轮数字证据为HISTORICAL_REPORTED。

版本恢复注意：主results/single_human_expert_e_v1/REPORT.md先组合旧SAC_CANCELLED_CLOSEOUT的BLOCKED，再于行144起追加最终E_SEARCH_COMPLETE（行148）。统一归档索引取到前一个status，不能按索引第一条将E_SEARCH终态错误写成BLOCKED；两个阶段和原失败同时保留。

`expert_strength_value_adequacy_v1`再做同空间三次重启，最好1356.790798；只比冻结K2 E改善0.280170%，未达到该包0.5% material门槛。丰富差分K3搜索取得1348.371552，相对旧E再改善0.898957%；confirmation成立，力矩比B增23.655%。其common-mode诊断没有运行，不能将“共同进度被限制”追认成已测根因。K3收益也不证明K2数学上无法表示实际执行路径，因为native planner只是按自己选定nominal waypoint采样graph，坐标、初始化与覆盖也会改变搜索结果。108 attempt含106完整任务和两个失败/中止，全部保留。来源：主库docs/expert_strength_value_adequacy_v1/EXPERT_STRENGTH_VALUE_ADEQUACY_V1_REPORT.md，行3–17、29–47。

更重要的发现是多步依赖：四个snapshot的L1/L2/L3/full前缀诊断中，OUTBOUND_3的一步收益为-5.179440 N·s，而完整收益为+49.790775。仅把“下一步后回到B”的成本作为永久Q^B目标，会漏掉需要后续配合的运动。这推动后续remaining-repetition cost-to-go与明确continuation合同。该证据来自四个已暴露诊断state、K2 prefix，不是K3 continuation已完整资格化，也不是few-shot训练样本。

## 6.2 早期96D价值学习与原生120D Q是两条不同历史线

2026-09-30的`value_learning_research_v1`采用96D estimated state/belief、reference、task、continuation及candidate target/delta。27组共同状态分支用于局部排序；503条VALID MATCHED轨迹、6162实际激活决策，按条件划分train/validation/test=3811/1177/1174行。MATCHED固定声明续行时长，NATIVE_SCHEDULER研究绝对best-known，两者不能混为一个性能范围。FULL ridge的validation regret0.684，test regret3.555且test排名ρ=-0.333，证据只支持有限开发成绩。

该96D ridge含显式progress/span/beta/phase×candidate_delta交互；96→32 tanh→32 tanh→1 MLP也有联合交互。FULL ridge按validation优于FULL MLP，但SHORT MLP的test FULL regret2.1946优于SHORT ridge8.5562。因而“历史MLP始终输给linear”不准确。FULL/SHORT预测目标不同，RMSE不能跨目标直接比较。

连续学习pilot也没有实现目标：SCRATCH和PRIOR各8次attempt仅4次VALID，来自新的开发片段而非连续Human/adaptation会话；PRIOR未显示先验改善，SCRATCH第三个有效片段选中已存在候选。跨epoch起点bootstrap后estimated dq超过原2°/s启动门，native continuity失败；不是得到“八次连续重复已收敛”。该包858条新增记录包含711 VALID、128 INFEASIBLE、11 INVALID和8 INTERRUPTED_HOST_RESOURCE。报告状态是BLOCKED。其少数模型boundary promotion实际发生过，但不能用这些更新事件证明少repetition个体化成功。来源：主库docs/value_learning_research_v1/LEARNING_RESEARCH_V1_REPORT.md，行3–7、42–85及连续执行部分；历史报告数字为HISTORICAL_REPORTED。

## 6.3 B-native M2：学习器决定哪个剩余协调计划，B决定怎样安全执行

`b_native_learning_matrix_v1`把学习直接接到冻结B，移除P/full-repetition性能预测器、known_model truth provisioning和P-specific筛选。B依次负责因果commissioning/observer、adaptive human waypoint MPC、native scheduler/quintic、receipt governor、ROM/mechanics/clearance/tracking证书、current-model revalidation、机器人—人体仿真与fallback。Q没有取得HOLD、终点、robot torque或人体状态写入权。

M0是B；M1在六个ordinary计划上使用原B当前段score S；M2用同六计划加direct remaining-cost Q；M3为三个ordinary/B/carry加三个G head，并用S；M4对同mixed pool用Q。S来自原native clone decide/_evaluate，不是invented repetition predictor。九候选union只用于离线归因，不参与拟合。

120D特征合同可以按源码直接确认：55D因果commissioned B observation + 3D previous realized residual + 30D masked candidate table + 30D masked carry table + 2D issued counts。表形状为(OUTBOUND/RETURN,5 interior slots,3 graph knots)，已issued slot归零；counts除5。K3是一个native request内部的空间graph采样，不是三个独立控制周期。candidate集合包括zero-B、carry、historical design、正/负以及reversal等；随机扰动只改变冻结候选生成，不能当作状态学习。来源：side/b_native_learning_matrix_v1/code/native_core.py，行6–28，CONFIRMED。

Q输出单位N·s，标签=当前repetition完整实际J_F减已测prefix；branch将声明的合法masked K3 suffix提交到原B，其后仍经accept/reject/fallback，suffix结束回B。标签并非下一repetition成本，不是Q*，也不是持续在线Neural Q反复重选的已验证policy value。输入不使用未来真force、true q/dq或未来clearance；这些可作label与审计，不能成为部署状态。

初轮训练349行，最终253 train/73 dev，很多行是同源branch后续相邻状态。原120→128 ReLU→128 ReLU→1有32229参数，loss含标准化absolute MSE加10倍同state pair差MSE。linear是标准化后ridge拟合原120D，没有交叉项。按dev regret再RMSE选模：linear regret0、RMSE8.523668；MLP regret0.851245、RMSE11.219440、harmful top1=1。五个dev group含两个zero-spread，只有三个有排序信息，且当时没有独立test gate。源码train_native.py行31–45、48–69确认训练与选模规则；结果数字为历史训练记录支持。

四十次scientific正式method运行（五方法各8）全有效：M2相对M0平均降力7.177%，其中nominal8.379%、合法deviation5.976%；M4平均6.085%，G没有稳定额外收益。M2 force减少伴moment mean100.496→124.568 N·m·s。总151/240 physical attempt包括分支、失败、复验等；四十方法运行不等于151独立条件。原host真实执行七次均invalid，因stale-at-apply/command-age等不能给失败截断J_F排名。Q平均推理约0.096 ms，但native validation约184.961 ms、total coordinator约215.354 ms，瓶颈主要在重复验证与提交链。来源：side/b_native_learning_matrix_v1/FINAL_REPORT.md，行17–51；该包scientific结果不能升级host资格。

## 6.4 linear有force收益，为什么仍没有真正state-conditioned ranking

源码feature()直接拼接，不乘state与plan；ridge模型也是z·w+b。因此固定候选集合、mask、carry及counts时：Q(s,p)=g(s,history,carry,counts)+h(masked p)。候选i与j分数差只剩h(p_i)-h(p_j)，公共state项严格相消。绝对Q随状态大幅变动，并不改变固定池偏好。

`m2_host_generalization_attribution_v1`对131个真实旧/新决策（OUT58、RETURN73）审计，固定池解析及mixed-precision native排序均只有一种，top变化0，pairwise误差最大3.41484e-6 N·s；state×plan交叉导数0。Mask可让已issued slot消失，carry可改变候选身份，native feasibility/current admission可改变可执行集合，late-result可回carry。这些机制确实依赖状态和时间，但不能归为Q学会了状态条件偏好。来源REPORT行43，CONFIRMED；native_core.py行6–12、train_native.py行40–42为直接源码支持。

与此同时，同一包四对prefix×seed的真实host研究中M2都降低force，合并6.828%，每对约5.664%–9.008%；8物理run原安全与causal轴PASS，19个Q-selected非零计划、107891关联native steps。RETURN贡献85.578%，平均力项解释99.962%，不是靠缩短HOLD偷取主要收益。这个结果支持“冻结偏好经B可行性与执行器实现有实际force价值”，不支持“已经学会依患者当前状态改变排序”。两个prefix早期SCI已暴露，两seed复用，不是新Human或人群泛化；9 attempted dispatch中一诊断启动失败为0物理步。formal runtime未运行，legacy R2和strict55均FAIL，observed FAST还两次rolling FAIL。来源REPORT行5–17、19–45、FAST表。

## 6.5 新32×32 Neural Q的负结果说明什么

新joint120→32 ReLU→32 ReLU→1，4961参数，有state×plan交互；16×16与32×32各按validation regret再RMSE选择，二者validation regret0，32×32 RMSE更低。结构probe中plan差随state变化，说明非加性表达存在，但probe合成组合无物理rollout标签，不能当真实决策成功。

80条合法branch-start row被按来源整轨迹划分47/16/17，来自8/3/2 snapshot、2/1/1父来源；总13snapshot、4来源、同Human。64个test非tie pair来自两个state，不能当64个独立实验。新模型test mean regret9.9306，旧linear1.6207，历史128×128为16.6014；新模型仅比大MLP部分改善，没有超过linear。三个top1比例不足以遮盖错误动作实际代价：OUTBOUND错选candidate7带19.8612 N·s regret，RETURN正确。测试来源是公开历史诊断，只未用于本轮拟合/选择，不是前瞻新Human数据。

后续counterfactual复盘又发现：74 ordinary候选在13snapshot上fixed regret全部为0；加六个历史G head的80行cohort只有一个OUTBOUND额外机会3.241335 N·s。该机会首先是candidate coverage扩展，不是已证明same ordinary池必须state-conditioned ranking才能获益。三个共有计划、相同mask/carry的匹配层未观察ranking inversion。这不证明所有状态排序永远相同，却解释当前监督缺乏足够“同一计划在状态变化时由好转坏”的独立标签。直接加大网络容量没有证据；更大的历史MLP也较差。

主要瓶颈应分开：有效独立状态很少；RETURN状态高度收敛；candidate/mask变化与真正state preference混杂；dense motion最初不完整；V_commit标签与rolling V_replan合同不同。结构交互能力只是必要条件之一。source：side/m2_neural_q_motion_v1/DATASET_AUDIT.md行5–23、NEURAL_Q_EVALUATION.md行13–39；side/m2_motion_counterfactual_ranking_v1/REPORT.md行27–41。此轮不重训。

## 7. force下降与人体运动负担产生冲突

host四对归因中moment积分增加13.28%–25.64%，knee true-reference TASK RMS增加0.341°–0.424°，3/4 clearance下降，一次force peak上升4.229703 N。再对历史八组B/M2 dense真运动核查，八组knee max/p95速度、p95/RMS加速度都更高，excursion增加1.109°–2.834°、累计角位移多2.191°–6.707°。轻度滤波不改变主要方向；hip RMS速度略降、jerk混合。因此force优并不构成更平顺或治疗剂量相同。

moment是力矩，积分单位N·m·s；momentum是动量，不能由moment integral直接推断。旧B-relative的10%速度/加速度与指定jerk非劣、0.5°行程差、累计量±5%、端点/phase边界±0.5°、时长±0.1s、moment≤25%和tracking等都是冻结研究比较协议。它们不是临床统一舒适阈值。旧motion FAIL不能改称PASS，也不能直接等同临床不安全。

强低力C2在同父scientific比较可降15.090469%，但knee负担及行程FAIL。lowforce修复去掉M2 RETURN slot0可保留约83.91%降力，行程差2.453°→1.296°、moment/tracking失败消失，但速度/加速度、jerk和行程仍FAIL；另一强链保住13.819507%、约91.58%原收益，同样未合格。接近边界0.812734%且约束比1.010916仍判FAIL。真实速度超对应B max110%的持续时间约M2 2.342s、C2 2.566s，不能解释成孤立数值尖峰。源lowforce REPORT行9–19，结果SUPPORTED限定局部干预。

## 8.1 旧snapshot为什么不能单独恢复

counterfactual要问“同一完整状态，如果换一个计划会怎样”。只有human q/dq相同不够：MuJoCo integration、mutable model、commissioning/observer历史、reference phase、controller/planner/scheduler、carry、issued slots、生命周期、native handles及RNG都可能影响后续。旧JSON snapshot只保存process-scoped摘要，数组、integration和长历史为hash，opaque handle靠活进程继承。15个snapshot文件中13个cohort使用，没有durable可恢复checkpoint，也没有原父进程。报告停止在RESTORATION_GATE，新增branch0/30，不能新建近似plant再称同初态反事实。源counterfactual REPORT行19–23。

同包从历史runtime_artifacts重新恢复80条约0.25ms原生qpos/qvel，只做审计不仿真。cost闭合必须用包含边界的TASK prefix记录，不能误用运动导数去重索引；完整终值减prefix与首value row误差最大4.37262e-9 N·s。V_commit可用于有限表标签，但历史SCI OUTBOUND selected committed比rolling剩余高20.646403、RETURN差0；两处只有原selected action一个rolling结果，没有其他candidate滚动反事实，不能测V_replan候选排名或把20.646403当host偏差界。

完整motion/fairness三档strict/moderate/wide筛查80→13，均只剩zero，67非zero全部被phase-shape等完整条件排除；不是证明物理空间全局无解。若仅看负担10%/25%或去掉phase-shape，仍有有限小收益state。这是敏感性诊断，不能事后放宽原规则。

## 8.2 live-state fork解决的是科学可复现性

直接触发匹配研究的是先前`m2_coordination_space_exploration_v1`：22/24实际attempt全部physical/causal通过，但legacy R2与strict55全部FAIL；12候选中3通过研究比较，选0.10倍RETURN表发现降4.1077%，两个保留seed仅+.1491%与-2.3865%，资格0/2（加速度/jerk失败）。发现候选完整降61.574911 N·s，其中OUTBOUND降53.240124，远早于RETURN动作。3次同seed B-zero范围26.067509；这些诊断揭示cold commissioning与native activation机会差异，不能挑最好的B重做分母。原Stage D新自由度未运行，终态DISCOVERY_NOT_VALIDATED。source：side/m2_coordination_space_exploration_v1/REPORT.md行3–7、85–95。这推动从“相同初始设置”改为“同完整实际状态”的公平比较。

`m2_matched_bidirectional_exploration_v1`在quiescent活父进程中Linux address-space fork，继承上述物理、控制、估计、phase/lifecycle、RNG与native handles；hash用于核验，JSON没有用于恢复。两次same-control全部归档trace、116320 native行、5817 receipts精确一致，child后parent hash不变，完整入口及RETURN入口匹配。这使干预前negative control与同状态候选比较成立，限定SCIENTIFIC_SIMULATION。它没有复制OS scheduling，不等于host同状态因果时钟反事实。

该包还纠正旧RETURN-only“去程改善”：旧发现OUT减少53.240124 N·s，但RETURN前没有非零执行，差异从commissioning t=.010s开始，属于pre-intervention imbalance。三次B-zero范围26.067509 N·s；n=3只能定位早期执行/观测差异，不能断定beta或OS是唯一根因。

真正同完整父状态比较：B0=1438.613498，O收益0.1197%、R0.3305%、OR0.4502%，皆motion/safety/fairness通过但低于预注册0.5%发现门。R从同RETURN入口独立分叉减少4.755075 N·s；OR约为O与R加和，交互仅-2.147e-8 N·s。Frozen M2同父force收益8.7997%却motion FAIL。16/18 attempt、12完整导出，保留验证NOT_RUN，没有调整发现门让结果通过。源matched REPORT行3–23、29–50、56–62。

## 8.3 从候选稀疏到可执行协调搜索，再到连续调整

comprehensive把范围扩展到phase、sign、amplitude、slot mask、onset/support、PWL knots/shape及双阶段独立参数。128完整search comparison中29 motion接受、4达到≥0.5%发现门；151/160 attempt含147完整任务，534非零native计划。最低force C2降15.090469%但FAIL；best eligible C4_1_5只在RETURN index2实际采一个负delta=-.029054927948，4520 native步，完整降10.627926 N·s（0.738762%），H1/H2为0.746213%/0.737962%，均PASS。这是同Human有限合法prefix的SCI_VALIDATED，不是人群泛化。

PWL graph自由度与执行自由度必须分开：native request只按nominal target公共进度采一个delta，再反对称分配[delta,-delta]。改变完整PWL形状并不授予每个物理step独立目标、时长或速度控制。raw_v2里的旧K3 action/previous=[0,0,0]是日志占位，真实action要从graph/spec与native metadata读取，不能将占位零直接纳入旧120D训练。

lowforce修复再探索268/300 attempt、262完整任务、215完整search/comparison，观察198条不同实际非零native序列。最佳NATIVE_SCALAR_18只在RETURN slot1/2采delta=-.020/-.022，9460 native步，去程/HOLD差0，RETURN降16.768044 N·s（1.165570%）。开发motion PASS但knee excursion .496750°距离.5°只剩.003250°；三个保留条件3/3、收益平均1.167181%。事后状态审计发现首次RETURN实际执行时q差最大3.94e-9rad、dq约1.03e-10rad/s：HOLD/端点续跑让RETURN高度收敛。3/3仍是注册条件配对通过，但不构成三个显著不同RETURN决策state。

该包广域比例整体31.17%，未达到用户要求40%；第三批超时截断以及NATIVE_SCALAR_19未知尾部compute保留，新增native steps至少20538960，不可称精确总数。其研究局限应与可信小收益一并向教授解释，不能只报PASS。

sequential允许合法后续边界fork，前序动作真实物理推进再比较suffix，不能把独立branch收益相加拼接。最好O0_+.006叠native18，三次实际非零调整（OUT .006；RETURN -.020/-.022），完整J_F=1419.188352，降1.350269%，SCI_DISCOVERY_ONLY。79/90 attempt、77完整归档；后续边界最优合格1.306938%。OUT单动作到RETURN0 q/dq差仅3.943e-9/6.446e-8，没有state-conditioned重选收益依据。V1 best1.379487%因motion FAIL；V2只完成B0与native18，best等未运行，不能说best已完成两条件验证。源sequential REPORT行3–27、31–63。

## 9. 更自由参考怎样出现，当前最好结果到底是什么

先前只调相对进度delta，common progress与中间路点速度主要由B决定。连续多slot仍不能表达请求间任意函数。为分辨有限候选/接口表达不足与真正物理权衡，`m2_free_trajectory_feasibility_v1`在隔离side-study保持完整原机器人—人体动力学，扩展OUT/RETURN各自共同进度、差分进度常数/倾斜、独立hip/knee通过速度，共10维。请求产生pose/dq意图，仍由quintic、governor、bridge、lifecycle、current admission和真实六轴torque闭环执行。没有human主动torque、qpos/qvel回放或接触绕过。它是连续函数定义的分段quintic，不是任意时间样条，也不是原native PWL逐步持续执行。

扩展zero全trace、76121 TASK人体native样本及全部receipt/torque复现PASS。最佳`development_resume_main_NATIVE_SCALAR_18_029` J_F=1403.259730，比同条件B1438.613498降35.353768 N·s、2.457489%；OUT/HOLD/RETURN减少17.273197/.000006/18.080565，积分闭合。所有冻结主运动/安全/任务条件PASS，达到≥2%里程碑，未达到≥5%。64个positive-step自由候选中10合格，84/96 attempt含错误、partial、repeat和验证；有限COBYLA budget终止不能称收敛或全局最优。

最新主要声明明确LEVEL1，扩展参数非零，不能称原B正式native LEVEL2已实现；LEVEL3与硬件未做。两组冻结后未用于选参的合法RETURN早期前缀W1/W2，同Human从真实前向动力学生state，remaining suffix资格1/2：W1降2.424287%但excursion FAIL；W2降2.379705% PASS。R0被条件prefix消费，不能称整串原动作独立未见验证。两条件真实RETURN1 q差.0143721rad、dq差.000536421rad/s，覆盖比此前接近零RETURN差更实质，但不是跨Human。

最佳knee p95速度比1.086165、max加速度比1.090230，行程差.497545°又贴近.5°；moment106.797982 vs100.417251 N·m·s，phase shape最大差14.238075°，jerk max比1.182036仅诊断。因此研究motion PASS并不意味着每一个平顺指标变好或治疗轨迹等效。最低力代表15.549494%仍因速度/加速度、excursion、duration、moment、tracking等FAIL。冻结字段消融no_free_velocity收益1.692630%但FAIL，no_free_common_progress2.538821%但FAIL；不能把后者更低J_F误当新合格赢家。

来源free REPORT行3–35、55–100及PHYSICAL_ACTION_SPACE.md；参数、控制权限与验证条件可由紧凑JSON继续审计。结果支持已有更好LEVEL1离线teacher；仍需验证如何迁移为B原生合法接口、在更不同状态/人体中保留收益，并定义临床任务允许的中间姿态范围。当前转向优质物理运动不是放弃学习，而是在学习前先确认动作、标签与任务质量确实值得学习。

## 问题推动的时间线

|问题/触发|结构变化|得到的证据|没有得到的能力|
|---|---|---|---|
|只跟踪或原B局部score不能说明best-known协调收益|离线E高预算真实物理搜索|K2强E5.42%、K3再有小幅提升|没有全局最优；不是成熟RL expert|
|孤立一步好坏会漏多步配合|remaining-repetition cost-to-go及固定suffix标签|四state多步诊断有一步/完整符号变化|V_commit与V_replan不自动等价|
|需直接接到B、隔离P/truth|120D causal state/plan/carry/count native Q|科学M2约6%–9%force收益|linear仍固定mask偏好；host未正式资格化|
|force好而膝速度/加速度/行程变差|dense motion、剂量与多指标审计|真实负担上升，强降力未成整体成功|没有临床舒适阈值|
|旧hash snapshot不能重启反事实|quiescent live address-space fork|同动作全trace/receipt精确复现及parent不污染|没有durable checkpoint；没有OS时钟复制|
|冷启动混杂冒充RETURN收益|同完整入口与RETURN negative control|O/R/OR小幅真实效果；发现门失败|没有把旧表面大收益追认因果|
|固定K3库稀疏、raw PWL被单点采样|更广可执行搜索与连续slot干预|0.7388→1.1656→1.3503%合格发现|RETURN状态收敛；best验证覆盖不完整|
|原delta不能控制共同进度与路点通过速度|隔离10D自由参考、原quintic/torque forward执行|开发2.457489% LEVEL1 PASS；W资格1/2|未证明LEVEL2/3、few-shot或跨患者|

日期：96D报告生成2026-10-01 05:34:31+08（研究包以2026-09-30命名）；native Q初轮seed为2026100611但seed不是运行日期；host attribution t0=2026-10-08 20:59:12+08；counterfactual保守t0=2026-10-08 23:51+08；comprehensive冻结RUN_PLAN t0=2026-10-12 21:16:15+08；lowforce t0=2026-10-13 02:58:22+08；sequential冻结RUN_PLAN t0=2026-10-13 14:17:42+08；free冻结RUN_PLAN t0=2026-10-13 18:58:37+08。其余本稿不凭包名/seed推断日期。三份RUN_PLAN原字段已转换为Asia/Shanghai，见reports/COMPACT_EVIDENCE_VERIFICATION.json。

## 教授讨论时需要分开的决定

1. 相同ROM、endpoint、phase duration允许多少中间hip/knee姿态与phase-shape改变？研究PASS是否保留了临床意图，需康复任务依据。
2. 真速度/加速度/jerk、累计角位移、力矩与clearance该如何优先评价？现10%/.5°/±5%为比较协议，不能当统一临床标准。
3. 保留原native离散目标的可审核安全链，还是增加bounded common-progress与独立pass-through velocity接口？后者已有LEVEL1 teacher，却需要接口与host证明。
4. 下一学习数据应先证明同固定candidate在不同合法state最优确会变化；otherwise复杂Q在固定排序baseline之上没有足够可学增益。如何增加独立来源且避免HOLD抹平RETURN差？
5. 选择V_commit、V_replan或完整策略值哪种监督？不先冻结执行/continuation合同，更多数据与网络可能继续学习错误问题。
6. 科学贡献优先落在执行架构、优质协调优化，还是少repetition personalization？后者目前未证明，前两者有实测贡献和明确局限。

阶段6–9历史复盘子任务只读WSL主库/side-study，仅向专属Windows staging写紧凑报告/源码摘录，该子任务新增物理、训练、Git及系统修改均0。整体夜间campaign实际attempt与失败见ATTEMPTS.jsonl及EXPLORATION_RESULTS.json。重算范围见EVIDENCE_LEDGER.json及reports/COMPACT_EVIDENCE_VERIFICATION.json：本轮独立复核紧凑记录的free收益2.4574889745%、phase闭合误差-2.27e-13 N·s、W1/W2资格1/2、131固定池唯一排序、linear系数差分与native18 RETURN收敛；没有重新积分全部旧raw或新仿真，不能将文档/紧凑核验当新物理资格。


## 完整研究史中的当前位置

现在真正缺少的不是又一个网络名称，而是三个相互衔接的证明：第一，符合治疗任务意图且有实际力收益的运动；第二，在不同合法状态中确实需要不同的协调选择；第三，这些选择能通过原B接口与真实时钟连续执行，之后才能研究少repetition个体化。今晚扩展参考属于第一项的隔离LEVEL1探索，没有跳过后两项。

不把所有旧失败解释为项目失败。High-ROM、HOLD/RETURN、strict55/R2、Neural Q、snapshot restoration分别指出物理任务、时序合同、监督目标或复现机制的边界。失败推动了更准确的架构和比较方式，这也是研究贡献的一部分。亦不把包装代码成功、报告文件齐全或storage核验PASS称为科研问题已解决。


## 本轮实际Human与任务：不能用类默认值代替

源码实际加载`high_rom_nominal_sync_120_v1.json`与其options合同，而不是早期Phase3的80°/100°默认任务。当前case为1.72m/75kg名义Human，rest5°/10°，K=10/10Nm/rad、B=5/5Nms/rad，cuff为shank的72%；start/return目标5°/10°，OUT目标120°/120°。`high_rom_v1.py`从冻结配置构造双方0–125°hard ROM与5°soft margin，这是一项明确工程假设，不是患者测得ROM。任务goal位于soft-limit onset，距hard bound5°。

原task合同要求角终值误差≤1°、速度≤2°/s，并另有controller更紧margin；原最低continuous HOLD为0.5s。当前MATCHED研究与其既有执行路径实际阶段时长约OUT9.005s、HOLD1.020s、RETURN9.005s、完整19.030s，所有新候选仍与该匹配B按冻结时间规则比较，不能把合同minimum与实际HOLD混写或缩短HOLD获益。原独立速度/加速度工程限为45/75°/s与300/600°/s²，另需更严格的B-relative motion比较，两层不互相替代。

人体参数用于隐藏plant创建/评价；controller使用明确ROM先验、合法任务目标及commissioned估计，真实q/dq留在evaluation。cr12_plant绑定六个既有motor；原sleeve weld在此bushing模型中关闭，接触由原spring-damper paired force/couple驱动，不是将参考强制焊接为人体状态。本轮不修改此物理定义。完整config/options与来源哈希、actual baseline起点和阶段时长见CURRENT_MODEL_AND_TASK.json；源为sac_env.py:147–150、high_rom_v1.py:10–30、runtime_coordination_residual_v2.py:1960–1978、cr12_plant.py:272–345。原初始化/reset写qpos不等于优化期间人体状态控制，后者未授权也未加入。


<!-- OVERNIGHT_FINAL_START -->
## 本轮夜间探索的最终补充（2026-10-14）

本轮未训练学习器。保留原机器人、被动Human、接触和执行约束，在隔离研究中将原10维意图扩为18维：两方向的共同进度倾斜/曲率、差分进度曲率、髋膝速度倾斜。参数仍经原quintic与原筛选/准入，再由六轴robot实际执行。

同完整开发父状态，冻结最好`development_repair2_quality_NATIVE_SCALAR_18_063`下降2.635613%，全部冻结motion规则PASS；相对旧2.457489%增加0.178124个百分点。这是一项有限开发改进，不是全局最优。16个±0.4新轴probe和后续三个区域的有限COBYLA结果保留；joint optimum不能把增益简单分摊为某一自由度的贡献，详见MECHANISM_ANALYSIS.json。

冻结primary在四个预注册合法prefix条件中合格0/4、完整任务4/4。四条件都来自同一已暴露Human；仅未消费suffix被测试，共享prefix不属于未见完整原策略。失败保留且不从分母移除，secondary事先冻结而没有用测试改选primary。VALIDATION_RESULTS.json记录完整candidate身份、冻结文件hash和先后时间、配对初态及干预前物理/控制相等。

最低force代表下降16.816751%，motion FAIL，失败项['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'RETURN_duration', 'excursion', 'cumulative_dose', 'task_duration', 'moment_integral_Nm_s', 'tracking']。它保留为负结果，不能称优质teacher。实际START/END=148/148，包含两次包装失败和真实commissioning，不把数学拒绝当physics。全部科学结论最多LEVEL1，未新增原B接口、host、硬件或临床资格。

与教授的关键问题仍是：允许多少中间姿态变化、怎样评价平顺与治疗剂量、何时迁移最小参考接口，以及何时才具备few-repetition学习值得使用的state/action/label证据。

<!-- OVERNIGHT_FINAL_END -->
