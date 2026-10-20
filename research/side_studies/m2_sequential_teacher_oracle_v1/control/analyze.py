from pathlib import Path
import json,time,hashlib,sys,subprocess,shutil
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
def load(n):return json.loads((S/n).read_text())
def put(n,x):(S/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
P=load('SEARCH_PROTOCOL.json');rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()];sel=load('FROZEN_SELECTION.json');lookup={r['id']:r for r in rows}
def measured(i):return load('reports/'+i+'_MEASURED.json')
def brief(r):
 m=measured(r['id']);return dict(id=r['id'],candidate=r['candidate'],J_F_N_s=m['J_F_N_s'],phase_J_F_N_s=r['phase_J_F_N_s'],comparison=r['comparison'],continuous_constraints=r['continuous_constraints'],motion=m['motion']['raw'],dose=m['dose'],tracking_RMS_deg=m['tracking_RMS_deg'],clearance=m['clearance'],moment_integral_Nm_s=m['moment_integral_Nm_s'],force_peak_N=m['force_peak_N'],moment_peak_Nm=m['moment_peak_Nm'],physical_task=m['native_physical_audit']['unchanged_evaluator']['physical_task_result'],native_execution=r['actual_execution'],fork_parent=r['parent_prefix'],fork_boundary=r['fork_boundary'],state=m['branch'],teacher_offline_future_evaluation=True)
discovery=[r for r in rows if not r['id'].startswith(('V','verify'))];valid=[r for r in discovery if r['comparison']['acceptance_pass']];best=max(valid,key=lambda r:r['comparison']['gain_percent']);native=lookup['baseline_NATIVE_SCALAR_18'];B=measured('baseline_B0_repeat_1')
validation=[r for r in rows if r['id'].startswith('V')];V=dict(frozen_unix=sel['unix'],selection_never_updated_after_validation=True,conditions=P['validation_conditions'],baselines={c['name']:measured(c['name']+'_B0_repeat_1') for c in P['validation_conditions']},rows=[brief(r) for r in validation],scope='same known human, legal shared native RETURN0 prefix; no clinical, cross-human, host-clock or deployable-policy claim',RETURN_state_audit=[])
for cond in P['validation_conditions']:
 prefix=cond['name'];ids=[r['id'] for r in validation if r['id'].startswith(prefix+'_')]
 for ident in [prefix+'_B0_repeat_1']+ids:
  ds=load('output/'+ident+'_DECISIONS.json')['rows'];match=[d for d in ds if d.get('phase')=='RETURN' and d.get('native_index')==1]
  if not match:continue
  d=match[0];q=load('reports/'+ident+'_MEASURED.json');summary=load('source/results/'+ident+'/summary.json');start=next(t['time_s'] for t in summary['task']['phase_transitions'] if t['to']=='HOLD')-q['phase_durations']['OUTBOUND'];native_t=[a['first_execution_physics_s'] for r in validation if r['id']==ident for a in r['actual_execution'] if a['phase']=='RETURN' and a['physically_executed_nonzero']];
  with np.load(S/'motion_series'/(ident+'.npz')) as z:
   absolute_t=float(d.get('current_inputs',{}).get('physical_time_s',start+d['task_s']));i=int(np.argmin(abs(z['time_s']-absolute_t)));assert abs(float(z['time_s'][i])-absolute_t)<1e-8;state=dict(time_s=float(z['time_s'][i]),q_rad=z['true_q_rad'][i].tolist(),dq_rad_s=z['true_dq_rad_s'][i].tolist())
  V['RETURN_state_audit'].append(dict(id=ident,phase='RETURN',slot=1,decision_task_s=d['task_s'],causal_current_inputs=d.get('current_inputs'),evaluation_truth_separate=state,first_execution_physics_s=min(native_t) if native_t else None))
states=[x for x in V['RETURN_state_audit'] if x['id'].endswith('_B0_repeat_1')]
if len(states)>=2:
 V['between_conditions_RETURN1_difference']=dict(max_abs_q_rad=float(np.max(abs(np.array(states[0]['evaluation_truth_separate']['q_rad'])-states[1]['evaluation_truth_separate']['q_rad']))),max_abs_dq_rad_s=float(np.max(abs(np.array(states[0]['evaluation_truth_separate']['dq_rad_s'])-states[1]['evaluation_truth_separate']['dq_rad_s']))))
