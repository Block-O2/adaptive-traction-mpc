# Stage-4 康复轨迹自然激励与自适应泛化预注册

状态：**预注册文本已冻结；其后用户完成正式运行，结果见
`STAGE4_TRAJECTORY_EXCITATION_GENERALIZATION_REPORT.md`。**
下文中的未来时态保留预注册时点含义，不据结果回改研究合同。

本文件回答的问题是：在不加入校准动作、主动激励或额外识别轨迹的前提下，不同正常康复任务自身提供的自然激励，如何影响 11-base 积分回归的可辨识性、trust qualification/promotion 时序，以及 trusted adaptation 的控制收益？

本预注册冻结于查看任何新轨迹闭环结果之前。离线审计只使用精确参考运动学、名义 Human-V2 和 oracle 逆动力学；不得根据未来正式结果重做轨迹、修改阈值或增加探测动作。

## 1. 已恢复的研究合同

- 当前正式锚点实际由 `run_stage4_single_challenger_closed_loop_ab.py` 调用 `cold_start_teaching_reference`，即 23 s 分段 quintic 高屈曲任务；代码中另有 `continuous_teaching_reference`，但它不是该正式 runner 的锚点。
- 当前 11-base 参数顺序为 `[a,b,d,g1,g2,k1,k2,rho1,rho2,bv1,bv2]`。其中 `rho_i = k_i q_ri`；这些量是 control-effective base combinations，不是独立解剖参数真值。
- 积分识别器使用 0.50 s 滑动窗口、每 5 个高层测量样本形成一个新 block，并用现有 estimator box span 对参数方向缩放。识别不需要瞬时加速度输入。
- L4 trust 比较 challenger、population prior 与固定 incumbent 对未来 measured integral targets 的预测；oracle beta 和 clean prediction error只允许在 rollout 后追加。
- pacing 只依赖 retained geometry/dynamics validity。第一次 qualification 后，现有 0.75 s 低通与 hysteresis 约需 1.021 s 才进入高置信度，再以 0.25/s 从 0.5 恢复到 1.0，约需 2 s。后续 challenger rejection 不会使已保留模型失效。
- Stage-4 patient mismatch 正式结果显示 registered formal perturbed anchor 在现有锚点上于 9.72 s 第一次 promotion，并观察到 tracking RMSE 与 oracle torque-prediction RMSE 分别下降 6.85% 与 10.30%；该单轨迹结果不能推出跨轨迹泛化。
- nominal sensor decomposition/multiseed 说明 promotion 可能吸收 sensor bias、drift、preprocessing 与 reconstruction effects；因此本研究中的 beta 仍只能称为 measured-domain/control-effective model，不得称为物理患者参数识别。

## 2. 科学问题与边界

预注册的主因果链为：

```text
康复轨迹
  -> 自然激励与积分回归质量
  -> challenger qualification / control promotion 时序
  -> measured-domain 与 clean-oracle 模型预测质量
  -> tracking benefit、progress 与 completion
```

只研究正常任务自然产生的信息。不允许：

- active probing、dither、校准摆动或在正式任务前后追加 identification segment；
- 为使 estimator 通过 rank/condition/trust gate 而调整轨迹；
- 查看闭环结果后删除、替换或重定时不利轨迹；
- 更改 estimator bounds、trust/pacing、MPC、allocator 或 safety setting 来补偿弱激励；
- 将 no promotion、prior retained 或 incomplete progress 自动解释为 unsafe/incorrect。

允许且科学上有效的结论包括：**“该康复任务没有提供足够信息支持可靠的一次性患者自适应，因此 trust 保留 prior。”**

## 3. 预注册轨迹矩阵

机器可读定义为 `configs/stage4_trajectory_excitation_suite.json`。除 `two_cycle_moderate_23s` 外，所有变体都是对正式 23 s anchor 的预先声明式变换；缩放始终以初始姿态 `[5°,10°]` 为中心。所有轨迹均从该姿态开始并返回该姿态，且位于 Human-V2 ROM `[0°,80°] x [0°,100°]` 内。

