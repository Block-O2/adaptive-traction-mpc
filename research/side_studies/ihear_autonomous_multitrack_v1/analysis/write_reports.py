from pathlib import Path
import json,time,hashlib,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def write(n,s):(P/n).write_text(s.strip()+'\n')
ex=read('EXPERIMENT_RESULTS.json');rows=ex['rows'];D={r['id']:r for r in rows};hist=read('derived/HISTORICAL_NATIVE_AUDIT.json')['records'];H={r['id']:r for r in hist};sel=read('NEW_FROZEN_SELECTION.json');val=read('VALIDATION_RESULTS.json')
assert ex['status']=='COMPLETE' and 'Bmap_ER' in D
er=D['Adev_ER'];b=D['Adev_B'];avs=[D['Adev_'+x] for x in ['AV090','AV080'] if 'Adev_'+x in D];bm=D['Bmap_ER'];bmref=D['Bmap_B'];bmd=D['Bmap_D']
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[x for x in events if x['event']=='START'];ends=[x for x in events if x['event']=='END']
win='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/'+P.name
def fig(name):return f'![{name}]({win}/figures/{name})'
def f(v,n=6):return f'{v:.{n}f}'
def motion(r):return 'PASS' if r['motion']['acceptance_pass'] else 'FAIL: '+', '.join(r['motion']['failed_requirements'])
def basic_table(rr):
 lines=['|完整运行|J_F N·s|对本组B降力%|膝真实下冲°|膝excursion−B°|原motion|','|---|---:|---:|---:|---:|---|']
 for r in rr:lines.append(f"|{r['id']}|{r['J_F_N_s']:.9f}|{r['motion']['gain_percent']:.6f}|{r['terminal_response'][1]['return_overshoot_below_goal_deg']:.9f}|{r['motion']['excursion_delta_deg'][1]:+.9f}|{motion(r)}|")
 return '\n'.join(lines)
def trade_table(rr):
 lines=['|运行|force RMS/peak N|moment integral/peak Nm·s/Nm|tracking RMS hip/knee °|min clearance m|','|---|---|---|---|---:|']
 for r in rr:
  m=r['complete_metrics'];lines.append(f"|{r['id']}|{r['force_RMS_N']:.6f}/{m['force_peak_N']:.6f}|{m['moment_integral_Nm_s']:.6f}/{m['moment_peak_Nm']:.6f}|{m['tracking_RMS_deg'][0]:.6f}/{m['tracking_RMS_deg'][1]:.6f}|{m['clearance']:.9f}|")
 return '\n'.join(lines)
at=basic_table([r for r in rows if r['id'].startswith('Adev_')]);bt=basic_table([r for r in rows if r['id'].startswith('Bmap_')])
signal_table=['|候选|Δ真实膝下冲°|ΔJ_F对ER N·s|完整TV_v Δ%|完整TV_a Δ%|完整jerk RMS Δ%|','|---|---:|---:|---:|---:|---:|']
for r in avs:
 v=r['variation_delta_vs_ER_percent']['full'];signal_table.append(f"|{r['id']}|{r['overshoot_change_vs_ER_deg']:+.9f}|{r['delta_J_F_vs_ER_N_s']:+.9f}|{v['velocity_TV_deg_s']:+.6f}|{v['acceleration_TV_deg_s2']:+.6f}|{v['combined_jerk_RMS_deg_s3']:+.6f}|")
