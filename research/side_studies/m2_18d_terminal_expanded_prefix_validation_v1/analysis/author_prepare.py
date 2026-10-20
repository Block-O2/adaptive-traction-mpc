from pathlib import Path
import json,shutil,hashlib,time
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_terminal_response_repair_v1';P=S/L.name
assert json.loads((P/'audit/T_EXECUTION_CONTRACT_AUDIT.json').read_text())['status']=='PASS'
assert not (P/'ATTEMPTS.jsonl').exists()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
plan=json.loads((P/'RUN_PLAN.json').read_text());checked=[];conflicts=[];registrations=[]
def matches(x,target):
 if isinstance(x,dict):return x.get('prefix')==target or any(matches(v,target) for v in x.values())
 if isinstance(x,list):return any(matches(v,target) for v in x)
 return False
for pkg in S.iterdir():
 if not pkg.is_dir() or pkg==P:continue
 evidence=list((pkg/'audit').glob('*FORK_CONTEXT.json'))+list(pkg.glob('*RESULTS.json'))+list(pkg.glob('*DONE.json'))+list((pkg/'output').glob('*_DATA.json'))
 for f in evidence:
  try:x=json.loads(f.read_text())
  except (ValueError,OSError):continue
  checked.append(dict(path=str(f),sha256=sha(f)))
  for c in plan['validation_conditions']:
   if matches(x,c['prefix']):conflicts.append(dict(condition=c['name'],path=str(f)))
 f=pkg/'RUN_PLAN.json'
 if f.is_file():
  try:
   x=json.loads(f.read_text())
   for c in plan['validation_conditions']:
    if matches(x,c['prefix']):registrations.append(dict(condition=c['name'],path=str(f)))
  except ValueError:pass
put('audit/NEW_PREFIX_PROVENANCE.json',dict(status='PASS' if not conflicts else 'FAIL',conditions=plan['validation_conditions'],checked_execution_records=checked,prior_execution_conflicts=conflicts,registrations=registrations,scope='All Side Studies top-level RESULTS/DONE, audit fork contexts and output DATA records; not cross-patient evidence'))
assert not conflicts,conflicts
text=(A/'control/preflight.py').read_text().replace("A=P.parent/'m2_18d_autonomous_review_v1'","A=P.parent/'m2_18d_terminal_response_repair_v1'")
text=text.replace("assert sc.STUDY==P and mh.PACKAGE==P and am.S==P","assert sc.STUDY==P and mh.PACKAGE==P and am.S==P\nassert json.loads((P/'audit/T_EXECUTION_CONTRACT_AUDIT.json').read_text())['status']=='PASS'\nassert json.loads((P/'audit/NEW_PREFIX_PROVENANCE.json').read_text())['status']=='PASS'\nassert sc.sha(P/'code/terminal_repair.py')==sc.sha(A/'code/terminal_repair.py')")
(P/'control/preflight.py').write_text(text)
protocol='''# 冻结T扩展合法prefix验证 v1 — 事前协议

T0=北京时间2026-10-17 14:47:58；硬截止18:47:58；18:02:58起禁止新physics START。最多30 START，含cold父、fork、重复、失败。串行physics，后45分钟仅核验/交付。提前明确结论即停止。

先审计历史真实request/activation/splice/receipt/native/phase。只有合同PASS才允许physics。本轮冻结倍率1.5及5ms向上对齐；原18D参数、RETURN plateau、正式B、plant/Human/robot/contact/gravity/actuator、ROM/torque/task/HOLD、门槛、truth firewall、40ms bridge、100ms lifecycle、current admission、source age、native ownership、carry/braking/fallback均冻结。T源码字节等同上一轮，不开发新因子。

新条件事前固定：V1 seed=2026101901，OUTBOUND prefix=[[-.045,-.075,-.055]]；V2 seed=2026101902，OUTBOUND prefix=[[-.09,-.03,-.065]]。均通过原context、action和native执行链，实际完整状态来自cold commissioning和合法prefix，禁止设置/回放Human。一个prefix动作被实际消费后，在下个OUTBOUND原生决策边界quiesce，并从同一完整live地址空间串行fork B/E/T。父进程在child期间暂停，每次核验原父状态hash未变，child fork restored全状态hash精确相等。父完成后须与B完整raw物理字段一致。全任务积分保留commissioning后的共同task prefix，不将已消费OUTBOUND0称未见动作。

主要比较为每条件完整B/E/T配对，报告完整和phase JF、duration、native运动v/a/jerk、dose、tracking/moment/ROM/clearance/force和moment峰、绝对安全、task、receipts、ownership、原motion/fairness全部门。jerk max与phase shape仍为历史诊断项，不能新增为门。

T综合资格要求原motion/fairness、task、absolute safety、scientific causal execution全部PASS；保留降力要求完整JF相对匹配B至少1%，同时逐项报告相对E差值。固定T下即使未accepted或退回原合法计划，也要记录，不能称T执行通过。只在T综合PASS且降力>=1%后同父状态做一个确定性T重复，不增加新状态分母。每组最多5 START；本轮目标两组，不为耗预算添加条件。

时间/恢复/配对合同失败即停止physics。task/absolute safety/causal失败停止physics并诊断。motion失败保留原标签，定位joint/phase/metric与执行时间线，不改倍率/参数/门槛；仅按预先固定第二条件检查状态依赖。所有条件T通过且保留收益：仅支持同Human有限适用域及继续扩大验证，不宣称通用策略。motion通过但force优势不稳：只称运动修复。禁止启动18D+Waypoint或Q/RL训练。所有START/END/native/partial/父来源及失败均入账，结束保护核验并STOP。
'''
(P/'INTERVENTION_PROTOCOL.md').write_text(protocol)
audit=json.loads((P/'audit/T_EXECUTION_CONTRACT_AUDIT.json').read_text())
lines=['# T真实执行合同审计','', '**合同一致性：PASS；本审计无新physics。**','', '历史原生物理时钟与task相对时钟分开。N2 task origin physical=10.050s，最终request physical=16.835s。所有下表均为task相对秒。', '', '|历史条件|臂|request|activation|splice|suffix时长|suffix结束|终点TRACK carry|OUT/HOLD/RETURN|','|---|---|---:|---:|---:|---:|---:|---:|---|']
for r in audit['historical_rows']:
 g,a=r['id'].split('_');lines.append(f"|{g}|{a}|{r['request_task_s']:.3f}|{r['activation_task_s']:.3f}|{r['splice_task_s']:.3f}|{r['suffix_duration_s']:.3f}|{r['suffix_end_task_s']:.3f}|{r['endpoint_carry_s']:.3f}|"+'/'.join(f'{x:.3f}' for x in r['phase_durations_s'])+'|')
