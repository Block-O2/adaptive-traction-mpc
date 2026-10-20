# T真实执行合同审计

**合同一致性：PASS；本审计无新physics。**

历史原生物理时钟与task相对时钟分开。N2 task origin physical=10.050s，最终request physical=16.835s。所有下表均为task相对秒。

|历史条件|臂|request|activation|splice|suffix时长|suffix结束|终点TRACK carry|OUT/HOLD/RETURN|
|---|---|---:|---:|---:|---:|---:|---:|---|
|N2|E|6.785|6.790|6.830|0.220|7.050|1.955|9.005/1.020/9.005|
|N2|T|6.785|6.790|6.830|0.330|7.160|1.845|9.005/1.020/9.005|
|U1|E|6.785|6.790|6.830|0.215|7.045|1.960|9.005/1.020/9.005|
|U1|T|6.785|6.790|6.830|0.325|7.155|1.850|9.005/1.020/9.005|

suffix自身的时间与phase clock是两个量。原MATCHED SACExpertEnv.transition_allowed要求非HOLD phase_elapsed>=9s、HOLD>=1s；runtime还要求真实estimated arrival、reference readiness、原settling/causal dwell。该下限在上一轮已存在，不是本轮改动。5ms控制网格与原状态机导致观测OUT/RETURN为9.005s、HOLD为1.020s，全task19.030s。

N2 composite包含40ms既有bridge和suffix。E composite=.260s，T=.370s；receipt progress无额外delay。T将suffix真实执行结束向后移110ms，同时从原终点等待TRACK区间中占用110ms：1.955s变1.845s。U1原suffix=.215s，T=.325s，carry1.960s变1.850s。HOLD并未被提前计入，也未缩短。

延长不是免费额外时间：phase内运动/终点等待的分配实际改变，属于固定倍率的直接后果。该变化已在真实receipt和native记录内，不能称运动参考时长不变。没有修改任务下限/timeout或重解释积分区间。

实际reference核验：用存档schedule边界独立求解quintic，逐个suffix/carry receipt q/dq对照，最大误差<1e-8；receipt progress逐项等于min(physical elapsed, composite duration)。末段到HOLD所有receipt均TRACK，无BRAKE模式切换、无progress delay或后续OUTBOUND重规划。后续反馈/被动Human仍可制动及settle，不等于监督器BRAKE。

所有positive receipts连续，全部native step按物理区间唯一归属，torque及步数精确匹配。历史receipt无直接plan_request_id字段：request→activation/composite→receipt的链接由唯一active时间区间、progress、完整多项式q/dq及原runtime元数据重建，不伪造直接ID。原current admission、连续几何certificate、mechanics、40ms桥与100ms生命周期的源码和原request记录保留在audit JSON。100ms是计划接受生命周期，已接受的参考可以继续执行更长。

证据为历史PHYSICAL_LEVEL1 raw的独立离线算术重建；数学曲线不是新物理验证，也不赋予host/strict/R2/FAST资格。下一阶段只使用冻结T。

详证：audit/T_EXECUTION_CONTRACT_AUDIT.json及四份HISTORICAL_TIME_EVIDENCE.json；精确源码hash和带行号规则保存在总审计JSON。
