"""Describe all frozen pairs, preserve historical failures, and decide no new search."""
from pathlib import Path
import os,json,time,hashlib,collections,sys
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()] if (P/'ATTEMPTS.jsonl').exists() else []
starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];rows=[]
for s in starts:
 ident=s['id'];end=next((r for r in ends if r['id']==ident),None);f=P/'output'/(ident+'_DATA.json');partial=P/'output'/(ident+'_PARTIAL_COMPUTE.json');data=json.loads(f.read_text()) if f.exists() else {};metric=data.get('metric',{});pp=json.loads(partial.read_text()) if partial.exists() else {}
 err=P/'reports'/(ident+'_ERROR.json')
 rows.append(dict(id=ident,kind=s.get('kind'),START_unix=s['unix'],END_unix=None if end is None else end['unix'],wall_s=None if end is None else end['unix']-s['unix'],returncode=None if end is None else end['returncode'],joined=False if end is None else end['joined'],actual_new_native_steps=metric.get('actual_new_native_physics_steps',pp.get('actual_new_native_physics_steps')),archived_native_steps=metric.get('native_physics_steps',pp.get('native_physics_steps')),partial=not bool(metric.get('task_valid')),task_complete=bool(metric.get('task_valid')),failure_reason=json.loads(err.read_text()) if err.exists() else None,source_manifest_sha256=s.get('code_manifest_sha256'),snapshot_hash=s.get('snapshot_hash')))
engineering=read('audit/ENGINEERING_EVENTS.json')['rows']
ac=dict(physical_START=len(starts),physical_END=len(ends),cap=40,all_attempts_accounted=collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows),native_steps_exact=all(r['actual_new_native_steps'] is not None for r in rows),rows=rows,preSTART_engineering_failures=[r for r in engineering if r['stage']=='before physical START'],engineering_events=engineering,counts_include_all_parents_forks_failures_repeats=True)
put('ATTEMPT_ACCOUNTING.json',ac)
historical=read('provenance/ihear_overnight_research_retrospective_v1__VALIDATION_RESULTS.json')
histrows=[r for r in historical['rows'] if r.get('arm')=='frozen_best']
vr=[]
for c in read('RUN_PLAN.json')['validation_conditions']:
 g=c['name'];f=P/(g+'_RESULTS.json')
 if not f.exists():continue
 r=read(g+'_RESULTS.json')['rows']
 if len(r)!=2:continue
 for armrow in r:
  armrow['complete_task_duration_s']=sum(armrow['phase_durations'].values())
  armrow['native_motion_span_duration_s']=read(armrow['metrics_path'])['dose']['duration_s']
 b,a=r;comp=a['motion'];gate=read(g+'_PAIR_GATE.json');context=read('audit/'+g+'_FORK_CONTEXT.json');diag=read('derived/'+g+'_FAILURE_DIAGNOSIS.json') if (P/'derived'/(g+'_FAILURE_DIAGNOSIS.json')).exists() else None
 with np.load(P/'motion_series'/(g+'_B.npz')) as z:
  ii=int(np.argmin(abs(z['time_s']-context['physical_s'])));assert abs(z['time_s'][ii]-context['physical_s'])<1e-8
  realstate=dict(physics_s=float(z['time_s'][ii]),true_q_rad=z['true_q_rad'][ii].tolist(),true_dq_rad_s=z['true_dq_rad_s'][ii].tolist(),role='evaluation-only state diversity proof, never used to choose reference')
 prefixline=read('reports/'+g+'_B_EXECUTED_RESIDUAL_RECEIPTS.json');appliedprefix=[r for r in prefixline['rows'] if r['physically_executed_nonzero'] and r['first_execution_physics_s']<context['physical_s']-1e-9]
 assert appliedprefix,'PREFIX_MUST_ACTUALLY_EXECUTE'
 vr.append(dict(condition=g,source=c,complete_pair=True,B=b,original_frozen_18D=a,gain_percent=comp['gain_percent'],gain_N_s=comp['gain_N_s'],motion_pass=comp['acceptance_pass'],failed_requirements=comp['failed_requirements'],absolute_safety_pass=b['absolute_safety'] and a['absolute_safety'],receipt_pass=b['receipt']=='PASS' and a['receipt']=='PASS',full_pair_state_equal=gate['status']=='PASS',pair_native_hash=gate['native_hash'],pair_full_hash=gate['full_hash'],physical_fork_time_s=context['physical_s'],task_fork_time_s=context['task_s'],consumed_slots=context['count'],actual_human_state_at_fork=realstate,actual_nonzero_prefix_decisions=len(appliedprefix),diagnosis=diag))