put('VALIDATION_RESULTS.json',V)
state_audit=[]
for r in discovery:
 ds=load('output/'+r['id']+'_DECISIONS.json')['rows'];summary=load('source/results/'+r['id']+'/summary.json');start=next(x['time_s'] for x in summary['task']['phase_transitions'] if x['to']=='HOLD')-measured(r['id'])['phase_durations']['OUTBOUND']
 for slot in [0,1,2]:
  dd=[d for d in ds if d.get('phase')=='RETURN' and d.get('native_index')==slot]
  if not dd:continue
  d=dd[0];at=d.get('current_inputs',{}).get('physical_time_s',start+d['task_s'])
  with np.load(S/'motion_series'/(r['id']+'.npz')) as z:
   i=int(np.argmin(abs(z['time_s']-at)));assert abs(float(z['time_s'][i])-at)<1e-8;state_audit.append(dict(id=r['id'],slot=slot,time_s=float(z['time_s'][i]),q_rad=z['true_q_rad'][i].tolist(),dq_rad_s=z['true_dq_rad_s'][i].tolist(),causal_current_inputs=d.get('current_inputs'),truth_role='evaluation audit only'))
outids=[r['id'] for r in discovery if r['id'].startswith('outbound_')];baseline_state=next(x for x in state_audit if x['id']=='baseline_NATIVE_SCALAR_18' and x['slot']==0);entrydiff=[]
for x in state_audit:
 if x['id'] in outids and x['slot']==0:
  entrydiff.append(dict(id=x['id'],max_abs_q_rad=float(np.max(abs(np.array(x['q_rad'])-baseline_state['q_rad']))),max_abs_dq_rad_s=float(np.max(abs(np.array(x['dq_rad_s'])-baseline_state['dq_rad_s'])))))
put('RETURN_DECISION_STATE_AUDIT.json',dict(evaluation_only_states=state_audit,OUTBOUND_vs_native18_RETURN0_differences=entrydiff,not_deployment_inputs=True))
put('SEQUENTIAL_BRANCH_RESULTS.json',dict(protocol=P,discovery=[brief(r) for r in discovery],branch_queues={p.stem:json.loads(p.read_text()) for p in (S/'queue').glob('seq*.json')},RETURN_state_audit_reference=str(S/'RETURN_DECISION_STATE_AUDIT.json'),teacher_uses_future_suffix_evaluation=True,all_trajectories_full_physics_no_stitching=True,finite_best_known_only=True))
put('FORCE_MOTION_COMPARISON.json',dict(B0=B,NATIVE_SCALAR_18=brief(native),best_known=brief(best),baseline_diagnostics=[brief(r) for r in discovery if r['id'].startswith('baseline_') and r['candidate_id']!='NATIVE_SCALAR_18'],validation_results=V,acceptance_sha256=P['motion_protocol_sha256']))
def conflicts(c):
 return any(c.get('phases',{}).get(ph,[None]*5)[i] is not None for cond in P['validation_conditions'] for ph,ss in cond['prefix'].items() for i in range(len(ss)))
vbest=[r for r in validation if r['candidate_id']==best['candidate_id']];suffix_pass=len(vbest)==len(P['validation_conditions']) and all(r['comparison']['acceptance_pass'] for r in vbest);verified=suffix_pass and not conflicts(best['candidate'])
grade='VERIFIED_FEASIBLE' if verified else 'SCI_DISCOVERY_ONLY'
teachers=[]
teacher_candidates=list(sel['candidates'])
if not any(c['id']=='NATIVE_SCALAR_18' for c in teacher_candidates):teacher_candidates.append(native['candidate'])
for c in teacher_candidates:
  rr=[r for r in validation if r['candidate_id']==c['id']];dr=[r for r in discovery if r['candidate_id']==c['id']];conditioned_pass=len(rr)==len(P['validation_conditions']) and all(r['comparison']['acceptance_pass'] for r in rr);passed=conditioned_pass and not conflicts(c)
  teachers.append(dict(id=c['id'],candidate=c,grade='VERIFIED_FEASIBLE' if passed else 'SCI_DISCOVERY_ONLY',conditioned_suffix_validation_pass=conditioned_pass,nonzero_candidate_action_consumed_by_condition_prefix=conflicts(c),role='historical_fixed_comparator' if c['id']=='NATIVE_SCALAR_18' else 'new_teacher',development=[r['id'] for r in dr],validation=[r['id'] for r in rr],validation_gain_percent=[r['comparison']['gain_percent'] for r in rr],causal_input_schema='per-decision current_inputs only: observation, commissioned estimated model, B-owned current reference, phase, progress, past issued graph/history',offline_labels=['full_J_F_N_s','remaining_J_F_N_s','motion_pass'],future_truth_not_deployment_input=True,raw_v2_zero_is_placeholder=True,teacher_is_fixed_sequence_not_online_policy=True,Neural_Q_trained=False))
