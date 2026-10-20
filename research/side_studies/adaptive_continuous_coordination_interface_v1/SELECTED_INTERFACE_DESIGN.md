# 最小扩展路线选择

|路线|可复用部分|缺口与代价|
|---|---|---|
|A 递归扩展rolling composite|边界C2、前缀剩余时间、suffix激活/实际splice|任意多段嵌套后仍需完整ROM/极值/geometry/current admission/escape，且原prefix验证假定单段；盲目递归会扩大改动|
|B 版本化MultiSegmentReference|把多段suffix视为一个不可变认证对象，原rolling前缀与splicing不变|新增typed payload与全路径证书，两个原类型消费分支|
|C 逐点增加planner请求|可继续用原单段schema|改变调用频率和lifecycle；不符合本任务有效内部自由度目标|

选B并复用A的已有外壳。新增multisegment_reference.py；隔离副本safe_fallback.py保留完整原_prepare_single_decision，再按显式intent包装；activation_validation.py只为新类型分派全路径检查与shifted geometry，原旧类型分支保留。没有改正式B。总修改范围由最终manifest/diff给出。

只在第二个OUTBOUND请求（索引1）把选中原段分为四子段。零修改仍是新多段对象；仅对已证明每个子段都等于原多项式的情况，用原全局多项式求值避免浮点重参数化差。非零节点修改必须关闭此identity快路，且有负测试防止伪装；不把对象压回端点。

非零演示只改中间节点膝q +0.05°，其通过dq/ddq、外部q/dq/ddq、总duration和任务锚点保持。若motion失败，按事先顺序减为.02/.01°，只按资格决定，不按force选择。未增加planner频率。

所有启动由owned串行父进程控制；physics上限24 START，4小时后不再START；不搜索force、不训练网络。P0失败须先归因，不进入P1。P1/P2通过后仅一次同条件重复，不自动开始优化。

最终版本：首批.05° motion失败，按预先声明顺序减为.02°通过；最终版仅重复.02°，不依force选择。子段record局部时长摘要修复、完整identity_payload和新增序列化测试见audit/SERIALIZATION_REPAIR.json；首版源码、测试和manifest在versions/interface1。
