# 当前控制权限与密度审计

结论：有效密度先受“每个原生请求选择一个目标与通过速度→单段quintic及全路径证书→端点触发下一请求”约束。数学插点本身不是主要障碍。SOURCE_CONFIRMED / TRACE_VERIFIED。

源码前缀：`source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/`。1376/1376个历史源码/模型/权重文件SHA256核验通过后复制，改动仅为本包路径迁移。实际import闭包见audit/IMPORT_PREFLIGHT。主HEAD为8bb04662b1578b72c097f546be9e836167e280e8；不能认为干净HEAD自带全部runtime。

|问题|回答与源码证据|置信|
|---|---|---|
|1 下一对waypoint|反馈MPC对估计状态加二维action，原池排序；native residual在名义目标progress处采反对称delta再评价。human_waypoint_feedback_mpc.py:214–238,258–291,407–427；full3d_adaptive_integration_v1/coordination_residual_v2.py:17–41。|高|
|2 步长与方向|span×.20×scale×direction；scale=(.5,1)，五方向(1,.5),(1,.75),(1,1),(.75,1),(.5,1)，临近目标截断和去重；终末策略另处理。feedback_mpc.py:35–43,224–237。|高|
|3 候选与执行|通常评价10个初始候选，只选一个计划；端点截断/terminal/residual会改变计数。本B的14次candidate_count=[10, 10, 10, 10, 10, 1, 1, 1, 10, 10, 10, 10, 10, 2]。18D=[11, 11, 11, 11, 9, 1, 1, 1, 11, 12, 12, 11, 10, 1]。|高，TRACE_VERIFIED|
|4 重规划触发|phase start、旧schedule endpoint，非零通过速度端点处prefetch。原40ms继续桥支持等待，不是每5ms调用planner。runtime_coordination_residual_v2.py:3184–3234。|高|
|5 完整任务request|B/18D各14次TASK、20次全session；强低力失败代表有16次TASK，不是固定永远14。事件与phase见DIAGNOSTIC_RESULTS。|高|
|6 接受/激活/生效|本配对各14个ACTIVATED、14个边界C2记录、10个实际SPLICED。逐native行连接positive-step receipt，力矩一致且steps闭合；proposal-only未当执行。|高|
|7 独立可调项|正式native residual只改目标上的反对称progress delta；scheduler控制内部q/dq/ddq。10D/18D隔离研究额外改共同/差分目标与通过速度，仍只在旧请求处形成单段quintic。任意内部状态不在正式B权限内。|高|
|8 速度/加速度/时间|通过速度取限速/1.875、制动距离、剩余量限制的最小值；终点/HOLD为0。feedback_mpc.py:184–212。duration在reference网格上取可行值，解析运动极值、因果20ms窗口、ROM和clearance均检查。scheduler.py:218–246,459–565。|高|
|9 C2保证|记录边界q/dq/ddq连续到原1e-10检查精度；不保证jerk、恒速或真实Human C2。rolling_suffix_splice.py:21–30；runtime:3008–3016。|高|
|10 端点a约定|原_quintic_coefficients的c2=0、末端二阶导RHS=0。scheduler.py:180–205。插入内部点后沿此约定重建一般会改变原曲线。|高，MATH_VERIFIED|
|11 K3与slots|K3是一次graph的三个参数结点；native residual.py:21–27在一次名义m处np.interp只产生一个delta。每phase五个研究slots是干预请求索引，不是K3点各执行一次。code/interfaces.py:5–7,19–22。|高|
|12 不加planner频率能否加点|数学与普通pickle可表达。当前scheduler/admission/clearance没有任意多段路径资格。原RollingSuffixCompositeSchedule确可拼接已认证旧桥+单段suffix，但不授权任意新样条。rolling_suffix_splice.py:15–63；online_planning.py:29–49。|高；扩展可行性INFERRED|
|13 密度瓶颈|具体阻塞为coefficients==(2,6)及绑定该多项式的全路径证书，之后还有通过状态、endpoint触发、governor/current admission和实际动力学限制。不能把瓶颈只归数学表达。|高/中|

分母不能混用：candidate count通常10；waypoint count为14个已选段的目标（含重复HOLD目标）；新增trajectory control points属于数学参考。activated=14，actual suffix splices=10。每组整session共5817条receipt（其中5816条positive-step），116320个0.25ms步；TASK为3806个5ms成本区间、76120个native步、76121个真值边界样本。FAST带宽、planner频率与这些数量不同。

Human为被动hip/knee，robot六轴力矩经原cuff耦合，本包不向Human写状态或增加执行器。18D是隔离LEVEL1，不据此升级Native-B LEVEL2或host LEVEL3。
