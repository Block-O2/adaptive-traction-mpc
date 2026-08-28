# Stage-4 患者 × 轨迹 × 测量实现交叉复现预注册

状态：**预注册文本已冻结；其后用户完成正式运行，收尾审阅见
`results/stage4_crossed_excitation_replication_summary_final/research_report.md`。**
下文中的未来时态保留预注册时点含义，不据结果回改研究合同。

本研究只在现有 Human-V2 仿真与冻结 Stage-4 控制合同内检验：实用激励质量、trust qualification/promotion 时序、模型预测和 tracking benefit 之间已观察到的关系，是否能跨患者 mismatch 与 measurement realization 保持。它不是临床、患者总体、舒适度或安全有效性研究。

机器可读合同为 `configs/stage4_crossed_excitation_replication.json`。本文件与该 JSON 一起冻结；后续结果不得用于改变矩阵、轨迹、患者、种子、阈值或解释门槛。

## 1. 研究边界与冻结合同

每个 paired case 只有两个 arm：

- `prior_only`：完整运行相同的 estimator/trust/pacing，但患者特异 beta 永不进入控制；
- `trusted_adaptive`：beta 只有在合法 causal promotion 后才能进入控制。

除预注册的 patient、trajectory 和 measurement seed 三个因素外，以下内容全部冻结：

- `noise_bias_drift_200hz` 的 sensor magnitude、200 Hz 采样、preprocessing 与 measurement routing；
- MPC seed `20260824`、feasible-first batched CEM、horizon 15、32 candidates、2 iterations、6 elites、原 cost/constraints，interaction weights 仍为 0；
- accumulated integral 11-base estimator、现有 bounds、regularization、smoothing 与 update limits；
- L1/L2/L3 与 single-incumbent/at-most-one-challenger L4，现有 embargo、validation blocks、looks、HAC 与 alpha spending；
- confidence pacing、1:1 cuff-aware allocator、initial state、plant integration 与全部 safety/termination 设置；
- 所有患者定义、轨迹定义与 runtime 规则；每个 arm、每个 case 都从全新 estimator/trust/pacing/MPC/RNG 状态启动。

禁止 active excitation、额外 calibration motion、弱轨迹 retuning、新 trust/pacing 逻辑、事后 success threshold、静默重跑或覆盖输出。坏结果、no promotion、late promotion、incomplete progress 与 safety event 都是应保留的证据。

## 2. 因素水平及选择理由

### 2.1 患者 mismatch

三个患者均原样取自 `configs/stage4_patient_mismatch_cases.json`。这里的“强度”是现有 estimator span 内的工程距离，不是临床严重度，也不是单一机制的有序剂量。

| level | patient id | span L2 | 物理含义与选择理由 |
|---|---|---:|---|
| mild/small | `registered_stage2_mild_anchor` | 0.152789 | +5% mass 与两个 passive equilibrium 各 -2°；无 geometry mismatch。提供小型 mixed mismatch。 |
| mixed/moderate | `registered_moderate_anchor` | 0.188129 | mass、COM、stiffness、equilibrium 与小 cuff-geometry mismatch 的现有组合。提供中等 mixed/geometry case。 |
| stronger composite | `registered_formal_perturbed_anchor` | 0.460384 | 现有正式 height/mass/COM/stiffness/equilibrium/cuff-geometry anchor；三者中 span distance 最大，并直接连接已完成轨迹研究。 |

选择 mixed anchors 而非新造单参数病例，是为了复用已冻结、已验证、能由当前 11-base 加 geometry estimator 表示的 Human 配置。患者水平不是严格嵌套，因此不得把跨患者差异解释为单一 mismatch magnitude 的因果剂量效应。

### 2.2 康复轨迹与离线激励

三个轨迹原样取自 `configs/stage4_trajectory_excitation_suite.json`，均为 23 s，wall-time 均为 `23 + 9 = 32 s`。

| level | trajectory id | rank(Z) | cond(X) / cond(Z) | sigma_min(X) | lambda_min(I) | 选择理由 |
|---|---|---:|---:|---:|---:|---|
| anchor/high information | `registered_high_flexion_23s` | 11 | 1.22e3 / 349 | 0.174 | 3.03e-2 | 现有高屈曲正式 anchor；两关节 ROM 与动力学效应相对丰富。 |
| joint-biased/weak absolute information | `hip_dominant_low_knee_23s` | 11 | 6.12e3 / 109 | 0.0345 | 1.19e-3 | 髋运动丰富、膝变化小；normalized condition 看似好，但绝对最弱方向明显变弱，检验 joint-specific excitation。 |
| full-rank/practically poor | `two_cycle_moderate_23s` | 11 | 9.54e4 / 1.96e4 | 0.00239 | 5.73e-6 | 两次正常中等屈曲重复同一协调曲线；结构满秩但 practical conditioning 极差，是原预注册 poor-conditioning case。 |

