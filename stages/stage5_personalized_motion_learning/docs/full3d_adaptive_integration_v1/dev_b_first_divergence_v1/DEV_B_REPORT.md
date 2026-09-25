# DEV-B — 匹配状态首次偏离诊断

状态：`DEV_B_DIAGNOSIS_COMPLETE`；独立审计 PASS（有界诊断结论）。
版本 `dev_b_first_divergence_v1`，development/diagnostic
simulation only。旧正式结论 `FULL3D_FRESH_FAILED_WITH_EVIDENCE` 不变。

## 结论与证据边界

**CAUSALLY_SUPPORTED：最大的模型激活命令突变主要起源于 Human inverse-dynamics
广义作用的突然替换，随后通过原有 wrench 分配和 Jᵀ映射传到 CR12。**
在同一观测、物理状态、robot 参考和控制历史下，旧/新命令差为 34.833872 Nm；
沿总变化方向，动力学项贡献 97.01%，状态项 2.68%，交互约 0.312%，
allocation geometry 项约 −0.000785%。这些是向量投影，范数不能相加。

**CAUSALLY_SUPPORTED：这个上游突变造成局部物理瞬态。** 仅改变最初作用量
的应用过程，最大案例瞬时 Human acceleration 峰值 9.918→0.813 rad/s²。

**OBSERVED / OPEN：它并未被证明是后续恢复超时的根因。** 完整恢复反事实中，
production 和减弱首次突变的分支均在 9.055 s 停止；没有剩余时间再容纳原有
1.5 s 最小轨迹段。此次诊断没有修好完整生命周期，也没有推广新控制器。

**OBSERVED：床接触是重要模型解释限制。** 最大案例存在约 33.353 kN
MuJoCo 床–大腿法向反力，贡献 [15.364, 0] Nm Human 广义载荷。
candidate 模型与 cuff-only 输入的局部吻合包含接触条件，不能称为独立
Human 动力学辨识成功。这个接触量与 cuff 力量不是同一物理量。

唯一建议的下一修复是模型激活时的控制作用连续迁移，详见
`DEV_C_DECISION.md`。没有实施 DEV-C。

## 案例、检查点和可重复性

四例均来自已有开发/已消耗数据：

| 案例 | DEV-A 角色 | 捕获物理时刻 s | 同态旧/新 robot torque 差 Nm |
|---|---|---:|---:|
| balanced_near_upper_current_rom_r01 | 最大激活突变、恢复超时 | 7.025 | 34.833872 |
| balanced_ordinary_r01 | 恢复成功、task clearance 拒绝 | 7.030 | 2.210271 |
| balanced_middle_r01 | 完整任务成功 | 7.030 | 7.657037 |
| development_nominal | 原 nominal 完整任务 | 7.025 | 0.001221 |

OBSERVED：最大案例的名称表示任务目标所在 operating cell；激活发生在低角度
task-start 附近，不能把这个时刻误称为 near-upper-ROM 姿态。

保存位置是 software model/observer 已更新、生产 guard 已检查，但新模型
尚未计算/执行第一个命令的边界。保留 old model 与同一 interface inversion，
因此可以在完全相同物理状态下计算新旧命令。完整 `MjModel`、`MjData`、
`mjSTATE_INTEGRATION` 和 qacc warmstart、robot helper models、last command、
measurement history/RNG、observer cache、reference history、supervisor、
monitor/authority、updater 全部历史、beta/residual、schedule/bridge、phase、
time、pending plan 均被复制/序列化。没有仅靠 qpos/qvel reset 来声称匹配。

OBSERVED：四个检查点的 true q/dq、robot q、qhat、beta 与历史记录差值均为
精确零。每例的两个独立 activated 克隆在 200 ms 后 full integration hash
相同；每条 production 分支的 40 个命令/状态边界与历史 q/dq/qhat/torque
也精确一致。最大案例 1.5 s baseline 同样复现历史。

捕获时重放历史实际记录的规划延迟，使等待的物理步数相同；没有用当前
host wall time 改变分支的初态。物理仍执行原来的等待 reference。这个阶段
不产生新的 runtime qualification 结论。原 DEV-A 的 4 次 >100 ms task
planning abort 保持原样；未对其做优化或重测。

## 源码链和方程

以下 Stage-5 源码路径均相对
`stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/`；
Stage-4 allocator 位于 `stages/stage4_adaptive_control/src/traction_mpc_stage4/cuff_allocator.py`，
Stage-3 executable 位于 `stages/stage3_full3d/src/traction_mpc_stage3/executable_command.py`。

