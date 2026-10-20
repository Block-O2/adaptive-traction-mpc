# 多段连续参考执行接口 V1：隔离资格结果

本轮打通了一个非零内部控制点的实际 MuJoCo 执行链，完成P0/P1/P2及一次同父状态重复。证据等级为 **PHYSICAL_LEVEL1（isolated scientific simulation）**；这不是正式B Native LEVEL2、host-clock LEVEL3或硬件资格。本轮没有优化force、没有训练、没有修改正式B。

## 开头十问

1. **旧接口为何拒绝？** 单段constructor要求2×6；4×2×6在shape检查即失败。旧continuous certificate、tracking-offset geometry和escape准备还绑定单一多项式/duration。旧负测试仍拒绝，未删除限制。
2. **rolling composite可否复用？** 可以。复用其40ms旧桥prefix、suffix局部时间、C2接续、activation及实际splice。它不会自动为任意多段suffix提供全路径资格。
3. **新增的最小能力？** 一个不可变MultiSegmentReference模块，加两处隔离消费分支：原escape完整准备后包装；activation对新类型做整路径current重验及实际每段shifted-path检查。系数、分区、模型/任务/phase/source和stop身份绑定hash。
4. **安全/current admission保留？** 原有安全规则和数学口径保留；每段新增解析ROM/v/a、边界C2、原连续geometry包络、跨节点20ms历史、原mechanics整体+逐段screen、future bridge/stop。原mechanics是采样检查，未宣称其连续未来wrench不变性。source age、100ms lifecycle和当前状态准入仍按原scientific模式执行。
5. **零修改物理等价？** 两组P0均PASS。最终组完整trace全部字段、116,320 native行的物理状态/torque/contact、5,817 receipts的物理/参考/来源字段精确一致。新对象没有折回旧载荷；只有系数身份已证明的零修改对象复用原全局求值核以避免浮点重参数化差。
6. **新增内部点有实际issued reference？** 有。第二个OUTBOUND请求的中间膝q +0.02°，四段总长1.27s、支撑[.3175,.9525]s；外部q/dq/ddq和时间不变。实际激活后255条正native-step receipt携带同一认证对象的样本；独立系数重建与receipt q/dq一致。
7. **真实机器人—人体响应？** 有。同完整父状态、同前史，原FAST/allocator输出经原MuJoCo执行，5100个native子步与这些receipt唯一归属且torque完全一致。相对zero multi，实际Human q最大变化hip/knee约0.00200561/0.0204096°，dq约0.0213702/0.111355°/s；robot各轴torque最大差0.151403Nm。这些来自真实存档状态，不是计划意图。
8. **完整任务/motion通过？** 最终.02°及重复均完成OUTBOUND/HOLD/RETURN，原scientific物理task、绝对安全、motion/fairness、receipt均PASS；完整物理trace重复精确一致。原任务phase时长9.005/1.020/9.005s不变。首批.05°任务/安全PASS但motion FAIL，保留其负结果。
9. **尚未证明什么？** host-clock实时资格（原始host scorer的plan_age仍FAIL）、正式Native LEVEL2、连续真实wrench/未来tracking-error不变集、硬件/临床、未见模型/患者及任意轨迹族。当前certificate hash记录于applied receipts，但该日志未保存其完整current certificate内容供独立重算；worker certificate和reference完整内容/hash已独立重建。
10. **是否具备下一轮低力优化前提？** 在这个冻结任务/模型/父状态和已测试的局部自由度内，合法非零执行这一前提已成立。还不构成任意连续动作空间可优化或跨条件安全资格；后续需另行定义有界动作族、验证范围和预算。本轮STOP，不自动开始搜索。

## 物理证据与全部结果

T0 2026-10-15 12:45:19中国时间；总计10 START/10 END，包含两个合法冷父进程及全部fork，24上限未用满。物理均串行、个体timeout600s；本轮报告生成时距T0约36.9分钟，成功后提前停止，无需耗尽建议时长。

|attempt|实际新增native steps|物理TASK|receipt|motion|J_F N·s（仅审计）|START至END墙钟s|
|---|---:|---|---|---|---:|---:|
|interface1_parent|116320|PASS|PASS|PASS|1438.613498467|472.1|
|interface1_B0|76120|PASS|PASS|PASS|1438.613498467|87.4|
|interface1_zero_multi|76120|PASS|PASS|PASS|1438.613498467|87.9|
|interface1_knee_005|76120|PASS|PASS|FAIL|1438.612052286|93.4|
|interface1_knee_002|76120|PASS|PASS|PASS|1438.613737555|87.6|
|interface2_parent|116320|PASS|PASS|PASS|1438.613498467|478.2|
|interface2_B0|76120|PASS|PASS|PASS|1438.613498467|87.4|
|interface2_zero_multi|76120|PASS|PASS|PASS|1438.613498467|89.9|
|interface2_knee_002|76120|PASS|PASS|PASS|1438.613737555|89.0|
|interface2_knee_002_repeat|76120|PASS|PASS|PASS|1438.613737555|90.3|

