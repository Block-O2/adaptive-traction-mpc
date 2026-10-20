# 方法与参数合同

原B与历史18D公式、完整原向量及RETURN两plateau分别见METHOD_DEFINITION.md、PARAMETER_MAP.json、FROZEN_18D.json。候选CANDIDATE.json与BOUNDED_REPAIR.json是完整候选，各自包含全部18项和plateau，不仅保存差值。

C：free_parameters[3,4,13]=0，其余逐字节数值相同；normalized同索引归零。令e=sin²(πclip(m,0,1)),u=2m−1，原去程速度乘数1+e[x3±x4±x13u]成为1；原native速度仍由当前目标与因果reference state决定，因此不是固定速度，也不保证最终已发reference速度恒定。原姿态公式、RETURN及终点/HOLD保持原规则。

R：仅若C科学假设失败，全OUTBOUND位置/速度9项[0,1,2,3,4,10,11,12,13]乘0.5；RETURN原样。R是新固定策略，不能称冻结18D泛化。

RUN_PLAN在新physics前冻结候选、N2开发与U1/U2/U3验证prefix、gate、最大40 START和T0+4h硬截止。T0=2026-10-17 13:26:19北京时间；最迟16:26:19停止派发，16:46:19结束物理，17:26:19前交付STOP。所有真实attempt串行，live os.fork完整继承隐藏状态；共同prefix进入完整JF，父hash前后不变。

评价：TASK 5ms force向量范数左积分；phase精确区间裁剪；native0.25ms qvel数值导数的全程/phase motion；tracking、moment、ROM、clearance、contact、torque、task/HOLD/goal、source age与receipt/native ownership均由原冻结评价器。原motion协议逐字节一致，raw jerk max仅诊断。失败/partial不排名；旧host实时失败不得被scientific PASS替代。

证据只为PHYSICAL_LEVEL1、同一Human/模型的开发和合法prefix remaining suffix；不是不同患者、正式Native LEVEL2、host-clock LEVEL3、临床结论。数学合同不冒充物理验证。
