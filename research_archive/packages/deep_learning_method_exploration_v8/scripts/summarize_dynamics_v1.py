from pathlib import Path
import json,statistics,time,hashlib
P=Path(__file__).resolve().parents[1];F=P/'families/learning_assisted';D=F/'analysis'
def load(name):return json.loads((D/name).read_text())
def mean(v):return statistics.mean(v)
a=load('CAUSAL_DYNAMICS_RESULTS_V1.json');b=load('DIRECT_HORIZON_RESULTS_V2.json');c=load('ACTION_RESPONSE_CONTRASTS_V1.json')
summary={'schema':'v8.dynamics_diagnostic_summary.v1','created_unix':time.time(),'scope':a['scope'],'autoregressive':{},'direct_horizon':{},'action_response':c['rows'],'new_physics':0,'new_policy_updates':0,'ridge_solves_total':a['ridge_solves']+b['ridge_solves']}
for variant in ['absolute','residual','history_residual']:
    rows=[r for r in a['rows'] if r['variant']==variant]
    if not rows:continue
    roll=[w for r in rows for w in r['rollouts']]
    summary['autoregressive'][variant]={'series':len(rows),'one_step_hip_q_RMSE_rad_mean':mean(r['one_step_RMSE'][0] for r in rows),'kinematic_hip_q_RMSE_rad_mean':mean(r['kinematic_RMSE'][0] for r in rows),'absolute_window_JF_error_N_s_mean':mean(abs(w['JF_error']) for w in roll if 'JF_error' in w),'nonfinite_rollouts':sum(w['status']!='FINITE' for w in roll),'horizons':{}}
    for h in [.5,1.]:
        selected=[w for w in roll if w['horizon_s']==h and w['status']=='FINITE']
        summary['autoregressive'][variant]['horizons'][str(h)]={'JF_MAE_N_s':mean(abs(w['JF_error']) for w in selected),'terminal_hip_q_MAE_rad':mean(abs(w['terminal_error'][0]) for w in selected),'windows':len(selected)}
for h in [.5,1.,2.]:
    selected=[r for r in b['rows'] if r['horizon_s']==h]
    summary['direct_horizon'][str(h)]={'JF_MAE_N_s':mean(abs(r['predicted_window_JF']-r['actual_window_JF']) for r in selected),'persistence_JF_MAE_N_s':mean(abs(r['persistence_window_JF']-r['actual_window_JF']) for r in selected),'JM_MAE_Nm_s':mean(abs(r['predicted_window_JM']-r['actual_window_JM']) for r in selected),'persistence_JM_MAE_Nm_s':mean(abs(r['persistence_window_JM']-r['actual_window_JM']) for r in selected),'terminal_hip_q_MAE_rad':mean(abs(r['terminal_error'][0]) for r in selected),'windows':len(selected)}