| trajectory | 康复/物理含义 | q1/q2 范围 deg | ROM deg | 时长 s | peak dq deg/s | peak ddq deg/s2 | 预期主要激励 | 与 anchor 相同 |
|---|---|---:|---:|---:|---:|---:|---|---|
| `registered_high_flexion_23s` | 现有分阶段髋膝屈曲、高屈曲停留、分阶段返回 | 5–75 / 10–90 | 70 / 80 | 23.0 | 20.625 / 28.125 | 31.753 / 43.300 | 两关节惯性/耦合、重力、被动刚度/偏置及阻尼；正式锚点 | 全部参考与导数、waypoint、hold、初末姿态 |
| `moderate_rom_23s` | 同一辅助屈曲返回任务的中等 ROM 版本 | 5–47 / 10–58 | 42 / 48 | 23.0 | 12.375 / 16.875 | 19.052 / 25.980 | 保留两关节协调，但降低惯性、阻尼和大角度重力变化 | 时长、waypoint 时刻、相序、hold、初末姿态 |
| `slow_high_flexion_34p5s` | 相同高屈曲路径以 1.5 倍时长慢速完成 | 5–75 / 10–90 | 70 / 80 | 34.5 | 13.750 / 18.750 | 14.112 / 19.244 | 保留 ROM/重力几何变化，降低速度与加速度相关激励 | 完整 joint-space path、协调关系、相对相序与 hold 比例 |
| `hip_dominant_low_knee_23s` | 膝保持接近伸展但不达 q2=0 奇异姿态的辅助髋屈曲/类 straight-leg raise | 5–75 / 10–30 | 70 / 20 | 23.0 | 20.625 / 7.031 | 31.753 / 10.825 | 髋侧运动丰富；膝侧 `k2/rho2/bv2` 及 distal/coupling 分离较弱 | 完整髋参考、时长、相序、hold、初末姿态 |
| `knee_dominant_low_hip_23s` | 大腿相对稳定的孤立辅助膝屈伸 | 5–22.5 / 10–90 | 17.5 / 80 | 23.0 | 5.156 / 28.125 | 7.938 / 43.300 | 膝侧激励丰富；proximal `a/g1/k1/rho1/bv1` 分离较弱 | 完整膝参考、时长、相序、hold、初末姿态 |
| `two_cycle_moderate_23s` | 23 s 内完成两次普通中等幅度屈曲返回，而非一次分阶段高屈曲 | 5–50 / 10–60 | 45 / 50 | 23.0 | 16.875 / 18.750 | 10.392 / 11.547 | 两次正常重复提供速度换向，但重复同一协调曲线，可能增加样本量而不增加独立方向 | 总时长、1 s 初末 hold、初末姿态 |

这些数值由轨迹定义直接计算，不是按 estimator 结果调出的目标。`two_cycle_moderate_23s` 的峰值为 `[50°,60°]`，选择依据是普通中等幅度双重复任务语义，不是为了达到某个 singular-value 阈值。

## 4. 闭环前名义/oracle 激励审计

### 4.1 方法

离线审计采用与当前高层识别数据一致的 20 ms 网格。对每条精确参考计算 `(q,dq,ddq)`，用名义 Human-V2 的 exact 11-base regressor 生成 oracle torque，再按当前 0.50 s integral block 和 5-sample stride 构造累计矩阵 `Y`。

定义：

```text
S = diag(current identifier upper - lower)
X = Y S
Z = column_normalize(X)
I = X^T X
```

- `Z` 的 rank、奇异谱与 condition 对应当前识别器的列归一化 SVD gate 语义；rank tolerance 为 `sigma_max * 1e-10`。
- `X` 表示 estimator-span-normalized parameter perturbation 对积分目标的绝对敏感度，适合判断“实际信息强度”；其 condition 不等同于当前 gate 的 condition。
- `I` 是累计设计信息 proxy。窗口重叠，因此它不是 independent-sample Fisher information，也不能转换为已校准置信概率。
- 名义 oracle 的 `Y beta` 与数值积分 torque target 的最大误差为 `2.99e-4 Nms` 以下，仅反映 20 ms trapezoidal discretization。

