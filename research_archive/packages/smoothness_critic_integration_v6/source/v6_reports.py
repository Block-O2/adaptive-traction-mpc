from pathlib import Path
import json,datetime,time,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(n,d=None):
 f=P/n;return json.loads(f.read_text()) if f.exists() else d
def write(n,s):(P/n).write_text(s.strip()+'\n')
def f(x,n=6):return '—' if x is None else f'{x:.{n}f}'
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n'
def data(g):return {r['tag']:r for r in read('data/'+g+'.json',[]) if r['horizon_s']==.5}
a=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',{});e=read('analysis/COMBINED_FROZEN_RESULTS.json',{});blend=read('analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json',[]);screen=read('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json',{});risk=read('models/WHOLE_HISTORY_RISK_V5_FROZEN.json',{});rule=read('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json',{});act=read('ACTIVATION.json');verify=read('PACKAGE_VERIFICATION.json',{});end=read('END.json',{});state='最终' if end.get('state')=='STOP' else '进行中，不能将未运行项目视作完成';elapsed=end.get('elapsed_seconds',a.get('elapsed_wall_s',time.time()-act['T0_unix']));primary=e.get('primary_rows',[]);legacy=e.get('legacy_rows',[])
base=read('audit/BASELINE_RAW_RECOMPUTE.json',{}).get('rows',[])
rows=[[r['id'],'PASS' if r['original_qualified'] else 'FAIL',f(r['JF']),f(r['JM']),'/'.join(f(x,3) for x in r['jerk_RMS_deg_s3']),f(r['force_norm_rate_RMS_N_s'],4)] for r in base]
s='# 平顺性强基线与有限插值\n\nCONFIRMED：v5 manifest 7266文件逐项一致；下表从实际 trace/native qvel/cache wrench 独立重算，未重做历史搜索。原积分与native未滤波motion保持。\n\n'+table(['v5身份','原门','JF N·s','JM Nm·s','jerk RMS髋/膝 °/s³','4kHz力模长变化率 N/s'],rows)
s+='\nCONFIRMED：同一合法VAL03前缀已用于开发，不称未见。TRAIN_O2_B、TRAIN_O2_COMPOSE与v5对应轨迹的全部原trace、native状态/torque/contact及scientific receipt字段逐项相同，见 audit/V5_MATCHED_RAW_REPRODUCTION.json。\n'
for g in ['DEV_O1','SMOOTH_A1','SMOOTH_A2']:
 r=data(g)
 if not r:continue
 s+='\n'+g+'（'+('开发' if g=='DEV_O1' else '冻结新前缀确认')+'）\n\n'+table(['方案','原门','JF','JM','髋jerk RMS','膝jerk RMS','4kHz力变化率'],[[t,'PASS' if x['qualified'] else 'FAIL',f(x['metrics']['full_JF']),f(x['metrics']['full_JM']),*[f(v,3) for v in x['metrics']['full_jerk_RMS_deg_s3']],f(x['metrics']['wrench']['force_norm_rate_RMS_N_s'],4)] for t,x in r.items()])
