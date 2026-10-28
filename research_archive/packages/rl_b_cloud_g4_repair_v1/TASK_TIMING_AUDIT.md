# TASK时序审计

| 输入 | OUTBOUND | HOLD | RETURN | TASK总和 | native整episode |
|---|---:|---:|---:|---:|---:|
| maximal | 9.005s | 1.020s | 9.005s | 19.030s | 29.080s |
| uniform random | 9.260s | 1.020s | 9.885s | 20.165s | 30.215s |

两者TASK native起点均约10.050s；之前是commissioning/recovery。20.165s不是host wall time，也不含准备/结束阶段。random单episode内部host wall为82.074s，外guard84.160s；不得与TASK仿真时间混用。完整原始phase开始/结束和source/commit在 `audit/TASK_TIMING_RAW_EVIDENCE.json`。

random共30次native RL decisions，25次ACTIVATED、5次FAILED；其中4次candidate会使已发reference回退，1次目标进入既有shank-table几何。均走原certificate/admission/fallback，未直接执行被拒动作。maximal为14次、13次激活、1次几何失败。random的5段fallback commit→fresh resume共1.310s，maximal1段0.255s。这个差1.055s不能直接等同于因果贡献：不同动作改变了其余运动与settling，未做反事实消融。可直接精确归属的phase差为OUTBOUND+0.255s、RETURN+0.880s。

原governor实际存在于TASK receipt.reference_progress：maximal3801条、random4024条commit；两者附加delay合计0，delayed intervals均0。因此本例不是governor减速造成。顶层reference_governor_records为空，不能据此误判governor未执行；证据使用实际receipt。科学source→activation native age约5ms；host activation_age_ms分别约24–38ms和25–68ms，含不同host调度成本，不能互相替代。均未触发100ms过期。

最终scientific commit记录：maximal actual_return_elapsed9.005s、TASK19.030s；random分别9.885s、20.165s；原期限10s与30s，reason=None。没有等待timeout才宣布success。封存verify_physics.py额外要求完整任务duration19.030±0.050s，random仍FAIL；该检查未改。

原19.030回归合同保持且未通过。源码运行参数实际为30s/task，不能声称19.030已经是runtime hard deadline。缩短任务、提高速度、改动作fraction、把允许时间改20.165，或仅删除random回归，都会改变现有科学问题，均未实施。该不一致是正式PPO启动阻塞，success reward不能被当成19.030回归通过。