完整 singular spectra、`I=X^T X`、information diagonal 与最弱三个 span-normalized directions 固定引用 `results/stage4_trajectory_excitation_design_audit/audit.json`，不得用未来 realized outcomes 替换。主要弱方向为：

- anchor：distal inertia `b` 与 `rho1/rho2/g2` 的组合；
- hip-dominant：`a/b/d` distal inertia/coupling 分离最弱，低膝变化同时削弱 knee rest/stiffness/damping 信息；
- two-cycle：`b/rho1/rho2/g2` 组合极弱，重复协调曲线增加累计行数却很少增加独立方向。

不选择 `knee_dominant_low_hip_23s`，因为前一正式研究中该 case 在 challenger 形成前由两 arm 共同触发 force gate，难以回答本研究的 excitation → trust → benefit 交互问题；这不是对轨迹定义的修改，也不否定该负结果。

### 2.3 Measurement realization

固定 seeds 为 `44104, 54113, 64122`。`44104` 是原正式 anchor；后两项是此前五种子预注册序列中的第 2、3 项。选择规则是“取冻结序列前三项”，不是按已有 promotion 结果挑选高低或有利 realization。Sensor magnitude 与 MPC seed 不变。

## 3. 精确平衡不完全交叉矩阵

完整 Cartesian product 需要 27 个 paired case。本研究预注册其中 18 个；对任意两个因素的每个组合，第三因素恰有两个水平。`R` 表示只读复用已有、哈希冻结的正式 bridge evidence，不重新执行。

| patient | anchor/high-flexion | hip-dominant/low-knee | two-cycle moderate |
|---|---|---|---|
| `registered_stage2_mild_anchor` | 54113, 64122 | 64122, 44104 | 44104, 54113 |
| `registered_moderate_anchor` | 64122, 44104 | 44104, 54113 | 54113, 64122 |
| `registered_formal_perturbed_anchor` | 44104 **R**, 54113 | 54113, 64122 | 64122, 44104 **R** |

构造规则为：给 patient、trajectory、seed 各编号 0/1/2，保留 `seed_index = (patient_index + trajectory_index + offset) mod 3`，其中 `offset ∈ {1,2}`。因此：

- 每个 patient、trajectory、seed 各出现 6 次；
- 每个 patient × trajectory cell 有两个 seeds；
- 每个 patient × seed cell 有两个 trajectories；
- 每个 trajectory × seed cell 有两个 patients。

分析矩阵为 18 paired cases / 36 arms；其中 2 pairs / 4 arms 是已有只读 bridge，未来新增执行为 **16 paired cases / 32 arms**。bridge 仅在全部文件 SHA-256 与 JSON 中登记值一致时纳入；不一致属于 mechanical integrity failure，不授权覆盖或重跑。

## 4. 预注册假设

1. **激励与时序：** practical excitation 较差通常对应更晚 qualification/promotion，或更高的 no-promotion 发生；同时报告 wall time、reference phase 与 normalized phase。
2. **mismatch 与 benefit：** 更强 patient mismatch 不保证更大 adaptive benefit；患者差异必须在同 trajectory、同 seed 下比较。
3. **prediction 与 tracking：** paired torque-prediction improvement 通常与 paired tracking-RMSE improvement 同向，但不要求每个 case 同号，也不把 max-error 冲突隐藏进 composite score。
4. **seed 稳健性：** measurement seed 可改变 promotion time/status，但不应系统性反转 anchor 相对 poor-conditioning trajectory 的主要 excitation pattern。任何反转原样报告。
5. **可用适应时间：** poor excitation 可能减少 first promotion 后剩余 reference time/fraction，而不一定完全阻止 promotion。

这些是方向性工程假设，不预注册二分 success threshold、p-value 门槛或“多数即成功”的事后规则。样本量只支持完整 case 表、matched contrasts 与描述性关联，不支持患者总体或 measurement-seed 概率估计。

## 5. 指标与时间归一化

每个 case/arm 保留原始连续值；paired benefit 正数定义为 adaptive error 更低。

