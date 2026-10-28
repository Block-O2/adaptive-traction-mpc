# 协调权限对齐：固定坐标2×2因子

L=逐关节终点锁；D=新时长编译。L0不锁单独已到内部终点的关节，L1锁；整向量终点/HOLD规则始终保留。D0对修改后目标重算原scheduler minimum，按旧固定H150 RETURN槽1/4/5因子1.1/1.2/1.5编译，忽略新增局部time意图；D1使用ceil(max(parent duration,new minimum)×local factor/5ms)×5ms。x、legacy、原guard和物理均固定，不能同时改变它们再归因。

零物理相同请求映射见analysis/PERMISSION_FACTOR_MAPPING.json：时长D差异和endpoint L差异分别可见。最早的scheduler-only映射误将内部终点用作注册goal而被拒，修正为注册goal后重算，旧失败日志保留；不是物理失败或放宽阈值。

## BEST 固定协调意图

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|FACT_BEST_L1_D0|PASS|1397.383797171|108.639142795|0|-0.067785|320.938/678.520|
|FACT_BEST_L1_D1|PASS|1398.034615470|107.971017015|0|-0.067785|320.151/678.366|

FACT_BEST_L1_D0 相对原同意图最大native q差=1.586/1.709°，q/dq逐项相同=False。

FACT_BEST_L1_D1 相对原同意图最大native q差=0.000/0.000°，q/dq逐项相同=True。

## C19 固定协调意图

|身份|原motion|JF N·s|JM Nm·s|跨模板数|最小模型曲率 m/s²|native jerk RMS 髋/膝 °/s³|
|---|---|---:|---:|---:|---:|---|
|FACT_C19_L1_D0|PASS|1398.459431854|108.101119275|0|-0.068245|319.996/674.902|
|FACT_C19_L1_D1|FAIL|1399.857062420|108.090020580|1|-1432.356195|885.967/1955.251|

FACT_C19_L1_D0 相对原同意图最大native q差=0.918/0.708°，q/dq逐项相同=False。

FACT_C19_L1_D1 相对原同意图最大native q差=0.000/0.000°，q/dq逐项相同=True。


FACT_BEST_L0_D0：TASK_FAIL/PARTIAL，62540新增native步；原中止=NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT。全任务JF/JM不排名，原硬安全项={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。

FACT_BEST_L0_D1：TASK_FAIL/PARTIAL，62920新增native步；原中止=NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT。全任务JF/JM不排名，原硬安全项={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。

FACT_C19_L0_D0：TASK_FAIL/PARTIAL，62840新增native步；原中止=NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT。全任务JF/JM不排名，原硬安全项={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。

FACT_C19_L0_D1：TASK_FAIL/PARTIAL，62660新增native步；原中止=NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT。全任务JF/JM不排名，原硬安全项={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
以上能识别两个compiler因素及其guard模式相互作用。L1D1是原新表示控制组；完整trace/native/receipt重现另行审计。D0恢复旧时长语义，但整个factor8仍使用modal目标提议，并没有恢复旧18D归一化目标域，因此L0D0不能冒称完整旧18D。旧18D与新8D非双向全族坐标变换；共同运动子族需逐请求target/pass/duration/certificate一致，x=0回到共同H150。尚未运行匹配完整权限后的旧18D/新坐标等预算优化，效率和性能创新均NOT_ESTABLISHED。


## 全部受保护partial（不排名）

- FACT_BEST_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62540；partial JF=1266.183076411996 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_BEST_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62920；partial JF=1274.327668919538 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D0：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62840；partial JF=1273.1658746470823 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
- FACT_C19_L0_D1：NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT；新增native=62660；partial JF=1270.9221378564696 N·s，仅作已消耗成本记录；完整任务费用不排名。硬安全={'force': True, 'moment': True, 'torque': True, 'human_speed': True, 'human_acceleration': True, 'robot_speed': True, 'session_clearance': True, 'true_clearance': True, 'measured_sleeve_clearance': True, 'no_shank_table_contact': True, 'no_human_rom_violation': True}。