1. `full3d_adaptive_integration_v1/runtime.py::_run_dev_a_active_recovery`
   在等待结束后把 prior 替换为 commissioning 的 `belief_310`。
2. `controller_interface.py::InterfaceAwareHumanStateObserver.update`
   复用同 timestamp 的 interface cache，再由新的 `PlanarCuffGeometry.estimate_state`
   求 qhat/dqhat；不会重复把同一 interface 数据向前积分。
3. `human_waypoint_shadow.py::HumanWaypointMPCShadowContractV1.command`：

   `a_req = Kp (q_ref − q_hat) + Kd (dq_ref − dq_hat)`

   `u_H = Y(q_hat,dq_hat,a_req) beta − tau_soft_limit + clip(W phi(q_hat,dq_hat))`。

   记录中的 ddq_ref 用于参考/监测，当前这一 inverse-dynamics 路径的输入是
   上述 PD acceleration，不是直接把 ddq_ref 加入前馈。
4. Stage-4 `CuffAwareSagittalAllocator` 在 `B(q) w_sagittal = u_H` 下使用
   原 force+surface-effort 代价。几何来自当前可部署 effective geometry。
5. `loaded_execution.py::build_stage5_loaded_execution_context` 保持两个
   cuff 参考点明确：`F_robot = F_human`，
   `M_robot = M_human − (p_robot−p_human) × F`。再加笛卡尔 feedback。
6. Stage-3 `executable_command.py`：

   `tau_raw = b(q_R,dq_R) + Nᵀ[k_post(q_neutral−q_R)−d_post dq_R]`
   `          + J_Rᵀ (W_allocator + W_position + W_velocity + W_orientation + W_angular_velocity)`；

   actuator command 为原 torque bounds 内的逐分量 clipping。
7. `runtime.py::_execute_interval` / `Stage5LoadedTrackBrakeSupervisor`
   实施原 filter/supervisor，然后 `plant.apply_executable_command` 和
   20 次 `plant.step()`。弹性 cuff 是真实的 Kelvin–Voigt 作用对，
   通过 MuJoCo force application 和物理 stepping 传给 Human；没有直接
   Human torque actuator，也没有赋值 Human 状态。

所有 world wrench 使用 world XYZ；force 是 N、moment 是 Nm。机器人 base
与 world 轴在当前配置下平行（旋转矩阵为 I，平移 [0.6,−0.62,0.04] m），
所以当前 robot-site Jacobian 的轴表达兼容 world wrench；没有把此结论
推广到任意 base rotation 或硬件 frame。物理测量的 cuff moment 位于 Human
site；与 robot-site command 比较时必须先转换参考点。

重要字段更正：历史 `allocated_wrench_world` 保存的是
`command.wrench_total_world`，包含 feedback；历史文件没有改写。
本诊断分别保存 `allocation_human_wrench_world`、command 的 allocator
force/moment、各 feedback、总 wrench、最终 torque，防止混用。

## 最大事件的同态分解

OBSERVED：在 t=7.025 s，状态从旧几何估计
`[0.138245, 0.259239, −0.024622, −0.051655]` 变为
`[0.141791, 0.262785, −0.024471, −0.051507]`（rad / rad/s）。
true state 为 `[0.141678, 0.262668, −0.024629, −0.051544]`。
位置估计误差由约 0.197° 降为约 0.0067°，没有出现更坏的估计跳变。

| 量 | 同态旧控制 | 同态新控制 |
|---|---|---|
| PD acceleration rad/s² | [−7.155599, −10.245246] | [−7.798129, −10.744963] |
| Human generalized action Nm | [31.010573, −5.233545] | [12.745032, −5.175542] |
| state residual Nm | [0, 0] | [−12, −0.201876] |
| robot-site allocator force N | [−34.496772, 0, 54.771269] | [−1.498593, 0, 17.651932] |
| robot-site allocator moment Y Nm | 9.425893 | −0.322396 |

CAUSALLY_SUPPORTED：固定旧状态/旧 allocation，单独更换动力学产生
17.200745 Nm Human action 差；固定动力学替换状态为 1.102937 Nm，
交互项 0.002624 Nm。固定新状态和几何进一步分解：beta 变化贡献
`[−5.196814, −0.012686]` Nm，残差贡献 `[−12, −0.201876]` Nm；
它们对应 robot torque 变化范数分别 9.972489 和 23.638060 Nm。

