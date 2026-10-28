"""Evidence-based report builder; absent branches stay explicitly NOT_RUN."""
from pathlib import Path
import json,collections,time,datetime
import numpy as np
from acl2_shared import P,R,put,read,utc,sha,records,native_used
def optional(n,default=None):return read(n) if (P/n).exists() else default
def write(n,s):(P/n).write_text(s+'\n')
def main(status='RUNNING'):
 A=read('ACTIVATION.json');elapsed=(time.time()-A['t0_unix'])/3600
 rows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()] if (P/'ALL_RESULTS.jsonl').exists() else []
 starts=[r for r in records() if r['event']=='START'];byid={r['id']:r for r in rows};nominal=[r for r in rows if not r['id'].startswith('LOCKED_')]
 B=byid.get('INTERFACE_B');H=byid.get('INTERFACE_H150');S=byid.get('INTERFACE_STRONG');qual=[r for r in nominal if r.get('qualified')];best=min(qual,key=lambda r:r['JF'],default=None)
 new=[r for r in nominal if r.get('qualified') and r['action'].get('family','').startswith('modal8') and np.any(np.asarray(r['action'].get('x',[]))!=0)];bestnew=min(new,key=lambda r:r['JF'],default=None)
 gate=optional('audit/RETIMED_INTERFACE_GATE.json',optional('audit/INTERFACE_GATE.json',{}))
 gate=dict(gate);gate['same_family_coordinate_identity']=optional('audit/INTERFACE_A1_ROTATED_REPEAT_GATE.json',{}).get('status')=='PASS';gate['zero_reproduces_H150']=optional('audit/INTERFACE_MODAL_ZERO_REPEAT_GATE.json',{}).get('status')=='PASS'
 audit=optional('audit/INDEPENDENT_RAW_AUDIT.json',{});groups=collections.defaultdict(list)
 for r in rows:groups[r['id'].rsplit('_',1)[0]].append(r)
 methodrows=collections.defaultdict(list)
 for r in rows:
  if r['category']=='optimization':
   parts=r['id'].split('_');methodrows['_'.join(parts[:-1])].append(r)
 table='|方法/分支|真实尝试|完整|原门合格|最佳合格JF N·s|对应JM Nm·s|\n|---|---:|---:|---:|---:|---:|\n'
 for k,v in sorted(methodrows.items()):
  q=min([r for r in v if r.get('qualified')],key=lambda r:r['JF'],default=None);table+='|%s|%d|%d|%d|%s|%s|\n'%(k,len(v),sum(r['complete'] for r in v),sum(r['qualified'] for r in v),f"{q['JF']:.6f}" if q else 'NONE',f"{q['JM']:.6f}" if q else 'NONE')
 def val(r,k='JF'):return 'NOT_RUN' if r is None else f"{r[k]:.6f}"
 def gain(r,ref):return 'NOT_RUN' if r is None or ref is None else f"{ref['JF']-r['JF']:.6f} N·s ({100*(ref['JF']-r['JF'])/ref['JF']:.6f}%)"
 failure=[r for r in rows if not r['qualified']];failurecounts=collections.Counter(x for r in failure for x in (r.get('motion_vs_B',{}).get('failed_requirements') or [r.get('error','UNKNOWN')]))
 ppo=[]
 for f in sorted((P/'jobs').glob('*/PPO_RESULTS.json')):ppo.append(json.loads(f.read_text()))
 ppotext='NOT_RUN：没有完成的 PPO_RESULTS.json；若有 partial rollout/checkpoint，保留于对应 jobs/models，不算完整训练结果。'
 if ppo:
  ppotext='\n\n'.join('模式 %s：训练%d集、%d个RL决策、%d个policy更新epoch（mean/std/value三组Adam各%d次，合计%d组更新）。冻结mean评价 %s。'%(p['mode'],p['training_episodes'],p['RL_decisions'],p['Adam_updates'],p['Adam_updates'],3*p['Adam_updates'],[(e['id'],e.get('qualified'),e.get('JF'),e.get('JM')) for e in p['mean_evaluations']]) for p in ppo)
 learn=[]
 for r in rows:
  pred=r.get('prediction') or {}
  if r.get('complete') and pred.get('model_id') and pred.get('predicted_outcome') is not None:
   learn.append(dict(id=r['id'],x=r['action'].get('x'),pred=pred['predicted_outcome'],nom=pred['anchored_nominal'],actual=[r['JF'],r['JM'],r['worst_ratio']],sd=pred['predicted_sd'],changed=(pred.get('nominal_counterfactual') or {}).get('changed_by_learning',False),qualified=r['qualified']))
 lstats=dict(n=len(learn),learned_decision_changed=sum(r['changed'] for r in learn),caution='Prequential outputs across changing models are descriptive, not frozen independent-state validation.')
 if learn:
  pr=np.asarray([r['pred'] for r in learn]);no=np.asarray([r['nom'] for r in learn]);ac=np.asarray([r['actual'] for r in learn]);sd=np.asarray([r['sd'] for r in learn]);lstats.update(JF_RMSE=float(np.sqrt(np.mean((pr[:,0]-ac[:,0])**2))),nominal_JF_RMSE=float(np.sqrt(np.mean((no[:,0]-ac[:,0])**2))),empirical_95pct_coverage=np.mean(abs(pr-ac)<=1.96*sd,axis=0),predicted_motion_pass_actual_fail=[r['id'] for r in learn if r['pred'][2]+r['sd'][2]<=1 and not r['qualified']])
 put('LEARNING_DECISION_RESULTS.json',dict(summary=lstats,rows=learn))
 lockrows=[r for r in rows if r['id'].startswith('LOCKED_')]
 cross='NOT_RUN：尚无冻结后独立合法prefix评价。'
 if lockrows:
  cross='仅同一名义Human的独立合法prefix，不是跨患者。逐状态B/H150/强固定/冻结方法分别配对，不跨分母比较。\n\n|ID|完整|合格|JF N·s|JM Nm·s|\n|---|---|---|---:|---:|\n'+''.join('|%s|%s|%s|%s|%s|\n'%(r['id'],r['complete'],r['qualified'],val(r),val(r,'JM')) for r in lockrows)
 write('REPRESENTATION_STUDY.md','# 协调表示\n\nA1：同一二维实际运动集合的原坐标与和/差坐标。单动作完整raw一致门：%s。坐标优化结果另见 UPPER_LEVEL_OPTIMIZATION.md。\n\nA2：H150上新增8个去程/回程共同路径、相对路径、局部时长和通过速度模式。零改变完整raw复现：%s。实签参考对比的数值秩：%s/8；这是有限干预证据，不是全局流形维度证明。\n\n设计幅度、实际权限与任务门见 EXPERIMENT_CONTRACT.md、LEARNING_CONTROL_INTERFACE_GUIDE.md 和 audit/INTERFACE_GATE.json。'%(gate.get('same_family_coordinate_identity','NOT_RUN'),gate.get('zero_reproduces_H150','NOT_RUN'),gate.get('observed_issued_reference_contrast_rank','NOT_RUN')))
 write('INTERFACE_EXECUTION_AUDIT.md','# 执行接口审计\n\n'+('NOT_RUN' if not gate else json.dumps(gate,ensure_ascii=False,indent=2))+'\n\n完整 issued/accepted/activated/rejected/applied 身份在每条 summary、EXECUTION_BINDING、原 EXECUTED_RESIDUAL_RECEIPTS、runtime_artifacts 与独立raw重算中保留。参考合法与真实Human motion合格分别判断。')
 write('UPPER_LEVEL_OPTIMIZATION.md','# 上层快速优化\n\n'+table+'\n相同累计真实尝试前缀才作主比较；共同工程、cold parent、模型构建和代理查询单列。方法命名见各jobs配置及source。任何代理最小值均不作真实全局最优或5ms在线声明。')
 write('PHYSICS_AND_LEARNING_COMPARISON.md','# 物理与Learning比较\n\n'+table+'\n名义模型从已完成历史reference和commissioned estimate生成平滑近似负荷，遗漏离散slot、governor、tracking/contact与当前状态准入。其反事实输入不是新候选未来真值。Learning的量值、排序、选择改变与实际收益分别见 LEARNING_DECISION_ANALYSIS.md。')
 write('LEARNING_DECISION_ANALYSIS.md','# Learning决策贡献\n\n'+json.dumps(__import__('acl2_shared').clean(lstats),ensure_ascii=False,indent=2)+'\n\n每次proposal在物理START前绑定模型与训练ID；B/C候选池及C同池名义反事实保留。量值RMSE下降不等于排序提高；排序改善不等于实际选择改变；选择改变后仍需实际合格JF更好。经验motion标签是仿真评价反馈，尚无患者可用传感器合同。')
 write('PPO_STUDY.md','# PPO新接口研究\n\n'+ppotext+'\n\n新actor为固定合法上下文的8维mean/logSTD及scalar value；一个commit计划对应一个RL决策和完整episode。scratch与教师初始化单列。使用tanh变换的精确密度、同generation rollout及原任务结果；没有旧checkpoint继续训练。训练内最好sample、冻结mean及独立状态结果分开。实际budget含mean评价和父前缀，不能把native积分当独立学习样本。')
 write('FAILURE_MECHANISM_ANALYSIS.md','# 失败机制\n\n已观察失败/不合格分支数：%d；原门原因计数：%s。所有失败raw/partial及native计账保留。\n\n接口吞自由度由实际reference/torque/Human响应检查；motion失败由原native指标定位。力下降但motion失败不能胜出。代理模型不闭合与PPO探索/credit问题属于不同路径，不能由负结果统称Learning无用或动作空间不足。详细支持证据见原attempt与 RESEARCH_DECISIONS.jsonl；未被干预识别的因果解释仍为假设。'%(len(failure),dict(failurecounts)))
 trade='NOT_RUN' if bestnew is None else '最佳新增modal方案 `%s`：JF %s，JM %s；相对H150降力 %s；JM变化 %s Nm·s；tracking %s；原motion门 %s。'%(bestnew['id'],val(bestnew),val(bestnew,'JM'),gain(bestnew,H),'NOT_RUN' if H is None else f"{bestnew['JM']-H['JM']:.6f}",bestnew.get('tracking'),bestnew['qualified'])
 write('MOTION_FORCE_MOMENT_TRADEOFF.md','# Force、moment与真实运动取舍\n\n'+trade+'\n\n原门容许范围内增加JM仍应明确报告，不称全面Pareto优势。原始native v/a/jerk、tracking、excursion、phase boundary、任务时长、接触/clearance/torque均在runtime/reports及audit/independent。未滤波的原motion门保持。')
 write('CROSS_STATE_RESULTS.md','# 独立合法状态\n\n'+cross+'\n\n未运行的登记prefix保持NOT_RUN；没有把同状态重复算作新状态，没有跨患者证据。')
 write('NEXT_RESEARCH_DECISION.md','# 下一步\n\n'+('优先围绕已观察的闭环时序/原motion边界，验证可部署运动余量预测能否在冻结候选排序中降低失败探索成本；沿用本轮最强合格固定参照、相同权限与原任务门。' if bestnew else '优先完成新增协调权限的真实执行与原motion余量诊断，再讨论学习器扩展。')+'\n\n少数重复患者适应：NOT_RUN，除非本包另有连续trial原始证据；当前多次仿真fork不能解释为患者两三次学习。')
 summary='''# iHEAR Lab — Autonomous Coordination & Learning Research v2

状态：%s。T0 `%s` UTC；硬截止 `%s` UTC；当前累计 %.4f h。终态与PID关闭以 END.json 为准。

真实物理START %d，闭合账本新增native %d；完整候选 %d，原门合格 %d；工程import-only失败另列，未冒充物理尝试。独立raw已重算 %s/%d。

同链参照：B JF %s，H150 %s，上一轮强固定 %s N·s。最佳新增modal方案 %s；相对B/H150/强固定降力分别为 %s / %s / %s。

%s

1. **实际多久和多少物理尝试？** 见本页计数、ACTIVATION、RESOURCE_AND_ATTEMPT_ACCOUNTING与END。原T0不重置，失败/partial计入。
2. **实现哪些表示？** A1同旧运动族换坐标；A2新增8个可解释路径/时长/通过速度模式。设计和实际权限分开。
3. **自由度真正执行？** 接口门：%s；实签参考contrast rank %s。完整身份及applied torque/Human响应见接口审计。
4. **找到新合格低负担运动？** %s
5. **相对B/H150/强固定怎样？** 见上述同链配对；独立prefix使用该状态自己的合格分母。
6. **改善来自哪里？** A1控制坐标效应，A2单模式干预和后续消融控制路径/时间/通过速度效应；未经消融的最优组合不作唯一因果归因。
7. **快速优化减少物理尝试？** 只比较相同累计attempt下达到同等合格JF所需次数；代理查询与历史工程成本单列，有限轨迹不作全局最优。
8. **Learning改变有价值决策？** 已记录有学习模型的预序结果%d条，其中%d条相对同池名义选择改变。额外真实收益须对等预算及冻结验证，不能由RMSE推断。
9. **PPO实质收益？** %s
10. **Q/Value或其它方法？** Q/Value NOT_RUN：当前高层每任务commit一次，没有先观察到必须用多步value解决的缺口；不重用旧公共state项相消的结构。
11. **已证实失败根因？** 原门失败计数%s；执行、预测、优化与学习失败分别查证据，不混为一个结论。
12. **哪些仍是假设？** 跨患者闭环模型、可部署motion sensing、有限最优是否接近物理上限、一般Learning额外价值与硬件实时均未建立。
13. **force伴随其它代价？** %s
14. **独立合法状态？** 已完成%d条冻结状态分支，详见 CROSS_STATE_RESULTS；不同prefix仍为同一名义Human。
15. **少数重复患者适应？** 没有连续trial原始证据时为NOT_RUN；多次fork搜索的历史不能缩写为患者两三次即学会。
16. **论文判断？** 本轮可贡献受约束执行表示、实际动作归属、等物理预算优化与失败机制证据；一般学习优势及少样本患者适应须有独立实证才升级。
17. **下一步具体问题？** 见 NEXT_RESEARCH_DECISION，优先闭环时序/原motion边界的可部署余量预测与候选筛选。
18. **长期日志？** 已追加开始记录；结束记录只在最终封包追加一次，证据见 audit/JOURNAL_END_RECORDING.json。

已观察事实以raw、原scorer和独立重算为准；有限机制解释注明支持范围；尚未验证的假设不当作结果。原物理/安全/scorer/任务合同与历史资产保护审计见 PACKAGE_VERIFICATION。没有Git commit/push/merge/reset/stash/clean，没有Stage2、最终Campaign或硬件实验。
'''%(status,A['T0_utc'],A['hard_stop_utc'],elapsed,len(starts),native_used(),sum(r['complete'] for r in rows),sum(r['qualified'] for r in rows),audit.get('audited',0),len(starts),val(B),val(H),val(S),bestnew['id'] if bestnew else 'NONE',gain(bestnew,B),gain(bestnew,H),gain(bestnew,S),table,gate.get('new_modes_executable','NOT_RUN'),gate.get('observed_issued_reference_contrast_rank','NOT_RUN'),trade,len(learn),lstats['learned_decision_changed'],ppotext,dict(failurecounts),trade,len(lockrows))
 write('REPORT.md',summary)
 put('REPORT_SUMMARY.json',dict(status=status,utc=utc(),elapsed_h=elapsed,physical_START=len(starts),native_steps_closed=native_used(),best_qualified=best,best_new_modal=bestnew,baseline_B=B,baseline_H150=H,strong_fixed=S,learning_summary=lstats,PPO_completed_studies=len(ppo),cross_state_branches=len(lockrows),failure_counts=dict(failurecounts)))
 import acl2_findings
 acl2_findings.main(status)
if __name__=='__main__':main()
