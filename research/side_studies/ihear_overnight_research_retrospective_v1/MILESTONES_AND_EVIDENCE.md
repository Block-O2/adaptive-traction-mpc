# 主要结果与证据：按研究问题阅读

本表保留各历史合同的PASS/FAIL，区分任务完成、motion比较、科学执行、host与正式部署。原strict55/R2 FAIL不追认PASS；新拆轴runtime合同的结果另列。速度/加速度10%、行程0.5°与剂量±5%是研究比较协议，不是临床标准。

证据等级和数据去留：CONFIRMED直接源码/记录；SUPPORTED有限实验；INFERRED解释；UNRESOLVED证据不足；HISTORICAL_REPORTED仅报告数字。保留原raw不等于本轮重算全部raw。EVIDENCE_LEDGER.json附每项source/行号/分母/可核验范围。

# 阶段1–5主要结果与负结果：可供总表直接引用

| 系统/工作包 | 结果 | 有效分母 | 此结果不能说明什么 | source / line | 等级 |
|---|---|---|---|---|---|
| 教授MATLAB | 12s完成；hip/knee max error1.16/1.14°；等效arm力峰4.4/5.3N | 一次成功原脚本capture；capture wrapper先前异常保留 | 没有真实robot actuator；直接Human joint torque，因此不是低cuff交互力 | git:c3957e8:linkage/docs/MATLAB_CODE_AUDIT.md:399–434 | HISTORICAL_REPORTED |
| linked Human V1 plant | 18rollouts完成；15tests通过 | 3trajectory×3synthetic profile×2contact mode | direct torque oracle验证plant，不证明force-only可行 | git:dc8a160:linkage/docs/PHYSICAL_PLANT_BASELINE.md:113–204 | HISTORICAL_REPORTED |
| ideal endpoint force | 数值完整9/9；nominal coordinated RMSE22.26/60.92°，condition1913，joint-limit3458samples | 3task×3profile=9force cases；另外9direct torque oracle | rollout跑满不等task成功；oracle≈零误差不证明cuff可执行 | git:586f8db:linkage/docs/IDEAL_ENDPOINT_FORCE_BASELINE.md:95–153 | HISTORICAL_REPORTED |
| Stage2 rigid cuff | nominal3°cycle RMSE.081/.195°；Fpeak109.81N；Mpeak27.19Nm；mild完成，moderate/adverse terminalfail | 四registered plant cases；nominal原15s与3°variant | 跑满15s不等terminal completion；不是hardware/clinical验证 | stages/stage2_linkage/docs/MUJOCO_STAGE2_VALIDATION_SUMMARY.md:46–100 | HISTORICAL_REPORTED |
| Stage3 UR10e full3D | 单15s smoke完整；RMSE.06850/.16920°；Fpeak111.207N；torque fraction.4720 | 一名义engineering smoke | 非CR12，非patient泛化 | stages/stage3_full3d/results/final_presentation/summary.md:3–11 | HISTORICAL_REPORTED |
| Stage4 crossed patient×trajectory×seed | promotion、completion、tracking/prediction RMSE improvement18/18；max error2case变差 | 18registered combinations | 不等每指标改善，不等current B或自由参考验证 | README.md:48–58；正式总包需要继续原report crosswalk | HISTORICAL_REPORTED |
| 旧HighROM90/120 lyingbed | command200N，但physical218.441N；16.046s force abort | 一原case；16047force samples exact reproduction；heldcommand5ms counterfactual | command gate不等physical gate；不能仅归因bed | STAGE4_PHASE_A_HIGH_ROM_INTERACTION_DIAGNOSIS.md:13–82 | HISTORICAL_REPORTED |
| suspended90/120 | 16.055s BRAKE_INFEASIBLE；Fpeak197.839N | 一新的contact counterfactual | 无seat/strap；不是成功或患者悬坐模拟 | STAGE4_PHASE_A1_B0_INTERACTION_AUTHORITY_AUDIT.md:15–45 | HISTORICAL_REPORTED |
| corrected Rigid/P1 NEW | rigid40/80 COMPLETE；90/12096.18/100%；120/12099.33/99.99%；后两SAFE_INCOMPLETE | 3case×2arms；1rigid40/80复用hashlocked | P1非HighROM可行必需；high progress仍非formalcomplete；原P1strict数值FAIL不变 | CORRECTED_BASELINE_REPORT.md:3–20 | HISTORICAL_REPORTED |
| 初GoalMPC smoke | 11SAFE_ACTION、43SAFE_UNCHANGED；.215s physical201.533N abort | 一动态smoke；attempt02report修正相同dynamics | 没有HOLD/RETURN；safe command不是safe physical transient | GOAL_MPC_V1_ENGINEERING_SMOKE.md:88–122 | HISTORICAL_REPORTED |
| first Goal complete | 4.615s；J_F443.642N·s；Fpeak173.252N；923SAFE_UNCHANGED | 一primary matched-modelepisode；attempt01–05含诊断/日志版本 | motion envelope当时disabled，后续blocked；非current qualification | GOAL_MPC_COMPLETE_V1_ENGINEERING_REPORT.md:8–11,38–91 | HISTORICAL_REPORTED |
| Phase3 HWMPC V3 | 14interface checks、47tests、19manifest；3plans42.20/64.91/65.48ms mean/p95/max | 三planning calls，非三个robot物理任务 | interface smoke不是fullCR12闭环或实时资格；V1NO-GO保留 | PHASE3_HUMAN_WAYPOINT_INTEGRATION_V3.md:59–97 | HISTORICAL_REPORTED |
| rho.60 commissioning/recovery | fit352samples lever误差19.899µm；46candidates拒绝；0recoveryintervals；trueclearance+5.170mm但certificate−1.827mm | 三原路径exact复现，其中2failed；1不同initializationoracle成功 | 准确effectivegeometry不等fullshank可辨识；oracle不是same-state | SIDE:commissioning-to-recovery-geometry-compatibility-v1/REPORT.md:7–47 | HISTORICAL_REPORTED |
| multirate R1/R2/R3 | sciencebit-identical三版本；host VALID0/13；R3qualification0/8，物理phase完成7/8 | 34START；12prephysics errors；22physical含8science/13host/1profile | physical完成不是strict55/R2/FAST资格；Q/M2NOT_RUN | SIDE:b_multirate_realtime_v1/REPORT.md:11–31,50–84 | HISTORICAL_REPORTED |
| runtime decoupling | 新4complete host task physical/causal/current admission/backlog PASS，FASTtail FAIL，B NOT_FROZEN | 5attempt=1startup+4complete tasks | 旧047/048新runtimePASS不改旧R2FAIL | SIDE:b_runtime_qualification_decoupling_v1/REPORT.md:3,53–59 | HISTORICAL_REPORTED |
| jitter/M2 finite host | 当前FAST恢复；6fully exported M2valid，25nonzero native plans/143645steps | 17physicalattempt；fullpair4pairs；旧FAST根因未确认 | M2_HOST_RESEARCH_FEASIBLE非deploymentqualified，非online personalization | SIDE:b_fast_jitter_m2_host_v1/REPORT.md:3–7,48–74 | HISTORICAL_REPORTED |

