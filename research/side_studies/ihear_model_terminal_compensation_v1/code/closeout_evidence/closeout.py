from pathlib import Path
import json, os, time, shutil, hashlib, collections
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_lowforce_repair_explore_10h_v1_review')
def load(n):return json.loads((S/n).read_text())
def rows(n):return [json.loads(l) for l in (S/n).read_text().splitlines()]
def put(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');t.replace(p)
def write(n,t):(S/n).write_text(t,encoding='utf-8')
def processes():
 out=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S)+'/code/' in cmd:out.append(dict(pid=int(p.name),cmd=cmd))
  except (FileNotFoundError,PermissionError):pass
 return out
assert (S/'VALIDATION_DONE.json').exists(),'VALIDATION_NOT_COMPLETE'
exit_record=load('OWNER_EXITED.json');assert exit_record['validation_only'] and exit_record['finalizer_returncode']==0
assert not processes(),'OWNED_PROCESS_STILL_ALIVE'
P=load('SEARCH_PROTOCOL.json');ev=rows('EVALUATIONS.jsonl');ledger=rows('ATTEMPTS.jsonl');x=load('SEARCH_AND_VALIDATION.json');v=load('PACKAGE_VERIFICATION.json');best=x['best_development'];bc=best['comparison'];m=json.loads(Path(best['metrics_path']).read_text());bm=load('reports/reexplore3_B0_repeat_1_MEASURED.json');c4=load('reports/baseline_C4_1_5_MEASURED.json');frozen=load('FROZEN_SELECTION.json');cat={c['id']:c for c in load('CANDIDATE_CATALOG.json')['candidates']}
archive=S/'preservation/pre_final_review';archive.mkdir(exist_ok=True)
for n in ['REPORT.md','PROFESSOR_BRIEF.md','LOW_FORCE_MECHANISM.md','PACKAGE_VERIFICATION.json','SEARCH_AND_VALIDATION.json','PROTOCOL_AND_ATTEMPTS.json','FINALIZED.json','FIGURES.md']:
 if not (archive/n).exists():shutil.copy2(S/n,archive/n)
starts=[r for r in ledger if r['event']=='START'];end={r['id']:r for r in ledger if r['event'] in ['END','FAIL','INTERRUPTED']};assert all(r['id'] in end for r in starts)
failed=[r['id'] for r in starts if end[r['id']]['event']=='FAIL' or end[r['id']].get('returncode',0)!=0];interrupted=[r['id'] for r in starts if end[r['id']]['event']=='INTERRUPTED']
# Parent prefix is a real new cold-start cost, counted once, never per fork child.
prefix=load('output/reexplore3_B0_repeat_1_DATA.json')['child'];known_partial_steps=prefix['physics_step_at_fork'];known_partial_s=prefix['physical_time_at_fork']
assert not (S/'output/reexplore3_parent_B0_DATA.json').exists() and not (S/'output/reexplore3_parent_B0_PARTIAL_COMPUTE.json').exists()
new_steps_lower=x['actual_new_native_steps']+known_partial_steps;new_seconds_lower=x['actual_new_physical_time_s']+known_partial_s
signatures={};parameter_shapes={};dev=[r for r in ev if not r['id'].startswith(('V','verify'))]
for r in dev:
 if not r['actual_execution_signature']:continue
 sig=[(ph,i,[z.get('delta') for z in met]) for ph,i,met,t,n in r['actual_execution_signature']]
 signatures.setdefault(json.dumps(sig,sort_keys=True),[]).append(r['id'])
regions={}
for stage in ['reexplore1','reexplore2','reexplore3']:
 rr=[r for r in dev if r['id'].startswith(stage+'_') and r['parameters'].get('changes',{}).get('operation')=='local_or_cross_slot']
 parents={cat[r['candidate_id']]['parameters']['direct_parent'] for r in rr}
 actual=[]
 for cid in parents:
  found=next((r for r in dev if r['candidate_id']==cid),None)
  if found:actual.append([(ph,i,[z.get('delta') for z in met]) for ph,i,met,t,n in found['actual_execution_signature']])
 regions[stage]=dict(parent_candidate_ids=sorted(parents),distinct_observed_native_center_sequences=len({json.dumps(a,sort_keys=True) for a in actual}),not_global_action_family_count=True)
