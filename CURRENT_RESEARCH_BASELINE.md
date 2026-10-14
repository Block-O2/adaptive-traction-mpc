# CURRENT RESEARCH BASELINE — 2026-10-14

本文件冻结当前研究边界，不新增控制或规划算法。主仓库位于 WSL
`Ubuntu-Research-Verify:/home/hank/coding/adaptive-traction-mpc-learning`；远端为
`git@github.com:Block-O2/adaptive-traction-mpc.git`。

## 正式 Controller B

正式 B 指现有受保护的执行与安全底座：robot/cuff 因果测量与 commissioned
belief → estimated Human state → 在线 hip/knee waypoint 有限候选 MPC → quintic
scheduler/governor → current-state admission → FAST feedback / cuff allocator →
六轴 robot torque → 原 cuff 接触与被动 Human 动力学。

基准使用 V=0；在线观测更新不等于持续模型学习或 few-repetition 个体化。
数学目标、issued reference、真实 Human q/dq 和 applied command receipt 必须分别保存。
FAST 的 5 ms 服务、0.25 ms native physics、40 ms bridge、100 ms proposal lifecycle
和历史 strict55 是不同时间尺度与资格轴。source age 从原测量起算，不能重试刷新。
过期/拒绝走合法 carry/stop、SAFE_FALLBACK_HOLD 和 fresh-state replan。

B 已有有限 scientific equivalence、physical/causal execution 与 host 研究证据；
各版本资格分别保留。FAST completion 和 HOLD→RETURN 包仍有原 R2 失败，
HOLD 包为 NOT_FROZEN，未创建统一 B_RUNTIME_BASELINE_V1。
不能统称正式 host-qualified、硬实时、真机或临床已验证。

## 历史与隔离研究

- E / offline teacher：有限搜索的 best-known reference，保留模型、配置、复现入口和负结果；不是全局最优或成熟 RL。
- 旧 native linear Q / M2：冻结候选池中 Q(s,p)=a(s)+b(p)，比较候选时公共 state 项相消。它提供固定偏好，不能称成熟 state-conditioned 排序器；mask/carry/可行性随状态变化不是 Q 学会状态交互。
- Neural Q：保留历史 96D/120D 网络、训练/验证记录、branch dataset 和 feature/label 合同；32×32 challenger 两个历史测试 state 的 mean regret 为 9.9306 N·s，linear 为 1.6207 N·s，未证明优势。V_commit 与 V_replan 不自动等价。
- Direct RL/SAC/DAgger：历史任务能力、安全接口失败及负结果保留，不自动并入 B。
- Coordination Optimization：10D/18D 为 Side Studies 隔离参考意图扩展，保留原执行与安全底座；没有批准直接迁移正式 B 接口。

## 最新开发结果的真实资格

夜间冻结 primary：`development_repair2_quality_NATIVE_SCALAR_18_063`。
完整同条件 J_F=**1400.697221 N·s**；B=**1438.613498 N·s**，降低
**2.635613%**。两者完整 TASK 均为 19.030 s；开发冻结 task/motion/safety
比较通过，但运动并非严格相同，治疗等效性未证明。

冻结新合法 prefix 条件：motion **0/4**；这属于同一 Human 的 remaining
suffix 验证，不是跨患者泛化。primary 没有按测试结果重选。
仅 **LEVEL1**，未证明原 Native-B LEVEL2、host-clock LEVEL3、真机或临床资格。
此前10D结果为 1403.259730 N·s / 2.457489%，合法状态 motion 1/2；
不得将文件名中的 NATIVE_SCALAR_18 误认作该前序研究具有18个自由参数。

## 平顺性与尚未解决问题

宽尺度速度起伏同时存在于 reference 和实际运动；终末制动存在额外跟踪响应。
已记录 C2 接续成立，不保证整条执行链或真实人体处处平滑。
18D 膝最大速度偏差 9.542°/s，髋为 4.963°/s；回程 RMS 改善，去程部分指标和
hip raw jerk 峰值未同步改善。raw acceleration/jerk 是数值导数诊断，
不能仅凭峰值宣称真实抖动或临床风险。没有证据证明波动不可避免。

