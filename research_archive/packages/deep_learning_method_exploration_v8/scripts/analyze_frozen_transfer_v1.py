"""Read only complete frozen predictions/results; never refits or reselects."""
from pathlib import Path
import json,hashlib,time,statistics
P=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
groups=['V8CTX01','V8CTX02','V8CTX03','V8CTX04'];contexts=[];outcomes=[];models={};sources={}
for group in groups:
    supervisor=load(P/'owned'/(group+'_SUPERVISOR_END.json'))
    assert supervisor['state']=='STOP' and supervisor['worker_exit_code']==0 and not supervisor['survivors']
    assert load(P/'jobs'/group/'WORKER_DONE.json')['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'
    link_path=P/'analysis'/(group+'_SELECTOR_EXECUTION_LINK.json');link=load(link_path)
    original=load(P/'predictions'/(group+'_FROZEN_CONTEXT_DECISIONS.json'))
    history=load(P/'predictions'/(group+'_FROZEN_HISTORY_DECISIONS.json'))
    assert original['before_any_candidate_outcome'] and history['B_completed_before_selection']
    rows={tag:load(P/'attempts'/(ident+'_RESULT.json')) for tag,ident in link['rows_by_tag'].items()}
    base=rows['B'];assert base['complete'] and base['qualified']
    menu={tag:row for tag,row in rows.items() if tag!='HISTORY_B'}
    qualified=[(tag,row) for tag,row in menu.items() if row['complete'] and row['qualified']]
    best_tag,best=min(qualified,key=lambda item:(item[1]['JF'],item[0]))
    config=load(P/'experiments'/(group+'.json'))
    contexts.append({'group':group,'case_key':config['case_key'],'best_qualified_menu_tag_evaluation_only':best_tag,'best_qualified_JF':best['JF'],'B_JF':base['JF'],'B_JM':base['JM'],'qualified_menu_tags':[tag for tag,row in qualified]})
    for tag,row in menu.items():
        outcomes.append({'group':group,'tag':tag,'id':row['id'],'complete':row['complete'],'qualified':row['qualified'],'JF':row.get('JF'),'JM':row.get('JM'),'delta_JF_vs_B':row.get('JF',0)-base['JF'] if row.get('JF') is not None else None,'delta_JM_vs_B':row.get('JM',0)-base['JM'] if row.get('JM') is not None else None,'motion_failed_requirements':row.get('motion_vs_B',{}).get('failed_requirements'),'axes':row.get('axes'),'actual_new_native_steps':row['actual_new_native_steps']})
    decisions={**{label:('A_B_FROZEN',d.get('choice_tag') or 'B',d.get('choice_tag') is None) for label,d in link['decisions'].items()},**{'C_'+label:('C_COLD_REPLAY_HISTORY',d['selected_tag'],False) for label,d in link['history_decisions'].items()}}
    for label,(scope,tag,abstained) in decisions.items():
        actual_tag='HISTORY_B' if label.startswith('C_') and tag=='B' else tag
        row=rows[actual_tag];valid=bool(row['complete'] and row['qualified'])
        rec={'group':group,'selector':label,'scope':scope,'selected_tag':tag,'actual_execution_id':row['id'],'abstained_to_B':abstained,'complete':row['complete'],'qualified':row['qualified'],'JF_if_qualified':row['JF'] if valid else None,'JM_if_qualified':row['JM'] if valid else None,'delta_JF_vs_B_if_qualified':row['JF']-base['JF'] if valid else None,'delta_JM_vs_B_if_qualified':row['JM']-base['JM'] if valid else None,'regret_to_best_qualified_menu_JF_if_qualified':row['JF']-best['JF'] if valid else None,'shared_recipe_not_independent_replication':True}
        models.setdefault(label,[]).append(rec)
    for path in [link_path,P/'predictions'/(group+'_FROZEN_CONTEXT_DECISIONS.json'),P/'predictions'/(group+'_FROZEN_HISTORY_DECISIONS.json')]+[P/'attempts'/(row['id']+'_RESULT.json') for row in rows.values()]:sources[str(path.relative_to(P))]=sha(path)
summary=[]
for label,records in models.items():
    valid=[r for r in records if r['qualified']]
    summary.append({'selector':label,'qualified_cases':len(valid),'total_cases':len(records),'choices':[r['selected_tag'] for r in records],'all_cases_qualified':len(valid)==len(records),'sum_delta_JF_vs_B_over_qualified_cases':sum(r['delta_JF_vs_B_if_qualified'] for r in valid),'sum_delta_JM_vs_B_over_qualified_cases':sum(r['delta_JM_vs_B_if_qualified'] for r in valid),'mean_qualified_menu_regret':statistics.mean(r['regret_to_best_qualified_menu_JF_if_qualified'] for r in valid) if valid else None,'failed_cases_not_assigned_low_partial_cost':True})
result={'schema':'v8.frozen_transfer_comparison.v1','created_unix':time.time(),'scope':'Four preregistered stock virtual conditions, frozen new-execution transfer. No clinical/IID-patient claim; do not tune V1 then reuse as heldout. C is cold replay, not continuous Trial.','contexts':contexts,'menu_outcomes':outcomes,'selector_summary':summary,'selector_records':models,'source_sha256':sources,'real_physical_attempts_saved':0,'full_menu_oracle_is_posthoc_evaluation_upper_bound_not_deployable_teacher':True,'model_refits':0,'new_physics':0}
out=P/'analysis/FROZEN_TRANSFER_COMPARISON_V1.json'
with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
lines=['# 四个冻结条件：同权限完整菜单与学习选择','',result['scope'],'',
'|选择器|原资格|四条件选择|合格条件ΔJF总和(N·s)|合格条件ΔJM总和(N·m·s)|','|---|---:|---|---:|---:|']
for row in summary:lines.append(f"|{row['selector']}|{row['qualified_cases']}/4|{', '.join(row['choices'])}|{row['sum_delta_JF_vs_B_over_qualified_cases']:.6f}|{row['sum_delta_JM_vs_B_over_qualified_cases']:.6f}|")
lines+=['','各行的合格子集可能不同；有资格失败的行不能按合格子集成本排在4/4合格策略之前。B为零增量，同动作执行共享不计独立复制或省试。所有非B完整失败仍保留原JF/JM，只不授予成功排名。','',
'|条件|合格菜单|评价时最小合格JF动作|','|---|---|---|']
for row in contexts:lines.append(f"|{row['group']}|{', '.join(row['qualified_menu_tags'])}|{row['best_qualified_menu_tag_evaluation_only']}|")
lines+=['','每个选择器实际执行ID、原失败项、分量增量及原文件SHA见JSON。此评价没有训练新权重或修改预选结果。判断BASELINE_INCREMENT须同时比较部署前锁定的简单规则、BC/父策略和同权限强传统；菜单最优是评价用上界，不能事后改称已知的部署策略。','']
(P/'analysis/FROZEN_TRANSFER_COMPARISON_V1.md').write_text('\n'.join(lines))
print(json.dumps({'contexts':contexts,'selector_summary':summary},indent=2))
