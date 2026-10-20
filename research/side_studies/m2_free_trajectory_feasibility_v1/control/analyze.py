from pathlib import Path
import json,sys,time,hashlib,collections,shutil,subprocess,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
sys.path.insert(0,str(S/'code'))
from study_common import clean,sha
import numpy as np
import analyze_matched as am
def load(p):return json.loads(Path(p).read_text())
def put(n,x):(S/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()]
dev=[r for r in rows if r['id'].startswith('development_resume_')]
selected=load(S/'FROZEN_SELECTION.json')
best=selected['best'];bm=load(best['metrics_path']);base=load(S/'reports'/(best['base_id']+'_MEASURED.json'))
allmetrics={r['id']:load(r['metrics_path']) for r in rows}
def free_execution(ident):
    summary=load(S/'source/results'/ident/'summary.json')
    lineage=load(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'))
    byidx={r['decision_index']:r for r in lineage['rows']}
    out=[]
    for rec in summary['learning_records']:
        plan=rec['selected_plan'];meta=plan.get('execution_screen',{}).get('free_trajectory')
        if meta is None:continue
        idx=rec.get('decision_index');actual=byidx.get(idx,{})
        owned=actual.get('actual_command_receipts',[])
        schedule=plan.get('schedule',{})
        ph=actual.get('phase');j=0 if ph=='OUTBOUND' else 5;active=bool(np.any(np.asarray(meta.get('parameters',np.zeros(10)))[j:j+5]))
        out.append(dict(index=idx,phase=ph,active_new_freedom=active,meta=meta,selected_plan_activated=rec.get('selected_plan_activated'),positive_step_native_count=actual.get('actual_native_steps',0),first_effect_physics_s=actual.get('first_execution_physics_s'),positive_step_receipt_count=len(owned),target_q_rad=plan.get('target_q_rad'),schedule=schedule,receipt_ids=[r['receipt_index'] for r in owned],actual_torque_peak_by_joint_nm=np.max(abs(np.array([r['command_torque_nm'] for r in owned])),axis=0).tolist() if owned else None))
    return dict(id=ident,status=lineage['status'],free_selected_records=out,accepted_positive_step_plans=sum(r['active_new_freedom'] and r['meta']['status']=='ACCEPTED' and r['selected_plan_activated'] and r['positive_step_native_count']>0 for r in out),ownership_error_count=lineage['ownership_error_count'],expired_write_receipts=lineage['expired_actual_write_receipts'])
executions={r['id']:free_execution(r['id']) for r in dev}
failcounts=collections.Counter(k for r in dev if np.any(r['candidate'].get('free_parameters',[])) for k in r['comparison']['failed_requirements'])
strong=min(dev,key=lambda r:r['J_F_N_s'])
def cost_bins(ident):
    summary=load(S/'source/results'/ident/'summary.json')
    tr={r['to']:r['time_s'] for r in summary['task']['phase_transitions']}
    with np.load(S/'source/results'/ident/'trace.npz') as z:
        mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1)
    bounds=[t[0],tr['HOLD'],tr['RETURN'],tr['COMPLETE']];out={}
    for ph,a,b in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
        cuts=np.linspace(a,b,11)
        out[ph]=[dict(normalized_phase_interval=[i/10,(i+1)/10],physical_interval_s=[float(cuts[i]),float(cuts[i+1])],J_F_N_s=float(f[:-1]@np.maximum(0,np.minimum(t[1:],cuts[i+1])-np.maximum(t[:-1],cuts[i])))) for i in range(10)]
    return out
