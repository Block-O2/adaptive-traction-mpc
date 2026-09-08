# Phase 3A 离线模型力分解与稠密力图谱

证据类别：**offline analytic/model-derived diagnostic**。本分析只读取冻结的四组 Rigid/P1 证据，没有运行新轨迹、推进 plant、调用 MPC 或修改任何科学设置。

## 定义与边界

- Human-level 计算使用冻结 population-prior Human model、control estimated q、已保存 reference phase/speed/rate，以及注册的 1:1 cuff-aware memoryless allocator。
- `tau_static = G(q) + tau_passive(q,0)`；`tau_refdyn = M(q)qdd_ref + C(q,dq_ref)dq_ref`；`tau_feedback = tau_des - tau_static - tau_refdyn`。
- allocator 在固定 q 下是线性的，因此 `w_total = w_static + delta_w_refdyn + delta_w_feedback` 在向量层闭合；三个向量的 norm 不可直接相加。
- `physical-command` 是独立的 execution/interface residual。P1 spring/damping 只出现在该执行层比较中，没有被塞进 Human torque 分解。
- `tau_feedback` 是按上述排除式定义的 correction bucket；它包含所有未被 static 与 nominal reference dynamics 解释的 MPC demand，不能进一步等同于某一个单独 cost term。

## Rigid 轨迹分解

数值均为 RMS/peak，单位 N。Human-level 表在 control 时刻计算；`feedback` 的原始 peak 均出现在 t=0 初始化点（85.63 N），因此轨迹边界解释以下面的事件表为准。

| 轨迹 | F_static | delta F_refdyn | delta F_feedback | Human F_total |
|---|---:|---:|---:|---:|
| 40/40 | 98.86/108.44 | 0.26/0.43 | 5.91/85.63 | 99.02/119.23 |
| 40/80 | 103.18/111.21 | 0.09/0.16 | 7.59/85.63 | 105.21/143.26 |
| 90/120 | 90.07/110.29 | 0.11/0.17 | 12.64/85.63 | 88.79/133.67 |
| 120/120 | 95.65/109.03 | 0.10/0.64 | 8.64/85.63 | 100.96/123.69 |

分量相对 command RMS 的跨轨迹中位比值为：static **0.941**、reference dynamics **0.001**、feedback/correction **0.077**。这些是 magnitude ratio，不是可相加百分比。

## 执行与接口层

下表在完整 physics 采样率上把已保存 command 以零阶保持方式对齐，因而保留了 P1 120/120 的 222.22 N 终止瞬态。

| 轨迹 | 接口 | command RMS/peak | physical RMS/peak | physical-command RMS/peak |
|---|---|---:|---:|---:|
| 40/40 | Rigid | 99.16/121.05 | 98.99/117.45 | 2.93/76.46 |
| 40/40 | P1 | 99.42/121.68 | 99.28/118.68 | 3.63/85.63 |
| 40/80 | Rigid | 107.51/200.00 | 105.49/197.50 | 23.55/173.78 |
| 40/80 | P1 | 101.67/127.05 | 101.58/123.20 | 3.58/85.63 |
| 90/120 | Rigid | 114.42/199.79 | 110.05/158.73 | 26.42/123.49 |
| 90/120 | P1 | 107.42/139.44 | 104.99/130.23 | 15.34/85.63 |
| 120/120 | Rigid | 103.83/200.00 | 100.61/209.55 | 24.54/241.40 |
| 120/120 | P1 | 103.38/200.00 | 100.02/222.22 | 24.25/215.63 |

`physical-command` 是 world-frame 向量差的 norm。它不能只凭幅值被解释成 spring 或 damping；P1 的详细 spring/damping 分解仍以既有 120/120 事件审计为准。

## 200 N 可行性边界附近

| 位置 | t (s) | static | refdyn | feedback | feedback 沿 total 投影 | 无 feedback 反事实 | Human total | command | Safety nominal executable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 40/80 penultimate_pre_event_control | 11.930 | 105.03 | 0.16 | 40.08 | 38.83 | 104.87 | 143.23 | 200.00 | 206.08263692042476 |
| 40/80 last_pre_event_control | 11.935 | 105.09 | 0.03 | 39.85 | 38.59 | 105.12 | 143.23 | 174.41 | 213.38293869140358 |
| 120/120 penultimate_pre_event_control | 10.400 | 81.25 | 0.14 | 24.95 | -18.70 | 81.40 | 61.01 | 175.37 | 175.3702090293573 |
| 120/120 last_pre_event_control | 10.405 | 81.43 | 0.14 | 39.00 | 38.66 | 81.57 | 120.07 | 200.00 | 207.116781838184 |

这里同时列出 feedback 向量幅值、沿 total-force 方向的投影和移除 feedback 后的反事实 norm，避免把向量 norm 当成可加标量。Safety Filter 的 `nominal executable` 是保存诊断，不属于 Human-level allocator 分解。