signals='\n'.join(signal_table)
ta=f'''# Track A — 终末停止响应与真实overshoot

## 假设、合同与结论
在ER110_R4_120父规则冻结下，仅将RETURN3膝通过速度乘0.90或0.80，保留该槽原选目标、髋通过速度与duration，通过原fixed-duration certificate/mechanics/escape/current admission检验。两个候选均数学可行、真实激活，完整task/safety/receipt通过，但原motion均因excursion失败。停止该因素搜索；不通过放宽门或增加第三个更小倍率取得通过。

## 真实下冲定义与时间
本包将回程真实下冲定义为max(0,最终issued reference q−RETURN真实最小q)，另报“参考稳定停止后继续位移”。native极值分辨率0.25ms，参考稳定停止时间来自5ms记录。它们与全程excursion−matched B不同。
ER膝参考终点9.5°；实际最低8.224621516°，下冲1.275378484°。参考16.895s稳定停止时actual=8.330104289°、dq=−0.191408179°/s；271ms后达到最低点，期间继续下降0.105482772°。首次穿过9.5°在16.5085s，因此大部分下冲形成于参考停稳之前。
原B真实下冲0.577911072°；其最低点17.09825s早于参考稳定停止17.175s。不能使用同一个“停稳后位移”代替各方法完整下冲。
ER全程膝max相对B低0.148870945°、min相对B低0.697467411°；相减才得到excursion差0.548596467°。这个恒等式说明0.548596°不是overshoot幅度。

## 配对物理结果
{at}

{signals}

所有积分为完整19.030s，phase仍9.005/1.020/9.005s。B/T/D/ER与历史全trace/native/receipt物理字段逐项复现。候选在新splice前与ER全body qpos/qvel、command/contact及step归属一致，之后真实运动改变；细节见derived/CAUSAL_RESPONSE_AUDIT.json。干预不是Human真值回放。

×0.80曾使真实膝角最大变化1.270993°、膝速度最大变化3.755052°/s，但RETURN5及最终等待窗口的最大膝角差已缩到0.020987°，最终下冲差仅0.006345°。RETURN3/4/5的原选时长1.245/1.515/0.440s及请求时刻均保持，不能归因于后续duration重新选择；RETURN4髋目标因果变化−0.018624°，其余冻结规则保持。窗口账本见derived/TRACK_A_WINDOW_RESPONSE.json。
×0.80在R3及其桥接窗口节省force积分0.435311 N·s，R4及其桥接却增加1.329535，最后增加0.003167，精确闭合完整+0.897391。局部收益确实存在，却被下游代价超过；这些partial窗口只用于机制诊断，不进入排名。

## 机制证据与限制
R3/R4请求、膝首次过目标、参考停稳、实际最低点的因果估计与真值角度差均约0.001°以内；在参考停稳处估计跟踪偏差−1.169492°，真值−1.169896°。现有证据不支持“估计器完全看不到误差”。RETURN4膝速度落零后RETURN5仍在完成髋运动；参考/allocator/position/velocity torque与恢复峰同步，但本轮未单独干预中介，因此不能宣布allocator或某一模型项是唯一根因。已采样停止窗口没有clipping或shank-bed接触事件；这不等于没有cuff耦合力。

## 失败边界与再次研究要求
×0.90/×0.80只把下冲分别减少约0.003154/0.006345°，相对于原0.048596° excursion缺口不足，且J_F增加。数学速度边界变小不保证真实终末误差等比例降低。此因素信息增益已低，停止继续缩小速度。
下一项有价值证据应来自一个新的、前瞻注册的髋终末时序受控干预：膝终点/停止参考不变，仅改变原合法RETURN5髋终末时间形状，检验膝继续运动是否随之改变；先重做原证书，不更改控制gain、模型或阈值。本轮不执行第三个A候选。

{fig('Adev_terminal_response.png')}

{fig('terminal_estimate_tracking.png')}

{fig('Track_A_local_and_downstream.png')}
'''
write('TRACK_A_TERMINAL_RESPONSE.md',ta)
state_table=['|状态/方法|原完整资格|膝v95 °/s|膝a95 °/s²|真实膝下冲°|excursion−B°|','|---|---|---:|---:|---:|---:|']
for r in hist:
 if r['state']!='repair' and r['arm'] in ['T','D']:
  m=r['raw_full_motion'];state_table.append(f"|{r['id']}|{'PASS' if r['archived_all_original_qualifications'] else 'FAIL'}|{m['velocity_deg_s']['p95_abs'][1]:.6f}|{m['acceleration_deg_s2']['p95_abs'][1]:.6f}|{r['terminal'][1]['return_overshoot_below_goal_deg']:.6f}|{r['excursion_delta_vs_B_deg'][1]:+.6f}|")
