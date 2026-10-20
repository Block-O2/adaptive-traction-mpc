from pathlib import Path
import json,sys,shutil,html
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def read(n):return json.loads((P/n).read_text())
assert (P/'PHYSICAL_DONE.json').exists()
contr=read('derived/TARGETED_CONTRASTS.json')['rows'];by={r['id'].removeprefix('targeted2_'):r for r in contr};acc=read('EXECUTION/ATTEMPT_ACCOUNTING.json');prot=read('audit/FINAL_PROTECTION.json');assert prot['status']=='PASS'
repeats={tag:read(tag+'_REPEAT_GATE.json') for tag in ['O','R']};repeat_ok=all(r['status']=='PASS' for r in repeats.values());assert repeat_ok
tab='| arm | full J_F | full ΔJ_F | support ΔJ_F | actual TV_v Δ% | reference TV_v Δ% | TV_a Δ% | jerk RMS Δ% | motion |\n|---|---:|---:|---:|---:|---:|---:|---:|---|\n'
for r in contr:
 tab+=f"| {r['id'].removeprefix('targeted2_')} | {r['full_J_F']:.9f} | {r['full_delta_J_F']:+.9f} | {r['local_delta_J_F']:+.9f} | {r['local_TV_v_percent']:+.4f} | {r['local_TV_refv_percent']:+.4f} | {r['local_TV_a_percent']:+.4f} | {r['local_jerk_RMS_percent']:+.4f} | {'PASS' if r['motion_pass'] else 'FAIL'} |\n"