原 R2/strict55/FAST 资格问题、状态覆盖、监督合同、跨状态 motion 可靠性、
治疗允许的中间姿态与平顺性依据仍待解决。工程 motion 容差不是临床阈值。

## 不得修改的底座

下一研究不能改变原 plant/Human/robot/contact/gravity/actuator、ROM、torque limits、
task goals、HOLD dwell/完成规则、truth firewall、40 ms bridge、100 ms lifecycle、
current-state admission、版本/phase/age 校验、causal receipts/native ownership、
carry/braking/fallback，或通过缩短任务与放宽阈值获得收益。
保持原 native 步进与物理顺序。历史失败、模型权重、唯一 trace 和冻结合同受保护。
新增能力置于版本化隔离模块；本次不把新研究写入 B，不训练或大规模搜索。

## 保存与复现索引

公开教授报告与来源：`docs/professor_update_2026-10-14/`。
单文件 `iHEAR_Professor_Update_2026-10-14.html` 内嵌三段真实保存状态回放、图与证据。
它是 mj_forward 渲染，未新增 physics run。速度诊断见同目录
`VELOCITY_SMOOTHNESS_DIAGNOSTIC.md` 和 `evidence/VELOCITY_DIAGNOSTIC_DATA.json`。
本轮核验与磁盘记录：`docs/stage_closeout_2026-10-14/`。

以下 canonical 包位于只读审计的 `/home/hank/coding/adaptive-traction-mpc-side-studies/`：

| 包 | 入口与保护对象 |
|---|---|
| b_fast_runtime_completion_v1 | REPORT.md、FINAL_CODE_MANIFEST.json、code/native closure、原R2失败与receipts |
| b_hold_return_critical_path_v1 | REPORT.md、科学gate、HOLD负结果；NOT_FROZEN |
| b_multirate_realtime_v1 / b_runtime_qualification_decoupling_v1 | 分时序资格与原执行归属 |
| b_native_learning_matrix_v1 / b_native_q_realtime_integration_v1 | 冻结Q、feature/action合同、训练验证与native执行记录 |
| direction-prior-value-v1 | REPORT.md、历史E/value及子研究合同 |
| m2_neural_q_motion_v1 | REPORT.md、MODEL_AND_FEATURE_CONTRACT.json、TRAINING_MANIFEST.json、NEURAL_DATASET.npz、models/ |
| m2_free_trajectory_feasibility_v1 | REPORT.md、PHYSICAL_ACTION_SPACE.md、BASELINE_REPRODUCTION.json、10D最佳及负结果 |
| ihear_overnight_research_retrospective_v1 | REPORT.md、REPRODUCTION.md、FROZEN_SELECTION.json、VALIDATION_RESULTS.json、CODE_MANIFEST.json、source/、weights/、motion_series/、关键trace/receipts |

这些原始模型/证据保存于本地包，不能因报告已push就宣称50 GiB历史实验已全部上传。
原工作目录还有332个既有暂存新增文件和39个初始未跟踪入口；没有未暂存tracked diff。
本轮只提交新收尾文件，既有研究修改保持原状态，不并入本次提交。
部分近期 runtime 只存在于这些本地暂存/隔离包；干净 Git checkout 本身
不等于已审阅整合的最新可运行正式 B。未来复用时需按 manifest 明确选择并审核源码闭包。

## 下一阶段起点

收尾前公开提交为 `15e981606ab8c5748fa0a638a9d18513173e9088`。
新的冻结 Git 起点是**新增本文件的收尾提交**，用
`git log -1 --format=%H -- CURRENT_RESEARCH_BASELINE.md` 获取精确 SHA；
最终 SHA 与 push 核验另记本地交付记录，避免文档自引用 SHA。

建议开发分支 `codex/continuous-coordination-planning-v1` 从该收尾提交创建。
下一阶段计划增加独立的连续髋膝协调规划模块，联合处理力、motion与平顺性，
保留当前 B 的执行与安全链，先冻结权限、合同和验收标准。
此处仅准备干净起点；收尾完成后 STOP，不自动开展研究。
