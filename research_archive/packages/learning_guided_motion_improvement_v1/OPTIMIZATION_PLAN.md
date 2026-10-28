# 冻结实验合同 v1

冻结UTC：2026-10-21T14:32:17.446062+00:00；T0与硬截止以START.json为准。先完成长期反思和零新物理恢复审计。本轮仅科学仿真开发。

## 问题、权限和分母

从当前条件真实完整合格的H150强父出发，三臂是否在相同新增真实物理预算下产生额外完整合格JF改善？若H150在本轮原门失败，禁止称强合格父；仅允许明确降级的B父子实验并另行冻结说明，历史H150失败不改写。

固定同一D01R合法cold commissioning与前缀；Linux完整address-space fork，核对RNG、Mj integration、observer、belief、scheduler、pending/lifecycle、receipt/native所有权和parent不变。合法prefix来自历史D01R_PLAN，不从q/dq重建活状态。当前nominal Human、robot/cuff原资产不改；多状态/跨患者NOT_VALIDATED。

连续参数x=(x_O,x_R)各∈[-1,1]。冻结H150的18D参数、T修复、RETURN姿态/时序为中心；只将18D OUTBOUND differential coefficient[1]增加0.002*x_O，RETURN differential coefficient[6]增加0.002*x_R。其余16个系数及H150修复固定。x=0严格回到H150；全臂可使用同一权限。它改变中间髋膝相反进度，端点因sin²包络不变。执行仍调用既有certified quintic、原planner/certificate/current-state admission/governor，拒绝时保留原fallback并记录实际执行。额外权限本身不归功Learning。

## 物理代理权限

既有名义Human inverse-dynamics和allocator可根据合法commissioned beta/geometry及拟议reference算名义wrench；没有证据证明它重现robot/contact、observer、闭环tracking与离散准入。历史Predictor的指数tracking-error衰减和completion allowance也是近似，不能称完整闭环真值。

本轮采用最小可解释的reference-template nominal proxy：只消费已完成历史B/H150的causal issued reference、commissioned belief，以及已登记参数；用同一sin²进度包络构造候选近似reference，计算名义inverse dynamics/allocator，导出phase/full JF、JM和reference运动量。真实tracking、contact、task与原motion资格均明确为UNKNOWN；不能把reference derivative当实际native jerk。只在原小trust domain内作为排序建议，最终资格由真实执行与原scorer决定。

事后机制重算另立身份，只用执行后estimated q/requested torque解释差异，不作为任何候选事前输入。所有事前预测在该candidate START前落盘并SHA绑定。使用历史名义reference是公开prior，不是目标候选未来轨迹。

## 三臂与公平性

A：有界直接pattern search，从固定坐标正负探测起步，以真实完整合格JF更新，违反原资格给予不可行。B：同域名义physics proxy，固定候选池中按模型力排序与距离筛选，不读取A/C反馈。C：physics prior加独立RBF GP残差；多输出预测JF/JM与最差motion ratio，预序更新，只使用自身已完成真实反馈；低样本不宣称泛化。每次模型身份与训练attempt ID保存。

共同初始设计4点(+0.5,0),(-0.5,0),(0,+0.5),(0,-0.5)，分别真实运行计入各臂预算；结果不跨臂共享。公开历史prior相同，均可读取同一已发布报告和合法causal模板；本轮强父工程复现对三臂共同公开。新增物理公平性与总历史/代理计算成本分别报告，不能称相同总成本。

每臂先12次，若其12次内出现至少一个完整原门合格且比强父下降>0.01 N·s的新候选，可仅该臂扩至20次。其它臂保持12，主比较固定12次前缀，扩展20单列。阈值为开发信号判据，不是临床或统计显著性。总优化≤60，独立冻结验证≤12，工程/恢复≤8，总物理START≤80，native≤8,000,000。预留独立冻结验证，最后45分钟不启大物理。单环境、可用RAM≥6GiB。

## 评分、停止与验证

原task/safety、matched motion/dose、timing与科学因果轴全部通过才进入正式JF收益排名。motion必须相对同链B按原MOTION_ACCEPTANCE_PROTOCOL/原compare计算，不能只相对H150使门变松。完整任务原19–19.06s时钟合同保留；逐phase/full JF、JM，tracking、v/a/jerk、excursion、终末overshoot、clearance/contact和actual torque同时报告。

主结论比较各臂相同12次预算下best qualified；C只有超过A与B的best qualified，且冻结重验真实执行通过，才可记LEARNING_ADDED_VALUE=OBSERVED_LOCAL，否则NOT_ESTABLISHED。学习预测验证使用整条candidate分组和prequential误差，重复相同x归同组。报告绝对误差、收益符号、排序和motion错误接受建议；不得随机拆相邻时间步。

冻结验证：各臂锁定best candidate后不再拟合/改参数；先同父exact repeat，随后在新合法prefix与其B/H150中验证（预算/资格允许时）；重复不算新患者或独立状态泛化。失败/partial仍计START和native计算，不给低力排名。原模型margin未知时禁止给安全预测PASS。

所有source/config/模型/候选SHA；旧研究树、Git HEAD/index/status保护；不commit/push/reset/stash/clean。硬停止、内存、磁盘、attempt/native预算优先于清单完成；普通候选失败继续其他臂。所有owned进程退出后STOP。
