# iHEAR Lab — 18D + Waypoint smoothing overnight v1

本轮完成历史机制复核、原B/18D精确物理复现、零形状等价、四组有界干预及条件分支复核。没有达到预先冻结的“明确完整降力或保留18D力收益同时改善完整运动”晋级条件，因此PRIMARY/SECONDARY均为null，新合法prefix验证未触发。新18D+S完整合格数值最低为 `development1_E_O_smooth`：J_F=1400.680808123 N·s，相对匹配18D变化-0.016413030 N·s，完整velocity TV变化-0.2571%。这是描述性最小值，不是冻结PRIMARY。

## 历史机制与组合接口

18D原始J_F=1400.697221153 N·s，B=1438.613498467 N·s，差37.916277314 N·s（2.635613%）。本轮两者从相同完整live父状态重新执行，全部trace字段与历史一致。原18参数、RETURN两个差分plateau、scheduler/bridge/current admission/receipt保留。零shape在B与18D均通过116320 native行、5817 receipts及完整trace等价，组合接口合法性在本开发条件有实证。

18D不是单一平滑机制：4–6 s和15–16 s合计贡献约53%的降力，但部分局部TV_a/jerk反而增加；全程moment也增加约7.03%。更早抬髋、降膝与模型重力/弹性需求变化一致，allocator通道变化有执行分量证据。不能把代数分解当独立物理因果中介比例。详见HISTORICAL_18D_MECHANISM、HISTORICAL_WINDOWS和原始来源hash。

## 完整结果

Δ以同一批次、同完整父状态的对应base（B或18D）为准；不同base的平滑形状分别按reference velocity TV设计，不是相同固定处理的纯2×2交互。support不同不做峰值对齐。force为原5ms采样左积分；0.25ms native只用于实际motion及ownership。所有phase和task均完整保存；partial不排名。

|arm|完整 J_F N·s|相对匹配base ΔJ_F|support TV_v Δ%|完整TV_v Δ%|完整jerk RMS Δ%|原motion|
|---|---:|---:|---:|---:|---:|---|
|development1_B0|1438.613498467|+0.000000000|—|+0.0000|+0.0000|PASS|
|development1_E0|1400.697221153|-0.000000000|—|+0.0000|+0.0000|PASS|
|development1_B_zero|1438.613498467|+0.000000000|+0.000 / +0.000|+0.0000|+0.0000|PASS|
|development1_B_O_smooth|1438.601171037|-0.012327431|-2.915|-0.2469|-0.0696|PASS|
|development1_B_O_opposite|1438.616679127|+0.003180660|+0.822|+0.0707|+0.0216|PASS|
|development1_B_R_smooth|1438.516382760|-0.097115707|-3.522|+0.0177|-0.0349|PASS|
|development1_B_R_opposite|1438.619539089|+0.006040621|+0.986|+0.0425|+0.0023|PASS|
|development1_E_zero|1400.697221153|-0.000000000|+0.000 / +0.000|+0.0000|+0.0000|PASS|
|development1_E_O_smooth|1400.680808123|-0.016413030|-3.698|-0.2571|-0.0603|PASS|
|development1_E_R_smooth|1400.713651794|+0.016430641|-4.415|-0.2031|-0.0496|PASS|
|development1_E_R_opposite|1400.693123654|-0.004097499|+1.269|+0.0661|+0.0225|PASS|
|development2_B0|1438.613498467|+0.000000000|—|+0.0000|+0.0000|PASS|
|development2_E0|1400.697221153|-0.000000000|—|+0.0000|+0.0000|PASS|
|development2_E_O_half|1400.688912224|-0.008308929|-1.985|-0.1399|-0.0339|PASS|
|development2_E_O_repeat|1400.680808123|-0.016413030|-3.698|-0.2571|-0.0603|PASS|
|development2_E_R_half|1400.705428518|+0.008207365|-2.340|-0.1137|-0.0329|PASS|
|development2_E_R_repeat|1400.713651794|+0.016430641|-4.415|-0.2031|-0.0496|PASS|
|development2_B_OR_smooth|1438.504055305|-0.109443162|-2.915 / -3.522|-0.2291|-0.1046|PASS|
|development2_E_OR_smooth|1400.697238764|+0.000017610|-3.698 / -4.415|-0.4602|-0.1099|PASS|