| 同态 robot torque 贡献 | 变化 L2，Nm |
|---|---:|
| allocator wrench 经 Jᵀ | 34.833872 |
| position / linear velocity / orientation / angular velocity feedback | 各 0 |
| bias | 0 |
| nullspace posture | 2.85e−14（数值舍入） |
| saturation | 0 |

完整 robot torque 差向量为
`[−20.458872, −12.644785, −17.836520, +8.480588, +4.246097, −15.061589]` Nm。
分量重构误差 <1e−10 Nm。历史相邻 5 ms 跳变为 34.780445 Nm；其中
allocator channel 变化范数 34.812778 Nm，position 0.029609、orientation
0.011125、其他各项 <0.001 Nm，向量相加恢复原跳变。相邻数值和同态
34.833872 的差来自那一个 5 ms 内实际状态变化，不是两种矛盾结果。

RULED_OUT（仅限该边界的主要起因）：新几何分配不是大放大源。
固定 q、u_H，geometry-only 改变 force 0.402346 N、Human-site moment
0.075016 Nm，完整 robot torque 0.308832 Nm；allocation dual matrix
condition 69.13→65.49，没有恶化。B 的 force/moment 列有不同单位，
该 raw condition 只作算法诊断，不冒充单位无关的物理条件数。
同 q 新旧 session clearance 分别 10.217/3.448 mm，说明 clearance
证书确实改变，但不能解释此刻 34.8 Nm 的命令差。

RULED_OUT（该匹配边界）：Jacobian、robot feedback、bias、clipping、stale
measurement 不是首个突变来源。COMMISSIONING/ACTIVE_RECOVERY 上下文对照
的 torque 差为零，因为 bridge 起点的目标 twist 同为零。原命令均 TRACK。

## 真实物理后果

每条 200 ms 分支记录 40 个控制区间、801 个物理边界。下面 acceleration
是 MuJoCo 每 0.25 ms 边界的瞬时 qacc 峰值，不能直接替代生产的 20 ms
motion-acceleration authority，也不能据此倒改历史合格/违规标签。

| 案例 | production qacc 峰值 rad/s² | diagnostic transfer 峰值 | production cuff peak N | transfer cuff peak N |
|---|---:|---:|---:|---:|
| 最大突变 | 9.918176 | 0.812736 | 90.584917 | 87.121832 |
| ordinary、后续 task 失败 | 3.049549 | 1.079977 | 100.068750 | 100.501707 |
| middle、DEV-A 完成 | 6.962879 | 1.572098 | 79.692796 | 79.692796 |
| nominal | 0.029574 | 0.026637 | 79.309191 | 79.308908 |

CAUSALLY_SUPPORTED：三条 varied 分支在相同初态下仅改变 action 应用过程就
改变了瞬态；nominal 模型变化极小，本来没有显著激活冲击。普通案例的
force peak 略增，说明这种诊断干预不能宣称普遍优化 interaction cost。
所有这些 200 ms 分支均未触发生产 guard abort。

最大案例的旧动力学+新估计/几何分支 qacc 峰值 0.554；新动力学+旧估计/几何
为 9.697，进一步支持动力学 action 应用为主导。两支同时改变了 estimate
与 allocation geometry；状态-only 贡献应以同态代数矩阵为依据。

初始 cuff strain/energy、contact、物理 q/dq 在所有克隆中一致，最大案例
spring energy 为 0.169117 J。命令先改变，经 robot torque→cuff strain/wrench
→Human physical response 传播；interface/contact 是真实传播机制。
RULED_OUT：不同初始 cuff preload 或独立接触事件不是这组分支差异的起点。
OPEN：接口/接触对后续振荡幅度的独立贡献，没有通过更换物理参数来辨识。

![最大案例 200 ms 匹配分支](../../../results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/summary_v1/largest_jump_analysis_0200ms.png)

最大案例 1.5 s matched follow-through：production 与 transfer 都完成该段，
true task-start 位置误差分别 `[−0.139,−0.280]°`、`[−0.105,−0.205]°`。
保留旧模型支在 0.810 s 因 session clearance 拒绝，不能把它当作更安全的
完整替代。所有不利结果保留。

进一步的 `full_recovery_v3/` 用原 DEV-A lifecycle 完整延续两支；两支都以
ACTIVE_RECOVERY_TIMEOUT 在 9.055 s 结束。production replay 与历史完整
恢复的 1810 个新模型命令、对应 true q/dq 和 qhat 逐区间精确一致。
计入一个激活前等待区间，共 1811 个物理控制区间。这些结果说明抑制首次
冲击并不足以修复该例恢复失败。

