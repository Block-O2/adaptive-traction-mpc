"""Generate the 20-question report from final evidence, never fabricated pilot data."""
import json,time
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from research_campaign import R,D,RAW,RUNS,C,save,sha

def read(name,default=None):
 path=D/name
 return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)
def fmt(value,digits=3):return '未测得' if value is None else f'{value:.{digits}f}'
def distribution(values):
 a=np.asarray([float(x) for x in values if x is not None and np.isfinite(x)],float)
 return {'count':len(a)} if not len(a) else {'count':len(a),'median':float(np.median(a)),'p95':float(np.percentile(a,95)),'p99':float(np.percentile(a,99)),'maximum':float(a.max()),'sum':float(a.sum())}
def model_table(models):
 lines=['|模型/目标|test MAE / RMSE (N·s)|FULL 动作排名 ρ|所选动作 regret (N·s)|top1 / top2|','|---|---:|---:|---:|---:|']
 for key,m in models.items():
  q=m['test_full_action_ranking'];prediction=m['test_target_prediction']
  lines.append(f'|{key}|{prediction["MAE_n_s"]:.3f} / {prediction["RMSE_n_s"]:.3f}|{q["mean_spearman"]:.3f}|{q["mean_regret_n_s"]:.3f}|{q["top1_accuracy"]:.3f} / {q["top2_capture_fraction"]:.3f}|')
 return lines
