from pathlib import Path
import os,json,time,hashlib,shutil,ast
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;S=P.parent;A=S/'m2_18d_early_return_motion_repair_v1'
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data=read(P/'derived/HISTORICAL_NATIVE_AUDIT.json');records=data['records']
for r in records:
 if r['archived_all_original_qualifications'] is None:
  r['archived_all_original_qualifications']=bool(r['archived_motion']['acceptance_pass'] and r['axes']['PHYSICAL_TASK_VALID']=='PASS' and r['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS' and r['native_safety'])
  r['qualification_resolution']='Conjunction of archived original motion/task/causal/native-safety fields; historical format lacks all_original_qualifications key'
put('derived/HISTORICAL_NATIVE_AUDIT.json',data)
hold=read(A/'HOLDOUT_REGISTRATION.json');cond=hold['condition'];logs=[];hits=[]
def contains(x):
 if isinstance(x,dict):return x.get('seed')==cond['seed'] or x.get('prefix')==cond['prefix'] or any(contains(v) for v in x.values())
 if isinstance(x,list):return any(contains(v) for v in x)
 return False
for f in S.rglob('ATTEMPTS.jsonl'):
 if f.is_relative_to(P):continue
 logs.append(str(f))
 for line in f.read_text().splitlines():
  x=json.loads(line)
  if x.get('event')=='START' and contains(x):hits.append(dict(path=str(f),record=x))
assert not hits,hits
put('HOLDOUT_REGISTRATION.json',dict(status='REGISTERED_UNUSED_CONDITIONAL_W2',registered_unix=time.time(),condition=cond,prior_START_logs_checked=logs,seed_or_exact_prefix_matches=hits,source_plan=str(A/'HOLDOUT_REGISTRATION.json'),source_sha256=sha(A/'HOLDOUT_REGISTRATION.json'),start_condition='Frozen development candidate eligible plus deterministic repeat PASS; exact same frozen candidate, matched B/T/D/ER; no W2 tuning',same_Human=True,no_physics_started=True))
risk=[]
for r in records:
 for e in r['events']:
  if e['phase']=='RETURN' and e['slot'] in [1,3,4,5]:
   est=e['deployable_state_deg_deg_s'];ref=e['reference_state_deg_deg_s']
   risk.append(dict(state=r['state'],arm=r['arm'],slot=e['slot'],phase_remaining_s=e['remaining_s'],estimated_q_deg=est[:2],estimated_dq_deg_s=est[2:],reference_q_deg=ref[:2],reference_dq_deg_s=ref[2:],tracking_estimate_minus_reference_deg_deg_s=[a-b for a,b in zip(est,ref)],distance_to_phase_goal_deg=[est[0]-5.5,est[1]-9.5],source_age_s=e['source_age_s'],offline_only_future_label=dict(full_qualification=r['archived_all_original_qualifications'],failed_requirements=r['archived_motion']['failed_requirements'],full_J_F=r['J_F'],knee_overshoot=r['terminal'][1]['return_overshoot_below_goal_deg']),no_online_admission_rule_inferred=True))
put('derived/STATE_RISK_FEATURES.json',dict(status='READ_ONLY_RETROSPECTIVE_FEATURE_TABLE_NOT_VALIDATED_ADMISSION',rows=risk,split_warning='Same episode repeats and shared prefix groups must not cross train/test; all these states now exposed',truth_firewall='only archived deployable estimates/reference/age in features; future truth/outcome kept under offline_only_future_label'))
root=A/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1'
names=['activation_validation.py','rolling_suffix_splice.py','scientific_scheduler.py','wall_physics.py','runtime_coordination_residual_v2.py','safe_fallback.py']
keywords=['source_age','sensor_age','100','40','0.04','lifecycle','current_state','estimated_state','qpos','qvel','command_receipt','active_receipt_index','native_steps','actual_human_acceleration']
out=[]
for name in names:
 f=root/name
 if not f.exists():continue
 lines=f.read_text().splitlines();matches=[]
 for i,line in enumerate(lines):
  if any(k in line for k in keywords):matches.append(dict(line=i+1,text=line))
 out.append(dict(path=str(f),sha256=sha(f),matches=matches))
for name in ['analyze_matched.py','explore_common.py','terminal_repair.py','rich_planner.py']:
 f=A/'code'/name
 if f.exists():out.append(dict(path=str(f),sha256=sha(f),public_functions=[n.name for n in ast.walk(ast.parse(f.read_text())) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]))
put('audit/EXECUTION_SOURCE_INDEX.json',dict(status='READ_ONLY_SOURCE_INDEX',files=out,note='Index supports manual source review; keyword absence is not proof of truth firewall'))
schema={
 'schema':'iHEAR.future_learning.transition.v1','status':'DESIGN_ONLY_NO_TRAINING','units':'rad, rad/s, seconds, N, Nm; metric exports may also carry degrees',
 'identity':{'study_id':'string','candidate_id':'string','parent_candidate_id':'string','source_manifest_sha256':'sha256','action_contract_sha256':'sha256','condition_id':'string','prefix_graph':'causal legal residual graph, not Human state','seed':'int','same_human_model_sha256':'sha256','full_fork_state_hash':'evaluation metadata, excluded from feature vector','split_group':'shared cold/prefix history group','exposure':'development | exposed_diagnostic | frozen_unseen | deterministic_repeat'},
 'observation_causal':{'source_sample_time_s':'original sample timestamp; never refreshed by retry','sensor_capture_ns':'original clock domain','estimated_human_q_dq':'ONLINE_ESTIMATED','estimated_acceleration':'causally derived estimate with validity and method','reference_q_dq_ddq':'issued reference at request','phase_slot_remaining_s':'task clock','goal_distance':'derived from causal estimate and frozen goal','recent_estimated_motion_history':'causal window; uncertainty and provenance required, not true native motion','running_estimated_extrema':'state memory with estimator uncertainty; not ground-truth extrema','commissioned_geometry_and_beta':'CALIBRATED/ONLINE_ESTIMATED with source status','model_version':'immutable identity','source_age':'computed in declared simulation or host domain','carry_braking_fallback_state':'actual execution state'},
 'action':{'proposed_intent':'bounded legal internal posture, duration multiplier, or pass velocity multiplier','parent_parameters_frozen':'bool','selected_target_duration_velocity':'pre-intervention parent and proposed values','certificate_hash':'new curve/current-state binding','request_id':'original request','admission':'accepted | rejected | stale | expired','activation_splice_times':'actual times or null','applied_action':'only reconstruct from activated schedule plus positive-step receipts; never proposal equals execution'},
 'execution_feedback':{'native_step_count':'actual new steps, shared prefix separately','receipt_ids':'original IDs; direct plan_request_id optional/null','binding_method':'direct recorded identity or explicit interval/version/reference/torque reconstruction','current_admission_result':'original result','source_age_at_apply':'original source','exit_reason':'complete | partial | exception | stopped','fallback_events':'preserved'},
 'offline_evaluation_only':{'true_human_q_dq_native':'SIMULATION_TRUTH, excluded from learner input','native_acceleration_jerk':'frozen gradient/SG sensitivity','true_clearance_contact':'SIMULATION_TRUTH','full_matched_B_quantiles':'future counterfactual; excluded from online admission','full_J_F_force_peak_RMS':'complete raw integration only','moment_integral_peak':'separate burden axis','tracking_motion_dose':'all original per-joint gates','overshoot_and_continuation':'separate diagnostic definitions','qualification':'task/safety/motion/receipt booleans and failure list','full_gain_vs_own_B':'only paired within condition','remaining_suffix_cost':'separate from full task, never rank partial as full'},
 'learning_contract':{'priority':'eligibility before force ranking; preserve failed low-force examples with explicit failure labels','followup_policy':'frozen causal replanning policy identity required; V_commit and V_replan not interchangeable','split':'group by common physical history; repeat not independent state; never tune on validation then call it unseen','representation':'must permit state-action interaction; historical a(s)+b(p) has state term cancel in action ranking','training_this_campaign':False,'deployment_authority':'ranking only within original certified admission; no controller or safety override'}
}
put('FUTURE_Q_LEARNING_SCHEMA.json',schema)
text='''# RESEARCH STATE AUDIT — 多方向自主研究 v1

证据范围：PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION，同一固定Human模型。原任务19.030 s，OUTBOUND/HOLD/RETURN为9.005/1.020/9.005 s。原B、历史18D/T/D/Early RETURN只读；本包不训练学习器。初始审计先于任何新physics。

## 已有资格与开发候选
|方法|确立的有限证据|未解决的边界|
|---|---|---|
|B|各历史匹配条件完整task/safety/科学receipt；原运动参照|host FAST/strict/R2仍有失败，未建立统一B_RUNTIME_BASELINE_V1|
|18D|原开发完整J_F 1400.697221153，匹配B 1438.613498467；传统离线18参数优化|旧新prefix motion 0/4；N2/U1/V1/V2存在峰值失败；不是RL|
|18D-T|N2/U1/V1/V2有限合法prefix与确定性重复通过|W1/O0失败；只证明对应remaining suffix，非跨患者|
|D|V1开发与重复、R0受控背景完整通过|W1/O0失败；R0共享W1 OUTBOUND历史，不能算完全独立新入态|
|Early RETURN ER110_R4_120|修复W1 v95/a95/amax/jerk RMS，J_F 1402.644192729|膝excursion差+0.548596467°，原0.5°门失败；无重复/未见验证资格|
|局部Waypoint|确实改变native Human，小幅局部及完整效应可重复|固定外端边界/时长的小幅shape信息增益低，未达到历史晋级；reference平滑不保证实际/完整改善|

## 五Track事前判定
A：最新ER膝目标9.5°，实际最小8.224621516°；真实下冲1.275378484°，不等于excursion差。16.895s参考停稳时已有1.169895711°下冲，随后271ms再下降0.105482772°。RETURN5仍在完成髋运动。检验RETURN3膝通过速度有界缩放；保留父参数，最多两个候选。原证书预检和完整physics均须通过，任何新失败不能被低力覆盖。

B：N2/U1/V1/V2多数RETURN近乎收敛；W1/R0共享OUTBOUND，W1/O0的RETURN响应几乎相同但完整相对门不同。必须分开绝对负担、匹配B分母、OUTBOUND累计极值及暴露状态。交付状态地图和只读因果特征表，不声称已有有效在线准入器。真正未见W2仅在新候选开发合格/冻结/重复后消费。

C：raw native梯度及SG5/21都保留；完整TV_v/TV_a/jerk与局部峰分开。已有微小Waypoint搜索收益不足，不再重开同边界密集搜索。优先分析A干预是否改善完整运动并检查下游代价。

D：ER对匹配B J_F降低2.353869%，moment integral仍增加约5.792%。tracking和moment不因降力自动改善。相同窗的allocator/接触/误差仅作关联，不冒称独立根因；没有新临床comfort门。本轮优先完整配对审计，不无依据改机械参数。

E：原source age/lifecycle/40ms桥接/current-state admission/certificate/receipt/native ownership保持；科学时钟通过不能替代host-clock资格。原receipt部分路径没有直接plan_request_id，间接时序、reference/torque/step核验保留且明确标注。未来学习schema区分因果输入、提议/实际应用、真值离线标签、完整资格和数据分组。本轮不做runtime重构。

## 共同机制与低信息方向
终末耦合/跟踪响应与累计运动门共同限制适用域：降低窄峰不保证p95或excursion通过。末段开始前已累积的极值不能由后来动作删除；匹配B未来全程p95不可供在线决策。形状小修、继续延长已修好的RETURN1、把所有下冲解释成停稳后的惯性都缺乏当前证据。

## 合法接口及证据层级
隔离wrapper可在原活态选后重建内部目标、suffix duration、内部pass velocity；必须重新通过原数学/连续几何/力学/escape/current admission和真实执行。不更改正式B接口、plant、HOLD、完整时长、gain、ROM/torque或原验收门。数学可行只允许进入physics，不构成Human运动通过。

全部25条历史配对native统计及源SHA见derived/HISTORICAL_NATIVE_AUDIT.json和audit/HISTORICAL_ANALYSIS_SOURCES.json。源码索引见audit/EXECUTION_SOURCE_INDEX.json；W2历史START审计见HOLDOUT_REGISTRATION.json。尚无本轮新合格候选，此时physics START=0。
'''
(P/'RESEARCH_STATE_AUDIT.md').write_text(text)
with (P/'MULTI_TRACK_DECISION_LOG.md').open('a') as f:f.write('\n## D1 — 五方向历史审计完成\n量化A真实下冲，B分母/共同历史问题，C微小shape低收益，D力矩代价与E执行缺口。优先A有界R3膝通过速度干预；B/C/D/E继续只读深入，不强行各跑physics。W2已复核无历史START，保留为条件验证。\n')
for n in ['RESEARCH_STATE_AUDIT.md','MULTI_TRACK_DECISION_LOG.md','FUTURE_Q_LEARNING_SCHEMA.json','HOLDOUT_REGISTRATION.json','derived/HISTORICAL_NATIVE_AUDIT.json','derived/STATE_RISK_FEATURES.json']:
 dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/n,dst)
print(json.dumps(dict(status='PASS',historical_records=len(records),causal_feature_rows=len(risk),source_files=len(out),W2_prior_START_matches=hits)),flush=True)