regular=[r for r in dev if r['id'].startswith(('reexplore1_','reexplore2_','reexplore3_')) and not r['candidate_id'].startswith('NATIVE_SCALAR')]
broad=[r for r in regular if r['parameters'].get('source')=='UNDERCOVERED'];extra=[r for r in dev if r['candidate_id'].startswith('NATIVE_SCALAR')]
coverage=dict(regular_completed=len(regular),regular_broad_completed=len(broad),regular_broad_fraction=len(broad)/len(regular),extra_completed=len(extra),extra_interrupted=1,total_completed_broad_fraction=len(broad)/(len(regular)+len(extra)),native_regions=regions,limitation='Extra scalar refinement diluted the requested >=40% overall broad allocation; regular queue satisfied it. This is a protocol deviation, not hidden as full coverage.')
shapes={}
for ph in ['OUTBOUND','HOLD','RETURN']:
 d=np.asarray(m['dose']['phase_shapes'][ph])-np.asarray(bm['dose']['phase_shapes'][ph]);i,j=np.unravel_index(np.argmax(abs(d)),d.shape);ix=np.flatnonzero(np.max(abs(d),axis=1)>.5)
 shapes[ph]=dict(max_abs_deg=float(abs(d[i,j])),normalized_phase_time_fraction=float(i/200),joint=['hip','knee'][j],fractions_above_point5=(ix/200).tolist(),diagnostic_only=True)
val=[r for r in ev if r['id'].startswith(('V1_','V2_','V3_'))];first_V=min(r['unix'] for r in starts if r['id'].startswith('V'));assert frozen['unix']<first_V
summaries=x['validation_summaries'];validated=x['validated_new_ids'];assert x['distinct_heldout_native_parent_count']==3
best_v=summaries[best['candidate_id']];assert best_v['scientific_validated']
worst={}
for cid in [c['id'] for c in frozen['candidates']]+['C4_1_5']:
 rr=[r for r in val if r['candidate_id']==cid];components={}
 for k in rr[0]['continuous_constraints']['components']:
  components[k]=np.max([np.asarray(r['continuous_constraints']['components'][k]) for r in rr],axis=0).tolist()
 axis={}
 for k in ['PHYSICAL_TASK_VALID','SCIENTIFIC_EXECUTION_CAUSAL_VALID','HOST_EXECUTION_CAUSAL_VALID','LEGACY_R2_MATCHED']:
  axis[k]=dict(denominator=len(rr),values=[json.loads(Path(r['metrics_path']).read_text())['axes'].get(k) for r in rr])
 worst[cid]=dict(complete_denominator=len(rr),attempted_denominator=sum(a['id']==z+'_'+cid for a in starts for z in ['V1','V2','V3']),motion_pass_count=sum(r['comparison']['acceptance_pass'] for r in rr),qualification_pass_count=sum(r['comparison']['eligible'] for r in rr),worst_normalized_components=components,axes=axis,force_gain_mean_percent=float(np.mean([r['comparison']['gain_percent'] for r in rr])),force_gain_worst_percent=min(r['comparison']['gain_percent'] for r in rr),extra_vs_C4_mean_percent=float(np.mean([r['extra_gain_vs_C4_percent'] for r in rr])))
