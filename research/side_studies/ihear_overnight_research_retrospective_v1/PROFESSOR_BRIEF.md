# 教授15–20分钟讨论底稿：从轨迹跟踪到协调运动

阅读方式：这是8页内容结构和口头讲解底稿，尚未制作PPT/PDF，也未发送。上次实际教授汇报边界未确认，以下保留完整主线；用户明早按教授已经知道的内容裁剪。每页建议一张图或一个核心证据，详细source/分母放研究史与证据表。

## 第1页｜最初的问题与最早系统（约2分钟）

我们希望机器人帮助患者完成康复动作，既要完成规定任务，也要降低人与机器人累计交互力；最终希望少数重复后适合这个患者。早期Spring2D用于控制和辨识方法研究，教授MATLAB提供髋膝与双臂的运动示意，之后才建立真实被动Human与robot+cuff的物理链。这些是不同模型，不能把早期很低的示意接触力与现在的袖套交互力直接比较。

最早Human V2任务由外部预定整条轨迹、速度、时长和端点。controller面对q_ref/dq_ref/ddq_ref，重点是跟踪、估计模型和保持安全。Stage2/3 inverse dynamics加反馈与后来的Stage4 MPC是不同版本。

图：ARCHITECTURE_EVOLUTION中的固定参考框架。只需说明“当时运动由外部规定，controller负责执行”，不展示所有代码模块。

## 第2页｜扩大ROM和真实接触暴露什么困难（约2分钟）

端点几何可达不代表完整路径能执行：近伸展几何、gravity/支撑、机器人力矩、袖套moment、接触瞬态与终末settling都可能形成瓶颈。历史90/120任务中command约200N而实际physical达到218.44N，说明指令安全与真实interaction安全不同。

修正即时cuff velocity feedback消除了原BRAKE/200N瓶颈，但高ROM部分仍SAFE_INCOMPLETE。既不能说“整个控制完全失败”，也不能把96%或99%的进度说成COMPLETE。这段研究让我们知道必须检查真实物理执行，而不能只检查数学命令。

图：研究演变图的“模型真实化→physical interaction→反馈与安全链”部分。大ROM旧任务与当前M2任务分开。

## 第3页｜关键架构转变：谁决定怎样运动（约3分钟）

转变发生两次。先从整条时间参考变成Goal-directed torque MPC，让controller面向phase目标决定generalized action；它暴露了Human-only预测与robot/interface实际执行的不一致，以及HOLD/RETURN与motion合同问题。之后才形成online hip/knee waypoint：高层从当前估计状态选择下一对目标，scheduler生成quintic中间运动，底层robot通过cuff真实执行。

所以我们没有直接设置人体关节角，也没有取消trajectory planning。变化是把运动决策从开始时固定整条轨迹，改成在线规划下一段；可执行性、安全与fallback仍必须保留。Phase3 V3最初只是接口smoke，后来的full3D B才接上完整robot执行与lifecycle。

图：固定轨迹→Goal torque→online waypoint三列。重点解释角目标、reference与实际人体运动的区别。

## 第4页｜B现在做到什么、还不能做到什么（约2分钟）

当前研究使用1.72m/75kg名义Human、shank的72%cuff、120°/120°目标；双方0–125°hard ROM是工程假设，未来自患者测量。实际模型与历史80°/100°默认domain分开。

B包括commissioning/state-model估计、在线waypoint、quintic/scheduler/governor、current-state admission、source-age lifecycle、短bridge/fallback和真实robot torque。它让我们能判断proposal是否真的执行，并把每个native step归到实际command。

科学仿真已能做精确同状态比较，有限host研究能完成physical/causal任务。正式实时资格仍要看各合同；原strict55、R2和FAST结果不等同，历史FAIL保留。B并未证明临床、硬件或few-repetition能力。工程重要性是让后面的收益具有可核验意义，不必在正文逐轮展示所有毫秒优化。

图：能力边界；附录保留原0/13 completeVALID、0/8 R3资格与后续拆轴结果。

## 第5页｜E、Q与Learning的预期和缺陷（约3分钟）

