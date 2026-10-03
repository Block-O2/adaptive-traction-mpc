# Commissioning-to-Recovery Geometry Compatibility v1

STATUS: COMPLETE_DIAGNOSIS_FIX_BLOCKED. 三条原路径精确复现；没有实现控制、接口或阈值修改。完成后 STOP。

## 结论与最小证据链

主因属于 **C/G/H**：名义模型 commissioning 到达的真实状态，与保留完整小腿保守上界的 recovery certificate 不兼容；certificate 按既有规则正确拒绝该状态。没有找到在冻结 handoff 和当前合法辨识信息下可部署的局部软件修复。

1. B/C 的 fit、beta、residual、handoff q/dq 和全部数值轨迹，与原 R2 精确一致。有效 knee-to-cuff=0.240475899 m，对模拟 truth 的误差19.899 µm；拟合位置残差 RMS1.505 µm、最大17.154 µm，352样本。完整小腿长度与 rho 未分别辨识。
2. 两个失败路径 handoff 的估计 q=[5.338567°,11.150913°]，dq=[0.004908307,0.012384048] rad/s；真实 q/dq 见 HANDOFF_EXACT 与 RECOVERY_EXACT。拟合 world hip=[0.000039235,0,0.062115336] m、L1=0.436819886 m。旧 emitted joint reference=[5.5°,9.5°]、dq/ddq=0；新 recovery candidate origin 使用 fitted causal observation。没有物理状态或历史 reset。
同一物理边界上，旧 population observer 估计 q=[0.117311868,0.218756440] rad；新 fitted observer 估计 q=[0.093175569,0.194620140] rad。旧名义袖套 lever 导致 q1/q2 同时偏高，观察到的 shank pitch不变；更新几何后状态估计纠正、未重置物理状态，暴露了该实际姿态对应的保守小腿端点违规。这个内生状态重表达单独记录于 HANDOFF_OBSERVER_REEXPRESSION.json，不混同于固定q的单因素矩阵。

3. 在完全相同 handoff 下，fitted geometry 的 distal-shank margin=-1.827095 mm；exact true effective geometry=-1.836838 mm；真实物理 clearance=+5.170123 mm。几何拟合误差不是负号的充分原因。
4. 首条 continuation 连续证书下界=-1.840858 mm；46条候选全部拒绝，执行0个 recovery interval。没有 planner/mechanics task-model 消费；已接受个体模型未激活，不能用版本号或拟合成功替代执行证据。
5. 正确 world-hip gauge 变换、oracle recovery origin 语义、ownership 标签均不改变负号。旧 commissioning cuff translation=(-46.9264,-0.00146,-5.1910) mm，只作用于 tool/sleeve reference；带入 fitted recovery 后 shank gap不变而 sleeve变负。当前 recovery 已使用 fresh zero offset，没有 offset 双计。
6. 重用旧名义 q 作为新 geometry 的 candidate origin 能得到假想 +13.894689 mm，但对应 emitted pose 位置差5.684 mm，实际 handoff gap仍为负。正确反解旧 emitted robot pose 后 origin gap仍为-0.527015 mm，且存在1.182 mm投影位置差。它们均未实施。
7. 保留 fitted geometry、仅在诊断中换成 oracle 到达的 q，gap变为+6.073567 mm；oracle geometry 在其自身状态为+6.066522 mm。决定局部符号差异的是状态与 prior 的组合。

## 为什么 existing oracle 可以通过

既有 oracle 完整成功，但不是 failed handoff 的 SAME-STATE oracle。它从初始化注入 true effective geometry，经另一条 commissioning/加载链到达 q=[7.928032°,15.208222°]，具有正的 conservative margin。两条 recovery 均使用同样 .46 m full-shank upper、1 mm margin、零 cuff translation 和相同 conservative checks。

还发现此前 oracle 描述需要限定：在 runtime.py:264 以被替换的 control geometry 求 loaded equilibrium 后，runtime.py:267–269 仍用未替换 STAGE5_GEOMETRY 的 nominal cuff frame 重表达 preload。两者初始 Human q相同，但机器人 attachment 实际位置相差 **47.747426 mm**，robot q、初始支撑动作及 startup alignment 不同。此初始化差异在 handoff 之前已存在。它是明确的 oracle setup/reference 消费不一致，不能把 oracle 成功归因于同机械初态下的几何辨识，也不能据此宣布 commissioning handoff 有 arithmetic bug。本研究没有进一步分离 preload 与后续 model/reference trajectory 对 oracle 成功的各自贡献。