checks=load('INDEPENDENT_DERIVED_CHECKS.json');assert checks['all_pass'];dense=sum('dense_acceleration_error' in r for r in checks['rows'])
errors=dict(historical_mechanical_fixed={k:z for k,z in v['errors'].items() if z.get('unix',0)<load('WRAPPER_REPAIR2_COMPLETE.json')['unix']},search_timeout={k:z for k,z in v['errors'].items() if z.get('unix',0)>=load('WRAPPER_REPAIR2_COMPLETE.json')['unix']})
closeout=dict(unix=time.time(),owner_exit=exit_record,owned_processes=processes(),attempts=len(starts),failed_attempts=failed,interrupted_attempts=interrupted,all_attempts_terminal=True,independent_integral_denominator=checks['denominator'],independent_dense_motion_denominator=dense,known_new_native_steps_lower_bound=new_steps_lower,known_new_simulation_s_lower_bound=new_seconds_lower,additional_killed_child_compute_unknown=True,known_partial_parent_steps=known_partial_steps,distinct_development_sampled_delta_sequences=len(signatures),coverage=coverage,best_phase_shape=shapes,validation_worst=worst,selection_frozen_before_first_V=True,selection_timestamp=frozen['unix'],first_V_dispatch=first_V,no_more_dispatch=True,no_training=True,errors_preserved=errors)
put('FINAL_CLOSEOUT.json',closeout)
x.update(final_closeout=closeout,unjoined_attempts=[],interrupted_attempts=interrupted,validation_worst_by_item=worst,actual_new_native_steps_lower_bound=new_steps_lower,actual_new_physical_time_s_lower_bound=new_seconds_lower,compute_completeness='killed NATIVE_SCALAR_19 final compute unknown; do not claim exact total',distinct_development_sampled_delta_sequences=len(signatures),reexploration_coverage=coverage,validation_status='2 frozen new representatives qualified in all three legal same-Human prefixes; high-gain representative diagnostic only')
put('SEARCH_AND_VALIDATION.json',x)
v.update(work_status='研究与冻结验证完成；再探索批次超时截断；收尾完成并停止',scientific_status='SCI_VALIDATED_WITH_RECORDED_WORKFLOW_DEVIATIONS',performance_status='可信但性能仍不足；未达2%或5%',owner_exit_pending=False,owner_exit_evidence=exit_record,final_process_absence=processes(),unjoined_attempts=[],interrupted_attempts=interrupted,all_attempts_terminal=True,validation_completed=True,scientifically_validated_ids=validated,errors_preserved_and_classified=errors,time_elapsed_s=time.time()-P['t0_unix'],physics_owner_elapsed_s=exit_record['elapsed_s'],final_closeout='FINAL_CLOSEOUT.json',third_wrapper_repair=False)
put('PACKAGE_VERIFICATION.json',v)
protocol=load('PROTOCOL_AND_ATTEMPTS.json');protocol['events']=ledger;protocol['validation_continuation']=load('VALIDATION_CONTINUATION_REGISTERED.json');protocol['deviations']=coverage;protocol['interrupted_attempts']=interrupted;put('PROTOCOL_AND_ATTEMPTS.json',protocol)
def table(rr):
 out='|方案／条件|完整力积分 N·s|比同条件 B 降低|比同条件 C4 额外降低|运动条件|最严重约束比|\n|---|---:|---:|---:|---|---:|\n'
 for r in rr:
  mm=json.loads(Path(r['metrics_path']).read_text());out+=f"|{r['id']}|{mm['J_F_N_s']:.6f}|{r['comparison']['gain_percent']:.6f}%|{r['extra_gain_vs_C4_percent']:.6f}%|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|{r['continuous_constraints']['worst_ratio']:.6f}|\n"
 return out
