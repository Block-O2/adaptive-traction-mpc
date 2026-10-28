# v6 实际冻结研究合同

CONFIRMED：本文件汇总事前登记的实际版本，不改变已执行实验合同。初稿及其事前后续策略修订保留在source/versions/EXPERIMENT_CONTRACT_initial_with_amendment.md；机器freeze、配置和每job SOURCE_MANIFEST为准。唯一T0为2026-10-26T09:55:17+00:00，硬截止15:55:17 UTC，末40分钟保留复核封包。

唯一 ACTIVATION 与六小时截止见 ACTIVATION.json；新动力学任务截止前预留封包时间。旧包只读，原 motion、安全、任务、5ms JF/JM 左积分及权限不变。

先恢复 v5 真实 raw、源码、模型与 manifest。强固定 BEST、HANDOFF、PATTERN、COMPOSE、ANTICIPATORY 保留原身份。只新增一个在 PATTERN 与 COMPOSE 合法坐标间的 BLEND，假设其保留大部分平顺性而减少 COMPOSE 的 JF 代价。初始最多 6 个开发父状态、4 个冻结评价父状态，每菜单 B 资格参照及五个候选；不广域搜索、不新增 PPO。

A 固定 COMPOSE；B 0.5 秒实测 JF；C 1 秒实测 JF；D 0.5 秒 JF 加冻结 Critic；E 在实际完整合格续跑中取最低剩余 JF，仅为有限菜单离线参照。主菜单HANDOFF/PATTERN/COMPOSE/BLEND在10:16:44 UTC冻结，早于10:17:50的TRAIN_O1开始。所有方法同父状态、同菜单，仅当前一次决策采用候选，之后均恢复共同COMPOSE及其H150 timing/posture。B完整资格锚与BEST单次辅助探针不混入主菜单；单次BEST不能冒充整策略强固定BEST。DEV/SMOOTH整策略承诺、主COMMON_COMPOSE与旧B rolling成本分库。固定HANDOFF/PATTERN/BLEND、训练时固定phase规则和直接guard历史规则一并公开，不能削弱强基线。

0.5/1 秒候选数据来自真实 MuJoCo 分支，不能称低成本在线预测或硬件尝试。累计历史只读取当下 observer、measured wrench、原 guard 返回值与已有 context rejection。observer 差分峰值与原 native 门不等价；最终资格仍由原 raw scorer 独立评价。不得使用未来 PASS/FAIL 作为选择 mask。完整任务失败绝不进入正式收益排名；若当前已知不可逆的原门失败，无论尾部预测如何均无资格。

模型须保留时间和阶段信息，按训练折拟合变换并设物理尺度下限；按整个父状态分割。常量/近常量字段有分布审计与 OOD 处理，ensemble 分歧不是校准置信度。成本回归和资格风险预测分开。新 test 输入、源、菜单、模型、规则在任何 test 动力学结果前冻结，揭示后不再训练并称其未见。

主线D及后续完整补充要求已收到，见USER_REQUIREMENTS.json。Critic完整菜单短窗和尾部实际执行时savings=0。传统事前phase库筛选在候选START前保存排序，阶段有效坐标先去重。S1/S2实际结果只更新开发V2的共同偏置、域/不确定性及资格证据，不用非配对反馈伪造相对收益。V2冻结后才执行S3与独立RETURN全菜单审计。只计真实未执行的唯一候选相对事前登记枚举的省略，父prefix、B锚、训练和审计全部收费；不宣称未观测尾部最优或整体摊销净节省。

主比较的后续策略进一步固定为 COMMON_COMPOSE：菜单只更改当前一次决策，之后所有候选均恢复同一 COMPOSE（包括其 H150 timing/posture 语义）。A 当前也选 COMPOSE，B/C/D 菜单相同。原 B 分支仅为原资格参照，不在决策菜单。DEV_O1 的整策略承诺实验单独作为动作库诊断，绝不混入此成本标签。该约束在主比较第一个 START 之前冻结。

CONFIRMED：TRAIN_R1–R3的B上游接COMPOSE后续被原excursion门拒绝，保留全部15个完整失败。之后登记COORDINATED_RETURN_PROTOCOL：先真实执行COMPOSE上游到RETURN1，再做同菜单/共同后续；原B锚从OUT1独立完整执行。父进程只付费采样prefix，不以partial成本排名。COORD_R1于11:37:32 UTC开始；旧失败仍作资格风险标签，以因果upstream字段区分。独立回程测试遵循同一已登记上游语义，未降低原门。

CONFIRMED：旧风险父状态别名和临时jerk max_abs错误标签均在测试前封存；最终风险V5使用12个实际父状态族的旧raw，整族CV。不同后续策略只共享“截至H已发生风险”，不共享cost-to-go。COORD_R2六分支24项线上/raw历史完全一致后，主模型于12:17:03 UTC冻结，TEST_O1于12:17:05 UTC才START。H=0.5现场预测断言完整结果尚不存在；揭示后不重训。contract_time_remaining来自原30秒task timeout减已用TASK时间，不是未来实际终点。

CONFIRMED：独立BLEND确认事前要求原完整门通过，且保留COMPOSE相对整策略BEST的髋jerk、膝jerk、native力模长变化率收益各至少90%；JF/JM另报，阈值不随结果变化。单一RULE为预登记全局BLEND加首个出程slot时间坐标0.25→0.125；仅核心A–D完成、两组BLEND确认通过且能保留40分钟封包时运行。开发失败不调参，最多15个新增START，独立列为自适应研究，不能改写主固定预算结果。

CONFIRMED：单一physics锁串行运行，总START上限150、native上限1500万，worker/supervisor双层截止及RAM/磁盘floor。每物理job有独立ID、配置/源码SHA、START/END、native账、局部wall上限和恢复依据。无Git写入、正式控制器替换、Stage2、硬件、患者或扩容。最终raw/scorer、历史保护、append-only日志及owned清理通过才封包STOP；不自动开启下一轮。

NOT_TESTED：廉价候选H预测器、精确native资格在线证书、患者级泛化、长程scratch PPO或临床舒适度。原guard、任务和未滤波native门仍为最终完整资格依据。

CONFIRMED：13:23:39 UTC、SMOOTH_A1/A2尚未START时，另登记REFERENCE_REUSE_AND_BOUNDARY_AMENDMENT。RULE_T1/T2改为对应SMOOTH状态相同合法prefix/seed，保留新完整B及RULE；必须先通过新B与已执行参照B的完整raw/native/receipt身份，再复用该状态实际跑过的BEST/COMPOSE/BLEND。原未执行配置封存，不冒充结果；规则参数、90%标准、原门不变。避免6次重复基线执行，另留4次START给已知TAILOT附近1e-3合法prefix扰动的新三动作风险挑战。总计划148、原总cap150不变；主四状态固定预算比较不变。边界模型、菜单和配置在新结果前冻结，不重训、不称患者泛化。

CONFIRMED：以上RULE复用只为事前预算设计，实际未满足原触发条件，因此不计任何RULE实际节省。随后冻结固定阶段配对与最后一次局部边界检验，最终149个START。最后O3配置虽有1e-5差异，实际父状态及B/RELATIVEP/SPEEDP全raw与已训练TAILOT相同；独立声明已停止、原FAIL审计封存，按训练父状态重放报告，未重训。最终独立模型证据仅4个主状态与2个真正新旧B状态，出程独立失败修复仍NOT_TESTED。
