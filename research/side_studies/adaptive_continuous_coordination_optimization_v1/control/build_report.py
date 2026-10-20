from pathlib import Path
import json,time,hashlib,platform,subprocess,shutil,os
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def load(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
 assert (P/'PHYSICAL_DONE.json').exists(),'Campaign must finish before selection/report'
 rows=[json.loads(x) for x in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()];ledger=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START'];ends=[x for x in ledger if x['event']=='END'];done=[r for r in rows if r['status']=='COMPLETE'];b=done[0];feasible=[r for r in done if r['motion_pass']];minr=min(feasible,key=lambda r:r['J_F_N_s']);minmotion=min(feasible,key=lambda r:r['jerk_RMS_combined']);tvbest=min(feasible,key=lambda r:r['velocity_TV_combined']);selection=load('FROZEN_SELECTION.json');assert selection['status']!='NEW_RECORD_PENDING_VALIDATION','Frozen paired validation required before final report'
 prov=load('NATIVE_PROVENANCE_AUDIT.json');an=load('DOWNSTREAM_ANOMALY.json');mechanism=load('ANOMALY_MECHANISM_DIAGNOSTIC.json');redistribution=next(x for x in load('TEMPORAL_FORCE_REDISTRIBUTION.json')['rows'] if x['id']=='development_legacy005');diag=load('DIAGNOSTIC_RESULTS.json');old=diag['cases'][1];cor=diag['cases'][0]['correlations'];interaction=load('PATH_TIMING_INTERACTION.json');plan=load('RUN_PLAN.json');tests=load('CERTIFICATION_TEST_RESULTS.json');math=load('DENSITY_MATH_TESTS.json');state=load('audit/INITIAL_GIT_STATE.json')
 for n in ['METRICS_CONTRACT.md','LITERATURE_POSITIONING.md']:shutil.copy2(L/n,P/n)
 table=['| Candidate | 内部点数 | family | J_F (N·s) | B−J_F (N·s) | motion | TV_v / B | jerk RMS / B |','|---|---:|---|---:|---:|---|---:|---:|']
 for r in rows:
  if r['status']=='COMPLETE':table.append(f"| {r['candidate']['id']} | {r['candidate']['waypoint_count']} | {r['candidate']['family']} | {r['J_F_N_s']:.9f} | {b['J_F_N_s']-r['J_F_N_s']:.9f} | {'PASS' if r['motion_pass'] else 'FAIL'} | {r['velocity_TV_combined']/b['velocity_TV_combined']:.6f} | {r['jerk_RMS_combined']/b['jerk_RMS_combined']:.6f} |")
  else:table.append(f"| {r['candidate']['id']} | {r['candidate']['waypoint_count']} | {r['candidate']['family']} | unranked | — | {r['status']} | — | — |")
 density=[]
 for n in [1,2,3]:
  rr=[r for r in done if r['candidate']['id'].startswith('D'+str(n)+'_')];density.append(dict(density=n,n=len(rr),motion_pass=sum(r['motion_pass'] for r in rr),min_J_F=min((r['J_F_N_s'] for r in rr if r['motion_pass']),default=None),min_jerk_ratio=min((r['jerk_RMS_combined']/b['jerk_RMS_combined'] for r in rr),default=None)))
 put('DENSITY_SUMMARY.json',dict(rows=density,caveat='unequal sparse shape coverage; density is confounded with arrangement and support; no universal optimum'))
 phase='\n'.join(f"| {ph} | {diag['cases'][0]['phase_J_F_N_s'][ph]:.6f} | {old['phase_J_F_N_s'][ph]:.6f} | {diag['cases'][0]['phase_J_F_N_s'][ph]-old['phase_J_F_N_s'][ph]:.6f} |" for ph in ['OUTBOUND','HOLD','RETURN'])
 corrtable='\n'.join(f"| {key} | {cor['0.5']['ALL'][key]['pearson']:.3f} | {cor['1.0']['ALL'][key]['pearson']:.3f} | {cor['0.5']['OUTBOUND'][key]['pearson']:.3f} | {cor['0.5']['RETURN'][key]['pearson']:.3f} |" for key in ['speed_variation','velocity_TV','acceleration_RMS','acceleration_variation','jerk_RMS','curvature_TV'])
 failcount=sum(not r['motion_pass'] for r in done);maxdelta=max(max(x['max_physical_trace_deltas'].get('evaluation_only_human_state_rad_rad_s',[0])) for x in prov['responses'])
 anomalytext='\n'.join(f"- {x['id']}: hip acceleration peak 在 task {x['hip_acceleration_peak_task_s']:.5f} s / absolute physics {x['hip_acceleration_peak_absolute_physics_s']:.5f} s，{x['hip_acceleration_peak_deg_s2']:.5f} deg/s²；最后 multisegment receipt 后 {x['delay_after_last_multisegment_receipt_s']:.5f} s；附近 5 ms robot torque 最大变化范数 {x['nearby_max_5ms_robot_torque_change_Nm']:.5f} N·m。" for x in an['rows'])
 report=f'''# iHEAR Lab — Physical Sensitivity, Adaptive Waypoint Density & Bounded Continuous Coordination v1

## 结论

新增自由度确实可以进入完整物理执行并改变实际 Human motion；它提供的是可追踪、可重复、端点与总时长不变的局部形状控制能力。本轮没有找到优于旧 18D 开发结果 1400.697221 N·s 的完整合格运动，也没有证明“更多 waypoint → 更平顺 → 更低累计 cuff force”。

本轮合格数值 force 最低为 **{minr['id']} / {minr['J_F_N_s']:.9f} N·s**，相对 B 差值为 **{b['J_F_N_s']-minr['J_F_N_s']:.9f} N·s**，即 **{100*(b['J_F_N_s']-minr['J_F_N_s'])/b['J_F_N_s']:.8f}%**。这种量级只报告为本状态下确定性数值敏感性，不能包装成新的有效降力里程碑。

合格组中最小 combined jerk RMS 是 {minmotion['id']}（B 的 {minmotion['jerk_RMS_combined']/b['jerk_RMS_combined']:.6f}）；最小 combined velocity TV 是 {tvbest['id']}（B 的 {tvbest['velocity_TV_combined']/b['velocity_TV_combined']:.6f}）。这些是不同的 motion 指标，不能合并成一个未定义的“舒适度”。

**+0.05° 的远期 motion FAIL 已重复。** 两次新运行的实际 native body/torque/contact、原控制 trace 和 receipt 控制字段完全相同；它是可重复的完整闭环敏感性，内部 downstream 机制仍未被因果分解。

## 本轮做了什么

先读取 B、旧 18D、+0.02°、+0.05° 的存档 raw/native/receipt；不为诊断重跑物理。随后在全新 Side Study 复制闭包内扩展 reference 构造器，保留原 full-path/current-state certificate、原 40 ms bridge、100 ms lifecycle、FAST/native ownership 与 task/safety/motion 门。

构造器允许 D1/D2/D3 的 1/2/3 个内部位置点，每个 hip/knee 位置扰动不超过 ±0.05°。D1=2 段，D2=3 段，D3=4 段；legacy +0.02/+0.05 已有三个分割 knot，但只扰动其中一个，因此不能将其误称为三个独立调优点的实证。新增点不是新增 planner 请求，physics 仍为 0.25 ms。

**搜索范围限制：** 本轮新物理干预围绕B的一个既有OUTBOUND suffix展开；旧18D仅作存档物理对照，未在旧18D参数上叠加新waypoint优化，也没有覆盖所有phase/placement/amplitude。因而“未找到低于旧18D的结果”不是新接口的全局收益上限证明。后续若在旧18D上研究新自由度，必须先处理其历史跨状态motion失败并另设冻结预算。

测试 {len(tests['rows']) if 'rows' in tests else 30} 项继承合同测试和 {len(math['rows'])} 项 density/C2/identity/非法输入测试通过。只有构造器发生语义改动；证书函数 AST 相同，motion protocol 字节相同；其余代码的绝对路径迁移另有清单。

物理 START 总分母 **{len(starts)}**：包含一个 cold parent、所有 fork、重复以及失败。候选记录 {len(rows)} 条，完整 {len(done)} 条，其中 motion PASS {len(feasible)}、motion FAIL {failcount}，异常/partial {len(rows)-len(done)}。完整 task 与 absolute safety、tracking、moment、force、causal receipt 均按原 evaluator 保存；motion FAIL 仍保留完整结果但不进入合格 force ranking。START/END 对账见 ATTEMPT_ACCOUNTING.json。

开发 seed={plan['seed']}，全部 candidate 从同一完整活父状态 fork；没有直接设置 Human qpos/qvel、没有物理 replay。父状态 hash 检查和父/零分支 B 等价门单独保存。deterministic repeat 不等于新的合法 state 验证。

## Force-time 与 motion-time

B 完整 J_F={b['J_F_N_s']:.9f} N·s；旧18D={old['J_F_N_s']:.9f} N·s。原 objective 仍是 5 ms cuff-force norm 的完整 TASK 左积分。0.25 ms native logs 只有 q/dq/torque/contact 等，不能声称已经获得 0.25 ms cuff-force；本轮没有插值伪造该数据。

| phase | B J_F | 旧18D J_F | B−18D |
|---|---:|---:|---:|
{phase}

旧18D 最大0.5 s local benefit 位于 {old['largest_benefit_windows'][0]['start_s']:.1f}–{old['largest_benefit_windows'][0]['end_s']:.1f} s，约 {old['largest_benefit_windows'][0]['benefit_vs_B_N_s']:.6f} N·s。它的收益分布和新小幅局部扰动的极小差异不能混同。

+0.05°相对B的局部正差积分为 {redistribution['positive_delta_force_area_N_s']:.8f} N·s，负差积分为 {redistribution['negative_delta_force_area_N_s']:.8f} N·s，绝对差面积为 {redistribution['absolute_delta_force_area_N_s']:.8f} N·s，净J_F差仅 {redistribution['delta_J_F_N_s']:.8f} N·s。新增自由度可以重新分布局部负荷；局部正负抵消说明完整累计量与瞬时负荷/运动质量都需要保存，不能从净量几乎不变推断物理运动没有改变。

所有 velocity TV、acceleration、jerk 都来自实际 Human dq 的未滤波 0.25 ms 导数。TV_v=sum ||Δdq||，speed TV=sum |Δ||dq|||；二者不等于关节空间几何 curvature。jerk p95/RMS/max、jerk energy、每个 joint 和 combined 结果在 JSON 中保留。

| B window Pearson r | 0.5 s 全任务 | 1 s 全任务 | 0.5 s OUTBOUND | 0.5 s RETURN |
|---|---:|---:|---:|---:|
{corrtable}

这些是同一确定性时间序列内的局部描述，不是跨 candidate 的 J_F 预测模型。0.5/1 s、phase、lag、epsilon 的敏感性均保存。HOLD 时长太短，独立完整 window 数不足，相关系数为 null 而非0。

在所列变化指标中，acceleration variation 的全任务窗口关联较高，jerk RMS 次之；在 phase 内排序、强度和符号并不稳定。speed variation 与 curvature variation 不能成为本轮 force surrogate。即便部分窗口相符，也仅 consistent with the hypothesis，不能写 smoothness causes lower force。

曲率用 hip/knee 等权 radian 平面中的 det(dq,ddq)/(||dq||²+eps²)^(3/2)，eps=1e-3 rad/s，另报1e-4/1e-2；raw curvature 只在速度>eps的相邻有效样本中统计。原地/低速对曲率诊断可有很大影响。它不是临床舒适度指标。

## 物理敏感性与 density

{chr(10).join(table)}

密度分组统计见 DENSITY_SUMMARY.json。不同 arrangement 的物理 Human response、robot torque、force/moment 和 issued reference 最大差异见 NATIVE_PROVENANCE_AUDIT.json；全任务响应向量的 SVD 仅是有限扰动输出多样性诊断，不能宣称系统形式上的 controllability rank。

多点相对单点增加了局部 q 值的独立设置与支持区间布局能力；真正的可用性还必须由当前 geometry/mechanics/ROM/v/a、task、motion 和 receipt 决定。D3 不是天然优于 D1，较密布局与不同正负点值同时改变了扰动的支持与局部曲率。当前 sparse sweep 不能识别普适的 diminishing-return 点，也不能把 density 与形状混杂的效应写成纯密度因果结论。

## Adaptive refinement 原型

从存档 B 在已打通 suffix 内的 force accumulation×actual velocity TV 选择局部区间：2.5–3.0 s，并把插入位置约束到可用 suffix 内部 fraction=0.75。adaptive_D2 保留 .5 点并新增 .75 点，做小幅 knee shape 评价。完整规则和原始窗口值见 ADAPTIVE_REFINEMENT_PLAN.json。

这是离线研究原型，使用实际运动诊断来设计下一次实验；运行时只向原 causal planner 提供注册参数，没有 native Human truth 输入。仅当 full task/safety/motion/receipt PASS、J_F降低、velocity TV无>1%恶化时，允许进入重复/进一步局部研究；本轮没有将它部署为在线 adaptive planner。

## Timing / speed

实际建立 P、S_PROXY、P+S_PROXY 三族。S_PROXY 保留全部 waypoint q 和总 suffix duration，内部时间移动 ±0.635 ms；共享内部 v/a 使 C2 保持，但点间 Hermite 几何路径可能变化。2001点 path Hausdorff 距离另存，不把有限采样距离当连续几何证书。

独立数学检查构造 exact fixed-path timewarp u+0.01u³(1−u)³，保持整个 suffix 端点 q/dq/ddq、总时长和几何路径。与原 quintic 复合后为 degree30，原 2×6 coefficient certificate 明确拒绝 INVALID_MULTISEGMENT_COEFFICIENTS。未借用旧证书、未物理执行这条未认证曲线。因此“纯 spatial 与纯 temporal 哪个更有效”仍未被完全解耦回答。

匹配 P/S_PROXY/P+S_PROXY 的 force gain interaction 为 {interaction['force_gain_interaction_N_s'] if interaction else 'not available'} N·s；三者 motion 全通过={interaction['all_three_motion_pass'] if interaction else 'not available'}。一次状态、小幅 proxy 的交互不足以证明稳定 synergy。

## +0.05° 远期异常

{anomalytext}

ANOMALY_REPEAT_GATE 对比全部116320条 native 记录、5817个 receipts及原trace，结果 {an['repeat_gate']['status']}。局部 reference 的边界 C2 和当前证书通过并不能保证远期 actual Human derivative burden 通过。torque transient 与 acceleration/jerk 峰的共现已保留；没有通过修改 controller gain/contact或 replay Human state来构造机制归因。

进一步核对了原 torque-component 定义，并验证 base+position+velocity+allocator+clipping 与实际command在异常窗口内的加和闭合。相对B的局部最大差异范数：allocator {mechanism['component_differences']['robot_torque_component_allocator_nm']['max_window_delta_norm']:.6f} N·m，velocity {mechanism['component_differences']['robot_torque_component_velocity_nm']['max_window_delta_norm']:.6f} N·m，position {mechanism['component_differences']['robot_torque_component_position_nm']['max_window_delta_norm']:.6f} N·m，base {mechanism['component_differences']['robot_torque_component_base_nm']['max_window_delta_norm']:.6f} N·m，clipping=0。allocator是最大的已观测贡献差异，但这仍不是allocator单独致因的证明；state/geometry/feedback/replan共同演化，机制尚未充分分离。最近一次plan activation提前约0.28 s，也不能把峰值直接解释成节点接续跳变。

## 冻结与验证

本轮无新方案低于1400.697221 N·s，因此未触发新的 frozen primary paired validation；VALIDATION_RESULTS.json 明确为 NOT_TRIGGERED。不能用同父状态重复代替新的合法状态或跨患者验证。旧18D 2.635613% development finding 和历史新状态 motion 0/4 保留原资格，没有按本轮数据重新选择它。

FROZEN_SELECTION 保留精确数值可行最小值，并另列仅用于呈现的0.01 N·s近似 tie-band motion对照；后者不是新primary、不是事后改变原motion门、也不进入验证重选。没有大规模COBYLA：本轮信号不足以支持把更多预算用于微小force差异追逐。

## 必须回答的11个问题

1. **density是否增加physical controllability？** 增加了可执行的内部形状配置能力，且 actual Human motion随之改变；这不等于严格控制理论意义的可控性证明。
2. **单点与多点区别？** 多点可在同一外部端点/总duration下分别设置局部位置、相位支持和相邻形状；原生physics/请求频率未增。
3. **多少点开始 diminishing return / penalty？** 当前D1–D3仅有限布局，结果和逐例motion门已给出；不足以冻结普适最优密度或临界点。
4. **force是否集中在motion variation大的区间？** 部分对应，整体与phase内均不是稳定一致；完整window积分、top-quartile force share及lag保留。
5. **哪个指标最相关？** 当前全任务窗口 acceleration variation较高；jerk、速度TV和曲率排序随phase/window改变，没有稳定胜出的force surrogate。
6. **spatial还是temporal更有效？** 物理P与timing proxy已比较；exact path/time分离受当前证书表示限制，纯效果仍unresolved。
7. **有明显synergy？** 保存了配对交互数值；未证明可重复、可泛化的明显synergy。
8. **+0.05° anomaly可重复？** 是，新的同父状态两次完整执行复现motion FAIL与相同native/control记录。
9. **有比1400.697221更好的完整合格运动？** 没有。本轮数值最小为{minr['J_F_N_s']:.9f} N·s。
10. **新合法state仍成立？** 没有新record触发验证，不能回答成立；当前新能力只在同一Human、同一开发父状态验证。
11. **下一步？** 优先解决 physical robustness：以+0.05°可重复远期响应为靶点，在新的合法prefix状态中辨别shape/timing/下游tracking敏感性，再决定是否构建精确speed模块。暂不进入few-repetition learning。

## 资格与边界

完整新执行属于 **PHYSICAL_LEVEL1 / development**。分段C2、identity/证书测试与exact timewarp是 mathematical/interface evidence；force-motion相关、epsilon和局部窗口统计是 correlational。没有LEVEL2、host LEVEL3、硬实时、跨患者、真机或临床结果。原host plan_age/strict资格失败仍原样保留；科学模拟使用原有mode-aware时钟，不能把它当host验收通过。

正式B、Human/robot dynamics、cuff/contact、gravity、actuator、ROM、task goal、HOLD、安全阈值、motion阈值、truth firewall、bridge/lifecycle/native ownership均未修改。未训练RL/Q/Neural Q；未推送、合并、提交或自动开始下一包。

起始主仓库分支 {state['branch'].strip()}，HEAD {state['HEAD'].strip()}。原有dirty/untracked状态按字节文本保存并复核，没有新建/切换分支。关键命令、环境、源码SHA、raw来源、START/END、参数及issued/applied/native证据见REPRODUCTION、EXECUTION_CODE_MANIFEST及audit。

**STOP。** 本轮预先冻结的有限敏感性组与合格重复已经结束，新增可执行shape自由度和可重复远期motion penalty已有证据；没有稳定的新force优化区域，停止扩大搜索，不宣称排除了所有合法trajectory。下一包只提出建议，不自动执行。
'''
 (P/'REPORT.md').write_text(report)
 decision=f'''# NEXT_RESEARCH_DECISION — STOP

本包完成有限diagnostics → matched physical sensitivity → density/timing proxy → provenance audit。新增能力是端点/总时长不变的实际形状控制与可重复的远期motion敏感性；不是新的≥2%force改进。

唯一推荐：**先解决physical robustness**。下一轮若获授权，在新合法prefix条件下对可重复+0.05°远期异常进行冻结配对归因，区分placement/amplitude与下游tracking响应，并预先定义失败后的停止门。不要直接扩大density、部署adaptive waypoint planner或训练few-repetition模型。

当前force最低合格值{minr['J_F_N_s']:.9f} N·s，未低于1400.697221；无新primary promotion，未触发paired validation。S_PROXY含几何混杂，纯speed模块需要单独表示与证书设计。

研究分类：G（远期异常同父状态可重复）；其余A–E按逐例结果审阅，不以极小数值差宣称稳定机制。当前能力与结论限PHYSICAL_LEVEL1、同一Human状态。正式B不变。STOP，不自动启动下一包。
'''
 (P/'NEXT_RESEARCH_DECISION.md').write_text(decision)
 reproduction=f'''# Reproduction and preservation

Canonical full package: `{P}`. Windows folder is a light review/export copy; raw compressed physics remains canonical in WSL.

Python: `/home/hank/envs/adaptive-online-rl-v1/bin/python`; Python {platform.python_version()}. Serial CPU MuJoCo scientific simulation; BLAS/OMP/MKL threads=1. No new dependency installation. Original B/18D/native evidence locations and hashes are in DIAGNOSTIC_RESULTS.json; they must remain available for archived comparisons.

This package is STOPPED. Do not delete PHYSICS_STOP.json or reset ATTEMPTS.jsonl. No default reproduction command dispatches physics. To authorize another campaign use a new output/version with fresh budgets and preserve this record.

Read-only evidence recomputation (writes analysis outputs only, no physics):

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python -B {P}/control/diagnostics.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B {P}/control/enrich_diagnostics.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B {P}/control/postprocess.py
/home/hank/envs/adaptive-online-rl-v1/bin/python -B {P}/control/protection_audit.py
```

For immutable verification copy the package first, since analysis regenerates timestamps/figures/JSON. Inherited fixture/certification tests use the read-only key_traces link to the previous package; that is an explicit archive dependency. Active `source/code/deps/weights` are new isolated copies with rebased paths, not links to production.

Physical command executed once after a pre-physics dependency-startup repair: `{P}/control/owner.py`, which owns campaign.py and joins its process. Every actual START includes code-manifest hash; all children inherit the same full process state at a legal boundary, keep normal current-state admission and native ownership, and never replay/set Human state. The pre-physics missing-contract failure is archived; it produced no physical START. Initial wrong-path unit imports were repaired before physics and all30+12tests rerun. Source rebase and startup repairs are documented under audit/.

Executed source is fixed by EXECUTION_CODE_MANIFEST.json. Postprocessing scripts may be added afterward; only control/diagnostics.py was enriched after the execution freeze, with curvature derivative diagnostic output, and this file is not imported by campaign/plant. No active physical code was edited during the campaign. `multisegment_reference.py` is the sole semantic delta in the copied plant/controller closure; safety/current certificate functions have identical ASTs. Source relocation is not counted as a controller change.

Evidence chain: MATHEMATICAL_TRAJECTORY coefficients → CERTIFIED_REFERENCE ID/path certificate → ACTIVATED_REFERENCE learning record → ISSUED_REFERENCE samples → APPLIED_COMMAND positive-step receipt/torque → ACTUAL_HUMAN_MOTION native q/dq. Every new multi receipt additionally archives full current path certificate content and reconstructs its ID. Native steps are uniquely joined to receipt intervals and exact torques; raw full-task/phase integrals close within1e-8.

Candidate IDs, parent hash, reference parameters/count/placement/node q/timing, reference/certificate hashes, issued/applied evidence, actual q/dq, forces/moments, task/motion/safety/tracking and wall durations are retained across CANDIDATE_RESULTS, output/*REFERENCE*, reports/*MEASURED and source/results/*/runtime_artifacts.json.gz. Force samples are5ms; Human derivatives are0.25ms. All failed/partial runs remainunranked in the denominator.

No stage/commit/push/merge/reset/stash/delete of unrelated material. Starting/final git state matches. No hardware, learning, production tuning or next package. Exact current stop markers and process ownership are recorded in PACKAGE_VERIFICATION.json.
'''
 (P/'REPRODUCTION.md').write_text(reproduction)
 accounting=dict(status='PASS' if len(starts)==len(ends) and {r['id'] for r in starts}=={r['id'] for r in ends} else 'FAIL',physics_START=len(starts),physics_END=len(ends),cold_parents=sum(r.get('kind')=='LEGAL_COLD_PARENT' for r in starts),forks=sum(r.get('kind')=='FULL_TASK_FORK' for r in starts),complete_candidates=len(done),motion_PASS=len(feasible),motion_FAIL=failcount,failed_partial_candidates=len(rows)-len(done),events=ledger,no_exclusions=True,prephysics_startup_failure_not_counted='No sc.run/dispatch occurred; preserved in audit/startup_failure_before_physics.log')
 assert accounting['status']=='PASS';put('ATTEMPT_ACCOUNTING.json',accounting)
 print('REPORT_BUILT',len(starts),len(done),len(feasible),minr['id'],flush=True)
if __name__=='__main__':main()
