from pathlib import Path
import json,time,hashlib,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
W='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/'+R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def md(n,s):(P/n).write_text(s.strip()+'\n')
def link(n,title=None):return '['+(title or n)+']('+W+'/'+n+')'
def fig(n,title):return '!['+title+']('+W+'/figures/'+n+')'
results=read('EXPERIMENT_RESULTS.json');by={r['id']:r for r in results['rows']};account=read('ATTEMPT_ACCOUNTING.json')
assert read('PHYSICS_CLOSED.json')['status']=='CLOSED'
b,e,h=[by['Ctrl_'+x] for x in ['B','ER','H150']];wb,we,wh=[by['W2_'+x] for x in ['B','ER','H150']]
assert h['selection_eligible'];repeat=read('REPEAT_VERIFICATION.json');assert repeat['status']=='PASS'
def os(r):return r['terminal'][1]['return_overshoot_below_goal_deg']
def delta(r):return r['excursion_delta_B_deg'][1]
def pct(v,base):return 100*(v/base-1)
def brief(r):return dict(id=r['id'],candidate_hash=r['candidate']['candidate_hash'],J_F_N_s=r['J_F_N_s'],force_reduction_percent=r['motion']['gain_percent'],knee_overshoot_deg=os(r),knee_excursion_delta_B_deg=delta(r),all_original_qualifications=r['all_original_qualifications'],full_new_contract_qualified=r['fully_qualified'],selection_eligible=r['selection_eligible'],motion_failed_requirements=r['motion']['failed_requirements'])
valid=dict(status='PASS_ONE_UNSEEN_PREFIX' if wh['selection_eligible'] else 'FAIL_UNSEEN_PREFIX',primary='H150',candidate_frozen=read('NEW_FROZEN_SELECTION.json'),deterministic_repeat=repeat,registration=read('HOLDOUT_REGISTRATION.json'),development=[brief(r) for r in [b,e,h]],unseen_prefix=[brief(r) for r in [wb,we,wh]],holdout_consumed=True,no_holdout_retuning=True,same_Human=True,physical_task_seconds=19.030,original_gate_deg=.5,evidence_scope='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION; one held-out legal prefix, not formal LEVEL2, host real-time LEVEL3, cross-Human, hardware or clinical qualification',not_statistical_replication=True)
put('VALIDATION_RESULTS.json',valid)

ledger=[]
for g in ['Dev','Ctrl','W2']:
 plan=read(g+'_PLAN.json')
 for arm in plan['arms']:
  ident=g+'_'+arm['id'];attempt=next((r for r in account['rows'] if r['id']==ident),None);out=by.get(ident)
  ledger.append(dict(id=ident,group=g,role=plan['condition']['role'],candidate=arm,registered_before_START=attempt is None or plan['frozen_unix']<=attempt['start_unix'],status='NOT_STARTED_SUPERSEDED_BY_BOUNDED_INTERFACE_REPAIR' if attempt is None else attempt['status'],actual_new_native_steps=attempt['actual_new_native_steps'] if attempt else 0,returncode=attempt['returncode'] if attempt else None,partial_reason=attempt['partial_reason'] if attempt else None,result=brief(out) if out else None,actual_execution_manifest_sha256=attempt['code_manifest_sha256'] if attempt else None,selection='FROZEN_PRIMARY' if arm['id']=='H150' else 'BASELINE' if arm['id'] in ['B','T','D','ER'] else 'NO_VALUE_AT_TESTED_BOUNDS'))
for row in read('audit/TIMING_PRECHECKS.json')['rows']:
 if row['status']!='PASS':ledger.append(dict(id=row['id'],status='PREPHYSICAL_INTERFACE_REJECTED',actual_new_native_steps=0,START=False,parameters=dict(duration_factor=row['factor']),source_hash=read('CANDIDATE_PLAN.json')['source_hashes']['terminal_planner.py'],archived_identity_sha256=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest(),identity_scope='Offline screening point recorded before physics; archival record hash computed at closeout, not represented as a prospective START candidate',evidence=row))
put('CANDIDATE_LEDGER.json',dict(status='COMPLETE',entries=ledger,partial_ranked=False,one_bounded_interface_repair=read('audit/BOUNDED_INTERFACE_REPAIR_V2.json'),all_candidates_have_registered_identity=True,parameter_search_stopped=True))

