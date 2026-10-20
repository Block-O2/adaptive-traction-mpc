"""Write a design-only next-stage data contract. No dataset export or training."""
from pathlib import Path
import json,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
contract=dict(schema='ihear_coordination_transition_design_v1',status='DESIGN_ONLY_NOT_RL_READY',training_authorized=False,online_state=dict(required=['source_sample_time_s','belief_sequence','causal_estimated_q_dq','commissioned_model_version','causal_tracking_error_against_receipt_reference','phase','phase_elapsed_s','phase_remaining_s','request_slot','previous_applied_action_id','active_reference_id','reference_q_dq_ddq','source_age_from_original_measurement','admission_status'],forbidden=['evaluation_only_human_qpos_qvel','future_full_task_cost','validation_outcome','patient_identifier_inferred_from_prefix']),action=dict(required=['full_18D_vector','RETURN_plateau_spec','phase_slot_semantics','waypoint_shape_if_any','parameter_contract_sha256','intended_action_id'],separate=['proposal','certified_reference','activation_result','issued_reference','applied_command_receipt'],B_fallback='Distinct executed action, never relabelled as the intended rejected action'),feedback=dict(force='Measured physical cuff-force norm left integral over actual owned interval including planning/carry time',motion='Actual native-derived evaluation burden stored separately from deployable observations',constraints=['task_completion','absolute_safety','ROM','torque','clearance','contact','motion_noninferiority','tracking','moment','receipt_causal'],terminal=['COMPLETE','SAFETY_STOP','TIMEOUT','ERROR_PARTIAL'],partial_policy='Preserve observed cost, censoring and reason; never zero-impute missing suffix or rank as full-task gain'),lineage=dict(required=['Human_model_id','source_package','parent_native_hash','parent_full_hash','fork_source','shared_prefix_id','execution_manifest_sha256','attempt_START_END','actual_new_native_steps'],split_rule='All forks/repeats from one parent/state family stay together; different prefixes are same Human, never different patients'),qualification=dict(blockers=['validated causal state applicability domain','stable traditional coordinator under original motion gates','executed action and interval credit assignment','state-action interaction beyond separable additive Q','held-out state family validation'],current_claim='This schema prepares provenance only. No policy fit, RL dataset readiness or training qualification.'))
(P/'FUTURE_Q_DATA_CONTRACT.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False)+'\n')
(P/'FUTURE_Q_DATA_CONTRACT.md').write_text('''# 后续Q-learning数据合同草案（仅设计）

本轮不训练、不导出可宣称RL-ready的数据集。可以准备来源与字段合同，优先工作仍由NEXT_RESEARCH_DECISION决定。

state只能使用请求时已存在的因果估计、belief/model身份、reference与receipt、tracking估计、phase/剩余时间/slot、原source age与准入状态。真实Human qpos/qvel、未来累计代价与验证标签单独保存在evaluation命名空间，禁止进入在线特征。

action保存完整18参数和RETURN plateau及phase/slot、可选Waypoint shape；必须分别保存意图、证书、激活、issued reference、真正applied receipt。被拒动作与后续B/carry/fallback不能被错误标为相同executed action。当前固定18D不是已学习的state-conditioned策略；旧可分Q(s,p)=a(s)+b(p)不能通过公共state项声称学到状态交互。

反馈按真实receipt所有权区间积分cuff force，含等待/carry；完整TASK JF是整任务终点评价，不能分配到任意单个proposal。部分/timeout/安全停止保留已观察积分、缺失后缀与原因，不以零填充奖励。motion、task、absolute safety、tracking/moment/ROM/clearance及causal资格分别存储，不能仅用force奖励吞掉约束失败。

split按Human/model、合法父状态与prefix家族分组；同父fork和确定性repeat不得跨训练/验证泄漏。同一Human的不同prefix不增加患者数。先证明传统协调的适用域、动作真正执行和区间credit assignment，再另立采集合同；本草案本身不满足启动Q-learning的前提。\n''')
print('FUTURE_CONTRACT_DESIGN_ONLY')