out=D/'DYNAMICS_DIAGNOSTIC_SUMMARY_V1.json'
with out.open('x') as stream:json.dump(summary,stream,indent=2);stream.write('\n')
lines=['# 学习动力学与辅助优化：阶段结果','',
'结论：在44条已有完整因果轨迹、6个整context开发折中，历史残差改善一步预测，直接多时域模型在1–2秒改善部分窗口成本预测；尚无共同动作前起点的可靠候选排序或真实控制增量。家族为 **NOT_FULLY_EXPLORED**。',
'','数据与身份：所有未来观测只作监督标签；自由展开不回灌未来reference、wrench或Human真值。完整motion失败保留用于动力学预测，1条partial不进入完整成本排名。首个测量起点已在动作后，可能含动作造成的状态差异；动作响应对比不能解读为OUT0反事实控制资格。','',
'|自回归机制|一步hip q RMSE(rad)|展开窗口JF MAE(N·s)|非有限窗口|','|---|---:|---:|---:|']
for name,x in summary['autoregressive'].items():lines.append(f"|{name}|{x['one_step_hip_q_RMSE_rad_mean']:.8g}|{x['absolute_window_JF_error_N_s_mean']:.6g}|{x['nonfinite_rollouts']}|")
lines+=['','运动学基线hip q一步RMSE为 '+str(next(iter(summary['autoregressive'].values()))['kinematic_hip_q_RMSE_rad_mean'])+' rad。一步拟合与自主展开的误差是不同门。','',
'|直接时域(s)|JF MAE|持久值JF MAE|JM MAE|持久值JM MAE|终点hip q MAE(rad)|','|---|---:|---:|---:|---:|---:|']
for h,x in summary['direct_horizon'].items():lines.append(f"|{h}|{x['JF_MAE_N_s']:.6g}|{x['persistence_JF_MAE_N_s']:.6g}|{x['JM_MAE_Nm_s']:.6g}|{x['persistence_JM_MAE_Nm_s']:.6g}|{x['terminal_hip_q_MAE_rad']:.6g}|")
lines+=['','相对B的40个非平凡动作窗口成本对比：']
for x in c['rows']:lines.append(f"- {x['variant']}：方向正确{x['sign_correct']}/{x['contrasts']}，对比MAE {x['mean_absolute_contrast_error_N_s']:.6g} N·s。")
lines+=['','已实施修正：由绝对next-observation改为运动学加残差；加入合法3-boundary过去历史；随后直接预测0.5/1/2秒终点变化及JF/JM分量，避免反复一步传播。未改变原物理、planner、任务或评价门。',
'','机制判断：CONFIRMED——一步状态误差不能授予控制有效性；SUPPORTED——过去历史和直接多时域目标在当前整context开发诊断中有信息；HYPOTHESIS——未来合法reference生成器/phase结构与足够动作覆盖可能改善模型；NOT_TESTED——模型梯度控制、概率ensemble、planner内反事实rollout及独立新条件控制收益。',
'','资源：两轮共36个ridge求解；0新物理、0策略更新。E1 wall约7.99s/CPU8.07s，直接时域wall约3.15s/CPU3.23s；各进程峰值RSS约598MiB。原结果、进程START/END及源/数据SHA均保留。',
'','后续决定：优先真实新条件策略采样与连续Trial接口闭合。当前数据不足以批准复杂World Model驱动策略；不作World Model家族否定。未运行的E4/概率模型、原planner未来reference条件化与共同动作前验证明确保留为NOT_RUN。',
'','证据：[汇总](analysis/DYNAMICS_DIAGNOSTIC_SUMMARY_V1.json)、[原自回归结果](analysis/CAUSAL_DYNAMICS_RESULTS_V1.json)、[直接时域结果](analysis/DIRECT_HORIZON_RESULTS_V2.json)。','']
(F/'RESULTS_V1.md').write_text('\n'.join(lines))
matrix='''# E 学习辅助优化与动力学模型探索

v7 GP/二次面/stump历史已恢复。本轮检验因果动力学的动作响应及自主展开；不以一步拟合代替真实控制。

|变体|针对机制|公平对照|覆盖/结果|
|---|---|---|---|
|E1绝对next-observation ridge|基础预测是否学到信息|persistence/kinematic|COMPLETED：18求解中的6；一步q弱于运动学|
|E2运动学+线性残差|去除容易的已知运动学|E1/kinematic|COMPLETED：6求解；一步改善未带来更好的自主JF|
|E3合法过去3-boundary残差|局部速度/负担变化信息|E2|COMPLETED：6求解；一步及展开JF改善，动作对比MAE未优于所有简单变体|
|E4直接0.5/1/2s终点delta+JF/JM|避免一步误差反复传播|同窗persistence|COMPLETED：18求解；1/2s JF较优，0.5s较差|
|E5原planner未来reference/phase结构|解决外生reference未知|原planner+简单残差|NOT_RUN|
|E6概率ensemble/模型梯度控制|不确定性与优化|先通过共同动作前响应门|NOT_RUN|

数据：44条已有完整轨迹、6整context开发折；未来观测只作标签，无新物理。起点首个已有post-action boundary，不授予OUT0排序资格。36个ridge求解、0策略更新。见RESULTS_V1.md及分析JSON。

当前机制覆盖已跨目标、历史表示、残差结构与传播方式；缺共同动作前响应、概率校准、独立控制、强传统增量和净效率。因此家族NOT_FULLY_EXPLORED，没有整体否定。
'''
(F/'METHOD_EXPLORATION_MATRIX.md').write_text(matrix)
with (F/'METHOD_VARIANT_LEDGER.jsonl').open('a') as stream:
 for name,solves in [('absolute_next_observation',6),('kinematic_residual',6),('history_residual',6),('direct_multihorizon_components',18)]:stream.write(json.dumps({'unix':time.time(),'variant':name,'status':'COMPLETED_DIAGNOSTIC_ONLY','scope':'6 whole-context development folds; post-action inputs','ridge_solves':solves,'new_physics':0,'new_policy_updates':0,'decision_valid':False,'task_increment':False,'family_status':'NOT_FULLY_EXPLORED','summary_path':str(out.relative_to(P))},ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['autoregressive']},indent=2))
