"""Build Chinese handoff from frozen saved evidence only; no physics/PPO."""
from pathlib import Path
import json,datetime,statistics,hashlib
from common import put,ROOT
from checkpoints import contract
from preflight import runtime

def read(n):return json.loads(Path(n).read_text())
def doc(n,s):Path(n).write_text(s.strip()+'\n')
acc=read('ATTEMPT_ACCOUNTING.json');eps=read('audit/EPISODE_ACCOUNTING_SUMMARY.json');pkg=read('PACKAGE_VERIFICATION.json');res=read('RESOURCE_USAGE.json');parity={k:read('audit/PARITY_'+k+'.json') for k in ('slow','maximal','random')};timing=read('audit/TASK_TIMING_RAW_EVIDENCE.json');now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
labels={'FORCE_INTEGRATION_PASS':'PASS','G4_PASS':'FAIL','EXECUTION_PASS':'FAIL','PPO_UPDATE_PASS':'NOT_RUN','CHECKPOINT_RESUME_PASS':'NOT_RUN','TRAINING_PILOT_READY':'FAIL'}
gates={'G1':{'status':'PASS','evidence':'9 independently audited real MuJoCo episodes; original native safety limits preserved','scope':'observed nominal case, not robustness or hardware safety'},'G2':{'status':'FAIL','evidence':'random TASK20.165000000054s fails unchanged19.030s ±0.050s frozen regression'},'G3':{'status':'PASS','evidence':'two full maximal-action episodes, each19.030000000049s; deterministic development repeats'},'G4':{'status':'FAIL','protocol_logic':'PASS','natural_specific_failure_coverage':'NOT_EVALUABLE','evidence':'G4_TERMINATION_REWARD_AUDIT.md; TEST_ONLY does not close all required real failure paths'},'G5':{'status':'PASS','evidence':'EXECUTION_CONTRACT_TESTS.json actor AST allowlist + causal certificate flags; actor41D, no future Human truth'},'G6':{'status':'NOT_RUN','mechanism_static_review':'implemented, not sufficient for cross-process reliability qualification','evidence':'CHECKPOINT_RESUME_AUDIT.json'},'G7':{'status':'PASS','evidence':'GUARD_UNIT_RESULTS.json + audit/RESOURCE_TIMEOUT_TEST_ONLY.json + all physical guards closed; minRAM28.709GiB'}}
validation={**labels,'training_pilot_ready_boolean':False,'gates':gates,'force_independent_episodes_passed':sum(e['independent_force_pass'] for e in eps),'observed_execution_core_episodes_passed':sum(e['independent_execution_core_pass'] for e in eps),'parity':{k:x['pass'] for k,x in parity.items()},'full_frozen_execution_regression_pass':False,'runtime':runtime(),'contract_sha256':contract(),'physics_execution_sha256':pkg['physics_execution_sha256'],'original_contract_relaxed':False,'positive_PPO_started':False,'generated_asia_shanghai':now,'terminal_status':'STOPPED_QUALIFICATION_BLOCKED','no_more_physics_or_training':True,'limitations':['natural HOLD failure, dedicated phase timeout and actual absolute-safety failure reachability not established','all episodes are development validation, not heldout robustness evidence','host realtime NOT_EVALUABLE','no positive PPO/update/checkpoint qualification']};put('VALIDATION_RESULTS.json',validation)
neg=read('runs/ppo_negative_gate_01/END.json');no_model=not Path('runs/ppo_negative_gate_01/forbidden_training').exists();put('PPO_SMOKE_RESULTS.json',{'status':'NOT_RUN','PPO_UPDATE_PASS':'NOT_RUN','reason':'G2/EXECUTION and G4 not PASS; user requires all gates before positive PPO','gradient_updates':0,'optimizer_steps':0,'PPO_train_calls':0,'training_environment_decisions':0,'training_native_steps':0,'training_episodes':0,'planned_training_seed':20261021,'actual_training_seed':None,'teacher_or_B_H150_weights_used':False,'policy_sha256':None,'model_sha256':None,'checkpoints_created':[],'negative_gate':{'evidence':'runs/ppo_negative_gate_01','returncode':neg['returncode'],'error':'CURRENT_RUNTIME_QUALIFICATION_REQUIRED','no_model_or_environment_output_created':no_model,'pass':neg['returncode']==1 and no_model},'qualification_physics_counts_separate':{'episodes':acc['actual_episodes'],'native_steps':acc['native_steps'],'RL_decisions':acc['RL_decisions']},'learning_success_claim':False,'formal_pilot_started':False})
put('CHECKPOINT_RESUME_AUDIT.json',{'status':'NOT_RUN','CHECKPOINT_RESUME_PASS':'NOT_RUN','reason':'No gate-approved PPO run and no trained checkpoint; do not fabricate a restore claim from random weights','checkpoint':None,'policy_hash':None,'optimizer_state_restored':None,'RNG_restored':None,'progress_restored':None,'new_process_resume_rollout_updates':0,'mechanism_review':{'save_atomic_generation_commit_marker':True,'policy_and_Adam_declared_saved':True,'SB3_local_source':'stable_baselines3/common/on_policy_algorithm.py:344 includes policy and policy.optimizer','python_numpy_torch_RNG_save_load':True,'SHA256_and_contract_rejection_present':True,'counters_num_timesteps_and_n_updates_checked':True,'fresh_episode_semantics_declared':True,'mid_episode_simulator_restore':False,'exact_optimizer_state_runtime_equality':'NOT_RUN','cross_process_stochastic_sequence_equality':'NOT_RUN','continuation_gradient_update':'NOT_RUN'},'static_followups':['train.py records train-call count and SB3 epoch count; actual optimizer.step calls must be counted directly during the future smoke','fresh physical episode resume must be checked separately from forbidden claims of bit-exact mid-episode restoration'],'no_random_checkpoint_substituted_for_trained_checkpoint':True})
coverage={
 'A_normal_complete':{'natural':'PASS','evidence':'runs/repair_reset_maximal_01/physics, episodes1 and2','exact19_030_pass':True},
 'B_OUTBOUND_timeout':{'natural':'NOT_EVALUABLE','TEST_ONLY_real_MuJoCo':'PASS','evidence':'runs/repair_outbound_TEST_ONLY_01/physics','reason':'TIMEOUT_OUTBOUND atTASK10.000s; phase-exit suppression, not a natural legal-action failure'},
 'C_HOLD_not_established':{'natural':'NOT_EVALUABLE','TEST_ONLY_sensor_clock':'PASS','evidence':'REPAIR_BOUNDARY_TESTS.json + G4_UNIT_RESULTS.json','reachability':'HOLD candidate ignores RL action; no authorized external perturbation. This does not prove global unreachability across all possible entry states. Prior exit-suppression physics aborted at18.700s NO_FEASIBLE before HOLD timeout.'},
 'D_RETURN_timeout':{'natural':'NOT_EVALUABLE','TEST_ONLY_real_MuJoCo':'PASS','evidence':'runs/repair_return_TEST_ONLY_01/physics','reason':'TIMEOUT_RETURN atTASK20.025s; RETURN duration10.000s'},
 'E_zero_progress_stagnation':{'natural':'PASS','evidence':'runs/repair_hold_01/physics and runs/repair_slow_01/physics','reason':'zero action fails at0.005s; slow fails at9.820s with no completion bonus'},
 'F_consecutive_rejections':{'natural':'PASS','evidence':'slow final two native request outcomes FAILED, then original NO_FEASIBLE terminal','TEST_ONLY_20_rejections':'PASS G4_UNIT_RESULTS.json','limitation':'does not claim a new production rejection-count threshold; original failure is planner infeasibility'},
 'G_absolute_safety_stop':{'natural':'NOT_EVALUABLE','TEST_ONLY_original_threshold':'PASS','TEST_ONLY_real_MuJoCo_chain':'PASS','evidence':'SAFETY_AUTHORITY_TESTS.json + runs/repair_safety_TEST_ONLY_01/physics/INJECTION.json','reason':'synthetic causal20ms acceleration1.01x original limits triggers original TASK_ACCELERATION_LIMIT atTASK1.010s; true plant was not forced unsafe'},
 'H_legal_fallback':{'natural':'PASS','evidence':'maximal one and random five committed brake/hold/fresh-resume cycles; raw receipts/certificates audited'},
 'I_partial_rewards':{'natural':'PASS','evidence':'all6 partial episodes (3 natural,3 TEST_ONLY) independently reconstructed, total progress0, completion-10, nonpositive force/variation costs'},
 'J_reset_independence':{'natural':'PASS','evidence':'runs/repair_reset_maximal_01/physics/RESULT.json all4 reset_checks true; per-episode reset and owner_close files'},
 'global_timeout':{'natural':'NOT_EVALUABLE','TEST_ONLY_logic':'PASS','evidence':'REPAIR_BOUNDARY_TESTS.json + G4_UNIT_RESULTS.json','reachability':'With only3 phases each bounded by10s, no intervening unclocked task stage, sum<=30s. Global30s is not independently earlier than all phase bounds; simultaneous-boundary/floating cases do not supply a distinct natural global-timeout episode.'}}
