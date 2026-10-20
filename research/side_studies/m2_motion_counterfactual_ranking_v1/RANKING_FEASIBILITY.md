# 状态相关排序可行性

**未观察到固定候选/mask/carry层中的排序反转；不能据此证明所有状态排序恒定。** 完整运动profile三档均只保留zero suffix。已有数据不能支持Neural Q v2训练或部署。

## 当前ordinary池与历史G-head扩展必须分开

原80行cohort包含 **74条ordinary K3候选＋6条历史离线G-head候选**。后者是原诊断留下的K3表标签，本轮没有生成G计划或训练G/P。当前Frozen M2 ordinary池的13snapshot全部 **fixed selection regret=0**，均值/最大均0，mean zero−best=73.897398N·s。包含G扩展后的0.249333均值、1.620668历史test均值和3.241335最大值均保留，但唯一新增机会来自OUTBOUND的historical G_head_0（candidate6），属于候选覆盖扩展；不能将它说成相同ordinary池已经存在需state-conditioned排序才能获得的收益。

相同计划/mask/carry的三个共同池没有包含G-head，均保持fixed最优。完整motion筛查的结果对ordinary与G联合池都只剩13条zero；普通池是74→13、完整历史cohort是80→13。先前表格统一使用80行历史cohort，不能混淆分母。

来源独立性进一步受限：三个注册父轨迹为初始OUTBOUND slot零、+0.12、−0.12三种prefix；第四个来源是已暴露nominal M2的精确动作replay。所有80条model_hash与model_beta各只有 **1种**，所以没有跨model estimate排序证据。公共context round4有12种并非12独立人体；RETURN近乎相同的成本亦不能放大覆盖。

## 同状态有限候选结果

| 候选筛查 | snapshot | 有效候选行 | 有force降低机会的state | snapshot均值fixed regret N·s | 按父来源等权均值 N·s |
| --- | --- | --- | --- | --- | --- |
| unconstrained | 13 | 80 | 13 | 0.249333 | 0.405167 |
| original_physical_task | 13 | 80 | 13 | 0.249333 | 0.405167 |
| strict | 13 | 13 | 0 | 0.000000 | 0.000000 |
| moderate | 13 | 13 | 0 | 0.000000 | 0.000000 |
| wide | 13 | 13 | 0 | 0.000000 | 0.000000 |

80行来自13个exact snapshot、4个source parent group（train2、validation1、历史诊断test1）、同一已暴露Human仿真；round4 causal120公共上下文仅12个fingerprint。不同parent名字和完整snapshot hash不保证独立人体或统计独立性。train/dev已参与旧linear拟合，13state合并regret是描述性回顾，不能作为新测试成绩。历史test2state均值regret仍为1.620668，与上一包1.6207一致。合并0.249333与按父来源等权0.405167使用不同分母，均明确保存；唯一非零snapshot损失3.241335，RETURN四个snapshot损失均0。

| 父来源 | phase/task s | 候选数 | zero−best N·s | fixed regret N·s | best与第二名差 N·s |
| --- | --- | --- | --- | --- | --- |
| parent_dev_0 | RETURN/11.630000 | 5 | 49.559486 | 0.000000 | 1.789711 |
| parent_train_0 | OUTBOUND/0.000000 | 5 | 112.447146 | 0.000000 | 22.205199 |
| v1_committed_attribution | OUTBOUND/3.545000 | 8 | 88.790594 | 3.241335 | 3.241335 |
| parent_train_1 | OUTBOUND/5.775000 | 6 | 68.177979 | 0.000000 | 1.208567 |
| v1_committed_attribution | RETURN/11.285000 | 9 | 49.521430 | 0.000000 | 1.910228 |
| parent_train_1 | OUTBOUND/0.000000 | 6 | 90.241946 | 0.000000 | 56.516874 |
| parent_dev_0 | OUTBOUND/2.740000 | 6 | 81.738525 | 0.000000 | 15.143577 |
| parent_train_1 | RETURN/11.630000 | 6 | 55.077999 | 0.000000 | 7.308224 |
| parent_train_0 | OUTBOUND/5.585000 | 6 | 87.278041 | 0.000000 | 19.535873 |
| parent_train_0 | OUTBOUND/2.935000 | 6 | 79.167918 | 0.000000 | 13.951544 |
| parent_dev_0 | OUTBOUND/5.395000 | 5 | 73.400939 | 0.000000 | 4.256235 |
| parent_train_0 | RETURN/11.630000 | 6 | 48.157845 | 0.000000 | 0.388070 |
| parent_train_1 | OUTBOUND/3.125000 | 6 | 80.347659 | 0.000000 | 17.198772 |

