from pathlib import Path
import json,hashlib,time
P=Path(__file__).resolve().parents[1];F=P/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1'
def write(n,x):(P/n).write_text(x,encoding='utf-8')
root='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
write('INTERFACE_FAILURE_ROOT_CAUSE.md',f'''# 原失败位置复现与根因

本轮先核对真实源码和反例，再实施隔离扩展。历史事实仍标为上一轮：28段数学等价、约.005299rad局部变化、支撑外6.11e-16rad、严格折回旧reference的完整复现。本轮tests/test_certification重新验证旧schema对4×2×6拒绝，并独立检查28段的每个实际子多项式，不仅检查canonical零修改快捷采样结果。

源码前缀：`{root}`。旧单段与旧activation/fallback原文件分别保存在audit/original_source，改动diff保留；原始来源/新副本SHA见CODE_MANIFEST。

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
''')
write('SELECTED_INTERFACE_DESIGN.md','''# 最小扩展路线选择

|路线|可复用部分|缺口与代价|
|---|---|---|
|A 递归扩展rolling composite|边界C2、前缀剩余时间、suffix激活/实际splice|任意多段嵌套后仍需完整ROM/极值/geometry/current admission/escape，且原prefix验证假定单段；盲目递归会扩大改动|
|B 版本化MultiSegmentReference|把多段suffix视为一个不可变认证对象，原rolling前缀与splicing不变|新增typed payload与全路径证书，两个原类型消费分支|
|C 逐点增加planner请求|可继续用原单段schema|改变调用频率和lifecycle；不符合本任务有效内部自由度目标|

选B并复用A的已有外壳。新增multisegment_reference.py；隔离副本safe_fallback.py保留完整原_prepare_single_decision，再按显式intent包装；activation_validation.py只为新类型分派全路径检查与shifted geometry，原旧类型分支保留。没有改正式B。总修改范围由最终manifest/diff给出。

只在第二个OUTBOUND请求（索引1）把选中原段分为四子段。零修改仍是新多段对象；仅对已证明每个子段都等于原多项式的情况，用原全局多项式求值避免浮点重参数化差。非零节点修改必须关闭此identity快路，且有负测试防止伪装；不把对象压回端点。

非零演示只改中间节点膝q +0.05°，其通过dq/ddq、外部q/dq/ddq、总duration和任务锚点保持。若motion失败，按事先顺序减为.02/.01°，只按资格决定，不按force选择。未增加planner频率。

所有启动由owned串行父进程控制；physics上限24 START，4小时后不再START；不搜索force、不训练网络。P0失败须先归因，不进入P1。P1/P2通过后仅一次同条件重复，不自动开始优化。
''')
write('MULTISEGMENT_REFERENCE_CONTRACT.md','''# MultiSegmentReference V1合同

对象字段为frozen dataclass、嵌套tuple/float/str；NumPy coefficients、candidate向量和certificate访问器都返回独立对象，外部写入不改变payload。pickle往返后相同值身份仍有效。普通object.__setattr__强行篡改不是不可实现的内存攻击，运行准入的digest核验会拒绝；完整性hash不是远端密码学身份认证。

reference_id覆盖：每段真实系数、duration及原metadata；全部knots；整体candidate label/phase/goal/目标q/dq；原曲线身份与canonical_zero模式；request ID、原source_sample_time/capture_ns、request model sequence/signature；任务ROM/起止锚点、原速度/加速度fraction后的限制、reference周期；tracking offset；冻结bridge/stop的系数、时间、candidate和原escape certificate。代码/模型/配置/权重hash还由START的EXECUTION_CODE_MANIFEST绑定。

certificate_id覆盖reference_id与完整path certificate JSON。certificate记录current model和geometry签名、实际解析极值、跨节点C2/20ms量、各段原continuous geometry下界、tracking-offset路径、整体+逐段原mechanics和future escape。实际激活会重新使用当前model/geometry检查，而非沿用旧曲线proof；当前证书ID也记录于应用receipt。

外部q/dq/ddq及duration不改变，内部允许非零通过dq/ddq。边界选择右侧段并钳制合法末端；所有内部q/dq/ddq差≤原1e-10容差。插入knots不是planner请求。原governor保留一条20ms receipt历史，不能在内部节点重置。

零修改identity求值：仅当所有segment系数与原多项式的精确仿射限制逐系数相同，才使用原采样核；不能因仅外部端点相同使用此路径。修改内部点而伪造canonical_zero会被拒绝。非零路径使用真正局部时间和子段系数。

请求source capture/sample保持原始值，重试不刷新。新类型额外核对original source、模型序列、同序列模型内容与reference version；原PlanLifecycle的100ms/phase/version与fresh command规则继续执行。100ms是计划准入/新命令年龄合同，不是强制每条已激活长轨迹100ms重规划。

原40ms桥、stop/commit/latch、carry/braking/HOLD保留。内部节点无需新激活；整条suffix进入原rolling外壳，实际splice时再验。末端moving状态必须已有合法escape，当前剩余phase预算覆盖primary+commit+stop。

实际issued样本必须由同一reference_id对象sample得出。原reference_progress_commit成功写receipt后，日志只附加reference/certificate ID、子段索引、局部progress、q/dq/ddq及原source，不改command。只有receipt applied且native_steps>0，才能称APPLIED_COMMAND；每native行再以唯一receipt区间、完全一致torque和steps数量审核。真正人体运动另由原物理q/dq证明。

等级边界：MATH_VERIFIED/INTERFACE_CERTIFIED仅为声明测试和reference认证范围；物理成功须另过P0/P1/P2。本包不自动获得正式B Native LEVEL2、host LEVEL3、硬件或临床资格。
''')
write('PATH_CERTIFICATION_REPORT.md','''# 多段路径认证口径

本轮复用原核，不把0.25ms native或5ms FAST步长当作连续时间认证充分性。

|检查|实现/保留口径|范围|
|---|---|---|
|q/dq/ddq接续|每条内部边界两侧解析sample差≤原1e-10|边界连续性|
|ROM|每个degree5的q导数实根+端点求范围；任务与当前Human模型双ROM|连续时间解析极值；比旧离散ROM更保守|
|速度/加速度|原_polynomial_extrema对每段真实coefficients/T；限制仍原reference fraction|连续时间解析极值|
|20ms reference运动|同一完整5ms时间网格，单一20ms前史；原governor仍对所有receipt anchors动态限制|原离散因果口径，不宣称连续加速度测量|
|geometry/clearance|每段原CombinedRigidTableClearanceV1.certified_minimum；原1201-node body margins加解析导数Lipschitz/已合法monotonic包络|每个闭区间连续保守下界，再取全路径最小|
|tracking offset|原常量观测误差假设，分别平移所有实际段；ROM连续极值与同一geometry核|是原预测假设，不是未来tracking-error不变集证明|
|mechanics/wrench|原AdaptiveMechanicsScreenV22的21点model screen；整条原21点保留，另外每段21点，当前准入重算|原采样mechanics，NOT_CERTIFIED连续未来wrench或物理不变性|
|current admission|保留原连续性、current model、live state/ROM/motion、goal、phase/剩余时间、shifted clearance、source/revalidation age和版本；新增payload/hash核验|当前因果模型资格|
|bridge/stop|复用原完整准备；检查末端到桥、桥commit到stop的C2、原40ms和5ms时钟，current model、解析limits与原geometry/offset再验|原future参考/停止通路；不是未来真值预测|
|异常拒绝|worker ValueError走原拒绝；current activation失败走原保留escape/fallback路径；迟到不能逆转原latch|原机制，host压力未验证|

旧分支没有改阈值/数学。新类型整体检查不能简化成“每小段分别合格”：还检查时间分区、所有内部边界、整体source/model/reference身份、跨节点20ms历史、当前tracking offset与剩余phase/stop预算。实际执行的同一对象与certificate绑定。

29项正负合同测试目前PASS，详见CERTIFICATION_TEST_RESULTS。它们包含原单段、多段、q/dq/ddq断裂、中间ROM/速度/加速度/clearance、tracking offset、immutable/pickle/篡改、source/capture、model sequence与同版本内容、reference版本、phase、late latch、未来预算/stop不可行，以及原worker/decode-once/prepared-mechanics路径。

NOT_CERTIFIED：任意轨迹族、跨患者/未见状态、连续真实wrench/跟踪误差不变性、host-clock deadline压力、硬件与临床安全。原B自身只有采样或代理保证的项目，仍按原范围报告；不把这些测试包装成更强数学结论。实际P0/P1/P2另报告。
''')
print('source/design/certification docs saved')
