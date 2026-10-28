# 最强传统基线与配对优化

**CONFIRMED：不存在跨Human、激活时点和所有指标统一的赢家。** 原B的低JM、强固定phase的平顺性、BEST/REF025/ANT的低JF及H150的动作权限均保留。额外quality失败不删除原qualified权衡；完整原不合格和partial不进入成功排名。[144个唯一候选完整证据](analysis/evidence_final_v4/ALL_CANDIDATE_EVIDENCE.json)、[全指标CSV](analysis/evidence_final_v4/ALL_CANDIDATE_METRICS.csv)、[资格分类协调](analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json)。

## 起点与同权限局部优化

**CONFIRMED：** v6历史STOP有149 START/END、9,353,000 native，5966项manifest与12条原积分复算通过。历史D1 BEST为1398.034615/107.971017，REF025的低JF伴motion恶化/VAL03失败；v4 D0的1397.383797/108.639143属于不同权限/条件，不能与当前任务直接排名。[历史核验](agent_reviews/history/HISTORY_AUDIT.md)。

当前已暴露nominal S1、OUT1的B=1437.971420/100.829734，phase=1405.990071/105.481425，COMPOSE=1407.304074/105.633628（JF/JM单位N·s/Nm·s）。BEST/REF025/ANT在此状态原excursion失败；BLEND原合格1405.607887/105.665530但额外quality失败，仍保留其JF/JM权衡。

四个合法RETURN时间x5=.80/.88/.93/1.00均改变真实动作、通过原及额外quality，ΔJF分别−.217177/−.146252/−.030825/+.040153，ΔJM+.289780/+.159091/+.084212/−.046380，没有双降。随后同一真实父的x3±.02、x7∈[−1,−.95]八点也无双降；跨组完整causal等价未证明，未混成三维训练。

**CONFIRMED：** 已测方向的简单解析组合TRAD_COMBO（phase基础x5=1、x7=−.95）在同父得到1405.935078/105.464006，较phase ΔJF=−.05499342、ΔJM=−.01741937，通过原门及额外quality。髋/膝jerk约增.0622%/.0668%，在冻结.1%内，不是全部运动指标严格下降。共享GP/quad动作1405.987192/105.482013，原门通过却JM上升，未超该传统组合。

## 冻结迁移：正负同时保留

|固定候选相对同状态phase|ΔJF|ΔJM|原门/额外quality|结论|
|---|---:|---:|---|---|
|TRAD_COMBO，PFXV01|−.05529679|−.01744766|均通过|有限prefix迁移正结果|
|TRAD_COMBO，PFXV02|−.06034078|−.01794088|均通过|有限prefix迁移正结果|
|TRAD_COMBO，short_segments|+.04003417|+.00939960|均通过|两成本反转，几何迁移负结果|
|共享GP/quad，PFXV01|−.00289429|+.00058891|均通过|JM目标失败|
|共享GP/quad，PFXV02|−.00313934|+.00060582|均通过|JM目标失败|
|共享GP/quad，short_segments|−.00304408|+.00056744|均通过|JM目标失败|

两个prefix的native/causal/pure物理前缀互异并无已知45项native别名；历史缺trace/未snapshot覆盖仍限制“完全新”的强声明。它们仍同nominal Human，未来RETURN0也在原预冻结条件中变化，不是患者IID或纯初态单因素。模型提案不读新state，所以检验的是固定动作迁移。PFXV02 H150原合格且JF更低，但JM/jerk/wrench更高；BEST/REF025/ANT原断言partial保留，不换测试条件。

short_segments原任务未缩短。14项在首次结果前冻结，11原合格、3失败，实际14条轨迹互异。B=1449.683225/100.713040；BEST/REF025/ANT均原合格并有约1410.62–1410.66的更低JF、约106.83–106.90的较高JM。不能只比phase称最强传统已被击败。前两次工程失败完整保留，B已在第二次失败暴露，修正ID后先exact重复，不把重启算新独立状态。

## 更早传统部署与简单等效对照

**CONFIRMED：** 重型HS同OUT0父的EARLY_H150原合格，JF/JM=1619.095307/122.098966，晚启H150=1623.978610/121.893646；髋/膝native jerk从1392.40/3865.00降至318.96/662.70，力变化率65.71→21.65。它是既有传统法更早部署，不是旧OUT1修复或Learning。

同父EARLY_18D及T5_ONLY均原合格，JF/JM=1619.160881/123.283174及1619.162214/123.262117；完整H150的JF/JM、jerk与力/moment变化率更好。简化保留约99.84%的相对B JF收益但非等效；EARLY_18D仍含T底层OUTBOUND terminal×1.5，不能称bare18D。early phase在HS触发constant-knee断言partial，未成为更强合格对照。

nominal早启phase原合格且JF降低，但JM增加、髋jerk比late phase增约.92%超过额外界；early H150 excursion失败。轻型LS全部early候选原motion失败。状态和权限边界不得抹去。

## LS合理迭代与停止

**CONFIRMED：** LS原B合格，phase膝excursion对B差.511014°>原.5°，不是可视作通过。三个RETURN内部路径修订仍差.512548/.513328/.510922°；NO_T5与R4时间对照更差，并增加原acceleration max_abs/p95_abs失败。最后四个原许可终端factor1/1.25/1.4/1.475的差为.851195/.603562/.529960/.513968°，全失败。未放宽原factor≤1.5或motion界，未继续无辨别力细扫。[最后复算](analysis/LSTF01_CLOSURE_AND_ALIAS_DIAGNOSTIC_V1.json)。

factor1与旧NO_T5实际reference/Human/torque/native/scientific receipt完全相同，仅schedule label不同；严格compare_raw仍FAIL，这个标签差不能计新物理探索。尝试全计费，V1派生误分类保留并由V2明确纠正。[别名终判](analysis/LSTF01_ALIAS_CLASSIFICATION_V2.json)。

## 交叉参数开发扩展

两case在结果前共同固定，原物理方程/任务/guard不变，只交换K/D整包。HS body+LS K/D仅B原合格，五完整候选motion失败，T5_ONLY原断言partial；LS body+HS K/D七项全原合格，但H150髋jerk比B更高，不能以qualification代替benefit。更简单18D/T5_ONLY在该格有更低JF、更高JM/jerk，全部保留权衡。包干预含commissioning改变，不识别单独质量/K/D或临床效应。

**SUPPORTED：** 本轮最明确进展为有限条件下的传统更早部署及微小配对改进；Learning没有独立增量。实际候选/完整门/强传统/独立状态与计算费用分列，所有全菜单已经真实执行，实际尝试节省0。


**CONFIRMED（工程与科学结论分层）：** DEVRT02_B已完整原合格，之后历史路径检查失败不降级该B或改判整作业成功；DEVRC01_B原物理资格已恢复PASS，但原worker工程失败及不排名保留。HOLDSS01_B属于HOLDSS02且无原motion verdict，不补资格。完整身份见[协调V2](analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json)。
