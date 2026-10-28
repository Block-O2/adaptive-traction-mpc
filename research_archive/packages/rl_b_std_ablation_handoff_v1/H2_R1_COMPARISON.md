# H2/R0 与 H2/R1 逐父对照

本轮从历史raw独立重算六条nominal mean轨迹的原5ms cuff积分与native Human运动，零新增物理/Adam。执行合同hash和public task contract逐字段一致。全部完整19.030秒，才允许下表描述性剂量比较。

|父seed|策略|JF N·s|JM Nm·s|knee tracking RMS °|RETURN knee overshoot °|hip/knee jerk RMS °/s³|
|---|---|---|---|---|---|---|
|1495656323|ORIGINAL_050|1446.792925|101.532803|0.554964|0.562655|416.435/1061.284|
|1495656323|RETENTION_H2|1435.949543|103.494314|0.472444|0.825639|381.026/881.508|
|1495656323|RETENTION_R1|1438.416202|103.108369|0.503203|0.529855|381.913/907.380|
|1630784693|ORIGINAL_050|1437.053824|102.749452|0.580361|2.177303|388.445/810.606|
|1630784693|RETENTION_H2|1432.539740|103.621209|0.629999|2.653867|379.253/797.378|
|1630784693|RETENTION_R1|1429.253998|104.463512|0.633442|2.360245|362.357/778.075|

H2主要贡献是两个选定成功050父在已测30/60 mean端点保持完整任务。原Control继续30集后两父mean均失败；H1仅一个父保持。H2组合改变完整episode聚合、更新频率、优势归一化样本和minibatch结构，并未唯一识别哪一项造成保持。H2实际Adam总数并不更少，不能用“少更新”作唯一解释。

R1没有显示跨父一致的额外剂量优势：
- 父1495656323：R1相对H2，JF +0.171779%，JM -0.372914%。
- 父1630784693：R1相对H2，JF -0.229365%，JM +0.812868%。

两父R1均较H2减小RETURN knee overshoot，但149的knee tracking和jerk略升，163的knee tracking也略升而jerk下降。R1相对原050的force小幅下降同时moment上升；没有Pareto冠军。

直接机制证据来自phase积分：两个H2及两个R1轨迹的force下降都集中在RETURN；OUTBOUND force反而略升。RETURN moment增加超过OUTBOUND moment下降，造成总JM上升。HOLD基本相同。相位内协调轨迹与实际施加参考发生改变；不能把force norm降低等同于moment降低。尚无已隔离证据证明具体cuff力臂、旋转变形或reward项是唯一根因。

R1与H2共享原050父及PPO方法家族；首批更新前可有共同样本，但更新后状态、成功/失败、聚合时点和训练样本分离。不是只差Reward的严格同轨迹因果对照。每支30→60都从030已flush状态延续，非无flush连续60。

online V仅为原causal估计器的归一化加速度平方积分；与native速度差分产生的实际a/jerk不同。原Reward并不直接惩罚native jerk，且actor不可读取未来/native truth。下一轮运动奖励须使用已发生的causal估计值，晋级另看native独立评价。

Gaussian原STD约0.97–1.00，与mean部署是不同执行分布。新的STD真实消融单列；不能把本表mean保持升级为随机可靠或跨患者泛化。G4严格矩阵、原B/H150同链live matched和独立合法初态仍未闭合。

## 同一R1目标下的保存轨迹复算

把同一个R1 observed cost `.0005 JF + .005 JM + .02 V` 应用于全部完整mean轨迹，作为只读诊断（不是跨Reward总数值排名）：

|父seed|策略|online V|同一R1成本|
|---|---|---|---|
|1495656323|ORIGINAL_050|0.127578799|1.233612056|
|1495656323|RETENTION_H2|0.098541754|1.237417177|
|1495656323|RETENTION_R1|0.101425783|1.236778461|
|1630784693|ORIGINAL_050|0.101337347|1.234300917|
|1630784693|RETENTION_H2|0.095961758|1.236295149|
|1630784693|RETENTION_R1|0.088951676|1.238723594|

两父R1模型虽然原mean JF略降、native jerk下降，但上述同一R1成本均略高于原050；JM上升的加权代价超过force/V下降的收益。这不是Reward漏洞，也不直接否定随机训练分布的目标；说明尚不能声称R1在nominal mean上改善了自己的总优化目标。提高moment价格只是可证伪的下一假设，不能把“当前moment权重不足”写成已识别根因。

## 原cuff测量点与构成关系

只读源码核对：原Kelvin–Voigt物理中 `F = R_H(Kx+Du)`，独立旋转couple为 `R_H(k_r theta+d_r omega)`；robot-facing sensor按原约定读取**adapter_cuff_site**处的transmitted wrench。Human-site moment另含`r×F`，不能把两个参考点混用。原接口分别含平移/线速度与旋转/角速度通道，因此降低JF不必降低JM。

保存5ms向量的范数分量分摊已独立重算，逐phase与原JF/JM求和一致，见 `audit/CUFF_TRADEOFF_MECHANISM.json`。它定位传感器方向上的变化，没有改变scorer；不能单凭这些积分把旋转弹簧、阻尼、姿态或某个Reward项确定为唯一原因，也不能将robot-site moment增加直接归因为力臂变大。
