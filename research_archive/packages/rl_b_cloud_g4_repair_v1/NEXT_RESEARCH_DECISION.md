# 下一轮决策

TRAINING_PILOT_READY=FAIL（NO）。当前可直接启动正式PPO Pilot的episode=0、seed=0；本轮已STOP，不自动启动后续运行。

唯一建议下一步：针对“19.030s固定执行回归”与“native-event两fraction动作+原10s/phase、30s/task终止器”的合同不一致，制定并冻结一个可检验的执行修复规范；保持19.030要求、任务和物理约束，明确失败动作的终止/评价，再用新环境版本闭合G4与执行门。若实现需改变RL动作含义，应显式登记并重新验证，不能删除失败回归或继承旧标签。HOLD/安全的自然证据与TEST_ONLY范围需要在同一资格规范中明确，不能靠制造超限来补证。

门全部通过后，先1个训练seed20261021、最多32个native-event rollout decisions的最小PPO smoke，直接计数optimizer.step，保存policy/Adam/RNG/进度，在新进程恢复并再做有限update，冻结checkpoint做有限完整评价。未完成这些之前正式Pilot仍为0。本建议不授权自动执行。

在未来smoke/resume通过后，当前CCX33首个有限Pilot建议1个seed、最多32个训练episode，另4个冻结policy完整评价episode；保持当前已实现的单物理环境。单环境完整任务本轮内部host wall约77–82s，外守护maximal两次156.76s。36个完整任务约46–49分钟纯物理量级，另留PPO、checkpoint与审计余量，估计60–75分钟，硬cap90分钟。PPO开销未实测，该预算是规划估算；partial长度与动作频率会改变吞吐。不要按50ms决策换算，不建议未经资格验证直接双环境PPO。原双环境1.93倍只是历史评价吞吐，本轮未复测。

不升级/购买云资源，不自动开展百万步训练，不接触正式B/H150。后续若要多seed科学结论，应另行冻结预算与held-out划分；当前1seed smoke/Pilot不支持泛化或已学会任务声明。