C只是在已完成、合法、已标注的有限候选中best，不是全局oracle；3条原失败仍保留，没有低成本标签化。zero suffix在fork前的既有prefix不撤销，不能当作从任务初始完全zero的B。A=同snapshot zero suffix；B=frozen linear在同合法池的固定masked排序；C=finite best。

不加研究motion约束时，13/13状态均存在force降低候选，平均remaining zero−best=74.146731N·s；在含历史G扩展的该有限池中best相对fixed的均值差为0.249333N·s。加入完整profile后候选80→13、force机会13→0、oracle额外机会0。0 regret在仅一个可行候选时是平凡结果，不证明学习能力。

## 平顺性与任务剂量的不同作用

| 档位 | 诊断gate组合 | 有效候选行 | 获益state | 平均zero−best N·s |
| --- | --- | --- | --- | --- |
| strict | burden_only | 13 | 0 | 0.000000 |
| strict | burden_and_dose_without_phase_shape | 13 | 0 | 0.000000 |
| strict | full_profile | 13 | 0 | 0.000000 |
| moderate | burden_only | 28 | 5 | 6.357298 |
| moderate | burden_and_dose_without_phase_shape | 19 | 4 | 4.351452 |
| moderate | full_profile | 13 | 0 | 0.000000 |
| wide | burden_only | 32 | 6 | 9.014420 |
| wide | burden_and_dose_without_phase_shape | 29 | 5 | 6.210357 |
| wide | full_profile | 13 | 0 | 0.000000 |

拆分诊断保持原阈值，未放宽完整profile。10%/25%运动负担容差单独仍允许5/6个snapshot有force机会；运动负担加excursion/累计角位移/端点/时长、暂不纳入phase形状的诊断，仍允许4/5个snapshot获益，平均机会4.351452/6.210357N·s。严格无负担增加则无获益。完整profile里的0.5/1/2° phase形状筛查排除全部67个非zero候选，是关键限制。因此“当前profile无合格获益”不能升级为“K3空间无解”；轨迹形状是否应是任务硬可比性标准尚需科学依据，不能为了保留force收益在本包改阈值。

## 真正相同计划的跨状态比较

| phase | 共有exact plan数 | snapshot数 | 父来源group数 | 稳定最优source | 最大fixed regret N·s |
| --- | --- | --- | --- | --- | --- |
| RETURN | 3 | 3 | 3 | historical_design | 0.000000 |
| OUTBOUND | 3 | 3 | 3 | cross_phase_reversal_1 | 0.000000 |
| OUTBOUND | 3 | 3 | 3 | cross_phase_reversal_1 | 0.000000 |

匹配使用float32原生masked有效表的精确bytes，外加同phase、eligible slot mask和masked carry；candidate index/source名不是identity。三个层各有三个共同exact计划，覆盖3×3个state位置（属于三个父来源），比较共有子池，原完整candidate集合因seed噪声不同，**不完全相同**。各层best计划保持不变；9个固定计划pair序列在0.001/0.1/1N·s分析分辨率下均0次反转，fixed在这些共同池regret均0。RETURN相同候选成本在三个parent间极接近，说明该层有效状态多样性有限，不可将其算成强跨状态泛化证据。

完整池best索引、phase或mask变化不作为state-conditioned preference；共有子池分析与全池分析分别导出。phase/count决定的合法表变化不能算 learned inversion。没有人工寻求反转、替换候选或删除负结果。state、phase、model estimate仅用于来源分层和描述；当前没有足够反转/独立状态支持因果关系拟合。

积分最大闭合误差0.000000N·s（JSON保留科学计数精度），prefix q/dq每组一致误差<1e-8。最小间隔及所有pair delta完整保存。微小间隔按三档分辨率处理；这些分辨率不是测得noise置信区间。重复标签误差分布及committed→host continuation偏差均NOT_EVALUABLE，不能仅用浮点误差推断真实策略可信度。