def violation_detail(row):
    ident=row['id'];m=allmetrics[ident]
    with np.load(S/'motion_series'/(ident+'.npz')) as z:
        t=z['time_s'];phase=z['phase'];dt=np.r_[np.diff(t),0.];out={}
        for field,metric in [('true_dq_rad_s','velocity_deg_s'),('acceleration_rad_s2','acceleration_deg_s2'),('jerk_rad_s3','jerk_deg_s3')]:
            x=np.rad2deg(z[field]);limit=np.array(base['motion']['raw']['full'][metric]['max_abs'])*1.1
            mask=np.abs(x)>limit
            peak=np.argmax(abs(x),axis=0)
            out[field]=dict(max_threshold_diagnostic_only_for_jerk=field=='jerk_rad_s3',seconds_over_B_peak_110_by_joint=np.sum(mask*dt[:,None],axis=0),phase_seconds={ph:np.sum(mask[phase==ph]*dt[phase==ph,None],axis=0) for ph in ['OUTBOUND','HOLD','RETURN']},actual_peak_by_joint=np.max(abs(x),axis=0),peak_physics_s_by_joint=t[peak],peak_phase_by_joint=phase[peak].tolist(),actual_p95=np.quantile(abs(x),.95,axis=0),actual_rms=np.sqrt(np.mean(x*x,axis=0)))
        out['q_extrema_actual']={str(j):dict(minimum_deg=float(np.rad2deg(np.min(z['true_q_rad'][:,j]))),minimum_physics_s=float(t[np.argmin(z['true_q_rad'][:,j])]),maximum_deg=float(np.rad2deg(np.max(z['true_q_rad'][:,j]))),maximum_physics_s=float(t[np.argmax(z['true_q_rad'][:,j])])) for j in [0,1]}
        out['contacts_and_controls_from_original_audit']=m['native_physical_audit']
    with np.load(S/'source/results'/ident/'trace.npz') as z:
        mask=z['stage']=='TASK';tau=z['cr12_actuator_command_nm'][mask]
        out['actual_control']=dict(torque_peak_by_joint_nm=np.max(abs(tau),axis=0),torque_RMS_by_joint_nm=np.sqrt(np.mean(tau*tau,axis=0)),shank_bed_contact_samples=int(np.count_nonzero(z['shank_bed_contact_evaluation_only'][mask])),contact_histogram=dict(collections.Counter(str(v) for v in z['active_contact_pairs_evaluation_only_json'][mask])),clearance_minimum=dict(session=float(np.min(z['session_shank_clearance_m'][mask])),envelope=float(np.min(z['dev_d_session_envelope_clearance_m'][mask])),measured_sleeve=float(np.min(z['dev_d_measured_sleeve_gap_m'][mask]))))
    cb=cost_bins(ident);bb=cost_bins(base['id'])
    out['force_gain_intervals']={ph:[dict(**c,matched_B_J_F_N_s=b['J_F_N_s'],gain_N_s=b['J_F_N_s']-c['J_F_N_s']) for c,b in zip(cb[ph],bb[ph])] for ph in cb}
    out['force_bin_alignment']='normalized actual phase clock; phase integral closes exactly; duration differences retained, not therapy-shape equivalence'
    assert abs(sum(b['gain_N_s'] for bins in out['force_gain_intervals'].values() for b in bins)-row['comparison']['gain_N_s'])<1e-8
    return out