tb=f'''# Track B — 状态依赖与适用域

## 假设与新增诊断
同一冻结时间修复不必适用于另一合法背景。预先登记Bmap：W1 OUTBOUND0保持，移除RETURN0背景，得到历史已暴露R0。真实commissioning后live fork，完整B/T/D/ER各自执行，B/T/D需与旧R0 raw核验。它是受控背景诊断，不是未见prefix验证；不按结果改ER参数。

{bt}

R0冻结ER原motion结论：**{motion(bm)}**。其完整资格为{bm['all_original_qualifications']}，task={bm['task']}、safety={bm['absolute_safety']}、receipt={bm['receipt']}。R0 ER绝对膝下冲{bm['terminal_response'][1]['return_overshoot_below_goal_deg']:.6f}°反而高于W1 ER的{er['terminal_response'][1]['return_overshoot_below_goal_deg']:.6f}°，相对excursion门却通过；绝对运动改善与相对资格并不等价。W1中的ER和两个新速度候选失败仍保留；R0不覆盖W1失败，不构成新广泛基线。

## 已有适用域地图
{chr(10).join(state_table)}

N2/U1/V1/V2现在全部属于已暴露诊断状态。历史独立验证在当时成立，不能在本轮再算新的未见证据。它们主要改变OUTBOUND，HOLD后RETURN几乎收敛；多个早期prefix不等于多个干预前RETURN状态。W1/R0共享OUTBOUND父历史；O0使用已见V1 OUTBOUND并保留W1 RETURN背景。重复、共享prefix、不同Human分别标注，不能合并为独立样本量。

## 绝对负担与匹配B分母
W1 T膝v95=22.559290，O0 T几乎相同；各自B全程v95却20.225905和20.979395，ratio由1.115366变为1.075307。O0 T a95=32.960832高于W1的28.552719，相对门仍可通过，因为其B参照也更高。R0 T真实下冲约1.29°大于W1 T的1.261666°，却完整资格通过；这并不说明R0实际下冲更小。完整excursion还依赖去程最大q，因此同样RETURN误差可产生不同qualification。

当前瓶颈有两层：动作发生前真实/估计状态与参考历史不同；原完整非劣门依赖全程负担和匹配B。仅phase/slot或当前目标距离不足以代表这两层，也没有足够样本证明某个在线准入阈值有效。

## 只读风险特征与下一证据
derived/STATE_RISK_FEATURES.json保存100条历史请求的deployable estimated q/dq、reference、目标距离、remaining及source age，未来完整资格/真值下冲置于offline-only标签。原完整B未来p95、native真值、最终极值不进入在线features。没有拟合、训练或部署准入器。
W2已复核无历史START；本轮未出现合格新开发候选，故W2保持未使用，未以暴露R0冒充验证。下一轮应先取得合格的机制干预，再按完整历史分组验证近干预状态；必要时补同seed严格匹配的背景因子角，不能把现有不同seed V1直接当完整factorial交互证明。

{fig('state_qualification_differences.png')}

{fig('W1_R0_state_diagnostic.png')}
'''
write('TRACK_B_STATE_ROBUSTNESS.md',tb)
sg=['|运行|raw/SG5/SG21膝jerk RMS °/s³|raw/SG5/SG21膝jerk max °/s³|','|---|---|---|']
for r in [er,*avs,bm]:
 m=r['complete_metrics']['motion'];sg.append('|'+r['id']+'|'+'/'.join(f(m[k]['full']['jerk_deg_s3']['rms'][1]) for k in ['raw','SG5','SG21'])+'|'+'/'.join(f(m[k]['full']['jerk_deg_s3']['max_abs'][1]) for k in ['raw','SG5','SG21'])+'|')
