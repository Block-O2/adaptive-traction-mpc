from pathlib import Path
import json,hashlib,datetime
P=Path(__file__).resolve().parents[1];G=P.parent/'rl_b_matched_recovery_stability_v1/github';S=G/'research/side_studies';D=G/'stages/stage5_personalized_motion_learning/docs'
refs={
 'B与当前科学边界':G/'CURRENT_RESEARCH_BASELINE.md',
 '18D/H150执行源码':S/'ihear_overnight_control_learning_transition_v1/control/campaign_v2.py',
 '18D强基线参数':S/'ihear_overnight_control_learning_transition_v1/FROZEN_18D.json',
 '机制与Waypoint':S/'force_mechanism_waypoint_v3/REPORT.md',
 '10D自由参考':S/'m2_free_trajectory_feasibility_v1/REPORT.md',
 '18D后续研究':S/'m2_18d_t_second_round_coordination_v1/REPORT.md',
 'E/CEM/COBYLA与离线value':S/'direction-prior-value-v1/REPORT.md',
 '受约束直接协调搜索':S/'m2_comprehensive_coordination_search_v1/REPORT.md',
 'Q监督与恢复边界':S/'m2_motion_counterfactual_ranking_v1/REPORT.md',
 'NeuralQ负结果':S/'m2_neural_q_motion_v1/REPORT.md',
 'ILC/BO/历史Value':S/'ihear_history_to_next_trial_learning_v1/REPORT.md',
 'IL与DAgger':D/'dagger_to_sac_expert_v1/DAGGER_TO_SAC_EXPERT_V1_REPORT.md',
 'SAC任务学习':D/'single_human_sac_expert_v1/SAC_EXPERT_V1_REPORT_R2.md',
 'SAC退化诊断':D/'single_human_sac_seed1_300k_failure_diagnosis_v1/SAC_SEED1_300K_FAILURE_DIAGNOSIS_REPORT_V1.md',
 'PPO240与H2来源':P.parent/'rl_b_autonomous_replication_v1/REPORT.md',
 'PPO稳定/H2/R1':P.parent/'rl_b_autonomous_stability_reward_v1/REPORT.md',
 '最新STD/R4':P.parent/'rl_b_training_stability_reward_v1/REPORT.md',
 '云端matched恢复':P.parent/'rl_b_matched_recovery_stability_v1/REPORT.md'}
rows=[]
for topic,f in refs.items():rows.append({'topic':topic,'path':str(f),'exists':f.exists(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None,'evidence_scope':'report/source recovered; complete original raw not implied'})
(P/'audit/SOURCE_RECOVERY_AUDIT.json').write_text(json.dumps({'github_commit':'1adb1de177d6f5f32de6d01c4e629cbfae9ce121','recovered_references':rows,'current_runtime_origin':'audit/CLOSURE_RELOCATION.json','missing_assets':'audit/MISSING_NONCODE_ASSETS_RESTORED.json','restored_ability':'new scientific-mode cold commissioning plus same-live-parent B/H150 full-address-space forks; historical portable serialized parent still not claimed'},indent=2,ensure_ascii=False)+'\n')
text='''# 少次重复运动接口提案 v1

本轮仅验证单周期局部优化；几十次同父仿真优化不能写成新患者两三次即可改善。C模型目前只在相同Human、相同合法父状态下使用二维候选参数，不具备患者状态泛化资格。

## 数据与因果输入

Trial1从合法完整任务产生causal history：commissioned beta/geometry及其估计来源、estimated q/dq、issued reference q/dq/ddq、实际测量cuff force/moment、原source timestamp、applied torque receipt、原执行拒绝/任务结局。保存每个时刻是决策前可用还是执行后反馈；不把native true Human q/dq、物理患者生成参数或下一trial receipt放入预测特征。

当前患者信息只能来自其已完成trial和当前因果观测。离线群体prior必须单列训练患者/轨迹数量、估计与生成侧物理参数边界及计算成本。本轮历史模板是同一nominal Human的已完成D01R causal reference与commissioned belief，不是群体先验；状态特征在本轮恒定，不能宣称学到跨患者条件关系。

本轮优化使用完整反馈JF/JM和原motion evaluator余量作为离线监督标签。原motion余量依赖evaluation-only native Human运动，尚非真实装置可直接获得的患者历史输入。下一阶段需先建立经传感器/observer误差验证的可部署运动测量与保守余量，否则此分支只保留仿真研究身份。

## Trial协议

Trial1执行固定强baseline，公开该患者真实因果历史。Trial2只用Trial1更新残差或局部协调参数；冻结candidate和模型SHA后才执行Trial2。Trial3/4按同样边界逐次更新，各trial保留原安全准入最终权限，不能用未来真值重选先前动作。

同一患者的公平对照从真实连续父状态分支，比较固定强baseline、history-disabled（冻结群体均值或无个体更新）、传统ILC、直接局部BO和物理+残差；动作权限、trial数、预算及原资格门一致。history-disabled不得偷看个体历史，强baseline若在该状态motion失败须单列并改用真实合格固定父。

新患者验证按患者与完整轨迹分组；不能随机分割相邻时间步。模型和超参数在未见患者前冻结，在线只允许预先指定的少次局部更新。每次真实尝试均记探索成本，包括partial/拒绝；报告每trial完整合格JF、JM/motion、累积实际负担ΣJF、失败partial负担与到达同等收益的真实尝试数。不同repetition的自然状态漂移须与同父固定对照区分。

## 本轮可复用接口

`source/nominal_proxy.py`定义causal template/belief输入与显式UNKNOWN输出；`source/optimizers.py`定义每臂独立模型、训练ID及参数提议；`predictions/`在START前冻结预测；`attempts/`和`history/`绑定实际结果及causal轨迹。后续应增加患者context与逐trial数据合同，并独立验证传感器motion余量，不直接复用本轮恒定父状态模型给新患者决策。

CROSS_CYCLE_READY=NOT_READY：本轮未实施Trial1→Trial2→Trial3/4的真实连续患者自适应，也未验证跨患者不确定性。
'''
(P/'CROSS_CYCLE_INTERFACE_PROPOSAL.md').write_text(text)
(P/'SOURCE_RETURN_PLAN.md').write_text('''# 源码回流计划

本轮不自动Git提交或推送。先review新包，再由用户确认是否纳入长期仓库。

建议审查：source/nominal_proxy.py中的明确模型/ROM/residual身份与causal输入allowlist；source/optimizers.py中的同权限直接/名义/残差臂、整轨迹监督与模型身份；source/study_worker.py中的预算、full-live fork与per-arm反馈隔离；独立积分/receipt审计及append-only研究决策日志。

历史runtime/source、code、control、deps是可定位的版本复制，仅做已登记路径与资产恢复，不应整包覆盖正式B或与PPO云端修复混合。数据、实验决策、参数域与脚本路径特化部分留在research包；模型预测有效范围、失败、held-out纪律与原scorer保护须一起保留。

回流前检查零参数与H150 raw等价、完整state fork与RNG、原安全/40ms bridge/100ms生命周期、未来真值防火墙、相同预算计数、旧raw保护及独立积分。仅新增身份明确的研究模块，不能因此给host实时/Stage2/硬件资格。
''')
print('STATIC_DOCUMENTS_WRITTEN',len(rows))
