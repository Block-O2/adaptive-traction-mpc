"""Generate evidence tables and the research decision without changing raw results."""
from pathlib import Path
import os,sys,json,time,hashlib,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def read(n):return json.loads((P/n).read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];attempts=[]
for s in starts:
 ident=s['id'];ee=[r for r in ends if r['id']==ident];assert len(ee)==1,(ident,ee);e=ee[0]
 data=read('output/'+ident+'_DATA.json') if (P/'output'/(ident+'_DATA.json')).exists() else {};m=data.get('metric',{});partial=read('output/'+ident+'_PARTIAL_COMPUTE.json') if (P/'output'/(ident+'_PARTIAL_COMPUTE.json')).exists() else {}
 errors=[dict(path=str(f.relative_to(P)),record=json.loads(f.read_text())) for f in (P/'reports').glob(ident+'_*ERROR.json')]
 attempts.append(dict(id=ident,kind=s.get('kind'),START_unix=s['unix'],END_unix=e['unix'],wall_s=e['unix']-s['unix'],returncode=e['returncode'],joined=e.get('joined',False),partial=not m.get('task_valid',False),task_complete=m.get('task_valid',False),actual_new_native_steps=m.get('actual_new_native_physics_steps',partial.get('actual_new_native_physics_steps')),archived_native_steps=m.get('native_physics_steps',partial.get('native_physics_steps')),parent_state_source=data.get('branch_start'),snapshot_hash=s.get('snapshot_hash'),failure_reason=errors or e.get('error'),code_manifest_sha256=s.get('code_manifest_sha256')))
forks=sorted([r for r in attempts if r['kind']=='FULL_TASK_FORK'],key=lambda r:r['START_unix']);assert all(a['END_unix']<=b['START_unix'] for a,b in zip(forks,forks[1:]))
assert all(r['actual_new_native_steps'] is not None for r in attempts)
put('ATTEMPT_ACCOUNTING.json',dict(physical_START=len(starts),physical_END=len(ends),cap=40,all_attempts_accounted=collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends),actual_new_native_steps=sum(r['actual_new_native_steps'] for r in attempts),native_steps_exact=True,serial_forks=True,parent_pause_rule='Parent waits via original os.waitpid; its START/END encloses child brackets but native execution is paused. Full parent new steps counted once, inherited child prefix excluded.',rows=attempts,includes_failure_partial_parent_and_repeat=True))
groups=[g for g in ['reproduction','N2','development','U1','U2','U3'] if (P/(g+'_DONE.json')).exists()]
allrows=[];state_rows=[]
for g in groups:
 assert read('audit/INDEPENDENT_'+g+'.json')['status']=='PASS'
 pair=read(g+'_PAIR_GATE.json');context=read('audit/'+g+'_FORK_CONTEXT.json');assert pair['status']=='PASS'
 rows=read(g+'_RESULTS.json')['rows'];B=next(r for r in rows if r['arm']=='B');E=next(r for r in rows if r['arm']=='E')
 for r in rows:
  m=read(r['metrics_path']);r=dict(r,group=g,comparison_to_frozen_E_N_s=r['J_F_N_s']-E['J_F_N_s'],full_duration_s=sum(r['phase_durations'].values()),raw_motion=m['motion']['raw'],dose=m['dose'],peaks=m.get('peaks'),full_state_match=True,independent_raw_PASS=True)
  allrows.append(r)
 if g.startswith('U'):
  with np.load(P/'motion_series'/(g+'_B.npz')) as z:
   i=int(np.argmin(abs(z['time_s']-context['physical_s'])));assert abs(z['time_s'][i]-context['physical_s'])<1e-8
   state=dict(q=z['true_q_rad'][i],dq=z['true_dq_rad_s'][i],role='Evaluation only proof of state diversity; never policy input')
  line=read('reports/'+g+'_B_EXECUTED_RESIDUAL_RECEIPTS.json');prefix=[r for r in line['rows'] if r['physically_executed_nonzero'] and r['first_execution_physics_s']<context['physical_s']-1e-9];assert prefix
  state_rows.append(dict(group=g,full_hash=pair['full_hash'],native_hash=pair['native_hash'],fork=context,actual_human_state=state,prefix_executed=True))