put('TEACHER_COORDINATION_INDEX.json',dict(teachers=teachers,data=str(S/'TEACHER_DATA.jsonl'),model_weights_frozen=True,training_performed=False,limitation='teacher selected using full future performance; finite same-human conditions only'))
repair=[r for r in discovery if r['candidate'].get('stage')=='REPAIR'];lines=['# 强低力连续协调修复','', '以下均为真实完整任务执行；收益保留只相对本轮同条件种子，未修改运动阈值。','', '|候选|完整收益%|种子收益保留%|最严重约束比|失败条件|','|---|---:|---:|---:|---|']
for r in repair:
 seed=lookup.get('baseline_'+r['candidate']['parameters']['source']);ret=100*r['comparison']['gain_percent']/seed['comparison']['gain_percent'] if seed else None
 lines.append(f"|{r['candidate_id']}|{r['comparison']['gain_percent']:.6f}|{ret:.2f}|{r['continuous_constraints']['worst_ratio']:.6f}|{', '.join(r['comparison']['failed_requirements']) or 'PASS'}|")
lines+=['','各候选真实velocity/acceleration/jerk的max/p95/RMS、行程及原native accepted delta与首次执行时刻见 SEQUENTIAL_BRANCH_RESULTS.json。不以统一缩小到近零作为修复；分别删入口、按slot重新分配原累计幅度、调整去程分配和补偿退出。','', '局部修复是否成功以冻结全部条件判断；运动代价改善或保留高降力不能单独取得可行资格。']
if (S/'STRONG_PREFIX_PRUNING.json').exists():
 x=load('STRONG_PREFIX_PRUNING.json');lines+=['','部分强去程重分配前缀已经不可由后续回程动作修复：']
 for d in x['rows']:lines.append(f"- {d['id']} 的 OUTBOUND 最大速度相对完整B峰值 {d['OUT_velocity_max_vs_full_B']}，最大加速度相对完整B峰值 {d['OUT_acceleration_max_vs_full_B']}；已有峰值超过1.1后，未来RETURN不能消除过去的峰值。因此未派发沿这些完全相同前缀的纯RETURN组合修复。这仅排除这些固定前缀，不排除修改更早OUTBOUND的其他运动。")
for seedid in ['M2_fixed_actions','C2_pair_1_2','repair2_2_0']:
 rr=[r for r in repair if r['candidate']['parameters']['source']==seedid]
 if not rr:continue
 rep=min(rr,key=lambda r:r['continuous_constraints']['worst_ratio']);seed=lookup['baseline_'+seedid];before=measured(seed['id']);after=measured(rep['id']);lines+=['',f"## {seedid}：较低最严重违反的代表 {rep['candidate_id']}", '',f"原收益 {seed['comparison']['gain_percent']:.6f}% → {rep['comparison']['gain_percent']:.6f}%；最严重约束比 {seed['continuous_constraints']['worst_ratio']:.6f} → {rep['continuous_constraints']['worst_ratio']:.6f}。",'','|真实人体指标/统计|髋：原→修复|膝：原→修复|','|---|---|---|']
 for sig in ['velocity_deg_s','acceleration_deg_s2','jerk_deg_s3']:
  for stat in ['max_abs','p95_abs','rms']:
   av=before['motion']['raw']['full'][sig][stat];bv=after['motion']['raw']['full'][sig][stat];lines.append(f'|{sig}/{stat}|{av[0]:.6f} → {bv[0]:.6f}|{av[1]:.6f} → {bv[1]:.6f}|')
 lines+=['',f"仍失败：{', '.join(rep['comparison']['failed_requirements']) or '无，motion PASS'}。jerk max仍仅诊断。"]