chains=load('REPAIR_CHAIN_SUMMARY.json')['rows']
chain_table='|种子|原降力|修复代表降力|收益保留|最严重约束比：原→修复|运动条件|\n|---|---:|---:|---:|---:|---|\n'
for r in chains:chain_table+=f"|{r['seed']}|{r['seed_gain_percent']:.4f}%|{r['repair_gain_percent']:.4f}%|{r['force_gain_retained_percent']:.2f}%|{r['worst_constraint_seed']:.4f}→{r['worst_constraint_repair']:.4f}|{'PASS' if r['motion_pass'] else 'FAIL'}|\n"
val_table=table(val)
constraints='|指标（最差关节）|开发最佳相对 B|冻结主条件|\n|---|---:|---|\n'
for k,a in bc['burden_ratios'].items():constraints+=f'|{k}|{max(a):.6f}|≤1.1|\n'
constraints+=f"|行程差|{max(bc['excursion_delta_deg']):.6f}°|≤0.5°|\n|累计角位移比|{min(bc['cumulative_ratio']):.6f}–{max(bc['cumulative_ratio']):.6f}|0.95–1.05|\n|末端最大差|{max(bc['endpoint_abs_delta_deg']):.8f}°|≤0.5°|\n|完整及各阶段时长差|0 s|≤0.1 s|\n|力矩积分比|{bc['moment_integral_ratio']:.6f}|≤1.25|\n"
report=f'''# 强低力运动修复与再探索：最终报告

机器人可以通过改变髋膝相对运动的进入、退出和阶段分配来降低交互力，但本轮仍未把原来约 7%–15% 的强降力行为修复成满足全部运动条件的方案。局部调整确实减少了一些负担；要保住较大收益时，速度、加速度或关节行程限制仍会失败。这是有干预支持的局部结果，不是物理上全局无解的证明。

最好合格新方案 NATIVE_SCALAR_18 的完整力积分为 **{m['J_F_N_s']:.6f} N·s**；相对同条件 B 的 {bm['J_F_N_s']:.6f} N·s，降低 **{bc['gain_percent']:.6f}%（{bc['gain_N_s']:.6f} N·s）**。相对 C4 的 {c4['J_F_N_s']:.6f} N·s，再降低 **{best['extra_gain_vs_C4_percent']:.6f}%（{best['extra_gain_vs_C4_N_s']:.6f} N·s）**。它已超过历史约0.74%点，但仍是小幅改进，**可信但性能仍不足**。没有 ≥2% 或 ≥5% 的合格证据。

新方案通过同动作精确重复、RETURN 介入前负对照和三个新合法前缀条件；保留条件收益平均 **{best_v['gain_mean_percent']:.6f}%**，最差 **{best_v['gain_worst_percent']:.6f}%**，资格通过 **3/3**。这是同一已知人体的有限扰动验证，不是跨人体、在线个体化或临床验证。

1. 原来低力怎样实现：动作图只在 B 原生目标请求处采一个值，以 [delta,−delta] 调整髋膝相对进度。强方案显著改变阶段内姿态；M2 和 C2 的最大阶段形状差分别约41.05°、49.12°。M2 有约2.342 s真实速度超过对应 B 最大值的110%，C2 有约2.566 s，不能概括成一个孤立尖峰。加速度最大值暴露与 p95／RMS 硬条件不同，零最大值超限时间也不意味着所有加速度条件通过。详细区间见 LOW_FORCE_MECHANISM_DATA.json。

2. 是否修复了负担：取消 M2 的 RETURN slot0，降力由7.716337%变为6.474926%，保留约83.91%；最大膝行程差由约2.453°减到1.296°，最严重约束比由4.9057减到2.5919，moment／tracking失败消失，但速度、加速度分位／RMS、jerk分位与行程仍失败。另一强链保留13.819507%降力、约91.58%原收益，最严重违反比4.5541→2.3599，也未合格。近边界链达到0.812734%与1.010916约束比，仍必须判 FAIL，未改阈值让它通过。

{chain_table}

3. 最好合格方案实际做了什么：仅 RETURN 原有 slot1、slot2 非零，native 接受 delta 为 −0.020、−0.022；首次执行绝对物理时刻约21.685 s、22.875 s，共9460个非零native步。去程和停留的力积分差为0，回程减少16.768044 N·s；完整及阶段时长差均为0。负对照确认介入前已归档物理量一致，收益没有归到未发生的后续动作。重复轨迹、116320个native行及5817条receipt精确一致。

{constraints}

膝行程差 **0.496750°** 接近0.5°上限，余量仅约0.003250°。阶段形状最大差 **{bc['phase_shape_max_delta_deg']:.6f}°**，发生位置及超过0.5°的归一化阶段时间范围见 FINAL_CLOSEOUT.json。它的运动条件 PASS 不表示治疗轨迹等效。力矩积分增加约4.376%，不等于动量或临床不适；jerk max继续只作诊断，原始导数用于验收，SG5／21仅是原有敏感性分析。

4. 是否达到强性能：开发与三个保留条件均无 ≥2%／≥5% 的运动合格新方案。约2.3%的冻结诊断代表在三个条件下都因加速度／行程失败。最大余量合格代表约0.61%，低于 C4 的约0.74%，它展示余量与力收益的差别，不是新的性能冠军。

5. 保留结果能否重复：三项条件各有自己的合法完整父运行、B0和C4，绝不使用旧B数值替代。实际 q/dq父状态签名不同为3/3，未把换文件名或重复当新条件。参数冻结时刻早于第一次V派发，验证后未重新选择或修复。原H1/H2已暴露，只作历史开发资料。

{val_table}

逐项最差运动条件、安全／科学归属／任务分母见 SEARCH_AND_VALIDATION.json 的 validation_worst_by_item；三个新代表各3次完整比较，全部任务和科学执行轴通过，两个新代表资格3/3，高收益诊断0/3。小样本和很有限的前缀扰动不支持显著性、人群或长期稳健性推断。

6. 实际测试量：共 **{len(starts)}/300** 次物理尝试，完整任务 **{x['complete_tasks']}** 次；完整搜索／方案比较 {len(dev)} 次。开发观察到 {x['distinct_nonzero_development_execution_signatures']} 条不同非零完整native执行序列；忽略实现时刻，仅按实际 phase、issued index、接受 delta 序列区分为 **{len(signatures)}** 条。这些是同条件已观察动作差异，不是独立人体数、图参数数或全未来状态动作族数。失败和精确重复均在总分母内。

可审计新增native步至少 **{new_steps_lower}**，新增仿真物理时间至少 **{new_seconds_lower:.3f} s**，fork继承前缀不重复计入。超时杀掉的NATIVE_SCALAR_19没有最终计算计数，真实总计算还包含未知尾部，因此不把下界写成精确总数。

7. 现在是否训练 Neural Q：本轮没有训练；不建议仅因上述 PASS 就开训。已交付完整策略、合法fork后续价值及实际局部决策的分组数据，动作编码来自真实图／spec，raw_v2全零K3仅是占位。当前可用估计状态、模型估计、carry、issued历史与mask和真实状态审计分离，未来执行与remaining force只作标签。旧／早期缺失完整数值输入的记录不可作为部署输入训练样本；不同固定续跑与旧Q滚动规则不能混成一个单步Q标签。

8. 教授最需看：强方案力累积与真实运动负担；同父slot干预前后的收益保留和未消除负担；三个新合法前缀上的冻结配对结果。最需决定：治疗允许的髋膝相对姿态／阶段形状范围；运动非劣与剂量阈值的康复依据；下一项实验如何区分现有接口表达限制、局部搜索不足与物理权衡。具体六页提纲见 PROFESSOR_BRIEF.md。

执行与限制：完成两批机制探索、四批修复、三批常规再探索和19项额外标量搜索比较。常规再探索广域比例 {coverage['regular_broad_fraction']*100:.2f}%；加入额外局部标量后，整体广域比例下降到 **{coverage['total_completed_broad_fraction']*100:.2f}%**，未达到用户要求的整体至少40%。原生中心实际差异见 FINAL_CLOSEOUT.json；不把参数名称当多样性。这一覆盖偏差必须保留，不能宣称完整满足探索分配。

第三批搜索因60分钟批次时限截断，尚未完成的父和child均记 INTERRUPTED。原owner退出、进程组消失后，只继续已注册的独立重复与V验证；没有延长超时或修复第三轮包装，也没有恢复搜索。原t0 2026-10-13 02:58:22+08:00、累计计数、9小时派发与10小时硬界保持不变。此前两次包装错误及来源分组、复合phase消融、阶段位置标签分析纠正全部保留前版和失败说明。

工作状态：研究、冻结验证和收尾完成，部分额外搜索因超时截断；科学结果：同一已知人体有限合法扰动下的小幅收益已验证；性能层级：可信但性能仍不足；部署资格：未获得。未开展正式host-clock、真机、在线适应或个体化训练。未修改B、人体系、安全、时长、bridge、issued slots或生命周期语义，未实施更自由controller对照，有限搜索未证明全局无解。

保护：两处Linux Git的branch／HEAD／index／staged／unstaged／untracked名称快照一致，所列复用源码及模型字节哈希未变；范围不包括全历史字节扫描或全部untracked内容哈希。保留全部新raw，不删除历史，不作Git写入或系统维护。最终实际退出、资源、失败与保护范围见 PACKAGE_VERIFICATION.json。教授图共5张，可从 FIGURES.md 统一进入。STOP，无下一工作包、定时任务或后台研究承诺。
'''
write('REPORT.md',report)
brief=f'''# 教授商讨：六页中文汇报提纲

## 第1页：研究问题与本轮结论

目标是依据人体状态及特性协调安全、平顺、低交互力运动，为未来实时个体化建立可靠行为。完整去程—停留—回程与原控制、安全规则保持。原来7%–15%低力动作伴额外运动负担，不能仅因积分低就使用。

本轮最佳合格完整力积分1421.845454 N·s，相对B降1.165570%，相对C4额外降0.429985%；三个新合法前缀平均{best_v['gain_mean_percent']:.6f}%、最差{best_v['gain_worst_percent']:.6f}%，资格3/3。**可信但性能仍不足；没有2%或5%合格证据。**

## 第2页：已经建立的实验能力与边界

完成活进程完整状态fork、合法父状态重建、原生采样和receipt审计、当前因果输入与真实状态隔离、完整力积分及dense运动检查。最佳新动作重复中native行和receipt精确一致，介入前负对照PASS。{len(starts)}次物理尝试、{x['complete_tasks']}个完整任务；{checks['denominator']}个完整积分独立闭合，{dense}份保留dense运动统计独立复核通过。

科学仿真时钟成立，host-clock实时执行仍NOT_EVALUABLE；没有真机、跨人体或在线适应资格。进程fork退出后，JSON／哈希不能独立恢复活对象；保存了合法父重建配置和原实现。

## 第3页：7%–15%强低力与0.74%点差在哪里

图1 force_cumulative、图2 knee_motion、图3 actual_execution。M2降7.716337%，C2降15.090469%，都运动FAIL。C4只实际执行一个RETURN slot，降0.738762%，运动PASS，但阶段形状最大差7.565056°。M2和C2阶段形状可差41.05°、49.12°，真实速度超B的110%持续约2.342 s、2.566 s。

同父干预：取消M2 RETURN slot0，降力仍6.474926%，约保留83.91%，膝行程差约2.453°→1.296°，moment／tracking失败消失，速度、加速度统计、jerk分位和行程仍失败。它支持该slot对后续负担有总效应，不证明具体接触／惯性机制。其余slot参数不变不等于后续原生时序不变。

## 第4页：修复保住多少收益、消除多少负担

图4 repair_tradeoff：横轴为最严重归一化约束比（1为边界），纵轴为完整力积分收益，分别显示全局点云与边界放大。强链的13.819507%点保住约91.58%收益，最严重比4.5541→2.3599，仍FAIL。近边界链0.812734%点最严重比1.010916，仍FAIL。C4链达到1.102168%合格；额外标量网格达到1.165570%合格。

{chain_table}

最佳新点只执行RETURN两项 −0.020／−0.022；全部16.768044 N·s收益来自RETURN，时长不变。膝行程差0.496750°非常接近上限，阶段形状最大差10.980605°。运动PASS与治疗轨迹等效必须分开讨论。

## 第5页：冻结保留验证与可信程度

图5 heldout_effect。三项条件在搜索前注册，使用同一Human的合法前缀，实际父q/dq不同。读取V前按原规则冻结最大收益NATIVE_SCALAR_18、最大余量NATIVE_SCALAR_01和近合格高收益repair2_2_0，之后未调参。

{val_table}

两个新合格代表均资格3/3；高收益诊断0/3。每项自有父、B和C4，完整任务与科学执行3/3通过，逐项最差值在SEARCH_AND_VALIDATION。重复不计独立样本；小扰动、小分母不支持人群显著性。

执行偏差须说明：额外网格使整体广域比例从常规{coverage['regular_broad_fraction']*100:.2f}%降至{coverage['total_completed_broad_fraction']*100:.2f}%，未满足整体40%；搜索第三批超时截断，只继续既注册验证，失败未删除。两轮包装修复保留并重新过零动作／父门；未发生第三轮包装修复。当前物理总计算只有下界，因为一个被杀child没有最终计数。

## 第6页：教授要决定的三个问题与下一项实验

1. 治疗允许哪些相对姿态和阶段形状变化？即使速度、加速度、剂量、末端合格，10.98°阶段差是否符合治疗目标，需外部依据，不能从仿真PASS推断。
2. 10%运动非劣、0.5°行程差、累计剂量和tracking条件的康复依据如何冻结？继续保持现协议用于本包，后续如需改变，应分别报告旧／新定义，不能事后让结果过门。
3. 下一步继续原生合法空间，还是单独授权最小参考自由度离线对照？PWL只按原请求采样，输入曲线平滑不等于真实运动平滑。当前结果尚不能区分接口表达不足、局部搜索覆盖不足与真实物理权衡。

建议的可区分实验设计（本轮未执行）：保留同Human、完整任务、原安全和运动评价，从一条已定位的强链出发，只比较原请求采样的两slot协调与明确增加一个进入／退出参考自由度的成熟离线方案；后者先按完整动力学独立回放并分账，未经B准入／生命周期执行不称原生可执行。若没有现成可靠工具则停在设计，不重写B。

Neural Q仍不训练：先审核行为价值、阶段形状与自由度。已留下正确动作编码、来源／parent／condition隔离和固定续跑合同的数据；未来结果仅作标签，缺少当前数值输入的早期样本不进入部署输入训练。任何新增对照与训练均需另行工作包，本轮STOP。
'''
write('PROFESSOR_BRIEF.md',brief)
with (S/'LOW_FORCE_MECHANISM.md').open('a',encoding='utf-8') as f:f.write('\n最终核验补充：M2 RETURN slot0取消的同父干预保留6.474926%降力，膝行程差减至1.295964°，仍未通过。最大值点wise暴露与p95/RMS统计门分开；不能把零最大值超限时间写成所有导数条件通过。最佳新方案RETURN两次实际接受delta −0.020、−0.022，全部收益来自RETURN；负对照和同动作重复PASS，具体见REPORT与FINAL_CLOSEOUT。\n')
# Improve readable plots using the same saved samples, never smooth the executed motion.
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':9,'axes.grid':True})
figdir=S/'figures'
reps=['baseline_B0_repeat_1','baseline_C4_1_5','recovery2_Frozen_M2','baseline_C2_pair_1_2',best['id']]
labels=['B','C4 (qualified)','Frozen M2 (motion FAIL)','C2 (motion FAIL)','New best (qualified)']
fig,ax=plt.subplots(figsize=(8,4.5))
for ident,label in zip(reps,labels):
 with np.load(S/'source/results'/ident/'trace.npz') as z:ix=z['stage']=='TASK';t=z['time_s'][ix];ff=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);cum=np.r_[0,np.cumsum(ff[:-1]*np.diff(t))]
 ax.plot(t,cum,label=label)
