"""Build Chinese evidence reports after fixed validation; no new physics."""
from pathlib import Path
import os,json,sys,time,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name

def read(n):return json.loads((P/n).read_text())
def write(n,t):(P/n).write_text(t+'\n')
def put(n,x):write(n,json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False))
def fmt(x,d=6):return f'{x:.{d}f}'
def pair(x):return ' / '.join(fmt(v) for v in x)
res=read('EXPERIMENT_RESULTS.json');groups=res['groups'];audit=read('audit/EXPANDED_PREFIX_AUDIT.json');timeaudit=read('audit/EXPANDED_EXECUTION_TIME_AUDIT.json');intervention=read('audit/INTERVENTION_EXECUTION_AUDIT.json');plan=read('RUN_PLAN.json');account=read('ATTEMPT_ACCOUNTING.json');by={g['group']:{r['arm']:r for r in g['rows']} for g in groups};conds={};ntpass=0;ngain=0
for g in groups:
 name=g['group'];d=by[name];t=d['T'];npass=bool(t['motion']['acceptance_pass']);ntpass+=npass;gain=t['motion']['gain_percent'];ngain+=gain>=1.;full=npass and t['absolute_safety'] and t['task']=='PASS' and t['receipt']=='PASS'
 ev=next(r for r in intervention['rows'] if r['group']==name)
 conds[name]=dict(complete=True,condition=g['condition'],pair_full_live_state=g['pair_gate']['status'],parent_exact_B=g['parent_gate']['status'],independent_native_arithmetic=g['independent_raw']['status'],prefix_execution='PASS',frozen_T_one_accepted_intervention=ev['one_accepted_final_intervention'],frozen_18D_motion_pass=d['E']['motion']['acceptance_pass'],T_motion_pass=npass,T_complete_qualification_pass=full,T_gain_percent=gain,T_delta_J_F_vs_E_N_s=t['J_F_N_s']-d['E']['J_F_N_s'],T_force_advantage_retained=gain>=1.,T_failed_requirements=t['motion']['failed_requirements'],T_absolute_safety=t['absolute_safety'],T_task=t['task'],T_causal_receipt=t['receipt'],repeat='PASS' if g['repeat_gate'] and g['repeat_gate']['status']=='PASS' else 'NOT_RUN',full_parent_hash=g['pair_gate']['full_hash'],J_F_N_s={a:d[a]['J_F_N_s'] for a in ['B','E','T']})
allpass=all(c['T_complete_qualification_pass'] and c['T_force_advantage_retained'] for c in conds.values())
status='ALL_NEW_PREFIX_T_QUALIFIED_FORCE_RETAINED' if allpass else 'FROZEN_T_STATE_FAILURE_OR_FORCE_INSTABILITY'
validation=dict(status='COMPLETE',scientific_status=status,contract_audit='PASS',mathematical_interface='PASS',conditions=conds,new_prefix_pairs=len(groups),new_prefix_T_motion_pass=ntpass,new_prefix_T_complete_qualification_pass=sum(c['T_complete_qualification_pass'] for c in conds.values()),new_prefix_T_motion_pass_rate=ntpass/len(groups),new_prefix_T_force_retained=ngain,repeats_excluded_from_denominator=True,same_Human=True,no_primary_reselection=True,no_threshold_changes=True,T_factor=1.5,T_source_byte_identity_previous=True,physical_level='PHYSICAL_LEVEL1',clock='SCIENTIFIC_SIMULATION',historical_results_not_relabelled=True,independent_audit='Separate numerical implementation/source path under one agent; not an independent person/agent review',LEVEL2=False,LEVEL3=False,host_strict_R2_FAST_new_qualification=False,hardware=False,clinical=False)
put('VALIDATION_RESULTS.json',validation)
# Generalized diagnoses cover failures in E and T, with whole-task gates unchanged.
lines=['# 运动失败与状态依赖诊断','',f'本轮新状态T motion通过{ntpass}/{len(groups)}。重复不增加分母。原18D的失败逐项保留。','', '|条件|臂|motion|失败项|完整髋/膝amax °/s²|膝峰task s / phase|','|---|---|---|---|---|---|']
for a in audit['groups']:
 for r in a['diagnosis']:
  m=by[a['condition']][r['arm']]['measured'];pk=r['full_acceleration_peaks']['knee'];lines.append(f"|{a['condition']}|{r['arm']}|{'PASS' if r['motion_pass'] else 'FAIL'}|{', '.join(r['failed_requirements']) or '—'}|{pair(m['motion']['raw']['full']['acceleration_deg_s2']['max_abs'])}|{pk['task_s']:.5f} / {pk['phase']}|")
