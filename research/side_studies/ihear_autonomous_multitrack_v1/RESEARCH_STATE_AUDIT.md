# RESEARCH STATE AUDIT — 多方向自主研究 v1

证据范围：PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION，同一固定Human模型。原任务19.030 s，OUTBOUND/HOLD/RETURN为9.005/1.020/9.005 s。原B、历史18D/T/D/Early RETURN只读；本包不训练学习器。初始审计先于任何新physics。

## 已有资格与开发候选
|方法|确立的有限证据|未解决的边界|
|---|---|---|
|B|各历史匹配条件完整task/safety/科学receipt；原运动参照|host FAST/strict/R2仍有失败，未建立统一B_RUNTIME_BASELINE_V1|
|18D|原开发完整J_F 1400.697221153，匹配B 1438.613498467；传统离线18参数优化|旧新prefix motion 0/4；N2/U1/V1/V2存在峰值失败；不是RL|
|18D-T|N2/U1/V1/V2有限合法prefix与确定性重复通过|W1/O0失败；只证明对应remaining suffix，非跨患者|
|D|V1开发与重复、R0受控背景完整通过|W1/O0失败；R0共享W1 OUTBOUND历史，不能算完全独立新入态|
|Early RETURN ER110_R4_120|修复W1 v95/a95/amax/jerk RMS，J_F 1402.644192729|膝excursion差+0.548596467°，原0.5°门失败；无重复/未见验证资格|
|局部Waypoint|确实改变native Human，小幅局部及完整效应可重复|固定外端边界/时长的小幅shape信息增益低，未达到历史晋级；reference平滑不保证实际/完整改善|

## 五Track事前判定
A：最新ER膝目标9.5°，实际最小8.224621516°；真实下冲1.275378484°，不等于excursion差。16.895s参考停稳时已有1.169895711°下冲，随后271ms再下降0.105482772°。RETURN5仍在完成髋运动。检验RETURN3膝通过速度有界缩放；保留父参数，最多两个候选。原证书预检和完整physics均须通过，任何新失败不能被低力覆盖。

B：N2/U1/V1/V2多数RETURN近乎收敛；W1/R0共享OUTBOUND，W1/O0的RETURN响应几乎相同但完整相对门不同。必须分开绝对负担、匹配B分母、OUTBOUND累计极值及暴露状态。交付状态地图和只读因果特征表，不声称已有有效在线准入器。真正未见W2仅在新候选开发合格/冻结/重复后消费。

C：raw native梯度及SG5/21都保留；完整TV_v/TV_a/jerk与局部峰分开。已有微小Waypoint搜索收益不足，不再重开同边界密集搜索。优先分析A干预是否改善完整运动并检查下游代价。

D：ER对匹配B J_F降低2.353869%，moment integral仍增加约5.792%。tracking和moment不因降力自动改善。相同窗的allocator/接触/误差仅作关联，不冒称独立根因；没有新临床comfort门。本轮优先完整配对审计，不无依据改机械参数。

E：原source age/lifecycle/40ms桥接/current-state admission/certificate/receipt/native ownership保持；科学时钟通过不能替代host-clock资格。原receipt部分路径没有直接plan_request_id，间接时序、reference/torque/step核验保留且明确标注。未来学习schema区分因果输入、提议/实际应用、真值离线标签、完整资格和数据分组。本轮不做runtime重构。

## 共同机制与低信息方向
终末耦合/跟踪响应与累计运动门共同限制适用域：降低窄峰不保证p95或excursion通过。末段开始前已累积的极值不能由后来动作删除；匹配B未来全程p95不可供在线决策。形状小修、继续延长已修好的RETURN1、把所有下冲解释成停稳后的惯性都缺乏当前证据。

## 合法接口及证据层级
隔离wrapper可在原活态选后重建内部目标、suffix duration、内部pass velocity；必须重新通过原数学/连续几何/力学/escape/current admission和真实执行。不更改正式B接口、plant、HOLD、完整时长、gain、ROM/torque或原验收门。数学可行只允许进入physics，不构成Human运动通过。

全部25条历史配对native统计及源SHA见derived/HISTORICAL_NATIVE_AUDIT.json和audit/HISTORICAL_ANALYSIS_SOURCES.json。源码索引见audit/EXECUTION_SOURCE_INDEX.json；W2历史START审计见HOLDOUT_REGISTRATION.json。尚无本轮新合格候选，此时physics START=0。

## 本轮结束更新

以上为新physics前的审计，保留事前判断。本轮最终START/END=12/12；AV090/AV080仍仅excursion失败，R0冻结ER通过原完整门但属于已暴露诊断。无新完整合格开发候选，无候选重复或未见W2验证。五个Track最终证据见各TRACK报告与REPORT.md，保护核验见PACKAGE_VERIFICATION.json。
