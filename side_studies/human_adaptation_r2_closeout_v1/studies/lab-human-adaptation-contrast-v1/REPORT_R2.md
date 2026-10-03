# Lab Human Adaptation Contrast R2
2026-10-04 02:51 Asia/Shanghai。STATUS：COMPLETE，已 STOP。主运行21/21，A/B/C成功1/7、6/7、6/7；另1次oracle完整成功与1项静态交接诊断，均排除主统计。13次主任务COMPLETE且独立physical/scientific均PASS；8次ABORTED physical FAIL，21次scientific状态/来源一致性均PASS。

冻结条件：身高1.72m，thigh.43688m/shank.40076m；mass60/75/90kg，K7/10/13双关节，rho.60/.66/.72；damping5/5、rest5°/10°、ROM/软限制/床/机器人/安装规则不变。任务5°/10°→120°/120°，完整OUTBOUND/HOLD/真实RETURN。保持同一旧四人体runtime/reference/pacing/measurement/scorer；CPU线程1、无渲染、无GPU，无RL/Gym新接口混用。NumPy源码fallback同用于全部臂，非实时后端等价证明。

|条件|A/B/C有效完整任务|B/C真实tracking RMSE（两关节合并，°）|C−B J_F|
|---|---|---:|---:|
|C0 nominal|PASS/PASS/PASS|0.509/0.515|-0.041%|
|C1 mass_low|FAIL/PASS/PASS|0.516/0.512|+0.227%|
|C2 mass_high|FAIL/PASS/PASS|0.473/0.460|+1.719%|
|C3 stiffness_low|FAIL/PASS/PASS|0.613/0.520|+0.067%|
|C4 stiffness_high|FAIL/PASS/PASS|0.617/0.520|+0.843%|
|C5 cuff_proximal|FAIL/FAIL/FAIL|—|不可比较|
|C6 cuff_intermediate|FAIL/PASS/PASS|0.529/0.538|+0.095%|

**B−A：** nominal无实质改善，J_F约+0.022%。60/90kg、K7/K13、rho.66的固定臂失败，B/C均恢复为完整任务；这是commissioning及后续恢复的完整链收益，不是同起点TASK消融。A在60/90kg发生ACTIVE_RECOVERY_TIMEOUT；K7/K13与两种袖套偏差的A发生TIMEOUT_OUTBOUND。A的全部beta/residual/数值几何固定；继承的因果袖套参考中心常量对齐已记录，未作个体参数拟合。

**C−B：** 成功数相同。K13的两关节合并真实tracking RMSE由0.617°至0.520°（-15.8%），同时J_F+0.843%、clearance略减少但通过原限值；K7 tracking约−15.1%。nominal与rho.66的tracking略恶化。六个可比完整任务的J_F变化范围-0.041%至+1.719%，无一致交互积分收益。90kg C任务比B长约0.5s，积分包含实际任务时长差。不能把持续更新称为统一赢家，也不能称其没有任何额外价值。

**辨识与消费：** B/C各条件commissioning的beta/residual/geometry数值完全相同（独立进程、未跨臂传数据）。14个几何拟合均接受，knee-to-cuff误差约0.17–19.90µm；rho.66约9.04µm，rho.60约19.90µm。C在自身TASK数据上，更新前模型相对冻结commissioning模型的逆动力学重建RMS误差下降67.4–96.3%；这使用因果重建力矩和事后有限差分加速度，是未用于commissioning的TASK误差表征，不是未来预测或同分布外部holdout。跨臂状态/力矩范围不同，不能仅用不同臂RMS或beta版本/L2证明学习。13个成功主任务均观测到独立planner/mechanics/execution实际数值模型哈希，包括子进程；4个提前失败运行存在明确未访问/未覆盖的planner/mechanics消费记录，未伪造。B TASK beta/residual冻结；C任务几何固定，合法beta/residual继续更新。

**rho.60重要失败：** B/C拟合有效距离准确，但在commissioning后进入保守几何域外，ACTIVE_RECOVERY_TERMINAL_REFERENCE_SEARCH_NO_FEASIBLE_POINT_FOUND，尚未执行恢复段。原0.46m结构性小腿先验下，即真有效几何在记录的交接真实q也得到distal-shank margin−1.829mm，而记录真实物理clearance约+5.170mm；46次连续路径检查全拒绝。D1从初始化即使用真有效模型（此条件真beta恰等于名义beta，显式注入真几何，零拟合/更新）在同任务/阈值/先验下完整成功，OUTBOUND/HOLD/真实RETURN全通过。故不能把rho.60任务视为固有物理不可行；普通链失败涉及旧模型commissioning→拟合坐标交接→保守安全域边界。D1的原scientific verdict只表明状态/版本一致性，刻意真参数注入不属于主臂因果学习证据。

**比较限制：** 恢复失败的TASK入口单样本及0积分均明确标为ENTRY_ONLY_NO_TASK_EXECUTION；其他失败短轨迹不与完整任务排名。完整truth只用于生成/评价或明确标记oracle。七个合成人体条件不是21独立成人样本，不做显著性/临床/任意人体推广。除已标明的局部oracle诊断，不声称已一般分离几何、beta、residual贡献。几何预筛仅必要条件，完整仿真通过不是硬件安全证明。rho.77/.85旧静态边界、原身高静态研究及全部185份既有文件逐字节保留。

**资源与隔离：** 首C0-A资源资格化通过并计入21主运行；未使用旧Windows峰值+4GiB门槛。物理父进程lifetime RSS峰值2.007GiB、最大单个reaped child lifetime峰值0.755GiB，非同时峰值和约2.762GiB；30s采样owned进程合计峰值1.640GiB，非精确总峰值。全期swap峰值0、OOM增长0，无资源告警/侧任务强杀。Windows最低1.041GiB出现在SAC diagnosis占用时，挡住下一次启动直到恢复；WSL最低4.873GiB。未发现>5k长训练/正式吞吐并行；SAC诊断自然完成后继续，不改/停SAC进程、repo、branch/index、共享STOP或环境。普通CPU重叠影响未作因果性能benchmark，所有wall-time仅characterization。

本次会话约90.1min，主运行harness累计22.1min；含前期准备的保守有效计时约124.6min，低于6h。两次仅harness/日志/准备目录修复与回归，零控制器/辨识/阈值调整。6个非关键成功日志去除冗余预测展开后，原physical/scientific/wall characterization逐项完全一致；完整失败/关键/oracle证据和压缩实际轨迹保留，未复制训练/归档历史。

详细结果：PRIMARY_MATRIX_R2.csv/json、COMPARISON_R2.csv/json、MODEL_IDENTIFICATION_RESULTS_R2.csv/json、MODEL_CONSUMPTION_EVIDENCE_R2.json、RESOURCE_DYNAMIC_QUALIFICATION.json、RESOURCE_OVERLAP_LOG_R2.json、PAIRING_AND_INITIALIZATION_AUDIT_R2.json、CONTROL_MODEL_FREEZING_AUDIT_R2.json、诊断与RETENTION_FINAL_R2.json、RAW_DATA_MANIFEST_R2.json。

后续需审查纳入的仅本目录R2 protocol/cases、harness/guard/analysis scripts、模型/配对/资源证据与报告；未向主仓库写入，未commit/push。
NEXT：下一独立研究优先验证commissioning→recovery的保守几何域兼容性，保持安全阈值；本轮不启动combined、RL或hardware，STOP。