当前窗口只读恢复以上数字，没有新增simulation与逐raw重积分，所以不把报告层数字标成新CONFIRMED物理验证。主SOURCE_EXCERPTS记录direct source支持，ledger中的架构主张可以CONFIRMED；这些两种强度须保留。

不可横向排J_F或force peak的原因包括：Spring2D/linked Human/Human V2不同动力学、直接joint torque/ideal endpoint/rigid或soft cuff不同权限、ROM/目标/时长不同、bed与suspended contact不同、surrogate机器人不同、clock合同不同。只有同父状态、同模型、同task与同口径的配对才解释差值。


# 性能、分母与负结果表（阶段6–9）

这张表按研究问题分组，各百分比只相对该行报告的匹配B/专家。表格不是跨条件J_F排行榜；同样写1438.613498的B也须有同状态/动力学/时钟/积分复现证据，不能仅凭数字相同认定可比。`报告数字`表示本轮未重算该包全部raw；`紧凑记录复核`只验证已保留JSON及算术，不升级为新物理实验。

|研究族 / 方法|实际结果（包内比较）|有效分母与覆盖|重要负结果 / 限制|科学与执行资格|来源|
|---|---|---|---|---|---|
|96D Learning Research / FULL ridge|validation regret .684；test3.555 N·s，ρ=-.333|27共同state分支；503 VALID MATCHED轨迹、6162决策；858新增记录：711 VALID/128 INFEASIBLE/11 INVALID/8中断|连续SCRATCH/PRIOR各4/8VALID，非连续state；五轮收敛未支持|COMPLETED_BOUNDED_STUDY_WITH_NATIVE_CONTINUITY_BLOCKER；非host/clinical|主docs/value_learning_research_v1/LEARNING_RESEARCH_V1_REPORT.md:3,42,74,85|
|96D SHORT MLP vs SHORT ridge|test FULL regret2.1946 vs8.5562|历史按condition/session划分；不是native120D池|SHORT MLP曾优于ridge，不能说MLP必然差；FULL/SHORT RMSE目标不同|历史离线学习；报告数字|side/m2_neural_q_motion_v1/HISTORICAL_MLP_RECOVERY.md:17,21,29|
|E K2 / E_SEARCH|1360.602793 vs1438.613498 N·s，降5.422631%；moment+22.177817%|92/120 search attempt全部完整VALID；nominal同Human冷确认|50k SAC预算取消；49返回transition不是50k专家；两cold是repeat非泛化|QUALIFIED STRONG EXPERT仅该历史科学合同；非正式host/患者|主docs/single_human_expert_e_v1/SINGLE_HUMAN_EXPERT_E_V1_REPORT.md:3,9,29,33,45|
|E strength / K3|1348.371552；比旧E再降.898957%，比bestK2再降.620526%|108 attempt含106完整任务、1 aborted、1 prephysics失败；3同空间重启|common-mode NOT_RUN；K3更好不证明K2数学不可表达；moment比B+23.655%|best-known探索benchmark；非全局最优|主docs/expert_strength_value_adequacy_v1/EXPERT_STRENGTH_VALUE_ADEQUACY_V1_REPORT.md:3,7,11,29,41|
|B-native M2 / direct Q|40method SCI运行全有效；M2配对降7.177%，nominal8.379%、deviation5.976%|5方法各8：四同trajectory重复+四legal deviation；151/240总attempt|G无稳定额外gain；moment100.496→124.568；七实际host run均invalid|SCIENTIFIC_SIMULATION；原native residual实际执行；host NOT_QUALIFIED|side/b_native_learning_matrix_v1/FINAL_REPORT.md:19,21,29,33,41,49|
|120D original linear vs128×128 MLP|dev regret0 vs.851245；RMSE8.523668 vs11.219440|253train/73dev行；5dev state组含2zero-spread；只有3informative|没有独立test gate；rows非独立轨迹；linear无state×plan|原选模CONFIRMED于源码；不是online personalization|side/b_native_learning_matrix_v1/code/train_native.py:31,40,45,67；side/m2_neural_q_motion_v1/HISTORICAL_MLP_RECOVERY.md:9,11|
|Frozen M2 host attribution|四对全部force降，合并6.828%，RETURN85.578%，mean-force99.962%|两prefix×两seed四pair；8完整物理run；9dispatch含1零物理失败；19Q非零计划、107891steps|moment+13.28–25.64%；kneeRMS+.341–.424°；clearance3/4下降；原R2/strict55全FAIL，formal runtime NOT_RUN|实际causal host研究成立，非formal LEVEL3/部署|side/m2_host_generalization_attribution_v1/REPORT.md:5,11,15,19,43,69|
|Frozen linear排序机制|固定mask/池/历史公共项相消；131decision固定池一种排序、top变化0|OUT58、RETURN73；真实mixed precision probe|state-conditioned learned preference FAIL；mask/carry/feasibility不等于学会state×plan|CONFIRMED于source及紧凑Q_RANKING_ATTRIBUTION记录|side/m2_host_generalization_attribution_v1/REPORT.md:43；code/native_core.py:6–12；code/train_native.py:40–42|
|32×32 Neural Q challenger|test regret9.9306 vslinear1.6207 vsoldMLP16.6014；新pairacc.90625 vs.953125|80合法branch：47/16/17行，8/3/2snapshot、2/1/1来源；test17candidate、64pair仅2state|有交互但未带决策优势；synthetic probe不是physics gain；future-motion oracle gate不可部署|EXPLORATORY_TRAINED / OFFLINE_ADVANTAGE_NOT_DEMONSTRATED / HOST_NOT_READY|side/m2_neural_q_motion_v1/REPORT.md:7；DATASET_AUDIT.md:5–23；NEURAL_Q_EVALUATION.md:13–39|
|Counterfactual restoration audit|ordinary74候选/13state fixed regret均0；含6旧G-head full80均值.249333N·s|13snapshot、12round4 context、4来源、1model_hash/beta；snapshot文件15非durable|新增branch0/30，STOPPED_AT_RESTORATION_GATE；full motion80→13只zero；V_commit与V_replan不自动等价，host差NOT_EVALUABLE|只读历史dense审计；没有新physics/训练|side/m2_motion_counterfactual_ranking_v1/REPORT.md:19–31,35–41,46–58|
|Matched bidirectional O/R/OR|同父降.1197/.3305/.4502%，均motion PASS但均低于.5%门|16/18attempt、12完整导出；一个已知setup，exact重复不增Human n|发现NEGATIVE_RESULT，heldout NOT_RUN；旧RETURN-only OUT差为前干预混杂|live-state SCI完整fork PASS；HOST_CLOCK_CAUSAL_QUALIFICATION NOT_EVALUABLE|side/m2_matched_bidirectional_exploration_v1/REPORT.md:3–23,29–50|
|Matched Frozen M2参考|同该matched B降8.7997%，knee p95速度/加速度/jerk比1.693/2.271/1.148|同完整native OUT父入口，8非零计划、43640steps|velocity、acceleration、jerk、excursion、moment、tracking失败|物理研究参考有效；motion FAIL非临床判定|同上REPORT:19,43–46,62|
|Comprehensive best C4_1_5|降.738762%，RETURN少10.627926 N·s；H1/H2 .746213/.737962%PASS|151/160attempt，147完整任务；128search比较，29motion接受、4发现合格；534非零计划|C2降15.090469%但motionFAIL；phase shape差7.565056°；C1_020任务失败保留|SCI_VALIDATED；实际B residual positive-step执行；非host|side/m2_comprehensive_coordination_search_v1/REPORT.md:3–21,35–41,65–84|
|Lowforce native18|降1.165570%（16.768044 N·s），只RETURN；V平均1.167181%/最差1.150820%，3/3PASS|268/300attempt，262完整，215search/comparison，198不同actual非零序列|首次RETURN state差仅~3.94e-9rad；3/3不是不同RETURN states；.496750°excursion贴近.5°；整体广域31.17%<40%|同Human有限合法prefix科学验证；原native residual执行；无host/clinical|side/m2_lowforce_repair_explore_10h_v1/REPORT.md:5–21,43–73,84；RETURN_STATE_VALIDATION_SCOPE.json|
|Strong lowforce定向repair|C2代表15.0905→13.8195%，保91.58%；M2去R0保83.91%|局部同父干预与repair lineage，完整失败保留|仍motionFAIL，不能叫teacher；速度超B110%持续M2约2.342s/C2 2.566s，不是孤立peak|A层原物理任务与B层运动条件分开；非global无解证据|同上REPORT:9–19|
|Sequential O0_+.006|1419.188352，降1.350269%；3实际调整；后续合法forkbest1.306938%|79/90attempt、77完整归档；validation保留18不可搜索|V1best motionFAIL；V2仅B0/native18，best未跑；RETURN状态接近零差|SCI_DISCOVERY_ONLY；参数不按validation重选；非两条件best验证|side/m2_sequential_teacher_oracle_v1/REPORT.md:3–27,31–63|
|Free10D / best扩展|1403.259730 vs1438.613498降2.457489%，OUT/HOLD/R少17.273197/.000006/18.080565|84/96attempt；64positive-step自由候选、10合格；zero76121native人体samples复现|≥5%未达；motion贴边；phase-shape差14.238075°；优化未证明收敛|LEVEL1主声明；非原B LEVEL2，LEVEL3/hardware NOT_RUN|side/m2_free_trajectory_feasibility_v1/REPORT.md:3–35,55–100；PHYSICAL_ACTION_SPACE.md|
|Free冻结W1/W2|W1 2.424287%FAIL(excursion)，W2 2.379705%PASS，资格1/2|两个合法prefix、同Human；pair初始完整state匹配；RETURN1真实q差.0143721rad|R0被prefix消费，只能后续suffix验证；不能称整串或跨Human；无validation后调参|SUPPORTED有限LEVEL1条件；紧凑JSON复核|同上REPORT:66–75；PHYSICAL_FEASIBILITY_VALIDATION.json|
|Free最低力/消融|最低15.549494%FAIL；no_velocity1.692630%FAIL；no_common2.538821%FAIL|冻结完整前向任务；消融无重选|更低J_F不能替代motion/safety/任务；没有合格≥5%|保留negative；不能升级高质量teacher|同上REPORT:29–35,93–100|

