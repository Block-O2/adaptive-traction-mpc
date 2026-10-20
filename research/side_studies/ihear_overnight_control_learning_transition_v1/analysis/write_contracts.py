from pathlib import Path
import json,time,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def doc(n,s):(P/n).write_text(s.strip()+'\n')
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
doc('LEARNING_PROBLEM_DEFINITION.md',r'''
# Learning问题与冻结合同

本轮主要学习问题是：在同一被动Human、合法prefix形成的可观测状态下，学习四个合法协调动作的完整任务价值及适用条件。使用实际完整物理回报训练有限动作价值模型，不运行COBYLA，不把参数搜索重命名为Q-learning。

**本轮主模型的精确定义为contextual Monte Carlo action-value regression**。一个动作定义RETURN2/3两个中间姿态修正及其冻结的后续执行规则；完整任务终止后得到回报。它有显式state×action交互，但没有多步Bellman bootstrap，不宣称学到Q*或长期患者适应。此前的18D仍是传统约束优化。

在线决策时点为RETURN slot 2、第一项姿态干预之前。七个输入为估计髋/膝q相对当前reference的误差、估计dq相对reference dq的误差、当时测得cuff force/moment范数、当前phase elapsed。request原source time、age、model hash、phase/slot同时保存。只使用已经获得的估计/测量；native Human truth、未来matched B统计、整个任务结束后的最小角度都不进入这次选择。

动作H150/HIP/KNEE/ZERO分别在RETURN2与RETURN3使用[+0.3,-0.3]、[+0.3,0]、[0,-0.3]、[0,0]度姿态修正。四者都保留18D、T、RETURN1×1.10、RETURN4×1.20及RETURN5 hip×1.5；全部由原5ms量化、规划、证书、current-state admission与allocator执行。ZERO只表示这两个姿态增量为零，不等于正式B。B只作为同父完整资格和force对照。

任务仍含OUTBOUND/HOLD/RETURN；不得截短HOLD或以partial force积分获益。奖励采用分层合同：提议合法、实际接纳/应用、完整task、原绝对安全、causal ownership、原motion/fairness全部满足后，才比较完整J_F。失败的完整积分仅为诊断标签，不作为成功奖励；拒绝动作的实际fallback与提议身份分开保存。overshoot、velocity TV、acceleration variation、jerk、moment、tracking、峰值与剂量同时保留。

训练单位是完整cold parent/prefix family。D01/D02为已暴露W1/W2；D03–D06为前瞻开发状态；V01/V02仅用于模型选择；U01–U03必须在权重与选择规则冻结后才消费。同父的所有动作、重复和时间节点不得跨split。只有一个Human，不将多条轨迹计为多个独立Human。

模型比较全局固定动作均值与具有每动作独立状态斜率的ridge。训练只使用D组，alpha候选0.1/1/10/100由V组选择；最终不把V再并入训练。学习完整J_F相对本状态H150的差及每个原资格归一化余量，匹配H150/B仅构成离线标签。保守选择要求预测余量超过leave-one-parent-out最大残差、预测force优势超过开发误差，并处于开发状态支持范围。证据不足保留H150；这不意味着H150在任何新状态都motion合格。

必须报告直接Q排序和保守选择两种结果，避免把资格屏蔽导致的动作变化当作Q学习出状态偏好。最终与固定H150及训练集选出的全局最佳固定动作对照。只有未见状态真实完整合格获益且确实优于全局固定动作，才考虑Q_GENERALIZATION_PASS。

跨重复是单独资格：必须先执行一整次运动，用其真实已获得反馈实际更新模型/记忆，再在下一次重新准入并执行。冷启动fork数据、离线重放选择和确定性重复均不等于FEW_REPETITION_LEARNING_PASS。连续plant接口若有失败，不修改门槛或重置Human状态使其通过。

参考方法来源：[Sutton与Barto，《Reinforcement Learning: An Introduction》第二版](https://mitpress.ublish.com/book/reinforcement-learning-an-introduction-2)；[Ernst等，Tree-Based Batch Mode Reinforcement Learning，JMLR 2005](https://jmlr.org/papers/volume6/ernst05a/ernst05a.pdf)。前者用于区分contextual action-value与完整MDP；后者用于区分回归拟合与真正的迭代Bellman目标。本轮不因引用后者就声称已实施fitted Q iteration。
''')
doc('LEARNING_DATASET_AUDIT.md',r'''
# 数据审计与历史设计诊断

历史线性Q/M2的Q(s,p)=a(s)+b(p)，比较同一状态候选时a(s)相消。状态导致的mask/carry变化不是学习到的state-conditioned ranking。来源：CURRENT_RESEARCH_BASELINE.md、b_native_q_realtime_integration_v1/REPORT.md与Q_STRUCTURE_AUDIT。

历史motion-aware Neural Q的80条合法branch row只有13个snapshot与4条父轨迹，不能按80个独立状态解读。32×32模型两个诊断测试state的mean regret为9.9306 N·s，linear为1.6207 N·s；没有显示优势。早期96D ridge包含显式交互，不能一概断言所有历史线性模型都没有交互。来源：m2_neural_q_motion_v1/REPORT.md。

scratch SAC的22次正式评估全部OUTBOUND失败，replay缺少HOLD/RETURN完整成功覆盖；降低rejection没有转化为完整任务。DAgger/anchored SAC另有任务获取、探索尺度、critic return-scale和资源问题；其更旧动作/任务/时序接口与本轮H150完整资格并不自动等价。来源：single_human_sac_failure_diagnosis/output/SAC_SEED1_300K_FAILURE_DIAGNOSIS_REPORT_V1.md、dagger_anchored_sac_v2/output/DAGGER_ANCHORED_SAC_V2_REPORT.md。旧的任务成功不是本轮motion合同通过。

因此，本轮优先采集少量同完整live parent的配对完整结果，保留全部失败，使用小模型。既有W1/W2只用于历史审计和开发，不能再称本轮未见测试。原始native truth只用于离线motion标签；七个在线特征在live decision boundary写出，不从未来trace反向挑节点。各动作必须在第一次姿态差异之前具有相同特征，并由完整fork hash、父进程未变化和实际receipt共同证明配对。

机器可读逐行合同见derived/DATASET_*.json及npz；proposed action、accepted/rejected、实际参考和receipt、完整结果、资格、cost分开保存。失败/partial/父对照不伪装成成功动作。TRAINING模型身份与split检查见models/VALUE_FREEZE.json及最终PACKAGE_VERIFICATION.json。实验结束时由结果报告补充实际行数、合格数与缺失，不预填。
''')
doc('RL_BASELINE_STUDY.md',r'''
# 受约束RL baseline合同

当前状态：NOT_RUN，尚未启动P2物理或PPO/SAC更新。本文件是一份可复现的设计合同，不代表RL已经有效；最终是否执行由Stage C的科学价值、剩余时间与原接口资格决定。

若启动，必须沿用同一四动作集合、七维因果状态、完整任务及所有原资格。策略输出离散参考动作id，不能输出直接torque。新episode由原冷启动commissioning和合法prefix开始；连续重复必须用既有persistent session与真实inter-rep settle/hold。不得直接设置/回放Human qpos/qvel，不能为了训练另建宽松代理环境。

算法对照可使用离散categorical PPO：CPU单线程，固定seed=2026102401，学习率3e-4、clip=0.2、gamma=1、batch覆盖4个完整episode、每批4个epoch，状态归一化只用开发数据。完整合格reward=-J_F/1000，失败单列failure label并使用-10的预注册惩罚；partial积分不得成为成功reward。此定义必须在真正启动前再次登记精确代码/权重身份与执行预算，不以本文替代运行manifest。

P2硬上限为24 episodes、2,400,000 native steps、3600秒墙钟，先到者停止；所有P2串行且与P1互斥。P1的同父对照与验证START另计，二者不得互相充抵。最后60分钟不启动physics或training，T0+10h强制退出。PPO的24集只能作最小探索，通常不足以声称稳定训练收敛或strong baseline。

独立评价必须在冻结checkpoint后使用全新合法prefix，完整task/safety/motion/causal通过后才报force收益，并与固定H150及价值方法比较总physical成本。仅有能训练的代码或checkpoint不得标注RL_BASELINE_QUALIFIED。Stage C数据不足时优先保留完整合同和负结果，不用昂贵RL掩盖主要学习问题。
''')
put('STATE_ACTION_REWARD_SCHEMA.json',dict(schema='ihear.state_action_full_outcome.v1',online_input_whitelist=['estimated_human_q_dq','issued_reference_q_dq','measured_current_cuff_force_moment','phase_elapsed','original_source_time_age','phase_slot_model_version','previous_completed_task_measured_feedback_when_explicitly_enabled'],online_forbidden=['native_human_qpos_qvel','future_truth','future_matched_B_metrics','future_candidate_result','test_outcome_before_policy_freeze'],required_identity=['parent_family','seed','split','action_hash','execution_manifest_sha256','policy_version','request_id'],action=dict(kind='bounded_reference_intent',ids=['H150','HIP','KNEE','ZERO'],direct_torque=False),execution_required=['proposed_action','accepted_rejected','actual_applied_reference','activation','positive_native_receipts','source_age','ownership'],outcome_required=['complete_task','task_pass','absolute_safety_pass','causal_pass','motion_pass','failure_reasons','J_F','force_peak','moment_integral_peak','tracking','native_motion','dose','overshoot'],qualification_first=True,invalid_cost_rankable=False,split_unit='parent/prefix family',truth_role='offline supervision and evaluation only',few_repetition_requires_actual_update_and_following_task=True))
put('REFERENCES.json',dict(sources=[dict(title='Reinforcement Learning: An Introduction, second edition',authors=['Richard S. Sutton','Andrew G. Barto'],year=2018,url='https://mitpress.ublish.com/book/reinforcement-learning-an-introduction-2',use='Terminology: contextual action values versus sequential MDP learning',limitation='Does not establish this simulator or method works'),dict(title='Tree-Based Batch Mode Reinforcement Learning',authors=['Damien Ernst','Pierre Geurts','Louis Wehenkel'],year=2005,venue='JMLR 6:503–556',url='https://jmlr.org/papers/volume6/ernst05a/ernst05a.pdf',use='Bellman iteration must not be conflated with a one-shot terminal cost regression',limitation='No fitted Bellman iteration claimed in this study')]))
print('CONTRACT_DOCUMENTS_SAVED',flush=True)