lines+=['','每个失败joint、完整metric值/匹配B比值/1.10门、峰时间、各phase贡献与超限时间见audit/*_PREFIX_AND_FAILURE_AUDIT.json。p95和RMS是全任务统计，phase比值只用于定位，不能改成新的phase门。jerk max保留为诊断项。','']
for a in audit['groups']:
 lines+=['## '+a['condition'],'']
 ev=next(r for r in intervention['rows'] if r['group']==a['condition']);event=ev['events'][0];ts=event['splice']
 for r in a['diagnosis']:
  if r['arm'] not in ['E','T']:continue
  if not r['failure_details']:lines.append(f"{r['arm']}：冻结motion/fairness全部通过。")
  for f in r['failure_details']:
   if 'joint' in f:lines.append(f"{r['arm']}：{f['joint']} {f['requirement']}，候选={f['candidate']:.9f}，B={f['B']:.9f}，比值={f['ratio']:.9f}>1.10；实际峰{f['peak']['task_s']:.5f}s（{f['peak']['phase']}），signed={f['peak']['signed_value']:.9f}。")
 lines.append(f"T/E此前schedule和splice前q/dq、torque、force一致。仅一个ACCEPTED末段duration干预；suffix E={event['E_schedule']['duration_s']:.3f}s，T={event['T_schedule']['duration_s']:.3f}s。具体request/activation/splice/receipt/native连接在对应NEW_TIME_EVIDENCE.json。")
 lines.append('')
if ntpass==len(groups):lines+=['','本轮未观察到T失败，因此没有可据以确认的T失败状态依赖。历史N2/U1与本轮两个prefix的结果支持该有限邻域的末段修复；它不证明不存在更远状态的失败。原18D若在多个状态出现相同膝末段加速度失败，只说明已测条件中的可重复现象。','', '固定T不能改变splice以前已经发生的运动峰；修复后完整任务峰若转移到前段，是后续扩大状态验证应关注的边界。不得据此自动为各状态增加特殊倍率。']
else:lines+=['','T失败应由上述joint/phase/metric与执行时间线定义。两种新prefix不足以建立稳定状态依赖模型，不进行按状态调倍率或重选方案。']
write('MOTION_FAILURE_DIAGNOSIS.md','\n'.join(lines))
nextstep='扩大合法状态验证' if allpass else ('设计状态条件校准的独立事前协议' if ntpass<len(groups) else '扩大合法状态验证并检验力收益稳定性')
write('NEXT_RESEARCH_DECISION.md',f'''# 下一步研究决定

本轮状态：{status}。

唯一建议下一步：**{nextstep}**。本轮不执行下一步，不开始18D+Waypoint或Q-learning。

T=1.5与18D参数/门槛继续冻结。本轮有限同Human状态可作为后续研究的保守比较基线；尚不足将T当作更广状态或跨患者已验证基线，也不足据此直接开始第二轮优化。应先在独立登记、完整匹配的更多合法prefix中检验适用边界，特别是末段外运动峰和低速/高通过速度的不同入末段状态。

只有更广验证明确通过后，才另行决定18D+Waypoint搜索的目标、约束和预算。失败时先区分末段参考失败、既有前段负担和匹配B门差异；不得把新校准冒充冻结T验证。''')
# Full report, with requested six answers and all metrics mapped to raw.
report=['# iHEAR Lab — 冻结18D末段修复：扩展prefix验证 v1','',f'**时间合同已解释；新合法prefix中冻结T motion通过{ntpass}/{len(groups)}，保留降力{ngain}/{len(groups)}。** 本轮无调参、无倍率搜索。','', '## 六个明确答案','', '1. **duration与phase/task时长已解释。** suffix真实延长，而原MATCHED非HOLD phase至少9s的执行规则不变。延长占用原终点TRACK等待区间；N2为0.220→0.330s，实际参考6.830–7.050→6.830–7.160s，终点carry1.955→1.845s。没有BRAKE切换、progress延迟或任务缩短。详见T_EXECUTION_CONTRACT_AUDIT.md。', f'2. **新状态motion通过率：{ntpass}/{len(groups)}（{100*ntpass/len(groups):.1f}%）。** 只有V1/V2计入分母；N2/U1及全部重复均为历史/重复证据。两状态均为同一Human的合法prefix后remaining-suffix验证。', '3. **每条件内部配对的力收益见下表。** 完整积分包含共同prefix；同时报告T对匹配B降力和T−18D，不把不同状态绝对J_F相互比较。', '4. **状态依赖：** '+('本轮无T失败，无法建立稳定失败状态依赖；也不能据此排除未测状态失败。' if ntpass==len(groups) else '存在T失败，joint/phase/metric已定位；当前样本不足以确认稳定状态依赖，不自动加特殊参数。'), '5. **保守基线：** '+('可在本轮及历史已测的同Human有限适用域内作为冻结研究比较基线；尚不足升级为广泛有效基线或直接启动第二轮优化。' if allpass else '当前失败/力收益不稳定阻止其成为覆盖所有新状态的保守基线。'), f'6. **唯一下一步：{nextstep}。** 本轮STOP，不自动开始18D+Waypoint或Q-learning。', '', '## 完整配对结果','', '|条件/臂|完整J_F N·s|对匹配B降力 %|T/臂−18D N·s|motion/fairness|task/安全/causal|','|---|---:|---:|---:|---|---|']
for g in groups:
 d=by[g['group']]
 for r in g['rows']:
  report.append(f"|{r['id']}|{r['J_F_N_s']:.9f}|{r['motion']['gain_percent']:.6f}|{r['J_F_N_s']-d['E']['J_F_N_s']:+.9f}|{'PASS' if r['motion']['acceptance_pass'] else 'FAIL: '+','.join(r['motion']['failed_requirements'])}|{r['task']}/{'PASS' if r['absolute_safety'] else 'FAIL'}/{r['receipt']}|")