validation=dict(evidence_level='PHYSICAL_LEVEL1',new_pairs=len(vr),complete_pairs=len(vr),positive_force_gain=sum(r['gain_percent']>0 for r in vr),motion_PASS=sum(r['motion_pass'] for r in vr),safety_PASS=sum(r['absolute_safety_pass'] for r in vr),receipt_PASS=sum(r['receipt_pass'] for r in vr),joint_qualification_PASS=sum(r['gain_percent']>0 and r['motion_pass'] and r['absolute_safety_pass'] and r['receipt_pass'] for r in vr),rows=vr,historical_primary_motion=dict(PASS=0,denominator=4,rows=histrows,classification='HISTORICAL_REPORTED retained byte-exact in provenance'),same_Human=True,new_patients=0,no_reselection=True,no_parameter_update=True,independent_state_rule='distinct actually evolved native states, not seeds or repeated full-state hashes',scope='remaining frozen policy after shared native OUTBOUND0 prefix; full-task J_F includes identical prefix. Does not evaluate original 18D OUTBOUND0 from an unseen commissioning state.')
assert len({r['pair_native_hash'] for r in vr})==len(vr),'DO_NOT_COUNT_DUPLICATE_STATE_AS_NEW'
differences=[]
for i,r in enumerate(vr):
 for s in vr[:i]:
  qdiff=float(np.max(abs(np.asarray(r['actual_human_state_at_fork']['true_q_rad'])-s['actual_human_state_at_fork']['true_q_rad'])));vdiff=float(np.max(abs(np.asarray(r['actual_human_state_at_fork']['true_dq_rad_s'])-s['actual_human_state_at_fork']['true_dq_rad_s'])))
  assert max(qdiff,vdiff)>1e-10,'DUPLICATE_PHYSICAL_STATE'
  differences.append(dict(a=r['condition'],b=s['condition'],max_q_difference_rad=qdiff,max_dq_difference_rad_s=vdiff))
validation['pairwise_real_Human_state_differences']=differences
failure_counts=dict(collections.Counter(req for r in vr for req in r['failed_requirements']))
validation['failure_requirement_counts']=failure_counts
put('VALIDATION_RESULTS.json',validation)
repro=read('BASELINE_REPRODUCTION.json')
passed=repro['status']=='PASS'
decision='B' if any(not r['motion_pass'] for r in vr) else 'C' if any(r['gain_percent']<=0 for r in vr) else 'A_LIMITED_SCOPE' if vr else 'D' if not passed else 'NO_VALIDATION'
if decision=='B':
 conclusion='开发复现资格成立，但冻结18D尚不具备跨合法状态的可靠motion资格。固定参数直接迁移不能被称为通用优化基线。'
 nextstep='优先开展独立版本、事前冻结的保守状态条件准入/有界校准研究；本轮仅提出合同，不实现、不调参。先确认能用因果状态/模型特征预测风险，再用新未见prefix验证；状态重优化须独立标识，不能冒充原18D泛化。'
elif decision=='A_LIMITED_SCOPE':
 conclusion='本轮测试范围内固定18D保留收益并通过原motion/safety，但历史0/4失败仍限制总体可迁移性；仅可冻结为本明确范围的可复现优化基线。'
 nextstep='先厘清历史失败与本轮通过的状态边界并建立保守适用域；其后才另立18D+Waypoint联合优化合同。'
elif decision=='C':
 conclusion='完整降力未稳定保留；冻结参数不具备直接迁移证据。'
 nextstep='优先分析状态依赖并另立事前冻结的适用域/有界校准合同；不进行本轮重优化。'
