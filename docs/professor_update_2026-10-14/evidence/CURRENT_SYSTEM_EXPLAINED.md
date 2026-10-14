# 当前系统怎样工作：从患者状态到真实运动

## 先用一句话说明

系统不是把患者的腿强制设置到目标角度。它根据机器人和袖套的测量估计人体状态，在线选择下一对髋膝参考目标，再由机器人通过真实接触推动被动人体。患者实际怎样运动，需要由完整动力学反馈测量和评价。

治疗合同给定起点、终点、ROM、OUTBOUND/HOLD/RETURN及完成条件。累计交互力J_F=∫||F_cuff(t)||dt是重要指标，但少做动作、缩短HOLD或改完成条件都不算改善。力矩积分、真实速度/加速度/jerk、运动剂量、tracking和clearance也要同时检查。

## 1. 输入来自哪里

可部署路径使用robot/cuff的因果测量和commissioned belief，不把MuJoCo真实人体q/dq作为controller输入。由cuff位姿、twist与geometry重建Human state；实际true q/dq只在实验评价中用于检查运动负担和估计误差。若某geometry或动力学量不可辨识，不能用simulation truth偷偷补齐再称在线估计成功。

commissioning先执行合法探测运动，建立hip位置、thigh length、knee-to-cuff lever和control-effective动力学模型。可识别的lever不等于full shank length和rho分别已知；拟合误差小不保证后续床面clearance证书通过。当前冻结B可用commissioning_only；这不是已经实现repetition间个体化。模型来源的STRUCTURAL_PRIOR、MEASURED、CALIBRATED、ONLINE_ESTIMATED、FIXED_NOMINAL或SIMULATION_TRUTH要单独说明。

## 2. 谁决定下一段运动

任务状态机决定当前phase与合法完成/hold条件。高层Human-waypoint planner从estimated state和phase goal提出有限Δq候选，得到下一对hip/knee目标。它可比较局部deterministic score，或者在原权限范围内接收冻结Q提供的剩余计划排序。goal、HOLD和terminal仍属于任务与B。

scheduler从当前已经发出的reference q/dq出发，为候选目标和endpoint velocity生成quintic段，选择满足reference motion、ROM和continuous clearance的duration。mechanics screen再用commissioned model检验所需wrench与原约束。在线选择路点不等于取消轨迹规划；只是把一次固定全episode轨迹改成在线生成下一段。

## 3. 为什么计划算出来后还不能马上用

planner计算期间，机器人与人体仍可能运动。旧snapshot上通过的目标，在结果返回时未必还能接入。current-state admission因此重验真实当前估计状态、model/reference版本、phase、目标、age、ROM、motion、clearance与接入连续性。source timestamp从原测量开始计，不因计算完成或重试而刷新。

100ms lifecycle限制proposal年龄；40ms bridge提供预先验证的短接续/停止通路；strict55是另一个历史qualification门槛。它们不同于5ms FAST服务周期或0.25ms native physics步长。迟到、拒绝或旧计划耗尽后使用合法carry/stop→SAFE_FALLBACK_HOLD，并以新state/source再规划；不能让一次失败proposal悬挂着继续执行。

## 4. 最后是谁实际推动人体

FAST反馈、安全与allocator将有效参考变成机器人控制需要的cuff wrench与六轴torque。原MuJoCo模型中的robot motor受原torque限幅；袖套attachment/bushing通过相对位姿和速度产生力、couple及transport moment，向机器人和人体施加成对作用，再由原native动力学步进得到实际q/dq。Human没有本轮新增主动执行器。

数学目标、issued reference、actual Human motion是三份不同记录。每个实际native step还应能归属到applied command receipt与实际torque；proposal被选中或参数非零都不等于运动已经执行。scientific模式通过显式物理步保证有限同状态实验可复现，host模式还要满足真实计算/提交年龄与时序；前者不能替代后者。

## 5. B、E、Q、自由参考各自负责什么

|角色|负责的决定|已有证据|当前限制|
|---|---|---|---|
|B|估计、在线waypoint、quintic、governor、准入、安全、robot执行与fallback|同条件科学精确回归，有限完整physical与causal host研究|原strict55/R2/FAST各包结果不同；没有统一正式部署资格|
|E|离线搜索更好的完整协调运动，提供best-known reference|有限动作族中实际force收益|有限预算；非全局最优；非成熟RL或患者个体化|
|旧linear Q/M2|有限remaining计划的成本排序，原B合法执行|同Human约6%–9%force收益；实际非零native执行|固定candidate/mask下无state×plan；运动负担变差；非连续个体化|
|Neural Q|尝试学习state与plan交互排序|32×32具有交互表达|两个test state上regret较linear差；覆盖/标签不足|
|自由参考研究|离线改变共同/相对进度与hip/knee路点通过速度|原10维开发LEVEL1降2.457489%，合法状态motion1/2PASS|非原B LEVEL2、非LEVEL3；中间姿态治疗等效性未证明|

