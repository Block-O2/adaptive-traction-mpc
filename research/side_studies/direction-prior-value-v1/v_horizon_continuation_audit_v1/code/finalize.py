"""Closeout only after campaign workers have joined; raw evidence remains in STUDY."""
from freeze import *
import sys,os,fcntl,collections,csv,struct
def load(name,default=None):
 p=STUDY/name;return json.loads(p.read_text()) if p.exists() else default
def fmt(x,n=3):return 'NA' if x is None else f'{x:.{n}f}'
def main():
 status=sys.argv[1];assert status in ('CORE_COMPARISON_COMPLETE','COMPLETE_WITH_ADAPTATION_PILOT','PARTIAL_RESUMABLE','BLOCKED_COMMON_INFRASTRUCTURE')
 handles=[]
 for name in ('runner.lock','controller.lock'):
  h=(STUDY/name).open('a');fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(h)
 live=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except (OSError,UnicodeError):continue
  if any(str(script) in cmd for script in (STUDY/'code/worker.py',LOCAL/'resource_monitor.py',LOCAL/'pilot.py')):live.append(int(p.name))
 assert not live,'PHYSICS_NOT_JOINED'
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts={e['id'] for e in events if e['event']=='START'};ends={e['id'] for e in events if e['event']=='END'};assert starts<=ends,'UNFINISHED_ATTEMPT_EVENTS'
 subprocess.check_call([sys.executable,str(LOCAL/'compute_ledger.py')])
 source=load('SOURCE.json');changed=[];missing=[]
 for name,expected in source['original_files'].items():
  path=Path(name)
  if not path.exists():missing.append(name)
  elif sha(path)!=expected:changed.append(name)
 git=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True)
 before=load('GIT_BEFORE.json');after=dict(branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--short'),index_sha256=sha(ROOT/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest())
 verification=dict(unix=time.time(),main_git_state_equal=before==after,original_sources_changed=changed,original_sources_missing=missing,no_live_owned_physics=True,all_attempt_events_ended=True,after=after,original_before=before)
 frozen_diffs=[name for name,expected in source['frozen_files'].items() if not Path(name).exists() or sha(Path(name))!=expected]
 unversioned=[name for name in frozen_diffs if not Path(name).is_relative_to(STUDY/'deps')]
 code=load('CODE_MANIFEST.json');code_diffs=[name for name,expected in code.items() if not Path(name).exists() or sha(Path(name))!=expected]
 verification.update(frozen_source_changed_except_versioned_dependencies=unversioned,versioned_dependencies_different_from_initial_snapshot=frozen_diffs,final_code_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),final_code_manifest_mismatches=code_diffs)
 save(STUDY/'FINAL_SOURCE_VERIFICATION.json',verification)
 assert not changed and not missing and before==after,'MAIN_SOURCE_OR_GIT_STATE_CHANGED'
 assert not unversioned and not code_diffs,'ISOLATED_SOURCE_HASH_MISMATCH'
 frozen_algorithms=load('FROZEN_ALGORITHM_VERIFICATION.json');assert frozen_algorithms and frozen_algorithms['status']=='PASS'
 for contract in STUDY.glob('COMPARISON_v*.json'):
  for name,expected in json.loads(contract.read_text()).get('algorithm_sources',{}).items():assert sha(Path(name))==expected,'FROZEN_ONLINE_ALGORITHM_CHANGED'
 analyses={b:load(f'ANALYSIS_v2_{b}.json',{}) for b in ('final','independent','fresh')};core=load('ANALYSIS_v1_core.json',{});pilot=load('PILOT_STATE.json',{});audit=load('HELDOUT_SNAPSHOT_ANALYSIS.json',{});synergy=load('KNOWN_NONMYOPIC_ANALYSIS.json',{});ledger=load('COMPUTE_LEDGER.json');c=ledger['summary']
 required_analyses=dict(analyses)
 extra=load('ANALYSIS_v2_extra.json',{})
 if extra:analyses['extra']=extra
 tail=load('ANALYSIS_v2_tail.json',{})
 if tail:analyses['tail']=tail
 if status in ('CORE_COMPARISON_COMPLETE','COMPLETE_WITH_ADAPTATION_PILOT'):
  assert core.get('groups_complete',0)>=4 and all(a.get('groups_complete',0)>=4 for a in required_analyses.values()),'REQUIRED_COMPARISONS_INCOMPLETE'
  assert audit.get('complete') and len(synergy.get('rows',[]))==5,'REQUIRED_FIXED_POOL_DIAGNOSTICS_INCOMPLETE'
 if status=='COMPLETE_WITH_ADAPTATION_PILOT':assert pilot.get('status')=='COMPLETE'
 stable=set.intersection(*(set(a.get('eligible_pilot_methods',[])) for a in required_analyses.values()))
 value_qualified=set(pilot.get('value_qualified_methods',[]));conclusions=dict(stable_primary_engineering_eligible_methods=sorted(stable),incremental_value_qualified_methods=sorted(value_qualified),pilot_value_attribution_evidence=pilot.get('value_attribution_evidence'),method_findings={},known_nonmyopic_replay_confirmed=synergy.get('first_two_worse_full_better'),no_statistical_significance_claim=True,no_new_human_claim=True)
 for method in ('P+G','P+V','P+G+V'):
  conclusions['method_findings'][method]=dict(passes_all_required_batches=method in stable,batch_mean_paired_gain={b:a.get('methods',{}).get(method,{}).get('mean_paired_gain_fraction') for b,a in analyses.items()},batch_moment_integral_change={b:a.get('methods',{}).get(method,{}).get('mean_moment_integral_change_fraction') for b,a in analyses.items()})
 if stable:
  candidates=stable&({'P+G'}|value_qualified)
  if not candidates:candidates={'P'}
  selected=max(candidates,key=lambda m:sum(a['methods'][m]['mean_paired_gain_fraction'] for a in required_analyses.values()))
  recommendation=f'保留已验证的 {selected} 冻结方案，下一轮仅在固定辨识误差条件下复验其相对 P 的收益；本轮不继续开发。'
 else:
  selected='P'
  accepted_losses=[m.get('selection_regret_within_accepted_Ns') for state in audit.get('states',[]) for m in state['methods'].values()]
  filter_gaps=[m.get('model_filter_opportunity_gap_Ns') for state in audit.get('states',[]) for m in state['methods'].values()]
  if accepted_losses and all(x is not None and abs(x)<1e-6 for x in accepted_losses) and any(x is not None and x>1e-6 for x in filter_gaps):
   recommendation='保留强 P，下一轮只校核并校准候选时序预测与真实完整后果的一致性；保持 R2、安全和物理不变，不直接降低筛选门槛。解决该模型筛选损失前，不接入更复杂的价值适应或在线辨识。'
  else:recommendation='保留强 P，下一轮只用保存状态校准候选完整后果预测的时序筛选与代价排序；保持 R2、安全和物理不变。在学习增强取得可重复改善前，不增加在线辨识与适应的耦合复杂度。'
 conclusions.update(recommended_method=selected,unique_next_recommendation=recommendation);save(STUDY/'CONCLUSIONS.json',conclusions)
 pool_gains={s['label']:s['quality']['P']['best_physical_remaining_Ns']-s['quality']['P+G']['best_physical_remaining_Ns'] for s in audit.get('states',[])}
 v_same_pool_changes={s['label']:{'P_to_PV':s['methods']['P']['selected_candidate_index']!=s['methods']['P+V']['selected_candidate_index'],'PG_to_PGV':s['methods']['P+G']['selected_candidate_index']!=s['methods']['P+G+V']['selected_candidate_index']} for s in audit.get('states',[])}
 conclusions.update(G_fixed_pool_best_candidate_improvement_Ns=pool_gains,V_same_pool_selection_changed=v_same_pool_changes);save(STUDY/'CONCLUSIONS.json',conclusions)
 development=[json.loads(p.read_text()) for p in (STUDY/'output').glob('*_DATA.json') if p.name.startswith(('parent_train_','parent_dev_'))]
 anchors={r['child']['label']:r for r in development};causal_keys={hashlib.sha256(struct.pack('<'+'f'*len(r['branch_start']['G_input']),*r['branch_start']['G_input'])).hexdigest() for r in anchors.values()}
 coverage=dict(development_parent_groups=sorted({r['group'] for r in development}),registered_fork_anchors=len(anchors),unique_float32_causal_G_anchor_inputs=len(causal_keys),completed_data_records=len(development),qualified_success_records=sum(bool(r['metric'].get('valid') and r['metric'].get('matched_eligible') and r['metric'].get('status')=='COMPLETE') for r in development),shared_initial_state_is_not_novel_coverage=True,all_branches_same_parent_split=True)
 save(STUDY/'DATASET_COVERAGE.json',coverage)
 lines=[f'# Direction Prior + Long-Horizon Value — Integrated Study v1',f'',f'STATUS: {status}',f'',f'累计墙钟 {c["elapsed_wall_s"]/3600:.3f} h；高保真尝试 {c["physics_attempts"]}/300（含失败、parent、分支及复验）。原始起点 2026-10-05 17:46:26 UTC；硬期限 16 h，派发截止 15.25 h。',f'', '## 信息条件与方法', '', 'KNOWN_MODEL 只向模型与 G/V 输入提供冻结 case 的有效人体 beta/几何参数。B 的观测器、执行器、安全审核仍使用原 commissioning 条件；真实 q/dq 仅用于独立事后评价，不进入 G/V。四组共用原物理初始化、attachment、preload、任务层与评价标准。不能称整个耦合仿真器为完美已知模型。', '', 'P 保留 B 续行、上一计划可行余部及结构化 CEM。每原生可修改决策点 2 代 × 8 个连贯 K3 表候选；G 每代至多 3 个，未增加搜索预算。K3 图在原生请求中采样一次，3 knots 不代表 3 次独立控制。HOLD 和 terminal ownership 由 B 管理。在线没有完整 MuJoCo 余程。', '', 'V 分数 = 近期模型成本 + 同状态 V_base + ΔV。单位 N s；标签为实际闭环完成余程成本减模型余程。π_cont=native-certified-committed-K3-suffix-v1，执行已承诺协调表并保留原生认证/拒绝。103D 输入含因果观测、前次 K3、未执行表、计数、已知参数；执行过的表行屏蔽。V 不是 Q* 或安全上界。', '', '模型仍近似接触与机器人跟踪。时序估计加入源自原生 bridge 的每段 50 ms 和冻结任务尺度的 500 ms 完成/估计 settling 裕量，独立 R2 资格规则未放宽。早期未 MATCHED 的规划器回归保留并排除排名。', '', '## 四组闭环结果', '', '有效才参与 J_F 排名；各批结果独立报告，不挑最优 seed 汇总。表中配对改善以 P 为基准，力矩变化为积分相对变化。', '', '| 批次 | 方法 | VALID/尝试 | J_F 均值 N s | 配对改善 % | 力矩积分变化 % | 最大 phase 差 s |', '|---|---|---:|---:|---:|---:|---:|']
 for batch,a in [('v1 core',core),*[(f'v2 {b}',a) for b,a in analyses.items()]]:
  for method,m in a.get('methods',{}).items():
   gain=m.get('mean_paired_gain_fraction');moment=m.get('mean_moment_integral_change_fraction');lines.append(f'| {batch} | {method} | {m.get("valid")}/{m.get("attempted")} | {fmt(m.get("mean_J_F_Ns"))} | {fmt(None if gain is None else 100*gain)} | {fmt(None if moment is None else 100*moment)} | {fmt(m.get("max_paired_phase_duration_change_s"),6)} |')
 lines+=['', '力矩积分的绝对均值（仅完整合格运行）：', '', '| 批次 | P | P+G | P+V | P+G+V |', '|---|---:|---:|---:|---:|']
 for batch,a in [('v1 core',core),*[(f'v2 {b}',a) for b,a in analyses.items()]]:
  values=[]
  for method in ('P','P+G','P+V','P+G+V'):
   moments=[r['metric']['moment_integral'] for r in a.get('rows',[]) if r['method']==method and r['valid']]
   values.append(fmt(sum(moments)/len(moments) if moments else None))
  lines.append('| '+batch+' | '+' | '.join(values)+' |')
 lines+=['', '单位 N m s；均值与逐配对相对变化是不同汇总量，不能互相替代。']
 info_index=lines.index('## 四组闭环结果')
 lines[info_index:info_index]=['候选调度/认证所用 native 规划器副本也保留 B 的估计模型。已知参数用于研究层的人体力/力矩代价预测和 G/V 输入；不能称候选时序或整个耦合预测器完美已知。所有四组的这项接线完全一致。', '']
 lines+=['', '## 峰值、跟踪、间隙与时延', '', '以下按各批合格运行汇总：F/M 峰值列为该批最大值，tracking 为各关节 RMS 的最大值，clearance 为最小实际物理间隙。决策时延列覆盖所有原生搜索点；低时延网络推理不能代替完整决策时延。失败与完整单次指标见 JSON/CSV。', '', '| 批次 | 方法 | F 峰值 N | M 峰值 N m | 真值 tracking RMS deg | 实际 clearance m | 决策均值/最大 s |', '|---|---|---:|---:|---:|---:|---:|']
 for batch,a in analyses.items():
  for method in ('P','P+G','P+V','P+G+V'):
   rows=[r for r in a.get('rows',[]) if r['method']==method and r['valid']]
   if not rows:continue
   latency=[x for r in rows for x in r.get('decision_wall_s',[])];tracking=[x for r in rows for x in r.get('tracking_evaluation_only_deg',{}).get('RMS_per_joint',[])];clearance=[r['metric']['physical_clearance'] for r in rows if isinstance(r['metric'].get('physical_clearance'),(int,float))]
   lines.append(f'| {batch} | {method} | {fmt(max(r["metric"]["force_peak"] for r in rows))} | {fmt(max(r["metric"]["moment_peak"] for r in rows))} | {fmt(max(tracking,default=None))} | {fmt(min(clearance,default=None),6)} | {fmt(sum(latency)/len(latency) if latency else None)}/{fmt(max(latency,default=None))} |')
 lines+=['', '## G、V 与互补性', '']
 lines+=['完整 common-mode 参考波形相对 P 的差异（名义 ROM 进度归一化后；各配对、各 phase 的最大 RMS / 最大峰值）：', '']
 for batch,a in analyses.items():
  for method in ('P+G','P+V','P+G+V'):
   reference=[v for r in a.get('rows',[]) if r['method']==method and r['valid'] for v in r.get('reference_common_progress_vs_P',{}).values()]
   if reference:lines.append(f'- {batch}/{method}：{100*max(v["RMS"] for v in reference):.4f}% / {100*max(v["peak"] for v in reference):.4f}%。')
 lines+=['', '原生请求中的共同目标采样保持不变；以上逐时刻波形差异属于冻结 native 执行语义，不能把收益解释成完全相同 common-mode 轨迹上的纯差分动作效果。', '']
 lines+=['G/V 的收益结论针对冻结的主指标 J_F。力矩积分增加属于真实代价，即使力矩峰值和安全资格仍通过，也不能称所有协调代价同时下降；完整 tradeoff 按批次和逐配对保留。', '']
 for method in ('P+G','P+V','P+G+V'):
  stats=[(batch,a.get('methods',{}).get(method,{})) for batch,a in required_analyses.items()]
  gains=[(b,m.get('mean_paired_gain_fraction')) for b,m in stats]
  eligible=all(method in a.get('eligible_pilot_methods',[]) for a in required_analyses.values())
  lines.append(f'{method}：三个必需独立批次均通过工程门槛={eligible}；批次配对平均改善 '+', '.join(f'{b}={fmt(None if g is None else 100*g)}%' for b,g in gains)+'。不以单个最好配对或 seed 代替跨批次结论。')
 for batch,a in analyses.items():
  interactions=a.get('factorial_interactions',[])
  def avg(key):return sum(r[key] for r in interactions)/len(interactions) if interactions else None
  lines.append(f'{batch}：G 边际改善（无 V / 有 V）={fmt(avg("G_gain_without_V_Ns"))}/{fmt(avg("G_gain_with_V_Ns"))} N s；V 边际改善（无 G / 有 G）={fmt(avg("V_gain_without_G_Ns"))}/{fmt(avg("V_gain_with_G_Ns"))} N s；组合超出加和的改善={fmt(avg("extra_combination_gain_beyond_additive_Ns"))} N s。满足预注册 pilot 工程门槛的方法：{a.get("eligible_pilot_methods",[])}。')
 lines+=['', '工程门槛是完整 VALID+MATCHED、全部配对正收益、均值至少 0.5%、同候选预算、native common-mode 采样误差 ≤1e-12、phase 差 ≤5 ms、共同 pretask 初始轨迹完全相同。不作统计显著结论。共同目标采样相等不代表完整逐时刻波形完全相同；每运行的波形差、tracking、clearance、峰值、fallback 和全部时延见 ANALYSIS/CSV。', '', '## 正常和合法偏离状态', '', '| 批次/状态 | 方法 | 合格配对数 | J_F 配对改善均值 % | 最小/最大 % |', '|---|---|---:|---:|---:|']
 for batch,a in analyses.items():
  for kind in ('nominal','deviation'):
   for method in ('P+G','P+V','P+G+V'):
    gains=[r['J_F_improvement_fraction']*100 for r in a.get('paired',[]) if kind in r['group'] and r['method']==method]
    if gains:lines.append(f'| {batch}/{kind} | {method} | {len(gains)} | {fmt(sum(gains)/len(gains))} | {fmt(min(gains))}/{fmt(max(gains))} |')
 lines+=['', '偏离通过合法 K3 前缀实际到达。独立训练初始化和新的 search seeds 不是新人体或新的测量噪声；本轮没有修改 measurement noise。只支持已暴露 nominal Human 上的机制判断。', '', '## 同状态完整后果诊断', '']
 for state in audit.get('states',[]):
  lines.append(f'{state["label"]}：完成 {state["completed_unique"]}/{state["expected_unique"]} 个唯一候选余程。')
  for method,m in state['methods'].items():lines.append(f'- {method}：来源 {m["selected_source"]}，合格 {m["qualified"]}，真实余程 {fmt(m["actual_remaining_J_F_Ns"])} N s；相对自身固定池合格最好项的选择损失 {fmt(m["selection_regret_Ns"])} N s；相对候选并集最好项 {fmt(m.get("selection_regret_vs_union_Ns"))} N s。')
  for method,q in state['quality'].items():lines.append(f'- {method} 池：最好真实余程 {fmt(q["best_physical_remaining_Ns"])} N s，G 生成/模型拒绝/物理合格={q["G_generated"]}/{q["G_model_rejected"]}/{q["G_physical_qualified"]}。')
  for method,m in state['methods'].items():lines.append(f'- {method}：仅在模型接受池内的排序损失 {fmt(m.get("selection_regret_within_accepted_Ns"))} N s；模型筛选机会损失 {fmt(m.get("model_filter_opportunity_gap_Ns"))} N s。V 与 P 共用筛选，不能用完整物理后果偷偷绕过它。')
 lines+=['', 'G 的有限候选池最好项相对普通 P 池改善（N s）：'+str(pool_gains)+'。这是两个保存状态的候选覆盖证据，不构成跨状态成功概率或稳健闭环收益的证明。', '', '同池 V 是否改变选择：'+str(v_same_pool_changes)+'。结合跨批次闭环结果判断价值贡献，不能把 G 的候选改善归到 V；正常状态的筛选损失和 RETURN 的接受池排序损失分别保留。']
 lines+=['', '固定池 V 重评分使用同候选和随机数，不改变第二代候选中心；它是排序诊断，不能冒充实际 PV 闭环。诊断 SearchInterface 在保存的因果/native 状态重新初始化，不继承一条实际闭环搜索历史；保留注册初始 K3 carry 和普通搜索。全集最好项是有限参照，不是全局最优。', '', f'历史 K2 只用作设计参考，线性映射到 K3 后重新采集全部五项后果；原历史成本未用于训练。新实测“前一/两步变差、完整配合变好”成立：{synergy.get("first_two_worse_full_better")}。P 选择 {synergy.get("P_selected")}，PV 选择 {synergy.get("PV_selected")}；选择损失分别 {fmt(synergy.get("P_selection_regret_Ns"))}/{fmt(synergy.get("PV_selection_regret_Ns"))} N s。', '', '| 协同前缀 | VALID | 真实改善 N s | P 预测改善 | PV 预测改善 | 余程力矩 N m s |', '|---|---|---:|---:|---:|---:|']
 for r in synergy.get('rows',[]):lines.append(f'| {r["label"]} | {r["qualified"]} | {fmt(r["benefit_vs_B_remaining_Ns"])} | {fmt(r["P_predicted_benefit_Ns"])} | {fmt(r["PV_predicted_benefit_Ns"])} | {fmt(r["remaining_M_Nms"])} |')
 lines.append('模型时序筛选资格：'+str({r['label']:r['model_eligible'] for r in synergy.get('rows',[])})+'。真实合格但被模型筛掉的路线不能仅归因为 V 排序错误；V 与 P 共用该筛选，未绕过。')
 if synergy.get('first_two_worse_full_better') and synergy.get('P_selected')==synergy.get('PV_selected')=='FULL':lines+=['', '强 P 已识别经本轮实测确认的完整多步协同，P/PV 都选择 FULL。V 对该路线的预测改善幅度可以更接近实测，但没有额外选择收益；这也不能证明它在未覆盖状态可靠。']
 wrong_sign=[r['label'] for r in synergy.get('rows',[]) if r['qualified'] and r.get('PV_sign_correct') is False]
 if wrong_sign:lines+=['', 'PV 仍误判以下前缀的真实收益方向：'+str(wrong_sign)+'。完整计划方向正确，不等于所有局部前缀方向均正确。']
 failure=load('V_FAILURE_DIAGNOSIS.json')
 if failure:
  d=failure['first_complete_plan_divergence'];lines+=['', f'额外冻结 nominal 配对的 P+V 力积分变差 {-100*failure["force_gain_vs_P_fraction"]:.3f}%。只读核验发现 V 有真实网络调用和非零校正；初始计划与 P 相同，首次完整计划分歧在第 {d["decision_index"]+1} 个搜索点，该点因果上下文相同={d["context_equal"]}、第一代候选相同={d["first_generation_plans_equal"]}。第二代中心和后续状态可能不同，不能把整轮损失全部归因于单个决策。权重、阈值与算法未调整。详见 V_FAILURE_DIAGNOSIS.json。']
 lines+=['', '## 开发数据与训练', '', '完整 parent 及其全部分支保持同一 split。最多两轮开发性采集/拟合；最终测试不进入训练或选超参数。共同起点造成跨 parent 重复，训练脚本从开发选择集排除 exact float32 输入重复，并在同 split 合并同状态 G 的多个不同好方向。三头保持不同 pending 计划，未平均相反动作。早期 native terminal 缺少标签，第二轮新增 logger-only terminal 标签；V_base 成本算术与 continuation 均未改变。', '']
 lines.append(f'开发采集包含 {len(coverage["development_parent_groups"])} 个 parent、{coverage["registered_fork_anchors"]} 个注册 fork 锚点、{coverage["unique_float32_causal_G_anchor_inputs"]} 个不同 float32 因果 G 锚点输入；{coverage["qualified_success_records"]}/{coverage["completed_data_records"]} 条保存余程数据完整合格。共享初始状态不算新增状态泛化。沿余程的 V 采样数量另外列出；不能把相邻采样点当独立测试组。')
 for p in sorted(STUDY.glob('weights_v*/TRAINING.json')):
  t=json.loads(p.read_text());lines.append(f'- {p.parent.name}：设备 {t["device"]}；V train/dev={t["V_counts"]}，G={t["G_counts"]}；V 选择 {t["V_selected"]}；MLP/linear 开发选择损失 {fmt(t["metrics"]["V_MLP"]["selection_regret_Ns"])}/{fmt(t["metrics"]["V_LINEAR"]["selection_regret_Ns"])} N s；权重 SHA256 {t["weights_sha256"]}。')
  m=t['metrics'];lines.append(f'  MLP/linear ΔV 开发 RMSE={fmt(m["V_MLP"]["deltaV_RMSE"],6)}/{fmt(m["V_LINEAR"]["deltaV_RMSE"],6)} N s；G 最近头计划 RMS={fmt(m["G_dev_nearest_head_plan_RMS"],6)}；CPU/训练设备最大输出差 V={m["V_numpy_device_max_difference_Ns"]:.8g} N s、G={m["G_numpy_device_max_difference"]:.8g}。拟合墙钟 {fmt(t["wall_s"])} s；host RSS 峰值 {t.get("peak_host_rss_bytes","未采样")} bytes，CUDA allocation 峰值 {t.get("CUDA_peak_allocated_bytes","未采样")} bytes。')
  if t.get('actual_parent_suffix_G_supervision'):lines.append(f'  G 另复用 {len(t["actual_parent_suffix_G_supervision"])} 个预先选择、成功执行的 committed-parent 剩余计划；开发去重前、train/dev 合计的入选头来源计数 {t.get("G_target_source_counts")}，实际训练/开发数量以上述 G_counts 为准。它们按该 parent 实测剩余成本排序，不宣称每个状态重新优化，也不生成或替换 V 标签。来源文件及 SHA256 见 TRAINING.json。')
 fit_check=load('INDEPENDENT_FIT_VERIFICATION.json')
 if fit_check:lines+=['', f'独立初始化协议核验：{fit_check["status"]}；{fit_check["development_source_files"]} 个来源文件逐项哈希相同，训练结构、分组、去重、标签与源码一致，保留测试标签未使用。它是独立初始化复验，不是第三轮开发。详见 INDEPENDENT_FIT_VERIFICATION.json。']
 lines+=['', '独立初始化测试同时更换搜索随机条件，批次差异不能单独归因为网络初始化。各批内部四组使用配对随机条件；不同批次分开报告。']
 lines+=['', '第二轮 MLP 开发 RMSE 比第一轮更差，开发选择损失均为零也未转化为稳定闭环收益；不能把开发集排序正确称为价值学习已成功。']
 lines+=['', '## 重复 pilot', '', f'状态：{pilot.get("status","尚未运行")}；原因/结论：{pilot.get("reason",pilot.get("claim","NA"))}。']
 lines+=['', f'归因规则：P+V 比 P，P+G+V 比 P+G；各必需批次所有合格配对正收益且均值至少0.5%，并先通过相对 P 的原主指标资格。只由 G 带来的组合胜利不晋级价值 pilot。增量 V 合格方法：{pilot.get("value_qualified_methods",[])}；原始配对归因证据见 PILOT_STATE/CONCLUSIONS。']
 if pilot.get('status')=='COMPLETE':lines+=['', f'方法 {pilot["method"]}；保留最佳已验证 round={pilot["best_round"]}、λ={pilot["frozen_scale"]}。G/V 网络冻结，个体部分只校准 [0.5,1.5] 的 ΔV 标量；一轮参数固定、实时反馈规划。配对 no-update 对照全部保留。该 pilot 是已暴露人体的标量策略校准，重新规划成本未替代 committed-suffix MC 标签。', '', '验证配对收益：'+str([r['gain_vs_no_update'] for r in pilot['validation']])]
 lines+=['', '## 资源、失败及计算账本', '', f'物理尝试 {c["physics_attempts"]}；可从 trace 精确核算的新仿真秒数 {fmt(c["actual_new_simulation_seconds"])}，原生步骤 {c["actual_new_native_physics_steps"]}，dt=0.00025 s。缺失/中断无 trace 的尝试仍计入300；其未完整记录的物理工作不能报告为零。', '', f'已记录主模型 API 调用 {c["known_main_model_calls"]}、原生 worker 模型调用 {c["known_native_worker_model_calls"]}；有 {c["missing_model_count_runs"]} 次早期/中断尝试缺完整计数，因此这些是可核算下界。规划器模型计数是主 API 子集，不重复相加；parent 墙钟包含其分支，不相加虚增。Scientific Mode 全时延已记录，不声称 hardware realtime PASS。', '', f'资源采样 {c["resource_samples"]} 次；峰值本任务 PSS={c["peak_owned_PSS_bytes"]/2**30:.3f} GiB；最小 Windows available={c["min_windows_available_bytes"]/2**30:.3f} GiB；OOM 增量 {c["oom_kill_delta"]}；新增文件 {ledger["new_bytes"]/2**30:.3f} GiB。', '', '开发 parent 的旧指纹展开 sensor histories，造成真实低余量和换页；迫近耗尽保护中断 worker。所有错误、尝试及原始资源样本保留。先去除与 fork 哈希失配相关的 GC/malloc_trim，再改为覆盖每项历史的流式指纹（显式 RNG/deque/cache）；连续健康样本后显式续跑缺失分支，未改变 physics 或降低保护阈值。没有 kill 未知进程、重启 WSL 或修改 RAM/swap。', '', '来源限制：最早 P smoke 源仅能按保留补丁事后重建，原 aggregate hash 不可恢复；PROVENANCE 明确标记。早期 retry 的 DATA 名与唯一 trace 目录有别名，COMPUTE_LEDGER 使用 trace 唯一映射避免重复计账。原结果及失败 END 不改写。', '', '## 交付与下一步', '', f'主项目 branch/HEAD、dirty/staged 状态、index 和原始来源文件 SHA256 全部与开始一致。证据：FINAL_SOURCE_VERIFICATION.json。本研究全部 raw trace/gzip、快照与旧版本保留在 {STUDY}。', '', '唯一下一步应由实测候选覆盖/排序诊断决定；本轮结果不能直接证明接回在线辨识后的收益。保持已冻结物理、任务、安全和候选预算，先在辨识误差条件下验证最佳已验证方法。', '', '复现/恢复：先读 RUN_PLAN、SOURCE、PLAN_AMENDMENT、TASK_LEDGER、STATE、ATTEMPTS；原始时钟和已耗预算不得重置。完成状态无需继续本轮。若 PARTIAL，停止所有旧 owner 后使用 recover.py 显式生成 retry，核对 queued/attempted ID 后再启 runner.py/controller.py；不得重放已经完成项。']
 lines+=['', f'部分中断工作从保存时钟补回 {c.get("partial_physics_recovered_runs",0)} 次；仍有 {c.get("physics_work_unknown_runs",0)} 次缺乏可靠物理时钟，合计物理工作因此为可核算下界。', '', '序列化根因进一步定位到逐行 Python iterencode 产生循环引用闭包，数百万临时对象延迟回收。v3 改用限定单行的 C 编码器；1000 个结构样例与原指纹逐字节一致，未构造整个历史的大字符串。完整 fork 回归比较早期及 RETURN 三次 B 续行的13项整个 trace，全部逐元素相等，见 FORK_WHOLE_TRACE_AUDIT.json。', '', '早期分支继承 parent 原生 artifact 路径，造成部分归档覆盖；唯一 child trace、summary 和 DATA 保留，但缺失的原生 artifact 无法凭空恢复。随后按 env.episode_dir 路由并独立 gzip；此来源限制保留，不删除历史失败。', '', '资源覆盖：早期采样仅覆盖 physics runner 子树；补充观察器启用后覆盖 runner 与 controller 两个子树。v1 短时拟合缺采样峰值，后续拟合另记 host RSS/CUDA 峰值；不把缺测填成零。']
 generic='唯一下一步应由实测候选覆盖/排序诊断决定；本轮结果不能直接证明接回在线辨识后的收益。保持已冻结物理、任务、安全和候选预算，先在辨识误差条件下验证最佳已验证方法。'
 lines=[recommendation if line==generic else line for line in lines]
 (STUDY/'REPORT.md').write_text('\n'.join(lines)+'\n')
 save(STUDY/'FINAL_STATUS.json',dict(status=status,unix=time.time(),elapsed_hours=c['elapsed_wall_s']/3600,physics_attempts=c['physics_attempts'],all_owned_workers_joined=True,source_verification=str(STUDY/'FINAL_SOURCE_VERIFICATION.json'),pilot_status=pilot.get('status'),report=str(STUDY/'REPORT.md')))
 dest=LOCAL/'deliverables';dest.mkdir(exist_ok=True)
 patterns=('REPORT.md','*.json','*.csv','*.png','*.pdf','PROGRESS.md','ATTEMPTS.jsonl','ROOT_PHASE_HISTORY.jsonl','USER_REQUEST.txt')
 for pattern in patterns:
  for p in STUDY.glob(pattern):
   if p.is_file():shutil.copy2(p,dest/p.name)
 for root in STUDY.glob('weights_v*'):
  if root.is_dir():shutil.copytree(root,dest/root.name,dirs_exist_ok=True)
 data=dest/'data';data.mkdir(exist_ok=True)
 for p in (STUDY/'output').glob('*_DATA.json'):shutil.copy2(p,data/p.name)
 contracts=dest/'contracts';contracts.mkdir(exist_ok=True)
 for pattern in ('*CONTRACT.json','KNOWN_MODEL_PARAMETERS.json','*DESIGN_REFERENCE.json','*_AUDIT_POOL.json','KNOWN_NONMYOPIC_POOL.json'):
  for p in (STUDY/'output').glob(pattern):shutil.copy2(p,contracts/p.name)
 outcomes=dest/'outcomes';outcomes.mkdir(exist_ok=True)
 for pattern in ('*_RESULT.json','*_BRANCH_ERROR.json','*_FORK_MISMATCH.json','*_PARENT_MISMATCH.json'):
  for p in (STUDY/'output').glob(pattern):shutil.copy2(p,outcomes/p.name)
 failure=load('V_FAILURE_DIAGNOSIS.json')
 if failure:
  for name in failure['source_files']:
   p=Path(name)
   if p.name.endswith('_SEARCH.json'):shutil.copy2(p,outcomes/p.name)
 provenance=dest/'provenance';provenance.mkdir(exist_ok=True)
 if (STUDY/'source_history').exists():shutil.copytree(STUDY/'source_history',provenance/'source_history',dirs_exist_ok=True)
 for root in (STUDY/'code_history').iterdir():
  if not root.is_dir():continue
  for relative in ('CODE_MANIFEST.json','code/train.py'):
   p=root/relative
   if p.exists():d=provenance/'code_history'/root.name/relative;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
 config=dest/'requests';config.mkdir(exist_ok=True)
 for p in (STUDY/'queue').glob('*.json'):shutil.copy2(p,config/p.name)
 evidence=dest/'resources';evidence.mkdir(exist_ok=True)
 for p in (STUDY/'output').glob('*.jsonl'):shutil.copy2(p,evidence/p.name)
 scripts=dest/'harness';scripts.mkdir(exist_ok=True)
 for p in LOCAL.glob('*.py'):shutil.copy2(p,scripts/p.name)
 save(dest/'MANIFEST.json',{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file() and p.name!='MANIFEST.json'})
 print(json.dumps(dict(status=status,report=str(dest/'REPORT.md'),physics_attempts=c['physics_attempts'])))
if __name__=='__main__':main()
