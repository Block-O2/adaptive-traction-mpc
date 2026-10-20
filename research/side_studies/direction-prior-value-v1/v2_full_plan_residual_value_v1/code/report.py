from common import *
import numpy as np
from datetime import datetime, timezone, timedelta

NEXT = '保留 frozen strong P；只有新增独立完整候选池的 oracle 出现可重复多状态选行动收益后，才另行重开 V2 训练门控。'
DEST = 'C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/v2_full_plan_residual_value_v1_work/deliverables'
def main():
 gate=read(NEW/'ORACLE_GATE.json');sem=read(NEW/'SEMANTIC_SUITABILITY.json');d=read(NEW/'FULL_PLAN_ERROR_DECOMPOSITION.json');comparison=read(NEW/'V1_V2_COMPARISON.json');verification=read(NEW/'PRESERVATION_AND_VERIFICATION.json');ledger=read(NEW/'COMPUTE_RESOURCE_LEDGER.json')
 assert gate['gate']=='FAIL' and sem['PRIMARY_V2_CONTRACT']=='ROLLING_P' and verification['status']=='PASS'
 lines=[]
 def put(s=''):lines.append(s)
 def table(headers,rows):
  put('| '+' | '.join(headers)+' |');put('| '+' | '.join(['---']*len(headers))+' |')
  for row in rows:put('| '+' | '.join(str(x) for x in row)+' |')
  put()
 def link(name):return '['+name+']('+DEST+'/'+name+')'
 put('# V2 Full-Plan Residual Value — Oracle Gate, Learning & Closed-Loop Qualification v1\n')
 put('STATUS: **COMPLETE_EARLY_ORACLE_STOP**。V2 STATUS: **V2_NOT_DECISION_RELEVANT（本次有限候选池范围）**。')
 put('PRIMARY 的 5 个 native parent pools 中，P 已选择各 accepted pool 的实际最低成本候选；完美 full-plan residual 的 top-1 收益为零。COMMITTED 仅改善一个 RETURN pool，不能满足多 parent 的预注册门槛。按用户明确要求提前结束，不构建训练集、不拟合网络、不运行闭环资格实验。该结论不是对所有 Human、所有候选或未来 V2 的普遍否定。\n')
 start=datetime.fromtimestamp(START,timezone(timedelta(hours=8))).isoformat()
 put(f'预算起点：{start}（Asia/Shanghai）；报告前验证 wall {ledger["elapsed_h"]:.3f} h；新增高保真 continuation **0/40**，训练 **0**，新权重 **0**。目标 3–5 h 不是最低运行时长，oracle 早期失败允许提前停止。\n')
 put('## 冻结定义与语义适用性\n')
 put('对当前实际 native request boundary 的因果状态 b 与完整 pending K3 candidate U：\n')
 put('`J_hat_full(b,U) = J_model_full(b,U) + DeltaJ_full(b,U)`，成本单位 N·s；所有成本均为现在至**当前 repetition 完成**的 remaining J_F，不包括已经发生的 prefix 或未来 repetition。J_model_full 是原 frozen strong P 对同一完整 candidate 的当前轮全剩余预测，保持原控制律、Human physics、R2、安全和 action authority。\n')
 table(['适用性','COMMITTED','ROLLING-P'],[[k,sem['assessments']['COMMITTED'][k],sem['assessments']['ROLLING_P'][k]] for k in 'ABCDE'])
 put('两者都可稳定定义。按照结果评分前登记的部署一致性规则，选择 **PRIMARY_V2_CONTRACT=ROLLING_P**；COMMITTED 保留为 diagnostic。PROTOCOL → SEMANTIC_SUITABILITY → ORACLE_GATE 的时间先后已验证，未在看到收益后改换 PRIMARY。\n')
 put('- COMMITTED：`DeltaJ_committed = J_actual_committed_full - J_model_full_same_candidate`。请求执行 U 的当前作用，并保持其 declared committed suffix；正常 native certification / rejection / fallback 继续有效，不做性能重规划。')
 put('- ROLLING-P：`DeltaJ_rollP = J_actual_rollP_full - J_model_full_original_candidate`。执行同一当前 native row 后，恢复 frozen P rolling search，把 U 保留为 previous plan/carry，两个 search generations 均保留正常 carry 候选，不使用 G/V/V2。该 residual 同时包含模型误差与 P continuation 的影响，是声明策略的条件残差，**不是 Q\***。\n')
 put('ROLLING-P 所用未来 optimizer ownership 是原 audit 明确保存的各 parent post-forcing P seed，并重构其下一次 search 的 RNG state；并非恢复历史线上 optimizer 随机流。结果只对应这些明确条件的 frozen P continuation。30 个 first-segment/carry 配对证明复用且 PASS。\n')
 put('输入原型包含当前 55D causal observation、估计 Human state/reference、phase/task/phase elapsed、nominal request、Human belief/effective β/geometry、模型版本、上一 issued K3 proposal、masked previous pending table、完整 masked U、issued counts、valid mask，以及上述 P ownership。observation 已包含 commissioned residual parameters。snapshot/plan hash 仅作 provenance，future truth、actual future cost/force、oracle 排名、sim-only q/dq 不进入输入。'+link('CAUSAL_INPUT_PROTOTYPES.json')+' 是 15 条预拟合特征审计原型，不是 TRAIN/DEV/TEST 数据集。\n')
 put('## Mandatory offline oracle gate\n')
 put('复用 normal OUTBOUND、deviation RETURN、synergy、late、value_failure 五个不同 native parent states，15 个 frozen candidates，30 个 qualified COMMITTED/ROLLING-P outcomes；14 个 candidate 通过原 hard screen。未生成新的 physics outcome。候选 pool 是原保存 CEM 的有限高信息子集，大小 2–5，并非完整 CEM population。late 来自旧 DEV，其余有 heldout/extra 来源；不能把全部五池称为新模型独立 HELDOUT_TEST。没有创建新的 split，旧 split 未改写。五个状态共享同一个 Human truth。\n')
 put('预注册 GO：至少两个不同 parent 修复 P 的错误 top-1 / 正向降低 accepted-pool selection regret（容差 1e−6 N·s），且无新损害。单 parent 或仅改变非最优候选的顺序不足。oracle 只对 accepted candidates 排名；`P + true residual = actual full cost`，不进入线上 controller，不绕过 screen。\n')
 for contract in ('ROLLING_P','COMMITTED'):
  put('### '+contract+(' — PRIMARY' if contract=='ROLLING_P' else ' — diagnostic')+'\n')
  rows=[]
  for s in gate['states']:
   c=s['comparisons'][contract]
   for method in ('P','P_V1','P_ORACLE'):
    m=c[method];rows.append([s['state'],method,m['accepted_size'],m['top1_index'],f'{m["selected_actual_cost"]:.6f}',f'{m["accepted_pool_regret"]:.6f}',f'{m["screening_loss"]:.6f}',f'{m["rank_correlation"]:.3f}'])
  table(['parent','method','accepted n','top1 local index','selected actual N·s','regret N·s','screen loss N·s','rank ρ'],rows)
  s=gate['summary'][contract]
  put(f'P → oracle 总 accepted-pool regret：**{s["accepted_P_regret_sum_Ns"]:.6f} → {s["accepted_oracle_regret_sum_Ns"]:.6f} N·s**；修复 {s["corrected_bad_selections"]}，新损害 {s["newly_damaged_selections"]}，top1 changes {s["top1_changes"]}，top3 set/order changes {s["top3_set_changes"]}/{s["top3_order_changes"]}；P mean rank ρ={s["mean_P_rank_correlation"]:.3f}。GO=False。\n')
 put('每个候选的 exact identity/plan hash、完整排序、top-k identities、top-k mean actual cost 均在 '+link('ORACLE_GATE.json')+'。四个池的 top3 覆盖全部 accepted candidates，top-k set 指标辨别力很低；synergy 的 oracle 改变次优顺序，但不改变选择成本。screen loss 定义为 accepted 最低实际成本 − 全部已资格化 frozen subset 最低实际成本；normal COMMITTED 的 14.424536 N·s 是 screening loss，不能归为 ranking gain。\n')
 put(f'![Oracle selection regret]({DEST}/ORACLE_GATE_REGRET.png)\n')
 put('## Full-plan residual 与 phase / timing / integration\n')
 rows=[]
 for c in ('COMMITTED','ROLLING_P'):
  s=d['summary'][c];a=s['min_median_max_Ns'];rows.append([c,*[f'{x:.6f}' for x in a],f'{s["pooled_RMS_Ns"]:.6f}',f'{s["within_parent_centered_RMS_Ns"]:.6f}'])
 table(['contract','min','median','max','all15 RMS','within-parent centered RMS'],rows)
 table(['parent','committed mean / within range N·s','rolling mean / within range N·s'],[[s['state']]+[f'{d["summary"][c]["parent_mean_residual_Ns"][s["state"]]:.6f} / {d["summary"][c]["within_parent_residual_range_Ns"][s["state"]]:.6f}' for c in ('COMMITTED','ROLLING_P')] for s in gate['states']])
 put('Residual 确实有 state、candidate/plan 依赖，不是所有候选共用的 additive bias。然而残差结构本身不代表 top-1 decision leverage。normal 的 rolling 范围还包含被 screen 拒绝的候选，不能把该范围直接当可选行动的收益。\n')
 rows=[]
 for c in ('COMMITTED','ROLLING_P'):
  for s in gate['states']:
   rr=[r for r in d['rows'] if r['state']==s['state']]
   rows.append([c,s['state']]+[f'{np.mean([r["residual_by_phase"][c][k] for r in rr]):.6f}' for k in ('OUTBOUND','HOLD','RETURN')])
 table(['contract','parent','OUTBOUND mean Δ N·s','HOLD mean Δ N·s','RETURN mean Δ N·s'],rows)
 put('COMMITTED 反映原全计划预测的实际模型差；较大的 OUTBOUND/RETURN 分量主导残差。ROLLING-P 在 synergy/late 出现负 RETURN 分量，抵消正 OUTBOUND 分量。逐 phase 和全任务均验证：`Delta_rollP = Delta_committed + (J_actual_rollP - J_actual_committed)`。不能把 rolling residual 全部叫作模型误差。\n')
 put('Integration：从既有 TASK trace 对 physical cuff-force norm 作左端点积分；第一段按 fork physical_time 精确截断，排除 inherited prefix。phase-wise 成本之和匹配 saved remaining J_F（<1e−6）；全 TASK 积分与原 metric J_F 同样通过检查。force integration 口径保持不变，无新采样或重新定义目标。\n')
 timing=[]
 for c in ('COMMITTED','ROLLING_P'):
  for phase in ('OUTBOUND','HOLD','RETURN'):
   v=[r['model_minus_actual_phase_duration_s'][c][phase] for r in d['rows']]
   timing.append([c,phase,f'{min(v):.6f}',f'{max(v):.6f}',f'{np.mean(v):.6f}'])
 table(['contract','phase','model−actual remaining duration min s','max s','mean s'],timing)
 put('保存 model scheduler segments（task start/end、force cost）和 physical phase duration，可逐 candidate 检查 reference/scheduler timing。模型内部事件边界与 native phase clocks 的差异不等同于全任务 completion 边界遗漏；此前 audit 的全模型 completion clock 对应检查仍保留原解释。timing、request/bridge、tracking/contact approximation 与 continuation replacement 相互耦合，当前证据不能唯一拆成互相独立的“timing cost”和“force model cost”。因此记录真实 phase/time/integral，而不伪造加法因果归因。未来真值 tracking/F/M/clearance/timing 仅在 offline metric_metadata，用于 outcome 资格和诊断，不作网络输入。\n')
 put(f'![Full-plan residual phases]({DEST}/FULL_PLAN_RESIDUAL_PHASES.png)\n')
 put('所有 15 个候选、两 contract 的 model/actual/full residual/phase 分量、parent/plan hash、原 outcome/trace 路径及 SHA 均在 '+link('FULL_PLAN_ERROR_DECOMPOSITION.json')+' 与 '+link('ORACLE_CANDIDATE_DIAGNOSTICS.csv')+'。\n')
 put('## V1 vs V2、模型与 closed-loop 资格\n')
 rows=[]
 for c in ('COMMITTED','ROLLING_P'):
  m=comparison['contracts'][c]['forecast_RMSE_Ns'];s=gate['summary'][c]
  rows.extend([[c,'P',f'{m["P"]:.6f}',f'{s["accepted_P_regret_sum_Ns"]:.6f}'],[c,'P+V1',f'{m["V1"]:.6f}',f'{s["V1_regret_sum_Ns"]:.6f}'],[c,'P+V2','N/A — NOT_TRAINED','N/A'],[c,'P+ORACLE','0','0']])
 table(['truth comparator','method','accepted14 forecast RMSE N·s','5-pool regret sum N·s'],rows)
 put('上述 RMSE 使用相同 14 个 accepted candidates，区别于前文包含 screen-rejected row 的 all15 residual RMS。V1 权重和原 committed labels 完全保留；将其预测与 rolling-P truth 比较，是本次声明的额外诊断 comparator，不是重定义 V1 的训练目标或原 heldout 结果。\n')
 put('V1 两 contract 均 helpful flips=0、harmful flips=1（value_failure）。在 PRIMARY，P/V1 regret 为 0/5.476548 N·s；V1 的较小局部 RMSE 仍可能导致错误 top-1。当前不能声称拟合 V2 比 V1 更接近 oracle，因为 V2 尚未拟合。\n')
 put('- ridge：NOT_TRAINED，mandatory oracle gate FAIL。')
 put('- MLP 2×128：NOT_TRAINED，同一门控原因。')
 put('- TRAIN/DEV/HELDOUT_TEST：NOT_CONSTRUCTED；parent-group split 规则已冻结但未执行；无 fitted heldout 数值。')
 put('- CLOSED LOOP：NOT_RUN_GATE_FAILED；P vs P+V2 cold paired qualification 未运行，不能作 promotion 或标记 MODEL_INADEQUATE。\n')
 put('## Repetition memory、保全与资源\n')
 put('V_n 仅评价 repetition n 的 remaining cost。结束后允许保留 best-so-far K3 plan、actual outcomes、G prior、dataset、V/correction parameters、Human belief；下一轮 V_{n+1} 仍只评价新一轮。future adaptation benefit / future-repetition reward 不进入本 target；本轮不实现跨 repetition online adaptation。详见 '+link('REPETITION_MEMORY_CONTRACT.json')+'。\n')
 put(f'保全检查 **PASS**：V1+audit {verification["V1_files_checked"]} files 按 size/mtime 检查，其中 <20 MiB 文件再验证 SHA；无改写、删除或新增。main scientific sources、Git HEAD/branch/status/index/cached diff 保持 baseline。30 outcomes 均 qualified，first-segment proof PASS，全部积分匹配，PRIMARY 在 oracle 前选定，没有 oracle online controller、训练或新增 physics。没有启动 physics owner，结束时无本包 physics/training worker。'+link('PRESERVATION_AND_VERIFICATION.json')+'、'+link('COMPUTE_RESOURCE_LEDGER.json')+' 保存逐项证据；RSS 指标仅指 verifier 进程，不冒充全系统峰值。\n')
 put('新目录独立保存 preregistration、语义、feature prototypes、oracle、分解、图表及代码。SOURCE_AND_EVIDENCE 保留初始代码 hash；CODE_FINAL_MANIFEST 另存最终辅助代码 hash，不覆盖原冻结证据。raw traces 仍留在原只读 WSL evidence，交付引用完整路径与 SHA，不重复制造大 trace。\n')
 put('## Negative results（4 项）\n')
 put('1. PRIMARY oracle 的 top-1 / regret 收益为零：0 个错误选择被修复。')
 put('2. COMMITTED 仅一个 RETURN pool 改善 11.204131 N·s，不满足多 parent 门槛，未事后切换 PRIMARY。')
 put('3. Oracle 不能绕过 hard screen；COMMITTED normal 仍有 14.424536 N·s screening loss。')
 put('4. 五个有限子池、共享 Human、明确 seeded continuation 限制外推；不支持完整 CEM、独立 Human 或 V2 闭环收益声明。\n')
 put('V2 STATUS: **V2_NOT_DECISION_RELEVANT**，仅针对此已声明证据范围。\n')
 put('NEXT（唯一建议）：'+NEXT+'\n')
 put('REPORT PATH: '+link('REPORT.md')+'\n')
 put('**STOP。** Oracle FAIL 后未进入 dataset construction、training、额外采集或 closed-loop dispatch。')
 (NEW/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 status=dict(status='COMPLETE_EARLY_ORACLE_STOP',V2_STATUS='V2_NOT_DECISION_RELEVANT',scope=gate['summary']['ROLLING_P']['scope'],primary='ROLLING_P',oracle_gate='FAIL',training_authorized=False,new_physics_attempts=0,training_runs=0,new_weights=0,dataset='NOT_CONSTRUCTED',closed_loop='NOT_RUN_GATE_FAILED',verification='PASS',next=NEXT,report=str(NEW/'REPORT.md'),completed_unix=time.time(),STOP=True)
 save(NEW/'FINAL_STATUS.json',status);save(NEW/'STATE.json',dict(status='STOPPED',STOP_DISPATCH=True,reason='mandatory oracle gate failed',active_owned_workers=[],training_authorized=False,unix=time.time()))
 (NEW/'PROGRESS.md').write_text('V2 package complete: oracle FAIL; STOP.\n\n0/40 new high-fidelity attempts; 0 training; 0 closed-loop.\n\nSee REPORT.md and FINAL_STATUS.json.\n')
 print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
