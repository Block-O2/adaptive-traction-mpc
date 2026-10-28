from pathlib import Path
p=Path('/home/hank/ihear-lab/learning_guided_motion_improvement_v1');f=p/'source/write_report.py';s=f.read_text()
s=s.replace("newrows={} if new is None else", "postdiag=load('audit/POSTHOC_MODEL_VS_SEARCH_DIAGNOSIS.json') if (P/'audit/POSTHOC_MODEL_VS_SEARCH_DIAGNOSIS.json').exists() else None;newrows={} if new is None else")
needle="\n if new is None:lines.append('未运行；不能声称新状态验证通过。')"
addition='''
 failed=[r for vv in results['rows'].values() for r in vv if r.get('complete') and not r.get('qualified')]
 failure_section=['','## 低force但原motion失败的本轮反例','']
 if not failed:failure_section.append('本轮当前参数域未观察到完整motion失败；这不证明预测器能识别失败域。')
 for r in failed:
  mm=measurement(r);failure_section.append(f"`{r['id']}` x={r['x']}，完整JF={fmt(r['JF'])}，原门失败={r['motion_vs_B']['failed_requirements']}；raw jerk RMS hip/knee={mm['motion']['raw']['full']['jerk_deg_s3']['rms']} °/s³。原physical/task轴={mm['axes']['PHYSICAL_TASK_VALID']}。该点只保留原始积分与负结果，不进入正式收益排名。")
 if postdiag:
  for r in postdiag.get('unqualified_complete_counterexamples',[]):failure_section.append(f"冻结最后C模型对未见失败动作`{r['id']}`的事后只读预测：motion UCB={fmt(r['frozen_C_motion_UCB'])}，实际最差原门比={fmt(r['actual_worst_ratio'])}；会预测motion通过={r['frozen_C_would_predict_motion_pass']}。这是未用于C实际选点的离线诊断，不冒称C实际执行过该点；反馈未回流任何proposal。")
 failure_section+=['','这类反例说明名义负荷或局部GP余量不能替代真实原门；不删除瞬态、不用滤波门替代raw，也不以任务完成冒充motion通过。']
 lines[-3:-3]=failure_section
 if new is None:lines.append('未运行；不能声称新状态验证通过。')'''
assert needle in s;s=s.replace(needle,'\n'+addition)
s=s.replace("for label,row,m in [('B',None,Bm),('H150',None,Hm)]+[(arm,best[arm],measurement(best[arm])) for arm in 'ABC']:", "for label,row,m in [('B',None,Bm),('H150',None,Hm)]+[(arm,best[arm],measurement(best[arm])) for arm in 'ABC']+[(r['id']+' FAIL',r,measurement(r)) for r in failed]:")
f.write_text(s);import ast;ast.parse(s);print('MOTION_FAILURE_AND_FROZEN_MODEL_LIMITS_INCLUDED')