必须保留的两种差异：历史matched Frozen_M2=1312.019870/8.7997%，后续comprehensive和sequential固定参考=1327.605231/7.716337%。虽匹配B数值相同，也不可把这两个冻结M2原执行合同/issued历史直接当同一方案。后续包明确做fixed-vs-rolling gate并记录共享prefix/count变化，应该按各自原合同引用。

结论级别：已证明有限条件中有实际force收益、有运动负担冲突、有精确科学fork、开发2.457489%可行自由参考；没有证明少repetition personalization、跨Human泛化、临床舒适、数学全局最优或正式部署资格。


## 今晚新增结果

本轮冻结、合法条件验证与独立核验已完成。最终数字列在下节、REPORT.md和EXPLORATION_RESULTS.json；数据版本以这些文件的generation/status字段为准。


<!-- OVERNIGHT_FINAL_START -->
## 本轮夜间探索的最终补充（2026-10-14）

本轮未训练学习器。保留原机器人、被动Human、接触和执行约束，在隔离研究中将原10维意图扩为18维：两方向的共同进度倾斜/曲率、差分进度曲率、髋膝速度倾斜。参数仍经原quintic与原筛选/准入，再由六轴robot实际执行。

同完整开发父状态，冻结最好`development_repair2_quality_NATIVE_SCALAR_18_063`下降2.635613%，全部冻结motion规则PASS；相对旧2.457489%增加0.178124个百分点。这是一项有限开发改进，不是全局最优。16个±0.4新轴probe和后续三个区域的有限COBYLA结果保留；joint optimum不能把增益简单分摊为某一自由度的贡献，详见MECHANISM_ANALYSIS.json。

