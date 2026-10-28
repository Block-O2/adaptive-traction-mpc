# G4终止与reward

整体G4_PASS=FAIL；协议/数学检查PASS，必要自然物理失败覆盖仍NOT_EVALUABLE。沿用上一轮qualify.py要求完整real failure matrix的门，不能把注入检查换成自然证据。

| 路径 | 自然物理 | 明确标记TEST_ONLY | 直接证据 |
|---|---|---|---|
| A_normal_complete | PASS | — | runs/repair_reset_maximal_01/physics, episodes1 and2 |
| B_OUTBOUND_timeout | NOT_EVALUABLE | PASS | runs/repair_outbound_TEST_ONLY_01/physics |
| C_HOLD_not_established | NOT_EVALUABLE | PASS | REPAIR_BOUNDARY_TESTS.json + G4_UNIT_RESULTS.json |
| D_RETURN_timeout | NOT_EVALUABLE | PASS | runs/repair_return_TEST_ONLY_01/physics |
| E_zero_progress_stagnation | PASS | — | runs/repair_hold_01/physics and runs/repair_slow_01/physics |
| F_consecutive_rejections | PASS | — | slow final two native request outcomes FAILED, then original NO_FEASIBLE terminal |
| G_absolute_safety_stop | NOT_EVALUABLE | PASS | SAFETY_AUTHORITY_TESTS.json + runs/repair_safety_TEST_ONLY_01/physics/INJECTION.json |
| H_legal_fallback | PASS | — | maximal one and random five committed brake/hold/fresh-resume cycles; raw receipts/certificates audited |
| I_partial_rewards | PASS | — | all6 partial episodes (3 natural,3 TEST_ONLY) independently reconstructed, total progress0, completion-10, nonpositive force/variation costs |
| J_reset_independence | PASS | — | runs/repair_reset_maximal_01/physics/RESULT.json all4 reset_checks true; per-episode reset and owner_close files |
| global_timeout | NOT_EVALUABLE | PASS | REPAIR_BOUNDARY_TESTS.json + G4_UNIT_RESULTS.json |

OUTBOUND/HOLD/RETURN的已超过10s handoff反例已修复并重测；安全优先、global30s及吸收态/finite-horizon terminated=True,truncated=False均有TEST_ONLY检查。正常成功和自然早停均通过真实step接口；所有终端只在最后transition置terminated，后续step拒绝重复完成/bonus。

自然失败：zero-action在0.005s被原reference-regression规则拒绝；slow在9.820s因无可行schedule终止；RETURN zero在10.220s因reference regression终止。slow最后两次planner请求连续FAILED；不是伪造新的REPEATED_REJECTION原生原因。20次拒绝是单独的计数/fallback unit，不能扩展为自然物理压力结论。

本轮TEST_ONLY真实MuJoCo：phase-exit suppression使OUTBOUND在10.000s TIMEOUT_OUTBOUND、RETURN在TASK20.025s TIMEOUT_RETURN。安全测试只将monitor的一个有效20ms acceleration字段设为原限值1.01倍，原authority于1.010s触发TASK_ACCELERATION_LIMIT。原threshold、plant与actor数据未改；这个成功终止测试不是自然超限或新的物理安全证明。

HOLD不成立：原action generator在HOLD忽略actor action，只返回既定hold目标。无授权外部扰动；9个有界episode未观察到自然HOLD失败，不能声称对全部可能HOLD入口已证明不可达。独立sensor-clock输入使dwell不成立并于原10s超时，duplicate timestamp不增加dwell。上一轮HOLD exit suppression真实物理先在18.700s触发NO_FEASIBLE，不能标作TIMEOUT_HOLD。

global30s：三段各10s且无不计时中间阶段，原phase bound通常先于或同时约束global bound；修复后不能通过晚到phase交接逃过它。该结构不能提供独立的早发global超时自然case，边界浮点并发情况仍单独保留TEST_ONLY，不伪造自然失败。

每个partial累计progress回到0、completion=-10，force与variation是非正成本；不存在少动/停住拿成功奖。所有9个raw reward、force和terminal独立重算通过。reset真实双episode检查四项均PASS。自然超时/HOLD/绝对安全的可达性仍未完整闭合；这是资格范围限制，不能通过测试名称或注入结果消除。