| 完整恢复量 | production replay | diagnostic transfer |
|---|---:|---:|
| force peak（5 ms 边界采样），N | 90.514975 | 87.060880 |
| moment peak，Nm | 7.416169 | 7.416169 |
| force integral，N·s | 494.331337 | 492.851649 |
| 最终 true q，rad | [0.039940,0.059295] | [0.039952,0.059318] |
| 终止 | ACTIVE_RECOVERY_TIMEOUT | ACTIVE_RECOVERY_TIMEOUT |

上述峰值采样频率不同于 200 ms substep 表，不能混成同一个 peak 指标。
两支各六次恢复规划，实际计算最大分别 2.500375/2.513750 ms；诊断固定重放
历史 5 ms 等待，物理不中断。没有本次 >100 ms 规划，但这不是新 runtime
qualification，也没有消除 DEV-A 历史四次超时。
OPEN：究竟哪个剩余的 contact-effective model / recovery-reference / execution
机制导致最终未满足 settle，还不能用本次干预唯一归因。

## 状态估计、模型准确性与接触限制

OBSERVED：最大案例，用 true q/dq 和 evaluation-only true cuff generalized
input 计算，old/new acceleration error 分别约
`[−25.091,−67.401]` / `[−0.189,−0.413]` rad/s²。
但这是 oracle-input 的局部一致性检查：actual qacc 同时包含 bed contact。

evaluation-only contact probe 把每个 MuJoCo contact 的 constraint 行经
`mj_mulJacTVec` 转为 generalized load；Auditor 另用 contact.frame.T 和
`mj_applyFT` 独立验证，结果精确吻合。最大案例 t=7.025 s：

- bed–thigh normal 33,353.295 N，penetration 4.819 mm；对 Human 为
  `[15.363881,0]` Nm；当时 cuff norm 仅 67.704611 N。
- cuff generalized input `[23.341926,−7.126927]` Nm。
- new inverse dynamics 在 true state/acceleration 为 `[23.523337,−7.144411]` Nm；
  相对 cuff-only residual `[0.181411,−0.017484]` Nm，而相对 cuff+contact 为
  `[−15.182471,−0.017484]` Nm。
- old 模型相对 cuff+contact 的 hip residual 为 +2.014427 Nm。
- 完整 `M qacc + bias − passive − applied − actuator − constraint` 闭合
  残差 ≤1.8e−15 Nm，Human actuator 项为零。

OBSERVED：最大案例所有 801 个 200 ms 物理边界均有 bed–thigh 接触；
ordinary 和 middle 在该窗口没有接触，仍出现 activation 瞬态。new model
在这两个无接触检查点的 true-state inverse-dynamics cuff-input residual
分别约 `[-0.05925,0.00015]`、`[-0.01080,-0.00003]` Nm。

因此，CAUSALLY_SUPPORTED 的范围是“模型应用导致命令/局部瞬态变化”；
OPEN 的范围包括 contact-conditioned residual 是否能在离开支撑后保持
控制充分性。不能把 contact-inclusive 拟合吻合说成自由 Human 动力学正确。
33 kN 模拟接触本身是重要 plant/setup 解释限制，本阶段没有改变床/接触参数，
也没有把它自动重新分类成历史 cuff-force failure。

## 检查、文件与未完成问题

当前所有生产 source/config/model 科学参数均未修改。新内容仅在 DEV-B
诊断脚本、测试、config、docs、results namespace。源依赖 hash 从各捕获
保存，checkpoint 内包含实际模型；仍有大量此前 untracked full-3D 依赖，
不声称 published HEAD 足以 clean-clone 复现。

16 个 DEV-B artifact/source-integrity 聚焦测试通过；`git diff --check` 通过。
独立审计 PASS，审计边界及未决解释见 `AUDIT_REPORT.md`、`STATUS.md`。详细命令见
`COMMANDS.md`，文件所有权见 `CHANGED_FILES.md`。早期 capture 字段名错误
和完整恢复匹配工具失败都保留，未覆盖物理/正式记录。

生产中的 100 ms fail-closed 语义、beta/residual 更新律及限幅、task MPC、
候选集、force/moment/ROM/加速度/clearance gates、plant、value=0 未改变。
没有 stage/commit/push/reset/stash/branch switch，没有新鲜资格、large-ROM
或学习实验。DEV-C 建议只针对已定位的首次应用不连续；后续超时和接触有效域
仍需在未来工作中保留其独立问题身份。