## 稠密数学图谱

- domain：q1、q2 各 0–125°，1° 网格；q2=0° 的奇异点保留为 NaN/Inf。
- `static_registered_force_n` 使用注册 1:1 cuff-aware allocator，是轨迹分解的 F_static。
- `static_minimum_translational_force_n` 使用同一 Human torque 约束下的纯最小平移力 allocator，只作为数学下界对照。
- 200/220/250 N 图是 static registered force 的工程余量，不是动态 closed-loop capability，也不是临床阈值。
- conditioning 同时给出 2×2 translational force map 与完整 2×3 sagittal allocation map。
- hip/knee sensitivity 表示 1 rad/s² 单关节加速度增量经注册 allocator 产生的平移力 norm。
- 没有生成单一“200 N acceleration authority”图，因为正负加速度方向、另一关节协同、背景 static wrench 与 moment 约束会产生多个不同而都合理的定义。
- 注册 allocator 的 static force 全域为 **0.06–182.30 N**；最小 200 N static margin 仍为 **17.70 N**，所以 200/220/250 N 图均没有零余量交叉线。
- 单位 1 rad/s² 敏感度：hip **2.76–4.17 N**，knee **0.46–0.78 N**。

## 解释

### DIRECTLY DERIVED

- 四条 Rigid 轨迹的 static、reference-dynamic、feedback/correction wrench 分量均按同一 world frame 重建，并在向量层闭合。
- 跨轨迹 RMS 中位数：static **97.26 N**，nominal reference dynamics **0.10 N**，feedback/correction **8.12 N**。
- A：在 RMS 尺度上，static mechanics 是主要负担：四条轨迹为 **90.07–103.18 N**，相当于 command RMS 的 **78.7%–99.7%**。但它单独不解释 rigid 边界失效。
- B：nominal trajectory dynamics 很小：RMS **0.09–0.26 N**，全轨迹 peak **0.64 N**；在本冻结慢轨迹下不是主要项。
- C：feedback/correction 平常为 **5.91–12.64 N RMS**，但在边界前可沿 total-force 方向增加约 **38 N**，不能视为始终微小的扰动。原始 85.63 N peak 是 t=0 初始化点。
- 稠密图谱显示的是解析 Human mechanics 与 allocator 几何，不是动态能力边界。

### SUPPORTED BY CURRENT EVIDENCE

- D：40/80 在 BRAKE 前，移除 feedback 的反事实为 **104.87 N**，加入 feedback 后 Human total 为 **143.23 N**；同一周期保存的 nominal executable 已达 **206.08 N**。120/120 也出现 feedback 向量方向翻转，并把 Human total 从约 **81.57 N** 推到约 **120.07 N**，随后 command/Safety nominal 超过 200 N。两次 crossing 都不是 static 或 nominal reference acceleration 单独造成；feedback 是触发链的重要部分，剩余放大出现在 robot execution/Safety Filter 层。
- E：当前证据支持 controller/execution stack 在 High-ROM 边界附近对 command force 有实质放大：Human total 尚低于 200 N 时，command/Safety nominal 已触及或越过 200 N。这里的“controller/execution stack”不能再细分为 MPC cost、robot pose/twist feedback、nullspace 或 Safety Filter 的单独因果份额。
- Rigid 的 `command - Human F_total` 与 `physical - command` 表明 Human torque demand 之外仍存在 robot execution feedback、Safety Filter/nullspace 选择和 plant/interface transient。
- P1 的 execution residual 包含 spring/damping/interface state；当前数据支持执行层差异，但不支持把它重新归因到 Human static/refdyn/feedback 三项。

### UNRESOLVED

- 该排除式不能把 `tau_feedback` 继续分解为 MPC cost、state-estimation error、passive velocity term或 optimizer switching 的独立因果贡献。
- 仅凭保存轨迹不能建立放宽 force budget 后 120/120 的完整 continuation，也不能建立 hardware 或 clinical capability。

### NOT SUPPORTED

- 不支持把 dynamic physical force 当作 q1、q2 的唯一函数。
- 不支持把任何分量 ratio 当作可相加的“贡献百分比”。
- 不支持“模型方法优于 RL”或任何临床安全结论。

## 建议

三项候选中建议选择 **2. controller-side investigation**。聚焦 40/80 与 120/120 的 Human feedback/correction、robot pose/twist execution feedback、allocator/nullspace 与 Safety Filter 可行性之间的分层关系。当前离线结果已经排除 static mechanics 与 nominal trajectory acceleration 作为 200 N crossing 的单独解释；直接放宽 120/120 force budget 会改变终止边界，却不能解决剩余归因。完成这一层离线或极小局部审计后，再决定是否预注册 relaxed 120/120 continuation。