- **offline excitation：** frozen rank、`sigma(X/Z)`、`cond(X/Z)`、完整 information matrix、`lambda_min(I)`、trace、diagonal、最弱参数方向/group energy；
- **trust/estimator：** first fit、first qualification、first promotion；promotion/rejection/pending counts；active-bound count、参数与最大 unconstrained estimator-span violation；
- **normalized timing：** `qualification_reference_phase / duration`、`promotion_reference_phase / duration`、first promotion 后 remaining reference seconds/fraction；no promotion 记 `null`，不填 0；
- **prediction：** measured-domain held-out loss 与 rollout 后 clean-oracle generalized-torque RMSE，full-task 及 post-first-promotion；
- **tracking：** combined RMSE 与 maximum absolute joint error，full-task 及 post-first-promotion；
- **task：** final reference phase、progress fraction、completion/time、termination reason；
- **safety：** force gate、moment、ROM、unintended contact、robot torque/velocity/joint limit、MPC/solver、nonfinite 与 MuJoCo warning 全部事件；
- **descriptive interaction only：** cuff force/moment peak/RMS 与 cylindrical surface proxy peak/RMS。surface proxy 不是 pressure、comfort 或 tissue load。

尽管三个轨迹本研究中均为 23 s，仍强制报告 wall-time 与 normalized reference-phase timing，以保持未来不同 duration 证据的可比合同。

## 6. 交互比较与隔离逻辑

### Trajectory excitation effect：固定 patient + seed

每个患者都有一组同 seed 的三种轨迹两两比较：

| patient | anchor vs hip | anchor vs two-cycle | hip vs two-cycle |
|---|---:|---:|---:|
| mild | 64122 | 54113 | 44104 |
| moderate | 44104 | 64122 | 54113 |
| stronger | 54113 | 44104 | 64122 |

这 9 个 matched contrasts 隔离 trajectory，直接检验 excitation → trust timing → remaining phase → prediction/tracking benefit。重点比较 anchor 与 two-cycle；hip-dominant 用于区分“joint-specific low excitation”与“重复协调造成的极差 conditioning”。

### Patient mismatch effect：固定 trajectory + seed

对每条 trajectory，mild–moderate、mild–stronger、moderate–stronger 各有一个共同 seed，形成 9 个 matched patient contrasts。它们检验同一自然激励与 measurement realization 下，mismatch case 如何改变 promotion 与 benefit；由于患者是 composite cases，不把差异归因于单一物理参数。

### Measurement realization effect：固定 patient + trajectory

九个 patient × trajectory cells 各有两个 seeds，形成 9 个 seed contrasts。它们检验 promotion status/time、bound pressure 与 benefit 对 realization 的敏感性。三个 seeds 只给描述性复现，不估计总体 promotion probability。

所有 contrasts 共享 case，但不是 27 个独立统计样本。报告每个 matched contrast、方向一致性、casewise Pearson/Spearman（仅描述）与完整负结果；不拟合不可识别的 unrestricted three-way interaction model。三因素 interaction 的结论限定为：主 excitation pattern 是否在不同 patient/seed matched slices 中保持、削弱或反转。

## 7. 完整性与 A/B 有效性

正式接线后，每个新 pair 必须满足：

1. patient/trajectory/seed 与 JSON 完全匹配，runtime 为 32 s，输出目录不存在且禁止 overwrite；
2. A/B 共享 patient、trajectory callable、measurement stream、MPC stream、controller configuration 与 initial state；
3. first adaptive control application 前满足现有 `atol=1e-10, rtol=0` isolation；
4. `prior_only` control beta 始终等于 population prior；`trusted_adaptive` 只在有效 promotion 后应用 beta；
5. case 之间无 estimator/trust/pacing/RNG warm start；oracle diagnostics 不进入 online decision；
6. bridge artifacts 的 path、provenance 与全部登记 SHA-256 完全一致；
7. finite trace、完整 provenance、patient/trajectory config hashes、controller fingerprint、两个 seeds 与 evidence category 均保存。

机械失败使该 pair 无效；科学上的 no promotion、poor tracking、incompletion 或 safety event 不使 pair 无效，也不授权 retuning。

## 8. 计算成本与停止规则

三个轨迹均请求 32 s wall-time。现有相同 runner 在这三条轨迹上的实测 rollout wall time 约 33.9–34.9 s/arm。因此：

- 分析矩阵等效模拟时长：36 arms × 32 s = 1152 s（19.2 simulated minutes）；
- 新执行：32 arms × 32 s = 1024 s（17.1 simulated minutes）；
- 按约 34.3 s/arm 估算，新 rollouts 串行约 18.3 min；计入 16 次进程启动、完整性检查与汇总，预计约 **20–25 min**。

未来只需手工执行 16 个 paired cases，均为统一 32 s runtime；相较 27-pair full Cartesian product 少 11 个新 pair，并复用两个完全相同的已完成 bridge。该规模足以手工运行，且没有重复原 deterministic anchor 的必要。

当前停止点：**只完成设计和 declarative preregistration。** 下一步需要单独授权把三因素选择接入现有 paired runner，并仅做 structural smoke。正式复现必须再获授权且由用户手动执行；完成预注册 16 个新 pairs 后停止，不追加患者、轨迹、seed、ablation 或调参。
