# Phase 3A measured-twist estimator 时域/频域离线审计

证据类别：**offline deterministic measurement replay**。只读取冻结 Rigid mechanics evidence，在200 Hz重放注册 `CausalMeasurementLayer`；新 trajectory runs：**0**，scientific settings changed：**false**。

## Estimator contract

| 项 | 注册语义 |
|---|---|
| 输入 | MuJoCo robot `adapter_cuff_site` WORLD pose，reference point为 cuff center |
| Sampling | 200 Hz，0 ms configured latency |
| Pose filter | 一阶指数 low-pass，cutoff 8 Hz，`alpha=0.222232` |
| Derivative | 最近120 ms、25个已低通 pose样本的因果二次最小二乘；输出当前端点的一阶系数 |
| 输出 | WORLD linear/angular measured twist |
| 当前使用者 | estimator channel、MPC state channel、low-level executable-command channel分别实例化同一 measurement case |
| Servo映射 | `Fv=140*(v_target_raw-v_measured_processed)` |

## Full-trajectory error（排除0-120 ms初始化段）

| case | duration | component RMS [x,y,z] m/s | vector RMS | vector peak | equivalent-force RMS N | force peak N | speed RMS ratio | speed peak ratio |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 40/80 | 20.865 | [+0.031, +0.004, +0.106] | 0.110 | 0.676 | 15.4 | 94.7 | 1.296 | 1.280 |
| 120/120 | 10.410 | [+0.043, +0.004, +0.127] | 0.134 | 1.345 | 18.8 | 188.3 | 1.021 | 1.036 |
| 90/120 | 29.255 | [+0.019, +0.004, +0.088] | 0.090 | 0.556 | 12.6 | 77.8 | 1.192 | 1.264 |

Full-trajectory including warmup、angular error和noise-free filter-only分解保存在 `summary.json`。`speed ratio` 大于1代表 estimated speed整体放大，不能单独解释为固定gain。

## Critical events

`estimator force error = 140*(truth-estimate)`；单元为 `norm / projection on saved final executable-force direction`。

| case | t | saved status | truth v | estimated v | estimator force-error vector | estimator norm/proj | genuine tracking norm/proj |
|---|---:|---|---|---|---|---:|---:|
| 40/80 | 11.935 | FILTER_INFEASIBLE | [+0.054, +0.000, -0.109] | [-0.125, +0.000, -0.577] | [+25.07, +0.02, +65.51] | 70.14 / +50.96 | 15.01 / +14.76 |
| 120/120 | 10.410 | FILTER_INFEASIBLE | [+0.148, +0.001, -0.599] | [+0.134, -0.001, -0.909] | [+1.96, +0.19, +43.45] | 43.50 / +29.84 | 94.36 / +86.36 |
| 90/120 | 22.185 | SAFE_UNCHANGED | [+0.121, +0.000, +0.003] | [+0.141, +0.002, -0.509] | [-2.89, -0.25, +71.73] | 71.79 / +56.61 | 9.97 / -0.78 |

## Cross-correlation delay

单元为 `best lag ms / correlation`。正lag表示 estimator滞后于truth；全轨迹结果仅是非平稳信号的最优对齐，不是固定transport delay。

| case | full x | full z | full speed | event-window x lag | event-window z lag |
|---|---:|---:|---:|---:|---:|
| 40/80 | 40.0 / 0.984 | 40.0 / 0.998 | 40.0 / 0.996 | 40.0 | 40.0 |
| 120/120 | 40.0 / 0.992 | 40.0 / 0.997 | 40.0 / 0.995 | 40.0 | 40.0 |
| 90/120 | 40.0 / 0.993 | 40.0 / 0.993 | 40.0 / 0.989 | 40.0 | 40.0 |

## Acceleration / deceleration / curvature

按每条轨迹自身、post-warmup moving samples定义：speed >0.05 m/s；speed-rate顶部/底部10%分别为acceleration/deceleration；velocity-direction turn-rate顶部10%为high curvature。表中为 equivalent estimator-force error RMS（N）。

| case | acceleration | deceleration | high curvature |
|---|---:|---:|---:|
| 40/80 | 73.5 | 37.7 | 58.4 |
| 120/120 | 73.1 | 31.6 | 48.9 |
| 90/120 | 48.6 | 26.4 | 38.1 |

## Error peak、sign reversal 与 extrema

Sign reversal要求truth在前后50 ms内均达到至少0.02 m/s，并匹配同方向estimated crossing；extrema要求truth component绝对值至少0.05 m/s，并在`-20/+100 ms`内匹配同类estimated extremum。它们是描述性事件检测，不是新的gate。

