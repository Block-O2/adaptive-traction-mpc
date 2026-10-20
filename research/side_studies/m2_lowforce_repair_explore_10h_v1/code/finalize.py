from pathlib import Path
import os,sys,json,time,hashlib,subprocess,shutil,datetime,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
S=Path(__file__).resolve().parent.parent;W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_lowforce_repair_explore_10h_v1_review');W.mkdir(exist_ok=True)
import numpy as np
def load(n,default=None):return json.loads((S/n).read_text()) if (S/n).exists() else default
def lines(n):return [json.loads(l) for l in (S/n).read_text().splitlines()] if (S/n).exists() else []
def put(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');t.replace(p)
def md(n,t):(S/n).write_text(t,encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(r):
 def g(*a):return subprocess.check_output(['git','-C',str(r),*a],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode()
 return dict(branch=g('branch','--show-current'),HEAD=g('rev-parse','HEAD'),status=g('status','--porcelain=v1'),index=sha(r/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest(),unstaged=hashlib.sha256(g('diff','--binary').encode()).hexdigest(),untracked=g('ls-files','--others','--exclude-standard'))
def table(rr):
 out='|候选／条件|完整力积分 N·s|相对同条件 B 收益|相对 C4 额外收益|motion|最严重连续约束比|\n|---|---:|---:|---:|---|---:|\n'
 for r in rr:
  m=json.loads(Path(r['metrics_path']).read_text());c=r['comparison'];out+=f"|{r['id']}|{m['J_F_N_s']:.6f}|{c['gain_percent']:.6f}%|{r.get('extra_gain_vs_C4_percent',float('nan')):.6f}%|{'PASS' if c['acceptance_pass'] else 'FAIL'}|{r['continuous_constraints']['worst_ratio']:.6f}|\n"
 return out
def main():
 P=load('SEARCH_PROTOCOL.json');ev=lines('EVALUATIONS.jsonl');ledger=lines('ATTEMPTS.jsonl');starts=[r for r in ledger if r['event']=='START'];ends={r['id']:r for r in ledger if r['event'] in ['END','FAIL','INTERRUPTED']};unjoined=[r['id'] for r in starts if r['id'] not in ends];catalog={c['id']:c for c in load('CANDIDATE_CATALOG.json',{'candidates':[]})['candidates']};frozen=load('FROZEN_SELECTION.json',{'candidates':[],'status':'NOT_FROZEN','discovery_rows':[]});dev=[r for r in ev if not r['id'].startswith(('V','verify'))];new=[r for r in dev if r['stage']!='REFERENCE' and r['candidate_id'] not in ['C4_repeat','C4_1_5']];eligible=[r for r in new if r['comparison']['eligible']];best=min(eligible,key=lambda r:-r['comparison']['gain_percent']) if eligible else None;val=[r for r in ev if r['id'].startswith(('V1_','V2_','V3_'))]
 independent=[];total_steps=0;physical_s=0;completed=0
 for a in starts:
  d=load('output/'+a['id']+'_DATA.json')
  if d:
   m=d['metric'];total_steps+=m.get('actual_new_native_physics_steps',0);physical_s+=m.get('actual_new_simulation_seconds',0);completed+=bool(m.get('task_valid'))
   tpath=S/'source/results'/a['id']/'trace.npz'
   if tpath.exists() and m.get('task_valid'):
    with np.load(tpath) as z:
     ix=z['stage']=='TASK';t=z['time_s'][ix];f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);jf=float(f[:-1]@np.diff(t))
    error=jf-m['J_F'];check=dict(id=a['id'],independent_TASK_integral_error_N_s=error,pass_=abs(error)<1e-8)
    mp=S/'motion_series'/(a['id']+'.npz');measured=load('reports/'+a['id']+'_MEASURED.json')
    if mp.exists() and measured:
     with np.load(mp) as z:
      t=z['time_s'];v=z['true_dq_rad_s'];acc=np.gradient(v,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2);ae=float(np.max(abs(acc-z['acceleration_rad_s2'])));je=float(np.max(abs(jerk-z['jerk_rad_s3'])))
      vals={'velocity_deg_s':np.rad2deg(v),'acceleration_deg_s2':np.rad2deg(acc),'jerk_deg_s3':np.rad2deg(jerk)};metric_error=0
      for k,x in vals.items():
       for met,out in [('max_abs',np.max(abs(x),axis=0)),('p95_abs',np.quantile(abs(x),.95,axis=0)),('rms',np.sqrt(np.mean(x*x,axis=0)))]:metric_error=max(metric_error,float(np.max(abs(out-np.asarray(measured['motion']['raw']['full'][k][met])))))
     check.update(dense_acceleration_error=ae,dense_jerk_error=je,motion_statistics_error=metric_error);check['pass_']&=ae<1e-10 and je<1e-8 and metric_error<1e-8
    independent.append(check)
  else:
   d=load('output/'+a['id']+'_PARTIAL_COMPUTE.json',{});total_steps+=d.get('actual_new_native_physics_steps') or 0;physical_s+=d.get('actual_new_simulation_seconds') or 0
 failures=[load(str(p.relative_to(S))) for p in (S/'reports').glob('*_TASK_FAILURE.json')]
 conditions={}
 for name in ['V1','V2','V3']:
  parent=load('output/'+name+'_parent_B0_DATA.json');snap=load('reports/'+name+'_B0_repeat_1_SNAPSHOT.json',{});rr=[r for r in val if r['id'].startswith(name+'_')]
  physical_signature=None;forkdata=load('output/'+name+'_B0_repeat_1_DATA.json');tp=S/'source/results'/(name+'_B0_repeat_1')/'trace.npz'
  if forkdata and tp.exists():
   with np.load(tp) as z:
    t=z['time_s'];i=int(np.clip(np.searchsorted(t,forkdata['child']['physical_time_at_fork'],side='right')-1,0,len(t)-1));true_state=z['evaluation_only_human_state_rad_rad_s'][i].tolist();physical_signature=hashlib.sha256(json.dumps(true_state).encode()).hexdigest()
  conditions[name]=dict(parent_complete=bool(parent and parent['metric']['task_valid']),parent_source=None if parent is None else parent['condition'],native_parent_hash=snap.get('native_hash'),full_parent_hash=snap.get('hash'),physical_q_dq_signature=physical_signature,rows=rr,scope='same known Human, legal prefix perturbation, not multi-Human',used_for_tuning=False)
 distinct=len({v['physical_q_dq_signature'] for v in conditions.values() if v['physical_q_dq_signature']})
 summaries={}
 for c in frozen['candidates']:
  rr=[r for r in val if r['candidate_id']==c['id']];g=[r['comparison']['gain_percent'] for r in rr];passes=[bool(r['comparison']['eligible']) for r in rr];summaries[c['id']]=dict(denominator=len(rr),qualification_pass_count=sum(passes),gain_mean_percent=float(np.mean(g)) if g else None,gain_worst_percent=min(g) if g else None,worst_continuous_constraint_ratio=max((r['continuous_constraints']['worst_ratio'] for r in rr),default=None),scientific_validated=len(rr)==3 and all(passes) and distinct==3,diagnostic_only=frozen['status']=='NEGATIVE_DIAGNOSTIC_ONLY' or not any(r['candidate_id']==c['id'] and r['comparison']['eligible'] for r in new))
  summaries[c['id']]['attempted_denominator']=sum(a['id']==v+'_'+c['id'] for a in starts for v in ['V1','V2','V3'])
 validated=[k for k,v in summaries.items() if v['scientific_validated'] and not v['diagnostic_only']]
 maxdev=best['comparison']['gain_percent'] if best else None;strong2=bool(best and maxdev>=2);strong5=bool(best and maxdev>=5);valid2=any(summaries[k]['gain_worst_percent']>=2 for k in validated);valid5=any(summaries[k]['gain_worst_percent']>=5 for k in validated)
 individual2=sum(r['comparison']['eligible'] and r['comparison']['gain_percent']>=2 and r['candidate_id']!='C4_1_5' for r in val);individual5=sum(r['comparison']['eligible'] and r['comparison']['gain_percent']>=5 and r['candidate_id']!='C4_1_5' for r in val)
 signatures={};active_actions=0
 for r in ev:
  key=json.dumps(r['actual_execution_signature'],sort_keys=True);signatures.setdefault(key,[]).append(r['id']);active_actions+=bool(r['actual_execution_signature'])
 signatures_dev={json.dumps(r['actual_execution_signature'],sort_keys=True) for r in dev if r['actual_execution_signature']}
 outcome=dict(protocol=P,attempts=len(starts),complete_tasks=completed,task_failures=failures,unjoined_attempts=unjoined,actual_new_native_steps=total_steps,actual_new_physical_time_s=physical_s,development=dev,validation=conditions,validation_summaries=summaries,distinct_heldout_native_parent_count=distinct,eligible_new_count=len(eligible),best_development=best,validated_new_ids=validated,development_milestones={'at_least2percent':strong2,'at_least5percent':strong5},validation_milestones={'all3_at_least2percent':valid2,'all3_at_least5percent':valid5},actual_nonzero_attempts=active_actions,distinct_observed_full_execution_signatures=len(signatures),distinct_nonzero_development_execution_signatures=len(signatures_dev),signature_caution='includes observed timing and delta, condition differences do not prove independent action families; no global equivalence claim',all_evaluations=ev,failures_preserved=True)
 put('SEARCH_AND_VALIDATION.json',outcome);put('INDEPENDENT_DERIVED_CHECKS.json',dict(rows=independent,denominator=len(independent),all_pass=all(r['pass_'] for r in independent)))
 before=load('preservation/GIT_BEFORE.json');after={r:git(Path(r)) for r in before};put('preservation/GIT_AFTER.json',after)
 hashes=load('preservation/FROZEN_SOURCE_HASHES.json');changed=[p for p,h in hashes.items() if not Path(p).exists() or sha(Path(p))!=h];git_equal={r:before[r]==after[r] for r in before};resources=lines('RESOURCE_SAMPLES.jsonl')
 errors={p.name:load(p.name) for p in S.glob('*ERROR.json')};stop=load('PHYSICS_STOP.json');repaired=load('WRAPPER_REPAIR2_COMPLETE.json') or load('WRAPPER_REPAIR1_COMPLETE.json');historical_errors={}
 if repaired and load('PIPELINE_DONE.json'):
  historical_errors={k:v for k,v in errors.items() if v.get('unix',0)<repaired['unix']};errors={k:v for k,v in errors.items() if k not in historical_errors}
  if stop and stop['unix']<repaired['unix']:stop=None
 complete=bool(load('PIPELINE_DONE.json')) and not errors and not unjoined
 science='SCI_VALIDATED' if validated else 'DISCOVERY_NOT_VALIDATED' if eligible else 'NO_NEW_QUALIFIED_CANDIDATE'
 if stop or errors:science='STOPPED_WITH_PRESERVED_EVIDENCE'
 status='研究工作包完成并停止' if complete else '研究工作包提前停止，完成现有证据收尾'
 perf='取得至少5%开发里程碑' if strong5 else '取得至少2%开发里程碑' if strong2 else '可信但性能仍不足' if eligible else '未取得新合格性能进展；有效负结果'
 verify=dict(unix=time.time(),work_status=status,scientific_status=science,performance_status=perf,deployment_status='NOT_QUALIFIED; scientific simulation only, no host-clock/hardware/clinical qualification',attempt_count=len(starts),budget_pass=len(starts)<=300,time_elapsed_s=time.time()-P['t0_unix'],hard_limit_s=36000,owned_child_join_evidence=[p.name for p in S.glob('*_DONE.json')],unjoined_attempts=unjoined,git_exact_state_equal=git_equal,protected_reused_source_bytes_changed=changed,protection_scope=load('INITIALIZED.json')['protection_scope'],independent_integral_and_motion_checks=all(r['pass_'] for r in independent),resources=resources,package_bytes=sum(p.stat().st_size for p in S.rglob('*') if p.is_file()),historical_deletions=0,new_raw_deletions=0,training_count=0,host_tests=0,hardware_tests=0,errors=errors,owner_exit_pending='owner writes OWNER_EXITED after this subprocess joins; final monitor must confirm')
 verify.update(historical_repaired_errors=historical_errors,wrapper_repair_cycles=[dict(registration=load('WRAPPER_REPAIR'+str(i)+'_REGISTERED.json'),completion=load('WRAPPER_REPAIR'+str(i)+'_COMPLETE.json')) for i in [1,2]],source_group_analysis_correction=lines('SOURCE_GROUP_NORMALIZATION.jsonl'))
 put('PACKAGE_VERIFICATION.json',verify)
 put('PROTOCOL_AND_ATTEMPTS.json',dict(protocol=P,events=ledger,attempt_denominator=len(starts),attempt_budget=300,validation_reserved_before_search=48,versions={p.name:sha(p) for p in (S/'code').glob('*.py') if p.name in ['worker.py','pipeline.py','mechanism.py','finalize.py','owner.py']}))
 baseline=[r for r in dev if r['id'].startswith('baseline_')];history=load('HISTORICAL_E_RECOVERY.json',{});mechanisms={p.stem:load(p.name) for p in S.glob('MECHANISM_*.json')}
 def relabel(x):
  if isinstance(x,dict):return {('normalized_phase_time_fraction' if k=='public_phase_fraction' else k):relabel(v) for k,v in x.items()}
  if isinstance(x,list):return [relabel(v) for v in x]
  return x
 mechanisms=relabel(mechanisms)
 put('PHASE_SHAPE_POSITION_LABEL_CORRECTION.json',dict(old_field='public_phase_fraction',correct_field='normalized_phase_time_fraction',meaning='(actual physics time - actual phase start)/(actual phase duration); NOT native target public progress',numeric_values_unchanged=True,frozen_evaluation_unchanged=True,original_derived_files_preserved=True))
 put('LOW_FORCE_MECHANISM_DATA.json',dict(mechanisms=mechanisms,interventions=[r for r in dev if r['id'].startswith('mechanism')],historical=history))
 from lineage_audit import build as change_audit
 changes=change_audit();mixed=[r['id'] for r in changes if r['pure_phase_isolation'] is False]
 repair_summaries=[]
 for seed in baseline:
  rr=[r for r in new if catalog.get(r['candidate_id'],{}).get('parameters',{}).get('source')==seed['candidate_id']]
  if not rr:continue
  feasible=[r for r in rr if r['comparison']['acceptance_pass']];picked=max(feasible,key=lambda r:r['comparison']['gain_percent']) if feasible else min(rr,key=lambda r:r['continuous_constraints']['worst_ratio']);gain=seed['comparison']['gain_percent']
  repair_summaries.append(dict(seed=seed['candidate_id'],seed_gain_percent=gain,repair=picked['candidate_id'],repair_gain_percent=picked['comparison']['gain_percent'],motion_pass=picked['comparison']['acceptance_pass'],force_gain_retained_percent=100*picked['comparison']['gain_percent']/gain if abs(gain)>1e-12 else None,worst_constraint_seed=seed['continuous_constraints']['worst_ratio'],worst_constraint_repair=picked['continuous_constraints']['worst_ratio'],actual_execution_before=seed['actual_execution_signature'],actual_execution_after=picked['actual_execution_signature']))
 put('REPAIR_CHAIN_SUMMARY.json',dict(rows=repair_summaries,selection='highest-gain feasible per seed, otherwise least worst violation; all other candidates retained'))
 mechanism_text='# 强低力机制：证据与边界\n\n'+table(baseline)+'\n'
 mechanism_text+='实际图只在原生目标请求处采样一次，反对称改变髋膝相对阶段进度；不是按时间连续播放的参考轨迹。负 RETURN delta 让膝在阶段方向领先、髋延后。原生 B 仍决定物理分段、准入、续跑和 fallback。\n\n'
 for name,mm in mechanisms.items():
  for r in mm['rows']:
   top=sorted(r['bins'],key=lambda b:-b['gain_N_s'])[:3];mechanism_text+=f"- {r['id']}：完整收益 {r['gain_percent']:.6f}%；最大三段降力贡献为 "+'；'.join(f"{b['start_s']:.2f}–{b['end_s']:.2f}s：{b['gain_N_s']:.3f}N·s" for b in top)+'。速度/加速度超限与降力重合量见 JSON；这是关联。\n'
 mechanism_text+='\n同父状态仅取消／缩放一个 slot 的比较属于干预证据；其估计的是包括后续原生重新规划在内的总效应。相邻 slot 参数不变不等于之后实际执行时序不变。两个 phase 的未执行收益不相加。逐 slot 幅度、接受值、receipt 与连续负担量均在 REPAIR_LINEAGE 和各 MECHANISM JSON。没有把曲线相邻解释成接触机制因果。\n\n旧强参考的 K3 参数已恢复；原始 trace/summary 存在，密集 native artifact 已报告化，不能完整重算旧 native 运动峰值。旧 1348.371552 N·s 不与新 B 相减；新的 Historical_E_replay 另作同条件完整比较。用户所谓“救济线”具体身份仍未推断。\n'
 mechanism_text+='\nREGISTERED_CHANGE_AUDIT.json 从实际注册 values／knots／support／slot 对比还原所有参数改变，不能只凭简写 operation 宣称单变量。以下被简写为 phase_isolation 的条目还同时缩放了保留相位的一项，按复合干预处理，排除纯 O/R 因果拆分：'+(', '.join(mixed) or '无')+'。保留原参数与执行结果，未改评分或重跑。\n'
 mechanism_text+='\n位置标签分析纠正：早期机制 JSON 的 public_phase_fraction 实际是原协议形状计算的归一化阶段时间，已在合并数据中改名 normalized_phase_time_fraction；原文件保留。它不等于请求的公共进度 m。形状数值、力积分、运动统计及原接受条件均未改变。\n'
 md('LOW_FORCE_MECHANISM.md',mechanism_text)
 report='# 强低力运动修复与再探索\n\n'
 report+='我们保持完整去程、停留和回程，以及原来的安全与原生控制合同，研究能否保留较大降力并减少额外运动负担。降力与运动负担始终分别评价，没有修改评分或缩短任务。\n\n'
 report+='原来的强降力动作改变了髋膝相对运动的次序与分配。取消一个前段调整不一定减轻负担；有些 RETURN 调整放大后反而同时保留更多降力、降低部分负担。问题不等同于一个孤立尖峰，需要检查整个后续原生运动。当前证据说明哪些固定调整产生总效应，仍不能凭波形相邻认定具体接触或惯性机制。\n\n'
 report+=f"本轮实际新增 {len(starts)}/300 次物理 attempt，完整任务 {completed}，新增 native 步 {total_steps}，新增物理时间 {physical_s:.3f}s（扣除 fork 继承前缀），实际非零执行 attempt {active_actions}。开发中观察到 {len(signatures_dev)} 个不同非零完整执行序列；这不是相同数量的独立人体或全局动作族。所有重型运行串行。\n\n"
 if best:report+=f"最好新合格方案为 {best['candidate_id']}，开发完整力积分比同条件 B 降低 {maxdev:.6f}%；比 C4 的额外收益见下表。{'已超过2%探索里程碑。' if strong2 else '仍没有达到2%探索里程碑，研究性能仍不足。'} {'达到5%探索里程碑。' if strong5 else '没有5%合格开发证据。'}\n\n"+table([best])
 else:report+='未找到新的运动合格且降力至少0.5%的方案，不能将低积分但超负担的结果包装成成功。有限搜索失败也不构成全局无解证据。\n\n'
 if best and maxdev<1:report+='新合格收益仍只有零点几，不能据此宣布研究性能充分成功。\n\n'
 if best and best.get('extra_gain_vs_C4_N_s',0)<=0:report+='该新合格点未优于现有 C4_1_5，不能称为当前性能进展。\n\n'
 report+=f'{status}。科学状态：{science}；性能状态：{perf}；部署资格未获得。技术 PASS 不等于临床轨迹等效或实时个体化。\n\n'
 report+='\n新保留条件仍是同一已知 Human 的合法前缀扰动；H1/H2 已暴露，没有作为新测试。候选在读取 V 条件结果前冻结。\n\n'+table(val)
 report+='\n各修复链实际保留的收益与负担变化：\n\n'
 for r in repair_summaries:report+=f"- {r['seed']} → {r['repair']}：收益 {r['seed_gain_percent']:.6f}% → {r['repair_gain_percent']:.6f}%，保留原降力收益 {r['force_gain_retained_percent']:.2f}%；最严重连续约束比 {r['worst_constraint_seed']:.4f} → {r['worst_constraint_repair']:.4f}，motion {'PASS' if r['motion_pass'] else 'FAIL'}。\n"
 report+=f"\n具有不同实际 q/dq 父状态的保留条件数为 {distinct}/3。新候选通过全部三个保留条件：{', '.join(validated) or '无'}。全部三个条件均 ≥2%／≥5%：{valid2}／{valid5}；单个保留配对中运动合格且 ≥2%／≥5%的次数：{individual2}／{individual5}。逐条件完整安全、任务及 motion 分母见 SEARCH_AND_VALIDATION.json。重复运行只检验数值重现，不计独立样本。\n\n"
 for cid,v in summaries.items():
  if v['gain_mean_percent'] is not None:report+=f"- {cid}：保留收益平均 {v['gain_mean_percent']:.6f}%，最差 {v['gain_worst_percent']:.6f}%；资格通过 {v['qualification_pass_count']}/{v['attempted_denominator']} 次实际尝试（完整比较 {v['denominator']}）；逐项最严重连续约束比 {v['worst_continuous_constraint_ratio']:.6f}。\n"
 report+='强低力来自髋膝相对姿态及其后续原生运动改变；当前证据可定位贡献区间与 slot 总效应，但不能仅由相邻曲线判定接触状态或“更快经过高力区”是因果来源。详细负担持续区间、相位形状最大偏差及贡献分解见 LOW_FORCE_MECHANISM.md 和数据 JSON。Motion PASS 仍不代表治疗轨迹等效；jerk max 始终只是诊断。\n\n'
 report+='Moment integral 只是力矩范数的时间积分，不是动量，也不能据此认定临床不适。原始真实速度／导数用于硬验收，SG5／21仅作原有敏感性对照。\n\n'
 report+='当前不建议因为技术 PASS 就开训 Neural Q。应先审核强收益是否跨新的合法条件保持合格，并决定相对髋膝姿态变化的治疗意义。Teacher 只准备数据，完整策略、fork 后续价值与实际局部决策分别编码。任何未来执行值、未来最大加速度与 remaining force 都是标签，不能进入当前输入；旧全零 raw_v2 action 占位符不作为动作。\n\n'
 report+='教授最需看三项证据：强种子的完整力累积与真实运动峰值；同 slot 干预后的收益保留与违反量；冻结候选在新合法前缀上的配对结果。三个问题：允许哪些 phase-shape 改变；10%运动非劣及剂量门槛依据如何与康复目标对应；在现有反对称目标接口中继续搜索还是单独授权一个更自由参考对照。\n\n'
 report+='没有执行更自由 controller 对照：有限原生搜索未证明某动作必不可表达；不以失败推断物理不可能。不训练、不在线适应、不做正式 host-clock 或硬件测试。模型、人体系、B、commissioning、estimator、安全、时长、issued slots、40ms bridge、100ms生命周期与准入未作语义改变。\n\n'
 report+='保护验证只覆盖明确列出的 Git 状态与复用冻结源码／模型文件，不声称全历史字节未变。未执行 Git 写入、系统维护或历史删除。命令和版本可见 PROTOCOL_AND_ATTEMPTS.json；失败与停止理由见 PACKAGE_VERIFICATION.json。\n\n产物：LOW_FORCE_MECHANISM.md、REPAIR_LINEAGE.jsonl、SEARCH_AND_VALIDATION.json、TEACHER_DATA_INDEX.md、PROFESSOR_BRIEF.md、PACKAGE_VERIFICATION.json。全部完成后 STOP，无自动下一轮。\n'
 report+='\n发生两次机械包装错误：漏复制冻结候选池输入、决策日志取错 reference 接口字段；各自保留失败输出，在原时间／attempt账本下完成零动作、父状态及 C4 重现检查，未修改动作、阈值或 B。另有一项来源分组分析纠正：M2 原始文件 provenance 曾被误当作链 ID，第一修复批未引用已改善的 M2 消融；纠正链分组后，后续按原排名规则选择中心。原计划数值及原评价结果保留，没有为此补跑物理。不能把这类运行失败或分析限制藏在一个 PASS 中。\n'
 md('REPORT.md',report)
 teacher=lines('TEACHER_COMPACT.jsonl');md('TEACHER_DATA_INDEX.md',f'# Teacher 数据索引\n\n本轮不训练。紧凑表 TEACHER_COMPACT.jsonl 有 {len(teacher)} 条完整策略／fork 后续价值记录；局部执行以独立原生 receipt 引用。失败标签在 SEARCH_AND_VALIDATION 与 ATTEMPTS，短程积分不作正常回归目标。\n\n当前输入来源：决策当时 causal55D observation、phase/public progress、model_hash、K3历史与 issued index；55D含估计人体状态及模型参数。动作从 graph/registered_spec 或真实 K3 表读取；raw_v2全零 action是占位，不是执行动作。完整策略不转换为旧120D单步Q动作。carry、issued history/count/mask 和估计 beta/residual 在对应 SNAPSHOT 的 interface_scientific_state／native manifest；需保持与当前决策时间对齐，未来receipt仅用于标签审计。当前输入与真实状态审计通道分开。\n\n固定 PWL/table 续跑由 B 原生规划 segments、carry/fallback；Frozen_M2 是旧冻结 Q 滚动重选，分账。完整 TASK left quadrature 与 fork 时已发生 prefix 积分分别定义 full 与 remaining 标签。相同完整父状态重建 gate 与原生 fork实现保留；父进程退出后哈希／JSON不恢复活对象，不能称可独立checkpoint。唯一重建代码、协议、seed与合法prefix保存在 code、SEARCH_PROTOCOL 与 queue。训练／验证未来必须按 parent、condition、source分组隔离；V1–V3不能转为开发样本后仍声称未见测试。\n')
 from local_labels import build
 local=build();put('LOCAL_DECISION_INDEX.json',local)
 with (S/'TEACHER_DATA_INDEX.md').open('a') as f:f.write(f"\nLOCAL_EXECUTED_DECISIONS.jsonl 有 {local['rows']} 条实际执行局部决策。剩余力积分按原 TASK trace 在实际 proposal time 剪裁所有 left-quadrature 区间；不复用导数去重索引。这是已观察的固定后续规则价值，不是单步 Q^B，不能当作已做独立局部反事实。未来接受值／receipt 和实际 native steps 全在 label_only；当前 action_input 保留真实 graph/spec／K3 编码。\n")
 with (S/'TEACHER_DATA_INDEX.md').open('a') as f:f.write('\nTEACHER_CURRENT_INPUTS.jsonl 提供新增探索决策的逐时刻估计 observation、beta／residual、issued count／mask、已 issued graph 历史、前次合法 graph／coordination carry。读取发生在本次动作选择之前；未把未来 receipt 和 realized delta 放入当前输入。full_capture_available=false 的初期复现／Frozen_M2 记录仍保留，但不能当作完整部署输入训练样本。snapshot 里的 ndarray 哈希只审计身份，不能替代数值输入。\n')
 brief='# 教授商讨：约六页内容提纲\n\n'
 topics=[('1 研究问题','希望机器人依据人体状态与特性，协调安全、平顺、低力运动，未来再追求实时个体化。当前完整去程—停留—回程保持不变，不以积分排名替代治疗目标。'),('2 已建立的能力',f'活进程完整状态 fork、零动作／同动作重现、因果输入与原生receipt归属、完整力积分及dense真实运动核验。本轮{len(starts)}次attempt；host与硬件资格仍未获得。'),('3 强低力为什么不直接用','7%–15%降力常伴膝速度／加速度、幅度、tracking等额外负担。当前0.74%点只执行一个RETURN slot，但phase-shape仍可明显改变。展示 force累积、真实knee负担和实际delta。'),('4 本轮修复证据',f'开发最好合格收益：{maxdev}%；三个新父条件验证通过方案：{validated}。展示种子→仅改一个slot→实际接受与执行→收益保留比例→最严重违反量。所有负结果保留。'),('5 障碍与能力边界','搜索覆盖有限，raw图只在nominal target请求采样；调平图不保证真实运动平顺。motion标准的治疗依据与phase-shape意义未定。已有结果不区分全局物理权衡与接口／局部搜索限制；不凭失败认定无解。'),('6 需要教授决定','三个问题：治疗允许的相对姿态／phase-shape范围；评价依据（速度、加速度、jerk、剂量与tracking）如何冻结；下一步继续原生表达，还是单独授权最小参考自由度离线对照。推荐下一步：审核最有信息的slot干预及冻结验证，再设计一个能区分接口限制与物理权衡的实验。')]
 for title,body in topics:brief+='## '+title+'\n\n'+body+'\n\n'
 md('PROFESSOR_BRIEF.md',brief)
 # Five clear static figures, separate units and axes.
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 plt.rcParams.update({'font.size':9,'axes.grid':True})
 figdir=S/'figures';figdir.mkdir(exist_ok=True)
 reps=[r for r in baseline if r['candidate_id'] in ['C4_1_5','C2_pair_1_2','Frozen_M2']]
 if best:reps.append(best)
 fig,ax=plt.subplots(figsize=(8,4.5))
 for ident in ['baseline_B0_repeat_1']+[r['id'] for r in reps]:
  p=S/'source/results'/ident/'trace.npz'
  if not p.exists():continue
  with np.load(p) as z:ix=z['stage']=='TASK';t=z['time_s'][ix];f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);cum=np.r_[0,np.cumsum(f[:-1]*np.diff(t))]
  ax.plot(t,cum,label=ident)
 ax.set(xlabel='Absolute physics time (s)',ylabel='Full TASK cumulative cuff force (N s)',title='Matched known Human; original TASK left quadrature');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'force_cumulative.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(2,1,figsize=(8,6),sharex=True)
 for ident in ['baseline_B0_repeat_1']+[r['id'] for r in reps]:
  p=S/'motion_series'/(ident+'.npz')
  if not p.exists():continue
  with np.load(p) as z:axs[0].plot(z['time_s'],np.rad2deg(z['true_dq_rad_s'][:,1]),label=ident);axs[1].plot(z['time_s'],np.rad2deg(z['acceleration_rad_s2'][:,1]),label=ident)
 axs[0].set(ylabel='True knee speed (deg/s)',title='Raw native motion; matched known Human');axs[1].set(xlabel='Absolute physics time (s)',ylabel='True knee acceleration (deg/s^2)');axs[0].legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'knee_motion.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(8,4.5))
 for r in reps:
  xx=[];yy=[]
  for ph,di,met,t,n in r['actual_execution_signature']:
   xx.append(t);yy.append(met[0].get('delta',0))
  ax.scatter(xx,yy,label=r['id'])
 ax.set(xlabel='First actual native execution time (s)',ylabel='Native accepted differential (normalized progress)',title='Actual activated nonzero plans; original issued slots');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'actual_execution.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(8,4.5))
 for stage in sorted({r['stage'] for r in dev}):
  rr=[r for r in dev if r['stage']==stage];ax.scatter([r['continuous_constraints']['worst_ratio'] for r in rr],[r['comparison']['gain_percent'] for r in rr],s=18,label=stage)
 ax.axvline(1,color='black',ls='--');ax.axhline(2,color='grey',ls=':');ax.axhline(5,color='grey',ls=':');ax.set(xlabel='Worst normalized motion constraint (guidance, gate unchanged)',ylabel='Full TASK force gain vs matched B (%)',title='Known Human development; force and motion remain separate');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'repair_tradeoff.png',dpi=150);plt.close(fig)
 if val:
  fig,ax=plt.subplots(figsize=(8,4.5))
  for cid in sorted({r['candidate_id'] for r in val}):
   rr=[r for r in val if r['candidate_id']==cid];ax.plot([int(r['id'][1]) for r in rr],[r['comparison']['gain_percent'] for r in rr],marker='o',label=cid)
  ax.set(xticks=[1,2,3],xticklabels=['V1','V2','V3'],ylabel='Full TASK gain vs own matched B (%)',title='Frozen candidates; same known Human, new legal prefixes');ax.axhline(.5,color='grey',ls='--');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(figdir/'heldout_effect.png',dpi=150);plt.close(fig)
 md('FIGURES.md','# 静态图索引\n\n'+''.join(f'- [{p.name}](figures/{p.name})：来源为本包配对 TASK trace、dense native motion／receipt、开发及冻结 V 表。\n' for p in figdir.glob('*.png')))
 for n in ['REPORT.md','LOW_FORCE_MECHANISM.md','LOW_FORCE_MECHANISM_DATA.json','PROFESSOR_BRIEF.md','TEACHER_DATA_INDEX.md','TEACHER_COMPACT.jsonl','SEARCH_AND_VALIDATION.json','PROTOCOL_AND_ATTEMPTS.json','REPAIR_LINEAGE.jsonl','PACKAGE_VERIFICATION.json','INDEPENDENT_DERIVED_CHECKS.json','SEARCH_PROTOCOL.json','HISTORICAL_E_RECOVERY.json','FIGURES.md']:
  if (S/n).exists():shutil.copy2(S/n,W/n)
 for n in ['TEACHER_CURRENT_INPUTS.jsonl','REPAIR_CHAIN_SUMMARY.json']:
  if (S/n).exists():shutil.copy2(S/n,W/n)
 for n in ['LOCAL_EXECUTED_DECISIONS.jsonl','LOCAL_DECISION_INDEX.json']:
  if (S/n).exists():shutil.copy2(S/n,W/n)
 shutil.copy2(S/'REGISTERED_CHANGE_AUDIT.json',W/'REGISTERED_CHANGE_AUDIT.json')
 shutil.copy2(S/'PHASE_SHAPE_POSITION_LABEL_CORRECTION.json',W/'PHASE_SHAPE_POSITION_LABEL_CORRECTION.json')
 shutil.copytree(figdir,W/'figures',dirs_exist_ok=True)
 put('FINALIZED.json',dict(unix=time.time(),work_status=status,science=science,performance=perf,windows_delivery=str(W),attempts=len(starts),best_gain=maxdev,validated=validated))
 print(json.dumps(load('FINALIZED.json'),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
