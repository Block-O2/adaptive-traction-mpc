# Critic、Cost-to-go、Q与Value

SUPPORTED：更多合法当前状态在开发集修正了部分完整任务排序。原两新参数条件现已完成冻结评价：A1/A2/A3/A5的JF主选择0/2合格，A4 margin主法2/2、均为B零增量。风险校准、独立泛化及实际省试均未建立，整体家族为NOT_FULLY_EXPLORED。

历史恢复发现具体问题而非“Learning失败”：v5短视排序与完整续跑不一致，但RETURN的1秒窗口已解决所测排序，未需额外critic；v6在匹配后续COMPOSE策略、加入累计量/风险后改变了4/4选择，却与强固定phase规则相同；v7的GP/二次面同选、部分前瞻JM方向错误，stump存在资格与基线增量限制。不同后续policy标签保持分库，旧权重/raw不改。

本轮A1使用6个因果OUT0开发context，测试绝对剩余JF/JM、相对B/强固定收益、pairwise、独立资格分类、25/15/constant表示与严格JM目标。完整recipe绑定18D/T底层、激活时点、posture/timing、legacy、slot覆盖及planner SHA；HOLDSS03虽名字含HOLD，原配置实际是OUT0完整承诺，已核实而未混进不同决策时点。

在四个预先冻结的新执行条件、完整五recipe审计中，A1 ABS25主法选择B/earlyH150/earlyPhase/earlyPhase，仅3/4原合格；第三条件的phase jerk RMS失败。原固定B、事前best-fixed与stump均4/4合格。A1合格子集的低JF不能与4/4对照直接排名。短窗0.5/1/2/4秒从已完成真实trace计算，属于已付费诊断，未声称是便宜的无物理推理。

A2把兼容标签扩为48行、10个真实父context，31原合格、17完整失败，缺失动作不补。比较旧库/合并库、绝对/相对成本、25/15/constant与risk ON/OFF。预指定合并ABS25/riskON在整父开发LOCO为8/10，旧库训练9/10；B及best-fixed10/10。Brier约.22498→.20755，但被预测合格的实际失败从4增至6，因此平均概率误差改善不能代替资格修复。

A3只改变合法状态表示和相应同权限简单对照，目标、标签、正则与支持门保持。KIN33增加当前估计q/dq及请求参考q/dq；WRENCH39再加当前实测F/M。原77维整体仍INVALID；这些字段须通过实际job/callback/observer/runtime等7角色SHA、checksum、OUT0、age=0、有限性及QA。请求参考不冒称实际emitted reference，尚缺的TASK积分/峰值不补零；guard43软件计数未入拟合。数值常量std≤1e−12固定z=0，避免放大参考dq约1e−16的噪声。

|同48行、整父开发LOCO|原合格/10|合格子集平均ΔJF / N·s|合格子集平均ΔJM / N·m·s|
|---|---:|---:|---:|
|A2/A3 ABS25 riskON|8|−18.892951|+2.735777|
|A3 ABS_KIN33 riskON|10|−22.602889|+3.284229|
|预指定A3 ABS_WRENCH39 riskON|10|−26.844099|+3.896525|
|A3 ABS_WRENCH39 riskOFF|6|−37.671481|+5.473714|
|W39 B / best-fixed|10|0|0|
|W39 if-stump|6，另1未知|−19.117744|+2.743442|
|W39 nearest|5|−30.997034|+4.386306|

不同合格率的成本子集不可直接排名。主39维模型选7个nonB、3个B；原第三条件改为合格earlyH150。但失败phase的预测失败分数仍约.370<.5，修正来自成本排序，而非识别出该motion失败。39维Brier反而约.21076，漏判仍6/48。25维全部240项对A2选择/资格/数值完全parity，最大差0，限定了此次表示变化的归因。

JM始终分列。现48行中21个合格非B动作的JM全部高于同父B；严格JM目标下DELTA39全选B，ABS39仍在CFL误选JM增加动作，实际strict仅9/10。原JM比≤1.25门保持，不把允许的JM上升说成双成本改善。