report+=['','T相对18D的微小J_F变化只用于确认收益保留，不能当作额外降力突破。匹配B自比motion PASS是参照，task/安全另审。','', '|条件/臂|OUTBOUND JF|HOLD JF|RETURN JF|OUT/HOLD/RETURN s|完整task s|','|---|---:|---:|---:|---|---:|']
for g in groups:
 for r in g['rows']:
  m=r['measured'];ph=m['phase_cost']['phases'];report.append(f"|{r['id']}|{ph['OUTBOUND']['J_F_N_s']:.9f}|{ph['HOLD']['J_F_N_s']:.9f}|{ph['RETURN']['J_F_N_s']:.9f}|"+'/'.join(f"{m['phase_durations'][p]:.6f}" for p in ['OUTBOUND','HOLD','RETURN'])+f"|{m['dose']['duration_s']:.6f}|")
report+=['','积分为原5ms force左积分并按真实phase边界切分；完整与phase闭合经独立实现重算，native导数来自0.25ms真实qvel，非数学参考。','', '## 运动、tracking与补偿代价','', '|条件/臂|vmax hip/knee °/s|amax hip/knee °/s²|jerk RMS hip/knee °/s³|tracking RMS hip/knee °|moment Nm·s|clearance m|force/moment peak|','|---|---|---|---|---|---:|---:|---|']
for g in groups:
 for r in g['rows']:
  if 'repeat' in r['arm']:continue
  m=r['measured'];f=m['motion']['raw']['full'];c=m['clearance'];clear=float(c) if isinstance(c,(int,float)) else None
  if clear is None:
   # Native physical clearance is stored under the measured audit.
   clear=m['native_physical_audit'].get('minimum_true_physical_clearance_m',None)
  report.append(f"|{r['id']}|{pair(f['velocity_deg_s']['max_abs'])}|{pair(f['acceleration_deg_s2']['max_abs'])}|{pair(f['jerk_deg_s3']['rms'])}|{pair(m['tracking_RMS_deg'])}|{m['moment_integral_Nm_s']:.6f}|{str(c)}|{m['force_peak_N']:.6f} N / {m['moment_peak_Nm']:.6f} Nm|")
report+=['','所有velocity/acceleration/jerk完整与phase max/p95/RMS、jerk max诊断、ROM excursion、cumulative travel、endpoint与phase边界dose、tracking、force/moment peak及完整native安全逐项指标均在EXPERIMENT_RESULTS.json的measured和delta_vs_B/delta_vs_frozen_18D。motion比值1.10、dose±5%、边界0.5°、duration0.1s、moment integral1.25及其余原门完全保留；不宣称多指标Pareto优势。','', '## 合法状态、前史与执行合同','']
for g in groups:
 a=next(x for x in audit['groups'] if x['condition']==g['group']);p=g['condition']['prefix'];report.append(f"- {g['group']}：seed={g['condition']['seed']}，prefix={json.dumps(p)}；fork task={a['fork_task_s']:.6f}s，完整父hash={a['full_live_parent_hash']}，native hash={a['native_hash']}。共同prefix J_F={a['prefix'][0]['task_prefix_J_F_N_s']:.9f}N·s，真实prefix native steps={a['prefix'][0]['prefix_native_steps_before_fork']}。")