## 0.46 m prior 的角色

这是固定的 **完整 knee-to-ankle shank 长度保守上界**，用于最坏情况 ankle/cylinder 构造；不是 knee-to-cuff 距离、不是估计器参数上界，也不是已测得的个体安装长度。配置和两个 clearance dataclass 一致。估计器 knee-to-cuff 上界是0.48 m，与0.46 m不同。

本 handoff shank pitch向下，公式为
\[
\min(z_{knee},z_{knee}+0.46\sin(q_1-q_2))-0.045-0.012-0.001.
\]
模拟 full shank=0.40076 m，其与prior的59.24 mm差异导致约5.9993 mm额外向下延伸；加上1 mm保守margin，解释物理正clearance与certificate负值。要令该 handoff 的 fitted shank certificate非负，需要 full-shank upper≤0.441958296 m；当前 commissioning 没有合法测量依据支持这个收紧。只在静态 hidden-truth diagnostic 中改为0.40076 m会得到+4.172179 mm，未用于控制或修复。

Frozen commissioning 允许明确受限的 nonworsening shank escape，源码明确禁止该例外用于 TASK/RECOVERY。把例外复制到 recovery、删掉起点、选择虚构 ownership 状态，都属于改变既有 certificate 行为，未实施。

## 复现结果与模型消费

| 路径 | COMPLETE | physical/scientific | OUT/HOLD/true RETURN | TASK时间 | TASK J_F |
|---|---|---|---|---:|---:|
| rho=.60 commissioning-only | ABORTED | FAIL/PASS | 否/否/否 | 0 intervals | 不适用完整任务比较 |
| rho=.60 continual-adaptive | ABORTED | FAIL/PASS | 否/否/否 | 0 intervals | 不适用完整任务比较 |
| existing known-truth oracle | COMPLETE | PASS/PASS | 是/是/是 | 15.49 s | 1187.608929 N·s |

Oracle TASK peak force109.239931 N、peak moment13.148696 Nm、deployable minimum clearance6.654246 mm、actual diagnostic clearance12.044649 mm。完整 mean/RMS/integrals/各阶段peak/tracking/update/prediction与数值消费hash在 COMPARISON.json 和 MODEL_CONSUMPTION_EVIDENCE.json。两个失败路径仅有TASK入口节点，force80.981402 N、moment9.482749 Nm；它们的零积分不能与完整成功任务排名。

Oracle 的 planner/mechanics/execution 数值消费均有逐PID记录；B/C在certificate前置拒绝，因此planner/mechanics缺项如实保留。失效路径没有TASK预测质量数据。Scientific PASS仅说明此冻结仿真记录的状态/来源/消费与评价模式一致，不等于physical成功或deployable oracle。

## FIX 与回归决定

**FIX: BLOCKED_NO_DEPLOYABLE_LOCAL_FIX_DEMONSTRATED；实际patch=0。**
降低未测 full-shank upper需要hidden truth，不能实施。当前没有证据支持通过合法几何表示变换使同一实际起点被原certificate接受；也没有证明任何未来causal commissioning设计都不可能成功。

rho=.66/.72没有新修复回归，因为未实现修复。FIX_DECISION.json保留原R2对应 commissioning-only COMPLETE/PASS/PASS的只读引用，明确不是本轮新回归。不能声称本轮满足“修复后四项回归”。所有140冻结源码hash与原670证据hash保持一致，阈值、task、prior、算法均未改变，故也没有宣称 envelope 被整体放宽或修复已经通过。

## 资源、保留与停止

严格单physics owner、CPU/nice19、数值线程1、无GPU/RL/渲染。三次run连同scorer wall总计125.74s；包括独立准备和静态审计的目录记录elapsed约18.8min。Host wall用于characterization，不是干净性能benchmark。
Parent含序列化/scorer lifetime RSS peak=1.950GiB；sampled planner-child VmHWM=0.149GiB（不是精确生命周期峰值）；sampled aggregate=0.905GiB。采样Windows minimum available=2.335GiB、WSL minimum=6.090GiB，swap0、OOM0、MuJoCo warnings空。SAC处于idle/STOP，未观察到SAC worker，未修改或影响SAC。

仅复制冻结最小源码、三条新关键轨迹；own event logs lossless压缩，未复制历史结果库。原R2与主repo只读，无git操作/环境变更/sharedSTOP写入。没有后续生产纳入文件；这些是独立诊断证据。NEXT: STOP，保留exact blocker；任何新的commissioning protocol或registered anatomy信息需另行授权与版本化研究。