def maintable(rr):
 s='|方案|J_F (N·s)|相对B降力|膝下冲 (°)|excursion−B (°)|全部资格|\n|---|---:|---:|---:|---:|---|\n'
 for r in rr:s+=f"|{r['candidate']['id']}|{r['J_F_N_s']:.6f}|{r['motion']['gain_percent']:.6f}%|{os(r):.6f}|{delta(r):+.6f}|{'PASS' if r['fully_qualified'] else 'FAIL: '+', '.join(r['motion']['failed_requirements'])}|\n"
 return s
rr=[by['Dev_D'] if a=='D' else by['Ctrl_'+a] for a in ['B','T','D','ER','H150','KD120','PD','FF','PDFF']]
ct='|辅助|Δ下冲相对ER (°)|ΔJ_F (N·s)|有效修正receipt|最大广义修正 [hip,knee] (Nm)|结论|\n|---|---:|---:|---:|---|---|\n'
for a in ['KD120','PD','FF','PDFF']:
 r=by['Ctrl_'+a];c=r['controller_execution'];assert c['status']=='PASS'
 ct+=f"|{a}|{os(r)-os(e):+.8f}|{r['J_F_N_s']-e['J_F_N_s']:+.8f}|{c['active_positive_receipt_count']}|{[round(v,6) for v in c['generalized_correction_peak_abs_nm']]}|motion FAIL|\n"
cost='|方案|moment积分 (Nm·s)|moment峰 (Nm)|tracking RMS髋/膝 (°)|最大robot力矩 (Nm)|膝≥20Hz速度能量占比|\n|---|---:|---:|---|---:|---:|\n'
for r in [b,e,h]+[by['Ctrl_'+a] for a in ['KD120','PD','FF','PDFF']]:cost+=f"|{r['candidate']['id']}|{r['moment_integral_Nm_s']:.6f}|{r['moment_peak_Nm']:.6f}|{r['tracking_RMS_deg'][0]:.6f} / {r['tracking_RMS_deg'][1]:.6f}|{max(r['robot_torque_peak_abs_nm']):.6f}|{r['velocity_spectral_energy_fraction_ge20Hz'][1]:.3e}|\n"

