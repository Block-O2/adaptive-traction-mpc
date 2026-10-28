"""Compose final scientific interpretation from actual, separately audited data.

This module changes reporting only. It neither chooses nor executes candidates.
"""
import json, time, collections
import numpy as np
from acl2_shared import P, R, read, put, utc, records, native_used

def get(name, default=None):
    return read(name) if (P/name).exists() else default

def write(name, text):
    (P/name).write_text(text.rstrip()+'\n')

def number(value, digits=6):
    return 'NOT_RUN' if value is None else f'{value:.{digits}f}'

def best(rows):
    return min((r for r in rows if r.get('qualified')), key=lambda r:r['JF'], default=None)

def table(headers, rows):
    return '|'+ '|'.join(headers)+'|\n|'+ '|'.join(['---']*len(headers))+'|\n'+''.join('|'+ '|'.join(str(v) for v in row)+'|\n' for row in rows)

def main(status='RUNNING'):
    allrows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()]
    D={r['id']:r for r in allrows}; A=read('ACTIVATION.json')
    summary=read('REPORT_SUMMARY.json'); account=get('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',{})
    baseline=D.get('INTERFACE_B'); H=D.get('INTERFACE_H150'); strong=D.get('CORE_STRONG',D.get('INTERFACE_STRONG'))
    development=[r for r in allrows if not r['id'].startswith('LOCKED_')]
    modal=[r for r in development if r['action'].get('family')=='modal8_retimed']
    winner=best(modal); raw=get('audit/INDEPENDENT_RAW_AUDIT.json',{})
    scorer=get('audit/UNCHANGED_SCORER_REPLAY.json',{}); pporeplay=get('audit/PPO_ON_POLICY_REPLAY.json',{})
    matched=get('MATCHED_BUDGET_RESULTS.json',{}); frozen=get('FROZEN_VALIDATION_ANALYSIS.json',{})
    response=get('REFERENCE_RESPONSE_LEARNING_RESULTS.json',{'status':'NOT_RUN'})
    gate=get('audit/RETIMED_INTERFACE_GATE.json',{}); lock=get('FROZEN_SELECTION.json',{})
    verification=get('PACKAGE_VERIFICATION.json',{}); close=get('CLOSURE_START.json')
    elapsed=(time.time()-A['t0_unix'])/3600
    headline=('尚无新增、完整且原门合格的modal运动。' if winner is None else
        f"新增表示内最佳已执行合格方案为 `{winner['id']}`：JF={winner['JF']:.6f} N·s、JM={winner['JM']:.6f} Nm·s。")
    attribution='尚无新增最佳运动可作表示归因。'
    if winner:
        coords=np.asarray(winner['action'].get('x',[0]*8));names=['O_common_path','O_relative_path','R_common_path','R_relative_path','O_local_time','R_local_time','O_pass_speed','R_pass_speed'];active=[names[i] for i in range(8) if abs(coords[i])>1e-12]
        attribution='当前最佳的非零模式为'+str(active)+'。'+('没有请求独立局部时长缩放；原scheduler仍会因路径/速度变化重新求合法时长。' if not np.any(abs(coords[4:6])>1e-12) else '请求了独立局部时长缩放，但未逐项消融最优组合，不能把全部增量唯一归于时间。')+' 时间权限扩展另有相同boundary下1.365→1.385s的构造证据。最佳运动是否能由完整旧18D重新表达，或只是旧局部二维范围之外的已有运动，尚未进行匹配反事实验证；不能把本轮额外JF收益统称为旧18D之外的新自由度收益。'
        put('REPRESENTATION_ATTRIBUTION_STATUS.json',dict(utc=utc(),best_id=winner['id'],active_modes=active,independent_time_requested=bool(np.any(abs(coords[4:6])>1e-12)),compiler_family_extension_witness='audit/EXECUTABLE_FAMILY_EXTENSION_WITNESS.json',global_old18D_equivalence_test='NOT_RUN',explanation=attribution))
    gains=[]
    for label,ref in [('同链B',baseline),('同链H150',H),('强固定参照',strong)]:
        if ref and winner:
            gains.append([label,number(ref['JF']),number(ref['JF']-winner['JF']),number(100*(ref['JF']-winner['JF'])/ref['JF']),number(winner['JM']-ref['JM'])])
    gain_table=table(['参照','参照JF','降JF N·s','降JF %','JM变化 Nm·s'],gains)
    methodrows=[]; methods={}
    for arm in 'ABC':
        rows=[r for r in allrows if r['id'].startswith('CORE_'+arm+'_')]
        initial=[r for r in rows if int(r['id'].rsplit('_',1)[1])<=16]
        adaptive=[r for r in rows if int(r['id'].rsplit('_',1)[1])>16]
        b=best(rows); bi=best(initial); ba=best(adaptive)
        methods[arm]=dict(attempts=len(rows),complete=sum(r['complete'] for r in rows),qualified=sum(r['qualified'] for r in rows),best=b,common_design_best=bi,adaptive_best=ba)
        methodrows.append([arm,len(rows),sum(r['complete'] for r in rows),sum(r['qualified'] for r in rows),number(b['JF'] if b else None),number(b['JM'] if b else None),number(bi['JF'] if bi else None),number(ba['JF'] if ba else None)])
    method_table=table(['方法','候选尝试','完整','原门合格','最佳JF','对应JM','共同前16最佳JF','后16最佳JF'],methodrows)
    budgetrows=[[r['physical_branch_attempt_budget'],r['method'],number(r['best_qualified_JF']),number(r.get('best_evaluated_PPO_mean_JF')),r['actual_new_native_steps']] for r in matched.get('fixed_attempts',[])]
    budget_table=table(['候选物理预算','方法','最佳合格sample/候选JF','PPO已评价mean最佳JF','新增native'],budgetrows)
    prequential=get('LEARNING_DECISION_RESULTS.json',{}); learn=prequential.get('summary',{})
    learned_rows=prequential.get('rows',[])
    adaptive_learning=[r for r in allrows if r['id'].startswith('CORE_C_') and (r.get('prediction') or {}).get('model_id')]
    changes=sum(bool((r.get('prediction') or {}).get('nominal_counterfactual',{}).get('changed_by_learning')) for r in adaptive_learning)
    cf=frozen.get('same_pool_native_counterfactuals',[])
    cfrows=[[r['pair'],r['winner'],number((r.get('learned') or {}).get('JF')),bool((r.get('learned') or {}).get('qualified')),number((r.get('nominal') or {}).get('JF')),bool((r.get('nominal') or {}).get('qualified'))] for r in cf]
    cf_table=table(['固定反事实对','原门赢家','Learning JF','合格','同池名义JF','合格'],cfrows) if cf else 'NOT_RUN：尚无两组冻结同池反事实的实际评价。'
    frozenmetrics=frozen.get('frozen_failure_domain',{'status':'NOT_RUN'})
    force_effect='NOT_RUN'
    if winner and strong:
        phase=[]
        for ph in ['OUTBOUND','HOLD','RETURN']:
            x=winner['phase_cost'][ph];b=strong['phase_cost'][ph]
            phase.append([ph,number(x['J_F_N_s']-b['J_F_N_s']),number(x['moment_integral_Nm_s']-b['moment_integral_Nm_s']),number(x['phase_clock_duration_s']-b['phase_clock_duration_s'])])
        force_effect=table(['phase','ΔJF N·s','ΔJM Nm·s','Δphase时长 s'],phase)
    joint=[r for r in modal if r.get('qualified') and strong and r['JF']<strong['JF']-.01 and r['JM']<strong['JM']-.01]
    pareto=best(joint)
    pareto_text=('尚未观察到相对强固定参照同时改善JF和JM至少0.01的完整合格方案。' if pareto is None else
        f"观察到相对强固定参照同时改善JF/JM的方案 `{pareto['id']}`：JF={pareto['JF']:.6f}、JM={pareto['JM']:.6f}；这不等于相对B也同时改善。")
    ppo=get('jobs/PPO_SCRATCH/PPO_RESULTS.json')
    train=[r for r in allrows if r['id'].startswith('PPO_SCRATCH_TRAIN_')]
    means=[r for r in allrows if r['id'].startswith('PPO_SCRATCH_MEAN_')]
    bt=best(train); bm=best(means)
    ppo_text=('PPO尚未完成；实际已执行训练分支%d，已执行mean评价%d。'%(len(train),len(means)) if ppo is None else
        f"已完成scratch训练{ppo['training_episodes']}个episode，即{ppo['RL_decisions']}个高层RL决策；policy更新epoch为{ppo['Adam_updates']}，mean/std/value三组Adam共{3*ppo['Adam_updates']}次参数组更新。")
    ppo_text+=f" 训练sample最佳合格JF={number(bt['JF'] if bt else None)}；训练后已实际评价mean最佳合格JF={number(bm['JF'] if bm else None)}。两者分别报告。"
    if means:
        lastmean=max(means,key=lambda r:int(r['id'].rsplit('_',1)[1]))
        ppo_text+=f" 末次实际mean检查点为{lastmean['id']}：JF={number(lastmean.get('JF'))}、JM={number(lastmean.get('JM'))}、原门合格={lastmean['qualified']}。开发检查点择优和末次策略分别保留。"
    pporows=[[r['id'],r['complete'],r['qualified'],number(r.get('JF')),number(r.get('JM')),number(r.get('worst_ratio'))] for r in means]
    ppo_table=table(['mean检查点','完整','合格','JF','JM','归一化最差motion比例'],pporows) if means else 'NOT_RUN'
    ppo_diagnosis=dict(status='NOT_RUN')
    if train:
        rewards=[]
        rollout=P/'jobs/PPO_SCRATCH/RL_ROLLOUTS.jsonl'
        if rollout.exists(): rewards=[json.loads(s) for s in rollout.read_text().splitlines()]
        initial_best=methods['A']['common_design_best']
        ppo_diagnosis=dict(training_attempts=len(train),complete=sum(r['complete'] for r in train),qualified=sum(r['qualified'] for r in train),training_best_id=bt['id'] if bt else None,best_sample_JF=bt['JF'] if bt else None,best_evaluated_mean_id=bm['id'] if bm else None,best_evaluated_mean_JF=bm['JF'] if bm else None,known_common_design_best_JF=initial_best['JF'] if initial_best else None,samples_matching_or_beating_known_design=sum(bool(r['qualified'] and initial_best and r['JF']<=initial_best['JF']+1e-8) for r in train),reward_min=min((r['reward'] for r in rewards),default=None),reward_max=max((r['reward'] for r in rewards),default=None),strict_force_order_within_qualified_reward=True,one_decision_per_episode=True)
        if initial_best:
            target=np.asarray(initial_best['action']['x']);distance=[float(np.linalg.norm(np.asarray(r['action']['x'])-target)) for r in train]
            ppo_diagnosis['closest_sample_distance_to_known_design_action']=min(distance)
            ppo_diagnosis['distance_is_not_probability_of_good_region']=True
        put('PPO_EXPLORATION_DIAGNOSIS.json',ppo_diagnosis)
    cross=frozen.get('cross_state',[]); crossrows=[]
    for state in cross:
        for method,r in state['methods'].items():
            crossrows.append([state['group'],method,state['B_qualified'],state['H150_qualified'],state['strong_qualified'],r.get('complete','NOT_RUN'),r.get('qualified','NOT_RUN'),number(r.get('JF')),number(r.get('JM')),number(r.get('gain_vs_qualified_strong')),number(r.get('gain_vs_qualified_B')),number(r.get('worst_ratio'))])
    cross_table=table(['合法状态','冻结方法','B合格','H150合格','强固定合格','完整','合格','JF','JM','相对合格强固定降JF','相对合格B降JF','原motion最差比例'],crossrows) if cross else 'NOT_RUN：独立合法prefix尚无闭合评价。'
    cross_baselines=[]
    for state in cross:
        for label,key in [('B','B'),('H150','H150'),('强固定','strong')]:cross_baselines.append([state['group'],label,state.get(key+'_qualified'),number(state.get(key+'_JF')),number(state.get(key+'_JM'))])
    cross_baseline_table=table(['合法prefix','同状态参照','原门合格','完整JF','完整JM'],cross_baselines) if cross_baselines else 'NOT_RUN'
    allocation=get('VALIDATION_ALLOCATION.json',{})
    extension=get('VALIDATION_TIME_EXTENSION_LOCK.json',{});unrun_states=len(extension.get('remaining_not_run',allocation.get('unrun_prefixes',[])))
    response_rows=response.get('rows',[])
    response_table=table(['冻结测试','完整','合格','参考响应预测JF','传统成本预测JF','实际JF','参考响应预测JM','传统成本预测JM','实际JM'],[[r['id'],r['complete'],r['qualified'],number(r.get('predicted_JF')),number((r.get('native_scalar_prediction') or [None,None])[0]),number(r.get('JF')),number(r.get('predicted_JM')),number((r.get('native_scalar_prediction') or [None,None])[1]),number(r.get('JM'))] for r in response_rows]) if response_rows else 'NOT_RUN：尚无参考响应模型的前瞻物理测试。'
    response_text='补充参考响应模型使用共同的17条因果控制历史（强固定+16个单向设计），学习参数到实签q/dq/ddq的有符号局部响应，再由原估计Human模型与allocator算负荷。仅用于离线排序，实际控制仍接收普通modal参数、经过原certificate和执行链。相同17条历史及相同候选池的传统成本响应模型、原粗名义模型各有一个冻结实测对照；另测两个参考响应候选。额外4次测试、cold parent及B/H150/strong均计账。它没有学习跨状态模型，没有原生motion预测或校准不确定性。'
    response_table_text=response_text+'\n\n'+response_table
    response_interp='当前无完整前瞻结果，不能从事后重建成绩推断新模型有效。'
    if response_rows:
        rb=response.get('best_learned_reference_candidate');scalar=response.get('native_scalar_same_pool_counterfactual');nom=response.get('nominal_same_pool_counterfactual')
        def candidate_cost_status(row):
            if row is None:return 'NOT_RUN'
            if row.get('qualified'):return number(row['JF'])+'（合格）'
            return number(row.get('JF'))+'（完整但不合格，仅诊断）' if row.get('complete') else 'PARTIAL_UNRANKED'
        tested_model_count=sum(r['id'].startswith('RESPONSE_MODEL_') for r in response_rows)
        reference_best=number(rb['JF']) if rb else '无合格候选（已实测%d个）'%tested_model_count
        response_interp=f"参考响应候选最佳合格JF={reference_best}；同数据传统成本模型JF={candidate_cost_status(scalar)}；同池粗名义候选JF={candidate_cost_status(nom)}。"
        if rb and scalar and scalar.get('qualified'):
            delta=scalar['JF']-rb['JF'];response_interp+=f" 参考响应候选相对传统成本模型实际降JF={delta:.6f} N·s；有限两候选对一候选、单次固定上下文结果，不能据此单独证明一般算法优势。"
        response_interp+=' 相同动作的多次执行只证明复现；不当作不同学习决策。预测误差另按唯一动作去重，attempt加权误差不作为独立新动作数量。'
    failures=[r for r in allrows if not r['qualified']]
    failed_counts=collections.Counter(x for r in failures for x in (r.get('motion_vs_B',{}).get('failed_requirements') or [r.get('error') or 'UNSPECIFIED']))
    failed_table=table(['ID','任务完整','原门合格','JF仅在完整任务可比较','错误/原门原因'],[[r['id'],r['complete'],r['qualified'],number(r.get('JF')) if r['complete'] else 'PARTIAL_UNRANKED',str(r.get('motion_vs_B',{}).get('failed_requirements') or r.get('error'))[:260]] for r in failures])
    interface='''A1保持原二维物理动作集合，用原坐标和和/差坐标执行同一动作；完整trace/native torque/receipt一致，随后各8个同预算候选比较搜索效率。A2在强固定参照上增加去程/回程的共同路径、相对路径、局部时长及通过速度模式。八方向实签参考差分数值秩为8，说明这组局部干预均能产生不同参考；不代表在原18D之外增加8个全局独立自由度。路径与通过速度部分可与旧18D重叠，独立局部时长相对旧最短时长构造扩展了可执行族。实际构造证据：同一OUTBOUND内部slot（slot=1）的目标/通过速度下，原最短1.365 s，新增模式签发1.385 s且原门合格，见 `audit/EXECUTABLE_FAMILY_EXTENSION_WITNESS.json`；这不是旧18D全局维度秩证明。

初版固定时长导致OUTBOUND空间proposal被原速度certificate拒绝；RETURN有一关节已达终点时仍改其位置，触发原KNEE_REFERENCE_MUST_BE_CONSTANT保护。v2通过原scheduler重新求合法最小时长，并逐关节保留已达目标的位置锁。原物理、任务端点/HOLD、安全、scorer、低层反馈和allocator保持。零modal逐raw复现强固定；零改H150及A1同动作也各有独立完整raw一致门。负局部时长仍可能被原certificate拒绝或成为无效动作，优化器不能把参数幅度视为实际权限。'''
    write('REPRESENTATION_STUDY.md','# 可执行协调表示\n\n'+interface+'\n\n'+attribution+'\n\n'+headline+'\n\n'+gain_table+'\n见 `audit/RETIMED_INTERFACE_GATE.json`、`audit/INTERFACE_A1_ROTATED_REPEAT_GATE.json` 与 `LEARNING_CONTROL_INTERFACE_GUIDE.md`。')
    write('UPPER_LEVEL_OPTIMIZATION.md','# 上层快速协调优化\n\nA为直接pattern search，B为粗名义负荷引导，C为同类名义模型加GP残差/经验completion筛选。各32个候选，前16个方向设计分别实际执行、各自保留反馈，后16才自适应。共同参照在预算0已公开，各方法可保留它；共同设计中的收益不能归于Learning。\n\n'+method_table+'\n\n'+budget_table+'\n\n曲线见 `figures/MATCHED_BUDGET_CURVES.png`。PPO mean评价消耗真实预算；最佳训练sample与已评价策略mean分开。cold parent、共同参照、接口开发、旧历史先验和补充分支在总账单列。单次搜索轨迹不能给出多seed统计优势；便宜代理未被宣称满足5ms在线控制。\n\n'+response_table_text)
    write('PHYSICS_AND_LEARNING_COMPARISON.md','# 物理、传统与Learning比较\n\n'+method_table+'\n\n'+budget_table+'\n\n粗名义模型不是可执行reference的精确前向模拟：平滑模板对离散slot、最小时长/准入、fallback及闭环跟踪的近似会改变排序。事后使用真实实签reference的名义负荷增量RMSE为0.027049 N·s，原预序粗模型为3.753157 N·s（8条开发干预）；前者不可作为前瞻成绩。数值构造消融也显示粗参考导数重建贡献了部分误差，不能把全部差距唯一归于未知Human物理。\n\n'+response_table_text+'\n\n'+response_interp)
    write('LEARNING_DECISION_ANALYSIS.md','# Learning的实际决策贡献\n\nGP要补足粗名义负荷与原motion结果之间的系统残差。它只使用各自已完成历史；完整但motion不合格的样本仍用于成本/余量训练，未完成任务的完整成本保持未定义，并保留completion标签。经验completion score不是校准概率，GP区间不是安全保证。\n\n1. 数值：预序开发统计见 `LEARNING_DECISION_RESULTS.json`，模型逐次变化且测试点由模型选择，不能作冻结无偏泛化成绩。\n2. 排序：冻结失败域的Spearman和成对顺序见下表；完整但失败的成本仍保留。\n3. 选择改变：自适应阶段已有%d条带GP的预序候选，其中%d次与同池名义选择不同。\n4. 实际价值：先选定最早两次改变的proposal，再对两方动作都进行冻结原链实测；结果如下。\n\n%s\n\n冻结6个随机失败域的结果（同状态，非新患者；模型在打开前冻结）：\n\n```json\n%s\n```\n\n%s\n\n%s\n\n没有把RMSE、排序、选择改变和最终实际合格JF互相替代。'%(len(adaptive_learning),changes,cf_table,json.dumps(frozenmetrics,ensure_ascii=False,indent=2),response_table_text,response_interp))
    write('PPO_STUDY.md','# PPO在新协调表示中的真实探索\n\n'+ppo_text+'\n\n'+ppo_table+'\n\n新8D actor从零mean、STD=0.2开始scratch；固定合法上下文用8维高斯mean/logSTD和scalar critic表达，每个任务只commit一个高层计划。没有语义不兼容的旧checkpoint或rollout复用。tanh动作使用精确变换密度且采样后不clip；同generation的8个episode来自一个冻结behavior，每批后更新。policy clip=0.2、全局梯度norm=0.5、mean/std LR=0.01/0.002；STD更新边界[0.05,0.7]、最多8个epoch，exact Gaussian KL和经验ratio KL任一>0.03后停止后续epoch。最后一次更新可超过阈值，没有宣称硬KL约束或回滚。entropy项为变换前Gaussian。\n\n合格任务reward为 `5*tanh((strongJF-JF)/5)`，在合格集合内严格保持JF排序；完整但不合格为负惩罚，未完成=-20。return=单次reward，raw advantage=reward-同批前value；同批中心化/标准化。同批constant scalar value在advantage中心化时完全相消，因此critic不贡献本固定上下文的actor排序；这是单决策PPO探索对照，不是状态依赖value学习。不存在本任务必须依靠多步GAE的证据。\n\n探索与信号诊断：\n\n```json\n'+json.dumps(ppo_diagnosis,ensure_ascii=False,indent=2)+'\n```\n\n独立重放状态：`'+pporeplay.get('status','NOT_RUN')+'`；重算seed采样、变换密度、原任务reward、advantage、五点差分clip目标梯度和Adam状态，详见 `audit/PPO_ON_POLICY_REPLAY.json`。真实native积分不是独立RL样本。完整budget含mean评价，按相同累计物理预算与A/B/C比较，额外64集结果另列。')
    write('FAILURE_MECHANISM_ANALYSIS.md','# 失败机制与未排除解释\n\n已证实的执行机制：固定时长的新空间proposal会被速度certificate拒绝，实际参考回退；RETURN逐关节终点未锁住会触发原task断言。保留初版全部raw/partial；修复只改变表示编译与原scheduler的调用，没有放宽原门。\n\n已支持的预测机制：事后实际reference名义负荷重建与粗前向模板之间误差很大；数值导数输入消融解释一部分，剩余映射/准入/闭环差异需前瞻响应测试。事后结果不证明新学习器能预测未来。\n\n失败/不合格计数：'+str(dict(failed_counts))+'。\n\n'+failed_table+'\n\n未完成任务的低积分不参与优胜比较。motion失败由原native速度/加速度/jerk、excursion、phase/endpoint及JM门定位；原绝对安全与原任务合格分开。没有由有限负结果推断Learning普遍无用，没有证明有限最优达到物理上限。跨患者参数、可部署motion观测和真正少次历史适应仍为未验证问题。')
    trade_details='NOT_RUN'
    if winner:
        comp=winner.get('motion_vs_B',{})
        trade_details='动作 `'+winner['id']+'`，x='+json.dumps(winner['action'].get('x'))+'。tracking RMS髋/膝='+str(winner.get('tracking'))+' deg；原motion最大归一化比例='+number(winner.get('worst_ratio'))+'。\n\n原门相对B负担比例：\n\n```json\n'+json.dumps(comp.get('burden_ratios',{}),ensure_ascii=False,indent=2)+'\n```\n\nnative v/a/jerk负担阈值1.0/1.05/1.10/1.25的敏感性单列，其他原门保持：'+str(comp.get('burden_sensitivity'))+'。'
    write('MOTION_FORCE_MOMENT_TRADEOFF.md','# 完整force、moment与实际Human运动\n\n'+headline+'\n\n'+gain_table+'\n\n'+pareto_text+'\n\n相对强固定参照的phase分解：\n\n'+force_effect+'\n\n'+trade_details+'\n\n见 `figures/FORCE_MOMENT_TRADEOFF.png`、`figures/HUMAN_MOTION_AND_NATIVE_JERK.png`、`figures/PHASE_FORCE_MOMENT_CHANGES.png`。native motion逐采样、未滤波、不删端点。原合格表示通过既定仿真门；不保证所有运动指标均改善，也不等于临床舒适性。')
    write('CROSS_STATE_RESULTS.md','# 冻结后的独立合法状态\n\n候选、模型、代码和prefix在任何新验证结果前由 `VALIDATION_INPUT_LOCK.json` 冻结。采用T0登记顺序中的前N个不同合法prefix，N由当时剩余wall预算决定。冻结后无训练或调参。\n\n'+cross_baseline_table+'\n\n冻结动作结果：\n\n'+cross_table+'\n\n实际分配：'+str(allocation.get('independent_states','NOT_RUN'))+'个新prefix；未运行登记条件数：'+str(unrun_states)+'。每个状态分别执行该状态B/H150/强固定，只有合格的同状态参照可作降力分母。H150不合格仍保留，并不自动取消其它已登记方法。\n\n这些是同一名义Human的独立合法prefix条件，未改Human物理参数；不能称跨患者。除fork时已执行OUTBOUND前缀造成状态变化外，该条件的公共RETURN前缀也按T0登记执行；这是完整合法prefix条件的转移检验，不能将结果唯一归于初始状态这个单因素。所有方法在各条件内使用相同公共前缀和自己的匹配参照。原训练状态的重复归于LOCKED_REPEAT，不计作新状态。参考响应模型只是固定上下文模型，其跨状态动作测试不等于状态条件学习。')
    next_text='最值得投入的是：在原执行编译器与合法状态变化下，能否用少量已完成运动的因果历史，预测候选实际会激活的参考及可部署motion余量，进而在等物理预算下优于强固定和传统成本响应/ILC/BO？先用本轮最强合格固定方案、原门和未暴露状态，比较history-disabled、传统历史优化与history-enabled响应模型；把前几次探索代价和Trial1→Trial2→Trial3累计负担全部计入。此为下一轮建议，本轮不自动启动。'
    guard=get('audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json',{});cause=get('MOTION_CAUSE_RESULTS.json',{'status':'NOT_RUN','rows':[]})
    if guard.get('status')=='ORIGINAL_GUARD_REPLAY_PASS':
        next_text='先在独立协议中研究原clearance反馈包络切换处的非光滑处理：保持相同几何、安全阈值、物理与scorer，比较分段几何约束或可证明保守的处理是否消除瞬时jerk，并重验B/强固定/最优方案。当前轮没有修改guard。还需用完整旧18D和匹配控制范围检验新最优轨迹的独立表示收益。随后再问：'+next_text
        c=guard['archived_clearance_record'];native=guard['native_motion'];guardtext=f"原链motion反例CORE_C_019已完成任务，但加速度max和jerk RMS不合格。原guard在{guard['causal_source_sample_s']:.6f} s的髋膝近等角位置，对圆柱最低端点切换做中心差分，得到曲率{c['model_curvature_m_s2']:.6f} m/s²、模型广义力矩修正{c['correction_nm']} Nm；native少数20点贡献jerk平方和约{100*native['top20_native_jerk_squared_fraction']:.2f}%。原函数以已记录因果q/dq、gap/gap-rate充分输入重放，曲率和修正量误差均为0。直接物理trace几何与控制器重建Human点存在1.3mm差异，已单独保存；充分输入适配器只用于代数重放，不冒充完整物理状态重建。原native绝对安全审计仍通过；内部近似半空间不可行与原motion失败分别报告。"
        write('FAILURE_MECHANISM_ANALYSIS.md',(P/'FAILURE_MECHANISM_ANALYSIS.md').read_text()+'\n\n'+guardtext+'\n\n原始证据：`audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`；扫描差分模板跨越几何端点分支时曲率可达数千，留在同分支时接近0。该结果确认了既有反馈计算的冲击机制；时序参数能否稳定避免它，需下列预登记实测，不能从代数重放推出患者运动或安全替代方案。')
        cause_table=table(['条件','结果','完整','合格','JF','JM','最小guard曲率','原motion失败'],[[r['id'],r['status'],r.get('complete','NOT_RUN'),r.get('qualified','NOT_RUN'),number(r.get('JF')),number(r.get('JM')),number(r.get('minimum_guard_curvature_m_s2')),r.get('failure_requirements','NOT_RUN')] for r in cause.get('rows',[])])
        write('FAILURE_MECHANISM_ANALYSIS.md',(P/'FAILURE_MECHANISM_ANALYSIS.md').read_text()+'\n\n四个原链条件干预（移除RETURN时长、±0.10、只保留该RETURN时长；初始±0.01因原5ms量化别名在实测前改为±0.10并保留原登记）：\n\n'+cause_table+'\n\n没有关闭guard或修改原门。`MOTION_CAUSE_RESULTS.json`保留全部四结果及开销；此分支不回填主A/B/C模型。')
    pguard=get('audit/PPO_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json',{})
    if pguard.get('status')=='ORIGINAL_GUARD_REPLAY_PASS':
        c=pguard['archived_clearance_record'];text=f"相同机制也在PPO_SCRATCH_TRAIN_0009出现：任务完整、仅jerk RMS不合格。{pguard['causal_source_sample_s']:.6f}s时实测gap约{c['gap_m']:.6f}m，原包络差分曲率{c['model_curvature_m_s2']:.6f}m/s²触发广义力矩修正{c['correction_nm']}Nm，随后髋native jerk在22.0005s达到约28608deg/s³。用原函数及该次已记录因果充分输入重放，曲率/修正量误差均为0。这支持GP与PPO的部分motion失败共享原低层非光滑反馈机制；不解释所有excursion或速度失败，也不代表PPO全部负结果都由它造成。"
        write('FAILURE_MECHANISM_ANALYSIS.md',(P/'FAILURE_MECHANISM_ANALYSIS.md').read_text()+'\n\n'+text+' 见 `audit/PPO_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`。')
        write('PPO_STUDY.md',(P/'PPO_STUDY.md').read_text()+'\n\n'+text)
    motionrows=[]
    pguard30=get('audit/PPO30_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json',{})
    if pguard30.get('status')=='ORIGINAL_GUARD_REPLAY_PASS':
        text30='PPO第30次同样完成任务但jerk RMS失败，JF=1398.823083不能计为合格收益。原函数因果输入重放PASS：21.995s时gap约0.428344m，差分曲率−624.933894m/s²触发约[8.85168,−2.80086]Nm修正，髋native jerk在21.9955s达到约28503deg/s³。该证据单独保存在 `audit/PPO30_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`，不将所有PPO失败自动归于此机制。'
        write('PPO_STUDY.md',(P/'PPO_STUDY.md').read_text()+'\n\n'+text30)
        write('FAILURE_MECHANISM_ANALYSIS.md',(P/'FAILURE_MECHANISM_ANALYSIS.md').read_text()+'\n\n'+text30)

    analytic=get('audit/CLEARANCE_CUSP_ANALYTIC_DECOMPOSITION.json',{})
    if analytic.get('status')=='PASS':
        analytic_text='零native解析分解进一步确认：C19原差分曲率−1432.356195几乎全部来自端点最小值项−1432.356216；PPO第9次的−449.597641中端点项为−449.568162，光滑项仅−0.029479。两个观测点的10μs原差分均跨分支，单分支解析曲率很小。精确切换点差分存在1/h尺度项，但这些非零偏置状态在足够小h下回到同分支，不能笼统称h趋零发散。详见 [解析说明](CLEARANCE_CUSP_ANALYTIC_NOTE.md)。'
        write('FAILURE_MECHANISM_ANALYSIS.md',(P/'FAILURE_MECHANISM_ANALYSIS.md').read_text()+'\n\n'+analytic_text)
        next_text+=' 对袖套端点最小值可先研究等价的两个光滑端点gap约束；代数等价并不证明替代反馈安全或有效，需要独立协议验证，当前未实现。'

    winners=[(label,value['best']) for label,value in methods.items()]+[('PPO trained mean',bm)]
    for label,r in winners:
        if r is None:motionrows.append([label,'NOT_RUN','NOT_RUN','NOT_RUN','NOT_RUN','NOT_RUN','NOT_RUN','NOT_RUN']);continue
        comp=r.get('motion_vs_B',{});ratio=max((max(v) for v in comp.get('burden_ratios',{}).values()),default=None)
        motionrows.append([label,r['id'],number(r['JF']),number(r['JM']),number(r.get('worst_ratio')),number(ratio),comp.get('burden_sensitivity',{}).get('1.05'),str(r.get('tracking'))])
    write('MOTION_FORCE_MOMENT_TRADEOFF.md',(P/'MOTION_FORCE_MOMENT_TRADEOFF.md').read_text()+'\n\n同空间各方法最佳合格结果的运动取舍：\n\n'+table(['方法','已执行方案','JF','JM','预定义最差比例','最大raw v/a/jerk负担比','v/a/jerk≤1.05','tracking RMS髋/膝deg'],motionrows)+'\n\n预定义最差比例是本轮既定仿真motion汇总指标，不是物理安全证明。1.05列仅收紧raw v/a/jerk负担比作敏感性诊断，未改变原门。训练sample最小值不替代PPO trained mean。')
    mech=get('EXECUTED_COORDINATION_MECHANISMS.json',{});termrows=[]
    for m in mech.get('rows',[])[:2]:
        d=m['posthoc_nominal_delta']
        for term in d['force']['signed_projection_delta_by_term']:termrows.append([m['id'],term,number(d['force']['signed_projection_delta_by_term'][term]),number(d['moment']['signed_projection_delta_by_term'][term])])
    if termrows:
        write('MOTION_FORCE_MOMENT_TRADEOFF.md',(P/'MOTION_FORCE_MOMENT_TRADEOFF.md').read_text()+'\n\n原估计模型的事后分量投影账本（N·s / Nm·s）：\n\n'+table(['方案','原模型分量','force投影积分变化','moment投影积分变化'],termrows)+'\n\n这是已实签q/dq/ddq代入原commissioned模型与allocator后的有符号代数分解，各项之和等于该名义norm积分。分量可互相抵消；它们不是独立真实负荷，也不是移除某物理项的因果干预。实际phase JF/JM仍由原scorer决定，不能把重力投影变化直接当作真实患者因果贡献。见 `EXECUTED_COORDINATION_MECHANISMS.json` 和 `figures/EXECUTED_REFERENCE_AND_LOAD_CHANGES.png`。')
    write('NEXT_RESEARCH_DECISION.md','# 下一步具体研究问题\n\n'+next_text+'\n\n本轮没有完成真实连续三trial患者适应，不能把17条或几十次fork的历史缩写为患者两三次学会。Q/Value未启动：本协议每任务只commit一次，没有建立需要多步价值方法解决的特定缺口。增加网络或episode不是当前首选解释。')
    count=len([r for r in records() if r['event']=='START'])
    original_gate=f"8方向执行核验={gate.get('new_modes_executable','NOT_RUN')}，局部实签reference contrast rank={gate.get('observed_issued_reference_contrast_rank','NOT_RUN')}/8。"
    complete_states=sum(bool(c.get('all_registered_candidates_closed')) for c in cross);begun_states=sum(bool(c.get('state_attempted',True)) for c in cross)
    primary_conclusion='目前只有共同设计的配对结果，尚不能判断自适应优化器的最终差异。'
    if min((v['attempts'] for v in methods.values()),default=0)>=32:
        traditional=best([v['best'] for k,v in methods.items() if k in ['A','B'] and v['best']]);cbest=methods['C']['best']
        if traditional and cbest:
            delta=traditional['JF']-cbest['JF']
            primary_conclusion=f"相同32候选预算下，C最佳JF={cbest['JF']:.6f}，最佳A/B={traditional['JF']:.6f}；C额外降JF={delta:.6f} N·s。"+('本次单seed开发轨迹有增量，仍须冻结实测及跨状态检验。' if delta>1e-8 else 'C未超过本轮最强传统主对照。')
    layer=get('GP_DECISION_LAYER_REPLAY.json',{})
    layertext='GP worst_ratio结构下界为sqrt(.95/1.05)，因为其定义包含累计行程比的双侧约束；低于该界的mean为结构性外推错误。没有为改善结果修正运行中的模型。\n\n'
    layertext+='精确同池决策重放：'+str({k:layer.get(k,'NOT_RUN') for k in ['status','adaptive_proposals','decisions_changed','GP_mean_changes','uncertainty_layer_changes','screen_layer_changes','screen_had_candidates','chosen_motion_predictions_below_structural_bound']})+'。各层次差异只证明算法选点改变，未测动作的物理好坏仍未知，详见 `GP_DECISION_LAYER_REPLAY.json`。'
    cfcounts=collections.Counter(r['winner'] for r in cf if r['winner']!='INCOMPLETE_PAIR')
    cftext='冻结双动作原链实测胜者计数：'+str(dict(cfcounts))+'。' if cfcounts else '冻结双动作实测尚未完成。'
    hits=get('OPTIMIZATION_TARGET_HITTING_ANALYSIS.json',{}).get('rows',[])
    hitrows=[[r['method'],r['performance_object'],r['force_gain_target_N_s'],r['status'],r.get('first_attempt'),r.get('actual_new_native_steps')] for r in hits]
    hit_table=table(['方法','评价对象','降JF目标 N·s','结果','首次真实候选尝试','新增native'],hitrows) if hits else 'NOT_RUN'
    coordinate_rows=[]
    for arm in ['NATIVE','ROTATED']:
        rr=[r for r in allrows if r['id'].startswith('COORDINATE_'+arm+'_')];b=best(rr);coordinate_rows.append([arm,len(rr),sum(r['complete'] for r in rr),sum(r['qualified'] for r in rr),number(b['JF'] if b else None),number(b['JM'] if b else None)])
    coordinate_table=table(['旧二维同族坐标','实际候选尝试','完整','合格','最佳JF','对应JM'],coordinate_rows)
    coordtext='同族坐标优化：每臂上限8候选，前4个物理设计相同且分别付费；后4个使用原坐标轴或旋转方向，两臂使用相同备选物理步长集合、实际x平方域相同；边界/重复点过滤后的实际逐次步长另按原账核验。共同cold parent/B/H150另计3条实际START。此分支从H150开始，不混入新8维优化主比较；单次8点结果不证明一般坐标优势。\n\n'+coordinate_table
    coordinate_identity=get('audit/COORDINATE_COMMON_DESIGN_RAW_IDENTITY.json',{})
    if coordinate_identity:
        coordtext+='\n\n新实测共同设计4对的科学raw身份核验='+coordinate_identity['status']+'；实际逐次步长检查='+coordinate_identity['adaptive_step_check']+'。原搜索的相同步长备选集合并不保证边界/重复点过滤后实际步长相同。若有差异，完整8次成绩仅作该受约束搜索的描述；严格等实际步长的比较使用预先登记的、只由步长决定的最长匹配前缀。详见 `audit/COORDINATE_COMMON_DESIGN_RAW_IDENTITY.json` / `COORDINATE_ACTUAL_STEP_AUDIT_ADDENDUM.json`。'
        pref=coordinate_identity['matched_prefix_results']
        coordtext+='\n\n'+table(['坐标','严格匹配前缀候选数','原门合格','最佳JF','对应JM'],[[a,v['candidates_paid'],v['qualified'],number(v['best_JF']),number(v['best_JM'])] for a,v in pref.items()])
    write('REPRESENTATION_STUDY.md',(P/'REPRESENTATION_STUDY.md').read_text()+'\n\n'+coordtext)
    write('UPPER_LEVEL_OPTIMIZATION.md',(P/'UPPER_LEVEL_OPTIMIZATION.md').read_text()+'\n\n'+coordtext)
    scoutrows=[r for r in allrows if r['id'].startswith('PARETO_SCOUT_SCOUT_')];scoutref=D.get('PARETO_SCOUT_STRONG',strong)
    scouttable=table(['预登记scout','O相对路径','R局部时间','完整','合格','JF','JM','相对强固定降JF','相对强固定降JM'],[[r['id'],number(r['action']['x'][1],2),number(r['action']['x'][5],2),r['complete'],r['qualified'],number(r.get('JF')),number(r.get('JM')),number(scoutref['JF']-r['JF'] if scoutref and r['qualified'] else None),number(scoutref['JM']-r['JM'] if scoutref and r['qualified'] else None)] for r in scoutrows]) if scoutrows else 'NOT_RUN：8个预登记force/moment组合尚未实测。'
    write('MOTION_FORCE_MOMENT_TRADEOFF.md',(P/'MOTION_FORCE_MOMENT_TRADEOFF.md').read_text()+'\n\n补充Pareto scout（8候选+4条启动参照/parent；与主32/臂预算分开；仅相对强固定的双改善门JF/JM各0.01）：\n\n'+scouttable)
    if len(scoutrows)==8 and all(r['qualified'] for r in scoutrows):
        native_best=methods['B']['best'];dominated=[r for r in scoutrows if native_best and native_best['JF']<r['JF'] and native_best['JM']<r['JM']]
        fixed_time=sorted([r for r in scoutrows if abs(r['action']['x'][1]-1)<1e-12],key=lambda r:r['action']['x'][5])
        scout_interpretation=f"8个scout中有{len(dominated)}个被已有主比较B最佳{native_best['id']}在JF/JM上同时支配；这组补充点没有自动证明更优Pareto前沿。"
        if len(fixed_time)==4 and np.all(np.diff([r['JF'] for r in fixed_time])>0) and np.all(np.diff([r['JM'] for r in fixed_time])<0):
            first,last=fixed_time[0],fixed_time[-1]
            prefix_same=all(abs(r['phase_cost'][ph][metric]-first['phase_cost'][ph][metric])<1e-9 for r in fixed_time for ph in ['OUTBOUND','HOLD'] for metric in ['J_F_N_s','moment_integral_Nm_s'])
            scout_interpretation+=f" 固定O_relative_path=1、其它路径/通过速度模式为0，R_local_time从{first['action']['x'][5]}增至{last['action']['x'][5]}时，JF从{first['JF']:.6f}升至{last['JF']:.6f}，JM从{first['JM']:.6f}降至{last['JM']:.6f}。去程/HOLD积分一致={prefix_same}，局部回程安排改变了force/moment取舍；这不是缩短完整任务，原phase时钟及门保持。有限4点不证明连续时序的全局规律。"
        write('MOTION_FORCE_MOMENT_TRADEOFF.md',(P/'MOTION_FORCE_MOMENT_TRADEOFF.md').read_text()+'\n\n'+scout_interpretation)
    fullcost=get('MATCHED_TOTAL_INTERACTION_BUDGET_RESULTS.json',{})
    fullrows=[[r['method'],r['total_physical_START_budget'],number(r['best_qualified_JF']),number(r.get('PPO_best_evaluated_mean_JF')),r.get('total_new_native_steps')] for r in fullcost.get('fixed_total_START_budgets',[])]
    fulltable=table(['方法','含启动参照实际START子集预算','最佳合格JF','PPO已评价mean最佳JF','新增native'],fullrows) if fullrows else 'NOT_RUN'
    write('UPPER_LEVEL_OPTIMIZATION.md',(P/'UPPER_LEVEL_OPTIMIZATION.md').read_text()+'\n\n含cold parent及B/H150/strong的完整成本比较：\n\n'+fulltable+'\n\nA/B/C各方法的实际记录子集均包含同一组4条CORE启动参照；这些子集有重叠，总账按union只计一次。PPO使用其自身4条启动记录。没有虚构额外执行或隐藏父前缀成本。见 `MATCHED_TOTAL_INTERACTION_BUDGET_RESULTS.json` 与 `figures/TOTAL_INTERACTION_BUDGET_CURVES.png`。')
    write('UPPER_LEVEL_OPTIMIZATION.md',(P/'UPPER_LEVEL_OPTIMIZATION.md').read_text()+'\n\n固定目标首次达到成本（先登记阈值、后看自适应结果）：\n\n'+hit_table)
    write('LEARNING_DECISION_ANALYSIS.md',(P/'LEARNING_DECISION_ANALYSIS.md').read_text()+'\n\n'+primary_conclusion+'\n\n'+layertext+'\n\n'+cftext)
    signal=get('PPO_EXECUTION_AND_SIGNAL_DIAGNOSIS.json',{})
    if signal.get('status')=='OBSERVED_ACTUAL_ROLLOUTS':
        signal_summary={k:signal.get(k) for k in ['training_attempts','completed_task_count','qualified_count','rollout_records','unique_completed_actual_reference_profiles','exact_strong_reference_repeats','slot_counts','execution_permissions_by_local_timing_sign','nonqualified_full_tasks_with_lower_JF_than_public_strong','qualified_reward_order_mismatches','critic_role']}
        write('PPO_STUDY.md',(P/'PPO_STUDY.md').read_text()+'\n\n实际执行与信号摘要：\n\n```json\n'+json.dumps(signal_summary,ensure_ascii=False,indent=2)+'\n```\n\n每generation的STD、mu、reward方差与饱和、实际激活/拒绝计数、critic相消误差详见 `PPO_EXECUTION_AND_SIGNAL_DIAGNOSIS.json`。')
    structural=get('STRUCTURAL_MOTION_DIAGNOSTIC_RESULTS.json',{})
    structural_text=''
    if structural:
        structural_text='补充结构有界motion GP诊断状态='+structural['status']+'。它与原最终GP使用相同32条训练记录、相同核，提前冻结6个原登记点的预测；只检验目标结构和筛选误放/误拒，未参与任何候选选择。'
        if structural['completed_test_rows']:
            sm=structural['metrics'];a=sm['original_raw_GP'];b=sm['bounded_log_excess_GP']
            structural_text+=f" 在{structural['completed_test_rows']}/6已完成点上，原/有界模型worst_ratio RMSE={a['RMSE']}/{b['RMSE']}，95%覆盖={a['empirical95_coverage']}/{b['empirical95_coverage']}，误放={len(a['screen_false_passes'])}/{len(b['screen_false_passes'])}，误拒={len(a['screen_false_rejects'])}/{len(b['screen_false_rejects'])}。"
        structural_text+=' 有界性不是校准或安全保证，详见 [结构诊断](STRUCTURAL_MOTION_DIAGNOSTIC.md)。'
        write('LEARNING_DECISION_ANALYSIS.md',(P/'LEARNING_DECISION_ANALYSIS.md').read_text()+'\n\n'+structural_text)
    margin_rows=[r for r in allrows if r['id'].startswith('MOTION_MARGIN_BACKOFF_RPASS_')]
    margin_best=best(margin_rows)
    margin_summary=''
    if (P/'MOTION_MARGIN_BACKOFF_PREREGISTRATION.json').exists():
        margin_summary=f"补充motion余量回退已实测{len(margin_rows)}/2个固定候选，最佳原门合格JF="+(number(margin_best['JF']) if margin_best else '无合格结果')+'。这是原参考模型与传统成本模型共同低力动作失败后，利用过去单模态反馈只减小R_pass_speed的传统修复；不归于主GP或PPO收益，2候选+4冷启动/参照另计。0.49deg仅为额外余量目标，原0.5deg门保持。'
        margin_table=table(['固定回退','R_pass_speed','完整','原门合格','预序JF','实际JF','实际JM','预序膝excursionΔdeg','实际膝excursionΔdeg','原最差比例'],[[r['id'],number(r['action']['x'][7],2),r['complete'],r['qualified'],number((r.get('prediction') or {}).get('predicted_JF')),number(r.get('JF')) if r['complete'] else 'PARTIAL_UNRANKED',number(r.get('JM')) if r['complete'] else 'PARTIAL_UNRANKED',number(((r.get('prediction') or {}).get('predicted_excursion_delta_deg') or [None,None])[1]),number((r.get('motion_vs_B',{}).get('excursion_delta_deg') or [None,None])[1]),number(r.get('worst_ratio'))] for r in margin_rows]) if margin_rows else 'NOT_RUN'
        margin_doc='# 运动余量的固定速度回退\n\n'+margin_summary+'\n\n'+margin_table+'\n\n依据：原候选膝excursion超过0.5deg来自RETURN最低点，过去R_pass_speed±0.35干预给出一坐标有限差分。两个新动作在任何本分支结果前固定为0.20/0.05，其余坐标不变。预测使用已经完成的仿真评价反馈，不借用未来Human真值，也不声称这些标签已可在患者上部署。所有失败保留，独立prefix打开前才按既定BEST_FIXED规则选择最佳已发现合格动作；之后无修复。\n\n注册与预算见 `MOTION_MARGIN_BACKOFF_PREREGISTRATION.json`；实际6条START和native量归入完整资源账本。'
        write('MOTION_MARGIN_BACKOFF.md',margin_doc)
        put('MOTION_MARGIN_BACKOFF_RESULTS.json',dict(utc=utc(),status='EXECUTED' if len(margin_rows)==2 else 'PARTIAL' if margin_rows else 'NOT_RUN',candidate_results=len(margin_rows),candidate_budget=2,total_physical_START_budget_including_parent_anchors=6,best_qualified_id=margin_best['id'] if margin_best else None,rows=margin_rows,original_gate_unchanged=True,secondary_margin_target_deg=.49,not_primary_equal_budget_result=True))
        for name in ['UPPER_LEVEL_OPTIMIZATION.md','PHYSICS_AND_LEARNING_COMPARISON.md','MOTION_FORCE_MOMENT_TRADEOFF.md','FAILURE_MECHANISM_ANALYSIS.md']:write(name,(P/name).read_text()+'\n\n'+margin_summary+' 见 [固定回退](MOTION_MARGIN_BACKOFF.md)。')
    ppoanswer=ppo_text+' 结论以已评价mean和冻结状态为准。'
    if bm and strong:
        ppoanswer+=f" 已评价mean相对强固定降JF={strong['JF']-bm['JF']:.6f} N·s。"
    elif ppo is not None:ppoanswer+=' 没有已评价且原门合格的mean可供政策收益比较。'

    adaptation='没有少数连续患者运动的直接适应证据。参考响应研究显示可从因果控制历史构建候选模型，但17条历史、额外forward测试及工程开销完整计账；跨prefix结果也不是跨患者或两三次适应。'
    journal='已追加开始记录；最终关闭时会追加一次简洁结果记录。' if not (P/'audit/JOURNAL_END_RECORDING.json').exists() else '开始、结束记录均已append-only写入根长期日志；见 `audit/JOURNAL_END_RECORDING.json`。'
    answers=[
      f"**实际多久、多少物理尝试？** 当前累计{elapsed:.4f} h，物理START={count}，闭合账本新增native={native_used()}；结束精确时长以END为准。失败/partial/cold parent均计入，候选表不把父前缀当成新增独立sample。",
      '**实现哪些表示？** '+interface.split('\n\n')[0],
      '**自由度真正进入执行链？** '+original_gate+' issued/accepted/activated/rejected及applied torque、Human响应完整身份在原raw和接口审计。参考合法仍需真实motion合格。',
      '**找到新的完整合格运动？** '+headline,
      '**相对B/H150/强固定怎样？** 见配对表，JF下降与JM变化同时列出；新prefix只用该状态合格参照。',
      '**改善来自哪里？** '+attribution+' 初始单模式设计与原强固定的差异是新参数化及其实际执行方案的收益，后续同权限自适应改进才归于具体优化决策；最优组合没有完整逐项消融时，不作唯一因果归因。',
      '**上层快速优化减少物理尝试？** 见相同attempt/native预算曲线；A/B/C共同前16完整付费，PPO mean评价付费。单次轨迹仅支持本实例的效率比较，不能证明一般样本复杂度优势或全局最优。',
      f'**Learning是否改变有价值决策？** GP自适应已记录{changes}/{len(adaptive_learning)}次同池选择改变；冻结双动作实测见LEARNING_DECISION_ANALYSIS。'+primary_conclusion+cftext+response_interp+margin_summary,
      '**PPO有实质收益？** '+ppoanswer,
      '**Q/Value或其它方法？** Q/Value NOT_RUN，没有观察到本commit协议必须用多步价值解决的缺口。新增的是有符号参考响应模型及同数据传统成本响应对照，其实际成绩单独报告。'+structural_text,
      '**哪些失败根因已证实？** 固定时长certificate拒绝、逐关节终点缺锁触发原任务断言、粗代理reference输入/导数构造误差均有干预或重算证据；C19与PPO第9次任务另定位到原clearance包络差分跨分支触发的瞬时控制修正。其余native motion失败逐例保留，partial不排名。',
      '**哪些仍是猜测？** 最优轨迹相对完整旧18D的可达性/范围匹配、模态组合/跨状态闭环误差的完整归因、稀少历史的患者适应、可部署运动传感、一般Learning额外优势及是否接近物理最优仍未建立。',
      '**降force有其它代价？** '+pareto_text+' 最佳force方案JM、tracking、未滤波native v/a/jerk与更严格门敏感性见取舍报告；原门合格不是所有指标都改善。',
      f'**独立合法状态验证？** 已登记{len(cross)}个不同prefix，其中{begun_states}个开始评价、{complete_states}个已闭合全部登记候选。模型、候选、prefix与代码先冻结；同一名义Human，未验证跨患者。',
      '**少数重复患者适应？** '+adaptation,
      '**论文贡献判断怎样改变？** 可保留贡献是可执行表示及权限辨识、等物理预算决策评价、reference响应缺口的机制证据。一般Learning优越、少次患者自适应和临床/硬件结论需要另外实证；负结果不泛化为整个Learning方向失败。',
      '**下一步具体问题？** '+next_text,
      '**长期日志完成？** '+journal]
    write('REPORT.md','# iHEAR Lab — Autonomous Coordination & Learning Research v2\n\n状态：'+status+'；T0 `'+A['T0_utc']+'` UTC；硬截止 `'+A['hard_stop_utc']+'` UTC。本页由实际结果生成，终态、准确时长及owned PID清理以 `END.json` 为准。\n\n'+headline+'\n\n'+gain_table+'\n\n'+method_table+'\n\n'+'\n\n'.join(f'{i+1}. {s}' for i,s in enumerate(answers))+'\n\n独立审计：raw已完成'+str(raw.get('audited',0))+'/'+str(count)+'；原scorer重放='+scorer.get('status','NOT_RUN')+'（'+str(scorer.get('audited',0))+'条），PPO重放='+pporeplay.get('status','NOT_RUN')+'。审计为同一研究agent的独立代码路径，不冒充独立研究者。历史源码与Git保护、封包hash及全部PID终态见 `PACKAGE_VERIFICATION.json` / `END.json`。\n\n完整对照：[上层优化](UPPER_LEVEL_OPTIMIZATION.md)、[Learning决策](LEARNING_DECISION_ANALYSIS.md)、[PPO](PPO_STUDY.md)、[Force/Moment/Motion](MOTION_FORCE_MOMENT_TRADEOFF.md)、[独立合法状态](CROSS_STATE_RESULTS.md)、[学习与控制接口说明](LEARNING_CONTROL_INTERFACE_GUIDE.md)。\n\n已观察事实以原raw/scorer及独立重算为准；解释标明证据范围，未验证假设不作结果。没有Git修改命令、Stage2、最终Campaign或硬件实验；本轮STOP后不自动启动下一轮。')
    summary.update(report_enhanced_utc=utc(),best_new_modal=winner,methods=methods,common_budget=matched.get('fixed_attempts',[]),PPO_exploration=ppo_diagnosis,reference_response=response,pareto_joint_best=pareto,validation_states=len(cross),final_answer_items=answers)
    put('REPORT_SUMMARY.json',summary)
    put('audit/REPORT_EVIDENCE_BINDING.json',dict(utc=utc(),report_status=status,candidate_rows=len(allrows),physical_START=count,source='source/acl2_findings.py',facts_only_from_actual_artifacts=True,unexecuted_branches_not_fabricated=True,writing_style_references='No suitable writing references found in the returned results; follows user-provided scientific reporting requirements.'))
