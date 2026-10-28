# 独立归档审查与修复记录

审查角色 `evidence_audit` 对实际控制/任务/scorer与冻结配置抽查30项；未发现科学参数被放宽。主文档区分局部最优、估计/native真值、科学仿真/真机，以及Learning训练/完整物理资格。以下为独立审查发现及主Agent修复记录；主Agent复验不冒称由独立审查者再次执行。最终远端克隆结果见顶层 ARCHIVE_VERIFICATION.md。

|严重度|发现|归档修复与验证范围|
|---|---|---|
|高|D01R launcher曾无条件PASS；原Campaign允许完整但motion不合格的row继续|最终只接受恰有B/H150两行、complete_task及all_original_qualifications均为True；失败保留真实row和非零退出。完整远端实际运行另记|
|高|两条v7代表raw缺原output与最终MEASURED/ownership/attempt输入|evidence_selection明确122项，含每ID全部6份output和MEASURED、EXECUTED_RESIDUAL_RECEIPTS、attempt RESULT。主Agent本地完整原scorer/ownership/motion/native重放PASS；远端另记|
|中|Python优化模式会移除assert资格门|三个动态launcher明确拒绝python -O/PYTHONOPTIMIZE；原资格assert保留。不是通过关闭门获得复现|
|中|EARLYH01标签曾误写heavy-soft|改为原case high_rom_matrix_heavy_stiff_sync_v1.json，数值与原研究包不变|
|公开资料|旧Git里含PRIVATE工作树状态和非必需用户原文|新树排除；未改写旧公开历史，因此不能撤回既有公开副本。原包未删除。排除清单单列|
|扫描误报|旧public exporter内含标准PRIVATE KEY header字符串|AST/原文核实是检测用字面量，无私钥payload；仅对该源码精确SHA做误报审阅，文件变化即不获豁免|

另有主Agent机械复现发现：生成manifest曾把随后覆盖的自身文件纳入hash，导致物理开始前失败，已排除两个生成manifest文件；失败日志与原因保留在最终核验说明。该修复不改变科学设置。

原v7_metrics_v3的额外quality终验由主Agent接入新组合launcher：原冻结jerk RMS≤1.001、force norm-rate RMS≤1.004，并要求JF/JM对phase不劣。原plant/controller/task/motion/safety不变，不重新拟合任何模型。

历史physical audit是被身份核对后的输入；离线重放不能称为新的动力学安全验证。完整Task的重新运行才是本轮新动力学复现，且仍是MuJoCo科学仿真，host/硬件/临床范围未晋级。
