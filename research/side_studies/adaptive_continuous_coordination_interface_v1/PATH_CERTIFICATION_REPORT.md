# 多段路径认证口径

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

30项正负合同测试目前PASS，详见CERTIFICATION_TEST_RESULTS。它们包含原单段、多段、q/dq/ddq断裂、中间ROM/速度/加速度/clearance、tracking offset、immutable/pickle/篡改、source/capture、model sequence与同版本内容、reference版本、phase、late latch、未来预算/stop不可行，以及原worker/decode-once/prepared-mechanics路径。

NOT_CERTIFIED：任意轨迹族、跨患者/未见状态、连续真实wrench/跟踪误差不变性、host-clock deadline压力、硬件与临床安全。原B自身只有采样或代理保证的项目，仍按原范围报告；不把这些测试包装成更强数学结论。实际P0/P1/P2另报告。

最终版本：首批.05° motion失败，按预先声明顺序减为.02°通过；最终版仅重复.02°，不依force选择。子段record局部时长摘要修复、完整identity_payload和新增序列化测试见audit/SERIALIZATION_REPAIR.json；首版源码、测试和manifest在versions/interface1。
