# iHEAR RL-B G4隔离修复与资格复核

完成隔离修复和9个真实MuJoCo episode，训练启动门仍未通过，已STOP。开始2026-10-20 14:47:23（Asia/Shanghai），报告生成2026-10-20T15:12:36.724515+08:00。未为了耗满预计2–3小时而扩展搜索。最后物理结束2026-10-20 15:01:28.734，之后只做独立重算、负向门和封存；4小时硬上限/最后30分钟物理启动禁区未触及。

| 独立资格 | 结果 |
|---|---|
| FORCE_INTEGRATION_PASS | PASS |
| G4_PASS | FAIL |
| EXECUTION_PASS | FAIL |
| PPO_UPDATE_PASS | NOT_RUN |
| CHECKPOINT_RESUME_PASS | NOT_RUN |
| TRAINING_PILOT_READY | FAIL |

TRAINING_PILOT_READY=FAIL即NO。G4协议测试PASS，但必要自然失败覆盖没有闭合；EXECUTION核心物理/接口对照PASS，但原random时长回归FAIL。没有正向PPO尝试。

1. **0.555109根因**：OUTBOUND TASK8.895s admission在apply前拒绝，trace预写的111.021810669N×5ms成本未清除；下一行同一native时间，正确dt=0。不是phase边界、terminal或reset。保留完整拒绝事件，按实际执行区间归属修复。
2. **summary与raw是否一致**：是。slow独立927.5259761342978、修复summary927.5259761342987N·s，差9.09e-13；9/9 episode force/reward独立审计PASS。另修复moment索引漏掉末区间0.040009019N·m·s。
3. **历史reward影响**：这项重复积分没有进入wrapper reward；slow force reward前后均-0.1855051952268596，总reward-10.187928954054334。历史PPO更新为0。summary消费者可能生成错误Learning标签；现有13条native Learning的force/state/完成字段不变，只有host apply时间戳变化，外部消费者未声称全部安全。
4. **random20.165s原因**：真实TASK，9.260+1.020+9.885s；比maximal多0.255s OUTBOUND和0.880s RETURN。30次提议、5次planner失败与合法fallback，而maximal14次/1次。receipt governor附加delay合计0；无timeout收尾或准备时间混入。不同progress提议/运动/settling与fallback共同造成时差，未用反事实实验虚报精确因果拆分。
5. **19.030合同**：保持，未放宽，但random未通过。实际原runtime为10s/phase、30s/task，故在20.165s仍可COMPLETE；不能把这个success当成19.030回归PASS，亦不能凭空声称原runtime存在19.030 hard deadline。
6. **G4真实路径**：正常成功、零进度/停滞拒绝、连续planner失败、合法fallback、partial reward和真实reset独立性通过。特定自然phase timeout、HOLD不成立和实际绝对安全失败仍NOT_EVALUABLE；OUTBOUND/RETURN timeout及安全终止的TEST_ONLY链路通过，绝不包装成自然证据。deadline晚到覆盖的代码缺口已修复，见反例。
7. **RL-B科学执行合同**：完整EXECUTION_PASS=FAIL；slow/maximal/random逐样本物理/命令parity PASS，全部9个core raw审计PASS。原19.030 random回归仍FAIL，host realtime NOT_EVALUABLE。
8. **真实PPO gradient update**：0；NOT_RUN。负向启动门正确拒绝，策略、optimizer、训练环境和checkpoint未创建，hash为null。
9. **跨进程checkpoint恢复**：NOT_RUN，不能给可靠性PASS。保存/恢复policy、Adam、RNG、进度与hash机制有静态代码，但未用随机权重代替训练恢复证明。
10. **下一轮可直接正式Pilot吗**：不能。G2/执行、G4失败，G6动态恢复未验证。先闭合执行合同与G4，再最小smoke/update/resume。
11. **CCX33预算建议**：当前正式Pilot0 episode/0 seed。未来全部门与smoke恢复通过后，建议单环境1seed、最多32训练+4冻结完整评价episode，估计60–75分钟、hard cap90分钟；本轮完整任务77–82s/episode，PPO开销尚未实测。不自动执行此建议。

| 运行 / episode | 类别 | 状态 | TASK s | RL decisions | native steps（含准备） | J_F N·s |
|---|---|---|---:|---:|---:|---:|
| repair_hold_01 / episode_0001 | 自然合法输入 | ABORTED | 0.005 | 1 | 40220 | 0.394471215 |
| repair_outbound_TEST_ONLY_01 / episode_0001 | TEST_ONLY | ABORTED | 10.000 | 6 | 80200 | 778.886923669 |
| repair_random_01 / episode_0001 | 自然合法输入 | COMPLETE | 20.165 | 30 | 120860 | 1616.695637115 |
| repair_reset_maximal_01 / episode_0001 | 自然合法输入 | COMPLETE | 19.030 | 14 | 116320 | 1449.840060953 |
| repair_reset_maximal_01 / episode_0002 | 自然合法输入 | COMPLETE | 19.030 | 14 | 116320 | 1449.840060953 |
| repair_return_TEST_ONLY_01 / episode_0001 | TEST_ONLY | ABORTED | 20.025 | 14 | 120300 | 1528.339205255 |
| repair_return_hold_01 / episode_0001 | 自然合法输入 | ABORTED | 10.220 | 11 | 81080 | 790.544754856 |
| repair_safety_TEST_ONLY_01 / episode_0001 | TEST_ONLY | ABORTED | 1.010 | 1 | 44240 | 91.403098847 |
| repair_slow_01 / episode_0001 | 自然合法输入 | ABORTED | 9.820 | 15 | 79480 | 927.525976134 |

共8个物理guard attempt、9个episode（6自然输入、3 TEST_ONLY），3 COMPLETE（其中random未过19.030回归）、6 partial。native 799020，TASK native 437220，RL decisions 106，gradient/optimizer updates均0。另有1个训练负向门和1个无物理的受控进程超时：合计10 START、10 END，全部闭合，owned进程和native executor均退出。所有异常/harness失败见audit/HARNESS_FAILURES.json；诊断命令未逐一记录独立wall时间，未伪造时间账。

最低可用RAM28.709GiB，高于6GiB；串行、峰值1物理环境，无观察到的OOM/MuJoCo warning或失控。未创建checkpoint；原ZIP与manifest、939份历史文件校验不变，ZIP450/450载荷重新核验，414 source中412不变、2个隔离修复有diff/hash。正式B/H150与原研究证据未覆盖。目录不是Git checkout，初始branch/HEAD不可用；没有stage/commit/push/merge/reset/stash/delete。

物理/任务参数与动作含义未变；仅事件成本归属、moment统计边界和超过原phase deadline的终止优先级发生修复。新版本已登记，不继承旧资格标签。所有本轮episode为development/smoke qualification，不是held-out鲁棒性或学习成功。唯一下一步见NEXT_RESEARCH_DECISION.md。

交付入口：ROOT_CAUSE_ANALYSIS.md、FORCE_INTEGRATION_REPAIR.md、G4_TERMINATION_REWARD_AUDIT.md、TASK_TIMING_AUDIT.md、RL_EXECUTION_PARITY_AUDIT.md、VALIDATION_RESULTS.json、PPO_SMOKE_RESULTS.json、CHECKPOINT_RESUME_AUDIT.json、ATTEMPT_ACCOUNTING.json、PACKAGE_VERIFICATION.json。最终状态STOPPED_QUALIFICATION_BLOCKED。