完整的 11x11 `I`、列归一化 information matrix、全部 singular vectors、block end times 和弱方向保存在 `results/robustness/trajectory_excitation/design_audit.json`；以下表格是同一 artifact 的审阅摘要。

### 4.2 Rank、condition 与信息强度

| trajectory | blocks/rows | rank | cond(Z) | sigma_min(Z) | cond(X) | sigma_min(X) | tr(I) | lambda_min(I) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `registered_high_flexion_23s` | 226 / 452 | 11 | 349.05 | 5.227e-3 | 1.217e3 | 1.739e-1 | 5.587e4 | 3.026e-2 |
| `moderate_rom_23s` | 226 / 452 | 11 | 709.16 | 2.625e-3 | 2.518e3 | 9.342e-2 | 6.238e4 | 8.728e-3 |
| `slow_high_flexion_34p5s` | 341 / 682 | 11 | 344.65 | 5.292e-3 | 2.526e3 | 1.031e-1 | 8.437e4 | 1.063e-2 |
| `hip_dominant_low_knee_23s` | 226 / 452 | 11 | 108.64 | 1.682e-2 | 6.119e3 | 3.448e-2 | 5.133e4 | 1.189e-3 |
| `knee_dominant_low_hip_23s` | 226 / 452 | 11 | 880.62 | 2.114e-3 | 2.579e3 | 9.650e-2 | 7.026e4 | 9.312e-3 |
| `two_cycle_moderate_23s` | 226 / 452 | 11 | 1.964e4 | 9.533e-5 | 9.536e4 | 2.393e-3 | 6.008e4 | 5.727e-6 |

全部 `Z` 奇异值（从大到小）为：

- anchor: `[1.824551,1.472385,1.437818,1.000025,1.000001,0.868184,0.604280,0.456628,0.327107,0.035915,0.005227]`
- moderate ROM: `[1.861730,1.498314,1.458801,1.000003,1.000000,0.805136,0.481060,0.416901,0.327381,0.015997,0.002625]`
- slow high-flexion: `[1.823801,1.473250,1.437160,1.000011,1.000001,0.865735,0.607714,0.458112,0.328344,0.036262,0.005292]`
- hip-dominant/low-knee: `[1.826795,1.468775,1.387668,1.056562,1.000000,0.999992,0.606381,0.300968,0.062228,0.033999,0.016815]`
- knee-dominant/low-hip: `[1.861854,1.476401,1.442858,1.001156,1.000000,0.748656,0.569817,0.504930,0.358047,0.035409,0.002114]`
- two-cycle moderate: `[1.872190,1.647128,1.460558,1.000056,1.000000,0.727773,0.267095,0.216273,0.024487,0.013010,0.0000953]`

`I` 的 diagonal 按 `[a,b,d,g1,g2,k1,k2,rho1,rho2,bv1,bv2]` 排列：

- anchor: `[4.484,0.153,0.278,39427.874,6349.507,3028.187,4352.401,1075.680,1548.980,32.572,45.373]`
- moderate ROM: `[1.614,0.055,0.132,50114.117,6429.985,1240.689,1938.741,1075.680,1548.980,11.726,16.334]`
- slow high-flexion: `[1.432,0.049,0.089,59696.037,9581.702,4544.965,6533.338,1623.040,2337.177,22.150,30.919]`
- hip-dominant/low-knee: `[4.484,0.053,0.858,39427.874,5574.910,3028.187,637.852,1075.680,1548.980,32.572,2.836]`
- knee-dominant/low-hip: `[0.280,0.216,0.089,58326.038,4581.324,325.697,4352.401,1075.680,1548.980,2.036,45.373]`
- two-cycle moderate: `[1.549,0.036,0.108,46728.168,6426.160,1668.089,2533.744,1075.680,1548.980,41.835,51.649]`

### 4.3 预先观察到的弱方向

下表给出 `X` 最小 singular vector 的主要载荷。符号只表示组合方向，不表示参数偏差的物理正负。