原task/safety/receipt结果、ROM、clearance、tracking、phase积分、moment、逐joint与combined TV_v/speed variation/TV_a/jerk、joint travel/excursion、torque分量及生命周期事件在ALL_ANALYZED_RESULTS、derived和原raw。velocity TV、speed variation、acceleration variation及jerk分别计算，不合并为临床舒适度。

## 科学判断

B+S复现了历史的小幅降力；18D+S的完整结果如表。局部reference与Human运动确实改变，但微小J_F下降不足以产生本轮新赢家。完整运动变化和下游响应必须一起评价，局部更平滑不保证完整更平滑。反向对照、被原速度证书拒绝的18D去程反向候选、所有motion失败和工程失败均保留。

本轮没有证明smoothness是独立原因，也没有证明18D与Waypoint存在明确可推广的互补收益。它也没有排除更广连续协调空间；结论只覆盖注册的两个窗口、固定内部dq/ddq、±0.05°位置偏移及有限条件分支。未进入RL/Q/Neural Q训练。

## 分母、边界与退出

T0=2026-10-17 02:12:56北京时间，实际截至本报告约0.87小时。8–10小时是目标；在有限研究方向没有新的晋级信号后提前结束，没有为空耗时长继续physics。硬截止13:12:56未触及。物理START=21/120、END=21；含冷父及全部fork。实际新增native步=1678920，继承前缀不重复计新步。30次验证预留未使用；新验证0对，历史18D合法prefix motion仍0/4。

仅PHYSICAL_LEVEL1 / same-Human development。正式Native LEVEL2、host-clock LEVEL3、硬实时、跨患者、真机与临床资格均未获得。原host/strict失败不被scientific模式PASS覆盖。

## 工程事件与保护

分析辅助函数保留旧包名，曾临时覆盖旧v3两份计划并写入四份新分析JSON；在任何physics前发现。两份旧计划从审阅镜像恢复，并与旧EXECUTION_CODE_MANIFEST的SHA逐字节一致；四份新文件移入本包。此事件明确保留于audit/ISOLATION_REPAIR，不声称全程零历史写入。正式B/plant/source语义未改变。另有控制台numpy布尔序列化、预检入口路径和模块名冲突的工程修复，均发生在physics前，不改变科学参数或门限。

源码闭包除了路径迁移保持语义一致；新增控制逻辑只在隔离control/campaign.py。原motion protocol字节一致。完整保护与退出复核见PACKAGE_VERIFICATION；它的PASS只代表审计合同，不代表科学假设成立。未commit/push/merge/reset/stash或删除历史失败。

## 图与复现

![历史共同时间轴](figures/18d_mechanism_timeline.png)

![B干预](figures/B_intervention_comparison.png)

![18D干预](figures/E_intervention_comparison.png)

canonical完整raw位于本WSL研究包source/results；Windows目录为审阅镜像，不伪称复制了全部raw。所有原始trace/native/receipt路径、identity、certificate、配置、START/END和代码hash均可追溯。见REPRODUCTION.md。下一步仅见NEXT_RESEARCH_DECISION，本轮STOP。

## 本轮关键反例、重复与组合

18D回程平滑support内ΔJ_F=-0.051323951 N·s，support外=+0.067754591，完整=+0.016430641。已存档的request时刻/执行标签变化数量=0；没有据此把抵消归为重规划时序改变。原纯allocator重算完整差=+0.007598878 N·s，实测差=+0.016430641；模型姿态需求、tracking、robot/contact响应仍共同参与，独立smoothness中介未识别。

两个batch的B/18D及18D去/回程smooth重复均比较了全部trace、116320 native行和5817 receipts，结果PASS。两批来自不同冷父进程，完整fork hash的跨批相等情况逐例保存；只声明同开发条件的确定性物理重复，不称相同父进程或新prefix验证。

|base|O+R完整ΔJ_F N·s|单独O/R差值之和|组合交互差|完整TV_v变化%|
|---|---:|---:|---:|---:|
|B|-0.109443162|-0.109443138|-0.000000024|-0.2291|
|E|+0.000017610|+0.000017610|+0.000000000|-0.4602|

交互差为ΔJ_OR−ΔJ_O−ΔJ_R，负值表示额外降力。它只描述本base的O/R组合；B与18D使用各自设计的S，不能将两者差异解释为相同处理的纯因果synergy。

![四组共同时间轴](figures/four_group_comparison.png)

![局部与下游累计变化](figures/downstream_cumulative_effects.png)
