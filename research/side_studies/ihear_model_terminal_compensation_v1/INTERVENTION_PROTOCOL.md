# 物理前研究协议

W1为已暴露开发条件；匹配B/T/D/ER保持。H只改变RETURN5髋终末时长，膝参考恒定。KD120只增加现有膝速度误差反馈20%；PD使用Kp=14、Kd=4.4的终点制动意图；FF使用当前合法参考加速度的0.5倍。PDFF复用同参数，共同受±0.2rad/s²及1rad/s³限制。全部由位置、速度和停止距离触发，不使用绝对秒数或Human truth。新修正位于原逆动力学之后、原补偿/加速度约束/allocator/输出安全过滤之前；不新增时钟入口。旧证书只保留其原参考范围，新控制输出每周期重新过滤并绑定receipt。

每次运行完整task19.030s，原motion含0.5°excursion门。单次/partial不得排名。原18D/T/D/ER身份、plant、Human、gravity、cuff、contact、torque、HOLD、bridge40ms、lifecycle100ms、安全门全部冻结。

{
  "eligibility": "Full 19.030s original task/safety/motion/receipt/native ownership; knee excursion difference<=0.5deg; actual intervention applied; J_F saving>=80% of ER saving vs matched B and >=1%; overshoot must improve >=0.05deg vs ER",
  "priority": "Prefer reference-only H if eligible; then existing DAMPING, FF, PD, PDFF. No tuning on held-out. No sole numerical gate-boundary search.",
  "stops": "Any task/safety/causal failure stops group for review; motion fail preserved and does not prevent independent next track; no more than one bounded revision per direction; all starts<=80, last60min no physics.",
  "next": "Freeze selected candidate, deterministic full repeat, then unused W2 with matched B/ER/new candidate. W2 failure never retuned as blind.",
  "predictions": "Causal rolling offline evaluation does not certify closed-loop prediction; only reuse sufficiently accurate predictor with validated uncertainty; timing contrast may test mechanism independently."
}