fork trace保留父启动前史，所以每条完整档案有116,320 native行；实际新增步数另列，不能重复计为fork新执行。匹配从完整live父状态fork，隐藏控制状态/模型/receipt/progress等继承；父进程在每个子进程结束后hash不变。所有最终子臂14个planner决策，未靠增加调用频率获得新自由度。

B的J_F=1438.613498467487；.02°=1438.613737554673，差+0.000239087186N·s。本轮按motion资格选择幅度；更低力的.05°因motion失败被拒，不能称force改进。独立原始完整TASK左积分及phase精确裁剪闭合，见PHYSICAL_VALIDATION。

最终.02°：原reference与修改reference的数学区别最大膝0.02°；支撑外约2.22e-16rad。真实闭环响应可在支撑之后传播，不声称后续实际运动/reference完全局部不变。所有pre-multisegment trace对照精确一致。原机械模型、cuff/contact、gravity、actuator、torque/ROM/任务目标、HOLD、phase完成、0.25ms native和5ms FAST均未改。

原绝对物理检查的force/moment、Human/robot speed、Human acceleration、ROM、clearance、contact、torque、真实goal dwell与return均PASS。峰值force 115.479118643N、moment 15.711377245Nm，最小真值shank clearance 0.011888026m（只用于评价）。原始scorer的host plan_age为FAIL，mode-aware scientific物理/因果检查为PASS；没有把host失败改成实时PASS。

## 失败与修复

- 首批.05°：hip原始native-derived acceleration最大比1.25228，jerk RMS比1.51197，超原1.10负担门。峰值在约15.92s，已晚于修改suffix结束约2.94s；对应15.915s receipt的robot轴扭矩出现短暂跳变。内部解析C2和path证书均合格；已定位下游闭环瞬态，完整非线性原因仍UNRESOLVED。未调控制增益、plant或阈值。预声明的.02°减幅通过；未继续.01°。
- 首批记录问题：子段record把原段metadata扁平复制，显示duration为1.27s，真实子段duration与证书为.3175s。实际系数、local sample、hash内容和物理不受影响。保存versions/interface1后修正实际时长/边界摘要，并附完整identity_payload；新增序列化/独立hash测试。最终版重新P0、.02°和一次重复。没有覆盖旧原始结果。
- 30项合同测试全部通过；28段历史参考的各实际子多项式独立求值最大q/dq/ddq误差1.33e-15/1.89e-15/1.32e-14。含非法q/dq/ddq接续、中段ROM/v/a/clearance、tracking offset、旧schema拒绝、source/model/reference/phase、不可行stop、迟到latch等负测试。数学测试不是物理执行替代。

## 身份、分层与复现

MATHEMATICAL_TRAJECTORY → CERTIFIED_REFERENCE → ACTIVATED_REFERENCE → ISSUED_REFERENCE → APPLIED_COMMAND → ACTUAL_HUMAN_MOTION逐层证据分别在REFERENCE_OBJECTS、summary learning/decisions、ISSUED_REFERENCE、applied receipts及native qpos/qvel。worker certificate绑定真实整路径；当前模型与原current admission在worker后/实际splice再次检查。日志附加身份不改控制。

最终reference_id `264a28844d876b5442e5fd5f448264a8626d1fbfd9dd9ef46623a6e70c8bacc9`；certificate_id `341bceb4236dd6b5298b3a14880b5b46628f492940c1d14b9f62d5177077e33a`。hash覆盖字段见MULTISEGMENT_REFERENCE_CONTRACT；current hash在key_traces的实际receipt。两个重复的物理轨迹相同，host capture导致值身份可不同，这是原source不得刷新的结果。

入口：[REPRODUCTION](REPRODUCTION.md)。完整源码/模型闭包与每次START版本manifest在CODE_MANIFEST、versions和source；raw物理在source/results，key_traces提供引用和关键切片。关键原始负例.05°保留。图表1–5均由实际payload/raw数据生成，SVG及PNG可导出。

![接口架构](figures/01_interface_architecture.png)
![零修改等价](figures/02_zero_reference_equivalence.png)
![内部点与导数](figures/03_internal_control_point_q_dq_ddq.png)
![实际issued与物理响应](figures/04_issued_and_physical_response.png)
![完整任务及运动门](figures/05_full_task_force_and_motion.png)

## 保护与关闭

主仓库HEAD/branch/index/staged/unstaged diff/status以及6141个文件/链接SHA与启动前一致。上一轮包1582个文件SHA一致；其余既有Side Studies全部69970个文件名/size/mtime一致。后者是metadata审计，未伪称对所有旧研究重新全量hash。证据audit/FINAL_PROTECTION_AND_EXIT。

两个owned owner/worker及所有子进程已join，活跃owned物理进程0。START/END闭合，唯一motion负例已保留。PHYSICS_STOP与STATE标记STOP；没有Git变更命令、提交/推送、force搜索或RL/Q/MLP训练。包实际逻辑/磁盘占用见STORAGE.json，最终内容SHA见PACKAGE_MANIFEST.json。
