# 存档候选参数与资格

全部为历史物理结果的本轮只读重算；本轮没有新增candidate。原始完整门、参数、逐关节/phase指标见JSON。

| candidate | J_F N·s | B−J_F N·s | TV_v/B | TV_a/B | jerk RMS/B | motion |
|---|---:|---:|---:|---:|---:|---|
| B0 | 1438.613498467 | +0.000000000 | 1.000000 | 1.000000 | 1.000000 | development PASS |
| 18D | 1400.697221153 | +37.916277314 | 0.894030 | 0.994565 | 0.995246 | development PASS |
| legacy002 | 1438.613737555 | -0.000239087 | 1.000069 | 0.999770 | 0.999964 | development PASS |
| legacy005 | 1438.612052286 | +0.001446181 | 1.000306 | 1.035347 | 1.126434 | FAIL |
| legacy005_repeat | 1438.612052286 | +0.001446181 | 1.000306 | 1.035347 | 1.126434 | FAIL |
| D1_knee_pos | 1438.613436156 | +0.000062311 | 1.000178 | 0.999970 | 1.000000 | development PASS |
| D1_knee_neg | 1438.613557388 | -0.000058921 | 0.999825 | 1.000032 | 1.000002 | development PASS |
| D1_hip_pos | 1438.613555366 | -0.000056899 | 1.000048 | 1.000031 | 1.000005 | development PASS |
| D1_hip_neg | 1438.613426120 | +0.000072347 | 0.999957 | 0.999975 | 0.999997 | development PASS |
| D1_coupled | 1438.613609029 | -0.000110561 | 0.999873 | 1.000064 | 1.000007 | development PASS |
| D1_coupled_inverse | 1438.613358554 | +0.000139914 | 1.000136 | 0.999946 | 0.999997 | development PASS |
| D2_knee_uniform | 1438.616075919 | -0.002577451 | 1.000218 | 1.000192 | 1.000017 | development PASS |
| D2_knee_alternating | 1438.620799334 | -0.007300866 | 1.000631 | 1.000477 | 1.000131 | development PASS |
| D3_knee_uniform | 1438.620598050 | -0.007099583 | 1.000183 | 1.000334 | 1.000005 | development PASS |
| D3_knee_alternating | 1438.620138600 | -0.006640132 | 1.000131 | 1.000985 | 1.000133 | development PASS |
| adaptive_D2 | 1438.618970175 | -0.005471707 | 0.999915 | 1.000180 | 0.999905 | development PASS |
| S_fixed_knots_early | 1438.613541287 | -0.000042820 | 1.000125 | 1.000027 | 1.000002 | development PASS |
| S_fixed_knots_late | 1438.613438256 | +0.000060211 | 0.999878 | 0.999976 | 0.999998 | development PASS |
| PS_early | 1438.613623026 | -0.000124558 | 0.999999 | 1.000094 | 1.000010 | development PASS |
| selected_repeat | 1438.613358554 | +0.000139914 | 1.000136 | 0.999946 | 0.999997 | development PASS |

最新19个arm：task/safety/receipt均为存档scientific-mode PASS；motion 17 PASS、2 FAIL。18D另为historical development PASS，旧合法prefix motion 0/4保持。Host plan_age失败不升级。
D1/D2/D3、adaptive及S_PROXY的精确fraction、每点hip/knee角度、时间fraction见CANDIDATE_PARAMETERS_AND_QUALIFICATION.json；18D18参数与冻结候选完整复制，未重新选择。
正负force差、force RMS和全部motion指标要联合审阅；低于B的极小数字不能单独当作新的有效改善。
