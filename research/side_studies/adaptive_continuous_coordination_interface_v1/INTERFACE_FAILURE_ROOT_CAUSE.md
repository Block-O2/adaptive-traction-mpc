# 原失败位置复现与根因

本轮先核对真实源码和反例，再实施隔离扩展。历史事实仍标为上一轮：28段数学等价、约.005299rad局部变化、支撑外6.11e-16rad、严格折回旧reference的完整复现。本轮tests/test_certification重新验证旧schema对4×2×6拒绝，并独立检查28段的每个实际子多项式，不仅检查canonical零修改快捷采样结果。

源码前缀：`source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/`。旧单段与旧activation/fallback原文件分别保存在audit/original_source，改动diff保留；原始来源/新副本SHA见CODE_MANIFEST。

|环节|原机制及准确限制|证据|
|---|---|---|
|A 单段载荷|QuinticHumanWaypointSchedule固定2×6；边界构造c2=0、末端a=0|human_waypoint_scheduler.py:81–119,180–205|
|B 多段载荷|多条各2×6，加严格时间分区及C2；整体不能直接传原constructor|原型与old_schema_still_rejects_4x2x6测试|
|C 路径证书绑定|原certificate与具体coefficients/单一duration及geometry签名绑定；重建原边界系数才复用|原activation_validation.py:119–141|
|D 拒绝位置|原__post_init__在shape不是(2,6)时ValueError|scheduler.py:112–115；本轮旧负测试PASS|
|E 时间与governor|governor对active_schedule.sample(progress)取样，用整条receipt-owned20ms历史框约束，不是每子段重置|receipt_reference_governor.py:9–30,42–73|
|F current admission|原模型mechanics、reference continuity、当前phase/剩余时间，future handoff还核对实际状态/运动/shifted ROM/continuous clearance/原source与revalidation age/版本/goal|原activation_validation.py:144–277|
|G FAST消费|runtime在governor选样后，以同一q/dq构造执行candidate，经原_execute_interval进入原反馈/allocator/robot torque|runtime_coordination_residual_v2.py:3433–3444,3534,3578–3593|
|H rolling composite|已有prefix_start、splice_elapsed、suffix局部时间、q/dq/ddq边界校验；可复用generic sample|rolling_suffix_splice.py:15–63|
|I 重新准入/splice|原validate_rolling_composite重验旧桥prefix及suffix；actual splice还再验suffix并受apply guard保护|原activation_validation.py:280–343；runtime:3455–3528|
|J future stop|原safe_fallback先生成40ms恒速桥与原制动轨迹，选原5ms节点commit，carry/braking/HOLD不可由迟到计划逆转|原safe_fallback.py:35–93,96–123|

因此并非时间定位/泛型取样完全缺失，也不是pickle强制端点压缩。组合问题是：旧scheduler的固定单段载荷、全路径certificate与shifted-path计算、准备escape时的单段类型复制。原rolling机制只认证“旧桥+一个已认证suffix”；不自行给任意多段suffix增加资格。

本轮选择新多段suffix对象、复用原rolling外壳。改动两处隔离分支：safe_fallback在完整原准备完成后包装；activation_validation保留原body，并为新类型增加整路径重验及逐段shifted路径处理。未改rolling/time/governor/FAST/allocator/plant。

分类：SOURCE_CONFIRMED、MATH_VERIFIED；tests中的拒绝PASS不代表物理成功。运行结果另见PHYSICAL_VALIDATION。