R=by['R_smooth'];O=by['O_smooth'];wrench=read('derived/WRENCH_COMPONENT_RECONSTRUCTION.json');terms=read('derived/DEMAND_TERM_DECOMPOSITION.json');windows=read('derived/MECHANISM_WINDOWS.json')
half_dose={tag:abs(by[tag+'_half']['local_delta_J_F'])/abs(by[tag+'_smooth']['local_delta_J_F']) for tag in ['O','R']}
full_half_R=abs(by['R_half']['full_delta_J_F'])/abs(R['full_delta_J_F'])
text=f'''# 18D force mechanism and targeted Waypoint interventions v3

日期：2026-10-17（Asia/Shanghai）。研究性质：存档机制诊断 + 有界、同一 Human 开发父状态的配对物理干预。正式 B 没有修改。

## 直接回答本轮四个问题

1. **18D 为什么有效？** 最有支持的解释是中间协调姿态与边界速度改变了运动时序和所需广义力矩，再通过原 allocator 与反馈执行改变 cuff force。去程更早抬髋降低模型重力需求；回程更早降低膝角，显著降低模型弹性需求。原 allocator 对存档 causal estimated q / requested torque 的重算给出 **−36.527540 N·s**，实测为 **−37.916277 N·s**；两者接近，但不能把 36.53/37.92 当成已识别的物理因果中介比例。
2. **收益是否真的来自 smoothness？** 18D 全程 TV_v 较低，与一部分收益相符；它不是主要机制的充分解释。4–6 s 的 force 降低伴随 acceleration variation 和 jerk RMS 增加；15–15.5 s 同时降力而实际 TV_v、TV_a、jerk 增加。原累计 J_F 不存在尖峰，图中同时给出瞬时 F 与累计增长。实际 allocator/command 的分解与姿态负荷项比单一 variation 指标更能解释大收益。
3. **主动压低 velocity oscillation，force 会下降吗？** 在本轮两个指定窗口，答案是**这两条 shape 干预中会出现小幅下降，并可确定性复现**。O_smooth 的 support TV_v {O['local_TV_v_percent']:.3f}%，support ΔJ_F={O['local_delta_J_F']:+.9f} N·s；R_smooth 分别为 {R['local_TV_v_percent']:.3f}%、{R['local_delta_J_F']:+.9f} N·s。反方向小幅对照、半幅和 exact repeat 都保留。此结论是“这类局部 shape 的总干预效果”，不是“smoothness 作为唯一中介已被识别”。
4. **直觉关系在哪里受阻？** 力不仅由速度变化率决定。姿态重力/弹性负荷、请求与制动时序、tracking/allocator 的合成 wrench、robot/contact 动力学及窗口端点的储能/释放共同作用。平滑带来的惯性/反馈减量可能很小、正负抵消，甚至 command-force 与接触力的有限窗口变化反号。本轮并未发现完全无信号；发现的是可重复但很小、依赖窗口和执行链的信号，不能以其解释 18D 约 37.92 N·s 的收益。

## 共同时间轴与局部证据

![共同时间轴](figures/01_core_common_timeline.png)

两条任务均从 absolute **10.05 s** 开始，到 **29.08 s** 结束，TASK=19.030 s。下轴 task、上轴 absolute，仅作坐标平移，没有峰值配准或 phase 重采样。OUTBOUND=0–9.005，HOLD=9.005–10.025，RETURN=10.025–19.030。橙色标出 B 高负荷窗，绿色标出主要净收益窗；request、activation、splice 独立保留。50 ms TV rate 来自 native dq/a，原瞬时 force 仍是 5 ms 记录；raw jerk 图为显示抽样，所有统计保留完整 native 点。

| phase | B J_F | 18D J_F | B−18D |
|---|---:|---:|---:|
| OUTBOUND | 725.825779 | 707.100520 | 18.725259 |
| HOLD | 54.394339 | 54.394333 | 0.000006 |
| RETURN | 658.393380 | 639.202368 | 19.191012 |
| total | 1438.613498 | 1400.697221 | 37.916277 |

4–6 s 与15–16 s 贡献10.099746 /9.996502 N·s，合计为净收益的53.00%。B 的最重负荷在1–2.5 s，最高峰115.479 N（task1.935 s）；因此最大收益窗口与最大原始 force 窗口不能混同。

| window | force benefit N·s | actual TV_v B→18D | TV_a B→18D | combined jerk RMS B→18D |
|---|---:|---:|---:|---:|
| 4–6 | 10.099746 | 0.841761→0.791018 | 12.452830→12.478632 | 18.796705→19.309372 |
| 15–16 | 9.996502 | 0.527044→0.444333 | 6.883824→8.676467 | 17.297771→16.539074 |
| 15–15.5 | 4.305193 | 0.222610→0.225426 | 1.111348→4.398990 | 2.581345→21.306858 |
| 15.5–16 | 5.691310 | 0.304435→0.218907 | 5.772476→4.277477 | 24.323119→9.642330 |

单位：TV_v rad/s，TV_a rad/s²，jerk rad/s³。4–6 s：髋平均86.179→92.251°，膝85.545→84.394°；髋 position-tracking RMS 0.568→0.615°、velocity-tracking RMS1.073→1.158°/s，均未改善，仍然降力。15–16 s：髋30.451→28.359°，膝35.964→21.946°；髋 position-tracking RMS0.476→0.580°变差，膝0.598→0.522°变好，不能称全关节 tracking 改善。同期 cuff moment 积分4–6 s 为4.500538→4.774529 Nm·s，15–16 s 为6.715720→8.579517；全程 moment 增加约7.03%，不能把低力直接等同于综合负荷或舒适度改善。

18D 同时改变内部 target、terminal velocity、每段 duration 与后续请求时间。OUT slot3：B target=(96.900,95.399)°、terminal velocity=(12,20)°/s、duration1.270 s；18D=(103.994,95.134)°、(13.294,20.195)°/s、1.215 s。RETURN slot4 请求15.585→15.180 s，splice15.635→15.230 s。因此15–15.5 s内18D有新 splice、B没有；两者的 derivative transient 落在不同半秒箱。C2 reference 也不保证 actual tracking derivative 没有瞬态，不能把 jerk 峰与累计力增长混为同一种现象。

[去程局部全过程](figures/02_outbound_mechanism.png) · [回程局部全过程](figures/03_return_mechanism.png) · 原始逐窗数据：`derived/MECHANISM_WINDOWS.json`、`derived/SCHEDULE_COMPARISON.json`。

## 从需求力矩到真实 command 的机制证据

两条任务的已commissioned geometry一致；11个beta参数全程不变，B/18D逐点完全相同。没有借在线参数变化解释收益。原 sagittal allocator 约束为 B(q)[Fx,Fz,My]=tau，目标和权重保持原样。

先把 estimated posture q 与 requested generalized action tau 做四种代数输入交换。全程 norm-level 两因素对称分解：**geometry +11.109240**、**action −47.636780** N·s，净−36.527540。4–6 s 为+0.795399/−9.762818，15–16 s 为+1.731544/−12.436982。因此证据并不支持“姿态让 allocator 几何杠杆独自变好”；更明显的是姿态/参考改变了所请求的力矩。这里的 geometry 指allocator输入几何，不包含姿态对重力和弹性需求的上游影响。

再按原逆动力学 regressor 把 tau 拆为 gravity、elastic、velocity terms、remainder，并用向量恒等式精确闭合纯分配 force-norm 差。remainder 含惯性、tracking、soft limit、residual 和安全修正，**不冒称单独测得的 acceleration 项**。

| 区间 | gravity | elastic | velocity terms | remainder | allocation geometry | 纯分配净Δ |
|---|---:|---:|---:|---:|---:|---:|
| full | −18.137642 | −30.621873 | −0.035799 | +1.225298 | +11.042477 | −36.527540 |
| OUTBOUND | −27.036257 | +6.587017 | +0.129809 | +0.276886 | +1.894127 | −18.148419 |
| RETURN | +8.898617 | −37.208891 | −0.165598 | +0.948383 | +9.148351 | −18.379137 |
| 4–6 | −15.409831 | +3.540114 | +1.092545 | +1.050877 | +0.758876 | −8.967419 |
| 15–16 | +1.608307 | −11.072753 | −1.134203 | −1.843470 | +1.736681 | −10.705438 |

均为18D−B，N·s。norm-level Shapley 和该向量投影分解是不同归因约定，geometry一列略有不同；各自都严格闭合，不能混用比例。4–6 s模型髋gravity均值9.922→6.355 Nm，requested hip action27.564→25.521 Nm；15–16 s模型膝elastic4.678→2.235 Nm，requested knee action−4.137→−6.385 Nm。更早抬髋降低重力项、更早降低膝角减少弹性项，是目前最具体且与方向一致的解释。

![需求项分解](figures/05_demand_term_decomposition.png)

进一步用存档robot q在一次性CR12模型内仅做kinematics/comPos，反解原Jᵀ，将存档robot torque分量还原为position / velocity / allocator wrench。`mj_step/step1/step2`全部禁止；model time保持0；sum与存档**total command wrench**闭合误差约5.7e−14。注意 trace字段`allocated_wrench_world`实际保存的是**总command wrench**，不是纯allocator输出；相关图与本报告明确区分。

| 区间 | position贡献 | velocity贡献 | allocator贡献 | 总command force Δ积分 | 实测contact force Δ积分 |
|---|---:|---:|---:|---:|---:|
| full | −2.353652 | −1.214017 | −35.616659 | −39.184329 | −37.916277 |
| 4–6 | +2.635558 | −4.399895 | −8.386103 | −10.150440 | −10.099746 |
| 15–16 | −3.841020 | +0.194979 | −10.763500 | −14.409541 | −9.996502 |

这说明实际command中allocator通道的变化占主导，去程局部velocity feedback也有贡献，回程该项甚至轻微反向。command force与contact force在有限窗口不必相等；robot/contact动力学和窗口边界响应仍在其中。以上是精确的已记录分量核算，不是关闭某个controller通道后的物理反事实，也不把全部force差归给单个通道。

## 有针对性的 Waypoint 实验

先完成上面的存档分析，再冻结实验。两组均为B已有suffix，O=task4.310–5.580 s，R=14.315–15.585 s。每条仅插入fraction=(.2,.4,.8)三个内部位置点，保留原每点v/a、外端q/dq/ddq、suffix总duration、task、plant与全部原资格门。offline SLSQP只最小化reference velocity TV，未使用force目标，没有physics sweep；runtime只收到注册常数和原causal输入，不消费native Human truth。

O内部(hip,knee)偏移为(+.05,−.0414768)、(+.05,−.05)、(−.05,+.05)°；R为(−.05,+.0419713)、(−.05,+.05)、(+.05,−.05)°。全路径幅度仍≤.05°。原±.05°反向对照被原REFERENCE_VELOCITY证书拒绝，保留拒绝，未派发physics；预先只尝试一次1/4幅度，全部通过。因反向幅度不同，不能当等幅中心差分。零shape分段对象保持独立identity/certificate，物理全trace/native/receipt与B完全一致。

主判据在看到非零结果前冻结：完整task/safety/motion/receipt通过，support实际TV_v较B低>1e−6相对量且support J_F下降>1e−8 N·s，才允许同方向半幅一次和同父状态重复一次。该极小容差仅用于条件分支，不能解释为临床/工程有效改善阈值。O/R均触发；没有增加方向、placement或放宽阈值。

{tab}

Δ均为candidate−B；support是各自注册的1.270 s区间，O/R的两个zero原始J_F与全部物理信号精确等于B。每个candidate均保存瞬时force、完整cumulative curve、q/reference、v/reference、TV、acceleration/jerk、tracking、moment、total torque、allocator/feedback响应，见`series/`、`derived/*METRICS.json`和下图。

![O干预](figures/06_O_targeted_intervention.png)

![R干预](figures/06_R_targeted_intervention.png)

O/R的exact repeat均对全存档native Human/robot/torque/contact及receipt控制字段精确一致；它们是确定性重复，不是新患者或新state证据。半幅support净力效果分别为全幅的{half_dose['O']:.3f}/{half_dose['R']:.3f}；相应motion完整保留，不外推线性剂量规律。观察到的净小收益也伴随局部正、负force差面积；并非每一时刻force都更低。O/R的force低于B时间分别约{100*O['local_force_lower_time_fraction']:.1f}%/{100*R['local_force_lower_time_fraction']:.1f}%，瞬时差范围分别为{O['local_force_delta_extrema'][0]:+.3f}至{O['local_force_delta_extrema'][1]:+.3f} N、{R['local_force_delta_extrema'][0]:+.3f}至{R['local_force_delta_extrema'][1]:+.3f} N。这里支持的是匹配窗口的净积分/均力改善，不是逐时刻一致下降。

两条smooth全任务收益分别只有18D收益的{100*abs(O['full_delta_J_F'])/37.916277314:.4f}% / {100*abs(R['full_delta_J_F'])/37.916277314:.4f}%，不能以本轮小改进解释旧18D的大改进。R_smooth还使最后一个RETURN请求提前5 ms；已存档完整时序，不能把support以外的全任务收益全部写成纯局部平滑效应。R_half的全程收益仍为全幅的{full_half_R:.3f}，而support收益约为一半，进一步显示全任务效应包含下游离散时序响应。O_smooth没有请求时间或label改变。

[所有新候选完整force/cumulative曲线](figures/07_targeted_full_task.png) · [局部motion–force对照](figures/08_local_motion_force_contrast.png) · [CSV数值表](derived/TARGETED_CONTRASTS.csv)。

干预后的需求项与真实command分量另存`derived/TARGETED_DEMAND_TERMS.json`和`derived/WRENCH_COMPONENT_RECONSTRUCTION.json`。O_smooth在support内，纯allocator模型force积分反而+0.001731 N·s，实际总command norm积分+0.011939，而实测contact force为−0.007838；这直接说明“TV下降→当下分配力下降→接触力下降”不是本实验已证明的单一路径。其全程command/allocator及tracking响应不同，有限窗口内robot/contact的动态响应不能被静态command替代。小幅shape干预的总效果可重复，smoothness的独立中介作用仍未隔离。

## 资格、负结果、保护及复现

物理START/END={acc['physical_START']}/{acc['physical_END']}，全部join；包括第一次因缺输出目录而在TASK入口停止的parent、已经完成后仅重算evaluator的B、修复后的新完整parent/B、所有zero、smooth、反向、half与repeat。科学候选上限未扩大；在看到任何非零结果前，只为失败启动恢复增加2个engineering START额度。原始失败、完整B原始数据、修复日志和两个大幅反向证书拒绝均保留，见`EXECUTION/`。未成功/partial不进入force排名；恢复的旧B明确单列而不重写原错误记录。

主仓库Git/index/staged/unstaged/status与文件size/mtime快照一致；消费历史存档SHA一致；执行闭包manifest一致；新physics source/code/deps/weights相对上一包仅做路径迁移，controller/plant/certificate没有语义改动；原motion protocol逐字节相同。完整检查见`audit/FINAL_PROTECTION.json`。本次没有提交、推送、合并、删历史或迁移到正式B。

force网格为5 ms，原J_F使用左积分，逐原区间裁剪phase/window；不对单调累计值寻找相关。native q/dq为0.25 ms，a/jerk为原edge_order=2数值导数，保留raw与逐关节统计；TV_v和TV_a为相邻向量差的Euclidean和。数值导数不是临床抖动测量。所有新physics通过原full-state fork、parent hash不变、task、native ownership/causal receipt、current-state admission、source age/lifecycle、safety与原motion evaluator；新物理资格仍是PHYSICAL_LEVEL1 scientific-mode。旧18D的合法prefix motion0/4、原host plan_age/strict失败未升级。

本轮同一Human、同一开发条件，reverse和half仍属开发干预，不能算独立统计样本；没有held-out新state、跨患者、硬实时、硬件或临床证据。没有做“只改变smoothness而姿态、时序、tracking、contact状态完全不变”的物理干预；现有闭环这些量相互依赖。代数输入交换不是合法可执行trajectory，更不替代完整fork实验。独立重算指同一agent的另一条核算路径，并非独立研究者或独立数据。上一轮20条候选的完整报告、指标合同与存档来源已读取；本轮深入机制重算聚焦B/18D，没有冒称重新审核全部历史native。

canonical：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1`。Windows是审阅镜像，不宣称已复制全部历史raw；本轮全部新完整raw、native、receipt、source closure留在canonical。本轮physics入口`control/targeted_campaign_repair1.py`是**已结束、有唯一attempt名的campaign，不可直接重跑覆盖**。重现须在新版本目录迁移路径、冻结新manifest/预算后，从合法cold parent重新fork；不得从保存的q/dq重建活状态。零physics分析可在canonical读取存档运行`control/refresh_core.py`、`control/allocator_counterfactual.py`、`control/demand_decomposition.py`、`control/postprocess_targeted.py`等，但应另设新输出以保护本报告。环境复用`/home/hank/envs/adaptive-online-rl-v1/bin/python -B`，线程数=1；没有安装依赖。

## 下一步研究建议与停止决定

**保留Waypoint作为局部shape控制工具，但停止扩大本轮搜索。** 两个窗口的同向、反向、半幅和重复已足以说明存在可操作的小信号；继续追逐小数点不会解答18D机制。优先把18D研究写成“协调姿态/边界速度→力矩需求→allocation/feedback→contact”的机制链，而非单一smoothness surrogate。

下一包建议先冻结一个能区分负荷需求与平顺性的配对合同：在同一合法完整父状态下，分别研究中间协调姿态变化和局部variation变化，严格匹配端点、duration、原资格门；在现有可证书化表示下检查能否形成load较接近但TV不同、或TV较接近但load不同的对照。先用本轮原regressor和command分解预测方向，再做极少量完整物理验证；不改gain、allocator权重或plant来制造归因。

若要推进可用策略，随后必须用预注册的新合法prefix检验原motion门余量，不能用同父重复代替；18D既有0/4失败应先解决。若目标是较大force降幅，应优先研究任务允许的中间协调姿态与被动负荷，而不是把jerk/velocity TV单独设为force代理。所有这些是下一轮建议，本轮已STOP。
'''
(P/'REPORT.md').write_text(text)
figs=[('01_core_common_timeline','核心共同时间轴'),('02_outbound_mechanism','18D去程机制'),('03_return_mechanism','18D回程机制'),('04_allocator_input_decomposition','allocator输入交换'),('05_demand_term_decomposition','力矩需求项分解'),('06_O_targeted_intervention','去程局部干预'),('06_R_targeted_intervention','回程局部干预'),('07_targeted_full_task','全部干预完整任务曲线'),('08_local_motion_force_contrast','局部motion–force对照')]
gallery=''.join(f'<section><h2>{title}</h2><a href="figures/{name}.png"><img src="figures/{name}.png" loading="lazy"></a><p><a href="figures/{name}.svg">SVG</a></p></section>' for name,title in figs)
summary=f'<p>18D主要证据指向姿态与广义力矩需求改变；局部Waypoint平滑出现可重复的小幅降力。O/R全任务收益为{abs(O["full_delta_J_F"]):.6f}/{abs(R["full_delta_J_F"]):.6f} N·s，仍远小于18D的37.916277 N·s。</p>'
head='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>18D mechanism & targeted Waypoint v3</title><style>body{font:17px/1.7 system-ui,sans-serif;max-width:1250px;margin:auto;padding:35px;background:#f7f8fa;color:#172b3a}img{width:100%;background:white}section{background:white;padding:20px;margin:24px 0;border-radius:8px}a{color:#166496}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:25px}h1{line-height:1.3}</style>'
(P/'EVIDENCE_INDEX.html').write_text(head+'<h1>18D机制与局部Waypoint验证</h1>'+summary+'<p><a href="REPORT.md">完整报告Markdown</a> · <a href="TARGETED_RESULTS.json">全部新结果JSON</a> · <a href="EXECUTION/ATTEMPT_ACCOUNTING.json">START/END总账</a></p>'+gallery+'<h2>完整报告文本</h2><pre>'+html.escape(text)+'</pre></html>')
print('REPORT_WRITTEN',len(text),'repeat_exact',repeat_ok)