lines+=['','suffix自身的时间与phase clock是两个量。原MATCHED SACExpertEnv.transition_allowed要求非HOLD phase_elapsed>=9s、HOLD>=1s；runtime还要求真实estimated arrival、reference readiness、原settling/causal dwell。该下限在上一轮已存在，不是本轮改动。5ms控制网格与原状态机导致观测OUT/RETURN为9.005s、HOLD为1.020s，全task19.030s。','', 'N2 composite包含40ms既有bridge和suffix。E composite=.260s，T=.370s；receipt progress无额外delay。T将suffix真实执行结束向后移110ms，同时从原终点等待TRACK区间中占用110ms：1.955s变1.845s。U1原suffix=.215s，T=.325s，carry1.960s变1.850s。HOLD并未被提前计入，也未缩短。', '', '延长不是免费额外时间：phase内运动/终点等待的分配实际改变，属于固定倍率的直接后果。该变化已在真实receipt和native记录内，不能称运动参考时长不变。没有修改任务下限/timeout或重解释积分区间。', '', '实际reference核验：用存档schedule边界独立求解quintic，逐个suffix/carry receipt q/dq对照，最大误差<1e-8；receipt progress逐项等于min(physical elapsed, composite duration)。末段到HOLD所有receipt均TRACK，无BRAKE模式切换、无progress delay或后续OUTBOUND重规划。后续反馈/被动Human仍可制动及settle，不等于监督器BRAKE。', '', '所有positive receipts连续，全部native step按物理区间唯一归属，torque及步数精确匹配。历史receipt无直接plan_request_id字段：request→activation/composite→receipt的链接由唯一active时间区间、progress、完整多项式q/dq及原runtime元数据重建，不伪造直接ID。原current admission、连续几何certificate、mechanics、40ms桥与100ms生命周期的源码和原request记录保留在audit JSON。100ms是计划接受生命周期，已接受的参考可以继续执行更长。', '', '证据为历史PHYSICAL_LEVEL1 raw的独立离线算术重建；数学曲线不是新物理验证，也不赋予host/strict/R2/FAST资格。下一阶段只使用冻结T。', '', '详证：audit/T_EXECUTION_CONTRACT_AUDIT.json及四份HISTORICAL_TIME_EVIDENCE.json；精确源码hash和带行号规则保存在总审计JSON。']
(P/'T_EXECUTION_CONTRACT_AUDIT.md').write_text('\n'.join(lines)+'\n')
for f in L.joinpath('control').glob('*.py'):shutil.copy2(f,P/'analysis'/f.name)
print('PREPARED',len(checked),'novel records checked; immutable T sha',sha(P/'code/terminal_repair.py'),flush=True)
