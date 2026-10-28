# R3十集单位消融实际反思

记录UTC：2026-10-21T02:18:50.625223+00:00。只测试R1整体除30这一尺度；成功/失败、progress、force/moment、online variation及floor全同除30。旧critic/Adam保持共同原050状态，PPO和原动作/物理/安全未改变。

1. **假设是否支持：** 两父十集后的mean/sample四条开发评价均完成，支持当前短窗口名义任务。两父首80/77条物理输入、prestate、PPO hyper和update AST精确匹配R0/H2、R1、R2，实际各20Adam；单位变化确实改变优化。不能由四个不同策略/模式结果宣布泛化率或更长保持。

2. **是否退化：** 已测十集mean未丢完成；训练sample各5/10、4/10完成。149 mean完整JF较父−0.279504%而JM+1.368140%；163 JF+0.325382%而JM−1.241229%。没有一致force改进或Pareto优势。149 mean jerk RMS为420.676/993.795，163为388.711/824.366°/s³；部分指标高于各自原父，不称全面平顺性改善。

3. **是否延长：** 本包不延长R3。预声明此消融最多各10集，剩余优先做R1与R0/H2相同60窗口的保持，再固定最终8条流。R3没有30或60证据，不靠短窗口/较低value loss挤掉经过更长测试的家族；完整模型和pending数据保留为数值诊断备选。

4. **修改PPO还是Reward：** 此次只改变单位，不继续尺度网格，不重标定critic/Adam、不改std。实际首更新actor参数L2在两父分别为R1的1.887/1.953倍，Gaussian KL却为2.576/0.230倍；参数距离和函数漂移不能等同，也不能用单点clip梯度给唯一归因。GAE、joint clipping、旧critic和Adam状态未分别隔离。四Reward真实模型/SHA/输入证据见R3_CONTROLLED_UNIT_EFFECT.json及两个原始audit文件。

5. **额外seed：** 当前保持问题仍以两个成功050父为共同对照，不是从零三seed。先完成已登记R1两父60验证，比增加R3新seed或从零训练更直接。独立合法初态仍不支持，没有改任务/Human去伪造泛化。

6. **污染与数据边界：** 此筛选只使用已见dev1=2026102101。最终2191–2194四RNG×两父仍未打开，8次/1320000保守native继续预留。原R0–R2定义不覆盖，新完整模块对它们输出逐项等价并单独保存双source SHA。冻结评价共同使用原R0算术，不能拿R3约−1失败回报与R1约−30作质量排名。

7. **剩余时间最有价值的工作：** R3队列正常闭合后，按当前源/配置与实际预算再准入R1两父30→60。当前全部未来保守native和390训练/52评价预测仍在硬限内；如新异常改变预算，则按真实状态处理，不能自动扩限。最后按预锁规则选固定checkpoint对，再做8条流与完整封存；9h15后不开新训练，10h硬停，不启动下一包或正式Campaign。

|父seed|训练完成/10|sampled|实际优化transitions|完整pending|Adam|PPO.train/epochs|
|---|---|---|---|---|---|---|
|1495656323|5/10|172|152|20|40|2/8|
|1630784693|4/10|160|160|0|44|2/8|

149的20条最后完整episode数据保存在010 pending generation，没有因十集筛选额外flush或冒称已经优化；生成policy/数据SHA及完整边界由恢复合同验证。163在第10集正好按原>=64规则发生更新，44Adam来自不同实际batch长度，不是另加十集终末flush。全部已做优化都保持原4epochs、0singleton。

两mean TASK均19.03秒；sample为19.935/19.695秒，JF分别1457.209479/1475.464890，只作不同duration的描述。全部tracking、velocity、acceleration、jerk峰值、终末误差及overshoot在R3_REWARD_RESULTS.json；不删除失败partial，也不自造通过阈值。全部20训练原独立安全/执行/Reward核对通过，完整policy/Adam/RNG恢复通过；这些结果仍不授G4、live matched、Stage2或正式Campaign资格。
