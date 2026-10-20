from pathlib import Path
import json,time,datetime,collections
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
def load(p):return json.loads(Path(p).read_text())
def measured(ident):return load(S/'reports'/(ident+'_MEASURED.json'))
def fmt(x):return f'{x:.6f}'
def main():
    result=load(S/'EXPLORATION_RESULTS.json');selection=result['frozen_selection'];assert selection,'NO_FROZEN_REFERENCE'
    best=selection['best'];strong=selection['diagnostic'];b=measured(best['base_id']);m=measured(best['id']);bad=measured(strong['id'])
    validations=load(S/'VALIDATION_RESULTS.json') if (S/'VALIDATION_RESULTS.json').exists() else {'rows':[],'primary_pass':0,'primary_condition_count':0,'status':'NOT_RUN'}
    verification=load(S/'PACKAGE_VERIFICATION.json') if (S/'PACKAGE_VERIFICATION.json').exists() else {'status':'PENDING','resources':{}}
    evidence_count=len(load(S/'EVIDENCE_LEDGER.json')['records'])
    mechanisms=load(S/'MECHANISM_ANALYSIS.json')
    secondary_gain=selection['secondary']['comparison']['gain_percent']
    region_text='\n'.join(f"- {x['stage']}：完整实际候选{x['complete_physical_candidate_count']}，motion通过{x['motion_pass_count']}；最小最差约束比候选下降{x['least_worst_constraint_candidate']['gain_percent']:.6f}%，最差比{x['least_worst_constraint_candidate']['worst_ratio']:.6f}，失败{x['least_worst_constraint_candidate']['failed_requirements']}。" for x in mechanisms['search_regions'])
    events=result['all_attempts_including_failures_and_parents'];failed=[r for r in events if r['event']=='END' and r.get('returncode',0)!=0]
    gains={ph:b['phase_cost']['phases'][ph]['J_F_N_s']-m['phase_cost']['phases'][ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN']}
    dev=[r for r in result['complete_evaluations'] if r['id'].startswith('development_repair2_')]
    new=[r for r in dev if r['candidate']['stage'] not in ['REFERENCE','VALIDATION','REPEAT']]
    ratio=m['moment_integral_Nm_s']/b['moment_integral_Nm_s']
    true_clearance=lambda x:x['native_physical_audit']['unchanged_evaluator']['raw_scorer_v2']['minimum_true_shank_clearance_m']
    session_clearance=lambda x:x['native_physical_audit']['unchanged_evaluator']['raw_scorer_v2']['minimum_session_shank_clearance_m']
    val_table=['|条件|冻结方案|本条件B J_F|方案 J_F|下降%|motion|失败项|','|---|---|---:|---:|---:|---|---|']
    for r in validations['rows']:
        number=lambda x:f'{x:.6f}' if x is not None else '不可评价'
        val_table.append(f"|{r['condition']}|{r['arm']}|{number(r['B_J_F_N_s'])}|{number(r['J_F_N_s'])}|{number(r['gain_percent'])}|{'PASS' if r['motion_pass'] else 'FAIL'}|{', '.join(r['failed_requirements']) or '无'}|")
    motion_table=['|实际原生指标|Hip最好/B|Knee最好/B|规则|','|---|---:|---:|---|']
    for signal,names in [('velocity_deg_s',['max_abs','p95_abs','rms']),('acceleration_deg_s2',['max_abs','p95_abs','rms']),('jerk_deg_s3',['max_abs','p95_abs','rms'])]:
        for name in names:
            x=m['motion']['raw']['full'][signal][name];y=b['motion']['raw']['full'][signal][name]
            motion_table.append(f'|{signal}/{name}|{x[0]:.5f}/{y[0]:.5f}|{x[1]:.5f}/{y[1]:.5f}|'+('max仅诊断' if signal=='jerk_deg_s3' and name=='max_abs' else '比值≤1.1')+'|')
    phase_text='；'.join(f'{ph}减少{gains[ph]:.6f}N·s' for ph in gains)
    text=f'''# iHEAR夜间研究探索与完整研究史复盘

## 给用户的十个核心回答

1. 最初要解决什么：让机器人完成康复运动，安全、平顺地降低人与机器人累计交互力；最终希望少数重复运动后适合该患者。早期先用Spring2D和独立Human模型建立控制/辨识基础，完整robot+cuff+被动Human是后来逐步形成的。
2. 最重要的研究转变：从外部规定整条运动，变成系统在线决定下一段协调目标，并证明计划怎样由真实仿真中的机器人执行。上次教授实际汇报时间/内容仍LAST_PROFESSOR_UPDATE_UNCONFIRMED，因此给出完整历史供用户裁剪。
3. 为什么走到在线关节目标：仅跟踪预定运动不能回答怎样协调更省力；goal-only torque MPC又暴露预测/执行、HOLD/RETURN和motion问题。后来直接选择下一对hip/knee路点，原quintic仍负责中间轨迹，机器人通过cuff推动实际Human；没有直接设置人体角度。
4. B完成什么：commissioning/state-model估计、在线waypoint、scheduler/governor、current-state admission、source age、bridge/fallback与command/native-step归属已有有限科学/host证据。正式strict55/R2/FAST资格仍分包分轴保留，不能统称部署完成。
5. 学习为何没有预期收益：120D native linear固定池的state项相消，形成有用固定偏好却没学会state-conditioned排序；32×32 Neural Q的两个test state上regret较linear差。状态/候选覆盖与V_commit/V_replan监督合同都存在问题，少repetition个体化没有证明。
6. 为什么先做自由协调优化：强低force方案常以更快膝运动、更大行程或更高moment换收益。应先找完整原动力学中值得学习的运动，再决定动作接口、监督与个体化。本轮18维扩展只是隔离意图，原执行与安全底座保持。
7. 今晚实际找到什么：冻结开发最好`{best['id']}`的J_F={m['J_F_N_s']:.6f}N·s，对同完整父B={b['J_F_N_s']:.6f}N·s下降**{best['comparison']['gain_percent']:.6f}%**，开发全部冻结运动/任务/安全比较PASS；比上轮2.457489%增加约{best['comparison']['gain_percent']-2.457488974523768:.6f}个百分点。冻结新条件motion通过{validations['primary_pass']}/{validations['primary_condition_count']}，完整限制见下表。只声明LEVEL1，不升级原B LEVEL2、host LEVEL3或临床效果。
8. 最大未解决问题：治疗任务允许多少中间姿态/时间分配变化，力收益怎样与真实运动负担权衡，以及这些运动在更不同合法状态/患者中是否可靠。当前工程比较标准不是临床阈值。
9. 需要教授决定：中间髋膝姿态带宽；速度/加速度/jerk/剂量依据；原native离散协调还是最小自由参考接口；执行架构、低力优化与few-repetition学习的贡献优先级；2D被动Human/cuff与硬件患者之间的差距。
10. 明早怎样整理：先读PROFESSOR_BRIEF与CURRENT_SYSTEM_EXPLAINED，再用详细研究史和证据表核实理解；确认上次实际汇报边界后裁剪成15–20分钟正式PPT。本轮只提供底稿和图，不制作PPT/PDF，不发送教授。

## 本轮新运动、物理证据和范围

新增共同进度倾斜/曲率、差分进度曲率和hip/knee速度倾斜，两个方向各自独立，共18维。数学参数、发出的quintic参考、真实Human运动分开记录。原Human/robot/contact/gravity/ROM/actuator/任务合同、40ms bridge、100ms lifecycle、安全和fallback均未改变。原B零调整全数据PASS；旧10维最好嵌入18维的116320native行、5817receipts及全部物理trace精确复现，独立积分误差0。

{phase_text}。完整TASK原左积分与实际phase边界闭合；任务目标和HOLD保留，真实excursion/累计剂量在冻结比较容差内，不能称运动严格相同。实际完整时间B/最好={sum(b['phase_durations'].values()):.6f}/{sum(m['phase_durations'].values()):.6f}s；B阶段={b['phase_durations']}，最好阶段={m['phase_durations']}，差值按冻结±0.1s规则检查。phase内的运动时间分配可变化，不能因此宣称治疗等效。

force peak最好/B={m['force_peak_N']:.6f}/{b['force_peak_N']:.6f}N；moment积分={m['moment_integral_Nm_s']:.6f}/{b['moment_integral_Nm_s']:.6f}N·m·s（比值{ratio:.6f}）；moment peak={m['moment_peak_Nm']:.6f}/{b['moment_peak_Nm']:.6f}N·m。最小true shank clearance最好/B={true_clearance(m):.9f}/{true_clearance(b):.9f}m，保守session clearance={session_clearance(m):.9f}/{session_clearance(b):.9f}m。完整绝对安全/ROM/contact/current admission/实际torque和receipt归属通过原评价，不能由reference合格直接推断physical合格。

{chr(10).join(motion_table)}

原45/75°/s、300/600°/s²工程限同时用于task/scheduler与原A scorer；scheduler另用原fraction .5/.25，A人体保护基于TASK采样true dq及有效因果20ms monitor窗口。这不是统一0.25ms瞬时true dq导数硬阈值。上表另按完整0.25ms真实运动raw导数比较B，两种口径不混写，均不是已认证临床阈值。

行程差Hip/Knee={best['comparison']['excursion_delta_deg']}°；累计角位移比={best['comparison']['cumulative_ratio']}；phase/endpoint最大差={best['comparison']['phase_boundary_max_delta_deg']:.9f}°；phase-shape最大差={best['comparison']['phase_shape_max_delta_deg']:.6f}°。jerk max和phase-shape按原规则诊断，不偷改历史FAIL。完整raw统计、超阈持续时间及跟踪见EXPLORATION_RESULTS与INDEPENDENT_SELECTED_METRIC_CHECKS。

## 冻结验证与不重选

{chr(10).join(val_table)}

固定四条件primary分母：实际attempt {validations.get('primary_attempted_count',0)}/4，完整任务{validations.get('primary_complete_task_count',0)}/4，正降力{validations.get('primary_force_reduction_count',0)}/4，正降力且全部motion/物理/因果比较合格{validations.get('primary_force_reduction_and_motion_pass_count',0)}/4。未完成时full J_F不可评价，不用partial力排名。

事前冻结secondary `{selection['secondary']['id']}`的开发下降{secondary_gain:.6f}%，选择规则为开发合格且降力≥1%中最小最大约束比；四条件合格{validations.get('secondary_pass',0)}/4。它是独立事先声明的保守参考，不能因测试较好而重新命名为primary或新未见最优。两个冻结方案的实际测试收益都逐行报告。

开发参数在{datetime.datetime.fromtimestamp(selection['unix'],datetime.timezone(datetime.timedelta(hours=8))).isoformat()}冻结，之后不根据验证重选或修复。四条件均同一已暴露Human、合法原native前缀前向生成状态，不能冒称跨患者。共享prefix消费的原slots不属于整串原策略的未见验证。primary和secondary均事前冻结，secondary结果不用于改选primary。真实OUT/RETURN边界状态、配对完整初态与pre-intervention negative control见VALIDATION_RESULTS。

## 低力负结果与优化局限

本轮最低力代表`{strong['id']}` J_F={bad['J_F_N_s']:.6f}N·s，降低{strong['comparison']['gain_percent']:.6f}%，motion={'PASS' if strong['comparison']['acceptance_pass'] else 'FAIL'}，失败项{strong['comparison']['failed_requirements']}。失败方案保留，不能称高质量teacher或临床舒适。不同真实运动区域包括旧合格teacher附近、B0无原residual起点及C2强低force修复，不只是单一旧参数缩放。

{region_text}

区域最小约束比仅是负担修复诊断，不是冻结primary的替换选择；完整具体约束与16个新增轴probe见MECHANISM_ANALYSIS。单轴probe和共同优化结果不能等同于最终参数逐轴ablation，因此不声称某一个自由度独自贡献全部新增收益。

有限COBYLA终态和实际调用保留OPTIMIZER_STATUS；预算终止不等收敛，全局最优或物理收益上限未证明。≥2%是研究里程碑，上轮已达到；本轮未找到满足全部开发motion规则的≥5%方案，不能用motion失败的低力方案代替。

## 分母、失败、资源与保护

实际新physical START={result['physical_attempt_start_count']}/200，END={result['physical_attempt_end_count']}；包含冷父、fork、optimizer真实rollout、失败/中断及验证，不计数学拒绝为physics，也不漏首次commissioning失败。完整评价{len(result['complete_evaluations'])}，本有效开发新候选{len(new)}，其中motionPASS={sum(r['comparison']['acceptance_pass'] for r in new)}；实际完整运动序列去重数={result['unique_actual_complete_motion_sequences']}，重复不增加患者或独立state分母。已知真实新增native步={result['known_actual_new_native_steps']}，总量精确={result['actual_step_total_exact']}。

两轮有界physics包装修复及原代码/错误/partial均保留：成员名遮蔽；标签不一致。后者数值物理完全相同也未直接放宽严格门限，恢复标签后重新通过。非零returncode事件{len(failed)}个，不隐藏失败。另有数学越界提案仅在LEVEL0拒绝，不调用physics。

主Git初始branch/HEAD/index/已暂存与未暂存diff保持；晚捕获tracked/untracked字节与symlink名称另列，不能冒充t0全部字节快照。原复用源码/模型/权重和历史报告保护范围见PACKAGE_VERIFICATION与独立审计，不宣称所有旧raw仍存在。普通本包raw仅在完整原评价、motion/receipt/积分核验后报告化；关键B/最优/强失败representative的完整raw保留。无旧数据删除、Git mutation、系统配置/存储维护或新定时任务。

包核验状态={verification['status']}；大小GiB={verification.get('resources',{}).get('study_GiB','待核')}；D真实剩余GiB={verification.get('resources',{}).get('D_free_GiB','待核')}。核验PASS仅表示保护/预算/文件/退出等合同，不等于科学问题全部解决。最终以PACKAGE_VERIFICATION.final与owned退出为准。

## 阅读与下一步

详细研究史不是REPORT拼接：原模型/权限、固定参考、高ROM失败、两次运动架构转变、B、E/Q/Neural、负担、counterfactual/fork与自由参考按问题因果组织。{evidence_count}条证据各附source、分母、等级、验证范围与明确的INFERRED因果解释。上次实际教授汇报边界仍未确认，不编造教授已知内容。

唯一推荐下一步：用户审阅8页教授底稿，与教授先确认治疗姿态自由度和运动质量评价依据，再冻结下一轮不同合法state证据/最小接口迁移合同。本轮不自动开始新包。

图表阅读见[FIGURES.md](FIGURES.md)，参数与16个新增轴probe、真实reference/torque/Human变化见MECHANISM_ANALYSIS.json，最小只读重算与历史physics命令见REPRODUCTION.md。

本次物理工作已停止；最后physical END与退出、时限合同见PACKAGE_VERIFICATION。停止不表示临床或学习目标已经完成，保留所有负结果供明早讨论。

根目录PHYSICS_STOP.json保留的是早期包装失败的历史事件；最终关闭以STATE.json、各LAUNCH/WORKER_EXIT及PACKAGE_VERIFICATION为准，不删除历史错误来制造全程无失败。
'''
    (S/'REPORT.md').write_text(text,encoding='utf-8')
    brief=S/'PROFESSOR_BRIEF.md';content=brief.read_text()
    import re
    start='<!-- OVERNIGHT_RESULT_START -->';end='<!-- OVERNIGHT_RESULT_END -->'
    update=f"{start}\n今晚实际新增：冻结开发最好下降{best['comparison']['gain_percent']:.6f}%，新合法条件motion {validations['primary_pass']}/{validations['primary_condition_count']}；相对上轮增加约{best['comparison']['gain_percent']-2.457488974523768:.6f}个百分点。事前冻结secondary开发下降{secondary_gain:.6f}%，新条件合格{validations.get('secondary_pass',0)}/4，不用测试结果改选primary。LEVEL1限定；同一Human、合法prefix后剩余策略的验证，不能称跨患者或整串原策略未见验证。验证状态{validations['status']}。\n{end}"
    if start in content:content=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:update,content,flags=re.S)
    else:content=content.replace('今晚结果应从REPORT.md的“实际新增结果”直接填入，不预写新突破。',update)
    assert update in content,'BRIEF_RESULT_BLOCK_MISSING'
    brief.write_text(content)
    print('FINAL_REPORT_DRAFT_UPDATED',best['id'],best['comparison']['gain_percent'],validations['status'],verification['status'])
if __name__=='__main__':main()