A4已恢复全部48行的45个原连续motion余量，所有余量有限、无补值，负余量重建与原failed_requirements逐行完全一致，6个目标为数值常量。已实际完成33个49-RHS ridge求解，共1617头，主法用多正则预测最小余量≥.02后按JF选。开发LOCO仅9/10，低于原A3分类的10/10；假可行6→2，但假失败3→17。CTX03真实jerk余量约−.679/−.684被预测为+.120/+.115，合格H又被误排除。ensemble是确定性分歧包络，不是校准安全置信区间。

A2实际54个风险拟合、324个双RHS ridge、960 API；A3实际33风险、198双RHS ridge、99stump搜索、720 API，约2.78秒wall、96MiB峰RSS；A4 wall3.74秒、峰RSS约88.5MiB。以上拟合本身均0新物理/0实际省试。V8COMPENG03已实际调用A3/A4等55个pre-B决策及C5个after-B决策，真实loaded-module、七角色callback/source/config证明通过独审。四个B/H子任务合格，但两phase在原膝参考断言提前终止，5个模型决策对应这些失败；不作完整成功排名。

这个已曝光 heavy 条件揭示动作格支持问题：原 48 行对该 case 只有 B/lateH/earlyH，nearest-context 距离为 0 并不表示两个 phase 已有标签。新增两个真实 partial 的 preaction payload 与旧 heavy 完全相同，原 11 硬条件全 true、完整资格 false，成本和 45 margin 缺失。A5 已实际只更新 50 行 operational 资格风险，成本仍严格保留 A3 原 48 行权重和归一化。

A5 一次拟合完成 11 个 logistic、96 次迭代、107 次 objective/gradient、500 个训练 design 行；20 批 API/420 项选择，0 新物理。已见 heavy 的 LATE_PHASE 失败概率 .354242→.530190，使 JF 主选择从失败 phase 改为合格 EARLY_H150；但另一个已见 case 由 B 改为失败 EARLY_PHASE，FULL 主法仍 8/10，误放仍 5/50，误拒 0→1。局部修补不能当总体或泛化改善。

整 case LOCO 的 risk48/risk50 十项主选择完全相同、均 10/10 合格，仍误放 7/50 动作格；heavy 留出时两个新标签同时移除，概率 parity 误差为 0。此处 50 格分母包含新增 partial，不能与旧 6/48 直接当成改善率比较。nearest50 在已见格达到 10/10、零误放，但 LOCO 仅 6/10且与 nearest48 相同，只支持记忆控制的解释。模型 wall .439s/CPU .434s/RSS 108288KiB，外部树费用另列；[完整 A5 结果](families/critic_value/support_qualification_v5/REPORT.md)。校准支路 NOT_RUN；实际 OUT0 及原新参数冻结验证的后续闭合结果见下节。

证据：[A1家族](families/critic_value/METHOD_EXPLORATION_MATRIX.md)、[A2](families/critic_value/coverage_risk_v2/)、[A3报告](families/critic_value/coverage_state_v3/REPORT.md)、[A4可恢复性](families/critic_value/coverage_margin_v4/AVAILABILITY_REPORT.md)。多决策TD/Bellman、其他后续策略、更多合法任务中途状态和可靠风险校准仍未充分覆盖。


## 原两新参数冻结验证（VAL03/04）

CONFIRMED：两作业在完整master发布后实际运行，模型/目标/阈值未按结果调整；原153 pre-B逻辑决策均已保存，分别1168/1224项metadata核对无失败，原评分分别7/10份回放一致。重载条件四个原nonB均KNEE断言partial，11hard全true不授完整TASK；轻载条件EARLY_PHASE完整却加速度p95不合格。主A1/A2/A3/A5恰好分别选入这些失败，不能给partial补完整JF误差。

A4 margin主法两次均选B、2/2完整合格，没有降力增量；这保留了安全选择证据，但不等于超过固定B。其余38项A目标/表示变体全留，不用事后更安全的B变体替换主法。开发39D的10/10与这两原参数0/2是不同数据范围，前者不能代替后者。

