"""Final offline mechanism synthesis; requires all registered patient owners joined.

Only JSON/text inputs. No physics/controller imports, replay, fitting or tuning.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--mirror',type=Path);args=ap.parse_args();p=args.package;sources={}
 def read(rel):
  f=p/rel;raw=f.read_bytes();sources[rel]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};return json.loads(raw)
 def fmt(x,n=6):return 'NA' if x is None else str(x) if isinstance(x,int) else f'{x:.{n}f}' if isinstance(x,float) else str(x)
 def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows])+'\n'
 cohort=read('VIRTUAL_PATIENT_COHORT.json');ids=[r['patient_id'] for r in cohort['patients']];plants={r['patient_id']:r for r in cohort['patients']};pairs={}
 for pid in ids:
  done=read(pid+'_DONE.json');owner=read('audit/'+pid+'_OWNER.json');assert done.get('all_children_joined') and owner.get('joined'),pid+' not joined'
  pairs[pid]=read(pid+'_COMPARISON.json')
 mechanism=read('audit_human/MECHANISM_EVIDENCE.json');m={r['patient_id']:r for r in mechanism['patients']};assert all(m[pid].get('joined_before_extraction') for pid in ids)
 motion=read('audit_human/ALL_MOTION_FAILURE_DETAILS_FINAL.json');mores={r['patient_id']:r for r in motion['patients']}
 valid=[pid for pid in ids if pairs[pid].get('full_integral_comparison_valid')];qualified=[pid for pid in ids if pairs[pid].get('complete_qualified_H150')]
 failed=[pid for pid in ids if not pairs[pid].get('complete_qualified_H150')];motionfailed=[pid for pid in valid if pairs[pid].get('motion_relative')=='FAIL'];partial=[pid for pid in ids if not pairs[pid]['H150'].get('complete_task')]
 def a(pid,arm):return m[pid]['arms'][arm]
 def metric(pid,arm,key,j=None):
  v=a(pid,arm)['motion_extra'].get(key) if a(pid,arm).get('motion_extra') else None
  return v[j] if j is not None and v is not None else v
 def change(pid,key,j=None):
  b=a(pid,'B')['measured'][key];h=a(pid,'H150')['measured'][key]
  return h[j]-b[j] if j is not None else 100*(h/b-1)
 def knee_exc(pid):return next(x['H150_minus_B'] for x in mores[pid]['excursion_gates'] if x['joint']=='knee')
 classification=table(['患者','变化','B 资格','H150 资格','完整 gain %','失败依据'],[
  [pid,plants[pid]['label'],pairs[pid]['B']['qualification'],pairs[pid]['H150']['qualification'],pairs[pid]['gain_percent'],
   pairs[pid]['H150'].get('abort_reason') or ', '.join(pairs[pid]['H150'].get('motion_comparison',{}).get('failed_requirements',[])) or '完整资格通过'] for pid in ids])
 gates=[]
 for pid in motionfailed:
  for r in mores[pid]['per_joint_burden_gates']:
   if r['failed']:gates.append([pid,r['joint'],r['signal']+'/'+r['statistic'],r['B'],r['H150'],r['ratio'],r['threshold']])
  for r in mores[pid]['excursion_gates']:
   if r['failed']:gates.append([pid,r['joint'],'excursion abs delta (deg)',r['B'],r['H150'],'delta='+fmt(r['H150_minus_B']),r['threshold']])
 gate_table=table(['患者','关节','失败项','B','H150','H/B 或差值','上限（未加容差）'],gates)
 extrema_table=table(['患者','gain %','moment 增幅 %','膝 tracking RMS 增量 °','B 膝下冲 °','H150 膝下冲 °','膝下冲增量 °','膝 excursion 增量 °'],[
  [pid,pairs[pid]['gain_percent'],change(pid,'moment_integral_Nm_s'),change(pid,'tracking_RMS_deg',1),metric(pid,'B','return_undershoot_deg',1),metric(pid,'H150','return_undershoot_deg',1),metric(pid,'H150','return_undershoot_deg',1)-metric(pid,'B','return_undershoot_deg',1),knee_exc(pid)] for pid in valid])
 damping=table(['患者','D 倍率','B 膝下冲 °','H150 膝下冲 °','局部下冲增量 °','膝 excursion 增量 °','motion'],[
  [pid,plants[pid]['physical']['passive_damping_nms_rad'][1]/5,metric(pid,'B','return_undershoot_deg',1),metric(pid,'H150','return_undershoot_deg',1),metric(pid,'H150','return_undershoot_deg',1)-metric(pid,'B','return_undershoot_deg',1),knee_exc(pid),pairs[pid]['motion_relative']] for pid in ['P07','P00','P08']])
 estimates=table(['患者','truth K [髋,膝]','fit K [髋,膝]','truth D [髋,膝]','fit D [髋,膝]'],[
  [pid,str(plants[pid]['physical']['passive_stiffness_nm_rad']),str([round(v,6) for v in a(pid,'B')['commissioning']['handoff_belief']['beta'][5:7]]),
   str(plants[pid]['physical']['passive_damping_nms_rad']),str([round(v,6) for v in a(pid,'B')['commissioning']['handoff_belief']['beta'][9:11]])] for pid in ids])
 failures=[];partial_rows=[]
 for pid in partial:
  d=read('audit_human/'+pid+'_FAILURE_DETAILS.json');failures.append(d)
  for r in d['failed_requests']:
   partial_rows.append([pid,r['request']['request_id'],r['return_elapsed_s'],r['schedule_origin_deg_deg_s'][1],r['schedule_origin_deg_deg_s'][3],
    '起始参考速度子条件 FAIL' if not r['recorded_start_knee_velocity_conjunct_pass'] else '起始参考速度通过；其余确切子条件未记录'])
 partial_table=table(['患者','request','RETURN elapsed s','拟调度起点膝参考 °','拟调度起点膝参考速度 °/s','能判定的断言子项'],partial_rows)
 partial_costs=table(['患者','完整 B J_F N·s','H150 前缀时长 s','H150 前缀 J_F N·s','完整 H150 J_F / gain'],[
  [d.get('patient_id','P06'),d['B']['J_F_N_s'],d['H150_prefix_only']['duration_s'],d['H150_prefix_only']['J_F'],'NA / NA'] for d in failures])
 mkup=sum(change(pid,'moment_integral_Nm_s')>0 for pid in valid);tkup=sum(change(pid,'tracking_RMS_deg',1)>0 for pid in valid);ukup=sum(metric(pid,'H150','return_undershoot_deg',1)>metric(pid,'B','return_undershoot_deg',1) for pid in valid)
 timestamp=datetime.now(timezone.utc).isoformat()
 text=f'''# 冻结 B/H150 跨虚拟患者失败机制报告

【PHYSICAL_LEVEL1】本轮 {len(ids)} 个预注册身份全部保留。H150 完整资格通过 {len(qualified)}/{len(ids)}；完整有效配对 {len(valid)}/{len(ids)}。观察到两类边界：{ '、'.join(motionfailed) } 完整执行后未通过冻结相对运动门；{ '、'.join(partial) } 在终末参考前置条件处中止。B 在这些条件成功，不支持把它们改称为模型无效。未通过 H150 的所有身份为 { '、'.join(failed) }。

本报告只解释本轮已执行、已 join 的 P0 物理证据。没有修改控制器、重跑规划、重放物理、放宽阈值或训练。最终汇总与分母见 [REPORT.md](REPORT.md)，参数敏感性见 [PATIENT_SENSITIVITY_ANALYSIS.md](PATIENT_SENSITIVITY_ANALYSIS.md)。数据提取时间 {timestamp}。

## 1. 证据层级与失败分类

`MODEL_IMPLEMENTATION_FACT` 是冻结源码和模型生成事实；`PHYSICAL_LEVEL1` 是实际 MuJoCo native/trace/receipt 证据；`MECHANISTIC_HYPOTHESIS` 是尚无消融或反事实验证的解释；`INSUFFICIENT_EVIDENCE` 表示无法据本轮判断。没有临床、硬件或统计显著性结论。

{classification}
绝对安全与任务完成分开报告。中止臂 task/causal FAIL、绝对 safety PASS 只覆盖已观察前缀；它们没有完整 H150 J_F 或配对 gain。完整配对中的 motion FAIL 不自动等于绝对安全失败。归档/独立算术核验 PASS 也不提升科学资格。

## 2. 完整执行后的失败：P05 与 P08

【PHYSICAL_LEVEL1】以下是全部实际失败的逐关节门。raw native 采样周期为 0.00025 s，未删端点、未用平滑结果替代。冻结 burden 上限是 1.10，代码比较 `H > 1.10*B + 1e−7`；excursion 比较 `abs(H−B) > 0.5° + 1e−7`。没有追加终末 undershoot 门。

{gate_table}
P05（K×0.7）三项失败都在膝；髋所有主要运动负担门通过。H150 膝速度峰 +26.360536717°/s 出现在 OUTBOUND elapsed 6.246500 s，物理时钟 16.296500 s。B 膝绝对峰为 RETURN 5.919000 s 的 −23.563603508°/s。**OUTBOUND 失败早于 RETURN5 终末时长组件，不能归因于该组件已经生效。**

加速度 p95 是分布统计量，没有唯一事件时刻。P05 H150 的 OUTBOUND/RETURN 膝加速度 p95 为 35.277480/27.253528°/s²，B 为 25.028427/25.988450°/s²。使用固定的 `1.10×B全任务p95+1e−7` 作诊断阈值，H150 有 4339 个超阈 native 样本，其中 OUTBOUND 3100、RETURN 1239，HOLD 0；B 有 2880 个。与此同时，P05 H150 膝加速度 max/RMS 比率分别为 0.697263/0.846136，jerk p95/RMS 为 0.918844/0.943629。不能把 p95 失败扩写成所有加速度与 jerk 变差。1.25 敏感性门不替代 1.10 冻结主门。

P08（D×1.3）只在膝 excursion 失败：B 111.153018218°、H150 111.681161782°，增量 0.528143564°。局部下冲增加 0.677175814°，OUTBOUND overshoot 减少 0.149032250°，相抵后仍超门。它接近但确实超过 0.5°冻结门；不得因幅度小而追认 PASS。其完整任务、安全、因果执行仍通过。

## 3. 局部下冲、excursion 与最终 endpoint 必须分开

【PHYSICAL_LEVEL1】RETURN undershoot 定义为 `max(0,最后实际签发RETURN reference−RETURN全段true q最小值)`，不是低谷时刻瞬时 tracking error，也不是最终 endpoint error。OUTBOUND overshoot 使用最后实际签发 OUTBOUND reference。完整配对的实际目标来自 trace/receipt，不能将名义 [5°,10°] 直接代入。

P05 两臂实际最终 RETURN reference 为 [5.5°,9.5°]。膝局部下冲 B 0.355743110°→H150 1.168182477°，增量 0.812439367°；OUTBOUND overshoot 同时减少 0.099450361°，所以 full excursion 增量为 0.712989006°。髋下冲反而从 0.564437758°降至 0.312668682°。两臂最终 endpoint 仍非常接近实际目标。这些量描述不同方面。

P00 的膝下冲增量 0.623118069°大于 0.5°，但原门只约束全 excursion；OUTBOUND overshoot 减少使 excursion 增量为 0.474247124°，故 motion PASS。该结果不表示局部下冲改善，也不授权事后新增资格门。

{extrema_table}
上述完整配对中，moment 积分增加 {mkup}/{len(valid)}，膝 tracking RMS 增加 {tkup}/{len(valid)}，膝局部下冲增加 {ukup}/{len(valid)}。同时改善 force 与髋 tracking，并不消除这些代价。尚未证明这些代价是降力的必然成本。

【PHYSICAL_LEVEL1】P05 最后膝参考平台从 RETURN 6.800 s 开始，H150 RETURN5 回执在 6.810 s 激活；时长由 0.510→0.765 s。回执中膝参考变化量约 1.42e−14°、参考最大速度约 3.12e−14°/s，而真实膝平台后仍变化 1.179601°。膝最低点在 RETURN 6.981500 s、q=8.331817523°，激活后 0.1715 s；髋当时仍为 9.196304°、速度 −11.308525°/s。B 膝最低点为 7.111250 s、q=9.144256890°，早于 B 最终参考平台 7.135 s。

图 [06_terminal_timeline.png](figures/06_terminal_timeline.png) 固定选择注册顺序首个可评价 motion FAIL，即 P05；窗口含 H150 激活前至少 0.3 s 和两臂低谷。它只显示局部 RETURN，不能定位 OUTBOUND 的全部失败。q/dq 为 native 0.25 ms，参考/力矩为实际 5 ms trace，以真实 RETURN elapsed 对齐，不归一化 phase。

## 4. 规划适用性失败：P06 与 P10

【PHYSICAL_LEVEL1】两者均在 `KNEE_REFERENCE_MUST_BE_CONSTANT` 前置断言中止。原错误保留为 `NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT`。两者 T=1、D=2、ER=2 已接受且激活，terminal H150=0；不能称为“执行髋终末时长×1.5后失败”。

{partial_costs}
前缀 J_F 只用于记录已发生负担，不能与完整 B 相减形成收益或排名。完整终末下冲、最终任务 endpoint、全任务相对运动资格均不可由此前缀补齐。

【MODEL_IMPLEMENTATION_FACT】`control/terminal_planner.py:13–17` 的条件是：

```python
(
abs(target[1]-start[1]) < 1e-10
and abs(start[3]) < 1e-10
and abs(velocity[1]) < 1e-10
)
```

`start` 来自 `current_reference_state`，`target` 为原候选 target，`velocity` 为原候选末端参考速度；单位 rad/rad·s⁻¹。条件不检查真实膝速度。断言位于 endpoint 保留检查、时长重建和新 certificate 之前。`runtime_coordination_residual_v2.py:3238–3253` 记录同一个 `request_reference` 为 `proposed_schedule_origin_rad_rad_s` 并传给 planner；prefetch 起点可不同于当下已执行回执参考。

{partial_table}
两例首个失败 request19 的起始膝参考速度均明确非零，足以判定断言失败。request20 起始参考速度为零，但失败的原 candidate target 与末端 candidate velocity 没有序列化，不能精确指定剩余哪一个子条件失败。P06 此时膝参考 9.656113892°、P10 为 10.197659649°，与任务最终 9.5°不同；任务最终目标不能冒充未保留的具体 candidate target。

P06 最后实际物理膝速度 0.835973°/s、P10 为 1.991977°/s；这证明实际运动与零参考速度可以同时存在，但不是断言读取的变量。两个 request 都未激活且不是 stale/deadline-miss 标记，不能用 host realtime 迟延替代已记录的断言原因。详见 [P06证据](audit_human/P06_FAILURE_EVIDENCE.md)、[P06输入](audit_human/P06_FAILURE_DETAILS.json) 和 [P10输入](audit_human/P10_FAILURE_DETAILS.json)。

## 5. 为什么不能给出统一刚度或阻尼阈值

【PHYSICAL_LEVEL1】P06 是 K×1.3 单因素且中止，P09 也是 K×1.3 的复合患者却完整通过；P10 为低 K 复合患者却出现同一参考断言。失败不能由“刚度达到 1.3 倍”这一阈值概括。复合病例同时改变长度、质量、被动力学等，不能拿它们估计单因素因果效应。

【INSUFFICIENT_EVIDENCE】P06 缺完整 H150 终末轨迹，因此不支持“刚度越大，完整终末下冲越大”的趋势。P05 H150 的绝对膝下冲 1.168182°还略低于 P00 H150 的 1.201029°，虽然配对恶化更大；这来自 B 基线也变化。

{damping}
【PHYSICAL_LEVEL1】在三个阻尼点中，H150 绝对膝下冲随 D 增大而减小，但 B 下冲减小更多，使相对下冲增量及 excursion 差增加，最终 P08 越门。该描述不能扩写成“高阻尼导致 H150 绝对下冲更大”或临床普遍规律。配对基线和绝对读数应同时保留。

## 6. 支持耦合解释的模型结构

【MODEL_IMPLEMENTATION_FACT】令 q1 为髋、q2 为膝，φ=q1−q2；b=I2+m2*c2²，d=m2*L1*c2，a=I1+m1*c1²+b+m2*L1²。冻结源码的惯性矩阵是：

```text
M = [[a+2*d*cos(q2), -(b+d*cos(q2))],
     [-(b+d*cos(q2)), b]]
膝方程：M21*ddq1 + b*ddq2 + d*sin(q2)*dq1²
       -g*m2*c2*cos(q1-q2) + passive2 = JkᵀF + My
passive2 = K2*(q2-qrest2) + D2*dq2 - soft_limit_term
Jk(x,z) = [sc*sin(phi), -sc*cos(phi)]
```

质量/长度/COM/惯量同时影响 M、重力与袖筒力臂；K/D 改变被动项。袖筒为有限 Kelvin–Voigt 连接，力含位置/速度误差，力矩含旋转误差、角速度误差以及 r×F，而不是一个把膝物理角锁死在参考上的理想约束。源码见 `source/stages/stage3_full3d/src/traction_mpc_stage3/human.py:103–118,155–195` 和 `spring_damper_interface.py:72–111`；生成与几何一致性审计见 [HUMAN_MODEL_AUDIT.md](audit_human/HUMAN_MODEL_AUDIT.md)。

【MECHANISTIC_HYPOTHESIS】髋速度/加速度改变可经上述耦合、重力与袖筒映射影响膝，即使膝参考已经保持不变；个体参数改变又会影响 commissioning、轨迹和候选选择。P05 的“膝参考常数、真实膝仍运动、髋仍运动”与此结构相容。没有逐项扭矩归因或组件消融，不能把观测低谷定量归因于其中某一项。

## 7. 真实估计与 plant truth 的离线对照

【PHYSICAL_LEVEL1；truth仅离线】以下是每患者自己的实际 commissioning handoff beta 中 K/D，B/H150 从同一合法父状态共享同一 belief。不是给控制器输入 truth 后的 P1；冻结算法允许每患者产生不同估计值。

{estimates}
P05 fitted Khip/Kknee=8.093966204/7.937675554，相对 truth7 分别高15.6281%/13.3954%。几何 fit 有352 accepted样本、pose RMS=8.15298e−7 m；完整11维beta、2×5 residual、几何估计与离线物理参数在 [MECHANISM_EVIDENCE_FINAL.json](audit_human/MECHANISM_EVIDENCE_FINAL.json) 中。

【INSUFFICIENT_EVIDENCE】beta 单项偏差不能替代加上 residual 后的整体预测误差，也不能证明失配是主要失败原因。没有 patient-aware P1、matched-state 模型反事实或 T/D/ER/H 组件消融。完整 H150 组合与 B 的对照足以描述组合结果，不能识别最后髋时长组件独立因果作用。

## 8. 对后续 Learning 的含义与本轮边界

【RESEARCH_RECOMMENDATION】状态候选应保留合法在线估计几何/动力学、q/dq、参考 q/dq、tracking、phase/elapsed、近期 force/moment、source age 和执行状态，并明确区分当前已执行参考与 future schedule origin。P06/P10 表明终末动作的参考前置条件值得成为显式状态/适用性信息。truth、生成器参数和未来结局仍只作离线标签。

动作研究可以比较启用/延后/禁用有界协调意图及原 B 选择，但仍需原 certificate、admission、splice、torque 和安全执行体系。本轮没有执行这种新策略。目标不能只奖励 J_F；任务完成、绝对安全、相对运动、moment、tracking 和局部终末响应必须分别记录。若未来增加局部下冲约束，须事前注册，不回写本轮门。

历史同Human合法prefix失败与本轮个体差异可能共享惯性/重力/有限袖筒耦合和参考适用性机制，但尚未证明同一原因，不能合并成同一统计分母。未来患者级保留身份与开发身份必须分开；如果设计使用了本轮保留患者结局，需另建未参与设计的确认集。没有训练、参数搜索、额外物理 START 或工作包B。

输入哈希清单见 [FAILURE_MECHANISM_INPUTS.json](audit_human/FAILURE_MECHANISM_INPUTS.json)。P05/P06详细备忘录与 v1/v2/v3 图像快照保留原貌；最终图像有独立版本QA。本报告不将缺失前缀补成完整轨迹，也不以忠实归档通过替代科学资格。
'''
 out=p/'FAILURE_MECHANISM_REPORT.md';out.write_text(text,encoding='utf-8')
 source=p/'audit_human/MECHANISM_EVIDENCE.json';dest=p/'audit_human/MECHANISM_EVIDENCE_FINAL.json';shutil.copy2(source,dest)
 manifest={'schema':'IHEAR_FAILURE_MECHANISM_INPUTS_V1','generated_utc':timestamp,'physics_starts':0,'all_registered_owners_joined':True,'registered_patient_count':len(ids),'valid_pairs':valid,'qualified_H150':qualified,'motion_failed':motionfailed,'partial_H150':partial,'sources':sources,'report_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'mechanism_snapshot_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'producer_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 mf=p/'audit_human/FAILURE_MECHANISM_INPUTS.json';mf.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
 if args.mirror:
  shutil.copy2(out,args.mirror/out.name)
  for f in [dest,mf]:shutil.copy2(f,args.mirror/'audit_human'/f.name)
 print(json.dumps({k:manifest[k] for k in ['registered_patient_count','valid_pairs','qualified_H150','motion_failed','partial_H150','report_sha256','physics_starts']}))

if __name__=='__main__':main()
