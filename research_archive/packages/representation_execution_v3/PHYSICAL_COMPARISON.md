# 完整物理对照与执行身份

**CONFIRMED**：B、H150和新最佳在隔离副本逐raw复现；完整旧18D强参照复得原JF/JM。两条修正后完整18D近似均通过原physical/task、scientific receipt、motion及R2时长门。这里的近性能替代不等于同一运动。

|本轮身份|完整原门|JF N·s|JM Nm·s|相对新最佳ΔJF|新增native步|
|---|---|---:|---:|---:|---:|
|MATCH_B|PASS|1436.456498145|101.253694591|38.421882675|69260|
|MATCH_FIT|PASS|1400.037116473|107.874686071|2.002501003|69260|
|MATCH_JOINT_FIT|PASS|1398.137074559|108.434998743|0.102459088|69260|
|P1_BEST|PASS|1398.034615470|107.971017015|0.000000000|69260|
|P1_B|PASS|1436.456498145|101.253694591|38.421882675|69260|
|P1_H150|PASS|1402.643211486|107.072271907|4.608596016|69260|
|P1_OLD_FIT|PASS|1399.982310590|107.876199630|1.947695120|69260|
|P1_OLD_STRONG|PASS|1400.089728260|107.704687851|2.055112790|69260|

`P1_OLD_FIT` 使用初版错误空间基准得到的参数，物理结果完整合格但仅作为保留的工程诊断。`MATCH_FIT`、`MATCH_JOINT_FIT`才是修正注册端点后的近似；所有尝试都计成本，未删除初版或重复B。

旧臂保留全部18个参数及冻结plateau、固定H150附加规则。`MATCH_JOINT_FIT`实际候选metadata中的18参数与登记向量一致；没有modal planner、独立局部时长或终点锁权限混入。

## 六层结果

1. **中间目标。** 注册状态上的必要条件及两个构造反例见 `OLD18D_EXPRESSIVITY.md`。实际闭环请求的逐目标差见机器表 `reference_layers`，并未将离线目标残差直接当作闭环轨迹误差。
2. **通过速度与边界。** 所有请求保存start q/dq、target q/dq和原证书。`MATCH_JOINT_FIT`相对新最佳的实际issued dq最大差为髋/膝 [1.4430781602121872, 1.1244358600057478] °/s，issued ddq最大差 [10.75868026652044, 5.794892239078158] °/s²。
3. **时长与请求时刻。** `MATCH_JOINT_FIT`按对应decision的最大请求时刻差 0.055000000 s，最大签发时长差 0.025000000 s。全TASK及逐阶段由原门核对；不通过时间扭曲或删除HOLD制造相等。
4. **issued / accepted / activated。** 实际5ms trace、learning activation、accepted command receipt和source timestamp分别保留。所有本表方案的每条applied receipt均关联到完整native区间，torque逐项相等，异常receipt为0；完整artifact每条116320 native行，不能把继承前缀重复算作新增物理预算。
5. **applied torque与真实Human。** `MATCH_JOINT_FIT`相对最佳，在相同物理时刻的native q最大差 [1.0861881151320074, 1.0083776777717548] °，native dq最大差 [1.7333060065252957, 1.3340977639650817] °/s；6轴robot torque最大绝对差 [2.540940872752813, 3.892179317934506, 1.3837343624063791, 0.48505074402889026, 0.5523693127570581, 0.7329240118048155] Nm。因此它没有复现最佳的真实运动，即使完整JF很接近。
6. **完整JF / JM / motion / task。** 联合近似原门PASS、excursion相对B增量 [0.16869440931287727, 0.4770507812792033] °，JF只高0.102459088 N·s而JM高0.463981728 Nm·s。新最佳膝excursion增量0.489368197°，距离原0.5°界仅0.010631803°；该余量不是可部署或临床资格。

两批均来自实际冷commissioning和登记合法prefix，各批分支通过完整live地址空间fork，父进程等待期间不步进，全部parent checks未变。跨批B逐raw一致及规范父hash一致提供重复证据，不声称复制OS调度。机器表列出了每一批父身份。

原scorer重放绕过缓存，直接调用原 `evaluate_execution_mode.evaluate`；另一条路径从完整TASK trace左积分重建JF/JM，从0.25ms native速度重建未滤波a/jerk、excursion、累计运动、边界与tracking，然后重跑原motion比较。P1及MATCH共10个START（含两个冷父）全部PASS，见 `audit/scorer_replay/`。这是同一Agent的独立计算路径，不是独立研究者或独立患者。

JF/JM是完整任务积分；native预算按实际新增积分计费。层级对照详见 `analysis/PHYSICAL_COMPARISON.json`；P2失败、微参数配对和negative controls另见 `CLEARANCE_NONSMOOTHNESS.md`，其失败结果不进入最佳合格排名。