s+='\nSUPPORTED：BLEND仅在已合法PATTERN/COMPOSE的局部时间坐标间插值，未扩展权限。以冻结的90%保留比例检验其JF收益；未因测试结果改阈值或重新选参数。\n\n'+table(['状态','BLEND少JF N·s','BLEND多JM Nm·s','髋/膝/力变化率收益保留比例','原门+90%保留'],[[r['group'],f(r['BLEND_JF_reduction_vs_COMPOSE']),f(r['BLEND_JM_increase_vs_COMPOSE']),'/'.join(f(v,4) for v in r['retained_fraction_of_COMPOSE_improvement_hip_knee_force_rate']),str(r['all_three_original_qualified'] and r['retention_90pct_pass'])] for r in blend]);write('SMOOTHNESS_BASELINE_COMPARISON.md',s)
write('WRENCH_FLUCTUATION_ANALYSIS.md', '''# cuff施力波动

CONFIRMED：原JF/JM采用5ms TASK左积分。4kHz记录只复制原native post-refresh已经计算的实际接口wrench；不增加observe/refresh/step。v5原raw重算与同前缀物理身份对照通过。v6各完整菜单的native wrench与原5ms重合点逐分量误差在data/*.json记录并断言小于1e-8 N。

SUPPORTED：各固定方案的力模长变化率、力向量变化率、力矩模长变化率、力峰值和RMS分别报告，见data/*.json及SMOOTHNESS_BASELINE_COMPARISON.md。少jerk或低变化率不等于低平均力或患者舒适度；JF、JM和原motion资格独立保留。

NOT_TESTED：真实传感器4kHz测量、连续sub-step重建、硬件舒适度或临床获益。
''')
wr=[]
for g in ['DEV_O1','SMOOTH_A1','SMOOTH_A2','RULE_DEV','RULE_T1','RULE_T2','PHASE_RULE_S1','PHASE_RULE_S2']:
 for tag,r in data(g).items():
  w=r['metrics'].get('wrench',{})
  if not w:continue
  wr.append([g,tag,f(w['force_RMS_N'],4),f(w['force_peak_N'],4),f(w['force_norm_rate_RMS_N_s'],4),f(w['force_vector_rate_RMS_N_s'],4),f(w['moment_norm_rate_RMS_Nm_s'],4)])
with (P/'WRENCH_FLUCTUATION_ANALYSIS.md').open('a') as out:
 out.write('\nCONFIRMED：以下变化率沿用v5原np.gradient(native time, edge_order=2)，保留端点；最初临时相邻差分版本已封存，最终比较没有换导数定义。\n\n'+table(['状态','方案','力RMS N','力峰值 N','力模长变化率RMS N/s','力向量变化率RMS N/s','力矩模长变化率RMS Nm/s'],wr))
model=read('models/COMMON_COMPOSE_FROZEN.json',{});dist=read('analysis/V6_TRAIN_FEATURE_DISTRIBUTIONS.json',[]);clock=[]
for d in dist:
 for x in d['features']:
  if any(n in x['name'] for n in ['task_elapsed_s','phase_elapsed_s','contract_time_remaining']):clock.append([d['phase'],x['name'],f(x['min'],4),f(x['max'],4),f(x['scale'],4)])
