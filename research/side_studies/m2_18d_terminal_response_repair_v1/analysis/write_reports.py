from pathlib import Path
import json,time
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
def read(n):return json.loads((L/n).read_text())
def put(n,x):(L/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def md(n,t):(L/n).write_text(t+'\n')
def pair(x):return ' / '.join(f'{v:.6f}' for v in x)
groups=read('EXPERIMENT_RESULTS.json')['groups'];n2=next(g for g in groups if g['group']=='N2');u1=next(g for g in groups if g['group']=='U1');by={g['group']:{r['arm']:r for r in g['rows']} for g in groups};T=by['N2']['T'];U=by['U1']['T'];E=by['N2']['E'];B=by['N2']['B'];audit=read('audit/INTERVENTION_EXECUTION_AUDIT.json');ar={r['group']:r for r in audit['rows']};account=read('ATTEMPT_ACCOUNTING.json');git=read('audit/GIT_BEFORE.json')
u_pass=bool(U['motion']['acceptance_pass'] and U['absolute_safety'] and U['task']=='PASS' and U['receipt']=='PASS' and U['motion']['gain_percent']>=1.)
n2pass=bool(T['motion']['acceptance_pass'] and T['absolute_safety'] and T['task']=='PASS' and T['receipt']=='PASS' and T['motion']['gain_percent']>=1.)
assert n2pass
checks={}
for g in groups:
 name=g['group'];checks[name]=dict(complete=True,pair_full_live_state=g['pair_gate']['status'],parent_unchanged_and_exact_B=g['parent_gate']['status'],independent_native_arithmetic=g['independent_raw']['status'],repeat='NOT_RUN' if g['repeat_gate'] is None else g['repeat_gate']['status'],original_frozen_E_motion_pass=by[name]['E']['motion']['acceptance_pass'],T_motion_pass=by[name]['T']['motion']['acceptance_pass'],T_absolute_safety_pass=by[name]['T']['absolute_safety'],T_causal_receipt=by[name]['T']['receipt'],T_gain_percent=by[name]['T']['motion']['gain_percent'],failed=by[name]['T']['motion']['failed_requirements'])
put('VALIDATION_RESULTS.json',dict(status='COMPLETE',scientific_status='REPEATABLE_N2_REPAIR_AND_ONE_NEW_PREFIX_PASS' if u_pass else 'REPEATABLE_N2_REPAIR_NEW_PREFIX_NOT_QUALIFIED',mathematical_interface='PASS',historical_raw_independent=read('audit/ARCHIVED_RAW_INDEPENDENT.json')['status'],intervention_execution_audit=audit['status'],conditions=checks,development_conditions=1,new_prefix_pairs=1,new_prefix_T_qualified=int(u_pass),same_Human=True,repeats_excluded_from_state_denominator=True,no_primary_reselection=True,no_threshold_changes=True,source_age_bridge_lifecycle_current_admission_preserved=True,independent_audit='separate numerical source path, single agent; not an independent human or separate agent audit',LEVEL1=True,LEVEL2=False,LEVEL3=False,hardware=False,clinical=False))
table=['|条件/臂|完整 J_F N·s|对B降力 %|对E ΔJF N·s|膝amax °/s²|对B膝比|motion|task/安全/causal|','|---|---:|---:|---:|---:|---:|---|---|']
phase=['|条件/臂|OUTBOUND JF|HOLD JF|RETURN JF|OUT/HOLD/RETURN s|','|---|---:|---:|---:|---|']
burden=['|条件/臂|vmax °/s hip/knee|amax °/s² hip/knee|jerk RMS °/s³ hip/knee|jerk max（诊断）|tracking RMS ° hip/knee|moment Nm·s|clearance m|','|---|---|---|---|---|---|---:|---:|']
for g in groups:
 for r in g['rows']:
  m=r['measured'];full=m['motion']['raw']['full'];motion='PASS' if r['motion']['acceptance_pass'] else 'FAIL: '+','.join(r['motion']['failed_requirements']);name=r['id'];p=m['phase_cost']['phases']
  table.append(f"|{name}|{r['J_F_N_s']:.9f}|{r['motion']['gain_percent']:.6f}|{r['delta_vs_frozen_18D']['J_F_N_s']:+.9f}|{full['acceleration_deg_s2']['max_abs'][1]:.6f}|{r['motion']['burden_ratios']['acceleration_deg_s2/max_abs'][1]:.6f}|{motion}|{r['task']}/{'PASS' if r['absolute_safety'] else 'FAIL'}/{r['receipt']}|")
  phase.append(f"|{name}|{p['OUTBOUND']['J_F_N_s']:.9f}|{p['HOLD']['J_F_N_s']:.9f}|{p['RETURN']['J_F_N_s']:.9f}|"+' / '.join(f"{r['phase_durations'][ph]:.6f}" for ph in ['OUTBOUND','HOLD','RETURN'])+'|')
  burden.append(f"|{name}|{pair(full['velocity_deg_s']['max_abs'])}|{pair(full['acceleration_deg_s2']['max_abs'])}|{pair(full['jerk_deg_s3']['rms'])}|{pair(full['jerk_deg_s3']['max_abs'])}|{pair(m['tracking_RMS_deg'])}|{m['moment_integral_Nm_s']:.9f}|{m['clearance']:.9f}|")
result_table='\n'.join(table);phase_table='\n'.join(phase);burden_table='\n'.join(burden)
delta=ar['N2']['delta_J_F_T_minus_E'];reduction=ar['N2']['knee_max_reduction_percent_vs_E'];local=ar['N2']['measures']['T']['terminal_knee_max_abs_acceleration_deg_s2']
mechanism=f'''# 机制证据与受控修复

本轮找到可合法实施、可重复的N2末段运动修复。唯一因素为最终OUTBOUND suffix由原0.220s改为0.330s；原18D参数、此前所有schedule、最终target/通过速度、request/activation和40ms bridge保留。原fixed-duration接口完成数学、连续几何、mechanics检验；真实physics继续接受原current admission与100ms lifecycle，无旁路。

## 直接受控证据

独立对齐检查在6.830s splice之前，参考q/dq/ddq、真实Human q/dq、施加robot torque和contact force均保持在1e-10原单位误差内；全部上游schedule逐字相同。首次参考/命令差异=6.835s，5ms实际运动差异=6.840s。新轨迹的accepted metadata、request id、实际activation、native positive receipts和每个native step已贯通核对。T恰好有一个ACCEPTED末段干预，未靠接口拒绝后fallback冒充修复。

N2 T实际末段膝amax={local:.9f}°/s²；完整TASK膝amax={T['measured']['motion']['raw']['full']['acceleration_deg_s2']['max_abs'][1]:.9f}°/s²，峰值已转移到原先存在的2.93475s前段。原18D完整峰90.058623°/s²下降{reduction:.6f}%；对匹配B比值={T['motion']['burden_ratios']['acceleration_deg_s2/max_abs'][1]:.9f}，通过1.10原门。完整motion/fairness所有冻结条款通过，不只是膝最大加速度单项。该变化在相同完整父状态的确定性重复中逐字段复现。

完整JF={T['J_F_N_s']:.9f}N·s，对B降力={T['motion']['gain_percent']:.6f}%，对E变化{delta:+.9f}N·s。这个微小力差不构成额外降力里程碑，结论是保留18D收益的运动修复。完整阶段时长9.005/1.020/9.005s，TASK19.030s，HOLD和RETURN没有缩短。

## 能推断到哪里

同完整live状态、相同上游运动，只改变合法末段参考时间形状，实际膝峰和资格随之改变。因此在该确定性模型与N2条件内，末段参考时间形状对异常具有可控的总效应，且无须先消除“hip先到”便能修复N2原motion失败。它不证明该因素是跨状态唯一根因，不证明某个allocator分量放大系数，也不能把数学参考amax等同真实Human amax。

源代码可直接确认的规则、存档的时序事实、基于时序的响应解释和仍未分离的机制，在`N2_TERMINAL_DIAGNOSIS.md`及`provenance/SOURCE_RULES.md`分别标识。clearance/acceleration projection在存档末段未激活，torque clipping为0；没有证据归因于这些限制器的突然切换。FAST位置/速度反馈、allocator、被动Human和contact之间的具体中介贡献仍未独立分离。

## 新prefix验证

U1事前固定为OUTBOUND=[[-0.075,-0.045,-0.05]]、seed=2026101801。107份历史执行结果/完整fork context检查未见该prefix执行；上一轮仅登记未运行。T未根据U1重选。

U1 T完整JF={U['J_F_N_s']:.9f}N·s，对匹配B降力={U['motion']['gain_percent']:.6f}%，motion={'PASS' if U['motion']['acceptance_pass'] else 'FAIL'}，原绝对安全={'PASS' if U['absolute_safety'] else 'FAIL'}，causal={U['receipt']}。新prefix综合资格={'PASS 1/1' if u_pass else 'FAIL 0/1'}。重复不增加状态数；这是同一Human的remaining-suffix验证，OUTBOUND0已由prefix消费，不能称整串策略未见初态泛化或不同患者验证。

![N2受控参考与真实响应](figures/N2_intervention_response.png)
'''
md('MECHANISM_FINDINGS.md',mechanism)
next_step=('在新的独立协议中保持T=1.5冻结，扩大合法prefix的末段规划资格验证，检验其适用域；本轮不启动。' if u_pass else '先补足U1失效窗口的参考—命令—真实响应机制证据；保持T与原门冻结，不进行倍率搜索。')
md('NEXT_RESEARCH_DECISION.md',f'''# 下一研究决定

终态：{'REPEATABLE_N2_REPAIR_AND_ONE_NEW_PREFIX_PASS' if u_pass else 'REPEATABLE_N2_REPAIR_NEW_PREFIX_NOT_QUALIFIED'}。

唯一建议的下一步：{next_step}

现有fixed-duration参考接口足够合法分离末段因素，无需先改变正式B或增加绕过证书的接口。当前证据支持末段参考规划的受控修复；尚不支持修改allocator、部署到正式B或宣称跨患者可靠。更细的闭环中介归属仍未证明，但与本轮总效应证据分开报告。

原B、冻结18D和C/R失败保留。完成后STOP；不自动开始18D+Waypoint优化，不训练Q-learning，不commit/push/merge。
''')
report=f'''# iHEAR Lab — 18D末段响应诊断与受控修复 v1

**找到N2可重复的合法运动修复，并保留18D降力优势。** {'一个此前未执行的新合法prefix配对也通过，适用范围仍限同一Human。' if u_pass else '一个新合法prefix未通过，不能称跨状态可靠修复。'} 本轮未改正式B，不修改18D参数，不训练学习器。

## 六个明确答案

1. **最早实质差异**：N2对N1 PASS从合法prefix本身已不同；0.010s issued/command分叉，描述性native q差超过0.01°在0.12850s、dq差超过0.1°/s在0.08675s。N2内部E/B共享prefix，18D在1.515s请求，bridge后1.565s参考/命令开始不同。末段不是差异的起点。T/E则严格保持此前运动，6.830s最终splice后才分叉。上述量级是描述阈值，不是新资格门。
2. **直接机制与推断**：源码确认范围拒绝、通过速度规则、网格quintic、40ms bridge和100ms scientific lifecycle；存档确认目标不同步与参考先停、实际仍运动及随后膝峰。T的配对结果建立末段参考时间形状的总效应；具体FAST/allocator/contact中介仍不能唯一归因。
3. **合法且可重复改善**：N2 T膝完整amax由90.058623降至{T['measured']['motion']['raw']['full']['acceleration_deg_s2']['max_abs'][1]:.6f}°/s²，对B比值由1.249192降至{T['motion']['burden_ratios']['acceleration_deg_s2/max_abs'][1]:.6f}。所有原motion/fairness、task、安全及causal门PASS；确定性重复逐字段PASS。末段自身amax降至{local:.6f}°/s²，完整峰已转移到此前的前段。
4. **降力保留**：T JF={T['J_F_N_s']:.9f}N·s，对匹配B降力{T['motion']['gain_percent']:.6f}%；与E仅差{delta:+.9f}N·s，不称新降力突破。
5. **新状态验证**：U1原完整live父状态配对，T综合资格{'PASS 1/1' if u_pass else 'FAIL 0/1'}；不是不同患者，重复不计新状态，不能升级为广泛泛化资格。
6. **下一步**：{next_step} 现有参考接口够用，正式B保持冻结。

## 诊断与唯一干预

存档诊断没有重跑physics。N2 18D髋先进入目标附近，膝后到；最后非终末target约[120,117.7845]°，空间意图越界拒绝，膝通过速度约8.8623°/s。最终request=6.785s、composite activation=6.790s；40ms bridge之后quintic实际执行6.830–7.050s。膝issued负加速度样本峰在6.995s，真实峰在7.07225s，届时参考dq=0而实际膝仍约5.918°/s。

N1 PASS也有先后到达、范围拒绝和相近参考加速度峰，所以事件共现不是充分因果解释。N2 B的全程膝amax=72.093488，N1 B=128.347787；冻结motion相对匹配B，不是跨状态统一绝对阈值。原N2绝对安全一直PASS。

T只在原18D已经选出最终OUTBOUND goal后，用原fixed-duration contract将suffix时长乘1.5、向上对齐5ms；N2为0.220→0.330s。原选目标、最终通过速度、所有此前schedule和物理运动不变。数学接口重建原0.220s完全一致，新参考精确峰约52.322°/s²；原连续几何、mechanics通过后才运行真实physics。全部current-state admission、source age、bridge、lifecycle、native ownership、carry/fallback原样执行。协议在第一START前冻结，未按结果改primary或门槛。

详见[N2诊断](N2_TERMINAL_DIAGNOSIS.md)、[事前干预协议](INTERVENTION_PROTOCOL.md)、[受控机制证据](MECHANISM_FINDINGS.md)。

## 全部完整物理候选

{result_table}

B自比PASS只表示参照，安全与task另审。原E的FAIL如实保留。历史C/R及其重复失败没有重跑、没有覆盖。父运行各自与匹配B全trace/native/receipt物理字段精确一致，单独计入账本，不当额外候选或状态。

{phase_table}

全部TASK均19.030000s。积分采用原5ms force左积分并在phase边界精确切分，共同prefix积分完整保留；完整/分阶段闭合通过。细节和每臂对B/E差值在`EXPERIMENT_RESULTS.json`。

## 运动、跟踪与绝对安全

{burden_table}

velocity/acceleration/jerk的完整max/p95/RMS及各phase、ROM/dose/phase边界、moment/force peaks、tracking、clearance和安全逐项条件均在结果JSON的`measured`中。jerk max为原诊断项，不偷换成新门；实际Human导数来自0.25ms native qvel，不能把数学曲线当真实运动。

每臂request/activation/splice、target/pass velocity、应用命令、原receipt与每个native step的归属已保存并核对。源age、当前状态检查和原安全规则未放宽。受控T在最终splice前的参考/物理一致性、唯一accepted干预和实际输出差异由不导入controller/plant的脚本复核，见`audit/INTERVENTION_EXECUTION_AUDIT.json`；全native独立核算见`audit/INDEPENDENT_N2.json`与`audit/INDEPENDENT_U1.json`。

## 证据层级、保护与预算

新物理属于原MuJoCo **PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION**。原LEVEL2、host-clock LEVEL3/strict55/R2/FAST负结果及未获资格保持；host profiling不作为物理等价字段，也没有变成实时资格。没有真机、临床或跨患者证明。独立复核是单agent下的独立算术实现，不冒称独立人类或第二agent审计。

起始Git branch=`{git['branch'].strip()}`，HEAD=`{git['head'].strip()}`，未切分支、stage、commit、push、merge、reset、stash或删除旧文件。新文件仅在本版本Side Study及审阅镜像；原B/plant/Human/robot/contact/gravity/actuator、ROM/torque/task/HOLD/完整duration、安全/motion门、truth firewall、40ms bridge、100ms lifecycle、current admission/source age、native ownership/receipts/carry/fallback冻结。最终SHA、metadata、Git逻辑状态及owned进程退出结果以`PACKAGE_VERIFICATION.json`为准。

T0=北京时间2026-10-17 14:05:15，硬截止18:05:15，17:20:15后禁止新START。本轮START/END={account['physical_START']}/{account['physical_END']}，上限20；新增native steps={account['actual_new_native_steps']}。无partial，无失败物理尝试；父、fork、重复和验证全部计入。提前得到明确有限结论后停止，不为填满3–4小时追加实验。实际耗时和关闭时间见最终核验文件。

canonical完整执行源及raw：`{P}`；Windows为可读报告/分析/证据镜像，`ENVIRONMENT.json`和manifest明确来源。`REPRODUCTION.md`给出只读复核入口；已关闭包禁止原地重启physics。

**STOP。** 不自动开始第二轮18D+Waypoint搜索或Q-learning。

![N2局部共同时间轴](figures/N2_terminal_timeline.png)

![N2受控修复](figures/N2_intervention_response.png)
'''
md('REPORT.md',report)
md('REPRODUCTION.md',f'''# 复核入口

本包已关闭。禁止原地重跑physics或清空账本；新增physics必须新版本、重新登记合同。

指定Python：`/home/hank/envs/adaptive-online-rl-v1/bin/python`，带`-B`。canonical：`{P}`。真实raw位于`source/results/<id>/trace.npz`、`summary.json`、`native_reference.npz`、`runtime_artifacts.json.gz`；native真值通过`wall_physics`存档，仅用于evaluation。

执行闭包与physics前SHA：`EXECUTION_CODE_MANIFEST.json`。原18D固定参数和RETURN plateau：`FROZEN_18D.json`；原门：`MOTION_ACCEPTANCE_PROTOCOL.json`；候选新增源：`code/terminal_repair.py`。唯一新因子1.5，无搜索或训练。完整命令见`N2_OWNER.json`、`U1_OWNER.json`及`ATTEMPTS.jsonl`；最后START已锁止。

只读数值复核：将`control/independent_recompute.py`复制到另一个新审计输出目录，绑定本包为读取根并单独绑定输出sink，再调用`measure(id)`；禁止直接覆盖本包已关闭的derived。它不导入controller/plant，逐行重算native映射/导数、积分、phase、dose、receipt ownership和source hash。`analysis/verify_archives.py`示范这种读写根分离方式。报告/图与对齐来源在`analysis/`，不属于physics执行闭包的后改文件。

执行前preflight用原scheduler重建存档N2因果模型与边界，original_duration=.220、T=.330，原mechanics与连续几何PASS。真正current-state admission和40ms桥在新物理链再次执行，不以数学测试替代物理资格。
''')
put('STATE.json',dict(phase='REPORTING_NO_MORE_PHYSICS',scientific_status='REPEATABLE_N2_REPAIR_AND_ONE_NEW_PREFIX_PASS' if u_pass else 'REPEATABLE_N2_REPAIR_NEW_PREFIX_NOT_QUALIFIED',physical_starts=account['physical_START'],physical_ends=account['physical_END'],next_action='Final history/Git/owned-process/package verification, then STOP',no_followup_campaign=True))
put('ENGINEERING_EVENTS.json',dict(physics_errors=[],nonphysical_events=[dict(event='Windows mirror has no usable Git cwd; canonical WSL Git used',effect='No Git mutation'),dict(event='One automatic approval review timed out on preflight invocation; allowed single retry succeeded',effect='No physics START consumed'),dict(event='Diagnostic figure rerender had an indentation error; corrected and rerendered',effect='Archived raw and physics source unchanged'),dict(event='One report patch failed syntax validation before writing; retried successfully',effect='No historical or physical change'),dict(event='Initial report aggregation used pre-finish metric containing inherited native steps; final audit corrected to branch-adjusted DATA metric and asserted agreement with independent per-attempt audit',effect='Raw, physical execution and scientific qualification unchanged; inherited steps excluded from final accounting')]))
print('REPORTS_WRITTEN','U1 qualified',u_pass,flush=True)