report+=['','每个新状态来自真实cold commissioning及合法prefix，随后完整地址空间os.fork，未直接设置或回放Human qpos/qvel。B/E/T的fork restored hash、fork前完整trace、prefix执行receipt及父不变检查全部精确通过，完整父结束与B raw逐字段一致。两新native状态彼此不同，也不同于N2/U1；数值差仅用于evaluation，不进入控制。OUTBOUND index0已被prefix消费，18D/T从index1开始比较remaining行为，不能称完整18D整串从未见初态执行。','', 'T源码与上一轮字节一致，倍率1.5，原18D参数/RETURN plateau与motion协议字节一致。仅一个最终OUTBOUND干预被原certificate/mechanics/current admission和执行链接受；所有此前schedule、参考及真实运动在splice前一致。每个T真实duration、request、activation、splice、reference receipt/native归属和carry详见audit/EXPANDED_EXECUTION_TIME_AUDIT.json与audit/INTERVENTION_EXECUTION_AUDIT.json。','', '## 证据层级与未解决问题','', '- **本轮PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION**：V1/V2各匹配B/18D/T，合格后T确定性重复。重复证明确定性，不是新状态。', '- **历史证据**：原B JF=1438.613498467、开发18D=1400.697221153（降力2.635613%）；N2/U1有限合法prefix与重复原样保留，原18D motion FAIL及旧host/strict/R2/FAST资格结果不改。', '- **数学证据**：原fixed-duration接口重建、连续几何certificate与mechanics；不能替代真实Human运动或native安全。', '- **独立重算**：单agent下独立算术源码路径，不导入controller/plant；不是独立人类或第二agent审计。', '- **未解决**：更广prefix/通过速度和更远状态的适用域、具体FAST/allocator/contact中介、跨患者、host实时/LEVEL2/LEVEL3与硬件/临床资格均未建立。历史receipt没有直接plan_request_id，已有明确间接时序/参考/torque/步数证据，不伪造字段。','', '## 预算、保护与关闭','', f"T0=北京时间2026-10-17 14:47:58；硬截止18:47:58；18:02:58后禁止新START。START/END={account['physical_START']}/{account['physical_END']}，上限30；新增native steps={account['actual_new_native_steps']}。父、fork、失败与重复全部计入；无partial。提前取得两条件有限结论后停止，不为填满预算追加实验。", '', '新修改仅在本版本Side Study与对应Windows审阅镜像。起始Git、旧历史metadata/SHA、冻结execution manifest、owned进程退出及最终计数见PACKAGE_VERIFICATION.json。无Git commit/push/merge/reset/stash/clean/branch切换。正式B、plant、安全执行链和历史证据均保持。','', 'canonical：'+str(P),'Windows审阅镜像：'+str(L),'', '**STOP。**']
timelines=['|新条件/臂|suffix时长 s|splice task s|suffix结束 task s|终点TRACK carry s|','|---|---:|---:|---:|---:|']
for ev in timeaudit['new_rows']:
 timelines.append(f"|{ev['id']}|{ev['suffix_duration_s']:.3f}|{ev['splice_task_s']:.3f}|{ev['suffix_end_task_s']:.3f}|{ev['endpoint_carry_s']:.3f}|")
timelines+=['','冻结的是1.5倍率及5ms向上对齐规则，不是统一0.330s。V1原0.225s→0.340s，V2原0.215s→0.325s；差异由各状态原合法duration及同一冻结取整规则产生，未重选倍率。','']
index=report.index('## 证据层级与未解决问题');report[index:index]=timelines
write('REPORT.md','\n'.join(report))
put('STATE.json',dict(phase='VALIDATION_COMPLETE_AWAITING_PROTECTION_SEAL',scientific_status=status,physics_starts=account['physical_START'],owned_pids=[],next_action='Finish independent protection verification; mirror reports; STOP',updated_unix=time.time()))
print('REPORTS_READY',status,'T motion',ntpass,len(groups),flush=True)
