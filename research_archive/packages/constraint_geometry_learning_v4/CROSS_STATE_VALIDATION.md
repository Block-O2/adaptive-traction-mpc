# 独立冻结跨状态验证

两个新prefix在打开任何其物理结果前冻结，配置SHA见analysis/LOCKED_VALIDATION_FREEZE.json；没有依据验证结果选择候选或调参。新条件通过真实冷commissioning+合法prefix构造完整父状态，不用q/dq重建plant。Human仍是同一个nominal commissioned设定，没有跨患者参数研究或真实Trial1→Trial2→Trial3。

## VAL_A

前缀：`{"OUTBOUND": [[0.09, 0.03, 0.025]], "RETURN": [[0.03, 0.025, 0.025]]}`。

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|VAL_A_SAFE_P|PASS|1399.148996918|108.346914529|0|-0.068270|319.492/675.152|
|VAL_A_BEST|PASS|1397.322186581|108.228536474|0|-0.067804|320.182/677.712|
|VAL_A_H150|PASS|1401.937344181|107.333537049|0|-0.068520|319.307/675.748|
|VAL_A_SAFE_M|PASS|1399.148267242|108.346991815|0|-0.068270|319.493/675.152|
|VAL_A_B|PASS|1435.598143972|101.574666997|0|-0.067213|305.319/713.569|
|VAL_A_C19|PASS|1399.148632081|108.346953172|0|-0.068270|319.492/675.152|

VAL_A_SAFE_P 相对此条件B的JF变化=-36.449147054 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_A_BEST 相对此条件B的JF变化=-38.275957391 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_A_H150 相对此条件B的JF变化=-33.660799791 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_A_SAFE_M 相对此条件B的JF变化=-36.449876730 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_A_C19 相对此条件B的JF变化=-36.449511891 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_A_SAFE_P：域外模型正式ABSTAIN；冻结naive transfer预报motion=PASS，实际=PASS。外推测试不赋予在线决策权限。

VAL_A_SAFE_M：域外模型正式ABSTAIN；冻结naive transfer预报motion=PASS，实际=PASS。外推测试不赋予在线决策权限。

VAL_A_C19：域外模型正式ABSTAIN；冻结naive transfer预报motion=FAIL，实际=PASS。外推测试不赋予在线决策权限。

## VAL_B

前缀：`{"OUTBOUND": [[0.06, 0.055, 0.035]], "RETURN": [[0.025, 0.04, 0.015]]}`。

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|VAL_B_C19|PASS|1400.053112154|107.926919414|0|-0.068199|319.339/676.754|
|VAL_B_BEST|PASS|1398.242876769|107.812194417|0|-0.067735|320.185/679.335|
|VAL_B_B|PASS|1436.915562231|101.164615115|0|-0.067117|305.185/713.127|

VAL_B_C19 相对此条件B的JF变化=-36.862450077 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_B_BEST 相对此条件B的JF变化=-38.672685462 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_B_C19：域外模型正式ABSTAIN；冻结naive transfer预报motion=FAIL，实际=PASS。外推测试不赋予在线决策权限。

## VAL_C

前缀：`{"OUTBOUND": [[0.075, 0.045, 0.02]], "RETURN": [[0.035, 0.015, 0.03]]}`。

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|VAL_C_B|PASS|1436.181353806|101.432232824|0|-0.067168|305.338/713.537|
|VAL_C_BEST_CONTROL|PASS|1397.622206032|108.068073342|0|-0.067777|320.262/678.493|
|VAL_C_BEST_OLD_DURATION|PASS|1396.982792519|108.734995310|0|-0.067777|321.011/678.629|

VAL_C_BEST_CONTROL 相对此条件B的JF变化=-38.559147774 N·s；完整原门=PASS，未通过者不列正式收益。

VAL_C_BEST_OLD_DURATION 相对此条件B的JF变化=-39.198561287 N·s；完整原门=PASS，未通过者不列正式收益。

结论只适用于已列合法prefix；有限无违规运行不是全局安全保证。未改变controller边界之外的Human参数，未做临床/硬件或host实时验证。冻结state结果与同父局部预测准确率不能合并成患者泛化准确率。


## 全部受保护partial（不排名）

- FACT_BEST_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62540；partial JF=1266.183076411996 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_BEST_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62920；partial JF=1274.327668919538 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62840；partial JF=1273.1658746470823 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62660；partial JF=1270.9221378564696 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
