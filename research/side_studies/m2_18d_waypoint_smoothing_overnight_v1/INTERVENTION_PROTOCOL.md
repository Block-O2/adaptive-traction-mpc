# 18D + targeted Waypoint smoothing intervention protocol

本轮为同一Human开发条件的隔离科学模拟。T0=2026-10-17 02:12:56（北京时间）；12:12:56以后不再启动新physics，13:12:56前完成退出。120次START含冷父、fork、失败、partial与验证；开发最多90次，至少30次预留。所有physics串行，完整live父状态fork，禁止由q/qvel重建父状态。任务未完成的结果不得进入完整J_F排名。

四组为原B、精确历史18D、B+S、18D+S。历史18D的18参数及RETURN槽1/2的差分图完整冻结。新增S放在原安全准备之后，以原MultiSegmentReference重新计算整条路径证书，并通过当前状态准入及原bridge/native receipt执行；不复用其他曲线的证书。

首批研究OUTBOUND槽3与RETURN槽3。B对应task约4.310–5.580 s与14.315–15.585 s；18D使用其自身的真实请求/拼接区间，精确数值在CANDIDATE_PLAN.json。它们覆盖已有force收益窗口和reference/actual速度变化段；最大历史收益窗口不等于B最高force窗口。新增内部点fraction=(0.2,0.4,0.8)，每点hip/knee q偏移最多±0.05°，保留内部原dq/ddq及外端q/dq/ddq、总suffix duration。完整task/phase duration另以实际结果检验，不能以其缩短获得降力。

每个base的形状独立由存档原reference的velocity TV目标做一次有界SLSQP设计，未使用force目标或新physics搜索。运行时只使用冻结点偏移与原causal状态。实际Human TV_v下降只是待检验的预测；reference变平不等于Human真的变平。base各自设计的S不能被当成同一个固定干预的2×2因果交互；若需宣称互补交互，必须增加固定点偏移跨base对照。

先检验B和18D原始trace身份；再检验两者的零shape多段对象与原曲线物理等价。分别保留正向smooth与−1/4幅度反向对照。反向控制不是等幅中心差分，拒绝证书的候选保留拒绝且不派发physics。离线fixture通过不代替runtime重新认证。

条件分支：完整task/原safety/motion/receipt均PASS且局部actual TV_v至少下降0.5%、局部force积分下降，才允许该方向半幅和exact repeat；O/R均有效才允许组合。每个有信息的窗口最多再做一次motion目标refinement。连续3–5个候选无新信息即停止方向。force下降但motion FAIL的结果保留，不能当赢家；只允许原门限下有界修复。

验证晋级规则在结果前冻结：所有原门限PASS，且相对匹配base完整降力至少0.5 N·s；或保留18D的force收益（相对18D最多增加0.1 N·s），同时完整actual velocity TV至少下降1%，combined jerk RMS不增加。另须报告各关节TV、speed variation、acceleration variation和jerk，不能互相替代。此工程研究筛选阈值不代表临床有效性。重复一致后冻结PRIMARY及更保守SECONDARY的参数、代码与选择规则hash，再做新合法prefix配对验证。验证失败不重命名PRIMARY。

所有force采用5ms真实存档左积分；native Human q/dq为0.25ms，a/jerk由既有gradient定义获得。完整phase积分、peak/RMS、tracking、moment、torque分量、request/activation/splice、reference/certificate/issued/native receipt分别保存。代数分解、相关、总轨迹干预效果与独立因果机制分别标注。

冻结不变：正式B、plant/Human/robot/contact/gravity/actuator、ROM、torque、任务/HOLD、truth firewall、40ms bridge、100ms lifecycle、source age、current admission、native ownership、receipt、carry/fallback及原task/safety/motion门。无RL/Q训练，无Git写操作，无历史失败删除。历史18D合法新prefix motion仍0/4；本轮不升级LEVEL2/LEVEL3、真机或临床资格。
