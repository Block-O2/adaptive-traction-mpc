# v5 实验合同

固定ACTIVATION见ACTIVATION.json；T0起最多10小时，重启不重置。科学物理串行、完整地址空间live fork，因果估计/参考/执行状态可用于决策，未来Human/native/torque/receipt仅作评价。保留原plant、guard、task/HOLD/端点/ROM/admission/torque/contact/clearance、原scorer及motion阈值。禁止自动Git、Stage2、Campaign、扩容和硬件。

## 优先问题与评价

区分参考平顺、实际Human与cuff平顺、完整JF三轴。native q/dq为0.25ms；原未滤波edge_order=2导数计算a/jerk，记录RMS/峰值/分位数、tracking/excursion/overshoot与逐项余量。wrench使用实际可得最高采样频率，原5ms左积分JF/JM及phase积分不改；绝不由5ms数据宣称亚毫秒力瞬态。另报变化率、TV、局部波动、控制修正、饱和、拒绝与fallback。失败partial保留不排名。

## 动态预算和冻结

CORE先复现B/H150/强固定BEST/已知C19反例/已知风险区避让，重算新平顺性与wrench指标并测吞吐。其后reference-smooth与execution-aware coordination至少各一类真实干预。小型显式分支模型优先；前瞻预测在START前冻结。优化方法按相同累计新增真实物理预算检查点比较，history/fit/proxy查询另账，自适应扩展另列。LOCKED_VALIDATION至少预留24次attempt，独立prefix在候选与模型冻结前不打开；同Human不同prefix不称跨患者。

## 长期决策

先在合法、可复现中间状态对同一候选和同一后续rolling/replan策略比较近期成本与实际完整剩余成本；承诺轨迹费用不能替代rolling标签。真实tail仅作离线诊断。在排序/选择有可复核实际差异后才训练小型成本Critic：分量remaining JF/JM/motion/task/time，明确gamma与后续策略，保留失败身份；比较short、short+learned tail、short+actual tail，准确率不等于决策收益。无此缺口则不训练。

## 有限job与退出

每组独立config/source SHA、父hash、PID/start_ticks、局部wall和全局截止，单attempt≤300s且≤180000新增native；全局初始cap=500 START/50M native并预留验证，非耗尽目标。RAM≥6GiB、磁盘≥18GiB，资源/因果/证据异常停止受影响实验并封存；普通motion失败/候选拒绝不停止全局。最后40分钟保留独立raw/scorer、历史SHA、receipt/native与进程审计。断线只继续已启动有限队列，不假定推理永久在线。终态STOP，无自动下一轮。

## 同权限修正与正式资格

首版逐关节参考调速和强固定边界附近的未裁剪分支目标移位没有严格对齐原modal参数权限；探索raw与原scorer不改，按audit/ACTION_PERMISSION_REVIEW.json排除正式同权限对照。STRICT01只优化原共同速度坐标c∈[-1,1]并保留slot权重，分支相对坐标也裁剪到原[-1,1]。正式候选需同时满足完整任务、原安全/motion/receipt和ACTION_PERMISSION_VALID。原scorer的PASS/FAIL不为新增权限轴改写。传统优化方法相互只在同一固定4维子族比较预算；动态参考/分支策略与固定计划的策略函数族不同，不能据其单项结果宣称相同搜索空间效率。


## 方法、目标与公平性

|方法|干预与比较对象|目标和限制|
|---|---|---|
|强固定A|历史BEST，同一原rolling执行链|正式主要基准；B、H150另保留原身份|
|Reference-smooth B|原共同通过速度坐标中的局部解析jerk优化|局部目标、完整issued参考、native Human分开判断|
|Execution-aware C|在已知交接前降低合法通过速度，随后搜索内部时间分配|不改executor；不以事后滤波制造改善|
|分支显式选择器|当前估计与已签schedule推断stencil接近风险，选择小相对移位|对照双向盲移位；风险启发式不作安全证书|
|Pattern／GP-BO|同一4维子族、同一历史起点、各自12真实试验|4／8／12检查点；自身反馈隔离；单搜索种子|
|相位组合|已完成OUTBOUND+HOLD与RETURN的经验分量模型|新最多3候选，原门全复核；池化历史优势单列|
|成本Critic|一个当前决策后恢复同一B rolling策略的真实剩余成本|gamma=1；主16标签／phase，次要8标签消融；测试前冻结|
|冻结PPO与修复|历史部署均值，加显式速度／时间修复的混合对照|历史reward与新S不同，不作同reward训练效率结论|

搜索综合指标S为0.65×组合native jerk RMS比+0.35×原200Hz force-norm变化率RMS比+0.004×ΔJF+0.004×ΔJM；后两系数单位分别为每N·s和每Nm·s。它是新研究检索目标，不能替换原scorer、原motion门或解释为临床偏好。新增质量前沿Q只取前两项，在预测JF/JM相对强固定增幅均不超过1%的研究筛选条件下保留至多一个组合；该筛选不是放宽任何原合同。全部分量仍单列。

Critic的主决策目标为原JF，而不是S或Q；JM、motion、时间分量分别预测和评价。C3中short费用及z_H由实际分支执行获得；未建立廉价候选短期状态预测器，故不是已经部署的实时控制器，也不自动节省physical START。B-policy价值与固定modal-policy的补充tail标签不混用。原MPC综合目标与本轮short-JF诊断不同，不能据后者宣称原MPC在所有状态下短视。

独立验证的条件于早期开发之后、任何验证执行之前预登记；完整方法候选、模型、配置和执行源码在首个验证START前冻结。精确相同的动作仅执行一次并记录方法别名；别名不增加样本或尝试数。PPO执行参数修复为额外预登记分支，最多11 START，排在主验证之后，不回写主固定预算与主验证结论。
