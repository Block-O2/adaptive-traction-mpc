"""Final evidence tables and concrete decisions. Never changes results or models."""
from pathlib import Path
import json,re,time
P=Path(__file__).resolve().parents[1]
def read(n,d=None):
 q=P/n;return json.loads(q.read_text()) if q.exists() else d
def fmt(x,n=6):return '—' if x is None else f'{x:.{n}f}'
def table(h,rows):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def append(n,s):
 with (P/n).open('a') as f:f.write('\n'+s.strip()+'\n')
def main():
 e=read('analysis/COMBINED_FROZEN_RESULTS.json');s=read('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json');rule=read('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json');phase=read('analysis/FIXED_PHASE_RULE_RESULTS.json');blend=read('analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json');diag=read('analysis/FROZEN_DECISION_DIAGNOSTICS.json');err=read('analysis/FROZEN_PREDICTION_ERROR_AUDIT.json');ranks=read('analysis/ACTUAL_ACTION_RANK_VARIATION.json');a=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');repro=read('analysis/CRITIC_PHYSICAL_REPRODUCTION.json')
 assert e['primary_states']==4 and len(e['legacy_rows']) in [2,3]
 halfgain=e['paired_summary']['B_HALF_SECOND']['mean_JF_improvement_N_s'];onegain=e['paired_summary']['C_ONE_SECOND']['mean_JF_improvement_N_s'];fixedgain=e['paired_summary']['FIXED_TRAINING_CHOICE']['mean_JF_improvement_N_s']
 primary=e['primary_rows'];legacy=e['legacy_rows'][0]
 for r in e['legacy_rows']:
  dd=read('data/'+r['group']+'.json',[])
  if any(not x['qualified'] for x in dd if x['horizon_s']==.5):legacy=r;break
  if r['group']=='LEGACY_BOUNDARY_O3':legacy=r
 lm=legacy['methods'];ld=lm['D_CRITIC'];lc=lm['C_ONE_SECOND'];lg=lm['GUARD_RULE_ONE'];le=lm['E_REAL_FULL_REFERENCE']
 challenge_has_failure=any(not x['qualified'] for x in read('data/'+legacy['group']+'.json') if x['horizon_s']==.5)
 alias_replay=(P/'audit/O3_PARENT_ALIAS_RECLASSIFICATION.json').exists() and legacy['group']=='LEGACY_BOUNDARY_O3'
 lt=(f"{'已封存的训练父状态重放' if alias_replay else '旧B后续局部挑战'}{legacy['group']}中，Critic选{ld['choice']}，完整原门{'PASS' if ld['qualified'] else '未完成' if ld['choice']=='ABSTAIN' else 'FAIL'}；"
     f"1秒选{lc['choice']}，原门{'PASS' if lc['qualified'] else 'FAIL'}，其H前已有native速度/加速度门失败={lc['native_peak_already_failed_by_H']}；"
     f"直接guard历史规则选{lg['choice']}，原门{'PASS' if lg['qualified'] else '未完成' if lg['choice']=='ABSTAIN' else 'FAIL'}。"
     f"离线完整合格参照为{le['choice']}。"+('O3与已暴露TAILOT实际父状态相同，已排除独立验证；两个真正新状态均无失败动作。故独立出程修复仍NOT_TESTED，不把训练重放的成功当泛化。' if alias_replay else '所有已执行新挑战都无失败动作，尚未触发出程motion修复检验，不能称已解决。' if not challenge_has_failure else '该局部新prefix避开运动失败，但强固定/guard规则是否相同必须一并比较，未证明一般修复。' if ld['qualified'] else '该新prefix未修复可完成原任务的出程决策，拒绝或低尾部成本均不算成功。'))
 confirmations=[r for r in rule['rows'] if r['group'] in ['RULE_T1','RULE_T2']]
 rt='传统单一RULE状态='+rule['status']+'。'
 if confirmations:
  jf=sum(r['RULE_JF_reduction_vs_COMPOSE'] for r in confirmations)/len(confirmations);jm=sum(r['RULE_JM_increase_vs_COMPOSE'] for r in confirmations)/len(confirmations)
  passed=sum(r['all_original_qualified'] and r['retention_90pct_pass'] for r in confirmations)
  rt+=f"{len(confirmations)}个冻结新prefix中{passed}个通过原门及90%三指标收益保留，相对COMPOSE平均少JF={fmt(jf)} N·s、JM变化={fmt(jm)} Nm·s。"
 else:rt+='未运行部分不制造结果；原因见ADAPTIVE_FIXED_RULE_RESULTS。'
 pt='固定阶段方案追加复核='+phase['status']+'。'
 if phase['rows']:
  pjf=sum(r['delta_JF_vs_COMPOSE'] for r in phase['rows'])/len(phase['rows']);pjm=sum(r['delta_JM_vs_COMPOSE'] for r in phase['rows'])/len(phase['rows']);pp=sum(r['predeclared_extra_quality_and_cost_bounds_pass'] for r in phase['rows'])
  pt+=f"{len(phase['rows'])}组配对中{pp}组通过原门及额外代价上限；相对COMPOSE平均ΔJF={fmt(pjf)} N·s、ΔJM={fmt(pjm)} Nm·s。"
 ib=[r for r in blend if r['role'].startswith('independent')];bg=sum(r['BLEND_JF_reduction_vs_COMPOSE'] for r in ib)/len(ib);bj=sum(r['BLEND_JM_increase_vs_COMPOSE'] for r in ib)/len(ib)
 moment_B_delta=[]
 for r in phase['rows']:
  anchor=next(q for q in read('data/'+r['reference_group']+'.json') if q['tag']=='B' and q['horizon_s']==.5)
  moment_B_delta.append(r['phase_rule_JM']-anchor['metrics']['full_JM'])
 p=P/'REPORT.md';body=p.read_text()
 changes={
  1:('CONFIRMED',f"研究至STOP经历{a['elapsed_wall_s']/3600:.3f}小时；含最终manifest/独立验证的准确总wall见END.json.actual_total_wall_seconds。真实MuJoCo START/END={a['physical_START']}/{a['physical_END']}，新增native={a['actual_new_native_steps']}步（{fmt(a['actual_new_simulation_seconds'],3)}模拟秒）；完整候选={a['candidate_complete_raw']}，冷启动父进程={a['cold_parent_episodes']}，其中{len(a['intentional_prefix_sampler_ids'])}个只采合法prefix。动力学仿真不是硬件或患者试验。"),
  3:('SUPPORTED',f"v5合法平顺性方案由原raw及匹配完整轨迹复现；新两组BLEND/C比较中通过原门={sum(r['COMPOSE_and_BLEND_original_qualified'] for r in blend if r['role'].startswith('independent'))}/2，但BEST作为整策略参照通过的组数={sum(r['all_three_original_qualified'] for r in blend if r['role'].startswith('independent'))}/2。不能把不合格BEST当成功强基线。"+pt),
  4:('CONFIRMED',"名义v5 COMPOSE的native力模长变化率RMS由强固定19.334070降到18.222197 N/s，约低5.75%；新BLEND和固定阶段方案相对COMPOSE均略回升，保持多数原收益而非每项同步下降。力向量、力矩变化率与峰值另列，未推断患者舒适度。"),
  5:('CONFIRMED',f"名义COMPOSE相对强固定为JF约+8.058633 N·s、JM约−1.904880 Nm·s。本轮BLEND相对COMPOSE平均JF−{fmt(bg)}、JM+{fmt(bj)}；"+pt+(f"但固定阶段方案相对原B平均JM仍+{fmt(sum(moment_B_delta)/len(moment_B_delta))} Nm·s，不能称对所有基线全面低负担。" if moment_B_delta else '所有完整JF/JM见原始配对表，不将单一积分下降称综合低负担。')),
  7:('CONFIRMED',f"四组主冻结新prefix中Critic原门通过{e['critic_qualified_states']}/4；相对1秒改变实际轨迹{sum(r['critic_changes_physical_execution_vs_one'] for r in primary)}/4，相对训练固定phase规则改变{e['critic_distinct_physical_choices_vs_training_fixed']}/4。HANDOFF/PATTERN标签别名不计物理改变。选中动作的同状态完整执行复现={repro['status']}，未被重称未见测试。"),
  8:('SUPPORTED',f"Critic相对1秒短窗在双方合格状态平均少JF={fmt(onegain)} N·s；相对训练冻结强phase规则平均少JF={fmt(fixedgain)} N·s。独立超过1秒且超过该固定规则>0.02 N·s的状态={e['meaningful_independent_increment_states']}。恢复长期排序已在真实完整tail观察，未建立强固定规则无法替代的增量价值。"),
  9:('SUPPORTED' if challenge_has_failure and not alias_replay else 'NOT_TESTED',lt),
 11:('SUPPORTED',rt+pt+"固定phase规则与事前库筛选提供直接价值；本轮新BO、ILC、PPO和Q网络均NOT_RUN，不宣称跨合同算法普遍优劣。"),
 12:('CONFIRMED',"确认B上游接平顺性后续可导致15个完整动作违反excursion；匹配COMPOSE上游恢复资格。还确认微扰配置未必改变实际父状态：O3已降格为TAILOT训练父状态重放、原独立声明封存。原失败峰值早于H，低尾部成本不能抵消；父状态别名CV、错误jerk max_abs标签和时钟微小scale等问题均有保留审计。"),
 14:('SUPPORTED',"新证据覆盖同一nominal Human的4个主冻结prefix、2个真正新的旧B出程状态、2个BLEND确认及筛选/固定阶段配对。O3与旧训练prefix实际相同，已剔除独立证据；不能把配置微扰、commissioning seed或训练父状态重放称新患者，自适应配对也不冒充未见模型选择测试。"),
 15:('SUPPORTED',"本轮暂停该成本Critic的扩张，保留冻结模型、raw与诊断代码。它能纠正短视排序，但未超过强固定阶段规则；风险头仍有跨父状态漏检，不足以替代原门。继续学习前先解决合法状态排序需求或原门的在线可观测性，不自动改名Q/PPO继续训练。"),
 17:('SUPPORTED',"下一轮最具体问题：以本轮通过的固定阶段平顺性方案为起点，保持原完整门和预先设定的髋/膝jerk及cuff力变化率保留要求，只对回程交接时间作小范围配对试验，检验能否继续同时降低JF/JM；若没有强phase规则解决不了的实际排序翻转，继续采用传统规则。精确native风险在线信息另作接口研究。"),
 18:('CONFIRMED',"根日志已核对v5完整开始/转折/结束且未重复；本轮开始、实际机制转折及实际结束均只追加。audit/JOURNAL_APPEND_ONLY_FINAL.json验证原20376字节前缀逐字节不变，保留可接受后续追加的封包snapshot。"),
 19:('CONFIRMED',"所有owned物理子进程、supervisor、编排与评分服务已结束；audit/OWNED_PROCESS_FINAL.json剩余活跃owned=0。END与PACKAGE_VERIFICATION封包、只读VERIFY_PACKAGE复核，终态STOP，不自动启动下一轮。")}
 for i,(tag,text) in changes.items():
  body,n=re.subn(r'^'+str(i)+r'\. \*\*[^\n]*',str(i)+'. **'+tag+'** — '+text,body,flags=re.M);assert n==1,(i,n)
 body+='\nCONFIRMED：O3身份审查先报告FAIL，随后按实际raw证据重分类，原失败审计保留为audit/O3_ACTUAL_PARENT_ALIAS_ORIGINAL_FINDING.json；修订后的独立性PASS只覆盖仍被声明独立的4+2状态。不能将PASS解释为O3的新状态资格。\n'
 body+='\n实际结果图：[平顺性](figures/01_SMOOTHNESS_RETAINED.png) · [冻结决策](figures/02_CRITIC_DECISION_VALUE.png) · [真实候选尝试](figures/03_PROSPECTIVE_ATTEMPTS.png) · [native时序](figures/04_NATIVE_WAVEFORMS.png)。同名PDF可独立导出。\n'
 p.write_text(body)
 decisionrows=[]
 for r in primary:
  for k in ['A_FIXED_SMOOTH','B_HALF_SECOND','C_ONE_SECOND','D_CRITIC','FIXED_TRAINING_CHOICE','E_REAL_FULL_REFERENCE']:
   m=r['methods'][k]
   if m['choice']=='ABSTAIN':decisionrows.append([r['group'],k,'ABSTAIN','无完整任务','—','—','—','—','—']);continue
   decisionrows.append([r['group'],k,m['choice'],'PASS' if m['qualified'] else 'FAIL',fmt(m['full_JF']),fmt(m['full_JM']),*[fmt(v,3) for v in m['full_jerk_RMS_deg_s3']],fmt(m['wrench']['force_norm_rate_RMS_N_s'],4)])
 append('SMOOTHNESS_CRITIC_COMBINED_RESULTS.md','CONFIRMED：完整task原始量逐方法并列（相同轨迹的多个方法共享一份物理结果，不重复收attempt）：\n\n'+table(['状态','方法','选择','原门','全JF','全JM','髋jerk RMS','膝jerk RMS','力模长变化率RMS'],decisionrows))
 append('CRITIC_DECISION_VALUE.md','NOT_TESTED：'+lt+'\n\nCONFIRMED：O3各方法行仅为已暴露训练父状态重放；原始独立声明已封存，不计新状态泛化。旧B部分A_FIXED_SMOOTH沿用公共schema，实际是训练固定旧B菜单动作，不是COMPOSE整策略基线。原B本身亦完整执行，不能用其他固定动作失败宣称Learning不可替代。\n\nCONFIRMED：主测试选中候选完整物理复现='+repro['status']+'；详情见analysis/CRITIC_PHYSICAL_REPRODUCTION.json。')
 append('CRITIC_MODEL_AUDIT.md','CONFIRMED：下表来自H时已落盘预测，绝对tail误差与相对排序分开；ensemble spread不是校准区间。主score_index3为菜单中心化tail JF，共同偏置不影响同菜单排序。\n\n'+table(['状态','tail JF RMSE N·s','tail JM RMSE Nm·s','剩余时长RMSE s','唯一合格pair数','Critic排序正确率'],[[r['group'],*[fmt(x) for x in r['absolute_RMSE']],r['unique_qualified_pairs'],fmt(r['pairwise_accuracy']['critic'],3)] for r in err['states']]))
 append('CRITIC_MODEL_AUDIT.md','CONFIRMED：上表O3属于已暴露训练父状态重放，仅作回归诊断；7个评价对象不是7个独立新状态。主4状态、旧B真正新状态2个、已封存重放1个严格分开。原始别名FAIL审计未删除。')
 rf=read('analysis/RISK_FAILURE_MECHANISMS.json')
 append('CRITIC_MODEL_AUDIT.md','CONFIRMED：整父状态族CV按阶段计数='+str(rf['cross_family_CV_by_phase'])+'。出程12个失败窗口全部漏检，HOLD6个全部漏检，18个TP全部在RETURN；这些是相关窗口。最终模型对已包含训练样本仍漏掉8个接近excursion边界的窗口，不把训练误差当验证。\n\nHYPOTHESIS：阶段/父状态覆盖、summary压缩及logistic线性/正则化可能共同限制风险头；最近异标签summary并不证明完整因果历史不可辨识。见analysis/RISK_FAILURE_MECHANISMS.json。')
 append('CRITIC_STATE_AND_LABEL_AUDIT.md','CONFIRMED：风险训练161条旧轨迹的936376个execution事件完成时间核验通过，未发现缺end字段；未来信号、未来/尚未结束事件和未来结果字段扰动均不改变当前特征或选择。原失败flag吸收性测试通过。见audit/CAUSAL_EVENT_AVAILABILITY_AND_TRUNCATION.json。这验证数据流，没有证明状态充分性或完整在线资格。\n\nCONFIRMED：时钟±15ms物理选择变化状态数='+str(sum(r['selection_changed_by_15ms'] for r in diag['states']))+'；标签变化数='+str(sum(r['selection_label_changed_by_15ms'] for r in diag['states']))+'。OUTBOUND的HANDOFF/PATTERN会在浮点相等分数下互换，但实际执行一致；未改模型或平局规则。')
 append('CRITIC_STATE_AND_LABEL_AUDIT.md','CONFIRMED：O3配置第三prefix系数微扰没有改变实际pre-fork历史，匹配已训练TAILOT及TAILRESCUE父状态。已停止其独立证据分支并重分类训练父状态重放，原始FAIL审计与完整raw均封存；无重训、无删除、未把相同状态改称未见。主4状态与额外2个真正新状态仍独立于训练。派发前应先比较实际因果prefix指纹，再声明新状态。')
 append('SHORT_HORIZON_VS_FULL_TAIL.md','CONFIRMED：开发表中的DEV_O1为整策略承诺，其余TRAIN/COORD为当前一次后接共同COMPOSE，不能把两种尾部标签混合训练。原B上游RETURN没有合格主菜单时E为空。\n\n'+table(['冻结状态','0.5s','1s','Critic','完整合格参照','Critic相对1s少JF'],[[r['group'],r['methods']['B_HALF_SECOND']['choice'],r['methods']['C_ONE_SECOND']['choice'],r['methods']['D_CRITIC']['choice'],r['methods']['E_REAL_FULL_REFERENCE']['choice'],fmt(r['critic_JF_improvement_vs']['C_ONE_SECOND'])] for r in primary]))
 rr=[[r['group'],str(r['all_original_qualified']),str(r['retention_90pct_pass']),'/'.join(fmt(x,4) for x in r['retention_hip_knee_force_rate']),fmt(r['RULE_JF_reduction_vs_COMPOSE']),fmt(r['RULE_JM_increase_vs_COMPOSE']),fmt(r['RULE_JF_reduction_vs_BLEND']),fmt(r['RULE_JM_increase_vs_BLEND'])] for r in rule['rows']]
 ruletext='SUPPORTED：'+rt+'\n\n'+table(['状态','原门','90%保留','髋/膝/力变化率收益保留','RULE少JF vsCOMPOSE','RULE多JM vsCOMPOSE','RULE少JF vsBLEND','RULE多JM vsBLEND'],rr)+'\nCONFIRMED：配对复用在任何SMOOTH_A1/A2结果揭示前登记，要求新完整B身份锚与既有raw/native/receipt精确匹配；原初未执行RULE配置保留source/versions，不冒充结果。计划由15降到9个START为边界留预算，但若RULE未触发，这6次只是预算减少，绝不计实际节省。动作与90%标准未因测试调整。实际筛选省略7个唯一候选另算，不归因于Critic。'
 for n in ['SMOOTHNESS_BASELINE_COMPARISON.md','OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md','MOTION_FORCE_MOMENT_TRADEOFF.md']:append(n,ruletext)
 phasetext='SUPPORTED：'+pt+'\n\n'+table(['配对状态','原门','全JF','全JM','ΔJF vsCOMPOSE','ΔJM vsCOMPOSE','髋/膝jerk与力变化率比值','额外界通过'],[[r['group'],str(r['original_qualified']),fmt(r['phase_rule_JF']),fmt(r['phase_rule_JM']),fmt(r['delta_JF_vs_COMPOSE']),fmt(r['delta_JM_vs_COMPOSE']),'/'.join(fmt(x,6) for x in r['hip_knee_jerk_force_rate_ratio_vs_COMPOSE']),str(r['predeclared_extra_quality_and_cost_bounds_pass'])] for r in phase['rows']])+'\nCONFIRMED：此为固定OUT1 HANDOFF后共同COMPOSE，不是整段HANDOFF。原任务/门完全相同，额外冻结研究界为髋/膝jerk≤COMPOSE1.001倍、力模长变化率≤1.004倍且JF/JM同时不增。主测试效果已知、参照状态部分暴露，故只称自适应配对复核；不是独立模型选择或新的未见Critic状态。scope澄清见audit/FIXED_PHASE_BOUND_REGISTRATION_SCOPE.json。'
 for n in ['SMOOTHNESS_BASELINE_COMPARISON.md','OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md','MOTION_FORCE_MOMENT_TRADEOFF.md']:append(n,phasetext)
 append('MOTION_FORCE_MOMENT_TRADEOFF.md','CONFIRMED：逐阶段原左积分满足delta J=(T_new−T_ref)*mean_ref+T_new*(mean_new−mean_ref)，闭合误差<1e-8。实际差异主要是平均力/力矩变化，并不是延长或缩短原任务换积分。见analysis/FORCE_MOMENT_DOSE_DECOMPOSITION.json；该式是代数分解，不是机制独占或因果中介证明。\n\n'+table(['状态','D相对COMPOSE ΔJF','ΔJM','髋/膝jerk和力变化率Δ%'],[[r['group'],fmt(r['critic_minus_fixed_JF']),fmt(r['critic_minus_fixed_JM']),'/'.join(fmt(x,4) for x in r['critic_vs_fixed_hip_knee_jerk_force_rate_percent'])] for r in diag['motion_force_tradeoffs']]))
 append('OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md','CONFIRMED：各已测试phase/upstream域内完整合格菜单的排序是否反转：'+str([(r['domain'],r['actual_within_phase_upstream_order_variation']) for r in ranks['domains']])+'。阶段已知即可采用不同固定动作；没有以更复杂学习器解释已被phase规则覆盖的变化。模型纯拟合开销很小不等于标签免费，训练/确认/审计attempt全部计入本轮。')
 (P/'NEXT_RESEARCH_DECISION.md').write_text('# 下一研究决策\n\nSUPPORTED：暂停扩张当前cost Critic；保留其冻结诊断价值。'+rt+pt+'\n\nSUPPORTED：先在派发前核验实际因果prefix/参考/执行历史指纹，排除未生效配置微扰冒充新状态。再以通过的固定阶段方案为起点，保持原门和平顺性保留约束，仅对回程交接时间做有限配对，检验能否同时继续降低JF/JM。只有出现强phase规则无法覆盖的合法排序翻转，才重新讨论状态学习。\n\nSUPPORTED：风险方向需要原native门的合法在线信息及多个独立出程失败父状态。O3训练重放不作新失败验证，跨父状态漏检仍多；不换Q/PPO名称继续堆样本。\n\nNOT_TESTED：患者级泛化、其他commissioned Human、硬件、临床舒适度、长程PPO、Stage2及最终Campaign。当前STOP，不自动启动下一轮。\n')
 print('FINAL_REPORT_SUPPLEMENT','19 answers concrete','rule',rule['status'],flush=True)
if __name__=='__main__':main()
