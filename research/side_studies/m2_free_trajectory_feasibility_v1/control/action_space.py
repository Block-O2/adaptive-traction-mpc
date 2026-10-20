from pathlib import Path
import json,hashlib,sys,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
R=S/'source/stages'
paths=[R/'stage3_full3d/src/traction_mpc_stage3/human.py',R/'stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py',R/'stage5_personalized_motion_learning/src/traction_mpc_stage5/cr12_plant.py',R/'stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_feedback_mpc.py',R/'stage5_personalized_motion_learning/src/traction_mpc_stage5/human_waypoint_scheduler.py',R/'stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py',R/'stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/fast_plant.py',S/'code/free_planner.py']
e=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/expert_strength_value_adequacy_v1/output/E_RICH_DIFF_BEST.json')
hist=S.parent/'m2_lowforce_repair_explore_10h_v1/HISTORICAL_E_RECOVERY.json'
evidence=dict(registered_unix=time.time(),source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},E_recovery=json.loads(hist.read_text()),E_original_sha256=hashlib.sha256(e.read_bytes()).hexdigest() if e.exists() else None,E_not_a_matched_comparator=True)
(S/'PHYSICAL_MODEL_EVIDENCE.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
doc='''# 物理动作空间与本轮科学声明

本轮优化隔离 FreePlanner 的路点位置及独立通过速度，使用原 B 完整闭环、原五次多项式 scheduler、native governor、admission、lifecycle、40ms bridge、机器人力矩写入及完整接触模型。零参数必须先与未扩展 NativeResidualPlannerV2 精确重复。新参数是离线研究意图，不是已具备的原生 B residual 权限。

## 人体与施力路径

Human V2 具有 hip/knee 两个被动关节，状态为 q=[hip,knee]、dq=[hip速度,knee速度]，腿段方向 phi=hip-knee。质量矩阵 M(q)、Coriolis、重力、被动弹簧阻尼、软限位和 MuJoCo 约束组成实际动力学。Stage5Human 只扩展 cuff 位置；不重写人体动力学。完整实际参数由冻结 case/config/XML 决定，不把类默认身高体重当作所有运行的实际患者参数。

人体没有研究新增主动执行器。CR12 的六个真实模型 motor 接受受限关节力矩；robot backend 写入 plant.actuator_ids。机器人通过 sleeve/attachment 位姿与速度差形成实际 cuff wrench，经 mj_applyFT 向两端施加成对力和力矩，再进行原生 mj_step1/mj_step2。保持床面、摩擦/contact、ROM、软限位和 cuff 几何。初始化 qpos 是原 commissioning/合法起始状态构造；搜索不写 qpos/qvel，不注入人体主动关节力矩。

接触并非把数学人体轨迹直接交给 MuJoCo。Kelvin–Voigt bushing 中 r=p_R-p_H，x=R_H^T r-r0，u=R_H^T(v_R-v_H-omega_H×r)，F=R_H(Kx+Du)；SO(3)旋转误差和相对角速度产生 couple，人体侧还包含 r×F 的 transport couple，机器人侧得到相反力及 couple。模型可 forward simulate，但材料参数不等同临床认证。

## 三种空间的区别

|空间|合法变化|尚不能支持的声明|
|---|---|---|
|A 原生 B residual|既有 OUT/RETURN 请求处采样 delta，p→p+[delta,-delta]，native scheduler 生成连续运动；HOLD及端点不改|raw-v2 PWL请求间连续执行、独立共同进度或独立指定 dq|
|B 本轮丰富参考|OUT/RETURN 独立；共同进度、差分进度的常数/倾斜系数；独立 hip/knee 通过速度；原 quintic 连接产生连续 q/dq/ddq|任意样条精确跟踪、全面覆盖所有轨迹、物理全局最优|
|C 真正物理执行|以上意图通过原完整 scheduler/模型/几何认证和当前状态 admission 后，转换为 cuff 目标、机器人六轴合法力矩、原接触前向动力学，人体实际 q/dq 才是验收对象|参考 ROM 合格即代表人体物理可行；离线成功即原生 B 或 host-clock 成功|

原 B 将新路点通过完整当前估计状态和 commissioned dynamics 评估，scheduler 用有界速度与20ms因果加速度、连续 clearance 证书构造五次多项式。通过速度本来已实现，但只由固定公式决定：受 velocity/1.875、制动距离和终端剩余量约束。原 residual 没有独立速度调节参数。本轮利用这个现有动力学可执行通路，避免搭建全新底层控制器。

## 实际优化变量与局限

每个方向五个连续参数，共10个。令原请求路点平均 normalized progress 为 m，e=sin²(pi m)。q 进度增加 [c+d,c-d]，c=e*c0，d=e*(d0+d1*(2m-1))；通过速度分别乘以 1+e*(vcommon±vdiff)。每个完整任务参数固定；各合法请求得到新的位姿和通过速度，真实采样 q/dq/ddq 由原 quintic 决定。它是由连续低维函数定义的分段参考族，**不是请求间逐步采样原生 PWL，也不是任意完整时间样条**。端点目标、HOLD和治疗幅度合同不改，时间若变化仍必须≤0.1s。任何被模型/几何拒绝的意图保留并标记；不能把拒绝或无变化当成功实现自由度。

四个区域的起点为 B0、NATIVE_SCALAR_18、Frozen M2的已精确复现 fixed-action 参考、C2_pair_1_2。旧 E 强专家的30项K3参数和来源只读核验；旧 J_F 不参与同条件排序，不训练/调用更新后的 Q。M2 固定完整表与滚动冻结 Q 的等价只承继历史明确重复门限，再由当前完整物理复现检查，不声称任意状态固定表等价滚动策略。

Tracking 统一使用实际人体位置对正向执行的 receipt-owned 参考误差，与原 absolute tracking、安全、端点、各阶段时间及真实运动剂量同时检查。该指标解释的是执行跟踪能力；不同 phase-shape 的治疗等效性独立未知。若原任务/安全口径无法复用则 NOT_COMPARABLE，不排名。

数学参数提出=LEVEL0；完整原动力学前向任务、安全与冻结运动全部合格=LEVEL1。非零自由参数的研究方案最多 LEVEL1；只有不使用扩展且走原合法 residual 的实际 receipt 方案才可能 LEVEL2。LEVEL3不开展。实际 execution count、q/dq差、输入和接触证据必须核验，不能仅凭参数名判断新自由度已执行。

## 源码证据

* `traction_mpc_stage3/human.py`: frozen mechanical equations/soft limits; nominal_tracking_wrench 是指令构造模型，不是对人体注入外力。
* `traction_mpc_stage3/spring_damper_interface.py:69–100`: strain、paired wrench和transport couple。
* `traction_mpc_stage5/cr12_plant.py:272–355`:完整CR12/Human模型和六轴actuator绑定。
* `full3d_adaptive_integration_v1/fast_plant.py:40–65`:真实bushing施力和原生步进。
* `human_waypoint_feedback_mpc.py:180–212,240–375`:通过速度公式、原调度及mechanics screen。
* `human_waypoint_scheduler.py:81–180`:明确2×6 quintic和真实采样接口；不向该证书伪装高阶轨迹。
* `full3d_adaptive_integration_v1/coordination_residual_v2.py`:原生单值反对称delta。
* `code/free_planner.py`:唯一额外参考表达，源码/模型哈希见 PHYSICAL_MODEL_EVIDENCE.json。
'''
(S/'PHYSICAL_ACTION_SPACE.md').write_text(doc)
print('ACTION_SPACE_WRITTEN')