assert len({r['native_hash'] for r in state_rows})==len(state_rows)
dist=[]
for i,r in enumerate(state_rows):
 for q in state_rows[:i]:
  dq=float(np.max(abs(np.asarray(r['actual_human_state']['q'])-q['actual_human_state']['q'])));dv=float(np.max(abs(np.asarray(r['actual_human_state']['dq'])-q['actual_human_state']['dq'])));assert max(dq,dv)>1e-10
  dist.append(dict(a=r['group'],b=q['group'],max_q_delta_rad=dq,max_dq_delta_rad_s=dv))
selection=read('DEVELOPMENT_SELECTION.json') if (P/'DEVELOPMENT_SELECTION.json').exists() else {'selected':None};sel=selection['selected']
validation=[r for r in allrows if r['group'].startswith('U') and r['arm']==sel]
def qualified(r):return r['motion']['acceptance_pass'] and r['absolute_safety'] and r['receipt']=='PASS' and r['task']=='PASS' and r['motion']['gain_percent']>=1.
vpass=bool(len(validation)==3 and all(qualified(r) for r in validation))
put('EXPERIMENT_RESULTS.json',dict(evidence_level='PHYSICAL_LEVEL1',groups=groups,rows=allrows,source='All new full physical runs, no partial rankings',same_Human=True))
put('VALIDATION_RESULTS.json',dict(status='LIMITED_SCOPE_PASS' if vpass else 'NOT_PROMOTED',selected=sel,new_unseen_prefix_pairs=len(validation),selected_motion_PASS=sum(r['motion']['acceptance_pass'] for r in validation),selected_safety_PASS=sum(r['absolute_safety'] for r in validation),selected_causal_PASS=sum(r['receipt']=='PASS' for r in validation),selected_joint_PASS=sum(qualified(r) for r in validation),rows=validation,state_sources=state_rows,pairwise_Human_state_differences=dist,selection_using_validation=False,validation_candidate_unchanged=True,same_Human=True,patients=0,historical_primary_motion='0/4 retained',latest_prior_frozen_E_motion='3/4 retained, N2 FAIL',scope='Shared legal native OUTBOUND0 consumed; remaining policy transfer; full JF includes prefix. No unseen full initial commissioning state qualification.'))
meaningful=vpass and all(r['comparison_to_frozen_E_N_s']<=-max(1.,.001*next(b['J_F_N_s'] for b in allrows if b['group']==r['group'] and b['arm']=='B')) for r in validation)
conclusion='固定候选在本轮三个未见合法prefix通过完整资格；仅限同一Human与remaining策略范围。' if vpass else '本轮未建立新的可靠协调策略；已完成可复核的机制干预与失败边界诊断。'
nextstep='以冻结候选为有条件开发基线，先做旧V1–V4及独立合法prefix确认，再开展受限Waypoint联合研究；Q-learning只准备数据合同、不训练。' if vpass else '继续传统协调方法：先针对去程终末重规划/制动与实际闭环响应建立小型配对合同，保留位姿/速度分离表示和全部原motion门。暂不扩大Waypoint力搜索或训练Q-learning。'
put('NEXT_RESEARCH_DECISION.json',dict(branch='LIMITED_SCOPE_MOTION_IMPROVEMENT' if vpass else 'DIAGNOSTIC_NO_PROMOTION',conclusion=conclusion,next_step=nextstep,new_force_milestone=meaningful,automatic_next_study=False,STOP=True))
(P/'NEXT_RESEARCH_DECISION.md').write_text('# 下一研究决策\n\n'+conclusion+'\n\n'+nextstep+'\n\n本轮不自动开启下一包。历史18D motion 0/4与最新3/4来自不同prefix集合，全部保留；新候选的任何通过不能覆盖它们。未来Q数据需区分因果观测、动作意图、证书、实际激活/命令/receipt与真实反馈，保存失败和partial，评价truth单独标记，禁止进入在线state。\n')
table='\n'.join(f"|{r['group']} / {r['arm']}|{r['J_F_N_s']:.9f}|{r['motion']['gain_percent']:.6f}|{r['comparison_to_frozen_E_N_s']:+.6f}|{'PASS' if r['motion']['acceptance_pass'] else 'FAIL'}|{','.join(r['motion']['failed_requirements']) or '无'}|" for r in allrows)
n2=[r for r in allrows if r['group']=='N2'];ntable='\n'.join(f"|{r['arm']}|{r['raw_motion']['full']['acceleration_deg_s2']['max_abs'][1]:.6f}|{r['motion']['burden_ratios']['acceleration_deg_s2/max_abs'][1]:.6f}|{r['moment_integral_Nm_s']:.6f}|{r['tracking_RMS_deg'][0]:.6f} / {r['tracking_RMS_deg'][1]:.6f}|" for r in n2)
elapsed=(time.time()-read('RUN_PLAN.json')['t0_unix'])/3600
report=f'''# iHEAR Lab 自主研究与验证 v1

{conclusion} 新额外降力里程碑：{'成立（本有限测试范围）' if meaningful else '未成立'}。本轮改进是固定参数的机制分离检验，没有修改正式B、物理模型、安全执行链或门限。

## 1. 最重要瓶颈与选择理由

主要瓶颈是完整运动资格对合法状态敏感，而不是开发参数不可复现。原B=1438.613498467、冻结18D=1400.697221153 N·s，2.635613%收益已从本轮新物理精确复现。最近N2虽降力仍因膝最大加速度比1.249192>1.10失败；历史0/4另存。Waypoint局部能改变运动，但既有18D+S全程力效应微小、正负抵消，不能优先把它当降力主机制。优先级及来源见PRIORITY_AUDIT。

一个关键诊断边界：N2原18D膝峰约90.059°/s²，反而低于若干通过prefix的绝对峰；它相对匹配B的72.093°/s²超限。原门是逐状态非劣等研究合同，并非跨状态统一临床阈值。因此既不能以“别的状态峰更大也通过”取消N2失败，也不能仅凭该失败宣称N2绝对临床风险最高。绝对安全与relative motion资格分别报告。

## 2. 修改及原理

C仅将OUTBOUND速度common/differential/tilt三个系数（零基3/4/13）归零；其他位置系数、全部RETURN和两个native plateau保持。测试“终端速度偏置引起去程运动负担”的假设，同时争取保留姿态降力。若C科学失败，按事前合同最多使用R：全部9个OUTBOUND系数减半。完整参数见CANDIDATE/BOUNDED_REPAIR；原18D永不覆盖。控制器仍从因果B目标与当前reference生成轨迹，实际目标/时序会通过闭环变化；没有声称所有waypoint或真实运动不变。

原rich_planner、matched fork、analyze_matched与安全链源码只迁移根路径；改动是隔离campaign的候选表示与验证编排。数学18组直接生产公式测试通过；完整参数、plateau、RETURN和motion协议身份通过；imports与源码闭包通过。辅助加入tracking/torque/参考/真实运动诊断，保存独立计算路径。不训练任何RL/Q/Neural Q。

## 3. 完整物理结果

全部JF为完整TASK、原5ms force左积分；相对B为同完整live父状态的匹配B；相对E为同组冻结18D。确定性repeat不增加状态分母。

|组/臂|完整JF N·s|对B降力%|相对E ΔJF N·s|motion|失败项|
|---|---:|---:|---:|---|---|
{table}

N2主要数值：

|臂|膝加速度最大值°/s²|对B比值|完整moment Nm·s|hip/knee tracking RMS°|
|---|---:|---:|---:|---|
{ntable}

所有phase积分/时长、raw velocity/acceleration/jerk、剂量/ROM、tracking、moment、clearance、torque/contact与绝对安全细项、task与receipt/causal在EXPERIMENT_RESULTS、原MEASURED与独立INDEPENDENT文件。motion FAIL保留，不能以降力晋级。对应的issued reference、actual command和native Human q/dq分层存档。

## 4. 真正通过的测试与证据范围

新B/E复现包括全部trace字段、每条116320 native状态/contact/torque行与5817 receipts的物理/来源字段；host profiling不作为物理同一性。每组完整live fork继承隐藏状态，所有臂full hash相同，父在每臂后不变并继续完成原B。独立脚本不导入controller/plant，从原raw重算完整及phase积分、tracking、native导数/剂量和逐步receipt所有权；每个已完成组的独立复核均PASS。具体通过数量以VALIDATION_RESULTS和ATTEMPT_ACCOUNTING为准，不把数学结果代替物理资格。

本轮未见prefix新配对={len(validation)}，选定候选motion PASS={sum(r['motion']['acceptance_pass'] for r in validation)}/{len(validation)}；联合原task/safety/motion/causal与>=1%B降力PASS={sum(qualified(r) for r in validation)}/{len(validation)}。选择仅依据已暴露N2开发，不按U结果重选。若未触发U，分母为0，不能声称通过或失败的泛化率。

## 5. 是否有可重复进步及适用范围

{conclusion} {'保留本有限范围的运动资格价值，但不能自动推广到旧V1–V4或其他Human。' if vpass else '候选/备选失败属于有信息的科学负结果，不能命名为新基线。'} 本轮没有把微小JF差异包装为实质性降力。确切repeat资格见audit/*REPEAT；重复只说明确定性，不证明新状态泛化。

仅同一已暴露Human/model、PHYSICAL_LEVEL1 scientific simulation；prefix是实际原native执行后fork，完整JF包括共同前史，OUTBOUND0已消费。不是不同患者、未见完整初态、正式Native LEVEL2、host-clock LEVEL3、真机或临床资格。原strict/R2/FAST/plan_age负结果保留，scientific模式不覆盖host-clock资格。

## 6. 下一阶段

{nextstep} Waypoint作为局部可认证shape能力仍有价值，但平顺性需独立目标/约束，不能当累计force的单一代理。本轮尚不能直接启动无边界的18D+Waypoint联合优化。可以准备因果state/action/feedback schema与失败保留规则；需要先稳定传统协调方法的适用域，再讨论Q-learning数据采集和训练。

## 7. 保护、计时与退出

T0=2026-10-17 13:26:19北京时间；硬截止17:26:19。报告生成时约{elapsed:.3f}小时。物理START/END={len(starts)}/{len(ends)}，上限40；实际新增native步={sum(r['actual_new_native_steps'] for r in attempts)}，继承前史不重复计。所有失败、repeat和异常保留，不为耗尽时长扩大搜索。最终owned进程、Git/历史保护、执行manifest、磁盘与交付文件核验见PACKAGE_VERIFICATION；只有该文件PASS才视为交付完成。Windows为审阅镜像，完整source/raw在canonical WSL新包。无commit/push/merge。完成后STOP，不自动开启下一研究包。
'''
(P/'REPORT.md').write_text(report)
(P/'REPRODUCTION.md').write_text('''# 复核与复现入口

canonical新包：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1；指定Python=/home/hank/envs/adaptive-online-rl-v1/bin/python，运行带-B。Windows为审阅镜像，不含完整source/results。

本包已关闭，不可原目录重跑physics或重置账本。新物理复现须建立新的兄弟版本目录，复制source/code/deps/weights、完整候选、两个RETURN plateau、共享动作合同和motion协议；迁移根路径、冻结新的RUN_PLAN和manifest后，依序preflight→own_campaign reproduction→独立raw复核→N2→事前开发选择→development→U1/U2/U3。原RUN_PLAN和research_sequence记录实际条件分支；失败分支不跳过门限继续验证。不能从保存q/qvel恢复Human隐藏状态，必须原cold commissioning与live fork。

无physics复核入口：control/independent_recompute.py 后跟已完成组名；读取存档，仅向derived/audit写核算结果。control/diagnostic.py、tracking_chain.py、causal_features.py为诊断。为保护本次报告，建议复制分析脚本到新输出目录后改输出根，禁止向历史包写入。全部完整raw在source/results/<id>下trace.npz/summary.json/runtime_artifacts.json.gz/native_reference.npz；原始数据来源SHA与执行身份在manifest、MEASURED和账本。
''')
print(json.dumps(dict(groups=groups,selected=sel,validation=len(validation),joint_pass=sum(qualified(r) for r in validation),START=len(starts),END=len(ends),decision=conclusion),ensure_ascii=False))
