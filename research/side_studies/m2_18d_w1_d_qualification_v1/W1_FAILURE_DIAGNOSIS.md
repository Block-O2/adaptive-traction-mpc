# W1 运动失败诊断（新 physics 前冻结）

本诊断只读取历史真实 native 数据。W1 中 B/E/T 已执行；D 尚无 W1 结果。时间均相对完整 TASK 起点。

## 直接观察
膝速度超过完整 B p95×1.10 的第一个样本：11.992250s；膝加速度：1.715000s。超限样本不是瞬时资格门，原门评价全程 p95。
速度高值样本按 OUT/HOLD/RETURN 为 [0, 0, 4547]；加速度为 [1698, 0, 2706]。
全程 excursion 差 hip/knee=[0.15917680106832677, 0.5348840179534022]°；超过最终 B excursion+0.5° 的首次时刻=[None, 16.489500000036458]。
D 首个计划请求 12.790000s。其前缀 p95 计数和 excursion 不可逆下界均未证明必失败；不能把 T 的失败改写为 D 的失败。

## 源码与执行合同
matched_harness.control 在每 phase 的 prefix 槽优先执行合法图残差；W1 OUTBOUND0 在共同冷父里真实执行后完整地址空间 fork，RETURN0 在每个子臂中按同一规则通过原检查执行。后续策略造成的活状态可以不同，名义相同 RETURN0 不表示实际 RETURN 入态完全相同。冻结 D 只在 RETURN2/3 改内部姿态目标，每槽 [+0.3,-0.3]°，保持各活态原选择 duration/pass velocity；18D 参数、RETURN plateau 和 T1.5 不变。

## 归因限制与下一项最小实验
W1 相对 V1 同时改变 OUTBOUND 与 RETURN 背景，且正向 OUTBOUND 改变了后续 planner/plant 的整段历史。失败所在 phase 不识别原因。E/T 的受控差异仅能归因于冻结末段时长合同及其后续闭环响应。精确时段、峰、所有决策及证书/激活记录见 audit/W1_DIAGNOSTIC_NUMBERS.json。
需要以同一 seed 和 W1 OUTBOUND0 固定，单独移除 RETURN0；以及固定 W1 RETURN0、将 OUTBOUND0 换回 V1 合法图的两个配对条件。每个条件各自完整 B/T/D；它们估计整个背景规则的受控效果，不能把入态、allocator 或接触中介再拆成独立原因。D 是否能影响 RETURN 高值和后段 excursion 需要实际执行；OUTBOUND 历史不可由后段 D 改写，但既有下界未阻止全程门通过。

## 尚未识别
具体 allocator/contact/FAST 中介尚未识别；reference、tracking、moment、clearance 和请求/激活时间是可核验的相关响应。没有独立干预支持将其中任一项称唯一原因。N2/U1/V1/V2 仅证明同一 Human 的有限 prefix 条件，不证明任意合法状态。

## 共同高值与新增负担

velocity_deg_s: 第一个高值样本 B 也超该参照=False；T 超而 B 未超的最早时刻=11.992250s。B 各阶段高值计数={'OUTBOUND': 0, 'HOLD': 0, 'RETURN': 1942}。因此最早高值不等于首次策略差异，更不等于原完整资格门的瞬时失败。

acceleration_deg_s2: 第一个高值样本 B 也超该参照=True；T 超而 B 未超的最早时刻=3.125250s。B 各阶段高值计数={'OUTBOUND': 1347, 'HOLD': 0, 'RETURN': 1366}。因此最早高值不等于首次策略差异，更不等于原完整资格门的瞬时失败。

allocator 分量、clipping、命令、allocated wrench、clearance 与接触的完整阶段范围已保存 audit/W1_COMPENSATION_SIGNALS.json；只作相关解释，不用它们重定义资格或宣称唯一中介。

## 冻结协议后的受控实验结果

新物理结果与背景条件效应见 REPORT.md、EXPERIMENT_RESULTS.json、derived/BACKGROUND_CONTROL_EFFECTS.json；原事前诊断保存在 provenance/PREPHYSICS_W1_FAILURE_DIAGNOSIS.md，未回写历史。W1 D原完整资格失败；具体失败项['velocity_deg_s/p95_abs', 'acceleration_deg_s2/max_abs', 'acceleration_deg_s2/p95_abs', 'jerk_deg_s3/rms', 'excursion']。

D新增16.700s终末native峰，前一个5ms命令区间可见allocator/实际command脉冲；已采样contact为空、clipping为0、receipt source age为0。未识别唯一中介，不以峰值发生于RETURN直接认定RETURN参数是原因。完整窄窗见derived/W1_D_TERMINAL_WINDOW.json。

### 背景控制的可验证影响

|条件/臂|膝v p95|膝a p95|膝excursion|匹配B的v/a p95 ratio|原门|
|---|---:|---:|---:|---|---|
|W1_T|22.559290|28.552719|111.830856|1.115366/1.130897|FAIL|
|W1_D|22.359217|28.562887|111.839695|1.105474/1.131300|FAIL|
|R0_T|22.219639|31.915326|111.862695|1.083251/1.088300|PASS|
|R0_D|22.211520|31.717245|111.899138|1.082855/1.081546|PASS|
|O0_T|22.559290|32.960832|111.837271|1.075307/1.091366|FAIL|
|O0_D|22.359217|32.852949|111.846110|1.065770/1.087794|FAIL|

R0在RETURN前q/dq与W1精确相同；移除RETURN0背景后T/D通过原门，并改变RETURN真实响应，证明固定W1 OUTBOUND下的背景规则条件效应。O0改变OUTBOUND，T/D的RETURN q却只相差约9e-9°；T膝v p95基本不变，但匹配B参照变大使相对v门通过。加速度绝对p95甚至变大而相对门通过；excursion仍失败，D的终末a/jerk峰也仍存在。背景控制不是综合运动改善，也没有识别某个K3分量或allocator为唯一原因。

严格从终末RETURN5(16.540s)后才开始的修复不可能消除已累计的膝v/a p95与excursion失败：4234/4353个高值样本已超过原时长容差允许3827个，excursion亦已超最终B+0.5°。原D首个RETURN2请求前下界未成立，但到了终末才处理已太晚。下一合同需更早介入并保留完整原门，不能只修复16.700s峰。
