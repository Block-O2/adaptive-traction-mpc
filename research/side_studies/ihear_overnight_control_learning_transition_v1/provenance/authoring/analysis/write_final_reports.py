"""Chinese reports grounded in completed, independently recomputed evidence."""
from pathlib import Path
import json,time,datetime,collections
from repetition_paths import rep_path
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def doc(n,s):(P/n).write_text(s.strip()+'\n')
def append_final(n,section):
    title=section.strip().splitlines()[0];base=(P/n).read_text().split('\n'+title,1)[0]
    doc(n,base.rstrip()+'\n\n'+section.strip())
def flag(x):return 'PASS' if x else 'NOT_DEMONSTRATED'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def fmt(x,n=6):return '不适用' if x is None else f'{x:.{n}f}'
ex=read('EXPERIMENT_RESULTS.json');lr=read('LEARNING_RESULTS_FINAL.json');rep=read('derived/REPETITION_EVALUATION.json');acc=read('ATTEMPT_ACCOUNTING.json');fv=read('models/VALUE_FREEZE.json');qd=read('derived/QUALIFICATION_LEARNING_DIAGNOSTICS.json');pv=read('PREDICTION_VALIDATION.json');ds=read('derived/DATASET_all.json')
early=read('EARLY_VALUE_EVALUATION.json');ef=read('models/EARLY_VALUE_FREEZE.json')
capacity=read('derived/MODEL_CAPACITY_DIAGNOSTIC.json')
h=[r for r in ex['rows'] if r['action']=='H150' and r['parent'] not in ['REP','REPR']];test=[r for r in lr['rows'] if r['split']=='test'];train=[r for r in lr['rows'] if r['split']=='train'];valid=[r for r in lr['rows'] if r['split']=='validation']
h.sort(key=lambda r:ds['groups'].index(r['parent']))
h_table=table(['状态','split','J_F / N·s','对B降力%','膝下冲°','膝excursion−B°','门余量°','完整资格'],[[r['parent'],r['split'],fmt(r['J_F_N_s']),fmt(r['gain_vs_B_percent'],4),fmt(r['knee_undershoot_deg']),fmt(r['excursion_delta_B_deg'][1]),fmt(r['excursion_gate_margin_deg']), 'PASS' if r['qualified'] else 'FAIL: '+','.join(r['failed'])] for r in h])
q_table=table(['测试状态','实际Q选择','完整资格','对合格H150收益 / N·s','合格最优','regret / N·s','直接Q最优'],[[r['parent'],r['selected'],'PASS' if r['selection_qualified'] else 'FAIL',fmt(r['improvement_vs_H150_N_s']),r['best_qualified'],fmt(r['regret_N_s']),r['direct_argmin']] for r in test])
cost_table=table(['状态','moment相对B%','hip tracking RMS°','knee tracking RMS°','force峰值 N','moment峰值 Nm'],[[r['parent'],fmt(r['moment_cost_delta_B_percent'],3),fmt(r['tracking_RMS_deg'][0],4),fmt(r['tracking_RMS_deg'][1],4),fmt(r['force_peak_N'],3),fmt(r['moment_peak_Nm'],3)] for r in h])
qualification_table=table(['验收标志','结果','精确范围'],[['CONTROL_BASELINE_PASS',f'{sum(r["qualified"] for r in h)}/{len(h)} H150条件通过','仅逐行指定同一Human/prefix'],['LEARNING_DATA_READY','PASS',f'{len(ds["groups"])}父状态，{len(ds["records"])}动作行'],['Q_TRAINED','PASS',f'{len(train)}训练父状态；{len(valid)}验证父状态；终端成本回归'],['Q_GENERALIZATION_PASS',flag(lr['Q_GENERALIZATION_PASS']),'见冻结规则及实际U策略分支'],['FEW_REPETITION_LEARNING_PASS',flag(rep['FEW_REPETITION_LEARNING_PASS']),'见实际持续plant重复报告'],['RL_BASELINE_TRAINED','NOT_RUN','0 P2 episode / 0更新'],['RL_BASELINE_QUALIFIED','NOT_RUN','无RL checkpoint资格']])
doc('FROZEN_CONTROL_BASELINE.md',f'''
# H150冻结研究基线

H150仍可用于指定条件下的PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION研究对照。它不是所有状态的实际Human motion保证。全部参数、18D来源、T/ER/RETURN5 hip timing与原5ms量化保持冻结；动作定义见ACTION_SET.json、FROZEN_18D.json、FROZEN_SELECTION.json及执行manifest v2/v3/v4及序列化修复v5/v6。

W1/W2在本轮均为已暴露开发条件，不能再次称未见验证。D01R的B/H150与历史Ctrl全trace、native状态和科学receipt复现见audit/H150_REPRODUCTION.json；D02与历史W2相同范围的逐raw复现见audit/W2_FULL_RAW_REPRODUCTION.json。其余prefix、seed、split在任何相应物理结果之前登记于*_PLAN.json。一个Human模型不等于多个独立受试者。

{h_table}

RETURN膝下冲定义为max(0,9.5°−RETURN真实最小膝角)：9.5°是实际最终发出参考，不是名义10°。excursion为完整任务真实max−min；原门为两个关节相对matched B的绝对差均≤0.5°。门余量为0.5−max(abs(两关节excursion差))。负余量就是FAIL，即使只差几千分之一度；没有调宽门或追着W1阈值调参。

D03的H150膝下冲1.200755°与W1的1.201029°几乎相同，失败不能简单解释为下冲突然更严重。D03 matched B自身膝excursion为111.269980°，H150为111.773972°，差0.503992°；ZERO只把下冲缩小约0.004265°，留下约0.000273°的门余量。它在该确定性条件下PASS，但余量极窄，不代表稳健修复。完整候选与B极值分解见derived/EXCURSION_EXTREMA_DIAGNOSTIC.json。

{cost_table}

低force不是全面更优。moment、tracking、真实过冲与native平顺性仍须单独评估。完整字段（velocity max/p95/RMS、acceleration max/p95/RMS、jerk p95/RMS、TV、acceleration variation、dose、phase）见EXPERIMENT_RESULTS.json。原门见MOTION_ACCEPTANCE_PROTOCOL.json：motion burden 1.1、travel±5%、endpoint/phase boundary 0.5°、duration 0.1s、moment integral 1.25、force/moment peak 1.05及tracking+B0.5°均未改变。

![终末运动与力](figures/07_terminal_response.png)

![资格与成本分开评价](figures/08_qualification_cost.png)

保留原B planner、证书、current-state admission、机器人反馈/allocator和被动Human物理。不重开PD/FF/阻尼增益网格。下一步需要研究资格余量的状态依赖和终末传力响应；无需先把所有过冲消到零才允许Learning。
''')
pred_rows=[r for r in pv['rows'] if r['id'].endswith('H150') and r['region']=='terminal' and r['horizon_s']==.1 and r['method'] in ['causal_constant_acceleration','ridge_residual']]
pred_table=table(['父状态','用途','方法','100ms膝RMSE°','膝p95绝对误差°'],[[r['parent'],r['split'],r['method'],fmt(r['rmse'][1]),fmt(r['p95_abs'][1])] for r in pred_rows])
model=read('derived/COUPLED_MODEL_PREDICTION.json');mrows=[r for r in model['rows'] if r['horizon_s']==.1 and r['id'].endswith('H150')]
model_table=table(['轨迹','原2DOF模型输入','100ms髋RMSE°','100ms膝RMSE°'],[[r['id'],r['method'],fmt(r['rmse'][0]),fmt(r['rmse'][1])] for r in mrows])
extrema=read('derived/EXCURSION_EXTREMA_DIAGNOSTIC.json')['rows']
d3=next(r for r in extrema if r['parent']=='D03')['arms']
d3_separation=abs(d3['H150']['min_deg'][1]-d3['ZERO']['min_deg'][1])
d3_rmse=next(r['rmse'][1] for r in pred_rows if r['parent']=='D03' and r['method']=='ridge_residual')
doc('COUPLED_RESPONSE_IDENTIFICATION.md',f'''
# 机器人—cuff—Human闭环响应证据

原waypoint执行层Human请求为Kp(q_ref−q_est)+Kd(dq_ref−dq_est)，Kp=[180,140]、Kd=[28,22]。来源为source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_shadow.py的desired_acceleration，与stage3 human.py冻结系数一致。本接口的该请求未加入reference ddq；不能将它与另一套computed-torque实现混为一谈。图03用日志中实际reference与估计状态重构请求，native实际加速度只做离线比较。

request是进入Human逆动力学/allocator的期望量，真实Human加速度来自机器人执行、cuff wrench、被动动力学和反馈的闭环总结果。PREDICTION_VALIDATION.json的acceleration_alignment与图03显示二者幅值/形状不同；这支持“请求不是直接人体加速度”的结论，不能据此唯一归因于某个增益或延迟。

{model_table}

上述模型在每个origin冻结当时的beta、residual weights、估计状态以及输入；分别保持当时已测wrench或已发广义action，向前积分原2DOF模型100/200ms。它没有预测未来机器人反馈和传力，不是完整robot–cuff–Human闭环模型。测试时未来truth仅作为评价标签，MuJoCo没有新增步进。

{pred_table}

残差ridge固定alpha=10，只在W1的B/ER/H150轨迹训练；W2是历史轨迹验证，D03–D06是后续新prefix验证。100/200ms滚动origin使用当时估计、tracking、因果加速度、已测wrench和广义request；未来truth只在训练目标/评价端使用。初版权重与结果先保存在audit/prediction_initial，后续不按新状态调参。相邻origin高度相关，不能把数百窗口当成独立Human样本。

同父HIP−ZERO、H150−KNEE等干预的首个reference、robot torque、cuff和Human变化时间见derived/COUPLED_FACTORIAL_CONTRASTS.json。干预前轨迹相同；后续原replanning可能同时改变另一个关节参考。因此这是改变髋/膝协调参考的闭环总效应，不是隔离出的纯机械耦合系数，也不能用5ms首次差异推断唯一物理延迟。

短时角度预测误差与狭窄excursion门余量/候选运动差异处于不可忽略的尺度；模型还缺少候选动作输入和完整任务force目标，不能用角度RMSE直接论证N·s收益排序可靠。没有将预测器升级为自动控制器。进一步的动作选择必须由实际同父完整物理结果验证。

例如D03的H150与ZERO真实膝最小角只相差{fmt(d3_separation)}°，该轨迹100ms ridge预测的膝RMSE为{fmt(d3_rmse)}°，约为前者{fmt(d3_rmse/d3_separation,2)}倍。这是不同量的尺度对照，不是候选差值误差界或置信区间；它不足以认证如此小的运动差异，也不能代替动作条件反事实预测验证。

![请求与响应](figures/03_request_response.png)

![短时预测验证](figures/02_prediction_validation.png)
''')
doc('Q_VALUE_EXPERIMENTS.md',f'''
# 状态—动作价值实验

本轮已实际训练和执行有限动作contextual terminal Monte Carlo cost/value模型。它不是18D优化换名，不是多步Bellman Q-learning。每个动作有独立状态斜率，具有显式state×action项；能表达交互与实际学到有用交互是两件事。

实际数据：{len(train)}训练父状态×4动作，{len(valid)}验证父状态×4动作，{len(test)}测试父状态×4动作；另有{len(test)}个真实Q在线分支。训练父状态={fv['training_parents']}，验证={fv['validation_parents']}。同父所有动作保持同一split。选中ridge alpha={fv['selected_alpha']}。按标准化、重新中心化及1e-9绝对容差计算，训练状态rank={capacity['late_rank']['rank_at_absolute_standardized_tolerance_1e_9']}，七个特征不代表七个独立激励方向。权重SHA256：`{fv['model_sha256']}`。

成本目标为完整J_F相对同状态H150之差；另一个多输出头学习原资格余量。失败轨迹的完整成本只作诊断回归，不被当成合格reward。选择时先看开发leave-one-parent-out最大残差缓冲与状态支持范围；开发D03后、模型训练和全部U测试前，登记了资格恢复优先规则。原模型/数据/选择规则在U首次START前冻结；不会读未来matched B或Human truth。

这些误差缓冲只是少量开发父状态的经验最大误差，没有统计覆盖率或安全证明。七维特征也未被证明是Markov状态：没有完整机器人q/dq、全部自适应模型参数或长时tracking历史。失败结果同时受状态表示、数据覆盖、动作集合和预测不确定性限制，不能泛化成“价值学习在此类系统无效”。

完整任务成本中，选择之前的共同prefix成本在同父动作差值中抵消。该差值可用于当前有限候选排序；绝对完整任务回归不能因此直接解释成标准MDP的剩余cost-to-go。

{q_table}

测试delta成本RMSE={fmt(lr['metrics']['test']['delta_J_RMSE_N_s'])} N·s；纯force pairwise ranking准确率={fmt(lr['metrics']['test']['pairwise_force_ranking_accuracy'],4)}。这些诊断包含不合格动作的完整force标签，不能据此认定实际收益。预测与真实结果见图04。Q_GENERALIZATION_PASS={flag(lr['Q_GENERALIZATION_PASS'])}；保守选择非恒定={lr['nonconstant_selection_gate']}；直接Q排序表现见逐行结果。资格恢复的U父状态={qd['qualified_recovery_test_parents']}，对合格H150取得>0.01 N·s收益的U父状态={qd['qualified_force_gain_test_parents']}。

与全局固定动作对照：训练选择的动作={fv['global_action']}，是否对全部训练状态合格见models/GLOBAL_FIXED_BASELINE.json。还提供“最近训练父状态中合格最低成本动作”的简单条件规则诊断，见derived/QUALIFICATION_LEARNING_DIAGNOSTICS.json；此项在已登记固定动作结果上离线评价，没有额外执行在线规则分支，不能宣称是独立新实验。

实际U策略决策记录必须与冻结模型重新推断完全一致，完整J_F与它选中的同父固定动作分支一致。低regret若只是始终选择全局最优固定H150，不证明状态条件策略学习成功。资格mask导致的变化也不等于纯force Q排序学到反转。没有因为模型系数非零就宣称成功，没有训练Neural Q。

![Q预测与真实完整成本](figures/04_Q_prediction_actual.png)
''')
early_table=table(['测试状态','实际QE选择','完整资格','对B收益 N·s','恢复H150失败','regret N·s'],[[r['parent'],r['selected'],'PASS' if r['qualified'] else 'FAIL',fmt(r['gain_vs_B_N_s']),r['qualified_recovery_vs_H150'],fmt(r['regret_N_s'])] for r in early['rows']])
doc('EARLY_VALUE_STUDY.md',f'''
# 补充对照：更早选择完整后续方案

V01暴露了RETURN2动作集合的结构限制：共享此前H150执行历史后，仅修改两个中间姿态未必还有可行候选。为此在任何U结果出现之前登记EARLY_VALUE_PROTOCOL.json，增加三个实际QE分支，把决策放在共同OUTBOUND prefix完成、H150首次特有干预之前。该时点可以公平选择B/H150/HIP/KNEE/ZERO的完整剩余方案。原RETURN2主实验继续保留。

输入来自决策时严格此前的最后一个完整TASK测量样本（age≤10ms）：估计tracking q/dq、测得force/moment、OUTBOUND elapsed，以及当时已经处方给定的三个RETURN-prefix系数。后者是已知参考配置，不是未来实现的Human状态或未来成本。开发数据从每个动作的共同原始prefix重构，五个动作的十维向量逐位相同；实时QE输入又与同规则的raw重构核对。无Human truth进入选择器。

与主模型相同的6个D父状态训练、2个V父状态选alpha，原数据复用不增加独立样本数。模型有每动作状态斜率和资格余量头；alpha={ef['selected_alpha']}，标准化中心化状态rank={capacity['early_rank']['rank_at_absolute_standardized_tolerance_1e_9']}。冻结元数据中的默认浮点rank={ef['state_rank']}受均值舍入影响；六个中心化样本最多有五个独立方向，解释修正及奇异值见derived/MODEL_CAPACITY_DIAGNOSTIC.json，权重未改。权重在全部U测试之前冻结，SHA256=`{ef['model_sha256']}`。无法确认合格力收益时保留B后续方案，仍走原安全执行链。

{early_table}

EARLY_POLICY_ALL_TESTS_QUALIFIED={early['EARLY_POLICY_ALL_TESTS_QUALIFIED']}；EARLY_CONDITIONAL_BENEFIT_PASS={flag(early['EARLY_CONDITIONAL_BENEFIT_PASS'])}。实际选择非恒定={early['selection_is_state_conditioned']}，纯force排序非恒定={early['force_ranking_is_state_conditioned']}。不能把始终回退B当学习成功，也不能把资格头导致的切换当作纯force Q排序反转。

开发阶段八个状态全部选择B={capacity['early_development_all_B']}，四个替代动作在这八个状态均未通过经验余量缓冲={capacity['early_no_alternative_eligible_on_development']}。这已经显示全局最大LOO误差缓冲在小数据下过于保守；即使实际通过的开发轨迹也被屏蔽。它是可执行回退接口及保守性代价的对照，不能包装成有效条件学习。未在消费U结果后缩小缓冲以制造非恒定选择。

预注册晋级要求：三次完整资格均通过，选择非恒定，至少一次恢复H150失败、至少一次对B合格降力，而且平均成本低于在三个U上都合格的最佳固定动作。该固定对照为{early['best_all_test_qualified_fixed_action']}，均值{fmt(early['best_all_test_qualified_fixed_mean_J_F_N_s'])} N·s；QE均值{fmt(early['mean_policy_J_F_N_s'])} N·s。这个测试集最优固定对照仅用于事后评估，不进入在线选择或训练。

它是一次任务内更早的资格条件value选择，没有使用前一次运动反馈，也不是多步Bellman Q-learning。主Q_GENERALIZATION_PASS和FEW_REPETITION_LEARNING_PASS保持各自定义；补充结果不能代替这两个验收标志。机器结果见EARLY_VALUE_EVALUATION.json。
''')
if rep['status']=='TWO_ACTUAL_REPETITIONS_COMPLETED':
    reptext=f"真实连续plant完成第一次H150、原settle/hold边界、第二次任务的同父B/H150/MEMORY分支。第一次测得force积分用于一次有界value记忆更新，online kernel weight={fmt(rep['memory']['online_kernel_weight_N_s'])} N·s；第二次选择={rep['decision']['selected']}，实际动作改变={rep['action_changed']}，相对合格固定H150收益={fmt(rep['qualified_improvement_vs_H150_N_s'])} N·s。"