md('EXISTING_CONTROLLER_TUNING.md',f'''# 原反馈的小幅优化

结论：在本轮冻结的终末门控和幅度内，增加原膝速度反馈20%的KD120没有修复价值。膝下冲从{os(e):.9f}°变为{os(by['Ctrl_KD120']):.9f}°，excursion差仍为{delta(by['Ctrl_KD120']):+.9f}°，保持motion FAIL。不能据此否定所有阻尼优化，只能否定本次参数与接口组合。

原Human PD为Kp=[180,140]、Kd=[28,22]，原robot笛卡尔/姿态及零空间反馈保留。KD120新增项为near×0.20×22×(dq_ref,k−dq_est,k)，仅RETURN临近终点有效；总新增加速度±0.2rad/s²、变化率1rad/s³。因限幅存在，它不是全程将Kd精确改为26.4。没有积分项或更快执行入口。

新增意图经M(q_est)映射为广义作用，位于原action transforms与最终executable filter之前，保持原allocator/supervisor/write。候选是新控制律，不能称为B原能力；原reference证书只保留其原路径范围。每个变化后的输出均重做原检查并绑定positive-step receipt，见{link('audit/CONTROL_EXECUTION_VERIFICATION.json')}。

理想2DOF局部PD极点仅是设计参考，不能证明robot–cuff–Human的全局稳定性。本轮完整native轨迹、原全部运动/安全门和力矩/振荡诊断才是实证范围。

{ct}

一次接口修复：v1在主进程查询了只存在于planner worker的terminal属性。Dev_KD120在新增native step=0时失败；父partial与原STOP保留。v2只改为读取已接受的deployable terminal缓存；缺失缓存时禁用辅助。科学参数完全未变。修复前后代码、hash、纯接口检查均保存，没有用失败partial积分排名。其他新控制方向使用同一已修复接口。

停止KD120方向，不扩大增益。最小侵入的H150已有更明确的受控物理收益。
''')
md('PD_ASSIST_STUDY.md',f'''# 轻量终末PD辅助

结论：本次轻量PD没有独立改善价值，真实下冲比ER增加{os(by['Ctrl_PD'])-os(e):.8f}°，仍未通过原excursion门。其物理输出确实生效，不是零作用或未执行。

辅助意图采用Kp=14、Kd=4.4：max(0,14×(q_goal−q_est)−4.4×dq_est)，只沿膝终末制动方向作用。目标来自当前任务已接受的terminal reference缓存；当前issued终点为9.5°，不是偷偷改动注册10°任务目标。

near门由当前reference距终点6°以内逐渐开启，2°以内达到1；速度方向门在−0.2至+0.2°/s平滑变化；停止距离使用当前估计负向速度的平方/(2×0.35)，配合2°位置裕量。三者都是当前因果状态/参考函数，不以“17秒”触发。幅度±0.2rad/s²、变化率1rad/s³；stale、非有限值或无合法目标时辅助归零，并保留原安全机制的最终决定权。

新增广义作用=M(q_est)×delta_a，不直接附加到电机力矩。原reference输入定义、40ms bridge、100ms lifecycle/source age、5ms控制周期不变。reference证书不声称覆盖新控制律；变化后的作用由原输出过滤器、allocator、supervisor和actual-write检查重新验证。

{ct}

正向制动意图未必降低耦合系统的最终下冲；这里的结果表明该微小附加作用没有足够收益，不足以唯一归因于allocator、髋膝惯性或cuff柔顺。没有继续试更大Kp/Kd，也不把有界、局部稳定极点或“无安全失败”误称为全局稳定证明。

{fig('09_controller_intents.png','有界辅助意图')}
''')
interaction=os(by['Ctrl_PDFF'])-os(by['Ctrl_PD'])-os(by['Ctrl_FF'])+os(e)
md('FEEDFORWARD_ABLATION.md',f'''# 新增前馈与PD组合消融

原系统已补偿Human重力/科氏/被动项/软ROM/残差，并有robot bias torque。活跃Human跟踪律没有直接+ddq_ref项，因此本次FF只测试0.5×当前合法reference加速度，经M(q_est)转换，避免重复加重力或常数力矩。

FF同样受终末空间门、±0.2rad/s²和1rad/s³限制；PDFF复用完全相同的PD与FF参数。二者相加后共享同一幅度与变化率限幅，所以组合是有记录的非线性消融，不能假设两项贡献线性相加。

{ct}

FF相对ER使下冲增加{os(by['Ctrl_FF'])-os(e):.8f}°，并增加J_F={by['Ctrl_FF']['J_F_N_s']-e['J_F_N_s']:.8f}N·s。PDFF下冲为{os(by['Ctrl_PDFF']):.8f}°；四项差分interaction={interaction:+.8f}°。这些数值只刻画本次确定性比较，不是统计显著性，也不能证明更完整的闭环预测前馈一定无效。

本组PD、FF、PDFF均没有获得可采纳的修复；不增加这三个模块，不以隐藏调参追求门槛通过。H150的reference-only收益单独报告，它来自控制变量时序实验，不冒称由一个已验证的闭环模型预测器自动得出。

{cost}
''')

