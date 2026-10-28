# iHEAR Lab — RL-B G4 Closure & PPO Functional Readiness v1

本轮工程测试完成并STOP。PPO真实更新与跨进程恢复PASS；G4严格资格及冻结匹配评价仍FAIL，正式PPO Pilot不允许启动。报告时间2026-10-20T15:34:15.629721+08:00（Asia/Shanghai）。预计2–3小时是上限内建议，本轮证据足够后提前停止，未扩展实验。

|独立资格|结果|
|---|---|
| FORCE_INTEGRATION_PASS | PASS |
| RUNTIME_TASK_COMPLETE_PASS | PASS |
| MATCHED_TASK_EVALUATION_PASS | FAIL |
| G4_STRICT_PASS | FAIL |
| G4_TEST_HARNESS_COVERAGE | PASS |
| EXECUTION_PARITY_PASS | PASS |
| PPO_UPDATE_SMOKE_PASS | PASS |
| CHECKPOINT_RESUME_PASS | PASS |
| PPO_TASK_SUCCESS | FAIL |
| PPO_FULL_QUALIFIED | FAIL |
| TRAINING_PILOT_READY | FAIL |

1. **runtime COMPLETE与19.030s匹配资格**：前者要求原task状态机完整phase、有效HOLD和causal native RETURN commit，phase10s/TASK30s；后者还要求冻结匹配的task/safety/motion/causal资格，部署的必要回归是19.030±0.050s。二者独立，详见 TASK_QUALIFICATION_CONTRACT.md。配置原dwell0.5s、既有wrapper HOLD timing floor1s和观测HOLD1.020s分别保留，不混为一种合同。
2. **20.165s随机任务**：RUNTIME_TASK_COMPLETE=PASS，MATCHED_19_03_QUALIFIED=FAIL。9.260+1.020+9.885s均符合原runtime期限，总时长超出匹配窗口1.135s。原ZIP/部署包未包含正式B/H150完整历史匹配Master Contract，不能自行补写其充分条件；该部分审查NOT_EVALUABLE不掩盖已知时长FAIL。
3. **G4真实物理通过**：原正常完成、零进度/停滞拒绝、连续两次planner FAILED、planner失败、合法fallback、自然partial reward、terminated/truncated与真实双episode reset独立性。原9个episode本轮只读raw/phase力积分重新核对9/9通过；3个新PPO episode完整独立raw reward、force、实际Human motion和receipt ownership也通过。
4. **只有TEST_ONLY及缺失项**：phase/TASK timeout、HOLD不成立、绝对安全触发的自然证据仍NOT_EVALUABLE；原注入/单元链PASS，本轮41项协议/接口测试全部PASS。20次连续拒绝压力只有TEST_ONLY；自然观察只证明已有两次FAILED及其后原NO_FEASIBLE路径，绝不声称任意次数压力覆盖。详见 G4_STRICT_VALIDATION.md、G4_TEST_COVERAGE.json。
5. **G4是否闭合**：否，G4_STRICT_PASS=FAIL。保留原严格自然失败矩阵门，G4_TEST_HARNESS_COVERAGE=PASS不改变它。未绕过保护制造自然违规，也未把有限未观察证明成全状态不可达。
6. **PPO真实更新**：是。随机初始化CPU小网络，1seed、单环境、16个真实训练transition，2次PPO train/epoch、4次实际Adam梯度步；全部有限非零且权重改变。另38个完成episode的审计tail不进入优化器。无B/H150教师轨迹/模仿权重。
7. **跨进程恢复**：是。初始PID27443保存后退出；PID27885核对权重、完整Adam、三类RNG和8个训练状态字段后，从8→16训练steps、Adam2→4继续真实rollout和更新；第三PID28279再次载入并冻结评价。恢复是fresh physical episode，不声称MuJoCo中途连续恢复。SHA、计数语义与全部核对见 CHECKPOINT_RESUME_AUDIT.json。
8. **资源/吞吐**：3个新episode、78真实decisions、343520 native steps（TASK222920）；物理子进程总238.3s，约0.327decisions/s，平均79.4s/episode。最低可用RAM28.55GiB、单进程峰值RSS约959MiB；无OOM、资源超时或MuJoCo warning。单CPU affinity/单线程的工程预算足够，长期正式吞吐尚未验证。
9. **允许正式Pilot吗**：不允许。READINESS与train.py门禁逐字节保留，未写入新的正式PASS。PPO_UPDATE_SMOKE_PASS与CHECKPOINT_RESUME_PASS不授予G4或正式训练资格。
10. **当前Pilot episode/seed/时间预算**：0/0/0。没有开始正式训练。不会自动按million decisions扩大规模，也不会自动启动下一研究包。
11. **最少还缺什么**：自然timeout/HOLD失败/绝对安全触发三类严格G4证据或正式可达性审查闭合；原匹配合同来源和冻结执行回归闭合。冻结策略评价16.610s因原shank-table几何筛查拒绝candidate而ABORTED，0/1成功，PPO_TASK_SUCCESS和PPO_FULL_QUALIFIED均FAIL。首个训练episode成功不等于冻结策略学会任务。

本轮新物理仅3个episode，远低于12上限。所有物理进程3 START/3 END、episode3 START/3 END闭合，owned PID和native owner/executor均退出。保留原始失败、日志、transitions、native journal及两代checkpoint；计数/时钟记录的已知命名限制公开写入 ATTEMPT_ACCOUNTING.json 与 PPO_UPDATE_RESULTS.json，未冒充科学资格。

原ZIP、原部署与旧修复包共1749文件hash保护通过；源文件414份与上一隔离版本逐字节相同，原ZIP450个manifest载荷再校验通过。未改正式B/H150、Human/robot/cuff物理、安全限制、目标、HOLD或deadline，未更改action/scheduler/execution接口；只新增独立smoke入口、审计记录和报告，未重装环境。观察到的EXECUTION_PARITY_PASS是核心物理执行对照与新raw审计范围，完整冻结execution gate仍FAIL，host realtime NOT_EVALUABLE。

目录无Git checkout，branch/HEAD不可用；无stage/commit/push/merge/reset/stash/clean。全部新文件位于本隔离研究包，源码/输出manifest、保护hash与封存结果见 PACKAGE_VERIFICATION.json、SOURCE_MANIFEST.json、OUTPUT_MANIFEST.json。最终状态 STOPPED_QUALIFICATION_BLOCKED。唯一下一步见 NEXT_RESEARCH_DECISION.md。
