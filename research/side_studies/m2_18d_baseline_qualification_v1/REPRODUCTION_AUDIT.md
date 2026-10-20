# 本轮复现审计

结果PASS，证据为本轮新PHYSICAL_LEVEL1 scientific simulation，不是历史报告替代。B=1438.613498467487，原冻结18D=1400.697221153146 N·s，降力2.635612508%。两者完整task、motion/fairness、原绝对安全和scientific receipt/ownership均PASS。

完整TASK时长B/18D=19.030000000/19.030000000 s；phase clock时长均为OUTBOUND 9.005、HOLD 1.020、RETURN 9.005 s。合同HOLD dwell仍为原0.5s，实际phase时长不是另改的dwell。

|phase|B N·s|18D N·s|
|---|---:|---:|
|OUTBOUND|725.825779277982|707.100519987531|
|HOLD|54.394338793209|54.394332783500|
|RETURN|658.393380396297|639.202368382115|

所有历史trace字段精确一致；每对116320 native行和5817 receipts的物理/参考/来源字段精确一致。wall profiling/host timestamps不是scientific物理同一性字段。父/两个完整live fork保存restored hash，父在每臂后不变；父继续完成原B且与B子臂相同。无Human qpos/qvel直接设定或真实状态回放。

独立重算见audit/INDEPENDENT_reproduction.json：从本轮trace重算原5ms左积分和phase精确裁剪；从原native qpos/qvel重建Human映射、速度、raw acceleration/jerk、tracking，并逐native步核对实际torque与唯一正步receipt。该脚本不导入plant/controller/runner/optimizer，是独立计算路径，不冒称独立人员或agent审核。

执行源码来自retrospective，历史原1376项CODE_MANIFEST均已核对原件。物理前实际执行闭包按EXECUTION_CODE_MANIFEST冻结；复制执行源码只改根路径，原模型/配置、执行规则和阈值不改。最终归档检查另发现4份未随初始目录复制的native支持源码/构建产物；全部physics结束后按原SHA补齐，见FINAL_SOURCE_CLOSURE_MANIFEST和audit/CLOSEOUT_INITIAL_FAILURE_AND_REPAIR。它们没有回填进物理前manifest，不冒称物理前已完整复制全部历史支持文件。原执行路径/全部trace精确复现的结论保留，未在补齐后新增physics。首次包装缺少动作合同在START前失败，日志及修复留audit/prestart_launch1与ENGINEERING_EVENTS。开发B/18D结果未因验证修改。

原host scorer的plan_age/strict/R2/FAST资格不由scientific模式PASS覆盖：HOST_EXECUTION_CAUSAL_VALID仍NOT_EVALUABLE；原raw scorer的plan_age失败照存。完整issued reference见source/results/*/native_reference.npz及trace；applied commands/ownership/source/current admission见runtime_artifacts.json.gz、summary、reports/*EXECUTED_RESIDUAL_RECEIPTS。ROM/torque/contact/clearance及原绝对安全各项见MEASURED.native_physical_audit。参数身份、source/config/raw哈希见各manifest。