(S/'STRONG_MOTION_REPAIR.md').write_text('\n'.join(lines)+'\n')
(S/'OPTIONAL_TRAJECTORY_ORACLE.md').write_text('# 可选离线轨迹对照\n\nNOT_EVALUABLE：本轮未执行更自由轨迹的物理回放。已有stage1 spring2d oracle使用不同动力学，不可作为当前完整Human/接触模型对照；现有stage5 fork和native控制接口仅复用为原生序列搜索。没有在本轮建立独立可回放的连续髋膝参考求解链，未为可选阶段从零构建控制器。\n\n原生PWL在目标请求处一次采样，不能表达请求之间独立时间变化、HOLD残差、common-progress变化或直接dq/ddq。这个表达限制有代码和实际采样证据，但不能由此断言它就是高收益缺口的原因，更不能声称物理全局无解。只有未来同动力学连续参考回放成功、原生无法实现，才足以支持增添最小时间内协调自由度。\n')
ledger=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in ledger if r['event']=='START'];ends=[r for r in ledger if r['event'] in ['END','FAIL']];no_missing=all(any(e['id']==r['id'] for e in ends) for r in starts);resources=load('PROGRESS.json')
outbound=[r for r in discovery if r['id'].startswith('outbound_')];seq=[r for r in discovery if r['id'].startswith('seq')];outgood=[r for r in outbound if r['comparison']['acceptance_pass']];seqgood=[r for r in seq if r['comparison']['acceptance_pass']]
og=max(outgood,key=lambda r:r['comparison']['gain_percent']) if outgood else None;sg=max(seqgood,key=lambda r:r['comparison']['gain_percent']) if seqgood else None
lines=['# 连续协调与高质量可行运动搜索','',f"当前best-known合格完整运动 **{best['candidate_id']}**：J_F = **{best['J_F_N_s']:.6f} N·s**，相对本轮匹配B的 {B['J_F_N_s']:.6f} N·s降低 **{best['comparison']['gain_percent']:.6f}%**；结果级别 **{grade}**。有限候选搜索不代表数学全局最优。",'',f"≥2% 合格里程碑：{'达到' if best['comparison']['gain_percent']>=2 else '未达到'}；≥5%：{'达到' if best['comparison']['gain_percent']>=5 else '未达到'}。0.5%仅为历史发现门槛，不用于掩盖最终性能不足。",'', '|方案|完整J_F N·s|降低%|OUT/HOLD/RETURN N·s|运动资格|','|---|---:|---:|---|---|']
for r in [native,best]+[r for r in discovery if r['id'].startswith('baseline_') and r['candidate_id'] in ['Frozen_M2','C2_pair_1_2','M2_fixed_actions']]:
 lines.append(f"|{r['candidate_id']}|{r['J_F_N_s']:.6f}|{r['comparison']['gain_percent']:.6f}|"+'/'.join(f'{v:.6f}' for v in r['phase_J_F_N_s'].values())+f"|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|")
