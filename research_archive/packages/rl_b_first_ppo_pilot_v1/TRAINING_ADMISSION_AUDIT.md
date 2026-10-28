# 分级训练准入（冻结前审查）

旧reward v2：LEVEL_A=FAIL（本轮复核发现同为失败时较小JF仍可少扣分）。未启动任何训练。

唯一隔离修复：pilot_v3_failure_cost_floor。失败进度仍归零；真实力/运动成本照实累计，terminal completion项补足总成本到至少1.5。失败完整回报=-10-max(1.5, observed_cost)，消除安全范围内短失败通过少积JF获取优势。原200N×30s力成本上界1.2，原归一化加速度平方时间积分30s成本上界0.3；超过该量仍照实扣分，绝不抵消安全停止。actor/物理/安全/任务/deadline逐字节继承。

修复后的LEVEL_A尚待独立协议与源码复核。G4_STRICT_PASS=FAIL，三类自然证据缺口为timeout、HOLD失败、absolute safety trigger；既有TEST_ONLY_PASS不授予严格资格。LEVEL_C不得授予。

冻结后结论：LEVEL_A=PASS / DEVELOPMENT_TRAINING_ALLOWED。合同SHA256 `ed22f5e2417774f705a13924f66889419450798d6232fe2cfca309c13e225ec0`。原414源文件逐字节一致；新reward25组独立算术检查PASS、接口6项PASS、deadline10项PASS、absolute authority6项PASS。保留完整历史自然nominal/rejection/fallback/reset证据，不重复原物理审计。

三个未观察边界：原phase/global有限任务终止优先、连续sensor-clock HOLD与dwell清零、absolute authority覆盖任务转换/return commit；bounded actor仅提交candidate，不能修改HOLD目标、期限、certificate、escape或停止权。旧已观察真实物理未发现该路径失控；源码/逻辑/物理共同支持当前开发动作无已知安全执行漏洞。此判断不证明全动作不变性，不关闭自然矩阵，不升级G4或LEVEL_C。