write('CRITIC_MODEL_AUDIT.md', '''# Critic模型审计

CONFIRMED：旧模型未覆盖。原B后续Critic修订模型见models/LEGACY_B_REVISED_V5_FROZEN.json；平顺性后续模型见models/COMMON_COMPOSE_FROZEN.json。后者不使用旧B尾部成本标签。主回归保留时间/阶段/remaining budget、当前估计、参考、scheduler/governor、接口与执行记忆，以及新增因果累计历史。contract_time_remaining为原run_executed_case的30秒task timeout减去已用TASK时间，并非提前获知实际终点；真实remaining duration仅为结果标签。

CONFIRMED：每个整父状态交叉验证训练折内独立拟合center/scale。标准化尺度取训练std与按量纲设置下限的较大者；时钟下限0.5s，未删除全部时间信息。v5约15ms变化在0.001缩放下形成异常距离；旧分布逐字段见analysis/V5_FEATURE_DISTRIBUTIONS.json，新分布见analysis/V6_TRAIN_FEATURE_DISTRIBUTIONS.json。

'''+table(['阶段','时间字段','train min','train max','冻结scale'],clock)+'''
CONFIRMED：小型三lengthscale RBF ensemble分别输出绝对tail分量和菜单中心化tail分量。score类型只按整父状态留一验证选择，未使用新测试结果。成本与完整资格风险头分开；主策略训练若没有失败类，则明确不拟合该风险头。观测到的原门失败标记为吸收性条件，不能以低尾部成本清除；但精确native原motion在线监视器尚未暴露，不能将evaluation-only真值用作在线flag。

CONFIRMED：最初五个历史峰值失败都属于同一个TAILOT状态族，TAILRESCUE是同父重放。初版按job名划分的5/5交叉验证已废止；正确留出该父状态后，原小数据训练折没有失败正例。随后仅用v5已公开raw扩充完整过去历史窗口，形成1281个相关窗口、12个实际父状态族，其中3族含失败。operative风险头为WHOLE_HISTORY_RISK_V5_FROZEN，24个observer/wrench/time/phase及已完成guard/refusal/fallback历史字段。不同后续策略只可共享“截至H已发生风险”标签，不共享cost-to-go标签。

CONFIRMED：误把jerk max_abs当作原门的临时V3标签已经封存，未进入测试；原门对jerk使用rms/p95，没有jerk max_abs门。修正后逐窗口断言：完整原合格轨迹不得标作已经不可逆失败。见audit/INVALID_RISK_V3_LABELS.json。最终整父状态族留出CV仍有漏检和误拒，不能把模型分数当原完整门。CV明细与计算开销见WHOLE_HISTORY_RISK_V5_FROZEN；12族经实际执行prefix指纹再次核验，没有仅按job名制造独立样本。

CONFIRMED：LEGACY_B_REVISED_V5中的描述字段risk_positive_independent_state_families仍保留初版的1，实际嵌入风险权重与WHOLE_HISTORY_RISK_V5完全一致，覆盖3个失败族/12族；单独澄清见audit/FROZEN_LEGACY_RISK_METADATA_CLARIFICATION.json，未改冻结文件。v6_model.py保留的旧select辅助函数未用于实际冻结选择；operative入口为v6_selection.select，无支持候选时ABSTAIN。

SUPPORTED：OOD阈值来自训练父状态留一距离并设定界限；不确定/被筛候选按冻结规则回退。ensemble差异与logistic分数都不是校准置信区间或安全证书。数值拟合/推理开销见RESOURCE_AND_ATTEMPT_ACCOUNTING.json，初次import/I/O与纯数值推理分开说明。

CONFIRMED：实际准入为全特征RMS标准化最近距离不超过冻结阈值、已发生风险分数<0.5、可用的完整资格风险分数<0.5；全部不支持时ABSTAIN。ensemble std仅报告，没有校准拒绝阈值；没有失败类而未拟合的资格头返回None，不是“已证明安全”。全局距离可掩盖单字段外推，独立OOD拒绝可靠性NOT_TESTED。当前完整资格仍由原raw门评价，不能以此门后审计冒充事前安全证书。

NOT_TESTED：可部署的廉价H状态预测、完整原motion资格概率校准、硬件实时资格或一般患者域外可靠性。
''')
cv=risk.get('cross_validation',[])
conf=dict(TP=sum(r['failed'] and r['rejected'] for r in cv),FN=sum(r['failed'] and not r['rejected'] for r in cv),FP=sum(not r['failed'] and r['rejected'] for r in cv),TN=sum(not r['failed'] and not r['rejected'] for r in cv))
with (P/'CRITIC_MODEL_AUDIT.md').open('a') as out:
 out.write('\nCONFIRMED：冻结V5风险头整父状态族CV窗口混淆计数：'+str(conf)+'。同轨迹多窗口相关，这不是1281个独立验证样本；失败窗口漏检不能由较高总体正确率掩盖。\n')
 out.write('\nCONFIRMED：成本累计历史消融只删除history_前缀输入，保留upstream上下文与两个风险头。不能称为完整历史消融或将差异归因于某单个历史量。各折与各未见状态动作记录在主freeze和evaluation中。\n')
 out.write('\n'+table(['阶段','总字段','恒定字段','std低于量纲floor字段'],[[d['phase'],len(d['features']),sum(x['constant'] for x in d['features']),sum(x['std']<x['floor'] for x in d['features'])] for d in dist]))