| case | error peak time s | peak relative to audit event ms | reversal median delay x/z ms | extrema x delay/amp ratio | extrema z delay/amp ratio |
|---|---:|---:|---:|---:|---:|
| 40/80 | 11.870 | -65.0 | 40.0 / 40.0 | 40.0 / 1.212 | 40.0 / 1.295 |
| 120/120 | 10.365 | -45.0 | 40.0 / 40.0 | 35.0 / 1.042 | 30.0 / 1.039 |
| 90/120 | 22.010 | -175.0 | 40.0 / 40.0 | 15.0 / 1.013 | 40.0 / 1.225 |

## Exact discrete sinusoidal-equivalent response

对平移pose小信号，把一阶low-pass与25点quadratic derivative的精确离散权重串联，再除以理想`j*omega` velocity。该response随频率变化：

| frequency Hz | magnitude estimated/true | phase deg | equivalent delay ms |
|---:|---:|---:|---:|
| 0.50 | 1.012 | -3.3 | 18.1 |
| 1.00 | 1.045 | -7.1 | 19.8 |
| 2.01 | 1.150 | -18.1 | 25.0 |
| 4.00 | 1.325 | -51.0 | 35.5 |
| 7.97 | 1.021 | -132.6 | 46.2 |

8 Hz以上接近衰减零点且phase unwrap敏感，因此不报告单一高频delay。该表不包含plant、servo或measurement noise。

## Architecture provenance

- 8 Hz / 120 ms路径与`measurement.py`、`sensor_realism.py`一起在commit `dfe395b`（`finalize simulation research repository`）引入。
- 对应预注册Spec的科学问题是sensor noise/bias/drift如何影响state reconstruction、integral identification和trust promotion，且明确把noise与preprocessing合并为一个不可拆分regime。
- 实现同时创建`estimator_layer`、`mpc_layer`和`low_level_layer`；同一processed twist既进入Human state/identification，也直接进入robot executable-command damping feedback。
- 未找到针对当前High-ROM、140 mm adapter和140 Ns/m servo的独立bandwidth、phase-margin或interaction-force qualification。因此它**实现上服务两条路径，原始科学动机主要是sensor realism与estimation/trust研究**。

## DIRECTLY VERIFIED

- 三条轨迹在200 Hz全程重放；实际noise+preprocessing输出与noise-free preprocessing分别保存。所有事件与上一轮保存velocity-feedback重构闭合。
- 40/80事件的 estimator-force error为 70.14 N，真实瞬时tracking项为 15.01 N。
- 120/120相应两项为 43.50 N和 94.36 N。
- 90/120相应两项为 71.79 N和 9.97 N。
- 离散filter在1/2/4/8 Hz的magnitude与phase不是单位幅值、零相位；它不能等价为纯delay或理想velocity measurement。
- 三条轨迹的x/z cross-correlation、sign reversal和prominent extrema均显示约40 ms的描述性延迟；估计极值幅值通常不被简单衰减，而可被放大。

## SUPPORTED BY CURRENT EVIDENCE

- 当前estimator未被证明适合作为high-bandwidth Cartesian damping feedback。其1-4 Hz存在幅值放大和约20-35 ms sinusoidal-equivalent lag，8 Hz附近phase lag已超过130 deg；实际闭环适用性仍取决于未提供的servo crossover与stability margin。
- 40/80边界处 estimator-history error明显大于真实瞬时tracking error，并沿最终force方向叠加，因此它对200 N crossing有实质贡献。
- 120/120中真实tracking lag是较大项，estimator error仍是显著附加项；去掉estimator error的上一轮instantaneous diagnostic仍超过200 N。
- 90/120显示相似history lag也可在不触发BRAKE时出现，说明estimator lag不是充分条件；allocator、position feedback和vector direction共同决定margin。
- 同一band-limited derivative同时用于identification/state reconstruction与Cartesian damping，形成需求冲突的证据已经存在：前者重视noise rejection和causality，后者通常需要与servo bandwidth匹配的低phase-lag velocity channel。

## UNRESOLVED

- 没有open-loop robot frequency sweep、servo loop transfer function或hardware velocity source，不能给出稳定裕度或安全的新filter参数。
- 不能从保存轨迹证明哪一种control-feedback velocity estimator最佳，也不能把instantaneous MuJoCo truth当作可部署sensor。
- Cross-correlation受非平稳trajectory、BRAKE和termination影响，只能作为描述性lag指标。
- 本审计不预测分离velocity paths后的closed-loop tracking、force或task outcome。

## Recommendation

选择 **b) separate control-feedback and estimation velocity paths** 作为后续架构方向，但本任务不实现变化。保留当前causal path供state reconstruction/identification；另行预注册control-feedback velocity source与bandwidth/phase要求，并在任何rollout前完成离线/bench等价和stability checks。Filter/window sensitivity可以成为该预注册设计的验证步骤，而不是在当前路径上直接试调参数。