冻结primary在四个预注册合法prefix条件中合格0/4、完整任务4/4。四条件都来自同一已暴露Human；仅未消费suffix被测试，共享prefix不属于未见完整原策略。失败保留且不从分母移除，secondary事先冻结而没有用测试改选primary。VALIDATION_RESULTS.json记录完整candidate身份、冻结文件hash和先后时间、配对初态及干预前物理/控制相等。

最低force代表下降16.816751%，motion FAIL，失败项['velocity_deg_s/max_abs', 'velocity_deg_s/p95_abs', 'velocity_deg_s/rms', 'acceleration_deg_s2/p95_abs', 'acceleration_deg_s2/rms', 'jerk_deg_s3/rms', 'RETURN_duration', 'excursion', 'cumulative_dose', 'task_duration', 'moment_integral_Nm_s', 'tracking']。它保留为负结果，不能称优质teacher。实际START/END=148/148，包含两次包装失败和真实commissioning，不把数学拒绝当physics。全部科学结论最多LEVEL1，未新增原B接口、host、硬件或临床资格。

与教授的关键问题仍是：允许多少中间姿态变化、怎样评价平顺与治疗剂量、何时迁移最小参考接口，以及何时才具备few-repetition学习值得使用的state/action/label证据。

<!-- OVERNIGHT_FINAL_END -->