write('CRITIC_STATE_AND_LABEL_AUDIT.md', '''# 因果状态与标签

CONFIRMED：输入读取当前observer q/dq、已签参考及其导数、当前测量cuff wrench、phase/task elapsed、active suffix、governor、belief、previous executed delta、当前已施加robot torque和pending request。新增历史来自既有5ms boundary的measured wrench左积分、observer反向差分峰值、q范围、原guard修正/约束未满足计数和context拒绝。反向差分只使用截至H的数据，不把native evaluation-only Human或未来receipt喂给模型。

CONFIRMED：observer历史峰值与原native评分不等价。原gate的native峰值、最终PASS/FAIL、完整JF/JM只作为结果标签。已知原合同失败的吸收性接口已验证，但运行接口缺少精确在线原motion monitor。风险头使用截至H已完成execution_attempts的guard状态、拒绝写入与safe_fallback_events；未完成未来receipt不进入输入。COORD_R2六个开发分支的24项线上值与raw重建值全部相同，见audit/LIVE_WHOLE_HISTORY_FEATURE_REPLAY.json；后续独立状态同样逐条重放。完整状态充分性NOT_TESTED，风险头不是资格保证。

CONFIRMED：三种后续语义分库保存：DEV/SMOOTH整段承诺冻结方案；TRAIN/TEST当前一个候选决策后全部恢复共同COMPOSE；LEGACY_NEW_O当前一次后恢复原B rolling。严格不同成本标签不混合。候选只使用原modal8_retimed与legacy合法box，H150 timing/posture语义、原task/HOLD/端点及原guard保持。

CONFIRMED：TRAIN_R1–R3的B上游接COMPOSE后续导致15个完整候选都被原excursion门拒绝，已保留而未降低门槛。COORD_R1–R3改为先真实执行COMPOSE上游再到RETURN1决策；B资格锚从OUT1独立fork并完整执行。匹配上游后整段COMPOSE与DEV_O1逐字段完全一致，见audit/COORDINATED_UPSTREAM_FULL_RAW_IDENTITY.json。两类状态用因果upstream字段区分，旧失败仍进入资格风险训练。COORD/同类回程的父进程是付费合法prefix采样器，子分支均完整评价；父prefix的partial成本不排名，也不冒充完整成功。

CONFIRMED：每个新test在模型、特征、菜单、后续策略、选择规则和合同冻结后才START；在H=0.5时当场写入predictions/*_H05.json并断言完整summary尚不存在。离线重算只按因果白名单回放，逐项核对预测早于分支END。没有测试后重训再称未见。

NOT_TESTED：独立患者级泛化；全部实验为同一nominal Human不同合法prefix。多个horizon及同父动作不是独立患者或独立统计样本。
''')
short=read('analysis/TRAINING_DECISION_GAP.json',[])
write('SHORT_HORIZON_VS_FULL_TAIL.md', '# 短期与完整剩余任务\n\nCONFIRMED：候选完整真实续跑提供E离线参照；E不是可部署方法或全局最优oracle。原5ms左积分逐条闭合short+tail=remaining，原门失败不按低积分成功排序。\n\n'+table(['状态','0.5s选择','1s选择','完整合格选择','0.5s regret N·s'],[[r['group'],r['half'],r['one'],r['full_qualified'],f(r['half_regret_N_s'])] for r in short])+'\nSUPPORTED：出程HANDOFF/PATTERN的当前有效坐标相同，未来又恢复共同COMPOSE，实际轨迹相同；标签变化不等于真实动作或收益变化。当前菜单的短视不自动证明Learning必要，必须比较训练时冻结的透明固定动作/阶段规则。\n')
rows=[]
for r in primary+legacy:
 for name,m in r['methods'].items():
  if name.startswith('CRITIC_COST') or name.startswith('A_FIXED_') and name!='A_FIXED_SMOOTH':continue
  rows.append([r['group'],name,m['choice'],'PASS' if m['qualified'] else 'ABSTAIN' if m['choice']=='ABSTAIN' else 'FAIL',f(m['full_remaining_JF']),f(m['full_remaining_JM']),f(m['full_JF']),f(m['full_JM'])])