| trajectory | sigma_min(X) | 最弱 span-normalized combination | 解释 |
|---|---:|---|---|
| anchor | 0.1739 | `+0.890 b +0.301 rho1 -0.239 rho2 +0.165 g2` | 即使大 ROM 满秩，distal inertia 与常值 passive/gravity 积分项仍可互相补偿；第二、第三弱方向也主要是 `rho1/rho2` 与 `b/d/g2`。 |
| moderate ROM | 0.0934 | `-0.771 b -0.448 rho1 +0.358 rho2 -0.246 g2` | 较小角度变化使 `cos(q)`、`q` 与常值 offset 更接近相关，同时速度/加速度幅值下降。 |
| slow high-flexion | 0.1031 | `-0.966 b -0.173 a +0.155 d -0.084 rho1` | 相同路径保证列形状条件与 anchor 接近，但 acceleration boundary terms 和 damping terms 变小；更长时长增加重力/被动积分量，却没有同等增加惯性信息。 |
| hip-dominant/low-knee | 0.0345 | `-0.895 b +0.404 d -0.187 a` | q2 只变化 20°，distal/coupling inertia 难分；`k2` information diagonal 降至 anchor 的约 15%，`bv2` 降至约 6%。第三弱方向还混合 `rho2/g2/k2/bv2`。 |
| knee-dominant/low-hip | 0.0965 | `-0.984 rho1 -0.133 g1 -0.071 k1 +0.066 d` | q1 仅变化 17.5°；`k1` 与 `bv1` information diagonal 分别降至 anchor 的约 11% 与 6%，proximal gravity/stiffness/rest-offset 难分。后续弱方向仍由 `a/b/d` 组合主导。 |
| two-cycle moderate | 0.00239 | `+0.862 b +0.344 rho1 -0.287 rho2 +0.198 g2` | 两次重复增加观测行和 damping 能量，却主要重复同一协调曲线；独立方向几乎不增加。第二弱值仅 0.00868，主要仍为 `rho1/rho2/b/g2`。 |

关键解释：

1. **rank 11 不等于 practical identifiability。** `two_cycle_moderate_23s` 在当前 tolerance 下满秩，但 condition 比 anchor 差约两个数量级，最小信息特征值约小四个数量级。
2. **trace(I) 不能单独代表信息丰富。** slow 与 two-cycle 的 trace 大于或接近 anchor，分别来自更长累计时间或重复行；它们的最弱方向反而更差。
3. **列归一化 condition 也不能单独代表绝对灵敏度。** hip-dominant 的 `cond(Z)` 最小，但 `cond(X)` 与 `lambda_min(I)` 显示其低膝激励下绝对弱方向明显；列归一化掩盖了低能量列。
4. 这些弱方向是 11-base control-effective combinations。不得把它们解释为独立 mass、COM、inertia、rest angle 的解剖可辨识性。

## 5. 未来正式 paired A/B 合同

### 5.1 唯一跨 trajectory 变量

每个 trajectory case 使用其预注册参考函数与时长。除此之外，所有 case 使用同一患者、同一随机流、同一 controller/trust/safety 实现。`slow_high_flexion_34p5s` 的较长 duration 是该轨迹定义的一部分，不是闭环结果后的补偿。

观察窗统一采用预先声明的规则：

```text
wall_time_limit_s = reference_duration_s + 9.0 s
```

因此 23 s case 为 32.0 s，34.5 s case 为 43.5 s。固定 9 s wall-time allowance 避免把“轨迹更慢”机械地变成“观察窗早于 reference nominal duration 结束”；completion/progress 仍是有效结果，no-promotion case 仍可能因 confidence pacing 未完成。

### 5.2 固定患者与随机条件

- true Human：`registered_formal_perturbed_anchor`，即 `height_scale=1.06`、`body_mass_scale=1.08`、thigh/shank COM scale `[1.04,0.96]`、passive stiffness scale `[1.15,1.15]`、rest offset `[-2°, +3°]`、sleeve-center scale `0.94`；使用现有 geometry estimator。
- sensor regime：`noise_bias_drift_200hz`。
- measurement seed：`44104`，所有 trajectory 与两 arm 均复用相同时间索引的随机流（common random numbers）。
- MPC seed：`20260824`。

选择该患者和 seed 的理由是它们构成现有正式锚点，可在 `registered_high_flexion_23s` 上提供直接 replication link。初始实验只支持该固定 mismatch 与该固定 nuisance realization，不是 promotion probability 或 patient-population 结论。