ax.set(xlabel='Absolute physics time (s)',ylabel='Full TASK cumulative cuff force (N s)',title='Matched known Human; original TASK left quadrature');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figdir/'force_cumulative.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(2,1,figsize=(8,6),sharex=True)
for ident,label in zip(reps,labels):
 with np.load(S/'motion_series'/(ident+'.npz')) as z:axs[0].plot(z['time_s'],np.rad2deg(z['true_dq_rad_s'][:,1]),label=label);axs[1].plot(z['time_s'],np.rad2deg(z['acceleration_rad_s2'][:,1]),label=label)
axs[0].set(ylabel='True knee speed (deg/s)',title='Raw dense native motion; matched known Human');axs[1].set(xlabel='Absolute physics time (s)',ylabel='True knee acceleration (deg/s^2)');axs[0].legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'knee_motion.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,4.5))
for stage in sorted({r['stage'] for r in dev}):
 rr=[r for r in dev if r['stage']==stage]
 for ax in axs:ax.scatter([r['continuous_constraints']['worst_ratio'] for r in rr],[r['comparison']['gain_percent'] for r in rr],s=16,label=stage)
for ax in axs:
 ax.axvline(1,color='black',ls='--');ax.axhline(2,color='grey',ls=':');ax.axhline(5,color='grey',ls=':');ax.set(xlabel='Worst normalized constraint (1 = gate)',ylabel='Full TASK gain vs matched B (%)')