holdtext=(f"在此前未消费的W2合法prefix上，H150也通过全部原资格：J_F={wh['J_F_N_s']:.6f}N·s，相对匹配B降{wh['motion']['gain_percent']:.6f}%；下冲{os(wh):.6f}°，excursion差{delta(wh):+.6f}°。" if wh['selection_eligible'] else f"W2新prefix验证失败：{wh['motion']['failed_requirements']}。冻结候选没有在W2上重新调参；W1合格不能升级为普遍适用。")
md('REPORT.md',f'''# iHEAR Lab — Model-Based Terminal Compensation & Lightweight Feedback Study v1

本轮获得一个侵入较小的合格研究候选H150：仅将ER的RETURN5髋终末时长乘1.5并向上量化到5ms（W1为0.440→0.660s；W2为0.515→0.775s），保持膝参考意图和完整19.030s任务。W1真实膝下冲减少{os(e)-os(h):.6f}°（{100*(1-os(h)/os(e)):.3f}%），excursion差从{delta(e):+.6f}°降到{delta(h):+.6f}°，通过原B+0.5°门；降力{h['motion']['gain_percent']:.6f}%基本完整保留。确定性重复逐字段一致。{holdtext}

这是一项有限幅度的修复，不是消除过冲：W1仍有{os(h):.6f}°下冲，而原B为{os(b):.6f}°。W1的excursion门余量只有{.5-delta(h):.6f}°。H150没有新增PD或FF，也没有证明现有模型能够准确预测完整耦合系统的停止位置。

## 关键定义与设计

所有下冲按RETURN期间“最终issued膝reference 9.5°−真实最低膝角”定义，截断至非负。注册任务目标10°仍保留；若改按10°计，下冲会增加0.5°。reference自身运动、actual−reference误差、actual越过目标、全程max−min excursion、相对B excursion差是五个不同量。

W1 ER最低膝角8.224622°，发生在17.166000s；reference于16.895s停稳。停稳时已下冲1.169896°，其后继续0.105483°，约91.7%的下冲在reference停止前形成。不能把1.275378°下冲当成+0.548596° excursion差。

W1先复现冻结B/T/D/ER，再做H150和受限阻尼/PD/FF/PDFF；仅一次接口缺陷修复，参数不变。H150在第一次开发合格后即冻结，随后fresh cold parent完整重复，再运行此前未消费的W2配对。重复比较所有trace字段、native body/contact/torque/ownership和科学receipt/reference/source字段；host墙钟profiling不要求一致。开发数据不是盲测；确定性重复也不是鲁棒性证据。W2只测试同一Human的新合法prefix。

W1 seed=2026102001，prefix为OUTBOUND [0.08,0.04,0.03]、RETURN [0.04,0.02,0.03]；W2 seed=2026102002，prefix为OUTBOUND [0.11,−0.035,0.045]、RETURN [−0.04,0.025,−0.035]。这些是冻结接口中的合法协调动作，不是重放或直接设置Human qpos/qvel。

## 完整物理结果

{maintable(rr)}

W1中的T、D和ER仍保留原FAIL。KD120/PD/FF/PDFF都完成任务、安全和receipt检查，但未修复excursion，不升级为合格方案。仅比较完成的任务积分，失败partial没有参与排名。

{fig('05_force_motion_moment.png','力、运动及moment完整对照')}

## 对12个研究问题的回答

1. **B已有反馈与补偿。** 外层估计状态waypoint重规划，Human PD（Kp=[180,140]、Kd=[28,22]），Human逆动力学/重力/科氏/被动/软ROM/残差，增量加速度和clearance投影，robot笛卡尔/姿态/零空间反馈及bias torque都已存在。没有发现该活跃路径的积分项；Human跟踪律没有直接+ddq_ref项。详见{link('CONTROL_ARCHITECTURE_AUDIT.md')}。

2. **有反馈仍会过冲。** 广义加速度/力矩请求不是实际施加给Human的响应，robot–cuff传递与实际耦合不在2DOF闭环预测内。16.895s膝PD已请求+168.174°/s²制动，真实native加速度只有+5.753°/s²；以实测wrench驱动Human模型预测为+16.049°/s²。终末未发现torque clipping、床接触或增量投影active。证据支持“存在请求—响应差异”，不支持唯一根因归责。

3. **模型能否提前预测？** 因果100ms预测中，实测wrench冻结模型的膝位置RMSE0.038690°、p95误差0.074372°；保持当前广义请求为输入的模型RMSE0.138120°。简单因果恒加速度为0.031145°。200ms风险预测可在首次越过目标前约0.1585s发现趋势，但还不能可信预测完整停止位置或比较候选动作。误差范围是开发轨迹经验误差，不是独立校准的不确定性保证，因此没有部署自动预测补偿器。详见{link('MODEL_PREDICTION_STUDY.md')}。

4. **不新增控制器能否修复？** H150在本轮测试条件能修复原运动资格，同时实际下冲减少；它复用合法reference与完整准入/证书。控制变量证据：W1膝reference最大差5.55e−17rad，所有native机器人/人体状态、输出力矩和接触在干预前完全一致；第一次reference变化后才出现物理分叉。由此确认髋时序可因果改变膝响应，但不能分离人体惯性、robot反馈与cuff传递各自贡献。不是“模型已准确预测所以成功”。

5. **PD有独立价值吗？** 本次有界PD使下冲增加{os(by['Ctrl_PD'])-os(e):.8f}°，没有价值；不扩大增益搜索。此结论限定于本次门控、参数与接口。详见{link('PD_ASSIST_STUDY.md')}。

6. **新增前馈有独立价值吗？** 本次不重复重力的半幅reference ddq前馈使下冲增加{os(by['Ctrl_FF'])-os(e):.8f}°，J_F也增加，没有采纳价值。

7. **组合更好吗？** PDFF真实下冲{os(by['Ctrl_PDFF']):.8f}°，仍FAIL，没有显示有用互补。共享总限幅的非线性作用已公开，未使用隐藏调参。详见{link('FEEDFORWARD_ABLATION.md')}。

8. **哪种最小侵入？** H150仅扩展原合法终末quintic时序，不增加执行频率、独立反馈状态或电机力矩入口。KD120仍是改变控制律的新候选，而不是原B正式能力。

9. **是否保留降力并通过全部运动资格？** W1 H150 J_F={h['J_F_N_s']:.9f}N·s，保留ER降力收益{h['force_saving_retention_fraction']*100:.6f}%，下冲确实下降；完整task、原safety/motion/receipt/native ownership均通过，未放宽+0.5°门。合格不意味着恢复到B的下冲水平。

10. **是否在未见状态复现？** {holdtext} 验证prefix在候选冻结后登记，扫描33个历史START日志确认未消费；执行后不调参。完整证据见{link('VALIDATION_RESULTS.json')}。

11. **是否存在新代价？** H150相对ER的moment积分降低{e['moment_integral_Nm_s']-h['moment_integral_Nm_s']:.6f}Nm·s，最大robot力矩从{max(e['robot_torque_peak_abs_nm']):.6f}降到{max(h['robot_torque_peak_abs_nm']):.6f}Nm；髋/膝tracking RMS也降低。相对B仍保留moment积分+{pct(h['moment_integral_Nm_s'],b['moment_integral_Nm_s']):.3f}%、膝tracking RMS+{h['tracking_RMS_deg'][1]-b['tracking_RMS_deg'][1]:.6f}°的代价，但满足原门。没有观察到新的接触/执行安全失败。高频速度能量很小但膝≥20Hz占比相对ER略升，不能写成“完全没有高频增加”，也不以此宣称全局稳定。

12. **最终策略。** 将冻结H150保留为当前最小改动的研究候选；不替换正式B，不把ER单独升级。停止本次KD120、PD、FF、PDFF方向。下一步若另行授权，优先识别因果的robot–cuff–Human闭环输入响应与终末作用传递，再研究更早的减速/补偿；不继续追逐0.5°门边界，也不自动开启新包。

## 代价和新状态配对

{cost}

≥20Hz指标是完整native速度FFT能量占比，含端点/相位转换影响，属于振荡诊断而非独立稳定门。原raw速度/加速度/jerk、phase/dose、moment、tracking及force峰门均保留。运动资格采用冻结的10%负担门；更严的0%/5%敏感性结果在EXPERIMENT_RESULTS中保留。phase-shape是原协议的诊断量，不是后来豁免的门：H150与B同一时间的phase-shape最大差为W1 {h['motion']['phase_shape_max_delta_deg']:.3f}°、W2 {wh['motion']['phase_shape_max_delta_deg']:.3f}°，不能将“资格通过”理解成全程逐点复制B或临床等效。

W2的T和ER本身均通过原运动门。H150在W2验证的是进一步减少真实下冲并保持原资格，不能描述为又一次将ER从FAIL修到PASS。W2下冲相对ER减少{os(we)-os(wh):.6f}°，降力收益保留{wh['force_saving_retention_fraction']*100:.6f}%；任务、HOLD及各phase时长未改变。

W2 H150相对ER的代价变化：J_F {wh['J_F_N_s']-we['J_F_N_s']:+.6f}N·s，moment积分 {wh['moment_integral_Nm_s']-we['moment_integral_Nm_s']:+.6f}Nm·s，最大robot力矩 {max(wh['robot_torque_peak_abs_nm'])-max(we['robot_torque_peak_abs_nm']):+.6f}Nm，tracking RMS髋/膝分别{wh['tracking_RMS_deg'][0]-we['tracking_RMS_deg'][0]:+.6f}°/{wh['tracking_RMS_deg'][1]-we['tracking_RMS_deg'][1]:+.6f}°。其moment积分仍比匹配B高{pct(wh['moment_integral_Nm_s'],wb['moment_integral_Nm_s']):.3f}%，满足原门；不能把力积分降低理解成所有负担都比B低。

{maintable([wb,we,wh])}

{fig('08_development_holdout.png','开发及未见prefix配对')}

{fig('07_coupling_and_control.png','髋膝响应与实际控制输出')}

## 证据、预算和保护

共{account['START']}次START/{account['END']}次END（上限80），其中{account['complete_runs']}个完整运行、{account['partial_failed_runs']}个保留的失败/partial；实际新增native steps={account['actual_new_native_steps']:,}，不重复计入fork继承的prefix。所有物理串行；父进程等待子fork时不推进物理。原Dev接口失败和父partial未被覆盖，Ctrl/W2均完成完整cold parent。

所有完成记录由独立算术实现重新从raw计算5ms左端force积分、0.25ms真实状态导数和原motion统计，并逐native step关联实际receipt、力矩、ownership及source age。该复核在单独只读进程执行，但仍由同一研究Agent完成，不声称独立人员审计。全部owned进程退出；START/END闭合；历史文件逐个重新SHA256，Git HEAD/branch/status/cached/unstaged逻辑状态保持原样。最终校验结果见{link('PACKAGE_VERIFICATION.json')}，具体记账见{link('ATTEMPT_ACCOUNTING.json')}。

唯一证据等级为PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION。没有正式LEVEL2、host实时LEVEL3、跨Human、硬件或临床资格。两种执行版本已停止；不自动提交Git或启动下一研究包。

canonical完整原始包：`{P}`。Windows交付目录同时保留报告、图、控制/分析源码、JSON、trace/native派生序列及runtime原始记录；完整manifest与逐文件交付SHA核验保证二者一致。运行时临时文件不作为科学证据。
''')

