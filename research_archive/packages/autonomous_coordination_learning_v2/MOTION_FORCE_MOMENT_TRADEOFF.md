# 完整force、moment与实际Human运动

新增表示内最佳已执行合格方案为 `MOTION_MARGIN_BACKOFF_RPASS_020`：JF=1398.034615 N·s、JM=107.971017 Nm·s。

|参照|参照JF|降JF N·s|降JF %|JM变化 Nm·s|
|---|---|---|---|---|
|同链B|1436.456498|38.421883|2.674768|6.717322|
|同链H150|1402.643211|4.608596|0.328565|0.898745|
|强固定参照|1400.089728|2.055113|0.146784|0.266329|


观察到相对强固定参照同时改善JF/JM的方案 `CORE_C_023`：JF=1399.188323、JM=106.957822；这不等于相对B也同时改善。

相对强固定参照的phase分解：

|phase|ΔJF N·s|ΔJM Nm·s|Δphase时长 s|
|---|---|---|---|
|OUTBOUND|0.105381|0.014591|0.000000|
|HOLD|-0.000000|-0.000000|0.000000|
|RETURN|-2.160493|0.251738|0.000000|


动作 `MOTION_MARGIN_BACKOFF_RPASS_020`，x=[-0.18310670132483464, 0.0, 0.0, -0.9571745795248379, 0.0, 0.0, 0.0, 0.2]。tracking RMS髋/膝=[0.4494297997170835, 0.5423789594032323] deg；原motion最大归一化比例=0.978736。

原门相对B负担比例：

```json
{
  "velocity_deg_s/max_abs": [
    0.9780906560399754,
    1.0005875336370584
  ],
  "velocity_deg_s/p95_abs": [
    0.9874257765228985,
    1.0349776352187379
  ],
  "velocity_deg_s/rms": [
    0.9922071522250121,
    1.0315884606814485
  ],
  "acceleration_deg_s2/max_abs": [
    0.8521411706450276,
    0.5480845247683893
  ],
  "acceleration_deg_s2/p95_abs": [
    0.9551065242524072,
    1.0263554055801656
  ],
  "acceleration_deg_s2/rms": [
    0.8345843673716568,
    0.7704183258339353
  ],
  "jerk_deg_s3/p95_abs": [
    0.8822398120427943,
    0.8952143703165817
  ],
  "jerk_deg_s3/rms": [
    1.0494110716723097,
    0.9491262090453312
  ]
}
```

native v/a/jerk负担阈值1.0/1.05/1.10/1.25的敏感性单列，其他原门保持：{'1.0': False, '1.05': True, '1.1': True, '1.25': True}。

见 `figures/FORCE_MOMENT_TRADEOFF.png`、`figures/HUMAN_MOTION_AND_NATIVE_JERK.png`、`figures/PHASE_FORCE_MOMENT_CHANGES.png`。native motion逐采样、未滤波、不删端点。原合格表示通过既定仿真门；不保证所有运动指标均改善，也不等于临床舒适性。


同空间各方法最佳合格结果的运动取舍：

|方法|已执行方案|JF|JM|预定义最差比例|最大raw v/a/jerk负担比|v/a/jerk≤1.05|tracking RMS髋/膝deg|
|---|---|---|---|---|---|---|---|
|A|CORE_A_027|1398.549121|107.967222|0.998802|1.098683|False|[0.45082890090947375, 0.5388705575981261]|
|B|CORE_B_020|1399.335523|106.546391|0.986070|1.052379|False|[0.44625705007716693, 0.5391474164162122]|
|C|CORE_C_023|1399.188323|106.957822|0.999941|1.072724|False|[0.44782125491421887, 0.540280024312042]|
|PPO trained mean|PPO_SCRATCH_MEAN_0064|1399.918272|107.492306|0.955767|1.046932|True|[0.45082301614158266, 0.5329294286659827]|


预定义最差比例是本轮既定仿真motion汇总指标，不是物理安全证明。1.05列仅收紧raw v/a/jerk负担比作敏感性诊断，未改变原门。训练sample最小值不替代PPO trained mean。


原估计模型的事后分量投影账本（N·s / Nm·s）：