lines+=['','## 十项研究问题','',f"1. 加入OUTBOUND能否提升：本轮去程单动作叠加最佳合格收益为 {og['comparison']['gain_percent']:.6f}%（{og['candidate_id']}），原1.165570%为同父新物理复现。" if og else '1. OUTBOUND单动作叠加没有获得合格结果。', f"2. 连续调整：合法后续边界fork最佳合格收益 {sg['comparison']['gain_percent']:.6f}%（{sg['candidate_id']}）。每条轨迹已执行完整任务；父前序动作由真实物理推进，suffix完整评价，未相加或拼接独立实验。" if sg else '2. 连续调整没有获得合格结果。', '3. OUTBOUND与RETURN状态关系：见后续状态差和重选排名；HOLD端点可能消除去程状态差，不强求排序翻转。不同图参数但相同native sampled delta不算不同运动。', '4. 强低力修复：见 STRONG_MOTION_REPAIR.md 的真实收益保留与剩余约束；大收益而FAIL保持诊断级，不作为高质量teacher。', f"5. 最好完整运动：{best['comparison']['gain_percent']:.6f}%、{best['comparison']['gain_N_s']:.6f} N·s；主条件仍是全部运动及物理任务条件同时成立。", f"6. 2%/5%：{'达到2%' if best['comparison']['gain_percent']>=2 else '未达到2%'}，{'达到5%' if best['comparison']['gain_percent']>=5 else '未达到5%'}。", '7. 独立验证：参数在任何V输出前冻结，两个RETURN早期正负合法共享前缀条件未参与选择；验证后不修改参数。完整配对结果与真实RETURN1状态差见 VALIDATION_RESULTS.json。', '8. 接口限制：每次目标请求只采一个差分进度delta，B调度器生成时间运动；多个slot可以逐步调整，但不能原生表达请求间任意连续差分进度。尚无自由轨迹物理回放，不能断言这是收益缺口的主因。', '9. 可学习范式：以实际执行的OUT/RETURN方向、slot和当前估计状态归档少量固定完整teacher；它们使用离线未来评价选择，不是可部署在线策略。本轮未训练Neural Q，raw_v2全零K3占位不作为动作，动作来自graph/spec、accepted delta和receipt。', '10. 教授讨论瓶颈：端点/HOLD对状态差的消除、RETURN膝行程余量、保持低力时速度/加速度负担与原生目标采样粒度之间的关系。需要同动力学更自由协调参考的物理回放，才能区分接口表达不足与真正的物理权衡；有限负结果不能证明全局无解。','', '## 独立验证','', '|条件/方案|降低%|运动资格|最严重约束比|','|---|---:|---|---:|']
for r in validation:lines.append(f"|{r['id']}|{r['comparison']['gain_percent']:.6f}|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|{r['continuous_constraints']['worst_ratio']:.6f}|")
lines+=['', '上述运动非劣阈值为研究条件，未经临床舒适度验证；jerk max和阶段形状单独诊断。科学仿真执行验证不代表host-clock或真机资格。','', f"新增物理attempt **{len(starts)}/90**；验证保留18次不可转为搜索。搜索为串行运行，所有冷父、失败、重复均计入START分母；完整归档 {len(list((S/'output').glob('*_DATA.json')))} 次。总墙钟 {(time.time()-P['t0_unix'])/60:.2f} 分钟（最终退出核对见PACKAGE_VERIFICATION）。",'', '关键完整trace、native raw、紧凑结果与teacher已保留；普通新增候选在完整dense receipt审计后报告化，删除范围只限新包的生成raw，不删除历史。原科学模型、B、安全、issued slots、bridge和生命周期语义保持。','', 'STOP。本轮没有Neural Q训练、在线个体化、正式B架构修改或自动下一工作包。']
lines.insert(-1,f"\n最好方案完整序列在验证条件中的资格：{grade}；prefix条件下冻结剩余动作是否均通过：{suffix_pass}。RETURN0为合法状态生成前缀；若候选本身有非零R0，该动作被前缀消耗，只能称前缀条件下suffix的完整运动验证，不冒称同一整串原动作已独立验证。")
lines.insert(-1,'\n原生安全且任务完成为A层；冻结motion通过为B层；A/B均成立且≥2%作为本轮明显收益C里程碑。小幅B层改善可以可信，但不自动达到C目标。部分普通祖先raw报告化后，复现门限仅覆盖全部归档control trace和dense人体q/dq/derivatives，完整receipt及其他native body直接逐行复现不可再评；范围在各ANCESTOR_REPLAY_GATE明确记录。起始B与关键最好方案仍保留完整raw直接核验。')
lines.insert(-1,f"\n最好方案完整物理执行了 {sum(d['physically_executed_nonzero'] for d in best['actual_execution'])} 次非零协调调整；实际首次执行物理时刻及accepted delta："+'；'.join(f"{d['phase']} @ {d['first_execution_physics_s']:.6f}s，delta={d['native_coordination_metadata'][0].get('delta'):.6f}" for d in best['actual_execution'] if d['physically_executed_nonzero'])+'。')
if entrydiff:
 lines.insert(-1,f"\n去程单动作相对NATIVE18在RETURN0时的最大真实状态差：q {max(x['max_abs_q_rad'] for x in entrydiff):.6g} rad，dq {max(x['max_abs_dq_rad_s'] for x in entrydiff):.6g} rad/s。状态审计与后续RETURN候选完整排序见RETURN_DECISION_STATE_AUDIT.json及SEQUENTIAL_BRANCH_RESULTS.json；接近数值零的入口差不能支持状态相关重选收益。")
(S/'REPORT.md').write_text('\n'.join(lines)+'\n')
put('PACKAGE_VERIFICATION.json',dict(status='PENDING_FINAL_PROCESS_AND_HASH_CHECK',attempts=len(starts),all_started_attempts_have_end_or_failure=no_missing,missing=[r['id'] for r in starts if not any(e['id']==r['id'] for e in ends)],protocol_hash=hashlib.sha256((S/'SEARCH_PROTOCOL.json').read_bytes()).hexdigest(),motion_protocol_hash=hashlib.sha256((S/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest(),elapsed_s=time.time()-P['t0_unix'],grades=dict(best=grade,performance='NEGATIVE_RESULT' if best['comparison']['gain_percent']<2 else grade,optional_oracle='NOT_EVALUABLE'),no_training=True,no_B_semantic_change=True))
print(json.dumps(dict(best=best['candidate_id'],gain=best['comparison']['gain_percent'],grade=grade,attempts=len(starts))))