[逐主法/seed及全部变体面板](families/critic_value/analysis/val04_and_two_original_cases_brief_v1/REPORT.md)与[原冷任务结果](analysis/TWO_ORIGINAL_NEW_PARAMETER_COLD_RESULTS_V1.json)提供精确来源。新的POSTAPP配方只用于解释接口适用性、尚待执行；其新标签和动作不会移植回原学习器。全家族仍NOT_FULLY_EXPLORED。


## 主法身份与原两条件结果更正（精确原行，旧滚动面板保留）

**CONFIRMED，更正而非重训：** BC批准的预登记primary是 `AGGREGATE_5_OLD_NORM`，不是 `AGGREGATE_5_NEW_DEV_NORM`。批准fit manifest `families/il_dagger_sac/context_aggregation_v1/SOURCE_MANIFEST_FIT_V1.json`，SHA `84518257bc5c0713e2cf8c29a69245c46ec58059de3a1fdaff6ebb485961f76e`，JSON pointer `/primary`。原VAL03 helper `families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL03_MAIN_V1/RESULT.json` SHA `0f456b53387de27ed539463e6cd2e9126a411ec0a181471dc0b86caf8e7823cd` 的 `/decision_alignment/choice_table/24`：OLD_NORM选EARLY_H150、PARTIAL_NOT_RANKED；原VAL04 helper `families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL04_MAIN_V1/RESULT.json` SHA `a5bdb426efd6fcd95ad696f17035f24fad6db1439ad1468b7ffb0a6e8aaa9617` 的同一 `/decision_alignment/choice_table/24`：OLD_NORM选EARLY_H150、COMPLETE_ORIGINAL_QUALIFIED。因此**原BC主法为1/2完整合格**，light与强固定H同一recipe；没有学习独有增量。

NEW_DEV_NORM变体在两文件的 `/decision_alignment/choice_table/23` 分别选EARLY_H150 partial、EARLY_PHASE完整motion不合格，才是**0/2**。此前本文件或所链滚动面板中的“BC主法0/2”、将NEW_DEV_NORM列为primary的解释现已superseded；原模型、原输出和旧面板字节保留，不以改表掩盖更正。A1/A2/A3/A5 JF主法0/2、A4 margin两次B的2/2、SAC/NQ指定主端点1/2等其它原结果不受此身份更正影响。

另，12个categorical parent/first/last逻辑端点（两helper的 `/decision_alignment/choice_table/11` 至 `/decision_alignment/choice_table/22`）在VAL03均选EARLY_H150 partial、VAL04均选B完整合格：每个端点均1/2，light零B增量；不得把parent误述为light选H150。它们不是12个独立参数条件。

本更正仅逐项读取已闭合原metadata：0新helper/model/fit/raw/scorer/physics调用，未改冻结源、模型、阈值、原标签或主法。


## 已暴露heavy的新适用性recipe开发诊断（POSTAPP01，原验证不追改）

**CONFIRMED，限定接口完成性：** `V8POSTAPP01`精确复用原VAL03 case/seed/prefix，B recipe不变，四个原nonB fullrecipe只增加 `terminal_timing_applicability=True` 并采用新identity。原loaded `base_campaign.compare_raw`的实际code值/源SHA/job绑定通过；B对原VAL03 B完整raw一致（116320 native身份记录、5817 receipts，非新增物理计数）。5个child和parent均闭合，6份原scorer replay精确重现原标签。

四份新nonB回执各在RETURN slot5依据当前reference与公开goal跳过一次optional timing；原1e−10阈值、断言、guard/scorer与11硬门不变。四个新nonB全部完整结束，但**motion资格全失败**：两H150为excursion，两phase为acceleration max_abs及excursion。B完整合格；不能把replay PASS/硬门通过/避免KNEE中止写成四配方合格，不能以其JF下降声称有效降力。后续continuous-heavy按主审因Hmotion资格false而NOT_RUN。

