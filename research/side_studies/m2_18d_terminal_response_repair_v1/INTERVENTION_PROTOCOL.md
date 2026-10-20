# 事前协议：T — 最终去程 suffix 时长单因素

登记于新增 physics 前。N2 已暴露，用于机制开发；N1仅作历史PASS对照，不作新状态验证。原B/18D/C/R及历史失败冻结。T不是18D参数调优，不训练任何学习器。

## 假设与单一修改

N2最终quintic在短距离内从膝8.862332°/s到0，参考存在加速后制动，真实膝响应在参考停下后仍有速度和负加速度峰。检验延长该最终参考的制动时间能否降低真实峰，且保留先前18D累计力收益。该实验只识别合法终末参考时间形状的总效应，不能唯一分离FAST/allocator/contact中介。

冻结T系数 **1.5**，仅在OUTBOUND原18D已经选出的target精确等于内部phase goal时启用。先让原18D完整执行原始选目标与选通过速度，再对同target、同request reference q/dq、同目标dq、同phase用原`plan_fixed_duration_reference_contract`重建，时长为原suffix时长×1.5向上对齐5ms。原quintic边界、ROM、连续几何证明、mechanics、causal tracking-offset、current admission、40ms bridge、100ms lifecycle、source age和receipt全部仍由原执行链审查。若原接口拒绝T，记录拒绝并保留原合法执行，不能绕过合同。HOLD/RETURN及非最终OUTBOUND完全保留冻结18D。

1.5是一次事前固定的机械检验，不进行倍率搜索。N2存档距离1.860977°、初速8.862332°/s，原0.220s使平均速度大于初速；延长到0.330s允许更缓的制动几何。数学曲线只用于接口与假设检验，不能当作真实运动证据。

## 先决条件

先完成原源码/数学/接口检查。T的生产公式必须对实际存档请求重建；位置/速度边界、定时、原几何证书和外部execution checker调用必须核对。所有新执行源独立复制并登记路径迁移及SHA，原B源不得写入。原参数18项和RETURN plateau字节一致，motion协议字节一致。

## 完整配对与固定分支

用N2 seed=2026101702、合法prefix OUTBOUND=[[-.06,-.06,-.06]]原cold commissioning后，在同一个完整live父状态fork B、冻结E、T，串行执行。B/E必须与历史raw物理字段精确一致；不以重放qpos/qvel构建父状态。全TASK包含共同前史，task为19.03s，完整phase不缩短。

主要资格为原task、motion/fairness、绝对安全、causal receipt全PASS；保留明确降力定义为相对匹配B完整JF至少1%，且同时报告相对E变化。不因T结果改变primary、权重或阈值。额外降力不是本实验目标。

- A：T全部资格PASS且降力≥1%，同live父状态做一次确定性T重复；预算允许时固定验证U1：seed=2026101801、OUTBOUND=[[-.075,-.045,-.05]]，它曾在上一轮登记但从未运行，故本轮必须核实后才可称新prefix。同一Human，只验证remaining suffix。U1比较B/E/T，不根据U1重选。
- B：motion PASS但降力<1%，作为运动质量修复证据，停止扩展；本轮不进行倍率折中搜索。
- C：T motion FAIL，即使降力也不得晋级；不减倍率重试。分析终末响应后STOP。
- D：响应无法归因或未产生预注册参考效应，停止physics，交付最小证据缺口。
- E：接口不能保留原合同而独立实现该因素，记录数学/接口阻断，不做虚假干预physics。

只有完全PASS候选才重复，重复不是新状态。最多20 START，含父、fork、失败；每次保留START/END、returncode、native steps、partial与错误。T0=北京时间2026-10-17 14:05:15，18:05:15硬截止，17:20:15后无新START。完成有限分支即可提前结束。最后独立核算、历史/Git保护核验、owned进程退出，STOP。
