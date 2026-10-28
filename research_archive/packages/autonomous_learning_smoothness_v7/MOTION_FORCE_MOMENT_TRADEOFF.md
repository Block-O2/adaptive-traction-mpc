# Motion、force、moment分开评价

**CONFIRMED：** JF/JM是原19.03s TASK含HOLD的5ms实测wrench模长左积分。native运动/力/moment变化率用原.25ms未滤波信号、原差分与边界；没有裁峰、缩窗、改积分或新权重。表内皆完整原qualified，但仅允许同group/同父/同权限内直接比较，不作跨Human总排名。

|执行ID|JF N·s|JM Nm·s|髋/膝jerk RMS deg/s³|force模长rate RMS N/s|moment模长rate RMS Nm/s|
|---|---:|---:|---:|---:|---:|
|DEVPC02_B|1437.971420|100.829734|305.097/715.575|20.8754|3.3881|
|DEVPC02_V6PHASE|1405.990071|105.481425|296.249/635.141|18.2940|2.8469|
|DEVPC02_TRAD_COMBO|1405.935078|105.464006|296.433/635.566|18.2918|2.8467|
|DEVPC02_SHARED_GP_QUAD|1405.987192|105.482013|296.223/635.070|18.2938|2.8469|
|EARLYH01_B|1661.045665|115.660506|1388.713/3872.833|66.2702|9.6123|
|EARLYH01_LATE_H150|1623.978610|121.893646|1392.404/3864.999|65.7073|9.4045|
|EARLYH01_EARLY_H150|1619.095307|122.098966|318.960/662.698|21.6503|3.2054|
|CFACTORL01_B|1621.921913|109.441244|331.825/813.977|20.4844|3.3677|
|CFACTORL01_EARLY_H150|1584.244705|114.507866|353.259/756.562|18.9236|2.8162|
|CFACTORL01_EARLY_PHASE|1588.086269|114.462552|328.090/709.138|17.8440|2.7166|

**CONFIRMED：** nominal传统组合相对phase小幅双成本改善且保留冻结额外界，jerk并非严格降低；相对B仍JM更高。GP/quad只降极小JF而JM上升。SS上传统组合原门及额外quality均过，但双成本反转，不能改测试状态消除负结果。完整速度/加速度/jerk的RMS、峰、p95/p99及force/moment TV、变化率均在[全指标CSV](analysis/evidence_final_v4/ALL_CANDIDATE_METRICS.csv)。

**CONFIRMED：** 同重型OUT0父early H150大幅改善运动与wrench，相对late H150的JF−4.883302、JM+.205319；JM仍高于B。支持更早完整策略干预的效果，不是所有指标占优。三个T-family方案OUT+HOLD轨迹完全相同，RETURN各配方实际激活后分叉；完整H150优于所测两个简化方案，但该结论不迁移到LS-stiff格所有目标。

**CONFIRMED：** HS旧OUT1前已发生区间占约95–96%髋jerk²、97–98%膝jerk²、89–90%force-rate²；同N理想未来为零的条件RMS floor约1358.08/3815.74及62.48。峰在task1.005–1.0105s、早于OUT1约.69s，不是TASK首尾求导假峰。early首次参考/物理分叉早于late guard事件，完整策略因果效果成立；guard中介或唯一物理成因仍**HYPOTHESIS**。[过去负担](agent_reviews/past_burden/REPORT.md)、[机制审查](agent_reviews/early_h150_mechanism/REPORT.md)。

**CONFIRMED：** LS phase膝excursion增.511014°由RETURN minimum −.618006°与OUT maximum −.106992°共同决定，不能只看出程峰。路径、去T5、R4及最后四factor都未恢复资格；低JF不补偿失败。LS-stiff的H150虽原合格，髋jerk331.83→353.26，原benefit仍0；early phase在该格原合格且两关节jerk/force-rate均<B，却付出JM增加，显示动作库/目标选择的重要性，不是已训练stump的成功。

tracking RMS、excursion/endpoint、最小clearance、六轴native torque RMS/峰/p95/p99、原motion sensitivity、guard active/unsatisfied/peak correction、fallback及原scorer axes逐项保存在[完整JSON](analysis/evidence_final_v4/ALL_CANDIDATE_EVIDENCE.json)和各native_metrics。HOST_EXECUTION_CAUSAL_VALID为NOT_EVALUABLE的科学仿真不改成真实时钟资格。partial原积分/硬flags在各protected_task_failure保留，全部不入成功排名。

**NOT_TESTED：** 真实硬件交互、临床舒适度和患者安全。更低jerk、JF或wrench不是这些结论的替代。所有图为原指标标准科研图快照：[图和数据说明](analysis/figures_final_v3/README_zh.md)。