这是原已暴露条件的新固定recipe实现能力诊断，不是第三个独立参数case，不把旧模型选择/Q/标签套到新recipe，也不修改原VAL03 partial或两原条件主法结果。完整原物理付费与一回原B raw比较保留；本次独立审计额外model/scorer/raw/physics调用均0。独立metadata审148项无失败，见 `families/critic_value/analysis/postapp01_closed_metadata_review_v1/RESULT.json` SHA `73c9f51c8187e3ede4ec3fc17567d911aba6362f42736a3f930790f07340d2ca`；该scope通过不是motion/generalization/净效率通过。


## POSTAPP02 已暴露条件实现能力诊断：原合格路径也可被新开关改变

独立审查完成于原 physics exit0、原回放 END PASS/6缓存闭合之后；146 项 metadata/source-pin 检查全部通过。配置 `experiments/V8POSTAPP02.json` SHA `150d6b842bb42856afa20768597506f2cc0bcd0df813d5f214e4ec2aafee3acd`；原 VAL04 配置 SHA `736b440db5d98fd71595662ca0f03a0b216d761140ee6e320594925459b673ff`。同 case `224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87`、seed 2026102754 和原 prefix；B 保持原配方，四个新 recipe 仅增加 `terminal_timing_applicability=True`。原 B 跨 job full-raw gate PASS，引用真实 loaded 原 `compare_raw` 的源码/CodeType 值证明，未新调用比较。

五个 child 均完整、joined，parent hash 不变、owner/PID 已闭合；原 11 hard 条件全 True、原回执 `true_hard_safety_violation=False`。只有 B 合格；四个新 nonB 均 motion 不合格。原 EARLY_H150 **合格** JF/JM=`1323.2139574827079 / 101.44771132880281`，新 EARLY_H150_APPLICABILITY 完整但 excursion 失败，JF/JM=`1323.2513097001054 / 101.50423541091276`。原 LATE_H150 与 LATE_PHASE 也由合格变为失败：新 LATE_H 为 excursion；新 LATE_PHASE 为 acceleration max_abs + excursion。原 EARLY_PHASE 已 acceleration p95 失败；新版本仍失败，项目为 acceleration max_abs、acceleration p95、jerk p95、excursion。完整未合格成本仅作描述，不计合格收益。

四份原实际 timing capture 各一条，均为 **RETURN slot 5**：`knee_at_public_goal=False`、`knee_reference_stationary=True`、`optional_timing_requested=False`、原 threshold `1e-10`，truth_used=False、model_calls=0、原 terminal assertions 未改。这是实际跳过可选请求的局部证据；原 VAL04 无对应 capture，不能反推旧 predicate 为 True/False，也不能把新启发式称为全局 predicate 修复。原执行 binding/candidate（除新身份与 action flag）逐值一致；没有运行四个旧新 nonB 的额外 raw compare。六份原 replay PASS 意味原资格/失败标签精确复现，并不使四个新 nonB 合格。

这是 EXPOSED_POSTVALIDATION_IMPLEMENTATION_CAPABILITY_DIAGNOSTIC_NOT_GENERALIZATION，新增独立条件数 0；原 VAL04 标签/冻结模型选择保留，旧模型选择不得转移到新 recipe。固定分支 model/fit/map/RNG 调用 0，所有家族仍 NOT_FULLY_EXPLORED。

独立证据：[POSTAPP02审查](families/critic_value/analysis/postapp02_closed_metadata_review_v1/REPORT.md)，RESULT SHA `8d0b48da95a54ef8471d245ed240e5ae241a5bb174cf1e510643306e9ff6bd70`；REPORT SHA `ceb4077cfa435afcdadc58db04e2a8436b8399fd9ab332a3db10353691a5460b`。其中逐行保存原/新 RESULT 与 execution、六份 replay、B gate、四份 RETURN5 capture、原 source SHA、资源和 PID 引用；本独审 0 raw/trace、0 模型/scorer/物理/数值重算。