else:reptext=f"持续重复pilot未完整完成，状态={rep['status']}。实际反馈更新={rep['actual_feedback_update']}，实际第二次策略决策={rep['actual_second_policy_run']}。失败原文：{rep.get('failure',{}).get('error','详见pipeline日志')}。失败后未放宽门或重置Human使其通过。"
if rep.get('run_prefix')=='REPR':reptext+=' 首次REP在第二次调用的序列化所有权检查中失败，未推进第二次physics；另保留一次零物理启动日志命名失败。随后以新代码身份修复并完整重跑，原失败、权重与门槛均保留。详见REPETITION_SERIALIZER_REPAIR.md。'
doc('FEW_REPETITION_EVALUATION.md',f'''
# 真实跨重复反馈pilot

{reptext}

FEW_REPETITION_LEARNING_PASS={flag(rep['FEW_REPETITION_LEARNING_PASS'])}。更新一个数值记忆并不等于有用个体化；若保持H150或没有后续完整合格收益，就不能称少重复学习成功。

采用已暴露W2 prefix作接口pilot，不能称未见测试或跨Human验证。第一次完成任务的测得force积分和当时合法状态用于下一次value修正；native truth与未来matched B仅用于离线审计。原plant、measurement layer、RNG和updater连续保留，原物理时钟不清零；没有设置或回放Human qpos/qvel。第二次动作仍通过原planner/certificate/current-state admission和机器人执行链。记忆在第二次START前冻结，主Q权重不变。

first raw reproduction、continuity、boundary native observation及反馈权重SHA分别保存在{rep_path('audit/REPETITION_FIRST_REPRODUCTION.json')}、{rep_path('output/REPETITION_CONTINUITY_BEFORE_SECOND.json')}、{rep_path('output/REP_BOUNDARY_NATIVE.json')}、{rep_path('models/REPETITION_MEMORY_FREEZE.json')}（未到达的阶段不虚构文件）。边界与新epoch bootstrap的native成本都单独或在parent增量内记账。完整状态与错误见derived/REPETITION_EVALUATION.json。

该pilot采用很保守的更新：反馈修正被absolute-value LOO误差限制，力优势门又包含该误差。因此，当其他动作原先预测成本更高时，一次反馈不能凭空制造有置信度的降力切换。它首先验证实际反馈/连续执行接口；不能用未切换的结果证明所有少重复学习都无效。下一轮需要在重复数据支持下更新不确定性，而不是强迫动作变化。

第一与第二次起始物理状态不同，因此跨次J_F数值的直接变化不能作为学习因果收益。唯一公平收益来自第二次相同live parent的MEMORY与固定H150比较；父进程等待串行fork并保持状态不变。

该pilot用一个已执行H150的完整任务成本修正其绝对价值，不能识别其他动作的反事实回报。残差也可能包含决策前共同prefix的成本变化，不能全部归因于后续协调动作。下一轮应记录已发生的prefix成本，区分剩余cost-to-go与完整任务总成本，并用重复数据估计动作差值及其不确定性；本轮没有把这项记忆更新解释为已识别个体动力学。
'''+ ('\n![实际重复表现](figures/06_actual_repetition.png)\n' if (P/'figures/06_actual_repetition.png').exists() else ''))
doc('REPETITION_SERIALIZER_REPAIR.md',f'''
# 连续重复的序列化修复与失败保留

初次REP_FIRST完整完成并复现D02_H150；实际测得force用于一次有界价值更新。原连续边界推进20个native步并通过。在第二次调用中，外层invoke错误地恢复了安装streaming serializer之前的persist_runtime_artifacts；原streaming_reuse.ensure因此触发STREAM_SERIALIZER_OWNER_CHANGED，第二次物理尚未推进。

audit/PARTIAL_COST_RECONCILIATION.json用第二次initial与失败时的同一plant时钟均为29.085000000047863 s，独立核实REP_parent新增native步数为0。该失败START仍计入总数，ATTEMPTS.jsonl原事件未改写。

v5把外层finally改为原streaming_reuse.restore(rt)，恢复已安装的合法序列化器。无物理probe先重现旧错误，再验证连续两次修复调用通过。原code/study_common.py、原plant、控制器、资格门、模型及权重均未修改。v5 owner随后因独占打开旧日志名而在worker创建前失败，保留为REPR_owner_log_failure，计1 START、0 native步；精确墙钟耗时未测量，事件时间明确为事后登记时间。

v6仅修正独立日志名，并以REPR_FIRST、REPR_boundary、REPR_parent及B/H150/MEMORY新身份完整重跑。v4/v5源文件、manifest、错误、第一次raw和初步结案结果均保留；初步报告快照见audit/v4_closeout。最终执行和保护审计在重跑之后重新进行，不将中途快照冒充最终结案。

实际重跑结论：{rep['status']}；FEW_REPETITION_LEARNING_PASS={flag(rep['FEW_REPETITION_LEARNING_PASS'])}。完整错误/修复证据见audit/REPETITION_FAILURE.json、audit/OWNER_LAUNCH_FAILURE_v5.json、audit/SERIALIZER_REPAIR_PREPHYSICAL.json及EXECUTION_CODE_MANIFEST_v4/v5/v6.json。研究没有因该代码修复改变动作选择规则或未见测试条件。
''')
append_final('LEARNING_DATASET_AUDIT.md',f'\n## 最终实际规模\n\n{len(ds["groups"])}父状态、{len(ds["records"])}动作行，其中{sum(r["full_task_outcome"]["qualified"] for r in ds["records"])}行完整合格；其余保留失败标签。train/validation/test分别{len(train)}/{len(valid)}/{len(test)}父状态。Q测试分支另计{len(test)}条，真实重复pilot单列，不混入冷状态训练集。完整START={acc["P1_START"]}，父进程/fork/失败/边界都计入；详见ATTEMPT_ACCOUNTING.json。没有不同Human数据。\n')
append_final('RL_BASELINE_STUDY.md','\n## 本轮最终决定\n\nNOT_RUN。P2 episode=0、native steps=0、policy/critic update=0、无训练checkpoint、无训练曲线。V01/V02中本合同的四个RETURN2动作全部不合格，重新探索同一确定性集合不能生成不存在的合格动作；需要先处理动作时点和可行集合。主要实验显示动作资格边界与状态辨识是首先需要解决的问题；在单Human、少独立父状态及24集探索预算下运行PPO不足以提供可信strong baseline。这是研究价值判断，并非已经耗尽10小时。用户允许提前停止低信息量方向及交付最小合同，因此将资源用于L1完整对照、真实反馈pilot及数值/保护审计。此结论只针对本轮有限动作合同，不否定其他合法动作空间中的PPO/SAC；本轮也不能与RL进行经验性能排名。\n')
doc('NEXT_RESEARCH_DECISION.md','''
# 下一轮研究决策

优先研究“基于可观测状态与上次实际反馈的资格余量估计及保守候选选择”。需要动作在部分状态中有可复核的合格性或收益差异，才有必要学习状态条件策略。不要用更深网络掩盖低独立状态数或全局固定动作优势。

先增加真实、预注册的prefix覆盖，重点采集边界附近且具有可执行替代动作的状态；保持parent/family split，保留拒绝、失败及原门。增加上一完整运动的测得force/moment/tracking统计及可靠性信息，再在真实连续plant上检验是否改善下一次。跨Human应单独注册参数族、开发Human与完全保留Human，不能把当前单Human结果外推。

当前没有证据要求回到无目标PD/FF/阻尼扫描，也不允许直接修改正式B。若持续重复接口或动作集合缺乏可靠可行候选，应先在独立版本修复/扩充该接口并重新资格，而不是让学习器隐藏失败。控制层仍负责安全执行，统计value只是提议层。

最有希望的研究贡献是：带资格不确定性的有限动作value学习，使用真实上一重复反馈，原安全控制链执行，以同父完整物理验证条件性资格恢复和成本收益。贡献成立需要超越全局固定动作与简单条件规则，并通过独立prefix和独立Human验证；本轮结论不预设该路线已成功。纯RL继续作为同约束、明确物理成本的辅助对照。
''')
answers=[
('H150是否仍合理？',f'是，作为指定条件的冻结研究基线。本轮{sum(r["qualified"] for r in h)}/{len(h)}个cold条件H150完整通过；逐状态资格见下表，不宣称普适回退。'),
('新状态是否资格退化？','有。D03的H150/HIP/KNEE excursion失败而ZERO通过；所有后续失败按原门保留，低force不覆盖FAIL。'),
('请求与预测差异主要证据？','原PD请求、测得cuff映射和native真实加速度不同；100/200ms原模型及因果残差预测误差已量化。模型没有完整机器人闭环和候选动作输入，不能直接预测完整停止结果。'),
('哪些控制问题继续，哪些暂放？','继续关注真实终末响应、资格余量和持续重复执行；暂放没有新假设的增益网格和“全部过冲先归零”的要求。'),
('是否真正开始Learning？',f'是。实际{len(train)}训练父状态的完整物理数据训练了显式交互value与资格余量模型，并在{len(test)}个未消费测试状态实时选择并执行。'),
('合法状态与动作是什么？','主模型使用七维在线tracking q/dq、测得force/moment、phase elapsed，选四个有界RETURN2/3姿态动作。补充QE在共同OUTBOUND prefix后选择B或四个完整剩余方案，另纳入三个已知处方RETURN-prefix系数。未来truth/B结果只作离线标签。'),
('是否学到状态相关偏好？',f'直接Q测试动作={lr["metrics"]["test"]["direct_actions"]}，保守实际动作={lr["metrics"]["test"]["selected_actions"]}。Q_GENERALIZATION_PASS={flag(lr["Q_GENERALIZATION_PASS"])}。补充早期QE选择={[r["selected"] for r in early["rows"]]}，EARLY_CONDITIONAL_BENEFIT_PASS={flag(early["EARLY_CONDITIONAL_BENEFIT_PASS"])}；资格头切换与force排序分开解释。'),
('是否真实跨重复改进？',reptext+f' FEW_REPETITION_LEARNING_PASS={flag(rep["FEW_REPETITION_LEARNING_PASS"])}。'),
('相比H150有完整合格收益吗？',f'对合格H150取得>0.01 N·s收益的测试父状态={qd["qualified_force_gain_test_parents"]}；资格恢复状态={qd["qualified_recovery_test_parents"]}，二者分开解释。'),
('哪些失败/数据不足限制结论？','只有一个Human、少量独立prefix，窗口/动作数不能代替独立状态数；excursion门余量窄，经验误差缓冲不等于形式安全证明，候选存在状态资格失败，跨重复pilot仅是已暴露条件。'),
('是否启动纯RL？','NOT_RUN；交付同约束最小PPO baseline合同。'),
('RL是否同约束完成任务？','未执行，RL_BASELINE_TRAINED与RL_BASELINE_QUALIFIED都不能通过。'),
('性能与物理样本成本如何？',f'P1共{acc["P1_START"]} START，实际新增native steps={acc["actual_new_native_steps"]}，P2=0。固定与value完整结果同父可比；没有RL经验性能排名。'),
('下一轮最值得研究？','观测状态/上一运动反馈如何预测资格余量，并在有真实动作差异时选择比全局固定动作更好的方案。'),
('需要扩展状态/Human吗？','需要先扩展有科学目的的合法prefix；跨Human必须另建开发/保留Human划分，目前无此证据。'),
('需要回头改原控制器吗？','不因本轮负结果自动修改正式B；只有可定位的执行或可行集合缺陷才在新隔离版本修复并重新资格。'),
('最有希望贡献是什么？','传统控制提供可执行、安全筛选基础，资格不确定性value利用真实反馈提议协调动作，完整物理证明收益；必须实证超越固定和简单规则。')]
doc('REPORT.md',f'''
# iHEAR：控制巩固与Learning过渡 v1

本轮完成控制复现、新prefix完整配对、因果预测审查、实际value训练、冻结策略测试及真实连续重复反馈pilot。H150在部分条件保持约2.3%降力，但存在新状态motion退化。学习是否成功由以下分立标志决定，不能由“模型已训练”推导。

{qualification_table}

仅PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION。没有跨患者、硬件、临床、正式Native LEVEL2或host实时LEVEL3结论。SCI模式中的墙钟plan age不构成实时资格；完整原科学因果/receipt链另行检查。全部正式B与历史包只读，无自动Git提交/推送/合并。

## 十七项研究回答

'''+ '\n\n'.join(f'**{i}. {q}**\n\n{a}' for i,(q,a) in enumerate(answers,1))+f'''

## 关键完整结果

{h_table}

{q_table}

补充的早期方案选择对照（预注册，仅增加三个测试分支）：

{early_table}

完整状态、晋级条件与主实验区别见EARLY_VALUE_STUDY.md。

![完整运动、力与力矩](figures/01_control_motion_force.png)

![Learning与原执行链](figures/05_learning_structure.png)

## 审计与交付索引

原始积分和native运动由独立算术进程重新计算，非独立人员复核；历史19个完整任务也重新计算。所有新完整任务、receipt、command torque与native步归属见derived/*_INDEPENDENT.json和audit/RAW_*.json。保护审计、split/model identity、START/END闭合、进程停止及文件manifest见PACKAGE_VERIFICATION.json与ATTEMPT_ACCOUNTING.json。

控制细节见FROZEN_CONTROL_BASELINE.md；耦合预测见COUPLED_RESPONSE_IDENTIFICATION.md与PREDICTION_VALIDATION.json；数据/方法见LEARNING_PROBLEM_DEFINITION.md、LEARNING_DATASET_AUDIT.md、STATE_ACTION_REWARD_SCHEMA.json、Q_VALUE_EXPERIMENTS.md；跨重复见FEW_REPETITION_EVALUATION.md；RL见RL_BASELINE_STUDY.md；下一步见NEXT_RESEARCH_DECISION.md。LEARNING_RESULTS.json保留原冻结策略评价，LEARNING_RESULTS_FINAL.json补充真实重复结论，不改写原实验结果。

完整逐分支成本、平顺性、moment、tracking、剂量及FAIL在EXPERIMENT_RESULTS.json。随机种子/prefix和候选身份见*_PLAN.json/ACTION_SET.json；训练权重见models，实际命令/日志见*_OWNER.json及logs。最终Windows交付与WSL canonical文件哈希一致性单独记录于DELIVERY_VERIFICATION.json。

数值口径保持原合同：完整force/moment采用实际5ms trace时钟的左积分；加速度为0.25ms native真实速度的原二阶边界梯度，jerk为其再梯度，未用平滑压低峰值。独立复核覆盖全任务及各phase指标，不把局部曲线平顺等同整体motion资格。
''')
events=[json.loads(s) for s in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
zone=datetime.timezone(datetime.timedelta(hours=8))
timeline=[]
for e in events:
    timeline.append([datetime.datetime.fromtimestamp(e['unix'],zone).isoformat(timespec='seconds'),e['event'],e['id'],e.get('returncode',''),e.get('kind','')])
doc('OVERNIGHT_TIMELINE.md',f'''# 执行时间线

T0=2026-10-19 01:57:00+08:00；no physics/training after=10:57；hard stop=11:57。阶段重叠：历史审计与新物理串行采集期间已启动Learning合同、模型实现及预测分析，无需等待控制误差归零。

模型冻结时间={datetime.datetime.fromtimestamp(fv['frozen_unix'],zone).isoformat()}。全部U消费在此之后。根据明确结果可提前结束，不为了填满10小时补低信息量实验。最后停止与审计时间以PACKAGE_VERIFICATION.json为准。

{table(['上海时间','事件','ID','returncode','kind'],timeline)}

重复pilot的初次序列化错误及v5启动日志错误完整保留，第二次任务未推进的0 native成本由连续时钟证明；v5启动失败时间为事后登记时间，未伪造精确墙钟耗时。首次D01导入失败发生在物理之前，以0 native steps保留并保守计1 START；修复缺少legacy manifest别名后以D01R新身份重试。preflight第一版的路径/换行比较问题保存在audit/preflight_attempt1，未覆盖旧实验。D03后资格优先规则澄清登记在训练前，不涉及测试条件或原门修改。
''')
doc('REPRODUCE.md',f'''# 身份与复核

canonical目录：`{P}`。Python：`/home/hank/envs/adaptive-online-rl-v1/bin/python`；MuJoCo/NumPy版本见ENVIRONMENT及源manifest。所有本轮新源文件位于control/analysis/learning或provenance/authoring。

执行层由EXECUTION_CODE_MANIFEST_v2.json冻结，v3增加在线Q及预注册早期QE选择，v4增加真实持续重复及反馈选择，v5/v6仅修复序列化恢复和独立启动日志；原B/物理/准入实现未更改。START记录携带执行manifest与group plan SHA。训练身份见models/TRAINING_CODE_MANIFEST.json、VALUE_FREEZE.json及EARLY_VALUE_FREEZE.json。测试plan添加Q、QE分支，原条件、种子和五个固定动作不变。相应测试START必须晚于两个模型的权重冻结。

只读复核算法入口：control/independent_recompute.py（不导入runner/plant）；analysis/audit_raw.py逐组重算原始完整积分、native平顺性与receipt；learning/evaluate_value.py根据冻结权重和记录状态复核策略。它们的输出仅能写新研究目录，若复算已封包结果，应复制到新的独立审计目录并保存原SHA，避免修改本包最终manifest。

实际物理启动命令完整保存在*_OWNER.json的command与logs，环境STUDY_GROUP/STUDY_MODE由owner设置。主测试入口为control/owner_v3.py；成功的连续重复入口为control/repetition_owner_v6.py，调用repetition_runner_v6.py。v4保留为失败证据，v5未启动worker。

所有physics已STOP，不应删除STOP标志后在本目录重跑。需要新物理复现时，创建新版本目录，复制冻结代码、权重及科学配置，在新包登记路径、T0/硬截止、预算和唯一运行ID等管理信息，冻结新的manifest并明确列出这些差异。保留原seed/prefix/控制参数/任务门，使用新的空输出目录保存新运行，不覆盖或删除本包证据；通过同父raw比较后才评估新结论。禁止从raw设置/回放Human状态。

P1 START={acc['P1_START']}，P2=0。parent完整轨迹含commissioning/prefix，fork继承全live地址空间但只计新增native后缀，父进程等待children，不并行推进physics。边界及persistent bootstrap额外成本在ATTEMPT_ACCOUNTING.json解释。报告图来自raw/numeric结果，没有绘制虚构RL训练曲线。
''')
print('FINAL_CHINESE_REPORTS_WRITTEN',flush=True)