### 5.3 两个 arm

- `prior_only`：完整运行相同 causal trust lifecycle；challenger 可 qualification，但 qualified beta 永不进入控制，控制模型始终为 population prior。
- `trusted_adaptive`：只有通过同一 causal L4 qualification 的 challenger 才能成为 control incumbent；promotion 前必须与 `prior_only` 完全一致。

每个 trajectory 单独形成一个严格 paired case。不得将一条轨迹的 estimate、trust state、pacing state 或 noise history warm-start 到另一条轨迹。

### 5.4 冻结项

以下项目跨全部 trajectory 和 A/B arm 冻结：

- initial Human/robot state；Human case 与 geometry mismatch；
- sensor model、sample rate、seed/RNG semantics、preprocessing、measurement routing；
- feasible-first CEM：batched implementation、horizon 15、32 candidates、2 iterations、6 elites、原 tracking/action/action-slew objective、interaction weights 为 0；
- 11-base accumulated integral estimator、0.50 s window、5-measurement stride、physical bounds、regularization、smoothing 与 update limits；
- L1/L2/L3 semantics；single-incumbent/at-most-one-challenger L4；0.5 s embargo；不重叠 0.5 s validation blocks；8/12/16 looks；lag-2 HAC；现有 anytime alpha allocation；
- confidence pacing 的 0.5 初始速度、low-pass、hysteresis、0.25/s recovery；
- 1:1 cuff-aware allocator、cylindrical surface proxy definition；
- control gains、force gate、moment limit、ROM、robot torque/velocity constraints、solver/warning handling、plant integration；
- controller implementation 与代码版本；
- no active excitation、no UKF/Kalman、no hybrid optimizer、no tracking tube/corridor、no new trust threshold/bound/retuning。

正式执行前只允许把已验证的 declarative `trajectory_reference(case, t)` 接入现有 paired runner，并做短 structural smoke 验证 reference injection、schema 与 A/B isolation。该机械接线不得改变上述科学合同。

## 6. 预注册问题、指标与分析

### 6.1 主要问题

1. richer natural excitation 是否对应更早、更稳定的 first qualification/promotion？
2. 即使 structural rank=11，poor conditioning 是否仍降低 useful adaptation？
3. 较好的 precomputed regressor quality 是否与较好的 measured prediction、clean-oracle prediction 和 tracking benefit 同向？
4. 是否存在正常康复轨迹，使一次性 adaptation 所获信息不足，最终 no promotion 或 promotion 太晚而没有可用任务余量？

这些是方向性问题，不预注册人为二分阈值，也不要求 adaptive 在每条轨迹获胜。

### 6.2 轨迹/激励指标

- 预先固定的 `rank(Z)`、完整 `sigma(Z)` 与 `cond(Z)`；
- `sigma(X)`、`cond(X)`、`I=X^T X`、`lambda_min(I)`、`trace(I)` 与 information diagonal；
- 最弱三个 span-normalized right-singular directions 及 parameter-group energy；
- ROM、duration、peak joint velocity/acceleration。

正式闭环不得替换上述 design matrix；可另行记录 realized clean-state regressor diagnostics，但必须标为 realized/descriptive，不能用于重定义轨迹或主要 excitation exposure。

### 6.3 Trust 与 estimator 指标

- first candidate fit time、first qualification time、first control-promotion wall time与reference phase；
- promotions、rejections、pending counts、每个 challenger 的 decision reason 与 validation look；
- active-bound count、具体 active/pressured parameter、maximum unconstrained violation in estimator spans；
- first promotion 后剩余 reference 秒数与比例；若无 promotion，明确记为 `none`，不得填 0 混淆；
- qualification 后 high-confidence time、nominal-speed recovery time、time at minimum/nominal speed。

### 6.4 Prediction、tracking、progress 与 safety

- measured integral-target training/held-out loss，严格保持 causal；
- rollout 后追加的 control-model generalized-torque RMSE：full-task 与 post-first-promotion；
- tracking combined RMSE 与 maximum absolute error：full-task 与 post-first-promotion；
- final reference phase、progress fraction、reference completion/time、termination reason；
- force gate、ROM、unintended contact、torque saturation、joint limit、MPC/solver failure、nonfinite state/wrench、MuJoCo warning 等全部 safety events。