## 6. 学习为什么暂时没达到预期

旧native linear Q把state项与candidate项相加；同一候选集合下，两candidate分数相减会消掉公共state项。因此它能形成有用固定偏好，却没有学会“当前患者状态变化时哪个计划更好”。candidate mask、carry和B可行性会随状态变化，不能把这些执行机制的变化算作Q的状态学习。

Neural Q能表达交互，但数据仅同Human、少数独立父状态、重复的branch rows，而且现有候选在不同状态中缺少明确ranking inversion。V_commit是执行声明suffix后回B的值，V_replan是后续重新选择的值，两者不自动等价。在这些问题未解决前，加网络容量或训练轮数没有保证。

## 7. 为什么现在先探索优质运动

如果更低force只是用更快膝运动、更大行程或更高moment换来的，学习得再快也未必符合康复目标。先找真实可执行、完整任务和多指标合格的运动，才能定义值得学习的action与label。离线teacher只是研究起点：以后还需要明确治疗允许的姿态自由度、更多不同合法state、原B接口迁移、host资格，最后才是few-repetition个体化。

本轮没有训练Q/Neural Q、G/P或online adaptation，也不把新扩展离线参考写回正式B。源码与历史分母见DETAILED_RESEARCH_HISTORY.md；今晚动态结果见REPORT.md。


## 本轮实际Human与任务：不能用类默认值代替

源码实际加载`high_rom_nominal_sync_120_v1.json`与其options合同，而不是早期Phase3的80°/100°默认任务。当前case为1.72m/75kg名义Human，rest5°/10°，K=10/10Nm/rad、B=5/5Nms/rad，cuff为shank的72%；start/return目标5°/10°，OUT目标120°/120°。`high_rom_v1.py`从冻结配置构造双方0–125°hard ROM与5°soft margin，这是一项明确工程假设，不是患者测得ROM。任务goal位于soft-limit onset，距hard bound5°。

原task合同要求角终值误差≤1°、速度≤2°/s，并另有controller更紧margin；原最低continuous HOLD为0.5s。当前MATCHED研究与其既有执行路径实际阶段时长约OUT9.005s、HOLD1.020s、RETURN9.005s、完整19.030s，所有新候选仍与该匹配B按冻结时间规则比较，不能把合同minimum与实际HOLD混写或缩短HOLD获益。原独立速度/加速度工程限为45/75°/s与300/600°/s²，另需更严格的B-relative motion比较，两层不互相替代。

人体参数用于隐藏plant创建/评价；controller使用明确ROM先验、合法任务目标及commissioned估计，真实q/dq留在evaluation。cr12_plant绑定六个既有motor；原sleeve weld在此bushing模型中关闭，接触由原spring-damper paired force/couple驱动，不是将参考强制焊接为人体状态。本轮不修改此物理定义。完整config/options与来源哈希、actual baseline起点和阶段时长见CURRENT_MODEL_AND_TASK.json；源为sac_env.py:147–150、high_rom_v1.py:10–30、runtime_coordination_residual_v2.py:1960–1978、cr12_plant.py:272–345。原初始化/reset写qpos不等于优化期间人体状态控制，后者未授权也未加入。


## 原工程限值与连续真实运动统计的口径

45/75°/s与300/600°/s²同时用于原task/scheduler和A scorer，不能只说参考限值。scheduler使用原fraction .5/.25，参考范围约22.5/37.5°/s与75/150°/s²；原HumanMotionAccelerationAuthority基于完整因果20ms dq_hat历史，A human-speed用TASK采样true dq，human-acceleration用有效monitor窗口。它们不是统一0.25ms原生true dq瞬时导数硬阈值，更不是临床阈值。本轮另用全部0.25ms真实dq的raw导数做冻结B-relative比较；两种口径都保留。强低force代表虽原A通过，仍会因相对速度/加速度、jerk、行程、时长或moment等B规则失败。来源详见reports中的selected-limit独立审计与各_MEASURED完整原评价。


<!-- OVERNIGHT_CONCLUSION_START -->
## 本轮冻结后的结论

原完整动力学中18D开发最好下降2.635613%，新合法prefix条件合格0/4；事先冻结secondary开发下降2.310981%，新条件合格1/4。未用测试改选primary；这是同一Human剩余策略的LEVEL1证据，未迁移原B接口或完成host/临床资格。

下一步仍应先确认治疗允许的中间姿态和motion依据；新状态的速度/加速度/阶段端点失败说明名义开发优化不能直接当可靠teacher。完整逐条件结果见REPORT与VALIDATION_RESULTS，接口变化与负担修复诊断见MECHANISM_ANALYSIS。本轮已停止，不继续训练或自动开启下一包。

<!-- OVERNIGHT_CONCLUSION_END -->
