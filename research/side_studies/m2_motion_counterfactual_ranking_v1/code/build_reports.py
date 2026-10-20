from common import *
import collections
def n(v): return 'NOT_EVALUABLE' if v is None else f'{v:.6f}'
def lines(p,needle):
 return [i for i,s in enumerate(Path(p).read_text().splitlines(),1) if needle in s]
def main():
 ranking=load(OUT/'RANKING_FEASIBILITY.json');ds=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json');rows=ds['historical_rows'];motion=load(OUT/'MOTION_DOSE_HOST_AUDIT.json');protocol=load(OUT/'EXPERIMENT_PROTOCOL.json');mp=load(OUT/'MOTION_QUALITY_PROTOCOL.json')
 proofs=[]
 for p,needle in [(MATRIX/'code/native_data.py','os.fork()'),(MATRIX/'code/interfaces.py','self.count[phase]+=1'),(MATRIX/'code/interfaces.py','self.table['),(MATRIX/'deps/fork_core.py','sha256(x.tobytes())'),(ROOT/'m2_host_generalization_attribution_v1/code/q_first_method.py','self.table=used.copy()'),(ROOT/'m2_host_generalization_attribution_v1/code/host_adapter.py','age_before>deadline'),(ROOT/'m2_host_generalization_attribution_v1/code/host_adapter.py','bridge_ms=40')]:proofs.append(dict(path=str(p),sha256=sha(p),lines=lines(p,needle),needle=needle))
 value=dict(status='CONTRACTS_DISTINCT_COMPARATIVE_VALUE_NOT_EVALUABLE',V_commit=dict(definition='Remaining native force integral from a complete live scientific fork; use the full masked K3 table at successive original B-owned request counts, certify/recompute each physical segment, original rejection/fallback, zero after finite table slots. Underlying B still replans segments; commitment means residual table is fixed.',label='native-certified-committed-K3-suffix-v1',actual_samples=80,restorable_now=False,execution_mode='SCIENTIFIC_SIMULATION'),V_replan=dict(definition='Execute a specified initial candidate intervention, then let the explicitly frozen continuation policy respond at subsequent B-owned requests, with its candidate regeneration/zero-residual choice, carry and issued counts, native admission, 40ms bridge and100ms lifecycle under a causal execution clock.',initial_intervention_unit='Must specify one current K3 segment versus full table suffix. Existing committed labels intervene on full future table; they cannot be relabelled as current-segment-plus-zero-B.',continuation='Original zero-residual B and frozen M2 reselection are separate possible policies. Observed host M2 regenerates candidates and replaces table/carry; zero B resets future residual. Specify which policy when collecting future labels.',same_state_paired_labels=0,measured_value_difference_N_s=None,ranking_difference='NOT_EVALUABLE'),clock_and_carry=dict(scientific='Physical integration is paused during computation; source/receipt/activation simulation versions checked, host wall plan_age may FAIL and realtime mode-aware result isN/A.',host='Physical motion continues; late proposal can use prior carry; source age and native admission/expiry determine actual activation. Proposal selection is not command ownership.'),source_evidence=proofs,supervision_recommendation='First keep V_commit explicitly named as a constrained finite-table ranking baseline with dense outcomes and valid full-state forks. Do not mix it with host policy value. Before a future Q is claimed to optimize repeated host decisions, measure current-intervention plus an explicitly frozen V_replan continuation at the same complete state. This package authorizes no training and supports no deployment promotion.',equivalence='Not established; intervention/continuation/clock contracts differ. No numerical difference can be inferred from unmatched historical host pairs.',next_primary_direction='D')
 save('COMMITTED_VS_REPLANNING_VALUE.json',value)
 md('COMMITTED_VS_REPLANNING_VALUE.md',f'''# Committed 与重复规划的价值合同

**合同不同；同状态数值差及排序差 NOT_EVALUABLE。** 不能将已有80条remaining cost称为真实host-replanning policy value。

`V_commit(s,p)` 是原进程内完整fork状态开始、执行完整masked K3表的剩余force integral。`TableInterface.choose`在每个原B请求按OUTBOUND/RETURN count取当前slot；后续继续消耗同一表，slot5后zero。B仍重新构造并认证各段schedule、保留拒绝/fallback及HOLD/terminal规则。因此committed是固定residual后缀，不是整个物理command开环、不重新规划。

`V_replan(s,p)` 必须明示p的干预单位，以及随后冻结的策略。当前slot之后zero-residual B，与随后继续Frozen M2候选生成/Q排序，是不同continuation。两者都由B负责本地重复规划/认证；不能因都调用B就把价值合同视为相同。原标签p影响后续所有未issued slots，不是当前slot之后立即zero-B。

Frozen host M2的`QFirstInterface.choose`重新生成candidate、计算Q、做原生certification，更新table/carry/count；`host_adapter`在真实source年龄超时后可能执行prior carry，保留40ms bridge、100ms native lifecycle与current-state admission。Scientific fork数据的物理时钟在计算期间不推进，保留simulation-version因果检查；原wall plan_age失败仍存在。这会改变后续状态及动作机会，但本轮没有相同完整状态下两合同的对照，差值范围、方向、排序变化均不可测。

不能拿历史全任务host配对与另一个prefix/state的committed分支相减。0个可恢复父状态、0个同state V_replan配对；本轮新增物理/host运行0。没有制造模拟host时钟或跳过原生admission来补表。

下一代Q首先应保持单一、清楚命名的 **V_commit约束有限表排序目标** 作为探索性参考，记录force与真实运动/剂量等完整标签；当前结果不支持开训v2。若要声明改善重复host策略价值，必须先建立同完整state、明确当前干预单位和冻结continuation的V_replan标签及合同转移证据。即使commit预测误差小，也只能支持有限候选committed排序，不支持online personalization、跨Human泛化或临床结论。

代码路径、准确行号、hash在JSON的source_evidence；保留原执行合同，不修FAST、不改R2/strict55。
''')
 profiletable=table(['研究档位','速度/加速度分布倍率','excursion绝对变化°','累计角位移倍率','阶段/终点变化°','phase轨迹形状最大差°'],[[p['id'],p['burden_ratio'],p['excursion_delta_deg'],p['cumulative_ratio'],p['endpoint_delta_deg'],p['phase_shape_delta_deg']] for p in mp['research_layer']['profiles']])
 hostrows=[]
 for r in motion['pairs']:hostrows.append([r['B_id'],n(r['excursion_delta_deg'][1]),n(r['cumulative_travel_delta_deg'][1]),n(r['endpoint_delta_deg'][1]),n(r['J_F_delta_N_s'])])
 md('MOTION_QUALITY_PROTOCOL.md',f'''# 研究级真实运动质量与任务公平性协议 v1

此协议是已暴露历史数据上的研究敏感性设置，**没有临床容差或舒适性资格**。阈值在本包derived候选分析前冻结；完整原八组B参考分布及hash见FROZEN_B_REFERENCE_DISTRIBUTION.json。不得按结果改变容差，也不把参考分布当作患者标准。

第一层必须满足原物理安全/ROM、任务COMPLETE、原tracking资格、原目标/时间可比性及原生合法执行。原force/moment peak与clearance下限等安全条件全部复用，未猜造新原生门限。历史SCI物理/因果有效，与真实host生命周期资格分列。

第二层关注真实人体dq、加速度peak/p95/RMS、启停/反向窗口、jerk及数值敏感性、excursion和完整任务J_F。速度使用native真dq；加速度为实际time上的gradient(edge_order=2)，jerk再次gradient；跨phase计算，不删端点。导出raw与3阶Savitzky–Golay5/21节点（约1.25/5.25ms）敏感性。phase启停窗口±100ms、速度反转±20ms；0.5deg/s反转事件检测只用于排除零速抖动。参考平滑性、robot/cuff运动不能代替人体运动。

{profiletable}

三档共同允许完整任务时长绝对差≤0.1s。核心运动筛查要求hip/knee速度max/p95/RMS与加速度p95/RMS在同档倍率内；加速度peak另报，不把数值尖峰自动变成新临床硬门。jerk p95/RMS同档筛查单独保存为optional，raw/filter所有值保留，未要求所有次要指标Pareto dominance。

任务运动剂量包括实际peak-to-peak excursion、累计abs Δq与积分abs dq、phase端点和最终q/dq。每phase以原transition物理边界、时间进度0–1对齐201点，比较真实q最大差。这是较严格的研究级轨迹可比性筛查；K3本来会改变协调轨迹，所以必须同时报告拆分gate诊断，不能将该形状容差天然当作临床或唯一科学公平性规则。分支筛查使用完整TASK运动/剂量，同snapshot zero-residual suffix作参考（既有prefix不撤销）；后缀窗口另行导出。完整host配对使用其成对B arm。

第三层允许有界补偿：moment integral≤1.25×B，true-reference RMS tracking每关节增加≤0.5°，但不得覆盖原硬资格失败。分支moment比较使用remaining integral，完整host比较使用full-task integral，二者另存完整数值。moment不是momentum。没有新加权reward。

所有基于未来motion标签的筛查均为离线有限候选参考，不能部署；没有预测motion admission模型。新增branch必须有可恢复完整状态、合法native执行、可信高分辨率trace才可评估。此次仅历史native约0.25ms运动已可恢复；原contact/tracking约5ms及原native scorer峰值分别标明。

## 上一轮knee excursion增加的含义

{table(['B运行','Δknee excursion°','Δ累计knee角位移°','Δ最终knee位置°','Δ完整任务J_F N·s'],hostrows)}

增加的幅度伴随更大的累计knee角位移：{n(min(r['cumulative_travel_delta_deg'][1] for r in motion['pairs']))}–{n(max(r['cumulative_travel_delta_deg'][1] for r in motion['pairs']))}°。终点偏移幅度最大{n(max(abs(r['endpoint_delta_deg'][1]) for r in motion['pairs']))}°，并非等于1.109–2.834°的excursion变化。它主要是中途实际轨迹/过冲/反转和累计运动量变化；任务原目标与完成条件不变，也不意味着真实运动剂量相同。没有把J_F按excursion归一化掩盖差异，不能推断临床舒适或伤害。

完整配对均不通过本轮三档完整研究profile；这是本轮新研究筛查结果，不撤销历史安全PASS或force收益，不改历史R2/strict55失败。
''')
 summ=ranking['summary'];ranktable=table(['候选筛查','snapshot','有效候选行','有force降低机会的state','snapshot均值fixed regret N·s','按父来源等权均值 N·s'],[[k,v['snapshots'],v['eligible_rows'],v['positive_force_opportunity_snapshots'],n(v['mean_snapshot_fixed_regret_N_s']),n(v['equal_parent_mean_fixed_regret_N_s'])] for k,v in summ.items()])
 components=table(['档位','诊断gate组合','有效候选行','获益state','平均zero−best N·s'],[[r['profile'],r['gate_family'],r['eligible_rows'],r['force_opportunity_snapshots'],n(r['mean_zero_minus_best_N_s'])] for r in ranking['constraint_component_sensitivity'] if r['gate_family'] in ['burden_only','burden_and_dose_without_phase_shape','full_profile']])
 snapdetail=table(['父来源','phase/task s','候选数','zero−best N·s','fixed regret N·s','best与第二名差 N·s'],[[s['parent'],s['phase']+'/'+n(s['task_s']),s['regimes']['original_physical_task']['count'],n(s['regimes']['original_physical_task']['zero_minus_best_N_s']),n(s['regimes']['original_physical_task']['fixed_regret_N_s']),n(s['regimes']['original_physical_task']['score_margin_N_s'])] for s in ranking['snapshots']])
 matched=[]
 for s in ranking['matched_fixed_candidate_strata']:
  costs=[g['regimes']['unconstrained']['fixed_regret_N_s'] for g in s['snapshots']]
  matched.append([s['phase'],len(s['common_exact_plans']),len(s['snapshots']),len(s['independent_parent_groups']),','.join(sorted(set(g['regimes']['unconstrained']['best_source'] for g in s['snapshots']))),n(max(costs))])
 md('RANKING_FEASIBILITY.md',f'''# 状态相关排序可行性

**未观察到固定候选/mask/carry层中的排序反转；不能据此证明所有状态排序恒定。** 完整运动profile三档均只保留zero suffix。已有数据不能支持Neural Q v2训练或部署。

## 同状态有限候选结果

{ranktable}

80行来自13个exact snapshot、4个source parent group（train2、validation1、历史诊断test1）、同一已暴露Human仿真；round4 causal120公共上下文仅12个fingerprint。不同parent名字和完整snapshot hash不保证独立人体或统计独立性。train/dev已参与旧linear拟合，13state合并regret是描述性回顾，不能作为新测试成绩。历史test2state均值regret仍为{n(ranking['split_regret']['test']['mean_fixed_regret_N_s'])}，与上一包1.6207一致。合并0.249333与按父来源等权0.405167使用不同分母，均明确保存；唯一非零snapshot损失3.241335，RETURN四个snapshot损失均0。

{snapdetail}

C只是在已完成、合法、已标注的有限候选中best，不是全局oracle；3条原失败仍保留，没有低成本标签化。zero suffix在fork前的既有prefix不撤销，不能当作从任务初始完全zero的B。A=同snapshot zero suffix；B=frozen linear在同合法池的固定masked排序；C=finite best。

不加研究motion约束时，13/13状态均存在force降低候选，平均remaining zero−best={n(summ['original_physical_task']['mean_zero_minus_best_N_s'])}N·s；仅在该小型有限池中额外state oracle相对fixed的均值机会为{n(summ['original_physical_task']['mean_snapshot_fixed_regret_N_s'])}N·s。加入完整profile后候选80→13、force机会13→0、oracle额外机会0。0 regret在仅一个可行候选时是平凡结果，不证明学习能力。

## 平顺性与任务剂量的不同作用

{components}

拆分诊断保持原阈值，未放宽完整profile。10%/25%运动负担容差单独仍允许5/6个snapshot有force机会；运动负担加excursion/累计角位移/端点/时长、暂不纳入phase形状的诊断，仍允许4/5个snapshot获益，平均机会4.351452/6.210357N·s。严格无负担增加则无获益。完整profile里的0.5/1/2° phase形状筛查排除全部67个非zero候选，是关键限制。因此“当前profile无合格获益”不能升级为“K3空间无解”；轨迹形状是否应是任务硬可比性标准尚需科学依据，不能为了保留force收益在本包改阈值。

## 真正相同计划的跨状态比较

{table(['phase','共有exact plan数','snapshot数','父来源group数','稳定最优source','最大fixed regret N·s'],matched)}

匹配使用float32原生masked有效表的精确bytes，外加同phase、eligible slot mask和masked carry；candidate index/source名不是identity。三个层各有三个共同exact计划，覆盖3×3个state位置（属于三个父来源），比较共有子池，原完整candidate集合因seed噪声不同，**不完全相同**。各层best计划保持不变；9个固定计划pair序列在0.001/0.1/1N·s分析分辨率下均0次反转，fixed在这些共同池regret均0。RETURN相同候选成本在三个parent间极接近，说明该层有效状态多样性有限，不可将其算成强跨状态泛化证据。

完整池best索引、phase或mask变化不作为state-conditioned preference；共有子池分析与全池分析分别导出。phase/count决定的合法表变化不能算 learned inversion。没有人工寻求反转、替换候选或删除负结果。state、phase、model estimate仅用于来源分层和描述；当前没有足够反转/独立状态支持因果关系拟合。

积分最大闭合误差{n(ranking['uncertainty']['max_integral_closure_error_N_s'])}N·s（JSON保留科学计数精度），prefix q/dq每组一致误差<1e-8。最小间隔及所有pair delta完整保存。微小间隔按三档分辨率处理；这些分辨率不是测得noise置信区间。重复标签误差分布及committed→host continuation偏差均NOT_EVALUABLE，不能仅用浮点误差推断真实策略可信度。
''')
 md('DATASET_FIELDS.md','''# 历史dense审计数据字段与复用边界

HISTORICAL_DENSE_COMMITTED_AUDIT.npz是80条原cohort的只读可复用导出，非新增独立状态、非v2就绪训练集。x为原causal120D float32，不注入真值；remaining_J_F_N_s为terminal native scorer−fork prefix，source_id/snapshot/parent/split保留原来源隔离，dense_trace是完整TASK高分辨率索引。无新模型/权重。

dense_branch_series/*：time_s、真实q/dq、梯度加速度/jerk、phase、fork_physical_s。所有true物理字段只作evaluation标签。branch_audits/*：完整来源/sha、candidate表、eligible mask、issued counts、carry、context、全部raw/5/21节点运动统计、full/remaining dose、启停/反转窗口、tracking、peak force/moment、remaining/full moment、clearance、原物理/SCI资格及host NOT_EVALUABLE、积分闭合及执行证据。

receipt_series/*：实际command receipt起止物理时间、native_steps、receipt_index、reference_effective_physics_s、q/dq reference。candidate action proposal不单独视作执行；branch_audits execution.requests/decisions与原runtime artifact索引保留认证、拒绝和科学版本因果链。未把这些SCI收据当作host40ms/100ms资格。

COUNTERFACTUAL_BRANCH_RESULTS包含80历史结果、3历史失败、8原cohort排除及空new_attempts。MANIFEST保存原91个DATA来源、所有raw/derived trace索引与hash。严格按父来源分组，dense节点和candidate pair不是独立样本。原失败/排除不重新筛选成有利样本。
''')
 report=f'''# iHEAR Lab — Motion-Constrained Counterfactual Dataset & Ranking Feasibility v1

终态：历史证据及dense运动审计完成；新增状态/分支阶段 **STOPPED_AT_RESTORATION_GATE**；真实host-replanning价值差 **NOT_EVALUABLE**。本轮完成研究交付，未训练或新增物理运行。

**唯一主要方向：D. 先解决监督目标或原生执行合同问题。** 已有数据能描述有限SCI committed后缀的force/运动权衡；完整state恢复、真实host continuation标签与合同转移尚未成立。不能直接开训v2，也不能只通过扩大网络容量解决。

## 三个核心问题

Q1：在原安全/任务资格下，已有13state的有限候选均有force获益；完整研究motion/fairness三档都只剩zero候选，获益0。仅运动负担与剂量诊断下还有有限机会，所以不能断言当前K3空间无解。三档profile不是临床阈值，阶段轨迹形状约束需进一步解释。

Q2：相同phase/mask/carry、精确相同三个共有计划的三个层均未出现ranking inversion，fixed regret0。完整候选池里仅一snapshot有3.241335N·s固定排序损失；不同pool/phase best索引变化不证明真实state-conditioned preference。此为有限状态覆盖下有效负结果，不证明所有人体状态排序不变。

Q3：原remaining label按native integral可严格闭合，dense motion也已恢复；作为 **V_commit有限表排序** 标签可用。它不是已证明的V_replan host policy value，同state数值差/排序差不可测。没有可靠可恢复父状态或匹配host因果时钟，本轮停止该比较。

## 最新状态核验与新发现

先读取并核验b_fast_jitter_m2_host_v1、m2_host_generalization_attribution_v1和m2_neural_q_motion_v1 REPORT与相关原始source/DATA/trace/BRANCH_GATE。原6%–7%force收益、RETURN主贡献、固定mask线性Q公共state项相消、新MLP test9.9306 vslinear1.6207负结果保持原报告范围；旧R2/strict55 FAIL未改。

新发现：原80合法branch的runtime_artifacts gzip仍有约0.25ms native qpos/qvel，上一包只导出5ms auxiliary label。本轮从这些原证据恢复全部80条dense真实运动，无任何physics rollout。每条验证人体列映射与sensor共同节点、严格递增native时间及同snapshot fork前q/dq完全一致。原13个snapshot仍只有4个source group，公共causal context round4为12个，不增加统计独立性。

原snapshot JSON是process-scoped fork摘要，数组/MuJoCo integration/长历史只有hash，opaque handles只能活进程fork复制。15个保存snapshot文件（13个cohort使用state及原排除）没有durable可恢复checkpoint，也无原父进程。阶段C不满足门限，新增branch attempts **0/30**；没有重建plant或persistent Human，也没有近似replay/拼接状态。

积分闭合使用fork时TASK logger区间 **包含边界** 的原始成本记录；不能用运动导数去重索引对区间cost求和。原终值减prefix与首value_row一致，重算最大误差 {ranking['uncertainty']['max_integral_closure_error_N_s']:.9e}N·s。先前exclusive-boundary诊断差完整保留，并明确不是标签uncertainty；未修改原标签或历史trace。

## 运动剂量与排序

{ranktable}

八组历史host配对knee excursion增加1.109–2.834°，累计knee角位移另外增加 {min(r['cumulative_travel_delta_deg'][1] for r in motion['pairs']):.6f}–{max(r['cumulative_travel_delta_deg'][1] for r in motion['pairs']):.6f}°；最大最终knee位置差 {max(abs(r['endpoint_delta_deg'][1]) for r in motion['pairs']):.6f}°。这说明原目标与完成虽相同，中途实际运动剂量和轨迹并非完全相同。Moment integral不等于momentum，没有临床推断。

不加新motion约束的全cohort fixed mean selection regret0.249333N·s；按4个父来源等权0.405167；历史test2state1.620668；最大3.241335。state oracle额外机会限定于该有限pool且全cohort含旧训练/开发暴露；不能当作独立泛化估计。完整三档profile的67个非zero候选均被排除，13zero保留；0 regret仅来自单一可行选择。

负担单独≤10%/25%仍有5/6state获益；负担加幅度/累计量/端点/时间、去掉phase形状的诊断有4/5state获益（平均zero−best4.351452/6.210357N·s）。所有67非zero计划不满足完整profile的phase形状界。报告这一敏感性，不按测试结果扩大轨迹形状容差，不把该结果说成普遍空间无解。

## 最终八项判断

1. 满足本轮完整研究motion条件且降低J_F：**本有限cohort未发现**；较弱拆分条件存在小幅获益，普遍可行性UNRESOLVED。
2. 不同状态出现有实际收益的固定计划最佳变化：**匹配共同池未观察到**；原全池变化受candidate/mask不同影响，不能归因state preference。
3. 固定排序损失：全13state均值0.249333N·s，父来源等权0.405167，原test1.620668，最大3.241335；匹配共同池及完整motion筛查损失0。
4. 状态条件化额外可获收益：有限全池回顾上界等于上述regret；不等于可部署收益。相同候选共同池未见额外机会，host transport未测。
5. 平顺性与剂量要求会显著收缩候选空间；strict负担无force机会，10%/25%诊断仍有小机会，但完整profile均无收益。临床可接受性NOT_EVALUABLE。
6. 神经网络数据充分性：**不足**。80rows≠80独立状态，13snapshot/12公共context/4来源group/同一Human，且RETURN状态多样性有限，没有新独立父状态。
7. Commit/replan合同一致性：**未成立且不能默认相同**；fixed residual suffix仍由B规划物理segments，host持续candidate替换、carry/expiry/admission与时钟机会不同；数值差NOT_EVALUABLE。
8. 首要补充：可恢复完整state及明确continuation/执行合同，随后才是独立来源数据与受运动约束的合法候选；没有证据要求扩大模型结构。

唯一建议D：先建立可验证完整状态fork与明确定义的监督/原生执行合同；保留V_commit作为有边界的参考，未来同state比较V_replan后再决定是否收集v2训练数据。本轮不启动后续工作。

## 预算、保护与验证

保守start={protocol['start_local']}，硬截止={protocol['deadline_local']}。新增离线branch0/30、正式host-clock配对0、新Q训练0、G/P/online adaptation0。只做单线程、串行历史数据分析，无重型物理并行。未改变Windows/WSL RAM、swap、电源或调度，未终止无关进程。

所有新增代码/报告/派生只在独立包目录及其Windows副本。Git branch/HEAD/index/status/staged diff与历史8074文件保护清单在最终PACKAGE_VERIFICATION核验；没有stage/commit/push/reset/stash/branch切换。冻结旧linear/NeuralQ权重、B/controller/commissioning及所有历史source/data/report不覆盖。完成退出后过程与时间见PACKAGE_CLOSED.json。

命令依次为指定Python -B执行code/prepare.py、state_audit.py、analyze.py、ranking.py、decompose_gates.py、build_reports.py、verify.py；所有是新目录内数据审计代码，不导入plant执行模块。read-only probe脚本/日志也保留。没有独立子agent（默认单agent；没有另行指派审计者），报告生成后做分开的保护/证据校验；无科学参数修复，积分重算边界口径澄清保留初诊。

核心文件REPORT.md、EXPERIMENT_PROTOCOL.json、MOTION_QUALITY_PROTOCOL.md/json、STATE_RESTORATION_AUDIT.md/json、COUNTERFACTUAL_DATASET_MANIFEST.json、COUNTERFACTUAL_BRANCH_RESULTS.json、RANKING_FEASIBILITY.md/json、COMMITTED_VS_REPLANNING_VALUE.md/json、PACKAGE_VERIFICATION.json；另有dense series/receipt索引、所有branch审计与字段说明。文件存在或机械校验PASS不能替代上述有限科学结论。

Canonical：{OUT}/REPORT.md。Windows review copy：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_motion_counterfactual_ranking_v1/REPORT.md。

STOP。无自动host实验、Neural Q训练、online personalization、跨Human泛化、实时/硬件或临床资格声明。
'''
 md('REPORT.md',report)
 print('REPORTS_WRITTEN',flush=True)
if __name__=='__main__':main()