md('NEXT_RESEARCH_DECISION.md',f'''# 研究决策：完成后STOP

采纳范围：冻结H150作为PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION研究候选。它不替代正式B，也不改变原18D/T/D/ER身份。{holdtext}

保留：RETURN5髋时长×1.5并向上量化到5ms（W1 0.440→0.660s，W2 0.515→0.775s）；现有5ms控制、40ms bridge、100ms lifecycle/source age、全部原资格门和冻结plant。

停止：本次有界KD120、PD、FF、PDFF。它们已真实执行，但没有修复原excursion门；不扩大增益，不用验证集再调参。H075在原接口预检被拒绝，没有START。

最小未解问题是实际下冲仍约{os(h):.3f}°，且多数在reference停稳前形成。当前Human模型对实测输入有短期预测价值，但把广义请求当作实际输入会显著误判未来响应；它缺少可用于控制选择的耦合闭环输入响应预测。

若用户另行授权下一轮，建议预注册小扰动的合法输入响应识别协议，明确测量wrench、请求wrench、robot/cuff动态状态与控制回路的因果映射；用开发外轨迹校准100–300ms误差及候选动作效应，再讨论更早的参考减速安排。跨Human需另立协议，不能修改本轮冻结plant来补做验证。这里仅给研究建议，没有启动任务或实验。

本轮已有完整对照、确定性重复及一个未消费prefix验证，信息足以作当前决策；没有为了用满4–6小时或80次START而继续低收益搜索。执行已封存，全部owned进程退出后STOP。
''')
for n in ['CONTROL_ARCHITECTURE_AUDIT.md','TERMINAL_OVERSHOOT_DIAGNOSIS.md','MODEL_PREDICTION_STUDY.md']:
 s=(R/n).read_text();s=s.replace('](figures/',']('+W+'/figures/');md(n,s)
for f in list(P.glob('*.md'))+[P/n for n in ['VALIDATION_RESULTS.json','CANDIDATE_LEDGER.json']]:shutil.copy2(f,R/f.name)
print(json.dumps(dict(status='REPORTS_WRITTEN',validation=valid['status'],starts=account['START'])),flush=True)