E先离线搜索较好的协调运动，帮助回答有限动作空间中是否有值得学的收益。M2把Q接在B合法remaining-plan选择处，Q没有取得robot torque或Human状态写入权。旧linear Q在有限同Human条件下有约6%–9%实际force收益。

但120D linear是state项加plan项。固定candidate集合中比较两个plan时state项相消，在固定candidate/mask/carry/count的131decision probe中排序只有一种；实际运行mask/carry变化可改变候选集合。这说明它形成了有用偏好，却还没有学会随当前state改变计划优劣。32×32 Neural Q可表达交互，但test仅两个state，regret9.9306N·s、linear1.6207N·s；候选覆盖和监督目标仍不足，不能只归咎网络太小。早期96D SHORT MLP曾好于对应ridge，不能笼统说所有MLP都失败。

早期scratch SAC300k没有取得完整phase任务；DAgger学生曾会完成，却在后续SAC fine-tuning丢失能力。anchored SAC50k的14.486%改善主要减少过长HOLD，不能与相同时长的协调force收益排序。这些不同路线、权限和分母在附录分开。

更进一步，V_commit与rolling V_replan合同不同，已有数据不保证训练目标等于最终在线policy价值。少数模型更新或offline训练完成都不是少repetition个体化成功。

## 第6页｜为什么先寻找优质协调运动（约2分钟）

force减少可能以膝速度、加速度、excursion和moment增大为代价。强低force方案约15%降力，却没有通过冻结motion规则；有些超速持续数秒，不是孤立数值峰。旧10%非劣、0.5°行程、剂量±5%是研究比较协议，并非已认证临床阈值。

我们因此先用同完整活状态fork比较，避免冷启动和前干预混杂。旧hash snapshot不能独立恢复，live-state address-space fork才让科学反事实成立。原候选请求只采一个相对进度delta，PWL数学图很丰富不代表执行权限丰富；这推动共同进度与独立路点速度的扩展。

图：force与motion权衡，以及“数学参考→issued reference→actual Human”的三层。

## 第7页｜当前可信结果与今晚新增结果（约2分钟）

上轮扩展参考在原完整动力学中开发J_F从1438.613498降至1403.259730N·s，改善2.457489%；去程与回程分别减少17.273197和18.080565N·s，HOLD几乎无变化。冻结motion开发PASS，但合法状态验证1/2PASS，失败为excursion。该结果是LEVEL1，不是原B LEVEL2或host LEVEL3；phase-shape差约14.24°，治疗等效性仍需讨论。

<!-- OVERNIGHT_RESULT_START -->
今晚实际新增：冻结开发最好下降2.635613%，新合法条件motion 0/4；相对上轮增加约0.178124个百分点。事前冻结secondary开发下降2.310981%，新条件合格1/4，不用测试结果改选primary。LEVEL1限定；同一Human、合法prefix后剩余策略的验证，不能称跨患者或整串原策略未见验证。验证状态COMPLETE。
<!-- OVERNIGHT_RESULT_END -->必须一同呈现：新候选来源、同条件B、实际attempt分母、motion/安全/完整任务、新条件验证，以及最强低force失败代表。若没有更好合格运动，也保留探索范围和负结果，不把脚本PASS当科研突破。

图：实际q/dq、累计force及分phase收益；数据不足不画。

## 第8页｜希望教授帮助决定什么（约2分钟）

1. 康复任务允许多大中间髋膝姿态调整，phase-shape应限制到什么范围？
2. 真实速度、加速度、jerk和运动剂量应依据什么评价，force/moment如何权衡？
3. 下一步保留B原生离散目标，还是迁移最小bounded common-progress/独立速度接口？
4. 论文科学贡献应优先执行架构、低力协调优化，还是少repetition个体化？当前后者尚未证明。
5. 当前2D Human和cuff模型与未来硬件、患者运动的关键差距是什么？

建议先确认前两项，再冻结下一研究合同。用户明早先读这份底稿，再用详细研究史检查理解，把确定的事实、负结果和待决定假设分开，最后亲自制作正式PPT；本轮不自动制作或发送。
