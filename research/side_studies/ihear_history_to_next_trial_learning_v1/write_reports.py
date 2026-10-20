"""Generate Chinese reports from completed physical evidence; never selects actions."""
from pathlib import Path
import json,collections,datetime,sys
import numpy as np
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def write(n,s):
    if '--check' in sys.argv:print('REPORT_RENDER_CHECK',n,len(s),flush=True)
    else:(P/n).write_text(s.strip()+'\n')
def n(v,d=3):return '—' if v is None else f'{v:.{d}f}'
def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join(['---']*len(head))+'|']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows])
def action(r):
    a=r['action']
    return a['base'] if a['phase'] is None else f"{a['phase']}[{a['slot']}] 膝 {a['knee_delta_deg']:+.6f}°"
def selection_reason(d):
    if not d['applicable']:return '特征域外，A0'
    if d['selected_index']!=0:return '通过保守选择；仍须原物理门'
    if not any(p['eligible'] for p in d['predictions'][1:]):return '候选预测资格不足，A0'
    return '保守采集/效益不足，A0'
def main():
    res=read('LEARNING_RESULTS.json');acc=read('ATTEMPT_ACCOUNTING.json');cont=read('CONTINUOUS_REPETITION_RESULTS.json');train=read('models/TRAINING_RESULTS.json');diag=read('models/MODEL_DIAGNOSTICS.json');flags=res['flags'];rows=res['rows']
    executed=[g for g in res['groups'] if g['status']=='EXECUTED'];learn=[r for r in rows if r['method'] in ['ILC','BO','VALUE']]
    test=[r for r in learn if r['split']=='heldout'];causal=[r for r in learn if r['strict_history_ablation_pass']]
    held=[r for r in test if r['history_causal_benefit']]
    adapted_value=[r for r in learn if r['method']=='VALUE' and r['action_adapted']]
    value_action_note=(f"Value 的 {len(adapted_value)} 个实际干预采用同一个固定参数动作 {action(adapted_value[0])}；这些消融中历史改变的是是否启用该修正，尚未证明丰富的患者特异动作排序。" if adapted_value and len({r['action']['action_hash'] for r in adapted_value})==1 else 'Value 的具体动作差异与资格逐患者列于结果表；不把模型预测差异直接作为实际个体化收益。')
    outcomes=table(['患者 / split','方法','实际动作','JF / N·s','相对 B 降力 / N·s','相对 disabled 降力 / N·s','完整资格','历史因果增益'],[[r['patient_id']+' / '+r['split'],r['method'],action(r),n(r['JF_N_s']),n(r['gain_vs_B_N_s'],6),n(r['gain_vs_disabled_N_s'],6),'PASS' if r['complete_qualified'] else 'FAIL','YES' if r['strict_history_ablation_pass'] else '未证明'] for r in learn])
    summary=table(['方法','运行患者','动作改变','完整资格','优于匹配 B 且合格','严格 history 消融通过','未见患者消融通过'],[[m,len(rr),sum(r['action_adapted'] for r in rr),sum(r['complete_qualified'] for r in rr),sum(r['complete_qualified'] and (r['gain_vs_B_N_s'] or 0)>.01 for r in rr),sum(r['strict_history_ablation_pass'] for r in rr),sum(r['split']=='heldout' and r['strict_history_ablation_pass'] for r in rr)] for m in ['ILC','BO','VALUE'] for rr in [[r for r in learn if r['method']==m]]])
    qtable=table(['患者','方法','safety','task','execution','原 motion','完整资格','JF / N·s','moment / N·m·s','knee RMS / °','失败项'],[[r['patient_id'],r['method'],r['absolute_safety'],r['task'],r['execution'],r['motion_relative'],'PASS' if r['complete_qualified'] else 'FAIL',n(r['JF_N_s']),n(r['moment_Nm_s']),n(None if r['tracking_RMS_deg'] is None else r['tracking_RMS_deg'][1]),', '.join(r['failed_motion']) or '—'] for r in rows])
    tradeoffs=[]
    for r in rows:
        if r['method'] not in ['ILC','BO','VALUE','H150'] or not r['complete_task']:continue
        base=next(b for b in rows if b['patient_id']==r['patient_id'] and b['method']=='B')
        a=read('reports/'+r['id']+'_MEASURED.json');b=read('reports/'+base['id']+'_MEASURED.json')
        changes=[100*(a['motion']['raw']['full'][k]['rms'][1]/b['motion']['raw']['full'][k]['rms'][1]-1) for k in ['velocity_deg_s','acceleration_deg_s2','jerk_deg_s3']]
        tradeoffs.append([r['patient_id'],r['method'],n(r['moment_Nm_s']-base['moment_Nm_s'],6),n(r['tracking_RMS_deg'][1]-base['tracking_RMS_deg'][1],6),*[n(v,4) for v in changes],n(r['motion_extra']['return_undershoot_deg'][1]-base['motion_extra']['return_undershoot_deg'][1],6)])
    motiontable=table(['患者','方法','Δmoment / N·m·s','Δknee tracking / °','knee velocity RMS Δ%','knee acceleration RMS Δ%','knee jerk RMS Δ%','ΔRETURN膝下冲 / °'],tradeoffs)
    thirdtable=table(['患者','T3 B JF','T3 KEEP JF','T3 更新 JF','更新相对 KEEP 降力','三个分支均完整合格','重复获益'],[[t['patient_id']]+[n(next(r['J_F_N_s'] for r in t['rows'] if r['method']==m),6) for m in ['B','KEEP','ILC']]+[n(t['improvement_vs_KEEP_N_s'],6),all(r['complete_qualified'] for r in t['rows']),t['few_repetition_benefit']] for t in cont['third_repetition']])
    selection_rows=[[r['patient_id'],r['method'],action(r),d['applicable'],n(d['predictions'][d['selected_index']]['predicted_full_JF_N_s']),n(d['predictions'][d['selected_index']]['uncertainty_N_s']),n(r['JF_N_s']),selection_reason(d)] for r in rows if r['method'].startswith(('BO','VALUE')) for d in [next(z['decision'] for z in read(('P00R' if r['patient_id']=='P00' else r['patient_id'])+'_RESULTS.json')['rows'] if z['id']==r['id'])]]
    selection_headers=['患者','方法','选择','适用域','预测 JF','标准差/保守误差','实际 JF','选择依据']
    selected=table(selection_headers,selection_rows)
    selected_bo=table(selection_headers,[r for r in selection_rows if r[1].startswith('BO')])
    selected_value=table(selection_headers,[r for r in selection_rows if r[1].startswith('VALUE')])
    def method_outcomes(method):
        return table(['患者','split','相对 B 降力 / N·s','相对 disabled 降力 / N·s','完整资格','严格历史消融'],[[r['patient_id'],r['split'],n(r['gain_vs_B_N_s'],6),n(r['gain_vs_disabled_N_s'],6),r['complete_qualified'],r['strict_history_ablation_pass']] for r in learn if r['method']==method])
    histories=[]
    for g in executed:
        group='P00R' if g['patient_id']=='P00' else g['patient_id'];h=read('learning/'+group+'_T1_HISTORY.json')
        histories.append([g['patient_id'],g['split'],h['sample_count'],n(h['JF_N_s']),n(h['features'][2]),n(h['features'][3]),n(h['features'][4],6),n(h['features'][5],6)])
    htable=table(['患者','split','5ms样本','Trial1 JF','OUT mid force','RET mid force','OUT膝误差/°','RET膝误差/°'],histories)
    fixedtable=table(['开发动作','患者数','完整资格','平均相对匹配 B 降力 / N·s'],[[m,len(rr),sum(r['complete_qualified'] for r in rr),n(float(np.mean([r['gain_vs_B_N_s'] for r in rr])),6)] for m in ['ILC','O_MINUS','O_PLUS','R_MINUS','R_PLUS'] for rr in [[r for r in rows if r['split']=='development' and r['method']==m]]])
    conclusion=('YES，但仅限列明的患者、动作和工程资格：'+', '.join(r['patient_id']+'/'+r['method'] for r in causal)+' 的 history-enabled 优于同起点固定 B 与相同规则的 history-disabled。'
        if causal else 'NOT_DEMONSTRATED：本轮没有方法通过严格的患者历史消融，不能声称第一次运动的患者特异历史使第二次运动优于不学习方案。')
    conclusion+=' 不能由此推导优于冻结 H150、开发数据中的最佳固定小扰动、广泛患者泛化或临床有效。'
    if held:general='未见患者上的独立合格消融收益出现在 '+', '.join(r['patient_id']+'/'+r['method'] for r in held)+'；这是有限工程证据。'
    else:general='三个未见患者上没有建立患者历史带来的独立合格收益。'
    write('REPORT.md',f'''# iHEAR：完整历史到下一次康复运动学习 v1

## 核心回答

**{conclusion}**

{general} 本轮研究层级为 MuJoCo `SCIENTIFIC_SIMULATION`；原 B-relative motion/fairness 是工程可比资格，不是临床安全阈值。

{summary}

## 证据和预算

共 {acc['starts']} 个 START / {acc['ends']} 个 END，预算上限 80。包含首次父轨迹、准备边界、失败、同起点 fork 和第三次重复；完整任务 {acc['complete_task_results']} 个，独立复算 {acc['total_recomputed_complete_tasks']} 个。实际新增 native steps 为 {acc['total_new_native_steps']:,}，它们不是独立训练样本。实际运行 {len(executed)} 个独立患者，P00R 是 P00 的重试身份。成功执行比较的完整 live 父状态共有 {acc['executed_matched_live_parent_count']} 个，其中同患者不同 repetition 仍不具有患者级统计独立性。

训练只有 {train['training_patients']} 个独立患者、{train['independent_parents']} 个 Trial2 父状态、{train['full_action_results']} 个完整网格动作结果。所有学习器冻结后才运行 V12 与 U14–U16。V13 在查看验证/测试结果之前因预算分配明确保留为 NOT_RUN。P05/P08 的第三次重复由自己的第二次 ILC 分支继续；不拼接其他方法状态。纯 PPO/SAC、神经网络以及 Bellman 多步学习均 NOT_RUN。

原始证据见 `source/results/`（trace、native、receipt）、`learning/`（完整因果历史及冻结决策）、`reports/`、`motion_series/`、`models/`、`audit/`。执行时间、代码/患者/动作哈希、returncode、partial 原因和 native 成本见 `ATTEMPT_ACCOUNTING.json` 与不可覆盖的 `ATTEMPTS.jsonl`。

## 十三个研究问题

### 1–2. 第一次运动提供了什么？哪些特征因果可用？

保存整次 OUTBOUND/HOLD/RETURN 的合法状态估计、reference、测量 force/moment、source age、commissioning belief、执行提案与 applied receipts；按真实 phase 和参考进度对齐。紧凑表示含完整/分 phase 积分、负担窗口、tracking、估计速度/加速度/jerk。没有将 JF 单标量冒充全部历史。原始历史始终保留，选择器仅使用明确允许的输入。

{htable}

力窗口和误差随患者变化，但负担最高窗口不等于动作收益最大的窗口。native Human qpos/qvel、真实模型系数、native motion 门与下一次结果只用于离线标签/评估，没有进入在线历史或策略。估计 5ms 导数不是 0.25ms native 资格指标。

### 3. 实际学到了什么？

ILC 使用事前固定的增益 0.25，将高负担窗口的中间膝参考向上一轮 estimated actual-reference 偏差方向移动，累计限幅 ±0.3°；它没有学习未知力梯度。BO 用实际开发动作数据训练独立成本和 motion-margin GP，再用当前患者已完成 B 的真实历史做一次有噪条件更新。Value 用显式 history×action 特征的正则化回归 ensemble，训练预测下一次完整成本、执行资格和 motion margin；在线只更新输入 context，权重不再变化。二者均标记 **DATA_LIMITED**，不是成功的 Bellman Q-learning。

### 4–7. 提出了什么动作，谁改变、谁获益，是否优于固定及 disabled？

{outcomes}

动作绑定零基 slot：OUTBOUND[1] 或 RETURN[3]，只改中间膝姿态；原 hip 目标、段时长、pass velocity、终点和 HOLD 保持原合同。certificate/admission/activation 和 native command 所有权必须通过。开发网格四方向是预注册固定对照，不是事后学习收益。严格消融在验证/测试使用相同规则、冻结群体平均历史填补或模型平均 context，当前患者历史不传入。开发 ILC 对 B 的零更新消融较弱，不能代替此检验。

冻结 H150 是另一完整低力对照，其资格逐患者单列，不能以它降力掩盖 motion 失败，也不能把运动门失败记作绝对安全失败。所有候选、正负结果、拒绝和 partial 均保留。所有增益是同一个完整 live parent 的配对比较；跨 repetition 的原始 JF 差异不解释为学习收益。

{fixedtable}

这张表只描述已经执行的开发网格，不是新增确认试验。相同模型/规则的 disabled 消融可识别当前历史对选择的贡献，但它不等价于“开发数据选出的最佳统一固定策略”。特别是 Value 选择 RETURN −0.3° 时，执行的参数本身也是一个固定网格动作。尚未证明历史个体化必要地优于这种强固定小扰动；不把该未检验结论附加到历史消融的正结果上。

{value_action_note}

### 8. 第三次真实重复是否进一步改善？

{thirdtable}

T3 的 KEEP 保留该分支 T2 动作，更新臂只能读该分支 T2 历史。`FEW_REPETITION_BENEFIT` 要求 T2 相对匹配 B 合格获益，且 T3 相对 KEEP 再次合格获益；一次正向 T3 数值不足以通过此标志。

### 9–10. 哪些仅属开发结果，未见患者如何？

P00/P05/P08 均是已公开的开发身份。旧 P09–P11 不再充当未见患者。新 V12、U14–U16 在实验前冻结物理生成种子及参数；模型/方法冻结早于其 Trial1，所有 Trial2 动作又冻结早于该患者任何 Trial2 结果。{general} 三个 heldout 不足以建立广泛跨患者可靠性。

本轮结束后这些已执行患者的结果已经公开；后续若据此修改算法，不能继续把 U14–U16 称作新算法的严格未见测试。V13 仍为本包 NOT_RUN，未生成任何物理结果。

### 11. 数据不足或模型不可靠的表现是什么？

{selected}

只有三个训练患者；17 维显式特征经 ridge 正则化，leave-one-patient-out 误差仍不能成为可靠概率校准。GP 采用原始任务重复间存在漂移的噪声下限，把上一轮 B 作为带噪同局部观察是经验假设，不是第二次回报标签。预测 motion margin 只覆盖选定工程余量，不能替代任何原门。域外/不确定时选择 A0 应记录 NO_ACTION_CHANGE；较保守的预测器没有带来动作变化时，不能宣传为学习增益。

冻结模型诊断：设计矩阵秩为 {diag['design_rank']}/{diag['feature_columns']}；成本头交互系数 L2 范数为 {n(diag['full_cost_head_interaction_l2_norm'],6)}，不是旧模型那种会在动作排序中完全抵消的纯状态项。开发上下文下，未加保守项的 full-fit 排序在 P05 更偏向 OUTBOUND 负向，在 P00/P08 更偏向 RETURN 负向；这只是模型诊断。Value 的成本误差下限为 {n(diag['model_value_cost_error_floor_N_s'],6)} N·s，GP 观察噪声为 {n(diag['GP_observation_noise_N_s'],6)} N·s，均与小幅动作收益同量级或更大。真实策略选择和物理收益仍须单独检验。

内部留一开发患者诊断还有一项限制：被留出的患者行不参与对应 ridge fit，但标准化均值/尺度仍来自全部三个开发患者。因此它不是严格独立的留一校准，误差下限只能作启发式风险控制。正式 validation/heldout 患者的特征与标签从未进入训练或标准化；两者须区分。发现后保持已冻结模型和所有真实结果，不作测试后重训。详见 `INTERNAL_VALIDATION_CAVEAT.json`；下一研究应在每个训练折内独立拟合预处理并另留校准患者。

完整成本预测以已知首轮 JF 为基线；绝对误差小不等于动作优势预测准确。history-disabled 没有当前患者的该基线，采用开发平均值。图5因此同时展示完整成本与同 context 的 action−B 配对优势，后者更接近本研究真正要识别的增益。

### 12–13. 哪个动作方向值得扩大？下一步是什么？

先扩大跨患者、同父状态的局部膝姿态正负扰动数据，尤其对比 OUTBOUND 高力窗口和 RETURN[3]，辨识动作条件下的力梯度与 motion 代价。P00 的固定 RETURN 负向网格收益高于其高负担窗口 ILC，已经证伪“最高力窗口自然就是最好修改位置”的强假设。保留低维有界参考优化，优先直接预测同父状态 action−B 优势并校准其不确定性，避免跨 repetition 状态漂移压过小控制收益；现阶段没有证据支持直接升级复杂 Neural Value/Q-learning 或大规模纯 RL。

## 分离验收标志

{table(['标志','结果'],[[k,str(v)] for k,v in flags.items()])}

`HISTORY_DATA_READY`、模型训练、动作改变、完整资格与历史因果收益是独立证据层级。0.01 N·s 是本包保守的收益报告门槛，不是原资格门、临床重要性标准或统计显著性阈值。更小的正向力差保留为 `QUALIFIED_SMALL_FORCE_SIGNAL_BELOW_0_01_N_s`，不抹去其原始数值，也不把它自动升格为历史因果收益。

## 完整资格与运动代价

{qtable}

完整 phase 积分和 native velocity/acceleration/jerk 在每个 `*_MEASURED.json`、`*_INDEPENDENT.json`；RETURN extrema 和终点另见 `derived/TERMINAL_RECHECK.json`。不以更低 partial JF 与完整任务排名。

下表均相对同起点 B，负数表示该诊断量降低。某项平顺性改善与累计力改善分开解释，不能用一项降低抵消其他资格失败。

{motiontable}

## 连续性、修复及限制

原合法 inter-repetition boundary 每次运行真实 native 步进；所有边界时间、保持命令及其 receipt 单独记录。后续任务通过原 fresh TRACK bootstrap（额外 10ms）进入 TASK，plant、measurement、observer、allocator、updater 等持久对象保留；原框架规定的临时 lifecycle/session/reference 状态重建。每个比较来自完整 Linux live address-space fork，父进程等待子进程，前后完整状态哈希一致。Python `os.fork` 自动 reseed 导致最初 P00 零步子进程校验失败；只修复隔离 fork RNG 恢复并保留失败，P00R 再执行零改动 raw/native/receipt 精确复现。没有写入 Human qpos/qvel。

实验编排器在首轮之后进行离线原资格审查，以确定是否能够形成合格配对；这个实验资格步骤会读 evaluation-only truth，但它不是学习器输入，也不改变其动作规则。部署层面的真实 wall-clock 时限与 `HOST_EXECUTION_CAUSAL_VALID` 在本科学仿真中为 NOT_EVALUABLE；这里的 execution PASS 指原科学模式的证书、causal receipt 和 native 命令所有权。

P00R v2 的准备 bootstrap 成本未独立导出，但实际额外时间、native、receipt 和命令保留；v3 后各 repetition 的准备元数据单独保存。所有主要 JF 都是完整 TASK，准备成本不并入目标。确定性单种子、狭窄虚拟参数范围、三个训练患者和三个 heldout、少量重复及微小力差，限制了结论范围。原安全门不改变；本包不晋升正式控制器。

BO/Value 只验证了固定 B 首轮到第二轮的条件优化；第三轮只运行 ILC。不能把这些结果解释为 BO/Value 在任意先前动作下的多轮收敛或长期价值学习。

## 图与核验

![完整历史到动作](figures/01_history_to_action.png)
![方法对照](figures/02_methods_force_moment_tracking.png)
![连续重复](figures/03_continuous_trials.png)
![真实运动与力](figures/04_actual_motion_force.png)
![预测与实际](figures/05_prediction_vs_observation.png)
![资格矩阵](figures/06_qualification_matrix.png)

最终保护、所有权退出、独立复算、split、历史隔离、交付 manifest 结果以 `PACKAGE_VERIFICATION.json` 为准。研究结束后 STOP，不自动继续研究。
''')
    write('ILC_STUDY.md',f'''# History-based iterative correction

规则在下一次结果可见之前固定：选择 OUTBOUND/RETURN 参考进度 0.2–0.6 中平均测量力较大的窗口；`a_next=clip(a_previous+0.25*(estimated_actual-reference knee lag), ±0.3deg)`。OUTBOUND[1] / RETURN[3] 的中间膝姿态经原证书和 admission 执行，终点不改。其可证伪假设是顺应误差方向减小 cuff 负担；没有已识别的力梯度或收敛证明。

{table(['患者','动作','相对 B 降力','相对 disabled 降力','完整资格','严格消融'],[[r['patient_id'],action(r),n(r['gain_vs_B_N_s'],6),n(r['gain_vs_disabled_N_s'],6),r['complete_qualified'],r['strict_history_ablation_pass']] for r in learn if r['method']=='ILC'])}

{thirdtable}

开发 disabled=B 零更新；验证和测试 disabled=三个开发患者平均合法特征，使用同一修正律，当前患者历史 withheld。后者防止把一项普遍有效的固定扰动误认作个体历史学习。直接跨 repetition 的 JF 减少受起始状态漂移影响，不能代替 matched KEEP/B。

方法背景参见 [Bristow、Tharayil、Alleyne，2006 ILC survey](https://experts.illinois.edu/en/publications/survey-of-iterative-learning-control-a-learning-based-method-for-/)。本实验只是受历史误差启发的有界迭代修正，不声称满足综述中的线性系统收敛条件。
''')
    write('BAYESIAN_OPTIMIZATION_STUDY.md',f'''# Constrained Bayesian optimization

实际训练样本 {train['full_action_results']}，来自三个开发患者、三个同父状态动作网格。输入是四个 phase-local force/tracking 特征以及两个有界动作坐标；成本 GP 和 motion-margin GP 分开，实际 execution 结果用 Beta(1,1) 平滑。核、尺度、噪声和阈值见冻结源码与 NPZ；未知/拒绝动作不获得虚构回报。

history-enabled 加入当前患者实际 Trial1 B 的带噪成本观察，history-disabled 不读取该历史，仅用训练平均 context。重复初态漂移由开发 B 的实际漂移设噪声下限，仍是局部平稳性假设。资格概率未经充分校准，保守 EI 每患者只有一个探索提案，原物理证书和所有安全/task/motion 门仍最终裁决。**DATA_LIMITED；不是形式安全控制器。**

{selected_bo}

{method_outcomes('BO')}

BO 在四个新患者上均完整合格，但只有 U16 实际改变动作；该次完整力积分增加 0.330361 N·s，未取得力收益。其 cuff moment 降低 0.096051 N·m·s、膝 tracking RMS 降低 0.001390°，是付出更高累计力的局部运动代价交换，不能升级为降力学习成功。其余三位患者与 disabled 同选 B，记 NO_ACTION_CHANGE。候选预测资格不足不等于候选已被真实物理判定非法。

是否实际改变和产生合格历史收益，以 REPORT 的分离标志与实际结果为准。随机搜索 NOT_RUN；四个预注册固定网格、固定 B/H150、简单 ILC 和 disabled 提供对照，不能仅凭 surrogate prediction 选胜者。

方法背景：[Gelbart、Snoek、Adams，Bayesian Optimization with Unknown Constraints](https://arxiv.org/abs/1403.5607)。这里只采用分离成本/资格预测和受约束采集的思路，不宣称复现完整算法或其性能。
''')
    write('HISTORY_VALUE_STUDY.md',f'''# History-conditioned value regression

模型是 17 维 ridge ensemble：截距、四个标准化历史特征、两个动作、两个动作平方、八个显式 history×action 交互。三个输出是 `J2-J1` 完整成本差、选定 motion margin、execution/task 资格。训练一次 full fit 和三次 leave-one-patient-out fit，λ=1；没有神经网络、TD 或 Bellman backup。

内部留一拟合共享全开发集的标准化参数，不能称为严格独立的不确定性校准；外部验证/测试不参与该标准化。见 `INTERNAL_VALIDATION_CAVEAT.json`。本包保留原冻结模型，不以测试后重训掩盖这一限制。

{train['full_action_results']} 个完整动作结果不等于同样多独立患者；只有三个患者/父状态，因此 **DATA_LIMITED**。持久权重见 `models/history_models.npz`，真实标签见 `models/TRAINING_DATA.json`，留患者误差见 `models/LEAVE_PATIENT_OUT.json`。预测误差下限和 ensemble spread 用于保守选择，不是可靠校准置信界。

{selected_value}

{method_outcomes('VALUE')}

V12、U14、U15 通过完整资格且优于同规则 disabled 与匹配 B；U16 回退 B，未获历史收益。三次干预都为 RETURN[3] 膝 −0.3°，当前证据说明历史改变了是否启用修正，尚未证明优于开发数据选出的统一固定 RETURN 负向动作，也没有超过合格 H150 的降力水平。微小降力伴随 moment、tracking 或局部下冲增加，详见主报告的逐项运动代价表。

在线 context 来自允许的完整历史；disabled 用训练平均 context 且函数断言其 history 参数必须为 None。若选择 B，则 NO_ACTION_CHANGE；若选择与 disabled 相同动作，不能声称历史反馈有额外贡献。完整结果和失败单列，不能用训练拟合宣传泛化。
''')
    write('NEXT_RESEARCH_DECISION.md',f'''# 下一研究决策：STOP，保留低维少重复优化

{conclusion}

下一阶段应先扩大独立患者与 matched local action 数据，辨识 OUTBOUND[1]/RETURN[3] 小幅膝姿态的条件收益方向，而非扩大到全部18D或直接升级复杂 neural/Q-learning。需要把完整力增益与 moment、tracking、native motion 和准备成本一起建模，建立患者级误差校准，并增加真实连续重复与 KEEP 消融。

必须加入只用开发数据预选的强固定 RETURN[3] 膝 −0.3° 对照，检验个体历史是否比一个普遍有效的小扰动更有价值。校准时应在每个患者留出折内重新拟合标准化；最终评价另用未暴露患者，不复用本轮已公开的 U14–U16 充当新算法的未见测试。

目前训练只有三个患者。更复杂模型、PPO/SAC、正式 B/H150 升级均没有足够依据，本次不启动。所有原始负结果与失败留存。仅可将本包作为下一研究设计证据；必须另行授权后再开始新的研究包。
''')
    print('REPORT_RENDERED_NOT_WRITTEN' if '--check' in sys.argv else 'REPORTS_WRITTEN',conclusion,flush=True)
if __name__=='__main__':main()
