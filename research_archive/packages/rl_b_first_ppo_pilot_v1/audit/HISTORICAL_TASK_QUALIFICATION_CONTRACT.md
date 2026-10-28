# RL-B 任务资格合同审查

本轮是 `UNQUALIFIED_TRAINING_SMOKE` 与既有证据复核；不授予正式训练或 B/H150 科学资格。来源为实际部署包和 ZIP，不引用不存在的仓库路径。源码指纹见 `audit/CONTRACT_SOURCE_REFERENCES.json`，完整旧包保护见 `audit/protected_before.json`。

## 两种独立资格

**RUNTIME_TASK_COMPLETE**：当前部署的 `SCIENTIFIC_SIMULATION`、`commissioning_only`、High-ROM nominal、DEV-A/DEV-D、native planner event 模式，按原传感器任务时钟和实际 native commit 完成 OUTBOUND → HOLD → RETURN → COMPLETE，且无 abort。任务不是单纯走满某个秒数。

- `source/.../task.py:at_goal` 要求在原 ROM 内，两关节目标误差 ≤1°、速度 ≤2°/s。在线完成可用更保守 margin；不扩大原目标集合。
- `source/.../high_rom_v1.py:contract` 加载 `configs/high_rom_v1/stage5_goal_task_120_v1.json`：起点/返回 [5°,10°]，目标 [120°,120°]，ROM [0°,125°]，原 dwell **0.5s**，phase timeout **10s**。必须区分配置 dwell 与观测到的整个 HOLD phase 1.020s。
- `pure_rl_env.py:transition_allowed` 还保留既有比较 timing floor：移动 phase 至少9s、HOLD phase至少1s；本轮逐字节保持。HOLD 1.020s不是把配置 dwell 改为1.020s，也没有缩短任务。
- `activation_validation.py:SensorSupportedTaskClock` 只给连续、有效、因果传感器区间 dwell；不满足目标或缺失连续性则清零；重复 timestamp 不增加 dwell。投影就绪与reference连续就绪共同约束 handoff。
- `pure_rl_env.py:_run` 传原 TASK deadline **30s**；phase 到期由原状态机判定。上一轮修复后的 reference-safe handoff 不允许已经超过10s的晚到完成覆盖 timeout；最终 native RETURN commit 再检查原 phase/TASK deadline。精确边界采用源码原有容差，不新增期限。
- COMPLETE 要求 start_validated、outbound_hold_completed、无 abort，原因果 RETURN 实际完成提交；wrapper 拒绝只有 status 字样、没有完整 phase/commit 证据的成功奖励。
- 原生终态是 COMPLETE / ABORTED；TIMEOUT_*、GLOBAL_TASK_TIMEOUT、NO_FEASIBLE_WAYPOINT、LOW_LEVEL_EXECUTION 等是 abort reason。没有将本轮报表 FAIL 伪造为原生状态。

**MATCHED_19_03_QUALIFIED**：必须满足冻结匹配评价的全部 task/safety/motion/causal 条件，以及封存 `verify_physics.py:audit` 的必要时长条件 `abs(task_s-19.03)<0.05`。该判定比 runtime COMPLETE 更强，不能只凭时长或 COMPLETE授予。

目前可追溯的实际部署验收链包括：独立 reward/terminal审计、完整任务/causal commit、proposal/request 一一对应、immutable causal source、同 episode/model 的 <100ms admission、当前状态 certificate、40ms bridge、native grid、ROM、禁止 bed contact、有效执行 geometry/reference acceleration、正的实际 receipts、唯一 native torque ownership及 executor退出；maximal另要求实际 bridge/admission与拒绝后合法 fallback/resume。`cloud_case_audit.py` 和 `cloud_motion_audit.py` 补充实际Human native/5ms/20ms速度加速度、force/moment/torque/clearance与truth firewall审计。这些条件保持各自来源和适用模式，不被简化为一个时间戳。

**证据边界**：服务器和原 ZIP 没有部署正式 B/H150 的完整历史匹配 Master Contract／资格矩阵；只发现上述 RL-B 冻结回归、High-ROM任务/物理配置与 online-interface development合同。因此不能将 RL-B 回归的全部通过包装成正式 B/H150 全资格，也不能自创其缺失的充分条件。正式 B/H150全合同恢复审查标记 NOT_EVALUABLE。RL-B 的已知必要时长失败仍是明确 FAIL，无需等待缺失合同才承认该失败。原runtime模式与历史匹配模式身份分别保留。

## 原20.165s随机任务的双重结论

`../rl_b_cloud_g4_repair_v1/runs/repair_random_01/physics/env/episode_0001/` 原summary、raw、native journal与本轮只读复算可直接追踪：OUTBOUND9.260s、HOLD1.020s、RETURN9.885s，总TASK20.165s，准备10.050s独立排除。最终transition为 `causal_return_actual_completion_commit`，无abort，各phase小于10s，TASK小于30s。

- RUNTIME_TASK_COMPLETE：PASS（该单个已观察 nominal episode）。原力、motion、安全、因果执行审计PASS。
- MATCHED_19_03_QUALIFIED：FAIL，时差+1.135s，超出封存允许范围；其他已观察执行检查通过不能抵消此失败。正式 B/H150充分条件缺失另记NOT_EVALUABLE。

没有把20.165改成19.030，没有延长deadline、缩短HOLD/任务或改评价公式。

## governor、fallback与动作拒绝

actor两维[-1,1]值是每个原 native planner event 的最大进度比例；不是直接torque、50ms rate或B/H150轨迹。HOLD候选忽略actor的任意比例，仍指向原mandatory目标。原planner构造candidate，再由certificate/current-state admission/100ms生命周期/40ms bridge/governor/低层执行决定实际扭矩。拒绝提议不成为已执行动作，也不获得伪造物理积分。

有预验证escape时，拒绝可保留escape并commit→brake→stop→hold，只有fresh、有效且未过期的重规划才能resume；没有可用合法候选/escape则原NO_FEASIBLE终止。连续拒绝不等价于存在一个任意次数的原生REPEATED_REJECTION终止器。原random五次fallback与maximal一次均有原receipt证据；governor额外delay合计0，不把总时差精确归因为governor或全部fallback。

正式训练门保持 `qualify.py` 的原严格自然失败矩阵和完整执行回归；本轮功能入口没有写PASS到READINESS，也没有给 `train.py` 取消门禁。