def main():
 now=datetime.now(timezone.utc);state=read('STATE.json');reference=read('BEST_KNOWN_REFERENCE_TABLE.json');native=read('NATIVE_BEST_KNOWN_REFERENCE_TABLE.json')
 offline=read('OFFLINE_VALUE_MODEL_COMPARISON.json');models=offline.get('selected_models',{})
 pilot=read('ONLINE_POLICY_IMPROVEMENT_PILOT.json');convergence=read('CONVERGENCE_ANALYSIS.json')
 capture=read('KNOWN_BENEFIT_CAPTURE.json');absolute=read('PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json')
 manifest=read('VALUE_DATASET_MANIFEST.json');latency=read('ONLINE_LATENCY_PROMOTION_GATE.json')
 records=[json.loads(p.read_text()) for p in RUNS.glob('*/rollout_result.json')]
 closed=[r for r in records if r.get('status')!='RUNNING'];counts=dict(Counter(r.get('status') for r in closed))
 times={}
 for category,prefixes in [('matched_reference',('search_',)),('native_reference',('native_search_',)),('local_branch',('branch_',)),('counterfactual',('counterfactual_','native_counterfactual_','alternate_probe_')),('other',())]:
  values=[]
  for p in (RAW/'launches').glob('*.json'):
   entry=json.loads(p.read_text())
   if prefixes and not p.stem.startswith(prefixes):continue
   if not prefixes and p.stem.startswith(('search_','native_search_','branch_','counterfactual_','native_counterfactual_','alternate_probe_')):continue
   values.append(entry.get('wall_s'))
  times[category]=distribution(values)
 elapsed=(now-datetime.fromisoformat(C['campaign_start_utc'])).total_seconds()
 save(D/'REFERENCE_AND_TRAINING_WALL_TIME.json',{'timestamp_utc':now.isoformat(),'campaign_elapsed_wall_s':elapsed,'rollout_launch_wall_s_by_category':times,'scope':'per-launch host wall distributions; overlapping runs mean sum is not campaign elapsed or pure CPU time; pilot direct runs recorded separately','offline_model_training':{k:m.get('training_wall_s') for k,m in models.items()}})
 text=['# Learning Research v1：性能上限、学习效率与在线计算','',f'生成时间：{now.isoformat()}。当前状态：`{state.get("status")}`，科学工作状态：`{state.get("scientific_work_status","研究处理中")}`。',
  '',f'累计运行 {elapsed/3600:.2f} 小时；9 小时上限为 {C["hard_deadline_utc"]}。新研究已关闭记录 {len(closed)} 个：{json.dumps(counts,ensure_ascii=False)}。历史 518 次探索、63.77 GB 原始来源另行冻结验证，不计为本轮新增实验。',
  '', '主指标为完成有效任务的实测袖套力模积分 J_F_task，单位 N·s。安全与任务有效性始终为硬门槛；均值/RMS/峰值力、力矩积分/峰值、时长、clearance 和 smoothness 分别保存于逐次结果，不重新加权成奖励。',
  '', '**必须区分两种范围：** NATIVE_SCHEDULER 是主目标的绝对 best-known 搜索；MATCHED 是固定声明续行时长的条件化学习研究。MATCHED 取得的改善不能当作绝对性能上限。所有参考均为 best-known，未证明全局最优。',
  '', '## 1. 接口是否复现已知有益协调？','',
  '是。四个 MATCHED 和四个 NATIVE 参考通过同一研究候选/执行接口复放，目标、实现 q、力轨迹和 J_F 差异均为零。来源包含同步、变起点、balanced-high 和 hip 条件；原始控制、安全、估计与几何屏障保留。见 ACTION_EXPRESSIVITY_GATE.json 与 NATIVE_ACTION_EXPRESSIVITY_GATE.json。',
  '', '## 2. 更强搜索是否超过旧 best-known？','',
  '下表旧值取全部历史 VALID 路径的最小成本，包括时序存在差异的路径；另外保留旧 timing-isolated 值，避免把受限旧参考当作绝对旧最优。Q 筛选新增参考与 CEM 搜索分开标注。',
  '', '|条件|MATCHED 旧 → 新 (N·s)|NATIVE 旧 → 新 (N·s)|新增实测评估 matched/native|','|---|---:|---:|---:|']
 for m,n in zip(reference.get('rows',[]),native.get('rows',[])):
  text.append(f'|{m["condition"]}|{m["previous_best_J_F_n_s"]:.6f} → {m["best_known_J_F_n_s"]:.6f}|{n["previous_best_J_F_n_s"]:.6f} → {n["best_known_J_F_n_s"]:.6f}|{m["evaluations"]}/{n["evaluations"]}|')
 text+=['','新赢家通过独立同起点再执行确认；这是确定性复现，不是独立受试者泛化。见 BEST_KNOWN_REFERENCE_CONFIRMATION.json、NATIVE_BEST_KNOWN_REFERENCE_CONFIRMATION.json。',
  '', '## 3. 更多路径自由度是否继续降低成本？','',
  'variable_start_120 的 MATCHED 搜索包络从 L0 1482.176759、L2 1481.931124 降至 L3 1473.789827 N·s。但该 L3 赢家的两个新增系数为零，实际上仍可由 L2 表达。因此更大搜索确实继续改善，尚未证明额外自由度本身带来因果收益。L1/L2/L3 的连续系数分别为 2/5/7，另有离散 horizon/return 选择；各层评估数量不同，也不能当作公平复杂度消融。其他条件未必改善，L4 未执行。',
  '', '## 4. 有证据接近平台吗？','',
  '不足。部分条件的有限预算包络变平，但有效评估、重启和代数覆盖不同，尚无充分重复优化或下界。CEM 保留基线、已知有益初始化、多个重启和均匀探索；每个提议使用真实冻结科学栈评价。见各条件 level_evaluations、restart_generation_evaluations、restart_best 和完整收敛曲线。',
  '', '## 5. 最佳协调有多强的条件依赖？','',
  '明显。大 ROM 条件倾向较强 hip-leading H3；普通低 ROM 的最佳 MATCHED 路径包含小幅相反方向或不同 catch-up peak，hip 普通条件保留旧 H4 参考。NATIVE 与 MATCHED 最佳策略也不同。六个代表条件不支持单一跨条件最优策略或人群结论。',
  '', '## 6. Q 能否正确排列动作？','',
  f'数据为 {manifest.get("runs")} 条 VALID MATCHED 轨迹、{manifest.get("rows")} 个实际激活决策、{manifest.get("features")} 个可部署特征；train/validation/test 行数为 {manifest.get("split_row_counts")}。27 组共同状态、共同续行规则的安全下一目标分支支持局部排序识别。训练按条件隔离，未随机拆相邻轨迹行。',
  '', '选定 FULL ridge 的 validation 平均 regret 0.684 N·s，legacy 1.690，ρ=0.417。held-out test ρ=-0.333、regret 3.555，对比 legacy 4.360；只支持有限的开发门槛，不能声称稳定跨条件正确排序。',
  '', 'Q 的实际语义是 Q(x,a | 已声明续行规则)，不是 Q*；每个目标从真实激活/生效区间计算 FULL 剩余回报与 1.5 秒 SHORT 回报。后续控制保持闭环，但本次策略先在首次 OUTBOUND 目标选择一个平滑续行模式，后续按该模式提议单个目标，不把整个 H3/H4 收益归因于孤立首个 waypoint。',
  '', '## 7. FULL 是否胜过 SHORT？','',
  '结果混合，不能作一致优势结论。FULL ridge 比 SHORT ridge 的 held-out FULL 动作 regret 更低；MLP 则 SHORT 的 FULL 动作 regret 2.195 优于 FULL 8.335。不同目标的预测误差量级不可直接比较，主要比较共同分支中的实际完整回报 regret。未用 test 重新选择模型。',
  '', '## 8. 简单模型与小 MLP 的效果？','']
 text+=model_table(models)
 text+=['','MLP 为两个 32 单元 tanh 层、NumPy Adam、三种冻结种子；ridge 含标准化线性项和可解释状态×动作交互。选模使用 validation；模型及 scaler 保存为不可变 NPZ。简洁 ridge 在本次 FULL 开发集较好，但 held-out 排名仍弱。',
  '', '## 9. PRIOR 比 SCRATCH 帮助多少？','',
  '两者使用相同候选库、模型族、由离线 validation 选定的超参数。SCRATCH 无跨条件预训练值权重，初始两轮用已知安全的连贯提议；PRIOR 只用其他 train 条件，并排除当前 sync 与全部 held-out test，当前在线行单独记录。它们均不是从零学习控制器、任务、安全或候选族。',
  '', '|会话|有效/尝试轮数|首轮 → 末轮 J_F (N·s)|收敛候选轮|','|---|---:|---:|---:|']
 for s in pilot.get('sessions',[]):
  rows=s['rows'];valid=[r for r in rows if r['status']=='VALID'];cv=next((x for x in convergence.get('sessions',[]) if x['session']==s['session']),{})
  text.append(f'|{s["mode"]}|{len(valid)}/{len(rows)}|{fmt(valid[0].get("J_F_task_n_s") if valid else None)} → {fmt(valid[-1].get("J_F_task_n_s") if valid else None)}|{cv.get("retrospective_first_trigger_repetition")}|')
 text+=['','本轮连续启动失败后，后续有效尝试来自新的开发片段，并未保留连续 Human/adaptation 状态。PRIOR 的有效片段均选基线，未显示先验改善；SCRATCH 在第1/3/5/7次尝试的成本分别为1509.460/1529.600/1478.874/1478.874 N·s。它利用前两个已完成回报，在第三个有效片段（第5次尝试）选中预先存在候选库中的0.15/H3。该有限冷起点选择结果不能当作连续个性化、完整从零学习或人群样本。共同起点对照仅在精确状态核验后计算，具体预测误差、排名、选择、失败和更新版本见 SCRATCH_VS_PRIOR_ANALYSIS.json。',
  '', '## 10. 小试验几轮稳定？','']
 for s in convergence.get('sessions',[]):text.append(f'- {s["mode"]}：首次回溯收敛候选={s.get("retrospective_first_trigger_repetition")}；有效轮数={s["valid_repetitions"]}。')
 text+=['','稳定性同时检查同一连续片段内最近三次有效任务的 baseline-adjusted 收益、精确模式、Q 排名、目标替代探针、安全和计算门槛。本轮未得到这种连续窗口，因此没有收敛触发。开发后冻结的数值尺度仅为探索性诊断，尚未由连续学习数据校准。',
  '', '## 11. 五轮收敛现实吗？','',
  '见完整回溯准则与 rep1/3/5/8 的同轮替代探针。即使成本/模式平稳，若 Q 排名、替代动作改善、安全或计算门槛不满足，也不能认定收敛。八轮预算并非“5 learn + 25 exploit”；后续应前瞻冻结开发所得阈值并按证据停学。',
  '', '## 12. Rep1/3/5/8 的已知收益捕获？','',
  '|会话/轮|MATCHED baseline / learned / reference (N·s)|条件化 capture|NATIVE 主目标 capture|','|---|---:|---:|---:|']
 for r in capture.get('rows',[]):
  if r['repetition'] not in (1,3,5,8):continue
  n=next((x for x in absolute.get('rows',[]) if x['session']==r['session'] and x['repetition']==r['repetition']),{})
  text.append(f'|{r["session"]}/{r["repetition"]}|{fmt(r.get("baseline_J_F_n_s"))} / {fmt(r.get("learned_J_F_n_s"))} / {fmt(r.get("reference_J_F_n_s"))}|{fmt(r.get("known_benefit_capture"))}|{fmt(n.get("known_benefit_capture"))}|')
 text+=['','capture=(baseline−learned)/(baseline−best-known)，仅正且可辨的分母计算。保留负值或超过 1 的结果；超过参考需独立确认后更新该状态 best-known。两种调度范围各用同轮前不可变检查点，不能把 MATCHED capture 当作绝对全局最优百分比。',
  '', '## 13. 本轮最佳有效成本/参考是什么？','',
  '见上方逐条件表与 ABSOLUTE_PRIMARY_REFERENCE_TABLE.json；跨条件 J_F 不直接排序性能。sync 的后试验0.18/H3探针独立确认成本1468.421258 N·s，更新条件化 best-known；此前0.15/H3的1478.873547 N·s参考保留为初始冻结比较。NATIVE 参考明显更低，说明匹配时长学习问题仍有范围限制。各参考同时保存时长、相位差、参数、可行比例与原始实验 ID。',
  '', '## 14. 学习器是否发现并确认更好行为？','',
  '离线 Q 在延迟采集中选择0.15/H3路径并独立确认1478.873547 N·s，低于 sync CEM 1485.999765；其train包含sync，不是held-out泛化。SCRATCH后续选到同一已知参考，未选择比它更好的路径；PRIOR未选中该路径。第5次的预声明替代探针0.18/H3得到1468.421258 N·s并独立确认，这是后试验探针的新发现，不能归为在线学习器的选择。本次最佳条件化参考因而更新，原参考capture另存。首次确认把嵌套配置误作为descriptor而实际复跑了基线，成本差异检查正确判FAIL并保留；随后使用原探针完整配置逐字复跑，差异为零。',
  '', '## 15–19. 完整在线计算、瓶颈、更新与策略加速','']
 section=D/'LATENCY_REPORT_SECTION.md'
 text.append(section.read_text() if section.exists() else '延迟并行工作流尚未形成最终报告，不能补造数据。')
 text+=['','## 20. 下一次更大实验具体用什么方法？','',
  '推荐“续行一致的原生调度模板＋版本化轻量 ridge critic”这一方法。先在独立开发版本验证接受终点到下一轮起点的参考连续性/安全桥接，保留原始1°/2°s启动门槛；再保留 NATIVE 基线作实际 fallback/incumbent，用少量连贯安全模板提议下一 hip/knee 目标，原始安全筛选后独立 Q 排名，已承诺续行复用已验证筛选。原生调度数据必须有共同状态/共同续行分支对照并通过新的 held-out 排名、主目标收益与完整提交链预算验证；安全轮边界切换模型，rep1/3/5/8 前瞻冻结探针和收敛准则。验证完成后才进入更大的 learn-until-converged → exploit 研究。本轮不启动最终30轮、硬件或 realtime qualification。',
  '', '这是一个下一步方法，包含必需的原生主目标与提交链验证门槛；当前 MATCHED critic 不能直接晋升为部署策略。推理已很快，优先削减重复安全计算和提交开销；只有少量候选仍无法满足预算时，才考虑轻量 proposal policy，安全筛选继续权威。',
  '', '## 证据、修复与 Git 状态','',
  'SCRATCH rep1 的物理任务有效，但在后来被撤销的静止续行代理门槛下提前执行，构成计算门槛的流程偏差。该轮保留，不追认成真实运动门槛通过；后续轮只能在单独冻结并复测的计算版本通过科学门槛后，从原始检查点安全边界恢复。见 PILOT_PROTOCOL_DEVIATIONS.json 与 boundary_computation_amendment_v3.json。不同计算版本不能合并成一份部署实时通过证据。',
  f'起点分支 codex/coordination-pacing-exploration-v1，HEAD {state.get("source_head")}；研究分支 codex/value-learning-research-v1。原始控制/估计/Human dynamics/历史证据哈希保持冻结；hidden truth 仅评估使用，未进入选择。修复上限6，已用 {state.get("repair_cycles_used")}，逐项见修复与基础设施记录。',
  '', '本轮改动位于新研究 scripts/value_learning_v1 与 docs/value_learning_research_v1，另新增 git-ignore 规则；大型原始轨迹忽略于 Git，lossless 压缩及 D 盘逐字节校验转存有清单/哈希。未 reset、stash、clean、merge、force push 或 git add -A。所有分阶段提交逐文件 stage。',
  '', 'RAW_DATA_MANIFEST.json、FINGERPRINTS.json、SOURCE_RAW_VERIFICATION.json、FINAL_EVIDENCE_VERIFICATION.json、Git checkpoint/REMOTE_VERIFICATION 记录用于复现。总时间与逐类别 launch 耗时见 REFERENCE_AND_TRAINING_WALL_TIME.json；并发工作时间求和不是经过的 wall time。',
  '', 'Git push 的自动审批已拒绝，理由是 GitHub 目的地/外发研究载荷授权未获确认。先完成可审查科学证据与本地提交，最后向用户请求向 https://github.com/Block-O2/adaptive-traction-mpc 的 codex/value-learning-research-v1 分支推送。未验证 local HEAD == remote HEAD 前，不宣称用户要求的整体 COMPLETE。',
  '', '`RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`。科学算法耗时、冻结物理仿真和确定性复现均不构成硬件实时或临床安全资格。']
 (D/'LEARNING_RESEARCH_V1_REPORT.md').write_text('\n'.join(text)+'\n')
 sources={p.name:sha(p) for p in D.glob('*.json') if p.name not in ('REPORT_PROVENANCE.json','RAW_DATA_MANIFEST.json','FINGERPRINTS.json')}
 save(D/'REPORT_PROVENANCE.json',{'timestamp_utc':now.isoformat(),'report_sha256':sha(D/'LEARNING_RESEARCH_V1_REPORT.md'),'source_evidence_sha256':sources,'20_questions_answered_or_explicitly_unavailable':True,'unmeasured_results_not_fabricated':True})
 print(json.dumps({'report':str(D/'LEARNING_RESEARCH_V1_REPORT.md'),'closed_runs':len(closed),'elapsed_h':elapsed/3600}),flush=True)

if __name__=='__main__':main()