representatives={r['id']:violation_detail(r) for r in [best,strong]}
put('FORCE_MOTION_TRADEOFFS.json',dict(best=best,strong_lowforce=strong,failure_frequencies=dict(failcounts),representative_details=representatives,accepted_free_execution=executions.get(best['id']),clinical_thresholds=False,global_infeasibility_proven=False))
put('FREE_TRAJECTORY_SEARCH_RESULTS.json',dict(protocol_sha256=sha(S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json'),candidate_count=len(dev),free_candidate_count=sum(np.any(r['candidate'].get('free_parameters',[])) for r in dev),free_positive_step_candidate_count=sum(e['accepted_positive_step_plans']>0 for e in executions.values()),rows=dev,optimizer_status=[json.loads(l) for l in (S/'OPTIMIZER_STATUS.jsonl').read_text().splitlines()] if (S/'OPTIMIZER_STATUS.jsonl').exists() else [],best=best,strong=strong,selection_frozen_unix=selected['unix'],globally_optimal=False,all_true_optimizer_rollouts_in_attempt_ledger=True))
put('FREE_EXECUTION_EVIDENCE.json',executions)
ablations=[r for r in rows if r['candidate'].get('stage')=='DIAGNOSTIC']
put('INTERFACE_ABLATIONS.json',dict(preregistration=load(S/'POST_FREEZE_DIAGNOSTICS_REGISTERED.json'),frozen_best=best,rows=ablations,reselection=False,removed_freedom_cost_delta_N_s={r['candidate']['id']:r['J_F_N_s']-best['J_F_N_s'] for r in ablations},scope='same original plant and seed policy, matched full tasks; ablations diagnose frozen reference freedom, not new held-out selection'))
historical=[]
old=S.parent/'m2_sequential_teacher_oracle_v1'
matches=[('B0_original','baseline_B0_repeat_1'),('NATIVE_SCALAR_18','baseline_NATIVE_SCALAR_18'),('M2_fixed_actions','baseline_M2_fixed_actions'),('C2_pair_1_2','baseline_C2_pair_1_2')]
for new,previous in matches:
    path=old/'reports'/(previous+'_MEASURED.json')
    if not path.exists():continue
    n=allmetrics['development_resume_'+new];o=load(path)
    fields=['J_F_N_s','moment_integral_Nm_s','force_peak_N','moment_peak_Nm','phase_durations','motion','dose','commissioning']
    diff=[k for k in fields if n[k]!=o[k]]
    nd=S/'motion_series'/('development_resume_'+new+'.npz');od=old/'motion_series'/(previous+'.npz')
    dense={}
    if od.exists():
        with np.load(nd) as a,np.load(od) as b:
            dense={k:bool(np.array_equal(a[k],b[k],equal_nan=True) if a[k].dtype.kind in 'fc' else np.array_equal(a[k],b[k])) for k in a.files}
    historical.append(dict(new_id=n['id'],historical_id=previous,source=str(path),historical_source_sha256=sha(path),numeric_fields_exact_equal=not diff,different_fields=diff,dense_exact_equal=dense,historical_cuff_integral_not_cross_condition_ranked=True))
baseline=load(S/'BASELINE_REPRODUCTION.json');baseline['historical_matched_numeric_checks']=historical;put('BASELINE_REPRODUCTION.json',baseline)
val=[r for r in rows if r['id'].startswith(('W1_','W2_'))]
states=[]
for cond in ['W1','W2']:
    path=S/'output'/(cond+'_frozen_best_DATA.json')
    if not path.exists():continue
    d=load(path);arm_states={}
    for arm in ['B0_match','frozen_best']:
        labels=load(S/'output'/(cond+'_'+arm+'_DECISIONS.json'))['rows']
        label=next(r for r in labels if r['phase']=='RETURN' and r.get('native_index')==1)
        with np.load(S/'source/results'/(cond+'_'+arm)/'trace.npz') as z:tstart=float(z['time_s'][z['stage']=='TASK'][0])
        t0=tstart+label['task_s']
        with np.load(S/'motion_series'/(cond+'_'+arm+'.npz')) as z:
            i=np.argmin(abs(z['time_s']-t0));arm_states[arm]=dict(physics_s=t0,sampled_physics_s=float(z['time_s'][i]),true_q_rad=z['true_q_rad'][i].tolist(),true_dq_rad_s=z['true_dq_rad_s'][i].tolist(),native_index=1)
    states.append(dict(condition=cond,**arm_states['frozen_best'],arms=arm_states,initial_complete_fork_snapshot=d['branch_start']))
state_difference=None
if len(states)==2:state_difference=dict(q_max_abs_difference_rad=float(np.max(abs(np.array(states[0]['true_q_rad'])-states[1]['true_q_rad']))),dq_max_abs_difference_rad_s=float(np.max(abs(np.array(states[0]['true_dq_rad_s'])-states[1]['true_dq_rad_s']))))
validation=dict(frozen_selection_unix=selected['unix'],parameter_file_sha256=sha(S/'FROZEN_SELECTION.json'),no_post_validation_tuning=True,rows=val,actual_remaining_state=states,actual_state_difference=state_difference,same_Human_not_different_patients=True,scope='complete matched tasks forked at OUTBOUND0: full frozen OUTBOUND, lawful native-only RETURN0 conditioning prefix in both paired arms, frozen unconsumed RETURN1+ suffix; consumed original RETURN0 action is not independently validated',coverage_amendment=load(S/'VALIDATION_COVERAGE_AMENDMENT.json'),repeat_gate=load(S/'BEST_REPEAT_GATE.json') if (S/'BEST_REPEAT_GATE.json').exists() else None,selected_repeat_gate=load(S/'BEST_SELECTION_REPRODUCTION_GATE.json') if (S/'BEST_SELECTION_REPRODUCTION_GATE.json').exists() else None,host_clock='NOT_RUN',hardware='NOT_RUN')
put('PHYSICAL_FEASIBILITY_VALIDATION.json',validation)
put('VALIDATION_RESULTS.json',validation)
for name in ['BEST_REPEAT_GATE.json','BEST_SELECTION_REPRODUCTION_GATE.json']:
    if (S/name).exists():assert load(S/name)['status']=='PASS',name
bestfree=bool(np.any(best['candidate'].get('free_parameters',[])))
native=next(r for r in dev if r['candidate']['id']=='NATIVE_SCALAR_18')
gain=best['comparison']['gain_percent'];newgain=gain-native['comparison']['gain_percent']
qual=[r for r in dev if np.any(r['candidate'].get('free_parameters',[])) and r['comparison']['acceptance_pass']]
decision='A' if gain>=2 and bestfree else 'C'
if sum(e['accepted_positive_step_plans']>0 for e in executions.values())==0:decision='D'
put('FINAL_DECISION.json',dict(direction=decision,best_gain_percent=gain,extra_gain_over_native_percentage_points=newgain,at_least_2_percent=gain>=2,at_least_5_percent=gain>=5,best_has_free_parameters=bestfree,feasible_free_candidates=len(qual),Level1_best=best['comparison']['acceptance_pass'],minimum_interface_extension_supported=decision=='A',future_teacher='nominal-condition offline teacher only; prefix validation scope and failures must be carried' if qual else 'no better generalized teacher promoted',no_next_package_started=True))
nativegap=f'''# 接口缺口与物理证据\n\n最好完整运动 `{best['id']}`，同条件 B 下降 {gain:.6f}%，相对 NATIVE_SCALAR_18 增加 {newgain:.6f} 个百分点。自由参数非零：{bestfree}。\n\n原 B 只有请求处反对称目标进度 delta；本轮研究意图另有共同进度及 hip/knee 独立路点通过速度。二者都由原 quintic 连续实现，故接口表达区别确实存在。实际 accepted positive-step 数据见 FREE_EXECUTION_EVIDENCE.json，不能凭参数名称当执行证据。\n\n最低力参考下降 {strong['comparison']['gain_percent']:.6f}%，资格 {strong['comparison']['acceptance_pass']}；最严重约束是 {strong['constraints']['worst_requirement']}，比值 {strong['constraints']['worst_ratio']:.6f}。未将它升级为合格 teacher。\n\n本轮覆盖10维低维参考族，固定原通过速度公式的乘性修饰和采样路点位置。尚未覆盖任意连续时间样条、独立加速度边界、整段速度分布或全维合法机器人输入优化。优化预算终止不等于收敛或全局无解。\n\n{'支持进一步研究最小共同进度/独立通过速度意图接口，并保留所有原认证。该扩展只在隔离包内。' if decision=='A' else '尚无足够性能证据支持正式 B 增加接口；表达差异本身不是价值证明。'}本轮没有正式B修改、host-clock资格、真机或学习。\n'''
(S/'INTERFACE_GAP_ANALYSIS.md').write_text(nativegap)
(S/'NEXT_RESEARCH_DECISION.md').write_text(f'''# 唯一下一主方向：{decision}\n\n{'找到明显更好的物理可行轨迹，研究最小B接口扩展。' if decision=='A' else '更自由优化尚未获得可信物理执行证据，应先解决执行/建模问题。' if decision=='D' else '运动与交互力之间的局部权衡仍强，进一步研究实际动力学机制。'}\n\n本轮最佳 {gain:.6f}%；≥2%={gain>=2}，≥5%={gain>=5}。冻结规则没有变化。有限搜索不证明物理全局无解；参考覆盖和优化收敛仍有明确限制。只推荐上述一个方向，不自动启动下一包，不训练Q。\n''')
tables=[]
for r in [next(r for r in dev if r['candidate']['id']=='B0_original'),native,best,strong]:
    tables.append(f"|{r['id']}|{r['J_F_N_s']:.6f}|{r['comparison']['gain_percent']:.6f}|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|{r['constraints']['worst_requirement']} {r['constraints']['worst_ratio']:.6f}|")
attempts=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in attempts if r['event']=='START']
vbest=[r for r in val if r['candidate']['id']=='frozen_best']
vp=sum(r['comparison']['acceptance_pass'] for r in vbest)
phase=best['comparison']['phase_J_F_delta_N_s']
report=f'''# iHEAR Lab — Free Trajectory Optimization & Physical Feasibility v1\n\n本轮完成原完整机器人—人体动力学下的隔离自由参考研究。最好完整运动 `{best['id']}` 的 J_F={best['J_F_N_s']:.6f} N·s，相对同条件 B 的 {base['J_F_N_s']:.6f} N·s降低 **{gain:.6f}%**，全部冻结主条件 **{'PASS' if best['comparison']['acceptance_pass'] else 'FAIL'}**。≥2%：{'达到' if gain>=2 else '未达到'}；≥5%：{'达到' if gain>=5 else '未达到'}。唯一主方向 **{decision}**，不是全局最优结论。\n\n|完整方案|J_F N·s|降低%|冻结任务/运动资格|最严重约束比|\n|---|---:|---:|---|---|\n'''+ '\n'.join(tables)+f'''\n\n## 本轮新自由度与真实执行\n\nOUTBOUND/RETURN独立优化共同进度、差分进度的常数与倾斜，以及hip/knee独立通过速度，共10维。请求时产生位姿/dq意图，原quintic、governor、40ms bridge、100ms lifecycle、current-state admission和机器人六轴力矩闭环执行。数学参考、实际reference receipt、真实人体q/dq分开记录；没有qpos/qvel回放、人体主动力矩、模型变化或接触绕过。该族是连续函数定义的分段quintic参考，不能冒称任意时间样条或原生PWL逐步连续执行。详细权限见 PHYSICAL_ACTION_SPACE.md。\n\n扩展零调整的完整trace、76,121个TASK人体原生样本、全receipt/torque复现PASS；重新生成父与之前B完整数值一致。所有历史同条件复现范围和字节证据见 BASELINE_REPRODUCTION.json；旧E指标仅作设计起点来源，不混入排序。\n\n## 最好运动、收益分解与资格\n\n最好参数：`{json.dumps(best['candidate'].get('free_parameters'),ensure_ascii=False)}`；native种子 `{best['candidate'].get('seed_family')}`。新增自由参数是否非零：{bestfree}。通过所有真实hip/knee速度max/p95/RMS、加速度max/p95/RMS、jerk p95/RMS、excursion±0.5°、累计角位移±5%、端点/phase boundary±0.5°、总及阶段时间±0.1s、moment integral≤25%、tracking增量≤0.5°、force/moment peak补偿与原absolute安全。jerk max和phase shape仅诊断；这些是研究规则，不是临床舒适阈值。每项绝对值与比值完整保留，不用过滤显示曲线作为验收。\n\nOUTBOUND减少 {-phase['OUTBOUND']:.6f} N·s；HOLD减少 {-phase['HOLD']:.6f} N·s；RETURN减少 {-phase['RETURN']:.6f} N·s。按完整TASK原左积分、实际phase边界分配，闭合误差门限1e-8。不同条件分母不直接拼接。\n\n本轮最佳主要声明为 LEVEL1（完整原动力学、安全与运动条件）。{'它具有非零扩展参数，不能声称原生 B 已实现该收益。' if bestfree else '最佳仍使用原合法native residual，原生receipt证据可支持LEVEL2科学执行，但不代表host-clock。'}LEVEL3和真机均未开展。两个未用于选参的合法RETURN前缀条件，冻结remaining suffix资格 {vp}/{len(vbest)}；实际状态差和完整配对收益见 PHYSICAL_FEASIBILITY_VALIDATION.json。它们是同一Human，且前缀消耗R0，不冒称原完整策略跨患者或全串独立验证。参数冻结后未再修复或重新选择。\n\n## 力与运动权衡\n\n最低力代表 `{strong['id']}`，下降 {strong['comparison']['gain_percent']:.6f}%，运动失败条件 `{strong['comparison']['failed_requirements']}`。低力参考的实际暴露持续时间、phase负担、接触与控制输入见 FORCE_MOTION_TRADEOFFS.json。常见限制 `{dict(failcounts)}`。优化器同时接收完整力目标与实测各项约束，strong seed修复不能把超标方案升级为teacher。\n\n新自由运动合格数 {len(qual)}，实际positive-step自由运动候选数 {sum(e['accepted_positive_step_plans']>0 for e in executions.values())}。有限预算下COBYLA status和实际评估次数原样保存；不能把maxiter/budget终止说成收敛。未覆盖的更高维连续参考和底层输入优化仍是局限，不能判断真实物理最优只有1%–2%。\n\n## Teacher与下一决定\n\n{'本轮找到明显更好的原动力学可行参考，可作为有限条件离线teacher；最小接口变化需进一步以冻结验证范围约束，不直接合并正式B。' if decision=='A' else '没有满足显著性能目标的新teacher升级证据。合格运动可以作为有限条件离线参照，但不能把strong motion-FAIL或仅小幅收益当最终高质量teacher。'}下一主方向仅为 {decision}，理由见 NEXT_RESEARCH_DECISION.md；没有训练Q、Neural Q、G/P或在线个体化。\n\n## 预算、失败与保护\n\n新增attempt启动 {len(starts)}/96，所有冷父、完整fork、partial、optimizer真实评估、重复及失败均在START分母。首次归档因自有结果列表覆盖原参考rows导致KeyError，物理零调整完整且父未污染；保留错误和partial父，用原live snapshot与完整trace恢复记录，修正命名后新父精确复现。没有重置计数或墙钟。\n\n轻量归档只删除本新包已完成全receipt/安全/积分审计的普通生成raw；完整trace、dense运动、参数、指标和关键原始receipt保留，COMPACTION.jsonl记录每次原SHA/bytes。没有复制全历史或Windows镜像。原源码/权重、Linux两处Git状态、退出和空间见 PACKAGE_VERIFICATION.json；保护范围不是全部历史字节扫描。\n\n完成报告和核验后 STOP，不自动启动后续。\n'''
(S/'REPORT.md').write_text(report)
print(json.dumps(dict(best=best['id'],gain_percent=gain,direction=decision,attempts=len(starts),validation_pass=vp,validation_count=len(vbest))))