axs[0].set_title('All development comparisons');axs[1].set(xlim=(.90,1.16),ylim=(.45,1.8),title='Boundary detail (same points)');axs[0].legend(fontsize=6,loc='upper center');fig.tight_layout();fig.savefig(figdir/'repair_tradeoff.png',dpi=150);plt.close(fig)
figure_text='# 五张关键静态图\n\n'
for n,desc in [('force_cumulative','完整TASK力积分：原left quadrature；M2来自recovery2精确重现门通过的同条件记录'),('knee_motion','真实膝速度及加速度：保留原dense样本，无滤波救门'),('actual_execution','原生实际接受并激活的调整；不是输入PWL图'),('repair_tradeoff','力收益和运动约束分别显示，右图只放大同一批点'),('heldout_effect','三个新合法前缀；含运动失败诊断曲线，合格与失败标签以REPORT配对表为准')]:figure_text+=f'- [{n}.png](figures/{n}.png)：{desc}。数据来源为本包trace、motion_series及receipt／EVALUATIONS。\n'
write('FIGURES.md',figure_text)
for n in ['REPORT.md','PROFESSOR_BRIEF.md','LOW_FORCE_MECHANISM.md','PACKAGE_VERIFICATION.json','SEARCH_AND_VALIDATION.json','PROTOCOL_AND_ATTEMPTS.json','FINAL_CLOSEOUT.json','FIGURES.md','FROZEN_SELECTION.json','NEW_CANDIDATE_REPEAT_GATE.json','NEW_RETURN_NEGATIVE_CONTROL.json','OWNER_EXITED.json','VALIDATION_CONTINUATION_REGISTERED.json','VALIDATION_DONE.json','ATTEMPTS.jsonl','RESOURCE_SAMPLES.jsonl']:
 shutil.copy2(S/n,W/n)
shutil.copytree(figdir,W/'figures',dirs_exist_ok=True)
v['package_bytes']=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());v['closeout_elapsed_s']=time.time()-P['t0_unix'];v['hard_time_limit_pass']=v['closeout_elapsed_s']<=36000;v['storage_hard_limit_pass']=v['package_bytes']<20*2**30;put('PACKAGE_VERIFICATION.json',v);shutil.copy2(S/'PACKAGE_VERIFICATION.json',W/'PACKAGE_VERIFICATION.json')
put('FINALIZED.json',dict(unix=time.time(),work_status=v['work_status'],science=v['scientific_status'],performance=v['performance_status'],attempts=len(starts),best_gain=bc['gain_percent'],validated=validated,owned_processes_absent=True,no_followup=True))
print(json.dumps(dict(attempts=len(starts),complete=x['complete_tasks'],validated=validated,best_validation=best_v,failed=failed,interrupted=interrupted,unique_delta_sequences=len(signatures),coverage=coverage,elapsed_h=v['closeout_elapsed_s']/3600,package_GiB=v['package_bytes']/2**30,owned_processes=processes()),ensure_ascii=False))