|方案|原模型分量|force投影积分变化|moment投影积分变化|
|---|---|---|---|
|MOTION_MARGIN_BACKOFF_RPASS_020|inertia|-0.006692|-0.001055|
|MOTION_MARGIN_BACKOFF_RPASS_020|coriolis|-0.001814|-0.000641|
|MOTION_MARGIN_BACKOFF_RPASS_020|gravity|-1.552403|0.163230|
|MOTION_MARGIN_BACKOFF_RPASS_020|passive_elastic|-0.335607|0.132820|
|MOTION_MARGIN_BACKOFF_RPASS_020|viscous_damping|0.010857|-0.057225|
|MOTION_MARGIN_BACKOFF_RPASS_020|soft_limit|0.000000|0.000000|
|MOTION_MARGIN_BACKOFF_RPASS_020|state_residual|0.000382|0.000264|
|CORE_C_023|inertia|-0.008586|-0.003302|
|CORE_C_023|coriolis|-0.000056|-0.001081|
|CORE_C_023|gravity|-6.704883|-1.088147|
|CORE_C_023|passive_elastic|5.821442|0.392398|
|CORE_C_023|viscous_damping|0.009024|-0.022101|
|CORE_C_023|soft_limit|0.000000|0.000000|
|CORE_C_023|state_residual|-0.002456|-0.000538|


这是已实签q/dq/ddq代入原commissioned模型与allocator后的有符号代数分解，各项之和等于该名义norm积分。分量可互相抵消；它们不是独立真实负荷，也不是移除某物理项的因果干预。实际phase JF/JM仍由原scorer决定，不能把重力投影变化直接当作真实患者因果贡献。见 `EXECUTED_COORDINATION_MECHANISMS.json` 和 `figures/EXECUTED_REFERENCE_AND_LOAD_CHANGES.png`。


补充Pareto scout（8候选+4条启动参照/parent；与主32/臂预算分开；仅相对强固定的双改善门JF/JM各0.01）：

|预登记scout|O相对路径|R局部时间|完整|合格|JF|JM|相对强固定降JF|相对强固定降JM|
|---|---|---|---|---|---|---|---|---|
|PARETO_SCOUT_SCOUT_01|0.35|0.07|True|True|1399.910797|107.511532|0.178931|0.193156|
|PARETO_SCOUT_SCOUT_02|0.70|0.07|True|True|1399.468853|107.565072|0.620875|0.139616|
|PARETO_SCOUT_SCOUT_03|0.70|0.14|True|True|1399.540577|107.433104|0.549152|0.271584|
|PARETO_SCOUT_SCOUT_04|0.70|0.28|True|True|1399.783617|107.196377|0.306111|0.508310|
|PARETO_SCOUT_SCOUT_05|1.00|0.10|True|True|1399.354765|107.636573|0.734963|0.068115|
|PARETO_SCOUT_SCOUT_06|1.00|0.20|True|True|1399.520294|107.428914|0.569434|0.275773|
|PARETO_SCOUT_SCOUT_07|1.00|0.40|True|True|1399.811902|107.060786|0.277826|0.643901|
|PARETO_SCOUT_SCOUT_08|1.00|0.50|True|True|1400.000341|106.853490|0.089387|0.851198|


8个scout中有8个被已有主比较B最佳CORE_B_020在JF/JM上同时支配；这组补充点没有自动证明更优Pareto前沿。 固定O_relative_path=1、其它路径/通过速度模式为0，R_local_time从0.1增至0.5时，JF从1399.354765升至1400.000341，JM从107.636573降至106.853490。去程/HOLD积分一致=True，局部回程安排改变了force/moment取舍；这不是缩短完整任务，原phase时钟及门保持。有限4点不证明连续时序的全局规律。


补充motion余量回退已实测2/2个固定候选，最佳原门合格JF=1398.034615。这是原参考模型与传统成本模型共同低力动作失败后，利用过去单模态反馈只减小R_pass_speed的传统修复；不归于主GP或PPO收益，2候选+4冷启动/参照另计。0.49deg仅为额外余量目标，原0.5deg门保持。 见 [固定回退](MOTION_MARGIN_BACKOFF.md)。
