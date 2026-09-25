# Integrated full-3D adaptive recovery v1

**BLOCKED_MECHANICS_OR_DEPLOYMENT_INFORMATION**

本轮首先解决了用户要求的物理可信性检查，发现阻塞不是旧 DEV-C 方法边界，
而是当前注册 setup 与固定髋–床–大腿碰撞几何的实质矛盾。33.35 kN 已证实为
MuJoCo 求解出的床–大腿法向反力；它从 commissioning 第一个积分区间起存在，
持续至少 7.025 s。它不是模型激活造成的短暂尖峰，也不是 N/kN、frame 或
per-contact/aggregate 报告错误。没有足够的物理依据唯一决定应如何修正该装配，
因此本轮没有更改控制器、辨识律或物理属性，也没有启动 fresh qualification。

## 1. 明确的本地基线和本轮工作

分支 `codex/stage5-architecture-recovery`，HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`。实际基线是更新后的本地 DEV-A
startup/ACTIVE_RECOVERY lifecycle；`dev_c_bumpless_transfer=False`，
`dev_a_recovery=True`。完整快照记录 607 个源码、配置、模型和 native 依赖的
SHA256、9.6 MB 本地 source archive、tracked working-tree patch 和起始 dirty
清单；末尾重新计算时 607 项全部未变。详见 `BASELINE_MANIFEST.json`。

本轮新增了 evaluation-only 装配/接触诊断、实际物理积分力采样、数据独立复算
与图表工具；未启用 DEV-C。三个真实 CR12–cuff–Human commissioning 前缀重放
使用历史规划延迟，分别到 7.025/7.030/7.025 s，最终 MuJoCo integration state
向量与原 DEV-B checkpoint 完全相同。记录包含 0.25 ms 物理区间、robot ctrl、
qpos/qvel、分 contact-pair 的力、距离、持续时间和冲量。力在原生 `mj_step2`
求解后、下一边界 `observe/_refresh` 之前读取，不触发额外物理步。

这证明最终物理状态及独立核对的 checkpoint 字段一致；**不声称每一个中间
完整状态或整个 pickle 文件逐字节一致**。Auditor 额外核对了 strongest 的
派生物理字段、模型/参考/控制字段。原 reference/qhat/cuff/robot 对齐历史 trace
仍保留并列入 review provenance。没有用这三段前缀冒充新的完整任务结果或
runtime qualification。

## 2. 33.35 kN 的来源和可控性

源码的几何关系为：

`z_bed = 0.012 m; r_thigh = 0.050 m; z_hip_nominal = 0.062 m`。

`thigh_geom` 是 `fromto=(0,0,0) → (L_thigh,0,0)` 的 capsule，近端球心与
**固定 hip hinge** 重合。注册 hidden setup 给 hip-z 加入 ±6 mm 偏移，床面
和 radius 保持不变。因此近端球的有符号间隙为

`g_proximal = z_hip − r_thigh − z_bed = Δz_hip`。

这个球心不随 q1/q2 运动，故负偏移造成的重叠不能通过关节控制消除。最强例
`balanced_near_upper_current_rom_r01` 的 `Δz=-4.819128111 mm`，与实际 contact
distance 完全一致。用克隆物理数据在 q1=0/5/15/40/80° 做静态诊断，固定近端
接触距离始终约 −4.819128 mm。这些静态赋值只用于 evaluation 几何检查，
不属于控制、恢复或任务执行。

在 t=7.025 s 的匹配 checkpoint：

| 量 | 独立重算 |
|---|---:|
| 单个 bed–thigh normal force | 33,353.295159 N |
| 同 contact 的切向 force norm | 322.835480 N |
| world force on thigh | [322.835480, 0, 33353.295159] N |
| contact world position | [−0.003885622, 0, 0.009590436] m |
| normal point Jacobian 对全部 DoF | [−5.55e−17, 0, …, 0] |
| normal inverse effective mass | 4.78e−33 1/kg |
| 接触广义载荷 `JᵀW` | [15.363881, 0] Nm（Human） |
| MuJoCo `qfrc_constraint` 对应 Human 分量 | [15.363881, 0] Nm |

法向力几乎没有可控关节力臂；它与固定髋的支撑约束形成反力。实际 15.364 Nm
Human 载荷来自约 47.590 mm 力臂上的切向摩擦。weld equality 已禁用，cuff
仍是原 compliant interface；没有发现额外 rigid cuff weld 在同时强制约束。
模型量纲、米制 radius/位置、正质量与力矩映射一致。这里不能把 33.35 kN
解释为患者实际可承受力、机器人施加的 cuff force，或已验证的床/组织接触。

核查采用的 API 约定与 MuJoCo 官方文档一致：`mj_contactForce` 返回 contact
frame 中 force/torque；frame 的行是局部轴，第一轴是 normal。我们用
`frame.T` 转为 world，再以 equal-and-opposite `mj_applyFT` 重构广义载荷。
来源：[MuJoCo simulation documentation](https://github.com/google-deepmind/mujoco/blob/main/doc/programming/simulation.rst)
和 [MuJoCo computation](https://mujoco.readthedocs.io/en/3.7.0/computation/index.html)。
这两个来源仅用于验证 API/frame 语义，没有据此修改物理参数。

关键源码：Stage-3 `coupled.py` 的 bed/capsule/fixed hip，Stage-5 `plant.py`
的 hip transform，`fresh_qualification_v1/scenario.py` 的 hip-z 扰动。
不是同名 nominal 模型替代了真实 varied plant：诊断直接读取实际耦合模型。

## 3. 时间、冲量与对照

每个冲量均为 `Σ F_normal[k]·(t[k+1]−t[k])`，使用实际积分区间，没有额外
terminal step。contact duration 是对应 geom pair 被报告的区间总时长；force
activity 另有字段。三例顺序运行，无 CPU 重任务竞争；延迟固定重放，因此本轮
wall time 不作为新的实时资格证据。

| 前缀案例 | thigh normal peak | thigh duration / normal impulse | shank normal peak | shank duration / normal impulse |
|---|---:|---:|---:|---:|
| strongest activation case | 33,353.295 N | 7.025 s / 234,306.898 N·s | 94.829 N | 1.14175 s / 80.454 N·s |
| balanced ordinary r01 | 0 N | 0 s / 0 N·s | 91.384 N | 1.085 s / 73.469 N·s |
| nominal development | 195.003 N | 0.829 s / 8.173 N·s | 119.327 N | 1.2495 s / 109.791 N·s |

strongest 的 thigh 接触 onset 是 t=0，normal 几乎恒定，与模型激活前后无关。
shank 接触约 t=2.4605 s 才出现，最大穿透约1.093 mm，不能把两个 contact
合并解释成同一事件。ordinary 是无 thigh-contact 的对照，但有 shank-contact。
nominal 的近端几何名义相切，只有机器精度级负 distance（最低约−4.16e−17 m），
仍出现非零接触求解载荷；其中 normal force>1e−8 N 的区间合计0.1305 s，
0.829 s接触检测时长还包含零力区间。这也需要解释，不能称 nominal 完全无床接触。

![接触与 Human 运动的对齐时间线](../../../results/full3d_adaptive_integration_v1/integrated_recovery_v1/review_v2/contact_timeline.png)

## 4. 原 clearance 指标覆盖范围

`fresh_qualification_v1/domain.py::mechanical_screen` 只检查 static shank
clearance、initial shank contact 和 CR12 endpoint IK。
`TruePhysicsMonitor` 的 true clearance 也明确为 **shank capsule** bottom
相对 bed plane；它不是 whole-leg clearance。当前 deployable session clearance
同样不能证明固定近端大腿没有重叠。本轮保持历史字段和文件原样，新诊断显式
增加 `immutable_proximal_thigh_gap_m`、pair 分离和 contact wrench。

旧24例全部保留。11例存在固定负近端间隙，范围 −5.967 至 −0.329 mm；13例
没有该负间隙。以下仅是历史 DEV-A 结果关联，不是重新运行或因果归因：

| 几何分组 | 案例数 | 历史 task entry | 历史 COMPLETE |
|---|---:|---:|---:|
| 固定近端负间隙 | 11 | 4 | 0 |
| 非负间隙 | 13 | 11 | 2 |

![旧24例固定近端间隙](../../../results/full3d_adaptive_integration_v1/integrated_recovery_v1/review_v2/old24_fixed_hip_gap.png)

**不将所有床接触自动判错，也不将所有接触视为允许支撑。** 已确定的是：当前
physically questionable 固定近端载荷没有被原 screening/metric 充分覆盖；
要把它解释为合法软床支撑需要额外物理依据。负间隙的静态不变性不等于已证明
所有 task 在数学仿真中不能完成，但它阻止可信的整域物理资格结论。

## 5. 对瓶颈问题的回答

- **机械 setup：OBSERVED / CAUSALLY_SUPPORTED（几何和载荷映射）。** 固定
  近端球重叠的解析关系、全 q 静态探查、实际全前缀与独立力矩重构一致。
  该异常在任何拟合激活前已存在；不能用 beta 更快更新解释或消除。
- **信息/辨识：OPEN。** 现有 commissioning 将 cuff-only 输入拟合到含床
  接触的物理响应；DEV-B strongest 的 residual/model 局部吻合包含约15.364 Nm
  未建模接触载荷。没有证据可把这种拟合直接叫作 free-motion patient dynamics
  已识别。本轮没有 cadence/cap/residual 干预，不能认定慢更新为主因。
- **accepted→applied 控制作用：历史局部因果证据保留。** DEV-B 34.8 Nm
  dynamics-switch、DEV-C 四例局部改善和有限 takeover 是有效的限定结果。
  DEV-C v2 后期步长超界和 v3 首拍拒绝也保留；本轮未混合其配置或启用它。
- **映射/执行/任务规则：仍 OPEN 且可能交互。** 无固定重叠的 ordinary
  仍历史失败，13例该组也仅2完成，因此接触异常不是全部失败的充分解释。
  暂无本轮 matched intervention 能将全部失败分别归于 B/C/D/E。

既有当前基线先以 population prior 完成固定 physical commissioning，随后
batch geometry fit/replay beta+residual、active recovery、settle、task HWMPC；
task 才继续20 ms更新。新模型是否及时且有用不能仅看 sequence：历史 DEV-C
局部 takeover 已证实，但其24例有8个终止时 latest accepted≠fully realized。
本轮所有重放停止在首个拟合命令之前，不产生新的 takeover 或完整性改善结论。

## 6. 为什么现在停止，以及唯一下一步

这次用户 amendment 已允许跨 DEV 字母边界修复；停止并非重新施加旧限制。
但是当前源码没有足够信息决定正确的实际支撑关系：应如何理解 ±6 mm hip-z
变化与床/近端碰撞体的关系？提高 hip、改变/截短 collider、改变床面/床顺应性、
增加骨盆自由度或只保留正偏移案例是不同的实质方案。任何一个都不是可由当前
证据唯一确定的单位或代码修正。任意选一项会改变物理假设或缩小注册域。

因此不能通过 estimator/controller 调参、删除 guard、软化接触或剔除11例把
该问题隐藏。本轮没有 stable candidate，未进入 freeze/fresh qualification。
这也是与 Auditor 一致的 `BLOCKED_MECHANICS_OR_DEPLOYMENT_INFORMATION`。

**唯一推荐下一步：明确并登记固定髋、近端大腿碰撞体与床面的物理支撑关系，
包括 ±6 mm z 扰动应代表什么；据此进行有依据的版本化装配修正，再从本轮
snapshot 恢复 integrated controller development。**

## 7. 历史结果、资格与尾部

本轮完整新控制器 old-24 regression：未运行；fresh qualification：未运行。
所有历史失败仍保留：原 fresh 三臂各0/24；DEV-A 24 commissioning/15 task
entry/2 complete；DEV-C v2 仍24/15/2。DEV-C v2 的127 planner calls 保留
5个>100 ms deadline miss、最大119.396 ms；不是本轮新计时结果。原 limits、
late-plan rejection和等待期真实物理reference执行未改动。没有对超时后的安全
物理尾段补做本轮资格，因此也不扩大其既有安全主张。

本轮没有任何 full-session improvement claim。未来120–130°范围仍是后续必需
能力，当前机制研究不构成大ROM、硬件、临床或HEX资格；未进行学习训练。

## 8. 复核和可运行交付

`COMMANDS.md` 提供环境前缀和全部命令；`EXPERIMENT_MANIFEST.json` 记录输入/
输出/new diagnostic source哈希；`CHANGED_FILES.md` 列出新增文件与无生产变更；
`METRICS.md` 定义量纲和时间；`ARCHITECTURE.md` 是数据流图；独立结论在
`INITIAL_AUDIT.md` / `AUDIT_REPORT.md`。本轮只在本机运行模拟，未上传数据。

验证包括3个最终 integration state精确匹配、全部区间连续/时长/冲量独立复算、
607个基线哈希保持、20项聚焦软件测试通过、诊断JSON解析和 `git diff --check`。首次静态诊断因安装
MuJoCo的 `mj_fullM` API签名而失败，已改为 `mj_fullM(model,data,dst)`；这是
诊断脚本兼容修正，没有科学结果被当作失败或剔除。

代码/模型依赖和大量结果仍未提交，heavy checkpoints在本地保留。compact
review package只包含轻量对齐trace、报告、config、source patch和hash索引，
不代表一个 clean clone 能直接重现当前工作树。未 stage/commit/push/reset/
stash/switch branch，未删除历史或无关文件。
