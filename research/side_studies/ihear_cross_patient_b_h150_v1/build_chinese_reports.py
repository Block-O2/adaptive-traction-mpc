"""Write final Chinese synthesis from closed, independently checked observations only.

Offline: no simulator, controller, estimator or physics imports.
"""
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone

P = Path(__file__).resolve().parent

def load(name):
    return json.loads((P / name).read_text(encoding='utf-8'))

def fmt(value, n=3):
    if value is None: return 'NA'
    if isinstance(value, bool): return 'PASS' if value else 'FAIL'
    if isinstance(value, int): return str(value)
    if isinstance(value, (list, tuple)): return '[' + ', '.join(fmt(x,n) for x in value) + ']'
    if isinstance(value, (int, float)): return f'{value:.{n}f}'
    return str(value).replace('|', '\\|')

def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(fmt(x) for x in r)+' |' for r in rows])+'\n'

def names(rows):
    return '、'.join(r['patient_id'] for r in rows) or '无'

def main():
    stats=load('derived/REPORT_STATISTICS.json')
    sens=load('derived/CROSS_SENSITIVITY_SNAPSHOT.json')
    account=load('ATTEMPT_ACCOUNTING.json')
    history=load('audit/HISTORY_PRESERVATION.json')
    adm=load('PATIENT_ADMISSIBILITY_RESULTS.json')
    cohort=load('VIRTUAL_PATIENT_COHORT.json')
    assert stats['snapshot_status']=='FINAL_DISPATCH_FILE_PRESENT'
    assert stats['launcher_gate']['status']=='PASS' and not stats['read_errors']
    assert account['status']=='PASS' and history['status']=='PASS'
    rows=stats['rows']; sr={r['patient_id']:r for r in sens['rows']}; ix={r['patient_id']:r for r in rows}
    assert len(rows)==12 and all(r['final_complete_qualified_pair'] is not None for r in rows)
    valid=[r for r in rows if r['full_integral_comparison_valid']]
    qualified=[r for r in rows if r['final_complete_qualified_pair']]
    bqualified=[r for r in rows if r['qualified_B_reference']]
    failed=[r for r in rows if not r['final_complete_qualified_pair']]
    incomplete=[r for r in rows if not r['H150']['complete_task']]
    motionfail=[r for r in valid if r['motion_relative']=='FAIL']
    worseforce=[r for r in valid if r['gain_percent']<0]
    bothfail=[r for r in rows if r['B']['task']=='FAIL' and r['H150']['task']=='FAIL']
    safefail=[r['run_id'] for r in stats['arm_rows'] if r['absolute_safety']=='FAIL']
    static_n=sum(r.get('model_static_valid') is True for r in adm['rows'])
    commissioning_n=sum(r.get('own_commissioning_pipeline_reached_task_fork') is True for r in adm['rows'])
    modelbad=[r['patient_id'] for r in adm['rows'] if r.get('status')=='MODEL_NOT_ADMISSIBLE']
    labels={'P00':'原 Human 参考','P01':'段质量 ×0.8','P02':'段质量 ×1.2','P03':'段长 ×0.95','P04':'段长 ×1.05',
            'P05':'被动刚度 ×0.7','P06':'被动刚度 ×1.3','P07':'阻尼 ×0.7','P08':'阻尼 ×1.3',
            'P09':'短轻、高刚度低阻尼复合','P10':'长重、低刚度高阻尼复合','P11':'段比例不对称、高刚度高阻尼复合'}
    def axis(r):
        a=r['H150'];safe=a['absolute_safety']+('（仅已观察前缀）' if not a['complete_task'] else '')
        return f"{a['task']} / {safe} / {a['causal_execution']}"
    outcomes=table(['患者及变化','B 完整 J_F N·s','H150 完整 J_F N·s','降力 %','B 完整资格','H150 task / safety / execution','H150 motion','H150 完整资格'],
        [[r['patient_id']+' '+labels[r['patient_id']],r['B']['J_F_N_s'],r['H150']['J_F_N_s'],r['gain_percent'],r['qualified_B_reference'],axis(r),r['motion_relative'],r['final_complete_qualified_pair']] for r in rows])
    abort_table=table(['H150 患者','原始中止原因','已观察 TASK s','前缀 J_F N·s（非完整）'],[
        [r['patient_id'],r['H150']['abort_reason'],r['H150']['observed_prefix_duration_s'],r['H150']['observed_prefix_J_F_N_s']] for r in incomplete])
    subset_names={'all_valid_pairs':'全部有效完整配对（含运动失败）','new_patients_valid_pairs':'新患者有效完整配对（不含 P00）',
        'final_complete_qualified_pairs':'完整资格通过子集','new_patients_final_complete_qualified_pairs':'新患者完整资格通过子集'}
    averages=table(['统计子集','预注册分母','有效 n','等患者平均 %','范围 %','正 / 零 / 负'],[
        [subset_names[k],v['registered_denominator'],v['gain_denominator'],v['equal_patient_mean_gain_percent'],
         fmt(v['minimum_gain_percent'])+'–'+fmt(v['maximum_gain_percent']),f"{v['positive_gain_patients']} / {v['zero_gain_patients']} / {v['negative_gain_patients']}"] for k,v in stats['comparisons'].items()])
    trade=table(['患者','moment 积分 B → H150 N·m·s','moment 增幅 %','tracking RMS B → H150 [髋,膝]°','RETURN 下冲 B → H150 [髋,膝]°','膝 excursion 差 H−B °'],[
        [r['patient_id'],fmt(r['B']['moment_integral_Nm_s'])+' → '+fmt(r['H150']['moment_integral_Nm_s']),sr[r['patient_id']]['moment_change_percent'],
         fmt(r['B']['tracking_RMS_deg'])+' → '+fmt(r['H150']['tracking_RMS_deg']),
         fmt(r['B']['return_undershoot_from_actual_issued_reference_deg'])+' → '+fmt(r['H150']['return_undershoot_from_actual_issued_reference_deg']),
         sr[r['patient_id']]['H150_minus_B']['true_excursion_deg'][1] if sr[r['patient_id']]['H150_minus_B'] else None] for r in rows])
    moment_up=[r for r in valid if sr[r['patient_id']]['moment_change_percent']>0]
    knee_tracking_up=[r for r in valid if r['H150']['tracking_RMS_deg'][1]>r['B']['tracking_RMS_deg'][1]]
    knee_under_up=[r for r in valid if r['H150']['return_undershoot_from_actual_issued_reference_deg'][1]>r['B']['return_undershoot_from_actual_issued_reference_deg'][1]]
    mvalues=[sr[r['patient_id']]['moment_change_percent'] for r in valid]
    allstats=stats['comparisons']['all_valid_pairs']
    def group_line(ids):
        return '；'.join(pid+'：gain='+fmt(ix[pid]['gain_percent'])+('%' if ix[pid]['gain_percent'] is not None else '')+'，完整资格 '+('PASS' if ix[pid]['final_complete_qualified_pair'] else 'FAIL') for pid in ids)
    mass_delta=ix['P02']['gain_percent']-ix['P01']['gain_percent']
    length_delta=ix['P04']['gain_percent']-ix['P03']['gain_percent']
    damping_gains=[ix[pid]['gain_percent'] for pid in ['P07','P00','P08']]
    damping_span=max(damping_gains)-min(damping_gains)
    factor_motion=table(['患者','H/B 髋 tracking RMS °','H/B 膝 tracking RMS °','H/B 膝下冲 °','H/B native 膝速度峰 °/s','H/B native 膝加速度峰 °/s²'],[
        [pid]+[fmt(ix[pid]['H150'][key][j])+' / '+fmt(ix[pid]['B'][key][j]) if ix[pid]['H150'][key] is not None and ix[pid]['B'][key] is not None else 'NA'
        for key,j in [('tracking_RMS_deg',0),('tracking_RMS_deg',1),('return_undershoot_from_actual_issued_reference_deg',1),('native_velocity_peak_deg_s',1),('native_acceleration_peak_deg_s2',1)]]
        for pid in ['P01','P02','P03','P04','P05','P06','P07','P00','P08']])
    parameter_lines=(
        '- **质量**：【PHYSICAL_LEVEL1】'+group_line(['P01','P00','P02'])+'。这是两个段质量及其一致惯量的变化，总体重参数仍为 75 kg。不能从三点推断临床体重响应。\n'
        '- **腿长**：【PHYSICAL_LEVEL1】'+group_line(['P03','P00','P04'])+'。COM、膝位置、cuff 力臂和惯量随长度一起更新，属于形态一致变化的总效应。\n'
        '- **刚度**：【PHYSICAL_LEVEL1】'+group_line(['P05','P00','P06'])+'。低刚度暴露膝运动非劣失败，高刚度暴露终末参考适用前提失败；【INSUFFICIENT_EVIDENCE】高刚度 H150 未完成，不能宣称刚度越高、完整终末下冲越大。\n'
        '- **阻尼**：【PHYSICAL_LEVEL1】'+group_line(['P07','P00','P08'])+'。具体 tracking、真实下冲与制动相关统计见敏感性表；有限三个配置不能分离所有估计与控制路径的贡献。\n'
        '- **复合差异**：【PHYSICAL_LEVEL1】'+group_line(['P09','P10','P11'])+'。多参数同时改变，不能将其中任何失败单独归因于某一倍率。\n')
    report=f'''# iHEAR Lab：冻结 B/H150 跨虚拟患者研究，工作包 A

【PHYSICAL_LEVEL1】本轮完成 12 个预注册患者配置的 P0 对照，B 完整资格 {len(bqualified)}/12，H150 完整资格 {len(qualified)}/12。有效完整配对 {len(valid)}/12 的等患者平均降力为 {fmt(allstats['equal_patient_mean_gain_percent'])}%，范围 {fmt(allstats['minimum_gain_percent'])}–{fmt(allstats['maximum_gain_percent'])}%。未通过患者全部保留：{names(failed)}。这些结果表明 H150 的收益可转移到多个新 plant，但固定协调并非所有患者均适用。

本报告最高证据为 MuJoCo 物理仿真 `PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION`，没有统计显著性、临床人群或硬件结论。`MODEL_STATIC_CHECK` 指模型/几何检查；`MODEL_IMPLEMENTATION_FACT` 指实际源码结构；`MECHANISTIC_HYPOTHESIS` 指未用组件消融证实的解释；`INSUFFICIENT_EVIDENCE` 指本轮无法判断；`RESEARCH_RECOMMENDATION` 指未来研究建议。

## 研究合同与读数方式

【MODEL_IMPLEMENTATION_FACT】P0 冻结原 B/H150 算法、deployable prior、原 commissioning-only 估计、18D/T/D/ER/H150 参数、目标、5 ms 量化、证书、admission、allocator 和所有原资格阈值。不同患者合法 commissioning 可产生不同 belief；没有将真实患者参数直接喂给控制器。P1 仅交付协议，没有运行。

每患者从自身 cold initialization 与物理 commissioning 出发，在同一患者的完整 live 父状态串行 fork B/H150。跨患者不复制状态。所有患者使用同一 W1/D01R 合法 prefix；B 是该 prefix 条件下的原 B，不能与零 prefix 开发条件 B 混称。完整 J_F 包含共有 TASK 前缀，后续相同 RETURN intent 的入口状态可因两臂历史不同而分离。P00 与历史 W1 trace/native/receipt 科学字段精确复现通过。

预注册顺序、实际段质量实现及原审计草案与执行合同的对应关系见 [合同采用记录](CONTRACT_ADOPTION.md)。历史冻结源码仅在新副本中重定位路径；新 harness 供给隔离 patient plant 并保留失败。离线评价将原硬编码名义 case 绑定到本次实际患者，同时解除“先合格才可计算指标”的提升断言以保存失败的真实积分；没有改动指标公式、原资格门或正式控制算法。完整原始评价、独立复算及这些适配的来源均可追溯。

力按原 5 ms 左积分；真实 Human 导数按原 0.25 ms native 口径；SG 仅辅助诊断。每患者 gain=(J_B−J_H)/J_B。NA 表示不可评价，绝不是零收益。数组顺序均为 [髋,膝]。完整数值、实际 phase 时间、force/moment peak、torque、clearance 和原安全逐项门见 [完整指标表](analysis/REPORT_TABLES.md)、[逐臂原始评价](reports/) 与 [结果 JSON](CROSS_PATIENT_EXPERIMENT_RESULTS.json)。

【PHYSICAL_LEVEL1】36 次运行的扭矩分解与 allocator wrench 在每个正时长 TASK 执行区间都有有限值，并与实际 applied receipt 对齐；六个可选遥测字段仅在最后无后续区间的边界行为空。原汇总直接取 max/RMS 因该行传播为空，原字节保留；另附 [遥测覆盖与有效执行区间统计](audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json)，提供有限值计数、缺失位置、来源哈希、区间峰值与按区间时长加权的 RMS。没有删除内部缺失点来制造完整性，中止臂仍仅覆盖自身前缀。

## 1. 实际建立多少个物理合法患者？

【MODEL_STATIC_CHECK / PHYSICAL_LEVEL1】12 个预注册身份（1 个原参考、11 个新参数配置），静态模型/质量/惯量/装配检查 {static_n}/12；到达自身 commissioning 后合法 TASK fork {commissioning_n}/12；B 完整任务、安全、执行资格 {len(bqualified)}/12；有效完整 B/H150 积分配对 {len(valid)}/12。模型合法与 H150 成功是不同分母。原 commissioning/admission 及后续真实 B 任务证据可复核，但本轮没有另创独立“commissioning 稳定性认证”门。

## 2. 哪些是模型不可达，哪些是控制失败？

【PHYSICAL_LEVEL1】`MODEL_NOT_ADMISSIBLE`：{'、'.join(modelbad) or '无'}。两臂均 task FAIL：{names(bothfail)}。H150 未完成任务：{names(incomplete)}；完整任务但原相对运动合同失败：{names(motionfail)}。B 在同患者的通过结果说明这些已观察失败不能用“该患者模型不可达”解释；这不证明 B 在未测试状态也总能完成。绝对安全 FAIL 记录：{'、'.join(safefail) or '无'}；中止臂的安全 PASS 仅覆盖已观察前缀，不能写成完整任务安全通过。

{abort_table}
这些原始失败保留，没有修改 planner 条件或重跑覆盖。`KNEE_REFERENCE_MUST_BE_CONSTANT` 检查的是拟调度膝参考条件，不是要求真实膝速度为零。发生该失败时，完整 H150 组合中的末端髋时长意图尚未成功执行；不能把较短前缀的低 J_F 宣传为降力成果。

## 3. 各患者 B 与 H150 的完整资格？

【PHYSICAL_LEVEL1】B 完整资格基于绝对 task/safety/execution、完整积分及原 launcher COMPLETE；B/B 相对 motion 不用于证明安全。H150 完整资格还要求有效匹配 B、原相对运动/交互门、意图实际执行和独立证据。所有 12 行如下。

{outcomes}
## 4. 跨患者平均、范围与逐行降力是多少？

【PHYSICAL_LEVEL1】上表逐行收益只比较同患者 B/H150。下表是患者等权均值，没有按轨迹点数加权，也没有用不同患者的绝对 J_F 排名。P00 单列参考身份，并另报排除它的新患者统计。不完整患者不进入 gain 均值，但仍留在预注册资格分母中。

{averages}
完整资格子集均值描述已通过的条件，不是预注册全队列的无条件成功率。运动失败但积分完整的患者仍纳入“全部有效完整配对”，其数值改善不能称为合格控制收益。

## 5. 哪些患者降力却 motion 失败？

【PHYSICAL_LEVEL1】{names([r for r in motionfail if r['gain_percent']>0])}。P05 的 gain={fmt(ix['P05']['gain_percent'])}%，但膝速度最大值 H/B=1.118697、膝加速度 p95 H/B=1.113201，均超过 1.10；膝 excursion 增量 0.712989°，超过 0.5°。其 task、绝对 safety 和 causal/execution 仍通过，不能混称为安全门失败。H 膝速度峰及较高加速度负担出现在 OUTBOUND，因此不能把所有失败归因于 RETURN5 髋终末延时。其他运动失败的逐项来源见 [失败机制报告](FAILURE_MECHANISM_REPORT.md) 与资格 JSON。

P08 的 gain={fmt(ix['P08']['gain_percent'])}%，唯一失败项是膝 excursion：B 111.153018° → H150 111.681162°，增加 0.528144°，超过原 0.5° 门。其原速度、加速度和 jerk 主要负担门通过。P08 的 H150 绝对膝下冲比 P00 略小，但其匹配 B 改善更多，故相对 excursion 仍失败；不能写成“高阻尼使 H150 绝对下冲增加”。

## 6. 哪些患者 H150 比 B 更差？

【PHYSICAL_LEVEL1】完整 J_F 负收益患者：{names(worseforce)}。但完整资格更差的患者为 {names(failed)}，不完整臂不具备可比较的完整 force gain。即使完整资格通过，代价也可能上升：有效配对中 moment 积分增加 {len(moment_up)}/{len(valid)}，膝 tracking RMS 增加 {len(knee_tracking_up)}/{len(valid)}，膝局部 RETURN 下冲增加 {len(knee_under_up)}/{len(valid)}。motion PASS 表示原合同容许范围内，不表示每个指标均改善。

## 7. 腿长、质量、刚度与阻尼有什么影响？

{parameter_lines}
【PHYSICAL_LEVEL1】在本次取点中，质量从 0.8 到 1.2 倍时 gain 增加 {fmt(mass_delta)} 个百分点；形态一致长度从 0.95 到 1.05 倍时 gain 变化 {fmt(length_delta)} 个百分点；三个阻尼点的 gain 全范围仅 {fmt(damping_span)} 个百分点。降力幅度接近不代表真实 tracking/制动完全相同。P09 在同为 1.3 倍刚度时通过，而 P06 失败，说明单一刚度阈值不足以概括这个队列的适用边界。

完整数值及三个单因素参考点的描述性斜率见 [敏感性分析](PATIENT_SENSITIVITY_ANALYSIS.md)。这些倍率是预注册工程敏感性范围，没有文献或人群采样依据支持将其称作临床分布。

## 8. 终末下冲与 moment 代价如何变化？

【PHYSICAL_LEVEL1】下冲相对于各臂实际签发的终末参考，不直接以名义 [5°,10°] 替代。最终 endpoint 误差、局部极小值下冲和全程 excursion 是不同量。完整配对的 moment 积分增幅范围为 {fmt(min(mvalues))}–{fmt(max(mvalues))}%。P00 膝下冲从 0.577911° 到 1.201029°，但 excursion 增量只有 0.474247°并通过原门，原因包括 OUTBOUND 膝 overshoot 同时下降；不能据 excursion PASS 推断终末下冲没有增加。

{trade}
P06、P10 的 moment/运动完整指标保留 NA，已观察前缀另存原始证据，不和完整任务混算。真实局部时间轴与物理耦合解释见失败报告；原接口有限刚度、髋膝惯性/重力耦合支持机制假说，但本轮没有独立改变 H150 组件来确定唯一原因。

## 9. 原控制模型失配是否是主要障碍？

【INSUFFICIENT_EVIDENCE】尚不能确认。原冻结估计器在患者自己的 commissioning 中更新 geometry/beta/residual，本实验并不是把参考患者的数值模型强行固定在所有人上。离线审计发现部分 beta 与物理真值有差异，但 beta 误差不能替代整体预测误差，因为还有 residual。未运行同时帮助两臂的 P1，也未做 matched-state 模型/组件消融，因此不能认定失配是主因，或宣称已知模型会消除 P05/P06 等边界。

## 10. H150 的主要优点与真实适用边界？

【PHYSICAL_LEVEL1】优点是在多个新 plant 上保持小幅完整降力，完整资格通过的患者为 {names(qualified)}。边界包括被动力学变化造成的运动负担和参考可用性失败、moment/膝 tracking 代价，以及对合法入口状态的条件依赖。本轮只覆盖这些参数、这条 W1 prefix、原任务和原执行合同；没有覆盖所有患者、所有 prefix、完整参数连续域或 host realtime。历史同 Human 8/11 合法 prefix 结果不并入本轮跨患者分母。

## 11. 这些数据能否用于未来 Learning？

【PHYSICAL_LEVEL1 / RESEARCH_RECOMMENDATION】可以作为冻结策略对照、失败分类和受约束协调设计的数据。已保存 PATIENT_ID、合法因果 STATE、实际 ACTION/执行意图、OUTCOME 和独立 TRUTH；原始 case、source、native/receipt 及配对身份都有哈希绑定。见 [schema](LEARNING_DATA_SCHEMA.json) 和 [manifest](LEARNING_DATA_MANIFEST.json)。

需要遵守时间与单位语义：紧凑状态 q/dq 为物理 rad/rad·s⁻¹，legacy 55D 状态为原归一化向量；request/handoff reference 的误差不一定是当前已发出 reference 的同步 tracking。新增因果对齐字段独立保存。`ESCAPE_ADMITTED` 是证书事件，不等于执行回退；`TRACK` receipt 也可能跟踪 fallback reference，实际回退须读原 raw event。P06 的 partial 证据归属可以通过，而任务/策略资格仍失败。

P00–P08 为未来开发身份，P09–P11 为未来拟合保留身份；同患者的全部 prefix/轨迹必须一起划分。后三个身份的本轮结局已公开，若未来方法设计利用这些结果，需要另建未用于设计的新确认患者。当前只有 B/H150 两种冻结策略及有限意图覆盖，不能当作已经覆盖连续动作空间，更不代表 Learning 已经成功。

## 12. Learning 最应学习什么差异与动作？

【RESEARCH_RECOMMENDATION】优先学习“何种状态与个体估计下应启用、延后或禁用某种协调”。候选状态包括合法估计的几何/cuff 力臂、动力学组合系数、残差与可信度，加上 q/dq、phase/elapsed、tracking、近期 force/moment、source age、执行/准入状态和终末参考适用性。真实生成质量、刚度、native truth 与未来结局只能作离线标签，不能泄漏到在线 STATE。

动作以原 B 回退选择、T/D/ER/H 类有界时序/小姿态意图为研究对象，仍经过原证书、current-state admission、splice、torque 和 fallback。目标必须同时约束任务、安全、运动、moment 与 tracking，不能只奖励降低 J_F。新增局部下冲目标应在下一轮前瞻性预注册，不回写本轮资格门。

## 13. 继续调 H150，还是条件协调学习？

【RESEARCH_RECOMMENDATION】保留 B/H150 为冻结对照，优先准备状态/个体条件协调研究。少量组件诊断可用于明确动作语义与状态充分性，但不应在本队列反复调一组通用常数来提高已观察通过率。该建议不授权或触发训练、P1 或工作包 B；详见 [下一阶段决策](NEXT_RESEARCH_DECISION.md)。

## 证据闭合与交付

独立离线复核覆盖完整 5 ms 左积分、phase 闭合、native 运动统计、同患者父状态与模型身份、receipt/command/native 归属以及所有已观察失败。P06、P10 原始任务中止，独立部分证据核验不提升其任务资格。START={account['START_count']}，END={account['END_count']}，上限 80；预算及串行记账通过，继承前缀不重复计作新增 physics。

历史与 Git 原状的逐字节复核通过，详情见 `audit/HISTORY_PRESERVATION.json`；正式源码和参数冻结身份由 `EXECUTION_CODE_MANIFEST.json` 与最终 package verification 检查。最终 `PACKAGE_VERIFICATION.json` / `PACKAGE_CLOSED.json` 生成后才构成封包完成；它们记录所有 owned 进程退出、完整清单和 STOP。完整 raw/native 数据在 canonical WSL 包中，Windows 同名目录是审阅镜像，位置与范围见 [复核入口](REPRODUCIBILITY.md)。

没有训练、参数搜索、P1、Git 提交/推送/合并或工作包 B。最终 STOP。
'''
    sensitivity=f'''# 跨患者敏感性分析

【PHYSICAL_LEVEL1】本表只分析预注册 P0 冻结 B/H150，在同患者匹配 B 上计算 gain。12 个身份全部保留，完整有效配对 {len(valid)}，完整资格通过 {len(qualified)}。参数倍率是探索性工程范围，不是临床分布；不做显著性检验或连续域外推。实际 case、XML、COM/惯量和 cuff 坐标见 `VIRTUAL_PATIENT_COHORT.json`、`STATIC_PATIENT_AUDIT.json` 和 `derived/CROSS_SENSITIVITY_SNAPSHOT.json`。

## 单因素覆盖与结论

{parameter_lines}
质量变化保持段长/COM 比例不变，以 m(rL)² 同步改变惯量；长度变化则同时更新 body geometry、膝 joint 位置、COM、惯量和 cuff 附着。它们都不是“只改一个动力学常数”的孤立因果实验。P11 采用独立大腿/小腿倍率，不能用总腿质量一个数完整描述其差异。

## 配对结果与分母

{outcomes}
{averages}
## 力、力矩、跟踪与终末运动

{trade}
【PHYSICAL_LEVEL1】有效完整配对中 moment 增加 {len(moment_up)}/{len(valid)}，膝 tracking RMS 增加 {len(knee_tracking_up)}/{len(valid)}，膝 RETURN 下冲增加 {len(knee_under_up)}/{len(valid)}。应把 force 降低和这些代价一起解释；“完整资格通过”不等于各项均优于 B。下冲取实际签发参考，名义目标偏差另存 JSON，不能混用。

以下补充各单因素真实运动读数，单元格顺序为 H150 / B；native 加速度峰是原始离线导数，不替代原安全监测加速度门。

{factor_motion}
质量两端的 gain 差为 {fmt(mass_delta)} 个百分点，长度两端差为 {fmt(length_delta)} 个百分点，三个阻尼点全范围为 {fmt(damping_span)} 个百分点。对这些小幅差异不宣称统计显著性。高刚度复合患者 P09 与高刚度单因素 P06 的资格不同，阻止了“刚度达到 1.3 即统一失效”的阈值解释。

## 十项敏感性问题

1. **质量是否影响降力幅度？**【PHYSICAL_LEVEL1】P01/P00/P02 的 gain 为 {fmt(ix['P01']['gain_percent'])}/{fmt(ix['P00']['gain_percent'])}/{fmt(ix['P02']['gain_percent'])}%。这是该质量与一致惯量变化下的三点描述，不证明一般线性规律。
2. **腿长是否影响 cuff 映射和真实运动？**【MODEL_IMPLEMENTATION_FACT / PHYSICAL_LEVEL1】cuff 距膝始终为小腿长的 0.72，P03/P04 随小腿长改变；各自 cold commissioning 得到合法 belief、同患者共享后对照。真实 motion/tracking 不完全相同，具体数值如表；没有用 reference 代替真实运动。
3. **高刚度是否加剧终末下冲？**【INSUFFICIENT_EVIDENCE】P06 H150 在 RETURN 前提失败处中止，缺完整终末数据；复合高刚度病例同时改变其他参数。现有证据支持刚度变化暴露适用性边界，不支持单调的完整下冲结论。
4. **阻尼是否影响 tracking/制动？**【PHYSICAL_LEVEL1】P07/P00/P08 逐关节 tracking 和下冲不同，原始速度、加速度、jerk、TV 和 phase 指标全部保存。它们可以描述制动响应变化；【MECHANISTIC_HYPOTHESIS】阻尼变化可能经真实阻力和估计/规划共同改变响应，不能从三点隔离各路径。
5. **哪些 B 通过、H150 失败？**【PHYSICAL_LEVEL1】{names(failed)}。具体多轴失败见资格表；部分任务失败不归类为模型无效。
6. **哪些两臂均失败？**【PHYSICAL_LEVEL1】{names(bothfail)}。这只是已测配置、prefix 与任务的观察结果。
7. **哪些 H150 更差？**【PHYSICAL_LEVEL1】完整 force 负收益：{names(worseforce)}；整体资格下降：{names(failed)}。moment、膝 tracking 和下冲的恶化另外记录，不因 gain 正值而忽略。
8. **哪些降力且 motion/完整资格通过？**【PHYSICAL_LEVEL1】{names([r for r in qualified if r['gain_percent']>0])}。其余完整降力但 motion 失败：{names([r for r in motionfail if r['gain_percent']>0])}。
9. **是否有 force–moment–tracking 权衡？**【PHYSICAL_LEVEL1】存在本队列内的配对代价权衡，如上表；没有证明这些代价是降力必然代价或不可通过其他控制方式改善。
10. **是否与历史状态依赖失败有相似机制？**【MECHANISTIC_HYPOTHESIS】原髋膝惯性、重力和有限刚度 cuff 耦合、终末物理速度与参考 plateau 的不一致可以解释相似现象；但 P05 的超限还出现在 OUTBOUND，P06 又是参考前提失败。完整组合比较不足以把历史/本轮所有失败统一归因于同一组件。历史 8/11 prefix 结果不参与本轮统计。

## 物理读数的解释限制

所有完整任务的实际 OUTBOUND/HOLD/RETURN 时间及剂量必须读取原记录；不能将名义 HOLD 时间替代真实 phase 边界。完整 phase J_F 使用原 5 ms 区间裁剪并与总积分闭合，导数来自 0.25 ms native 序列。安全门中的原因果监测加速度与离线 native 导数是不同口径，分别保留，未互换门槛。

P0 保留原 commissioning-only 估计，因此不同患者的 belief 数值并不固定。合法在线估计、模型残差、历史状态和协调请求共同决定结果；没有 P1 或同入口消融，不能用生成参数与结果相关就宣称某种模型失配为主要原因。单一确定性 seed 不支持噪声鲁棒性或总体统计推断。

P09–P11 在本轮是预注册复合压力测试，并为未来拟合保留身份；公开的结局如果影响后续设计，就必须增设新确认身份，不能继续称为完全未见测试。下一阶段建议见 `NEXT_RESEARCH_DECISION.md`；本轮无参数搜索和 Learning。
'''
    (P/'REPORT.md').write_text(report,encoding='utf-8')
    (P/'PATIENT_SENSITIVITY_ANALYSIS.md').write_text(sensitivity,encoding='utf-8')
    sources=['derived/REPORT_STATISTICS.json','derived/CROSS_SENSITIVITY_SNAPSHOT.json','ATTEMPT_ACCOUNTING.json','audit/HISTORY_PRESERVATION.json','PATIENT_ADMISSIBILITY_RESULTS.json','VIRTUAL_PATIENT_COHORT.json']
    binding={'schema':'CHINESE_SYNTHESIS_SOURCE_BINDING_V1','generated_utc':datetime.now(timezone.utc).isoformat(),'physics_started':0,
        'inputs':{n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in sources},
        'outputs':{n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['REPORT.md','PATIENT_SENSITIVITY_ANALYSIS.md']}}
    (P/'audit/CHINESE_REPORT_BINDING.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CHINESE_REPORTS_WRITTEN',len(valid),len(qualified),'ZERO_PHYSICS')

if __name__=='__main__': main()