write('CRITIC_DECISION_VALUE.md', '# 冻结Critic决策价值\n\n'+state+'。CONFIRMED：选择函数不读取未来qualification mask。D以实测0.5s成本加冻结tail预测并经因果风险/OOD规则选择；固定COMPOSE、其他固定平顺性候选、训练时固定动作和1秒窗口都保留。每个候选已完成真实物理，故这部分物理节省=0。\n\n'+table(['状态','方法','候选','原门','剩余JF','剩余JM','全JF','全JM'],rows)+'\n'+table(['对照','双方原合格对数','Critic平均少JF N·s'],[[k,v['qualified_pairs'],f(v['mean_JF_improvement_N_s'])] for k,v in e.get('paired_summary',{}).items()])+f"\nCONFIRMED：主测试状态数={e.get('primary_states',0)}；Critic通过={e.get('critic_qualified_states',0)}；相对训练固定规则真实物理选择改变={e.get('critic_distinct_physical_choices_vs_training_fixed',0)}；同时超过1秒与训练固定规则且差值>0.02 N·s的状态={e.get('meaningful_independent_increment_states',[])}。该阈值为研究决策门，不是临床意义阈值。\n\nSUPPORTED：无独立增量时停止扩张该成本模型，不自动换Q/PPO名称继续训练。新测试结果不会反向进入主权重。预测误差、风险分数、OOD和H现场预测重放详见analysis/evaluation/*.json。\n")
write('SMOOTHNESS_CRITIC_COMBINED_RESULTS.md', '''# 平顺性与Critic合并结果

CONFIRMED：主比较所有方法使用同一四候选菜单HANDOFF/PATTERN/COMPOSE/BLEND、同一合法父状态、当前一次干预后共同COMPOSE。A固定COMPOSE保留高平顺性基线；其他固定候选和按训练冻结的phase规则也公开。B为0.5秒，C为1秒，D为修订Critic，E为真实完整续跑离线参照。BEST单次动作仅为辅助探针，不能冒充整段强固定BEST。

SUPPORTED：若D降低JF但与更简单的固定动作相同，不能称独立Learning收益；若牺牲jerk/wrench、JM或motion资格，须保留取舍。全任务与剩余任务JF/JM、native jerk、wrench各量逐状态记录在data/*.json和analysis/evaluation/*.json，配对收益只在双方完整原合格时计算。失败状态独立列出，不通过换分母隐藏。

CONFIRMED：本主比较是冻结反事实菜单审计。每个候选在实际H写入预测，为取得E参照仍继续全部tail；不同候选的H与完整结束交错，整菜单选择记录在末尾按冻结函数汇总。该函数不读未来结果，但不能称已实现少尝试的闭环在线Critic部署。另行完整执行复现用于核实选中动作的真实收益；不是新的未见状态。

CONFIRMED：整策略BLEND检验与一次决策Critic检验分开。前者用固定90%平顺性收益保留要求检验JF代价，后者检验状态决策价值，不能相互替代。
''')
srows=[[r['group'],r['choice'],str(r['qualified']),r['actual_unique_candidate_full_runs'],r['exhaustive_unique_reference_candidate_runs'],','.join(r['omitted_unique_candidate_identities']) or '无',str(r['ood_fallback']),f(r['audit_regret_N_s'])] for r in screen.get('rows',[])]
write('OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md', '# 优化与实际尝试效率\n\nCONFIRMED：本轮没有重新开展广域pattern/BO搜索。只生成一个有明确假设的PATTERN/COMPOSE插值BLEND，独立确认其force–moment–smoothness取舍。新BO/ILC/PPO训练均NOT_RUN，不能沿用v5固定12次比较来宣称本轮优化效率普遍领先。\n\nCONFIRMED：Critic需要各候选真实H状态；它的完整菜单实验全部执行，因此Critic实际尝试节省为0。下面的事前筛选是透明传统phase动作库规则，只用候选执行前的合法状态与冻结开发统计，不使用执行后的H状态。出程无效坐标别名在枚举参照中也被去除，未削弱基线。\n\n'+table(['状态','事前选择','原门','实际候选完整续跑','去重枚举数','未执行唯一候选','OOD回退','独立全菜单审计regret'],srows)+f"\nCONFIRMED：实际未执行的唯一候选续跑数={screen.get('prospectively_omitted_unique_complete_candidate_runs',0)}。这是相对预登记去重枚举协议的前瞻遗漏计数，不是整个研究campaign已获得净物理节省，也不归因于Critic。全部训练、cold parent、B资格锚、开发更新与独立全菜单审计均计入总预算。S1/S2结果只用于开发更新v2，S3/AUDIT在v2冻结后才运行。\n\nSUPPORTED：已执行选择的完整资格与另一个RETURN全菜单审计可以检验有限发现率/漏优风险；被省略状态的其他尾部未执行，其最优性和漏优率NOT_ESTABLISHED。OOD分数与拒绝记录全部保留，不把未运行候选标作失败或合格。训练成本摊销后净节省NOT_ESTABLISHED。\n")
write('MOTION_FORCE_MOMENT_TRADEOFF.md', '''# Motion、force与moment取舍

CONFIRMED：v5 COMPOSE相对强固定约+8.058633 N·s JF、−1.904880 Nm·s JM，不能称全面低负担。新增BLEND仅试图减少该JF代价，可能回升JM且损失少量平顺性收益；精确配对结果见analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json和SMOOTHNESS_BASELINE_COMPARISON.md。

CONFIRMED：原任务、native未滤波motion、force/moment峰值、tracking、excursion、累计运动、端点/阶段边界、phase/HOLD时长和ownership条件共同保留。full与remaining成本、jerk/wrench分量单列。原门FAIL或partial不进入正式低成本成功排名。

HYPOTHESIS：运动与力变化率改善可能与提前降低rolling交接速度及局部时序有关；本轮没有新增独占中介比例或临床舒适度证明。
''')
write('LEARNING_CONTROL_INTERFACE_GUIDE.md', '''# 执行接口与复核入口

CONFIRMED：仅在独立v6包运行，正式B/H150/18D、Human/robot/cuff物理、原clearance guard、task/scorer与历史模型未被替换。实际Python为../rl_b_cloud_v1/.venv/bin/python，numpy2.2.6/scipy1.15.3/MuJoCo3.10.0与v5相同。首次误查旧报告的不存在环境路径及未使用的本包pip bootstrap只是工程准备，不算物理尝试。

CONFIRMED：source/v6_common_worker.py实现一次当前决策后恢复COMPOSE；v6_test_worker.py增加冻结模型现场预测身份记录；v6_legacy_worker.py保留原B后续；v6_worker.py用于整段固定方案。v6_features.py只读当前因果状态；v6_model.py/v6_eligibility.py/v6_selection.py分开成本、观测峰值风险和完整资格风险；v6_online.py在H保存预测，完整summary尚不存在。每job的SOURCE_MANIFEST与配置SHA为实际执行身份，未使用的复制历史工具不自动运行。

CONFIRMED：source/v6_prescreen.py是传统phase动作库均值规则，执行前打分并依据阶段有效坐标去重，原planner/admission/guard仍决定所有实际写入。代理拒绝/回退不替代原门。S1/S2开发更新与S3/AUDIT冻结验证分离，所有未执行身份可核查。

CONFIRMED：部署入口是v6_selection.select，v6_model.py保留的旧select未用于本轮冻结选择。主模型的score_index=3使用菜单中心化tail JF作相对排序，不能把该score当绝对剩余JF；绝对tail JF/JM/remaining duration另行重算误差。阶段库也使用已付费历史标签，并不是零开发成本。

复核：source/v6_scorer_replay.py直接调用原evaluate_execution_mode，绕开缓存并独立重建native motion；v6_identity_replay.py逐字段比较v5匹配轨迹；protect_history.py审计所有历史文件；VERIFY_PACKAGE.py只读验证本包manifest。主端点结果见END.json，全部物理START/END见runtime/ATTEMPTS.jsonl。

NOT_TESTED：没有廉价候选H状态预测器，因此Critic菜单还不是低成本在线控制器。原native精确资格在线monitor、完整lifecycle历史充分性、host实时、硬件、患者泛化、临床舒适度均未资格化。不自动运行Stage2、最终Campaign、下一轮研究或Git写操作。
''')
# Nineteen requested answers, with explicit epistemic labels and evidence links.
meanblend=[r for r in blend if r['role'].startswith('independent')];bg=float(np.mean([r['BLEND_JF_reduction_vs_COMPOSE'] for r in meanblend])) if meanblend else None;bj=float(np.mean([r['BLEND_JM_increase_vs_COMPOSE'] for r in meanblend])) if meanblend else None
answers=[
('CONFIRMED',f"实际经过{elapsed/3600:.3f}小时；MuJoCo START/END={a.get('physical_START',0)}/{a.get('physical_END',0)}，新增native={a.get('actual_new_native_steps',0)}步（{f(a.get('actual_new_simulation_seconds'),3)}模拟秒），cold parent={a.get('cold_parent_episodes',0)}。这些是动力学仿真，不是硬件/患者试验。"),
('CONFIRMED','v5 7266文件manifest一致；五个代表方案从raw重算JF/JM与native jerk吻合；已复用的VAL03前缀B/COMPOSE原trace、native与receipt逐字段复现通过。详见audit/BASELINE_RAW_RECOMPUTE.json、audit/V5_MATCHED_RAW_REPRODUCTION.json。'),
('SUPPORTED',f"提前交接协调的HANDOFF/PATTERN/COMPOSE仍是强平顺性基线；有限BLEND插值在{len(meanblend)}个冻结新前缀检验。90%保留要求及各状态结果见SMOOTHNESS_BASELINE_COMPARISON.md；不把开发结果当独立测试。"),
('SUPPORTED','4kHz cuff力变化率与jerk分别评价，native缓存与5ms重合点一致；BLEND保留比例按髋jerk、膝jerk、力模长变化率三项共同检查。降低波动不等于平均负载、所有力矩分量或舒适度都改善。'),
('CONFIRMED',f"冻结BLEND确认中相对COMPOSE平均少JF={f(bg)} N·s，平均多JM={f(bj)} Nm·s；原强固定的JF/JM对照与所有失败单列，不能称全面低负担优势。"),
('CONFIRMED','Critic加入因果累计测量成本、observer峰值及guard/context历史；训练折内缩放加物理下限，保留时间；成本/风险分开且后续策略标签隔离。风险父状态别名已纠正。精确native在线资格、完整fallback历史和充分状态仍未闭合。'),
('CONFIRMED',f"四组主冻结测试实际完成{e.get('primary_states',0)}组；相对训练固定规则改变真实物理选择{e.get('critic_distinct_physical_choices_vs_training_fixed',0)}组。逐方法动作、完整成本、门资格、jerk/wrench与预测误差见CRITIC_DECISION_VALUE.md。"),
('SUPPORTED',f"同时超过1秒短窗和训练时冻结的强phase规则且差值>0.02N·s的状态：{e.get('meaningful_independent_increment_states',[])}。没有独立增量时不将恢复短视选择称为不可替代的Learning价值。"),
('SUPPORTED','出程失败是否避免以LEGACY_NEW_O冻结新状态的原门和H前峰值为准，见analysis/evaluation/LEGACY_NEW_O.json。历史五个失败仅一个父状态族，不能用旧job分组CV宣称泛化修复；尾部低成本不能抵消已知原合同失败。'),
('CONFIRMED',f"Critic完整菜单节省=0。独立的传统执行前库筛选实际省略{screen.get('prospectively_omitted_unique_complete_candidate_runs',0)}个唯一候选完整续跑，对照为预登记去重枚举；未建立研究训练/审计成本摊销后的净节省，也不归因于Critic。"),
('SUPPORTED','传统固定库、phase规则与单一局部插值提供直接可核验对照。本轮BO/ILC及新PPO训练NOT_RUN；不做跨合同算法排行榜或宣称普遍优越。'),
('CONFIRMED','确认了job名分组会掩盖实际父状态复用、近恒定时钟在微小scale下扭曲核距离、相位无效坐标造成动作别名，以及费用预测无法改变已发生的资格失败。原guard不替换；没有重新开展广域clearance分析。'),
('HYPOTHESIS','observer峰值与guard历史是否足以预测完整native资格、改善是否能跨Human泛化、滚动交接是否独占波动来源，以及临床舒适度影响，仍无充分验证。'),
('SUPPORTED','新证据仅覆盖同一nominal Human的冻结合法prefix；具体资格与效果逐状态报告。没有把不同prefix或同父多动作称为不同患者。'),
('SUPPORTED','保留小型Critic作为诊断工具；若冻结选择与强规则相同，暂停该成本模型扩张。优先保留可解释的平顺性协调与已核验固定方案，风险路线需新的独立失败父状态和合法在线资格信息。'),
('SUPPORTED','Learning定位收窄为有因果状态支持、能改变实际决策且超过强规则的预测补充；更小RMSE、更多标签或换Q/PPO名称都不能代替独立控制价值。'),
('SUPPORTED','下一轮最具体问题是：在固定平顺性后续策略下，获取多个独立失败/边界父状态，建立可在线取得且对应原native门的不可逆风险信息，并先检验是否存在强phase规则解决不了的动作排序变化。'),
('CONFIRMED','长期日志已核对v5完整记录，已追加v6开始与失败父状态去重转折；'+('实际结束条目与append-only审计已完成。' if end.get('state')=='STOP' else '实际结束条目及最终append-only审计仍待封包。')),
('CONFIRMED' if end.get('state')=='STOP' else 'NOT_TESTED','所有owned作业是否结束以audit/OWNED_PROCESS_FINAL.json及END.json为准；最终STOP，不自动开启下一轮。')]
body='# iHEAR Lab — Smoothness Critic Integration v6\n\n'+state+'。T0='+act['T0_UTC']+'；六小时硬截止='+act['deadline_UTC']+'。所有新实现与raw隔离于本包，原guard和任务/运动门保持。\n\n'+'\n\n'.join(f'{i}. **{tag}** — {text}' for i,(tag,text) in enumerate(answers,1))+'\n\n详细证据：SMOOTHNESS_BASELINE_COMPARISON.md · CRITIC_MODEL_AUDIT.md · CRITIC_STATE_AND_LABEL_AUDIT.md · CRITIC_DECISION_VALUE.md · OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md · RESOURCE_AND_ATTEMPT_ACCOUNTING.json · PACKAGE_VERIFICATION.json。\n'
write('REPORT.md',body)
write('NEXT_RESEARCH_DECISION.md', '''# 下一研究决策

SUPPORTED：优先保留原门通过、取舍明确的固定平顺性方案。BLEND是否值得保留按冻结新prefix的JF/JM与90%收益保留结果决定，不能按测试后更换阈值。

SUPPORTED：若主Critic与训练冻结phase规则相同或不能超过1秒窗口，暂停该成本模型扩张；不自动换Q/PPO继续试。先寻找真实状态相关排序差异，或补足可在线观测的不可逆motion风险。

CONFIRMED：旧失败五条仅一个独立父状态族。新风险研究应获得多个合法独立失败/边界状态，冻结后保留完全未参与模型选择的测试；原B与平顺性后续标签继续隔离。

SUPPORTED：传统事前动作库筛选若在独立审计中保持资格和有限菜单质量，可作为减少穷举的工程策略；当前不能宣称整体研究已节省训练成本、一般漏优率为零或Learning不可替代。

NOT_TESTED：跨commissioned Human、患者级自适应、硬件实时、临床、长程PPO、Stage2、最终Campaign、服务器扩容。本包不会自动启动这些工作或下一轮。
''')
print('REPORTS_WRITTEN',len(answers),'answers',state,flush=True)
