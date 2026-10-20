from pathlib import Path
import os,sys,json,time,hashlib,shutil,difflib,datetime,collections,subprocess
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
def load(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False))
def write(n,x):(P/n).write_text(x,encoding='utf-8')
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert load('PHYSICAL_VALIDATION.json')['status']=='PASS';assert load('audit/FINAL_PROTECTION_AND_EXIT.json')['status']=='PASS'
V=P/'versions/interface2';V.mkdir(exist_ok=True)
for n in ['EXECUTION_CODE_MANIFEST.json','PHYSICAL_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json','MATH_VALIDATION.json','P0_ZERO_PHYSICAL_GATE.json','PARENT_FORK_GATE.json','PHYSICAL_ARM_RESULTS.json','PHYSICAL_PROGRESS.json','PHYSICAL_DONE.json','NONZERO_REPEAT_GATE.json']:shutil.copy2(P/n,V/n)
records=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in records if r['event']=='START'];ends=[r for r in records if r['event']=='END'];assert len(starts)==len(ends)==10 and {r['id'] for r in starts}=={r['id'] for r in ends};assert all(r['returncode']==0 and r['joined'] for r in ends)
metrics={r['id']:r for n in ['versions/interface1/PHYSICAL_ARM_RESULTS.json','PHYSICAL_ARM_RESULTS.json'] for r in load(n)['rows']};auditrows=[]
for st in starts:
 ident=st['id'];end=next(r for r in ends if r['id']==ident);m=load('reports/'+ident+'_MEASURED.json');summ=load('source/results/'+ident+'/summary.json');obj=load('output/'+ident+'_REFERENCE_OBJECTS.json')['references'];issued=load('output/'+ident+'_ISSUED_REFERENCE.json')['rows'];line=load('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');group=ident.split('_')[0];manifest='versions/'+group+'/EXECUTION_CODE_MANIFEST.json';assert sha(P/manifest)==st['code_manifest_sha256'];d=load('output/'+ident+'_DATA.json');branch=d['branch_start'] or {};physical=m['native_physical_audit']['unchanged_evaluator']['physical_task_result']
 row=dict(id=ident,event='AUDIT',unix=time.time(),true_start_unix=st['unix'],true_end_unix=end['unix'],returncode=end['returncode'],joined=True,source_parent=group+'_parent' if not ident.endswith('_parent') else 'legal cold parent',fork_full_identity=branch.get('full_hash'),fork_native_identity=branch.get('native_hash'),parent_after_child_unchanged=end.get('parent_hash_equal'),source_manifest=manifest,code_model_config_manifest_sha256=st['code_manifest_sha256'],reference_ids=list(obj),certificate_ids=[v['certificate_id'] for v in obj.values()],applied_current_certificate_ids=sorted({x['current_certificate_id'] for x in issued}) if issued and 'current_certificate_id' in issued[0] else sorted({x.get('worker_certificate_id') for x in issued}),native_rows_total=m['native_steps'],actual_new_native_steps=m['actual_new_native_steps'],task=physical['status'],receipt=line['status'],motion=metrics[ident]['motion'] if ident in metrics else dict(acceptance_pass=True,kind='parent exactly equals original B'),J_F_N_s=m['J_F_N_s'],raw_host_scorer_pass=m['native_physical_audit']['unchanged_evaluator']['raw_scorer_v2']['pass'],source_age_scope='original scientific lifecycle/source versions; host qualification not met')
 # Applied current certificate hashes come from actual receipts, not proposed issue logs.
 from stream_runtime_evidence import array_items
 row['applied_current_certificate_ids']=sorted({x['multisegment_reference']['current_certificate_id'] for x in array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts') if 'multisegment_reference' in x and x.get('applied') and x.get('native_steps',0)>0})
 auditrows.append(row)
 if not any(x['event']=='AUDIT' and x['id']==ident for x in records):
  with (P/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
put('ATTEMPT_AUDIT.json',dict(status='PASS',START=len(starts),END=len(ends),budget=24,rows=auditrows,negative_motion_attempts=['interface1_knee_005'],all_physical_tasks_completed=True,all_joined=True))
put('PHYSICS_STOP.json',dict(status='STOP',unix=time.time(),reason='bounded interface qualification and independent audit complete; no further START, no force optimization, no training',START=10,END=10))
v=load('PHYSICAL_VALIDATION.json');response=v['responses'][0];nz=v['arms'][2];m=load('reports/interface2_knee_002_MEASURED.json');good=metrics['interface2_knee_002'];bad=metrics['interface1_knee_005'];math=load('MATH_VALIDATION.json');prot=load('audit/FINAL_PROTECTION_AND_EXIT.json');plan=load('RUN_PLAN.json');elapsed=time.time()-plan['t0_unix'];ref=load('output/interface2_knee_002_REFERENCE_OBJECTS.json')['references'];rid=next(iter(ref));record=ref[rid]
put('PHYSICAL_INTERFACE_GATE.json',dict(status='PASS_WITH_SCOPE_LIMITS',evaluation_level='PHYSICAL_LEVEL1',SOURCE_CONFIRMED=True,MATH_VERIFIED=True,INTERFACE_CERTIFIED='typed whole-path/current-admission test scope; original sampled mechanics scope retained',P0='PASS_EXACT_COMPLETE_PHYSICAL_TRACE',P1='PASS_NONZERO_CERTIFIED_ACTIVATED_ISSUED_APPLIED_HUMAN_RESPONSE',P2='PASS_COMPLETE_TASK_AND_FROZEN_MOTION_FAIRNESS',nonzero_demo='interface2_knee_002',repeat='interface2_knee_002_repeat',reference_id=rid,certificate_id=record['certificate_id'],actual_applied_receipts=nz['annotated_applied_receipts'],actual_owned_native_steps=nz['annotated_native_steps'],negative_example=dict(id='interface1_knee_005',task='PASS',motion='FAIL',failed=bad['motion']['failed_requirements']),repaired_issue='child-duration summary corrected; v1 raw/source preserved; no control or threshold repair',physical_START=10,physical_END=10,not_certified=v['not_certified'],NOT_A_FORCE_OPTIMIZATION_RESULT=True,STOP=True))
for dest in ['interface2_B0','interface2_zero_multi','interface2_knee_002','interface2_knee_002_repeat','interface1_knee_005']:
 d=P/'key_traces'/dest;d.mkdir(exist_ok=True)
 for name in ['trace.npz','summary.json','runtime_artifacts.json.gz']:
  link=d/name
  if not link.exists():link.symlink_to(os.path.relpath(P/'source/results'/dest/name,d))
 for suffix in ['REFERENCE_OBJECTS.json','ISSUED_REFERENCE.json']:
  shutil.copy2(P/'output'/(dest+'_'+suffix),d/suffix)
# Initial source closure stays available verbatim; final CODE_MANIFEST adds current state.
initial=load('CODE_MANIFEST.json');shutil.copy2(P/'CODE_MANIFEST.json',P/'audit/CODE_MANIFEST_INITIAL.json')
changed=[]
for row in initial['copied_files']:
 now=sha(P/row['path'])
 if now!=row['sha256']:changed.append(dict(path=row['path'],initial_sha256=row['sha256'],final_sha256=now))
expected={r['path'] for r in load('audit/INTERFACE_EDITS.json')['modified']};assert {r['path'] for r in changed}==expected,changed
initial.update(final_unix=time.time(),changed_after_copy=changed,new_reference_module='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py',new_reference_module_sha256=sha(P/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py'),execution_versions=[dict(path='versions/'+g+'/EXECUTION_CODE_MANIFEST.json',sha256=sha(P/'versions'/g/'EXECUTION_CODE_MANIFEST.json')) for g in ['interface1','interface2']],scope='source provenance and exact two isolated original-file changes; final all-file closure in PACKAGE_MANIFEST.json')
put('CODE_MANIFEST.json',initial)
for n in ['PATH_CERTIFICATION_REPORT.md','MULTISEGMENT_REFERENCE_CONTRACT.md','SELECTED_INTERFACE_DESIGN.md']:
 text=(P/n).read_text().replace('29项','30项');text+='\n最终版本：首批.05° motion失败，按预先声明顺序减为.02°通过；最终版仅重复.02°，不依force选择。子段record局部时长摘要修复、完整identity_payload和新增序列化测试见audit/SERIALIZATION_REPAIR.json；首版源码、测试和manifest在versions/interface1。\n';write(n,text)
# Human-readable attempt table includes all physical STARTs.
rows='\n'.join('|'+ '|'.join([r['id'],str(r['actual_new_native_steps']),r['task'],r['receipt'],'PASS' if r['motion']['acceptance_pass'] else 'FAIL',f"{r['J_F_N_s']:.9f}",f"{r['true_end_unix']-r['true_start_unix']:.1f}"])+ '|' for r in auditrows)
maxhuman=response['max_actual_trace_deltas']['evaluation_only_human_state_rad_rad_s'];maxhuman_deg=[x*180/3.141592653589793 for x in maxhuman];maxref=response['max_actual_trace_deltas']['reference_q_rad'];maxrobot=max(response['max_actual_trace_deltas']['cr12_actuator_command_nm'])
write('REPORT.md',f'''# 多段连续参考执行接口 V1：隔离资格结果

本轮打通了一个非零内部控制点的实际 MuJoCo 执行链，完成P0/P1/P2及一次同父状态重复。证据等级为 **PHYSICAL_LEVEL1（isolated scientific simulation）**；这不是正式B Native LEVEL2、host-clock LEVEL3或硬件资格。本轮没有优化force、没有训练、没有修改正式B。

## 开头十问

1. **旧接口为何拒绝？** 单段constructor要求2×6；4×2×6在shape检查即失败。旧continuous certificate、tracking-offset geometry和escape准备还绑定单一多项式/duration。旧负测试仍拒绝，未删除限制。
2. **rolling composite可否复用？** 可以。复用其40ms旧桥prefix、suffix局部时间、C2接续、activation及实际splice。它不会自动为任意多段suffix提供全路径资格。
3. **新增的最小能力？** 一个不可变MultiSegmentReference模块，加两处隔离消费分支：原escape完整准备后包装；activation对新类型做整路径current重验及实际每段shifted-path检查。系数、分区、模型/任务/phase/source和stop身份绑定hash。
4. **安全/current admission保留？** 原有安全规则和数学口径保留；每段新增解析ROM/v/a、边界C2、原连续geometry包络、跨节点20ms历史、原mechanics整体+逐段screen、future bridge/stop。原mechanics是采样检查，未宣称其连续未来wrench不变性。source age、100ms lifecycle和当前状态准入仍按原scientific模式执行。
5. **零修改物理等价？** 两组P0均PASS。最终组完整trace全部字段、116,320 native行的物理状态/torque/contact、5,817 receipts的物理/参考/来源字段精确一致。新对象没有折回旧载荷；只有系数身份已证明的零修改对象复用原全局求值核以避免浮点重参数化差。
6. **新增内部点有实际issued reference？** 有。第二个OUTBOUND请求的中间膝q +0.02°，四段总长1.27s、支撑[.3175,.9525]s；外部q/dq/ddq和时间不变。实际激活后{nz['annotated_applied_receipts']}条正native-step receipt携带同一认证对象的样本；独立系数重建与receipt q/dq一致。
7. **真实机器人—人体响应？** 有。同完整父状态、同前史，原FAST/allocator输出经原MuJoCo执行，{nz['annotated_native_steps']}个native子步与这些receipt唯一归属且torque完全一致。相对zero multi，实际Human q最大变化hip/knee约{maxhuman_deg[0]:.6g}/{maxhuman_deg[1]:.6g}°，dq约{maxhuman_deg[2]:.6g}/{maxhuman_deg[3]:.6g}°/s；robot各轴torque最大差{maxrobot:.6g}Nm。这些来自真实存档状态，不是计划意图。
8. **完整任务/motion通过？** 最终.02°及重复均完成OUTBOUND/HOLD/RETURN，原scientific物理task、绝对安全、motion/fairness、receipt均PASS；完整物理trace重复精确一致。原任务phase时长9.005/1.020/9.005s不变。首批.05°任务/安全PASS但motion FAIL，保留其负结果。
9. **尚未证明什么？** host-clock实时资格（原始host scorer的plan_age仍FAIL）、正式Native LEVEL2、连续真实wrench/未来tracking-error不变集、硬件/临床、未见模型/患者及任意轨迹族。当前certificate hash记录于applied receipts，但该日志未保存其完整current certificate内容供独立重算；worker certificate和reference完整内容/hash已独立重建。
10. **是否具备下一轮低力优化前提？** 在这个冻结任务/模型/父状态和已测试的局部自由度内，合法非零执行这一前提已成立。还不构成任意连续动作空间可优化或跨条件安全资格；后续需另行定义有界动作族、验证范围和预算。本轮STOP，不自动开始搜索。

## 物理证据与全部结果

T0 2026-10-15 12:45:19中国时间；总计10 START/10 END，包含两个合法冷父进程及全部fork，24上限未用满。物理均串行、个体timeout600s；本轮报告生成时距T0约{elapsed/60:.1f}分钟，成功后提前停止，无需耗尽建议时长。

|attempt|实际新增native steps|物理TASK|receipt|motion|J_F N·s（仅审计）|START至END墙钟s|
|---|---:|---|---|---|---:|---:|
{rows}

fork trace保留父启动前史，所以每条完整档案有116,320 native行；实际新增步数另列，不能重复计为fork新执行。匹配从完整live父状态fork，隐藏控制状态/模型/receipt/progress等继承；父进程在每个子进程结束后hash不变。所有最终子臂14个planner决策，未靠增加调用频率获得新自由度。

B的J_F={metrics['interface2_B0']['J_F_N_s']:.12f}；.02°={good['J_F_N_s']:.12f}，差+{good['J_F_N_s']-metrics['interface2_B0']['J_F_N_s']:.12f}N·s。本轮按motion资格选择幅度；更低力的.05°因motion失败被拒，不能称force改进。独立原始完整TASK左积分及phase精确裁剪闭合，见PHYSICAL_VALIDATION。

最终.02°：原reference与修改reference的数学区别最大膝0.02°；支撑外约{response['outside_support_max_rad']:.3g}rad。真实闭环响应可在支撑之后传播，不声称后续实际运动/reference完全局部不变。所有pre-multisegment trace对照精确一致。原机械模型、cuff/contact、gravity、actuator、torque/ROM/任务目标、HOLD、phase完成、0.25ms native和5ms FAST均未改。

原绝对物理检查的force/moment、Human/robot speed、Human acceleration、ROM、clearance、contact、torque、真实goal dwell与return均PASS。峰值force {m['force_peak_N']:.9f}N、moment {m['moment_peak_Nm']:.9f}Nm，最小真值shank clearance {m['clearance']:.9f}m（只用于评价）。原始scorer的host plan_age为FAIL，mode-aware scientific物理/因果检查为PASS；没有把host失败改成实时PASS。

## 失败与修复

- 首批.05°：hip原始native-derived acceleration最大比1.25228，jerk RMS比1.51197，超原1.10负担门。峰值在约15.92s，已晚于修改suffix结束约2.94s；对应15.915s receipt的robot轴扭矩出现短暂跳变。内部解析C2和path证书均合格；已定位下游闭环瞬态，完整非线性原因仍UNRESOLVED。未调控制增益、plant或阈值。预声明的.02°减幅通过；未继续.01°。
- 首批记录问题：子段record把原段metadata扁平复制，显示duration为1.27s，真实子段duration与证书为.3175s。实际系数、local sample、hash内容和物理不受影响。保存versions/interface1后修正实际时长/边界摘要，并附完整identity_payload；新增序列化/独立hash测试。最终版重新P0、.02°和一次重复。没有覆盖旧原始结果。
- 30项合同测试全部通过；28段历史参考的各实际子多项式独立求值最大q/dq/ddq误差1.33e-15/1.89e-15/1.32e-14。含非法q/dq/ddq接续、中段ROM/v/a/clearance、tracking offset、旧schema拒绝、source/model/reference/phase、不可行stop、迟到latch等负测试。数学测试不是物理执行替代。

## 身份、分层与复现

MATHEMATICAL_TRAJECTORY → CERTIFIED_REFERENCE → ACTIVATED_REFERENCE → ISSUED_REFERENCE → APPLIED_COMMAND → ACTUAL_HUMAN_MOTION逐层证据分别在REFERENCE_OBJECTS、summary learning/decisions、ISSUED_REFERENCE、applied receipts及native qpos/qvel。worker certificate绑定真实整路径；当前模型与原current admission在worker后/实际splice再次检查。日志附加身份不改控制。

最终reference_id `{rid}`；certificate_id `{record['certificate_id']}`。hash覆盖字段见MULTISEGMENT_REFERENCE_CONTRACT；current hash在key_traces的实际receipt。两个重复的物理轨迹相同，host capture导致值身份可不同，这是原source不得刷新的结果。

入口：[REPRODUCTION](REPRODUCTION.md)。完整源码/模型闭包与每次START版本manifest在CODE_MANIFEST、versions和source；raw物理在source/results，key_traces提供引用和关键切片。关键原始负例.05°保留。图表1–5均由实际payload/raw数据生成，SVG及PNG可导出。

![接口架构](figures/01_interface_architecture.png)
![零修改等价](figures/02_zero_reference_equivalence.png)
![内部点与导数](figures/03_internal_control_point_q_dq_ddq.png)
![实际issued与物理响应](figures/04_issued_and_physical_response.png)
![完整任务及运动门](figures/05_full_task_force_and_motion.png)

## 保护与关闭

主仓库HEAD/branch/index/staged/unstaged diff/status以及{prot['main_files_sha256_verified']}个文件/链接SHA与启动前一致。上一轮包{prot['previous_package_sha256_verified']}个文件SHA一致；其余既有Side Studies全部{prot['all_existing_side_studies_metadata_verified']}个文件名/size/mtime一致。后者是metadata审计，未伪称对所有旧研究重新全量hash。证据audit/FINAL_PROTECTION_AND_EXIT。

两个owned owner/worker及所有子进程已join，活跃owned物理进程0。START/END闭合，唯一motion负例已保留。PHYSICS_STOP与STATE标记STOP；没有Git变更命令、提交/推送、force搜索或RL/Q/MLP训练。包实际逻辑/磁盘占用见STORAGE.json，最终内容SHA见PACKAGE_MANIFEST.json。
''')
write('REPRODUCTION.md',f'''# 复现入口与冻结边界

环境：WSL Ubuntu-Research-Verify；Python /home/hank/envs/adaptive-online-rl-v1/bin/python；包 {P}。现有依赖/模型随闭包保存，无需修改主仓库或旧Side Studies。

本包已经STOP。**默认只重放/审核存档，不产生新的physical START。** own_physics/physical_runner都拒绝PHYSICS_STOP；不要在本包删除marker或重置ledger。若将来另行授权物理复现，应使用全新隔离输出、独立T0/截止/START预算，保留这里的原始证据，按FINAL protocol运行匹配B/zero/.02/repeat；不含force搜索。

```bash
P={P}
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
# 30项数学/接口测试，零physical START；会重写测试结果时间。
$PY -B "$P/tests/test_certification.py"
# 只读raw physics，独立系数/receipt/native/积分/运动统计复算；写本包审计输出。
$PY -B "$P/control/audit_physics.py"
# 存档数据生成五组科学图；不stepping physics。
$PY -B "$P/control/figures.py"
```

冻结包若需保持字节身份，先复制到全新审阅目录，再运行这些会刷新输出的脚本。物理入口是control/own_physics.py → physical_runner.py，最终实跑版本manifest在versions/interface2；首版在versions/interface1。START以manifest SHA绑定源码/模型/配置/权重，ATTEMPTS追加AUDIT补全实际reference/certificate/steps/结果，不篡改历史START/END。

审计代码只导入原raw JSON streaming parser，不导入planner/controller；独立normalized polynomial导数求值、SHA重建、receipt/native唯一时间区间及exact torque/步数、完整原积分、motion统计。当前certificate的完整内容未存档，因此独立重算仅限reference+worker certificate，current hash/状态准入由实际运行记录与保留源码验证。host timing原失败仍保留。

PACKAGE_MANIFEST包含最终文件SHA（排除它自身、STORAGE及临时cache）；CODE_MANIFEST保留最初来源SHA及最终两处原文件改动。原plant/FAST/allocator/任务等复制项逐文件与初始隔离副本SHA相同。key_traces的raw链接都只指向本包source/results；导出时需保留相对目录或解引用复制。Windows review是轻量审阅副本，完整原始证据以WSL包为准。
''')
write('NEXT_RESEARCH_DECISION.md','''# 下一步决定：本轮STOP

已获得局部非零控制点的隔离PHYSICAL_LEVEL1执行资格示范，P0/P1/P2通过并重复。下一轮若另行授权，可基于这个版本定义有限的连续轨迹动作族，先证明范围内path/stop/current admission，再设独立预算考察force与motion；本轮不做该搜索。

目前物理动作权限只示范第二个OUTBOUND请求、四个等时子段、中点膝位置+0.02°，保留通过dq/ddq、外端边界和duration。数学表示可容纳更多局部状态，但尚无任意点/任意phase/任意模型的物理资格。+0.05°已有motion反例，不可按更低force采纳。优先厘清其下游扭矩瞬态、完善current完整证书存档，再谈扩大动作域。

正式B Native LEVEL2、host LEVEL3、硬件/临床、跨患者、连续真实wrench或tracking-error不变性仍未证明。不得把本轮PASS自动提升为这些资格。保持正式仓库、旧研究只读；不提交、不推送、不训练、不自动续跑。
''')
state=load('STATE.json');state.update(phase='STOP',status='COMPLETE_SCOPED',physics_starts=10,physics_ends=10,owned_pids=[],next_allowed_action='NONE: user-requested campaign STOP',last_checkpoint='independent audit, protection and exit PASS');put('STATE.json',state)
print('REPORT_AND_CLOSED_LEDGER_SAVED',flush=True)
