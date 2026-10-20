# 后续Q-learning数据合同草案（仅设计）

本轮不训练、不导出可宣称RL-ready的数据集。可以准备来源与字段合同，优先工作仍由NEXT_RESEARCH_DECISION决定。

state只能使用请求时已存在的因果估计、belief/model身份、reference与receipt、tracking估计、phase/剩余时间/slot、原source age与准入状态。真实Human qpos/qvel、未来累计代价与验证标签单独保存在evaluation命名空间，禁止进入在线特征。

action保存完整18参数和RETURN plateau及phase/slot、可选Waypoint shape；必须分别保存意图、证书、激活、issued reference、真正applied receipt。被拒动作与后续B/carry/fallback不能被错误标为相同executed action。当前固定18D不是已学习的state-conditioned策略；旧可分Q(s,p)=a(s)+b(p)不能通过公共state项声称学到状态交互。

反馈按真实receipt所有权区间积分cuff force，含等待/carry；完整TASK JF是整任务终点评价，不能分配到任意单个proposal。部分/timeout/安全停止保留已观察积分、缺失后缀与原因，不以零填充奖励。motion、task、absolute safety、tracking/moment/ROM/clearance及causal资格分别存储，不能仅用force奖励吞掉约束失败。

split按Human/model、合法父状态与prefix家族分组；同父fork和确定性repeat不得跨训练/验证泄漏。同一Human的不同prefix不增加患者数。先证明传统协调的适用域、动作真正执行和区间credit assignment，再另立采集合同；本草案本身不满足启动Q-learning的前提。
