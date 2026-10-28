# 优化与实际尝试效率

CONFIRMED：本轮没有重新开展广域pattern/BO搜索。只生成一个有明确假设的PATTERN/COMPOSE插值BLEND，独立确认其force–moment–smoothness取舍。新BO/ILC/PPO训练均NOT_RUN，不能沿用v5固定12次比较来宣称本轮优化效率普遍领先。

CONFIRMED：Critic需要各候选真实H状态；它的完整菜单实验全部执行，因此Critic实际尝试节省为0。下面的事前筛选是透明传统phase动作库规则，只用候选执行前的合法状态与冻结开发统计，不使用执行后的H状态。出程无效坐标别名在枚举参照中也被去除，未削弱基线。

| 状态 | 事前选择 | 原门 | 实际候选完整续跑 | 去重枚举数 | 未执行唯一候选 | OOD回退 | 独立全菜单审计regret |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SCREEN_S1 | HANDOFF | True | 1 | 3 | COMPOSE,BLEND | False | — |
| SCREEN_S2 | COMPOSE | True | 1 | 4 | HANDOFF,PATTERN,BLEND | False | — |
| SCREEN_S3 | HANDOFF | True | 1 | 3 | COMPOSE,BLEND | False | — |
| SCREEN_AUDIT | COMPOSE | True | 4 | 4 | 无 | False | 0.000000 |

CONFIRMED：实际未执行的唯一候选续跑数=7。这是相对预登记去重枚举协议的前瞻遗漏计数，不是整个研究campaign已获得净物理节省，也不归因于Critic。全部训练、cold parent、B资格锚、开发更新与独立全菜单审计均计入总预算。S1/S2结果只用于开发更新v2，S3/AUDIT在v2冻结后才运行。

SUPPORTED：已执行选择的完整资格与另一个RETURN全菜单审计可以检验有限发现率/漏优风险；被省略状态的其他尾部未执行，其最优性和漏优率NOT_ESTABLISHED。OOD分数与拒绝记录全部保留，不把未运行候选标作失败或合格。训练成本摊销后净节省NOT_ESTABLISHED。

SUPPORTED：传统单一RULE状态=NOT_RUN。未运行部分不制造结果；原因见ADAPTIVE_FIXED_RULE_RESULTS。

| 状态 | 原门 | 90%保留 | 髋/膝/力变化率收益保留 | RULE少JF vsCOMPOSE | RULE多JM vsCOMPOSE | RULE少JF vsBLEND | RULE多JM vsBLEND |
| --- | --- | --- | --- | --- | --- | --- | --- |


CONFIRMED：配对复用在任何SMOOTH_A1/A2结果揭示前登记，要求新完整B身份锚与既有raw/native/receipt精确匹配；原初未执行RULE配置保留source/versions，不冒充结果。计划由15降到9个START为边界留预算，但若RULE未触发，这6次只是预算减少，绝不计实际节省。动作与90%标准未因测试调整。实际筛选省略7个唯一候选另算，不归因于Critic。

SUPPORTED：固定阶段方案追加复核=COMPLETED_TWO_PAIRED_CONFIRMATIONS。2组配对中2组通过原门及额外代价上限；相对COMPOSE平均ΔJF=-1.309722 N·s、ΔJM=-0.152900 Nm·s。

| 配对状态 | 原门 | 全JF | 全JM | ΔJF vsCOMPOSE | ΔJM vsCOMPOSE | 髋/膝jerk与力变化率比值 | 额外界通过 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PHASE_RULE_S1 | True | 1405.990071 | 105.481425 | -1.314003 | -0.152203 | 1.000481/0.999953/1.003069 | True |
| PHASE_RULE_S2 | True | 1403.733763 | 106.198484 | -1.305442 | -0.153598 | 1.000473/0.999948/1.003112 | True |

CONFIRMED：此为固定OUT1 HANDOFF后共同COMPOSE，不是整段HANDOFF。原任务/门完全相同，额外冻结研究界为髋/膝jerk≤COMPOSE1.001倍、力模长变化率≤1.004倍且JF/JM同时不增。主测试效果已知、参照状态部分暴露，故只称自适应配对复核；不是独立模型选择或新的未见Critic状态。scope澄清见audit/FIXED_PHASE_BOUND_REGISTRATION_SCOPE.json。

CONFIRMED：各已测试phase/upstream域内完整合格菜单的排序是否反转：[('OUTBOUND|ORIGINAL_B_PREFIX', False), ('RETURN|ORIGINAL_B_PREFIX', False), ('RETURN|COMPOSE', False)]。阶段已知即可采用不同固定动作；没有以更复杂学习器解释已被phase规则覆盖的变化。模型纯拟合开销很小不等于标签免费，训练/确认/审计attempt全部计入本轮。
