# 运动失败与状态依赖诊断

本轮新状态T motion通过2/2。重复不增加分母。原18D的失败逐项保留。

|条件|臂|motion|失败项|完整髋/膝amax °/s²|膝峰task s / phase|
|---|---|---|---|---|---|
|V1|B|PASS|—|85.115049 / 72.100223|2.85425 / OUTBOUND|
|V1|E|FAIL|acceleration_deg_s2/max_abs|77.563960 / 92.406356|7.06725 / OUTBOUND|
|V1|T|PASS|—|77.563959 / 75.514435|2.93975 / OUTBOUND|
|V1|T_repeat|PASS|—|77.563959 / 75.514435|2.93975 / OUTBOUND|
|V2|B|PASS|—|85.115049 / 72.066461|2.82925 / OUTBOUND|
|V2|E|FAIL|acceleration_deg_s2/max_abs|77.563960 / 83.236791|7.06250 / OUTBOUND|
|V2|T|PASS|—|77.563959 / 75.673107|2.91475 / OUTBOUND|
|V2|T_repeat|PASS|—|77.563959 / 75.673107|2.91475 / OUTBOUND|

每个失败joint、完整metric值/匹配B比值/1.10门、峰时间、各phase贡献与超限时间见audit/*_PREFIX_AND_FAILURE_AUDIT.json。p95和RMS是全任务统计，phase比值只用于定位，不能改成新的phase门。jerk max保留为诊断项。

## V1

E：knee acceleration_deg_s2/max_abs，候选=92.406356048，B=72.100222774，比值=1.281637594>1.10；实际峰7.06725s（OUTBOUND），signed=-92.406356048。
T：冻结motion/fairness全部通过。
T/E此前schedule和splice前q/dq、torque、force一致。仅一个ACCEPTED末段duration干预；suffix E=0.225s，T=0.340s。具体request/activation/splice/receipt/native连接在对应NEW_TIME_EVIDENCE.json。

## V2

E：knee acceleration_deg_s2/max_abs，候选=83.236791017，B=72.066461224，比值=1.155000393>1.10；实际峰7.06250s（OUTBOUND），signed=-83.236791017。
T：冻结motion/fairness全部通过。
T/E此前schedule和splice前q/dq、torque、force一致。仅一个ACCEPTED末段duration干预；suffix E=0.215s，T=0.325s。具体request/activation/splice/receipt/native连接在对应NEW_TIME_EVIDENCE.json。


本轮未观察到T失败，因此没有可据以确认的T失败状态依赖。历史N2/U1与本轮两个prefix的结果支持该有限邻域的末段修复；它不证明不存在更远状态的失败。原18D若在多个状态出现相同膝末段加速度失败，只说明已测条件中的可重复现象。

固定T不能改变splice以前已经发生的运动峰；修复后完整任务峰若转移到前段，是后续扩大状态验证应关注的边界。不得据此自动为各状态增加特殊倍率。