else:
 conclusion='复现或验证合同尚未完整通过，不能升级基线资格。'
 nextstep='先修复最小复现/证据闭包问题；不启动新状态physics或下一研究包。'
put('NEXT_RESEARCH_DECISION.json',dict(branch=decision,conclusion=conclusion,exactly_one_recommended_next_step=nextstep,automatic_next_study=False))
put('BASELINE_CONTRACT.json',dict(status='REPRODUCIBLE_DEVELOPMENT_ONLY' if passed and decision=='B' else 'REPRODUCIBLE_LIMITED_TEST_DOMAIN' if passed else 'NOT_QUALIFIED',identity='original retrospective best primary, never reselected',candidate_file='FROZEN_18D.json',candidate_sha256=hashlib.sha256((P/'FROZEN_18D.json').read_bytes()).hexdigest(),execution_manifest_sha256=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest(),motion_protocol_sha256=hashlib.sha256((P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest(),native_plateaus_required=True,original_B_execution_required=True,development_case='high_rom_nominal_sync_120_v1',development_seed=2026101303,validated_full_initial_condition='same historical commissioning/TASK entry reproduced by complete live parent; do not infer general initial-state domain',full_task_only=True,historical_motion='0/4',new_motion=f"{validation['motion_PASS']}/{len(vr)}",new_prefix_results_are_remaining_policy_only=True,automatic_state_filter_available=False,formal_Native_LEVEL2=False,host_clock_LEVEL3=False,patients_validated=0,waypoint_smoothing_included=False,learning=False))
lines=['# 下一研究决策', '',f'条件分支：{decision}。{conclusion}', '',nextstep,'','任何状态筛选器必须只用原B允许的因果观测/估计与phase/剩余时间，不能读取真实Human状态或验证标签；拒绝时回原B/carry/fallback。诊断得到的特征仅是假设，不能凭这4个结果宣称筛选器有效。若需要改参数，应另存候选、版本和开发集，并冻结后使用新状态验证；不得放宽motion门限。','', '本轮不训练RL/Q/Neural Q、不叠加Waypoint、不启动大规模优化或下一包。历史0/4原样保留。']
(P/'NEXT_RESEARCH_DECISION.md').write_text('\n'.join(lines)+'\n')
if passed:
 b,a=repro['rows'];table='\n'.join(f"|{ph}|{b['phase_cost']['phases'][ph]['J_F_N_s']:.12f}|{a['phase_cost']['phases'][ph]['J_F_N_s']:.12f}|" for ph in ['OUTBOUND','HOLD','RETURN'])
 audit=f'''# 本轮复现审计

结果PASS，证据为本轮新PHYSICAL_LEVEL1 scientific simulation，不是历史报告替代。B={b['J_F_N_s']:.12f}，原冻结18D={a['J_F_N_s']:.12f} N·s，降力{a['motion']['gain_percent']:.9f}%。两者完整task、motion/fairness、原绝对安全和scientific receipt/ownership均PASS。

完整TASK时长B/18D={sum(b['phase_durations'].values()):.9f}/{sum(a['phase_durations'].values()):.9f} s；phase clock时长均为OUTBOUND 9.005、HOLD 1.020、RETURN 9.005 s。合同HOLD dwell仍为原0.5s，实际phase时长不是另改的dwell。

|phase|B N·s|18D N·s|
|---|---:|---:|
{table}

所有历史trace字段精确一致；每对116320 native行和5817 receipts的物理/参考/来源字段精确一致。wall profiling/host timestamps不是scientific物理同一性字段。父/两个完整live fork保存restored hash，父在每臂后不变；父继续完成原B且与B子臂相同。无Human qpos/qvel直接设定或真实状态回放。

独立重算见audit/INDEPENDENT_reproduction.json：从本轮trace重算原5ms左积分和phase精确裁剪；从原native qpos/qvel重建Human映射、速度、raw acceleration/jerk、tracking，并逐native步核对实际torque与唯一正步receipt。该脚本不导入plant/controller/runner/optimizer，是独立计算路径，不冒称独立人员或agent审核。

执行源码来自retrospective，历史原1376项CODE_MANIFEST均已核对原件。物理前实际执行闭包按EXECUTION_CODE_MANIFEST冻结；复制执行源码只改根路径，原模型/配置、执行规则和阈值不改。最终归档检查另发现4份未随初始目录复制的native支持源码/构建产物；全部physics结束后按原SHA补齐，见FINAL_SOURCE_CLOSURE_MANIFEST和audit/CLOSEOUT_INITIAL_FAILURE_AND_REPAIR。它们没有回填进物理前manifest，不冒称物理前已完整复制全部历史支持文件。原执行路径/全部trace精确复现的结论保留，未在补齐后新增physics。首次包装缺少动作合同在START前失败，日志及修复留audit/prestart_launch1与ENGINEERING_EVENTS。开发B/18D结果未因验证修改。

原host scorer的plan_age/strict/R2/FAST资格不由scientific模式PASS覆盖：HOST_EXECUTION_CAUSAL_VALID仍NOT_EVALUABLE；原raw scorer的plan_age失败照存。完整issued reference见source/results/*/native_reference.npz及trace；applied commands/ownership/source/current admission见runtime_artifacts.json.gz、summary、reports/*EXECUTED_RESIDUAL_RECEIPTS。ROM/torque/contact/clearance及原绝对安全各项见MEASURED.native_physical_audit。参数身份、source/config/raw哈希见各manifest。
'''
else:audit='# 本轮复现审计\n\n复现门FAIL。停止新合法状态物理验证，保留失败与partial，原因见BASELINE_REPRODUCTION.json和logs。不能伪造精确复现。\n'
(P/'REPRODUCTION_AUDIT.md').write_text(audit)
vtable='\n'.join(f"|{r['condition']}|{r['B']['J_F_N_s']:.9f}|{r['original_frozen_18D']['J_F_N_s']:.9f}|{r['gain_percent']:.6f}|{'PASS' if r['motion_pass'] else 'FAIL'}|{', '.join(r['failed_requirements']) or '无'}|" for r in vr)
failtext=[]
for r in vr:
 if not r['diagnosis']:continue
 for d in r['diagnosis']['details']:
  if 'joint' in d:
   ph=d['dominant_diagnostic_phase'];z=d['phase_diagnostics'][ph]
   failtext.append(f"- {r['condition']}：{d['joint']} {d['requirement']}完整比值{d['full_ratio']:.6f} > 1.10；主要诊断贡献位于{ph}（该phase指标比{z['ratio']:.6f}），绝对峰时刻task {d['absolute_peak']['task_s']:.6f}s。p95按超过完整B指标限的样本数、RMS按全程归一化均方增量定位，不以近零HOLD比值当主因；phase定位不等于证明单一因果。")
  else:failtext.append(f"- {r['condition']}：{d['requirement']}，完整数值见该条件FAILURE_DIAGNOSIS与MEASURED。")
duration_hours=(time.time()-read('RUN_PLAN.json')['t0_unix'])/3600
report=f'''# iHEAR Lab — 18D Baseline Qualification v1

{conclusion} 本轮复现门{'PASS' if passed else 'FAIL'}；新合法状态完整配对{len(vr)}，正降力{validation['positive_force_gain']}/{len(vr)}，motion PASS={validation['motion_PASS']}/{len(vr)}，绝对安全PASS={validation['safety_PASS']}/{len(vr)}，receipt/causal PASS={validation['receipt_PASS']}/{len(vr)}。历史motion 0/4另列并保留。

## 七个问题的明确答案

1. **真实方法与参数**：原B上方的固定参考意图扩展。18个无量纲系数分去程/回程，控制common/differential进度常数、一次/二次形状与终端速度common/differential/tilt；完整历史方案还含RETURN槽1/2的-0.020/-0.022 native差分plateau。算法公式、逐项数值及源码定位见METHOD_DEFINITION与PARAMETER_MAP；不能仅由“18D”名称解释算法。
2. **是否学习策略**：否。历史使用有限离线约束COBYLA/probe/候选筛选；本轮固定参数执行，没有Q-learning、Neural Q或在线RL。原B仍负责因果估计、在线waypoint选择、认证quintic、40ms bridge、100ms lifecycle、current admission、governor、FAST/allocator、torque与fallback。
3. **是否精确复现历史**：{'是；本轮新物理B/18D完整trace、native身体/contact/torque和receipt字段与历史精确一致，完整积分和phase独立重算通过。' if passed else '否；复现门失败，不开展新状态physics。'} 历史报告值、本轮新物理与独立raw计算在BASELINE_REPRODUCTION和REPRODUCTION_AUDIT中区分。
4. **新合法状态能否保留降力**：本轮{validation['positive_force_gain']}/{len(vr)}个完整配对正降力，数值如下。每种来自同一Human实际native prefix，fork发生在prefix执行后的下一原生请求，B/18D完整活状态匹配。完整J_F包括共同prefix；被冻结策略的OUTBOUND0已消费，因此结论是剩余策略的迁移，不宣称整串策略在不同患者上的泛化。
5. **motion/safety是否通过**：motion {validation['motion_PASS']}/{len(vr)}，绝对安全{validation['safety_PASS']}/{len(vr)}，receipt/causal {validation['receipt_PASS']}/{len(vr)}；降力不能掩盖运动失败，阈值未放宽。
6. **是否足以成为第二轮可靠基线**：开发条件下的完整可复现比较基线{'已成立' if passed else '未成立'}；跨合法状态的可靠直接迁移资格仍受本轮及历史失败限制，不能称通用最优/临床策略。固定参数直接迁移和为新状态重新优化必须分别评价。
7. **下一步优先级**：{nextstep}

## 本轮完整结果

|合法prefix条件|B完整J_F N·s|冻结18D完整J_F N·s|降力%|motion|失败项|
|---|---:|---:|---:|---|---|
{vtable}

各臂完整OUTBOUND/HOLD/RETURN积分、phase/task时长、tracking、moment、clearance、ROM/torque/contact与绝对安全细项、source/receipt/native ownership、完整父状态来源及hash都保存在VALIDATION_RESULTS、reports、derived与原raw。partial不排名。B自比motion PASS只证明比较基准；绝对task/safety另由原评价审查。不同条件的绝对J_F不用于重选最优；本轮通过率与历史0/4的prefix集合不同，不能解释为未改参策略的性能改善。

## 失败定位与解释

{chr(10).join(failtext) if failtext else '本轮没有可定位的motion失败或尚未完成验证；不据此覆盖历史0/4。'}

新条件各失败约束计数：{json.dumps(failure_counts,ensure_ascii=False)}。所有逐joint/full/phase原生raw统计以及超全程基准限的样本时长在derived/*FAILURE_DIAGNOSIS.json。motion是冻结工程非劣等/剂量规则，不是临床舒适标准；phase-shape和raw jerk最大值仅作诊断。源码描述了状态依赖的B目标、可行性与闭环响应，观察结果不足以证明特定非线性因果或一个有效筛选器。若各条件均降力而motion仍失败，应将其理解为本有限集合的力收益方向一致、运动可行域依赖状态的开发解，不能推成稳定通用协调规律。不得以重新优化后较好的结果冒称冻结18D的泛化。冻结可复现基线的适用边界见BASELINE_CONTRACT.json；没有现成自动准入筛选器。

## 历史失败原样保留

retrospective primary：V1–V4 motion 0/4，四者都有正降力；历史完整记录在provenance原VALIDATION_RESULTS。本轮另从历史trace和保存的native motion_series独立重算四对完整/phase J_F及所有raw burden统计，再确认每个条件都有原burden失败，见audit/HISTORICAL_FAILURE_RECOMPUTATION。它是历史raw重算，不是本轮新物理；其他历史fairness失败标签保留、不重新分类。V1 velocity p95；V2 acceleration p95/phase-boundary；V3 velocity p95/acceleration p95/excursion；V4 acceleration max/p95、jerk RMS/excursion。secondary 1/4不用于改选primary。历史更低力1196.685445候选motion失败及原host/strict/R2/FAST未获资格均保留。

## 证据层级与保护

**本轮新PHYSICAL_LEVEL1**：原MuJoCo native执行的父运行与完整live fork、issued reference、实际commands、native receipts和真实Human响应。**历史报告**：隔离provenance完整原文及hash。**数学/计算证据**：无physics的参数公式检查、SHA/源码闭包、独立raw积分/导数/ownership重算。**未解决**：跨患者、模型不确定性、整串策略未见初态、正式Native LEVEL2、host-clock LEVEL3/硬实时、硬件与临床；不将这些层级混称PASS。

环境：真实WSL Ubuntu-Research-Verify；指定Python 3.10.21；主仓库与Side Studies路径已确认，未安装/更换环境。canonical包：`{P}`。Windows目录只作审阅镜像，不含全部source/raw。主分支/HEAD及既有Git暂存/未暂存状态见audit/GIT_BEFORE与FINAL_PROTECTION；无commit/push/merge/reset/stash/clean或branch切换。

物理START={len(starts)}/40，END={len(ends)}，实际新增native步{ac['actual_new_native_steps']}（继承prefix不重复算新增）。完成本有限预注册集合后提前停止，不为耗尽4–6小时追加实验；报告生成距注册约{duration_hours:.3f}小时，六小时与最后一小时无新START规则在RUN_PLAN中冻结。START/END、returncode、partial及错误见ATTEMPT_ACCOUNTING。一次START前缺共享合同的包装错误保留，未新增物理attempt；分析脚本还曾将TASK-only两字段误用整session时间mask，已改为它们实际TASK时间轴，原始数据/物理不变。最终完整归档审计首次失败，发现4份native支持归档未复制；按历史SHA补齐并保留初始审计失败，没有改变执行manifest或新增physics。三项工程/审计事件均保留，不隐瞒失败。

所有新文件只在本版本化包及其Windows审阅镜像。历史保护包括全主仓库内容SHA、既有Side Studies元数据和受保护源码/权重/报告/关键raw SHA；精确范围与最终复核见PACKAGE_VERIFICATION。源码路径迁移、参数身份、原1376项manifest原件核对，以及最终完整归档逐项核对均有证据；4项支持文件为物理结束后补齐，不能与物理前执行manifest混淆。执行源不叠加Waypoint或训练；无科学阈值、模型、task、HOLD或控制底座改变。

完成后owned物理进程全部退出，最终进程/保护核验和文件清单见PACKAGE_VERIFICATION与EVIDENCE_MANIFEST。STOP；不自动启动下一研究包。
'''
(P/'REPORT.md').write_text(report)
(P/'REPRODUCTION.md').write_text('''# 复现入口

本包已STOP，不在原目录重跑或重置计数。新运行必须建立新的版本化兄弟目录，复制source/code/deps/weights、FROZEN_18D、motion合同与output/SHARED_COORDINATION_ACTION_CONTRACT，按新根路径迁移并重新冻结预算/manifest。

本轮命令使用指定`/home/hank/envs/adaptive-online-rl-v1/bin/python -B`：control/preflight.py；control/own_campaign.py reproduction；复现门和control/independent_recompute.py reproduction通过后，分别own_campaign.py N1、N2、N3、N4。每个owner等待全部fork结束，物理串行；日志/command和返回码见各OWNER.json。没有更改既有Git分支。

只读重新计算：control/independent_recompute.py reproduction N1 N2 N3 N4（向本包derived/audit写新计算输出；不启动physics）。正式指标由冻结code/analyze_matched.py和explore_common.py给出；独立计算不导入plant/runner/controller。

完整raw在source/results/<id>/{trace.npz,summary.json,runtime_artifacts.json.gz,native_reference.npz}；参数、代码、model/config、版本身份和各次START manifest见本包相应JSON。完整live状态由os.fork继承，不是从hash恢复隐藏状态；保存的hash仅作审计，不能用来替代完整fork。
''')
print(json.dumps(dict(branch=decision,new_pairs=len(vr),motion_PASS=validation['motion_PASS'],START=len(starts),END=len(ends)),ensure_ascii=False))