### 6.5 描述性 interaction metrics

只记录 cuff translational force peak/RMS、cuff moment peak/RMS、cylindrical surface proxy peak/RMS。它们不是成功标准；surface proxy 不是 pressure、comfort 或 tissue loading。

### 6.6 配对差异与跨轨迹关联

- 对每条轨迹报告 `trusted_adaptive - prior_only` 及分母有定义时的百分比变化；保留原始连续值。
- 无 promotion 时，两 arm 理应保持一致；该 case 主要检验 trust retention，不计算虚假的 post-promotion benefit。
- 以 6 条预注册轨迹为单位，描述 excitation metrics 与 first promotion time、remaining fraction、prediction benefit、tracking benefit 的 Pearson/Spearman 关联；`n=6` 只作描述，不作总体概率或因果 dose-response 声明。
- prediction benefit 与 tracking benefit 的关联同样只作描述。较好 identification quality 不保证较好 tracking，sensor compensation 也可能使 measured prediction 与 clean-oracle prediction方向不同。

## 7. 机械公平性与有效性判据

每个 pair 必须满足：

1. 相同 trajectory definition/hash、患者、初态、wall limit rule、measurement seed/sample realization、MPC seed/candidate populations 与 shared config；
2. first adaptive control application 前，time grid、reference phase、speed scale、God-view Human state、measured channels、estimated state、desired generalized action、allocated wrench、geometry/base estimate 与 control beta 满足现有 `atol=1e-10, rtol=0` isolation contract；
3. `prior_only` control beta 全程等于 population prior，且 control promotions 为 0；
4. challenger training 在 embargo 与 non-overlap validation 之前；oracle diagnostics 不进入 estimation、trust、pacing、MPC、termination 或 case selection；
5. 所有失败、no-promotion、late-promotion、incomplete、poor/adverse result 原样保存到新目录；不得覆盖或静默 rerun；
6. 任一 isolation assertion 失败只构成 mechanical invalid pair，不授权改科学参数后重跑。

## 8. 预注册解释词汇

- **naturally informative task**：离线设计 matrix 较好且闭环 qualification/promotion 留下可用任务余量；只描述当前 suite 相对关系，不制定临床阈值。
- **full-rank but practically weak**：rank=11，但 smallest singular values、`lambda_min(I)` 或 condition 显示某些方向对噪声/重构误差高度敏感。`two_cycle_moderate_23s` 已在闭环前属于这一类。
- **trust-retained prior**：没有候选获得足够未来 measured evidence，prior 被保留。这是有效保护结果，不是 controller failure。
- **late but valid adaptation**：qualification/promotion 合法但剩余 trajectory 太少，无法观察或产生有意义控制收益。
- **useful adaptation**：promotion 后 prediction 和/或 tracking 改善，且不新增 safety event、不降低 completion/progress；冲突指标仍报告为 mixed。
- **mixed/adverse adaptation**：promotion 后某个主要指标变差或 progress/safety 变差；不得用 composite score 隐藏。
- **controller/safety event**：单独按事件机制报告。它不能仅由 weak excitation、no promotion 或 prior retention 推断。

## 9. 执行门与停止规则

当前输出只授权：配置解析、轨迹 structural validation、exact nominal/oracle excitation audit、单元测试和短机械 smoke。**不授权正式 paired suite。**

轨迹套件在科学设计层面已经就绪：对照小而结构化，变量可解释，anchor 可复现，full-rank 与 poor-conditioning 已明确区分，且没有主动激励或事后调参。正式执行前仍需单独批准把 trajectory callable 接入 paired runner，并通过不产生科学结论的短 smoke；此后必须由用户运行正式命令。

一旦正式执行获批，停止规则是完成 6 个预注册 trajectory x 2 arm 的单患者、单 seed suite 及预注册汇总；不追加轨迹、seed、patient、ablation、retraining 或 threshold tuning。任何扩展都需要新的预注册。
