from common import *
def main():
 ranking=load(OUT/'RANKING_FEASIBILITY.json');ord=ranking['ordinary_pool_summary'];hist=load(OUT/'HISTORICAL_ROLLING_CONTINUATION_AUDIT.json')
 ordinarytext=f'''## 当前ordinary池与历史G-head扩展必须分开

原80行cohort包含 **74条ordinary K3候选＋6条历史离线G-head候选**。后者是原诊断留下的K3表标签，本轮没有生成G计划或训练G/P。当前Frozen M2 ordinary池的13snapshot全部 **fixed selection regret=0**，均值/最大均0，mean zero−best={ord['mean_zero_minus_best_N_s']:.6f}N·s。包含G扩展后的0.249333均值、1.620668历史test均值和3.241335最大值均保留，但唯一新增机会来自OUTBOUND的historical G_head_0（candidate6），属于候选覆盖扩展；不能将它说成相同ordinary池已经存在需state-conditioned排序才能获得的收益。

相同计划/mask/carry的三个共同池没有包含G-head，均保持fixed最优。完整motion筛查的结果对ordinary与G联合池都只剩13条zero；普通池是74→13、完整历史cohort是80→13。先前表格统一使用80行历史cohort，不能混淆分母。

来源独立性进一步受限：三个注册父轨迹为初始OUTBOUND slot零、+0.12、−0.12三种prefix；第四个来源是已暴露nominal M2的精确动作replay。所有80条model_hash与model_beta各只有 **1种**，所以没有跨model estimate排序证据。公共context round4有12种并非12独立人体；RETURN近乎相同的成本亦不能放大覆盖。
'''
 gaprows=[[r['phase'],r['issued_index'],f"{r['commit_remaining_N_s']:.6f}",f"{r['archived_rolling_remaining_N_s']:.6f}",f"{r['commit_minus_archived_rolling_N_s']:.6f}"] for r in hist['results']]
 gaptext=f'''## 已存在的scientific rolling诊断：有限数值差可测

{table(['phase','issued index','commit remaining N·s','archived rolling remaining N·s','commit−rolling N·s'],gaprows)}

来自原DIAGNOSTIC_ANALYSIS_v1和060_v1...REPLAY_GATE；本轮重新核验原initial applied table与selected branch表完全相同、remaining=原终值−同prefix integral，原replay gate记录所有trace字段精确相等和causal context相等。OUTBOUND固定后缀高20.646403N·s，RETURN为0，已支持continuation差别不能忽略。全部为 **SCIENTIFIC_SIMULATION** 的已暴露历史诊断，不是本轮新增实验。

这个gate未证明replay接口/对象、完整RNG、lifecycle及host时钟等与原rolling进程的完整可执行state相同；它证明物理trace和可见causal context匹配。每个state只存在原selected action的一个rolling结果，没有其他candidate的rolling反事实，因此不能计算V_replan候选排序或用20.646403作为host偏差界。真实host同完整状态下的价值差仍NOT_EVALUABLE。本包没有重新运行replay；hash和重新计算在HISTORICAL_ROLLING_CONTINUATION_AUDIT.json。
'''
 p=OUT/'RANKING_FEASIBILITY.md';text=p.read_text();text=text.replace('## 同状态有限候选结果',ordinarytext+'\n## 同状态有限候选结果',1);text=text.replace('仅在该小型有限池中额外state oracle相对fixed的均值机会','在含历史G扩展的该有限池中best相对fixed的均值差');md(p.name,text)
 p=OUT/'REPORT.md';text=p.read_text();text=text.replace('完整候选池里仅一snapshot有3.241335N·s固定排序损失','含历史G-head扩展的cohort池里仅一snapshot有3.241335N·s固定排序损失；ordinary池13state损失均0');text=text.replace('同state数值差/排序差不可测。没有可靠','真实host同完整state数值差/排序差不可测；旧scientific rolling诊断的两处差值20.646403/0N·s已核验，见下节。没有可靠');text=text.replace('## 运动剂量与排序',ordinarytext+'\n'+gaptext+'\n## 运动剂量与排序',1);text=text.replace('3. 固定排序损失：全13state均值','3. 固定排序损失：当前ordinary池13state均为0；含历史G-head扩展的80行cohort中全13state均值');text=text.replace('4. 状态条件化额外可获收益：有限全池回顾上界等于上述regret','4. 状态条件化额外可获收益：ordinary池没有观测到；历史G扩展池的唯一3.241335机会首先属于candidate coverage，有限全池回顾差值等于上述regret');text=text.replace('7. Commit/replan合同一致性：**未成立且不能默认相同**；','7. Commit/replan合同一致性：**未成立且不能默认相同**；历史SCI滚动诊断OUTBOUND高20.646403、RETURN相同，真实host差值NOT_EVALUABLE；');text=text.replace('build_reports.py、verify.py','enrich_analysis.py、build_reports.py、refine_reports.py、verify.py');text=text.replace('无科学参数修复，积分重算边界口径澄清保留初诊。','无科学参数修复，积分重算边界口径澄清保留初诊；初次机械校验的phase-count猜测错误（55/25，实际54/26）已按冻结原DATA核对修正，原FAIL及日志保留于derived_history，不改变样本或阈值。');md(p.name,text)
 p=OUT/'COMMITTED_VS_REPLANNING_VALUE.md';text=p.read_text();text=text.replace('**合同不同；同状态数值差及排序差 NOT_EVALUABLE。**','**合同不同；真实host同完整state价值/排序差 NOT_EVALUABLE，历史SCI rolling诊断有有限数值差。**');text=text.replace('0个可恢复父状态、0个同state V_replan配对','当前0个可恢复父状态、0个同完整host state V_replan配对');text=text.replace('下一代Q首先应保持',gaptext+'\n下一代Q首先应保持',1);md(p.name,text)
 value=load(OUT/'COMMITTED_VS_REPLANNING_VALUE.json');value['historical_scientific_rolling_diagnostic']=hist;value['V_replan']['same_full_restorable_host_state_paired_labels']=value['V_replan'].pop('same_state_paired_labels');value['equivalence']='Not established. Existing exact-physical/causal-replay scientific diagnostic has commit-minus-archived-rolling gaps20.646403/0 N s; full executable-state identity and candidate-wise host comparisons are absent.';save('COMMITTED_VS_REPLANNING_VALUE.json',value)
 m=load(OUT/'COUNTERFACTUAL_DATASET_MANIFEST.json');m['ordinary_vs_G_head']=dict(ordinary_rows=74,historical_offline_G_head_rows=6,ordinary_pool_regret_mean_N_s=0.,new_G_P_calls=0);m['model_estimate_diversity']=ranking['independence_audit'];save('COUNTERFACTUAL_DATASET_MANIFEST.json',m)
 md('DATASET_FIELDS.md',(OUT/'DATASET_FIELDS.md').read_text()+'\n候选池范围：74条ordinary、6条原offline G-head诊断标签。candidate_pool_class标明来源；当前ordinary池损失0，联合池最大3.241335来自G-head覆盖，不等同于state preference学习机会。所有model_hash/beta各1种，不能称跨estimate覆盖。\n')
 print('FINAL_SCOPE_AND_VALUE_REPORTS_REFINED',flush=True)
if __name__=='__main__':main()