put('G4_PHYSICAL_VALIDATION.json',{'status':'FAIL','G4_PASS':'FAIL','protocol_logic_pass':True,'all_key_real_failure_paths_closed':False,'natural_specific_failure_reachability':'NOT_EVALUABLE','coverage':coverage,'contract_sha256':contract(),'runtime':runtime(),'qualification_rule_preserved':'Inherited qualify.py requires complete real failure matrix; synthetic cases not promoted to natural evidence','no_failures_fabricated':True})
put('RL_EXECUTION_VALIDATION.json',{'status':'FAIL','EXECUTION_PASS':'FAIL','observed_native_execution_core_pass':True,'parity_pass':all(x['pass'] for x in parity.values()),'independent_core_episode_checks':len(eps),'frozen19_030_random_regression':'FAIL','random_TASK_s':timing['random']['task_s'],'maximal_TASK_s':timing['maximal']['task_s'],'action_mapping_changed':False,'physical_parameters_changed':False,'original_planner_and_certificates_changed':False,'governor_commit_receipts':{k:v['governor_receipt_count'] for k,v in timing.items()},'governor_total_added_delay_s':{k:v['governor_delay_added_s'] for k,v in timing.items()},'host_realtime':'NOT_EVALUABLE','evidence':['audit/PARITY_slow.json','audit/PARITY_maximal.json','audit/PARITY_random.json','audit/FINISHED_EPISODE_AUDITS.json','audit/TASK_TIMING_RAW_EVIDENCE.json']})
put('READINESS.json',{'G4_TERMINATION_REWARD_PASS':'FAIL','RL_EXECUTION_CONTRACT_PASS':'FAIL','RL_TASK_REACHABILITY_PASS':'PASS','all_G1_G7_pass':False,'gates':gates,'contract_sha256':contract(),'runtime':runtime(),'reason':'Do not train: frozen19.030 random regression fails and required natural G4 coverage not closed','positive_training_authorized':False})
rows='\n'.join(f"| {e['directory'].split('/')[1]} / {e['directory'].split('/')[-1]} | {'TEST_ONLY' if e['category'].startswith('TEST') else '自然合法输入'} | {e['status']} | {e['task_s']:.3f} | {e['RL_decisions']} | {e['native_steps']} | {e['force_N_s']:.9f} |" for e in eps)
statusrows='\n'.join(f'| {k} | {v} |' for k,v in labels.items())
doc('ROOT_CAUSE_ANALYSIS.md', '''# 根因与边界

证据先于修复：`audit/HISTORICAL_RAW_DIAGNOSIS.json` 从上一轮完整 trace 与在线 tick 独立左积分，未使用 summary 作为真值。

slow episode 的 trace TASK 行1779：native时间18.944999999999446s，TASK8.895000000000193s，下一行时间完全相同；力范数111.02181066943028N。旧行预写入0.5551090533471514N·s。原 `_execute_interval` 在 `CURRENT_MODEL_ACTIVATION_REVALIDATION` 处拒绝，未apply、未推进native physics。异常分支置 `execution_rejected_before_apply=True`，保留行后回到同一物理边界，但未撤销预写的5ms成本。正确归属为零时长、零积分。

这不是 OUTBOUND/HOLD phase交接、episode终止或reset重复累计；出错发生在同一OUTBOUND内部的admission拒绝。自然terminal行本身成本为0，reset前后的force/reward累计器独立清零。重复callback在wrapper按实际dt=0积分，未重复收费。

修复：拟执行行初始积分为0；成功执行后才按 `actual_interval_duration_s` 计入；异常只按真实已推进native时长计入。拒绝记录完整保留，未减去固定常数。未改5ms左积分定义。

另发现同一重复行使moment summary用 `min(executed_interval_count,len(rows)-1)` 截断，漏掉最后真实区间0.04000901910159N·m·s；改为全部相邻边界左积分，零时长行自然贡献0。旧114.71605487166386，独立/修复后114.75606389076545N·m·s。

独立deadline反例：原reference-safe handoff对OUTBOUND/RETURN在10.005s、reference_ready=True时仍接受HOLD/COMPLETE。新检查在原10s期限已经超过时先ABORTED，精确边界惯例沿用原terminal commit；没有放宽期限。见 `audit/DEADLINE_BEFORE_AFTER_TEST_ONLY.json`。它不是random20.165s的原因，后者各phase均小于10s。

random与maximal的总TASK差1.135s，来自不同合法progress提议、5次而非1次planner拒绝/fallback及到达/settling时刻。没有governor附加减速，实际receipt的delay_added_s合计0；无超时收尾或commissioning混入。原物理任务终止器为10s/phase与30s/task；19.030s±0.050s另见封存执行回归。当前代码未把19.030s编码为全局终止deadline。保持两者证据并报告执行FAIL，不能把30s改写为一个历史上存在的19.030s配置。

科学限制：9个episode是固定development输入和TEST_ONLY，不是新held-out研究。一次隔离修复周期已完成；没有通过调参改变行动含义来强迫random达到19.030s。
''')
doc('FORCE_INTEGRATION_REPAIR.md', '''# 累计力与reward归属

| slow episode量 | 修复前 | 独立raw / 修复后 |
|---|---:|---:|
| TASK左积分 N·s | summary928.0810851870452 | 927.5259761342978 |
| 错误单行 N·s | 0.5551090533471514 | 0（dt=0） |
| wrapper累计 N·s | 927.5259761342987 | 927.5259761342987 |
| reward force项 | -0.1855051952268596 | -0.1855051952268596 |
| reward总和 | -10.187928954054334 | -10.187928954054334 |
| moment summary N·m·s | 114.71605487166386 | 114.75606389076545 |

修复后slow summary force927.5259761342987与独立trace积分差9.094947017729282e-13N·s。不是按固定0.555109抵扣；每个拟执行事件只拥有实际推进的物理区间。

完整TASK与分phase复算：maximal OUTBOUND725.825779277981、HOLD54.39433879320881、RETURN669.61994288184，合计1449.840060953029N·s；random依次848.6989146009525、54.58529223632176、713.4114302774352，合计1616.69563711471N·s；slow仅OUTBOUND927.5259761342978。结束边界成本0。

`force_audit.py`完全不调用runtime积分或reward函数，从完整raw逐边界重算force/moment，再与独立online tick、summary和reward比较。所有9个episode均PASS，完整结果位于每个episode的 `FORCE_INDEPENDENT_AUDIT.json`。`audit_reward_physical.py`另从保存的transitions与public contract验证各reward项、吸收终态和无timeout bootstrap。

历史PPO reward未受这项重复积分影响：wrapper使用tick时间差乘前一传感器力，并非读取summary或interval cost。历史没有PPO训练，gradient update为0。若错误summary被用于后续监督标签/跨策略力成本比较，会污染标签与资格评价。对slow的13条现有native Learning记录逐字段比较，force、duration、completion及state均相同；仅candidate/selected_plan中的host reference_apply_ns不同，见 `audit/LEARNING_DIFFERING_FIELDS.json`。未证明所有未提供的外部Learning消费者都安全。

terminal observation为41维零向量；真实终端力仅保留在评价证据。reset前后force/moment/reward/动作队列/计数器清零，第二episode不继承状态。原始拒绝、失败与partial均保留。trace_node_count包含失败尝试，旧boundary_interval_relation_holds在含额外拒绝行时可为false；独立receipt ownership验证真实区间数，而不是将每一trace行当成已执行5ms。

物理回归：slow/maximal/random共316660个native状态与历史逐样本一致（q/dq、torque、contact、reference与force最大差0）；force修复没有改变Human真实运动、控制或cuff物理。
''')
doc('TASK_TIMING_AUDIT.md', f'''# TASK时序审计

| 输入 | OUTBOUND | HOLD | RETURN | TASK总和 | native整episode |
|---|---:|---:|---:|---:|---:|
| maximal | 9.005s | 1.020s | 9.005s | 19.030s | 29.080s |
| uniform random | 9.260s | 1.020s | 9.885s | 20.165s | 30.215s |

两者TASK native起点均约10.050s；之前是commissioning/recovery。20.165s不是host wall time，也不含准备/结束阶段。random单episode内部host wall为82.074s，外guard84.160s；不得与TASK仿真时间混用。完整原始phase开始/结束和source/commit在 `audit/TASK_TIMING_RAW_EVIDENCE.json`。

random共30次native RL decisions，25次ACTIVATED、5次FAILED；其中4次candidate会使已发reference回退，1次目标进入既有shank-table几何。均走原certificate/admission/fallback，未直接执行被拒动作。maximal为14次、13次激活、1次几何失败。random的5段fallback commit→fresh resume共1.310s，maximal1段0.255s。这个差1.055s不能直接等同于因果贡献：不同动作改变了其余运动与settling，未做反事实消融。可直接精确归属的phase差为OUTBOUND+0.255s、RETURN+0.880s。

原governor实际存在于TASK receipt.reference_progress：maximal3801条、random4024条commit；两者附加delay合计0，delayed intervals均0。因此本例不是governor减速造成。顶层reference_governor_records为空，不能据此误判governor未执行；证据使用实际receipt。科学source→activation native age约5ms；host activation_age_ms分别约24–38ms和25–68ms，含不同host调度成本，不能互相替代。均未触发100ms过期。

最终scientific commit记录：maximal actual_return_elapsed9.005s、TASK19.030s；random分别9.885s、20.165s；原期限10s与30s，reason=None。没有等待timeout才宣布success。封存verify_physics.py额外要求完整任务duration19.030±0.050s，random仍FAIL；该检查未改。

原19.030回归合同保持且未通过。源码运行参数实际为30s/task，不能声称19.030已经是runtime hard deadline。缩短任务、提高速度、改动作fraction、把允许时间改20.165，或仅删除random回归，都会改变现有科学问题，均未实施。该不一致是正式PPO启动阻塞，success reward不能被当成19.030回归通过。
''')
g4rows='\n'.join(f"| {k} | {v.get('natural')} | {v.get('TEST_ONLY_real_MuJoCo',v.get('TEST_ONLY_sensor_clock',v.get('TEST_ONLY_original_threshold',v.get('TEST_ONLY_logic','—'))))} | {v.get('evidence')} |" for k,v in coverage.items())
doc('G4_TERMINATION_REWARD_AUDIT.md', f'''# G4终止与reward

整体G4_PASS=FAIL；协议/数学检查PASS，必要自然物理失败覆盖仍NOT_EVALUABLE。沿用上一轮qualify.py要求完整real failure matrix的门，不能把注入检查换成自然证据。

| 路径 | 自然物理 | 明确标记TEST_ONLY | 直接证据 |
|---|---|---|---|
{g4rows}

OUTBOUND/HOLD/RETURN的已超过10s handoff反例已修复并重测；安全优先、global30s及吸收态/finite-horizon terminated=True,truncated=False均有TEST_ONLY检查。正常成功和自然早停均通过真实step接口；所有终端只在最后transition置terminated，后续step拒绝重复完成/bonus。

自然失败：zero-action在0.005s被原reference-regression规则拒绝；slow在9.820s因无可行schedule终止；RETURN zero在10.220s因reference regression终止。slow最后两次planner请求连续FAILED；不是伪造新的REPEATED_REJECTION原生原因。20次拒绝是单独的计数/fallback unit，不能扩展为自然物理压力结论。

本轮TEST_ONLY真实MuJoCo：phase-exit suppression使OUTBOUND在10.000s TIMEOUT_OUTBOUND、RETURN在TASK20.025s TIMEOUT_RETURN。安全测试只将monitor的一个有效20ms acceleration字段设为原限值1.01倍，原authority于1.010s触发TASK_ACCELERATION_LIMIT。原threshold、plant与actor数据未改；这个成功终止测试不是自然超限或新的物理安全证明。

HOLD不成立：原action generator在HOLD忽略actor action，只返回既定hold目标。无授权外部扰动；9个有界episode未观察到自然HOLD失败，不能声称对全部可能HOLD入口已证明不可达。独立sensor-clock输入使dwell不成立并于原10s超时，duplicate timestamp不增加dwell。上一轮HOLD exit suppression真实物理先在18.700s触发NO_FEASIBLE，不能标作TIMEOUT_HOLD。

global30s：三段各10s且无不计时中间阶段，原phase bound通常先于或同时约束global bound；修复后不能通过晚到phase交接逃过它。该结构不能提供独立的早发global超时自然case，边界浮点并发情况仍单独保留TEST_ONLY，不伪造自然失败。

每个partial累计progress回到0、completion=-10，force与variation是非正成本；不存在少动/停住拿成功奖。所有9个raw reward、force和terminal独立重算通过。reset真实双episode检查四项均PASS。自然超时/HOLD/绝对安全的可达性仍未完整闭合；这是资格范围限制，不能通过测试名称或注入结果消除。
''')
doc('RL_EXECUTION_PARITY_AUDIT.md', '''# 原执行链独立回归

PARITY_PASS=PASS（已观察输入）；EXECUTION_PASS=FAIL（完整冻结时长回归未通过）。科学仿真执行不代表host实时资格，host realtime为NOT_EVALUABLE。

`parity_audit.py`逐项读取历史与本轮完整raw。slow79480、maximal116320、random120860个native状态，共316660行；时间、native Human q/dq、实际command torque、contact均最大差0。trace的reference q/dq/ddq、estimated/true state、cuff force/moment和applied torque也最大差0；完整command_receipts的apply/native count、physics边界、source timestamp与torque完全一致。三个输出见audit/PARITY_*.json，容差1e-12，实测差0。

全部9个episode还独立核对唯一native所有权、receipt扭矩、source age、100ms同epoch/model admission、40ms bridge、current-state certificate、executor退出及真实Human运动。原ROM0–125°，dq45/75°/s，ddq300/600°/s²（native、5ms、20ms），force200N、moment60Nm、torque、clearance、contact均通过已观察case；无MuJoCo warning。TEST_ONLY安全事件来自合成monitor字段，真实plant并未违反这些物理限值。

414个封存source载荷中412个逐字节不变，只改runtime统计和reference-safe deadline优先级两个文件。Human/robot/cuff资产、模型参数、native0.25ms、controller5ms、Planner/certificate、current-state admission、receipt governor、40ms bridge、100ms lifecycle、source age、causal receipt/native ownership及安全阈值均未修改。各code hash与diff见CODE_CHANGE_MANIFEST.json和audit/ALL_CODE_CHANGES.patch。

新隔离版本rl_b_native_event_g4_repair_v1已登记，旧资格没有自动沿用；RL action仍是每次native planner event的两个最大progress fraction。没有变成50ms动作接口，没有B/H150模仿权重。deadline过期结果收紧，正常合法输入物理含义保持。物理重复回归用于修复验证，不能冒充独立held-out稳健性研究。

完整任务maximal两次19.030s；random复现20.165s，仍不满足19.030±0.050s封存标准，因此不给EXECUTION_PASS。核心raw审计通过不覆盖这项失败。
''')
doc('NEXT_RESEARCH_DECISION.md', '''# 下一轮决策

TRAINING_PILOT_READY=FAIL（NO）。当前可直接启动正式PPO Pilot的episode=0、seed=0；本轮已STOP，不自动启动后续运行。

唯一建议下一步：针对“19.030s固定执行回归”与“native-event两fraction动作+原10s/phase、30s/task终止器”的合同不一致，制定并冻结一个可检验的执行修复规范；保持19.030要求、任务和物理约束，明确失败动作的终止/评价，再用新环境版本闭合G4与执行门。若实现需改变RL动作含义，应显式登记并重新验证，不能删除失败回归或继承旧标签。HOLD/安全的自然证据与TEST_ONLY范围需要在同一资格规范中明确，不能靠制造超限来补证。

门全部通过后，先1个训练seed20261021、最多32个native-event rollout decisions的最小PPO smoke，直接计数optimizer.step，保存policy/Adam/RNG/进度，在新进程恢复并再做有限update，冻结checkpoint做有限完整评价。未完成这些之前正式Pilot仍为0。本建议不授权自动执行。

在未来smoke/resume通过后，当前CCX33首个有限Pilot建议1个seed、最多32个训练episode，另4个冻结policy完整评价episode；保持当前已实现的单物理环境。单环境完整任务本轮内部host wall约77–82s，外守护maximal两次156.76s。36个完整任务约46–49分钟纯物理量级，另留PPO、checkpoint与审计余量，估计60–75分钟，硬cap90分钟。PPO开销未实测，该预算是规划估算；partial长度与动作频率会改变吞吐。不要按50ms决策换算，不建议未经资格验证直接双环境PPO。原双环境1.93倍只是历史评价吞吐，本轮未复测。

不升级/购买云资源，不自动开展百万步训练，不接触正式B/H150。后续若要多seed科学结论，应另行冻结预算与held-out划分；当前1seed smoke/Pilot不支持泛化或已学会任务声明。
''')
doc('REPORT.md', f'''# iHEAR RL-B G4隔离修复与资格复核

完成隔离修复和9个真实MuJoCo episode，训练启动门仍未通过，已STOP。开始2026-10-20 14:47:23（Asia/Shanghai），报告生成{now}。未为了耗满预计2–3小时而扩展搜索。最后物理结束2026-10-20 15:01:28.734，之后只做独立重算、负向门和封存；4小时硬上限/最后30分钟物理启动禁区未触及。

| 独立资格 | 结果 |
|---|---|
{statusrows}

TRAINING_PILOT_READY=FAIL即NO。G4协议测试PASS，但必要自然失败覆盖没有闭合；EXECUTION核心物理/接口对照PASS，但原random时长回归FAIL。没有正向PPO尝试。

1. **0.555109根因**：OUTBOUND TASK8.895s admission在apply前拒绝，trace预写的111.021810669N×5ms成本未清除；下一行同一native时间，正确dt=0。不是phase边界、terminal或reset。保留完整拒绝事件，按实际执行区间归属修复。
2. **summary与raw是否一致**：是。slow独立927.5259761342978、修复summary927.5259761342987N·s，差9.09e-13；9/9 episode force/reward独立审计PASS。另修复moment索引漏掉末区间0.040009019N·m·s。
3. **历史reward影响**：这项重复积分没有进入wrapper reward；slow force reward前后均-0.1855051952268596，总reward-10.187928954054334。历史PPO更新为0。summary消费者可能生成错误Learning标签；现有13条native Learning的force/state/完成字段不变，只有host apply时间戳变化，外部消费者未声称全部安全。
4. **random20.165s原因**：真实TASK，9.260+1.020+9.885s；比maximal多0.255s OUTBOUND和0.880s RETURN。30次提议、5次planner失败与合法fallback，而maximal14次/1次。receipt governor附加delay合计0；无timeout收尾或准备时间混入。不同progress提议/运动/settling与fallback共同造成时差，未用反事实实验虚报精确因果拆分。
5. **19.030合同**：保持，未放宽，但random未通过。实际原runtime为10s/phase、30s/task，故在20.165s仍可COMPLETE；不能把这个success当成19.030回归PASS，亦不能凭空声称原runtime存在19.030 hard deadline。
6. **G4真实路径**：正常成功、零进度/停滞拒绝、连续planner失败、合法fallback、partial reward和真实reset独立性通过。特定自然phase timeout、HOLD不成立和实际绝对安全失败仍NOT_EVALUABLE；OUTBOUND/RETURN timeout及安全终止的TEST_ONLY链路通过，绝不包装成自然证据。deadline晚到覆盖的代码缺口已修复，见反例。
7. **RL-B科学执行合同**：完整EXECUTION_PASS=FAIL；slow/maximal/random逐样本物理/命令parity PASS，全部9个core raw审计PASS。原19.030 random回归仍FAIL，host realtime NOT_EVALUABLE。
8. **真实PPO gradient update**：0；NOT_RUN。负向启动门正确拒绝，策略、optimizer、训练环境和checkpoint未创建，hash为null。
9. **跨进程checkpoint恢复**：NOT_RUN，不能给可靠性PASS。保存/恢复policy、Adam、RNG、进度与hash机制有静态代码，但未用随机权重代替训练恢复证明。
10. **下一轮可直接正式Pilot吗**：不能。G2/执行、G4失败，G6动态恢复未验证。先闭合执行合同与G4，再最小smoke/update/resume。
11. **CCX33预算建议**：当前正式Pilot0 episode/0 seed。未来全部门与smoke恢复通过后，建议单环境1seed、最多32训练+4冻结完整评价episode，估计60–75分钟、hard cap90分钟；本轮完整任务77–82s/episode，PPO开销尚未实测。不自动执行此建议。

| 运行 / episode | 类别 | 状态 | TASK s | RL decisions | native steps（含准备） | J_F N·s |
|---|---|---|---:|---:|---:|---:|
{rows}

共8个物理guard attempt、9个episode（6自然输入、3 TEST_ONLY），3 COMPLETE（其中random未过19.030回归）、6 partial。native {acc['native_steps']}，TASK native {acc['task_native_steps']}，RL decisions {acc['RL_decisions']}，gradient/optimizer updates均0。另有1个训练负向门和1个无物理的受控进程超时：合计10 START、10 END，全部闭合，owned进程和native executor均退出。所有异常/harness失败见audit/HARNESS_FAILURES.json；诊断命令未逐一记录独立wall时间，未伪造时间账。

最低可用RAM{res['minimum_available_GiB']:.3f}GiB，高于6GiB；串行、峰值1物理环境，无观察到的OOM/MuJoCo warning或失控。未创建checkpoint；原ZIP与manifest、939份历史文件校验不变，ZIP450/450载荷重新核验，414 source中412不变、2个隔离修复有diff/hash。正式B/H150与原研究证据未覆盖。目录不是Git checkout，初始branch/HEAD不可用；没有stage/commit/push/merge/reset/stash/delete。

物理/任务参数与动作含义未变；仅事件成本归属、moment统计边界和超过原phase deadline的终止优先级发生修复。新版本已登记，不继承旧资格标签。所有本轮episode为development/smoke qualification，不是held-out鲁棒性或学习成功。唯一下一步见NEXT_RESEARCH_DECISION.md。

交付入口：ROOT_CAUSE_ANALYSIS.md、FORCE_INTEGRATION_REPAIR.md、G4_TERMINATION_REWARD_AUDIT.md、TASK_TIMING_AUDIT.md、RL_EXECUTION_PARITY_AUDIT.md、VALIDATION_RESULTS.json、PPO_SMOKE_RESULTS.json、CHECKPOINT_RESUME_AUDIT.json、ATTEMPT_ACCOUNTING.json、PACKAGE_VERIFICATION.json。最终状态STOPPED_QUALIFICATION_BLOCKED。
''')
state=read('STATE.json');state.update(phase='STOPPED_QUALIFICATION_BLOCKED',labels=labels,repair_cycles_used=1,physics_episodes_used=len(eps),positive_PPO_updates=0,last_physics_END_unix=acc['last_physics_END_unix'],no_new_physics=True,owned_processes=[],completed_asia_shanghai=now,remaining_next_action='Freeze and repair execution-contract consistency and unresolved G4 scope before any positive PPO; do not auto-resume.');put('STATE.json',state)
print('reports generated',now,labels)