tc=f'''# Track C — 实际Human平顺性与轨迹质量

## 发现与研究分配
native true dq按原0.25ms时间轴两次gradient得到acceleration/jerk，edge_order=2、不删端点。SG5/SG21、order3只作敏感性，不替代raw验收。TV_v是双joint速度向量相邻差范数之和，TV_a同理；combined jerk RMS是sqrt(mean(sum(j²)))，各joint门另算。

{signals}

{chr(10).join(sg)}

新速度候选真实降低完整velocity TV和combined jerk RMS，却轻微增加完整acceleration TV，且未修复excursion、J_F也上升。这是实际运动的有界改善与代价并存，不是数学reference更光滑即可晋级。
还有一个直接反例：×0.80的R3参考膝速度峰从19.832669降至19.488670°/s，真实Human同窗峰却由19.866159增至20.243157°/s。参考峰下降不能替代实际峰验证；后续R4真实速度峰虽然下降，完整force仍增加。完整窗口划分及积分闭合见derived/TRACK_A_WINDOW_RESPONSE.json。

## 时间分布与历史负结果
derived/TERMINAL_ESTIMATE_AND_COMPENSATION.json逐joint保存raw峰时刻/phase、高值样本分布和平方能量份额。历史D膝267.010807°/s²窄峰、raw jerk RMS1920.131547°/s³已经由ER显著降低，但余下终末下冲并未随峰值消失。全程p95、extrema、局部峰不能互相替代。
既有18D+Waypoint：去程平滑完整J_F只降低0.016413030 N·s，回程平滑反而增加0.016430641 N·s；后者局部省0.051324而下游增加0.067755。第二轮T去/回程微小shape收益仅0.004602/0.000682 N·s，未达冻结晋级。已有完整物理证据足以停止同一0.05°边界密集搜索。
固定外端q/dq/ddq与duration的quintic具有reference积分平方jerk最小结构；这个数学结论不约束闭环实际Human一定最平滑。历史改shape的reference jerk能上升而局部速度TV下降，指标目标本就不同。

## 停止与未解决
本Track完成诊断，没有额外Waypoint物理优化；使用A的真实干预作为平顺性反例。更广合法时序/协调空间未被否定，但重新研究需要一个能解释完整下游响应的新窗口和可证伪机制，不能仅重复更小q点搜索。

{fig('Adev_full_motion_force.png')}
'''
write('TRACK_C_MOTION_SMOOTHNESS.md',tc)
td=f'''# Track D — 力、力矩与跟踪代价

## 完整配对结果
{trade_table(rows)}

W1 ER比匹配B降低J_F {er['motion']['gain_percent']:.6f}%，moment integral却由{b['complete_metrics']['moment_integral_Nm_s']:.6f}升到{er['complete_metrics']['moment_integral_Nm_s']:.6f} Nm·s（+{100*(er['complete_metrics']['moment_integral_Nm_s']/b['complete_metrics']['moment_integral_Nm_s']-1):.6f}%）。降低force不能解释为全部交互负担下降。moment仍通过原1.25工程比例门，不由此得到临床舒适性。

两个速度候选相对ER的完整J_F增加，不能称降力改进；Tracking RMS、moment peak/integral、clearance及原absolute safety均单独检查。各phase积分和峰值见EXPERIMENT_RESULTS.json/complete_metrics/phase_cost，力与力矩均按原left quadrature闭合。force RMS为原5ms采样TASK序列的均方根，单列为描述统计。

## 补偿与因果限制
终末误差、allocator、position/velocity torque、force和moment存在共同时间响应；这些分量是同一闭环中的后处理变量。norm大小不能当可相加的力矩贡献，相关峰先后也不能证明唯一中介。R0与W1之间只解释整个背景规则的条件效应，不把模型重力/弹性项代数分解叫作独立物理因果贡献。

## 决策
本轮没有找到一个同时具有明确可控机制和显著预计收益的独立力矩干预，因此完成配对审计，不重定义comfort阈值或改plant/allocator gain。下一轮可沿髋终末时序受控实验检查force/moment/跟踪是否共同改变；完整原门仍先于力排名。

{fig('force_motion_moment_tradeoff.png')}

{fig('force_and_cumulative_cost.png')}
'''
write('TRACK_D_FORCE_MOMENT_TRACKING.md',td)
te='''# Track E — 执行资格与未来学习接口

## 当前执行链与证据
保持原commissioned belief与estimated Human state → 有界参考意图 → 新quintic/连续几何和mechanics/escape → 原40ms rolling bridge → current-state admission → feedback/allocator → receipt → 0.25ms native physics。不能用数学reference、提议或激活标记代替实际positive native步。
activation_validation.py的future handoff同时核验新估计状态、估计加速度、参考误差、ROM/motion、shifted geometry、剩余预算、版本/phase及原始source与revalidation sample年龄。原始source时间不被重试刷新。scientific_scheduler.py在实际write前拒绝达到100ms的source；模拟时钟资格和host profile分开。
trace字段actual_human_acceleration_rad_s2来自SplitAccelerationMonitor对历史dq_hat的因果差分；它不是本报告离线native真值gradient。见源码索引与手工调用链说明。字段名称不作为oracle许可。

## certificate、receipt与候选身份
audit/INTERVENTION_EXECUTION_AUDIT.json从最终schedule外端状态独立重建quintic，核对positive receipt中的q/dq；逐项核验T倍率、D姿态、ER时长、新速度因子、激活和native步数。D的outer_pass_velocity_unchanged元数据描述D父选择阶段；新AV候选随后明确改变膝通过速度，最终速度以新增意图和最终曲线核验，不将父阶段元数据误读为最终速度未改。
原部分receipt不含直接plan_request_id，不能伪造。绑定使用已记录request/source/version、半开激活时段、最终参考、逐步相同torque和唯一native step数量。每组完整live fork hash相同、父等待子且保持不变；全体raw原生归属另由分离算术实现复核。

## 尚未获得的资格
PHYSICAL_LEVEL1 SCIENTIFIC_SIMULATION不等于Native LEVEL2或host LEVEL3。历史FAST完成包的original R2失败，HOLD→RETURN包42 START、19完整host、0 complete+R2 PASS、NOT_FROZEN保持。HOLD的实际参考完成与串行交接开销有证据；本轮没有改时间戳、预执行、HOLD或任何准入门来修复。strict55/FAST单项好转也不能覆盖整体失败。

## 学习接口
FUTURE_Q_LEARNING_SCHEMA.json定义identity、causal observation、proposed/action-applied、execution feedback、offline evaluation、split与policy语义。derived/STATE_RISK_FEATURES.json提供只读历史特征示例，没有训练模型。
最值得后续学习的是原执行链可认证的有界duration/pass-velocity意图及必要内部协调姿态，而非直接torque、Human qpos或增益。当前只有有限反事实标签，无法宣称少量重复即可可靠学习。排序表示需包含state-action交互；历史a(s)+b(p)中的公共state项在比较action时相消，不能成为有效状态条件排序的证据。
奖励/资格优先级：先分非法/拒绝/过期/未应用、partial、task/safety/motion/receipt失败，再在完整合格样本中比较本状态匹配B的J_F。低力motion失败必须保留分项负标签；匹配B未来p95、true native extrema、全程真值下冲仅为离线标签。后续replan策略版本必须记录，V_commit与V_replan不可混用。

## 停止原因
执行合同审计未发现应在本轮改动的确定性缺陷；不扩大为实时系统重构。本轮无RL/Q-learning/Neural Q训练，无新增执行权限，无正式基线升级。
'''
write('TRACK_E_EXECUTION_AND_LEARNING.md',te)
assert sel['primary'] is None,'This report template requires reassessment if a new primary exists'
report=f'''# iHEAR Lab — Autonomous Multi-Track Control Research v1

**结论：五个Track均完成审查，A与B完成新真实MuJoCo配对实验；没有获得修复W1的完整合格新候选。** 两个减速前速度干预确实改变Human运动，却只小幅减少终末下冲，仍未通过原excursion门。已转入R0背景诊断，未用A失败阻止其他方向。没有训练Q-learning或提升正式基线。

## 1. 五个Track分别发现什么
|Track|主要证据与结论|本轮处理|
|---|---|---|
|A 终末响应|ER真实下冲1.275378°，大部分在参考停稳前形成；停稳后仍走0.105483°。因果估计能看到偏差。×0.90/×0.80改进很小且force增加|两个候选完整physics后停止该因素|
|B 状态可靠性|绝对运动与匹配B分母共同决定资格；通过状态也可有更大的绝对下冲。R0冻结ER结果为{motion(bm)}|新增B/T/D/ER已暴露R0配对；保留适用域边界|
|C 平顺性|新候选降低完整TV_v/jerk，却增加TV_a并未消除excursion失败；旧微小Waypoint搜索收益低|raw/SG及局部/完整分析，不重开密集shape搜索|
|D 力矩/跟踪|ER降force约2.354%，moment仍高于B约5.792%；更低force不能代表全部交互负担更低|完整force/moment/tracking/clearance配对审计|
|E 执行/学习|原证书/准入/receipt可核验；host/R2等缺口仍在。在线因果特征与未来真值标签必须分开|交付学习schema，未训练/未改实时系统|

## 2. 哪些已有问题得到真实改善
本轮复现了历史ER对W1 v95/a95/amax/jerk RMS的修复。新增速度干预进一步小幅降低真实下冲、完整velocity TV与jerk RMS，幅度见下表。这些是PHYSICAL_LEVEL1的有界实际运动变化，不是完整合格或临床效果。

{at}

{signals}

## 3. 哪些问题未解决，为什么
两个新候选仍失败于膝excursion。×0.80差+0.542252°，超0.5°门约0.042252°；减速前pass速度改变并未等比例改变最终停止误差。参考停稳前已有大部分误差，停稳后髋运动仍与膝响应交织，不能用“惯性”或“allocator”单词代替未完成的机制识别。广泛状态可靠性、host实时、跨Human/硬件/临床均未解决。

## 4. 哪些干预实际改变Human
AV090/AV080都沿原证书与native链真实应用，最终q/dq/torque receipt与新曲线相符；new splice前native历史精确一致，之后真实q/dq差异可观测。R0的冻结ER也通过真实执行比较。参数意图、数学曲线、issued reference、actual Human和完整资格分别保存。细节见audit/INTERVENTION_EXECUTION_AUDIT.json与derived/CAUSAL_RESPONSE_AUDIT.json。

## 5. 是否获得新的完整合格候选
没有。AV090/AV080原motion失败，不能进入合格force排名。R0的ER是原已冻结方法在已暴露背景的诊断，不能覆盖其W1失败或重命名为广泛新基线。

## 6. 是否完成重复和未见prefix验证
新候选没有开发合格，因此按预注册分支不启动候选重复或未见W2。B/T/D/ER跨包原轨迹复现是对照一致性证据，不是新候选重复，更不是新状态。W2只注册、未消费；R0是已暴露且共享OUTBOUND历史的背景控制。

## 7. 降force是否有moment/tracking代价
有。W1 ER moment integral由B的101.253695升至107.118048 Nm·s；tracking RMS hip/knee={er['complete_metrics']['tracking_RMS_deg'][0]:.6f}/{er['complete_metrics']['tracking_RMS_deg'][1]:.6f}°。各门仍按原阈值评价，不将允许范围说成无代价。新AV候选相对ER的force还上升。完整指标见Track D与EXPERIMENT_RESULTS.json。

## 8. 当前状态适应性瓶颈
动作前估计状态、reference q/dq与历史/剩余预算未被slot索引充分表达；去程全程极值与累积分布又影响最终相对门。W1/O0几乎相同的RETURN可以有不同p95资格，R0更大绝对下冲仍可相对通过。既不能只用最终FAIL学准入，也不能用未来matched-B统计作在线输入。

{bt}

## 9. 未来学习器值得学什么
优先有界、可重新认证的时长与内部pass-velocity动作，并保留必要空间协调。学动作的状态适用范围及执行/失败反馈，不学直接torque或越过准入。所有动作必须绑定实际activation/receipt/native ownership；失败低force、partial、被拒提议不能当成功样本。完整schema已交付，本轮无训练。

## 10. 下一轮投入方向
只推荐一个优先方向：**髋终末时间形状与已停止膝参考之间的耦合响应**。以冻结ER为父，另立协议，只改变原合法RETURN5髋终末时序、保留膝参考、所有原门与完整任务，首先证伪“膝后续下冲与髋终末运动无关”。停止继续缩小R3膝速度或重做微小Waypoint扫描。获得完整合格候选后再重复并使用未见prefix，不能跳过这一步。

## 证据、尝试与保护
T0北京时间2026-10-18 15:55:26；6小时硬截止21:55:26；21:10:26后无新physics，本包实际还额外预留900s完成在途运行。物理START/END={len(starts)}/{len(ends)}，总上限60，全部串行，包含父运行与fork。A两个候选已到停止点；B背景结果、C/D/E审计提供清晰结论后提前STOP，不为了目标4–6小时耗尽时间/预算。
全任务与各phase时长保持；独立算术复核为同一agent分离实现，不冒称第二agent或人类审计。最终完整积分、native导数、dose/ROM、receipt/torque/step归属、Git逻辑状态、122233历史文件metadata/SHA、冻结manifest及owned退出，以PACKAGE_VERIFICATION.json为准。审计PASS不等于科学候选PASS。
没有Git commit/push/merge/reset/stash/clean/branch切换、历史覆盖、plant/Human/robot/cuff/contact/gain/ROM/torque/task/HOLD/阈值改动。唯一新增控制是隔离R3通过速度wrapper；其余新工作为实验编排、诊断和报告。分析曾因TASK-only数组长度停止，已显式对齐并保留说明，未影响physics或科学参数。

完整canonical包：/home/hank/coding/adaptive-traction-mpc-side-studies/{P.name}。Windows审阅镜像：{win}。raw/native/receipts保存在canonical/source/results，镜像不冒充完整raw备份。命令、源码闭包与验算入口见REPRODUCTION.md。

{fig('Adev_terminal_response.png')}

{fig('Adev_full_motion_force.png')}

{fig('state_qualification_differences.png')}

**STOP。** 不自动进入下一包，不训练学习模型。
'''
write('REPORT.md',report)
write('NEXT_RESEARCH_DECISION.md','''# 下一阶段决策

本包STOP；不自动启动下一轮或Q-learning。

唯一优先建议：冻结ER110_R4_120为失败研究父候选，另立“髋终末时序—膝停止响应”可证伪协议。膝参考已停时仍存在约0.105°继续位移，估计器可见误差；R3膝通过速度两次缩放对完整下冲影响太小。优先用原合法RETURN5髋终末时长/时形作单因素干预，检查膝实际响应、完整excursion、raw运动门、force/moment/tracking和native执行；数学预检不过则不启动。

不要继续R3速度递减、微小Waypoint盲搜、改gain/plant/阈值或把已暴露R0当未见验证。先完整开发资格通过，再冻结、确定性重复和未见合法prefix配对。W2本轮未消费；未来仍须在新实验前重新审计未见身份。
''')
write('REPRODUCTION.md',f'''# 复核与复现合同

Canonical: /home/hank/coding/adaptive-traction-mpc-side-studies/{P.name}
Python: /home/hank/envs/adaptive-online-rl-v1/bin/python
Distribution: Ubuntu-Research-Verify

本包关闭后只读复核入口（不启动physics）：
```
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/{P.name}/analysis/readonly_verify.py
```

本轮真实physics命令记录在*_OWNER.json；入口control/owner.py Adev development及Bmap development，每次START登记group plan与execution manifest SHA。原owner/STOP/时间预算阻止关闭后自动重跑；继续须新的显式版本化包。

code/source/deps/weights由Early RETURN canonical复制，只对新包绝对路径重定位。原控制、安全、native源保持，新增control/terminal_approach_planner.py；候选参数见CANDIDATE_PLAN.json与各group_PLAN。初始所有历史metadata/SHA见audit/HISTORY_BEFORE.json（镜像可不包含完整大清单）。

离线分析入口：analysis/historical_audit.py、state_and_contracts.py、deep_diagnostics.py、experiment_analysis.py、verify_execution.py、independent.py；只有独立算术模块用于最后分离复核，绝不调用MuJoCo/planner。报告由analysis/write_reports.py生成。所有这些脚本随canonical保存；封存后不运行写入型分析去改历史报告，只读验hash。

完整native与receipt: source/results/<run>/runtime_artifacts.json.gz；trace.npz是原5ms轨迹，motion_series/<run>.npz是原0.25ms真实Human及冻结导数。EXPERIMENT_RESULTS记录完整指标，ATTEMPT_ACCOUNTING记录实际新steps、父状态/候选/hash/returncode、partial和失败边界。
''')
with (P/'MULTI_TRACK_DECISION_LOG.md').open('a') as fd:fd.write('\n## D4 — 跨Track结论与停止决策\nA两次缩放真实作用小、未过excursion，停止继续缩速；B完成已暴露R0固定ER对照；C不重开低收益Waypoint，D保留力矩/跟踪代价，E交付合同/schema不重构。无新开发合格候选，W2和重复未触发。下一步只建议新的髋终末时序受控协议，本包不执行。\n')
for name in ['REPORT.md','TRACK_A_TERMINAL_RESPONSE.md','TRACK_B_STATE_ROBUSTNESS.md','TRACK_C_MOTION_SMOOTHNESS.md','TRACK_D_FORCE_MOMENT_TRACKING.md','TRACK_E_EXECUTION_AND_LEARNING.md','NEXT_RESEARCH_DECISION.md','REPRODUCTION.md','MULTI_TRACK_DECISION_LOG.md']:shutil.copy2(P/name,R/name)
print(json.dumps(dict(status='REPORTS_WRITTEN',new_candidate=None,Bmap_ER_qualified=bm['all_original_qualifications'],START=len(starts),END=len(ends))),flush=True)
