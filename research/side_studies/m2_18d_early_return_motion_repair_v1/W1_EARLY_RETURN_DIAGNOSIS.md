# W1 早期 RETURN 运动诊断（物理前）

历史来源与 SHA 保护见 audit/HISTORICAL_MANIFESTS_VERIFIED.json；本文件不重跑诊断 physics。所有时间相对完整 TASK。

|槽|request|activation|splice|duration|此前 v 高样本|此前 a 高样本|此前膝 excursion°|
|---|---:|---:|---:|---:|---:|---:|---:|
|RETURN0|10.025|10.030|10.030|1.615|0|1698|110.569628|
|RETURN1|11.650|11.655|11.695|1.090|0|2303|110.569628|
|RETURN2|12.790|12.795|12.835|1.095|1922|2364|110.569628|
|RETURN3|13.935|13.940|13.980|1.245|3740|2436|110.569628|
|RETURN4|15.230|15.235|15.275|1.260|3740|2505|110.569628|
|RETURN5|16.540|16.545|16.585|0.440|4234|4353|111.830857|

## 直接物理观察
W1 D 完整 task/safety/causal PASS、motion FAIL。首段膝速度高值约 11.992–12.473 s，落在 RETURN1；其前缀尚未达到不可逆 p95/excursion 下界。RETURN5 请求16.540 s时，既有计数和excursion已超可补救下界；16.700 s终末峰值不是全部失败的充分解释。加速度高样本更早已在OUTBOUND出现；进入RETURN并非原因识别。

## 可验证背景影响
R0 固定W1 OUTBOUND、移除RETURN0背景后T/D通过；但某些绝对p95和excursion反而高于W1，完整B分母也变化。O0固定W1 RETURN、更换OUTBOUND后，T/D RETURN实际轨迹几乎重合，完整p95资格仍因OUTBOUND负担及匹配B改变；D终末尖峰仍存在。这识别整个背景规则的条件效应，尚不能分解allocator等中介或完整交互。

## 源码与执行合同
优先干预RETURN1的选后suffix duration，保留其原选target及pass velocity，使用原plan_fixed_duration_reference_contract重建quintic与独立证书。完整phase9.005/1.020/9.005 s合同通过原endpoint等待保持，不能缩短任务。桥接40ms、lifecycle100ms、当前状态和source age准入、fallback均沿原代码执行。原接口已支持，不扩展正式安全语义。

## 数学假设与未识别
固定端点速度的延时可能降低内部速度峰，但不保证所有极值单调改善，也可能改变后续选择、终末反馈及力矩。因此先重做连续性、ROM、几何、力学、当前准入预检，再以完整配对physics检验。D RETURN2/3规则不变，后续活态选择允许因果响应。
p95是同条件完整B的统计比，不是绝对临床阈值；高值计数是不可逆下界工具，不替代原quantile门。到候选真实splice之前的历史、最大值、累计行程、excursion不能被后段删除；p95可修复性还依赖剩余样本预算。任何模型预检都不构成物理通过证据。
原reference近零而16.695s allocator/torque脉冲先于Human峰值只是相关序列，尚未证明唯一机制。

完整事件/计数见 derived/EARLY_RETURN_DIAGNOSIS.json；共同图见 figures/W1_early_return_timeline.png。

## 本轮物理后补充（不改变物理前假设）

RETURN1真实执行后清除v95/amax/jerk资格失败；RETURN4时长1.260→1.515s后a95通过。当前唯一失败为膝excursion：差0.548596467°，超原门0.048596467°；首次不可逆17.066250s，晚于新终末请求16.900s。这与旧D在终末请求前已越下界的情形不同。该区别支持下一步聚焦停止响应，不支持放宽门或宣称泛化。完整数据见derived/REMAINING_EXCURSION_GAP.json、derived/CAUSAL_RESPONSE_AUDIT.json及REPORT.md。
