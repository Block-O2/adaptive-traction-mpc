# iHEAR Lab — Smoothness Critic Integration v6

最终。T0=2026-10-26T09:55:17+00:00；六小时硬截止=2026-10-26T15:55:17+00:00。所有新实现与raw隔离于本包，原guard和任务/运动门保持。

1. **CONFIRMED** — 研究至STOP经历5.535小时；含最终manifest/独立验证的准确总wall见END.json.actual_total_wall_seconds。真实MuJoCo START/END=149/149，新增native=9353000步（2338.250模拟秒）；完整候选=123，冷启动父进程=26，其中7个只采合法prefix。动力学仿真不是硬件或患者试验。

2. **CONFIRMED** — v5 7266文件manifest一致；五个代表方案从raw重算JF/JM与native jerk吻合；已复用的VAL03前缀B/COMPOSE原trace、native与receipt逐字段复现通过。详见audit/BASELINE_RAW_RECOMPUTE.json、audit/V5_MATCHED_RAW_REPRODUCTION.json。

3. **SUPPORTED** — v5合法平顺性方案由原raw及匹配完整轨迹复现；新两组BLEND/C比较中通过原门=2/2，但BEST作为整策略参照通过的组数=1/2。不能把不合格BEST当成功强基线。固定阶段方案追加复核=COMPLETED_TWO_PAIRED_CONFIRMATIONS。2组配对中2组通过原门及额外代价上限；相对COMPOSE平均ΔJF=-1.309722 N·s、ΔJM=-0.152900 Nm·s。

4. **CONFIRMED** — 名义v5 COMPOSE的native力模长变化率RMS由强固定19.334070降到18.222197 N/s，约低5.75%；新BLEND和固定阶段方案相对COMPOSE均略回升，保持多数原收益而非每项同步下降。力向量、力矩变化率与峰值另列，未推断患者舒适度。

5. **CONFIRMED** — 名义COMPOSE相对强固定为JF约+8.058633 N·s、JM约−1.904880 Nm·s。本轮BLEND相对COMPOSE平均JF−1.681372、JM+0.031123；固定阶段方案追加复核=COMPLETED_TWO_PAIRED_CONFIRMATIONS。2组配对中2组通过原门及额外代价上限；相对COMPOSE平均ΔJF=-1.309722 N·s、ΔJM=-0.152900 Nm·s。但固定阶段方案相对原B平均JM仍+4.595037 Nm·s，不能称对所有基线全面低负担。

6. **CONFIRMED** — Critic加入因果累计测量成本、observer峰值及guard/context历史；训练折内缩放加物理下限，保留时间；成本/风险分开且后续策略标签隔离。风险父状态别名已纠正。精确native在线资格、完整fallback历史和充分状态仍未闭合。

7. **CONFIRMED** — 四组主冻结新prefix中Critic原门通过4/4；相对1秒改变实际轨迹4/4，相对训练固定phase规则改变0/4。HANDOFF/PATTERN标签别名不计物理改变。选中动作的同状态完整执行复现=PASS，未被重称未见测试。

8. **SUPPORTED** — Critic相对1秒短窗在双方合格状态平均少JF=0.879994 N·s；相对训练冻结强phase规则平均少JF=0.000000 N·s。独立超过1秒且超过该固定规则>0.02 N·s的状态=[]。恢复长期排序已在真实完整tail观察，未建立强固定规则无法替代的增量价值。

9. **NOT_TESTED** — 已封存的训练父状态重放LEGACY_BOUNDARY_O3中，Critic选RELATIVEP，完整原门PASS；1秒选SPEEDP，原门FAIL，其H前已有native速度/加速度门失败=True；直接guard历史规则选RELATIVEP，原门PASS。离线完整合格参照为RELATIVEP。O3与已暴露TAILOT实际父状态相同，已排除独立验证；两个真正新状态均无失败动作。故独立出程修复仍NOT_TESTED，不把训练重放的成功当泛化。

10. **CONFIRMED** — Critic完整菜单节省=0。独立的传统执行前库筛选实际省略7个唯一候选完整续跑，对照为预登记去重枚举；未建立研究训练/审计成本摊销后的净节省，也不归因于Critic。

11. **SUPPORTED** — 传统单一RULE状态=NOT_RUN。未运行部分不制造结果；原因见ADAPTIVE_FIXED_RULE_RESULTS。固定阶段方案追加复核=COMPLETED_TWO_PAIRED_CONFIRMATIONS。2组配对中2组通过原门及额外代价上限；相对COMPOSE平均ΔJF=-1.309722 N·s、ΔJM=-0.152900 Nm·s。固定phase规则与事前库筛选提供直接价值；本轮新BO、ILC、PPO和Q网络均NOT_RUN，不宣称跨合同算法普遍优劣。

12. **CONFIRMED** — 确认B上游接平顺性后续可导致15个完整动作违反excursion；匹配COMPOSE上游恢复资格。还确认微扰配置未必改变实际父状态：O3已降格为TAILOT训练父状态重放、原独立声明封存。原失败峰值早于H，低尾部成本不能抵消；父状态别名CV、错误jerk max_abs标签和时钟微小scale等问题均有保留审计。

13. **HYPOTHESIS** — observer峰值与guard历史是否足以预测完整native资格、改善是否能跨Human泛化、滚动交接是否独占波动来源，以及临床舒适度影响，仍无充分验证。

14. **SUPPORTED** — 新证据覆盖同一nominal Human的4个主冻结prefix、2个真正新的旧B出程状态、2个BLEND确认及筛选/固定阶段配对。O3与旧训练prefix实际相同，已剔除独立证据；不能把配置微扰、commissioning seed或训练父状态重放称新患者，自适应配对也不冒充未见模型选择测试。

15. **SUPPORTED** — 本轮暂停该成本Critic的扩张，保留冻结模型、raw与诊断代码。它能纠正短视排序，但未超过强固定阶段规则；风险头仍有跨父状态漏检，不足以替代原门。继续学习前先解决合法状态排序需求或原门的在线可观测性，不自动改名Q/PPO继续训练。

16. **SUPPORTED** — Learning定位收窄为有因果状态支持、能改变实际决策且超过强规则的预测补充；更小RMSE、更多标签或换Q/PPO名称都不能代替独立控制价值。

17. **SUPPORTED** — 下一轮最具体问题：以本轮通过的固定阶段平顺性方案为起点，保持原完整门和预先设定的髋/膝jerk及cuff力变化率保留要求，只对回程交接时间作小范围配对试验，检验能否继续同时降低JF/JM；若没有强phase规则解决不了的实际排序翻转，继续采用传统规则。精确native风险在线信息另作接口研究。

18. **CONFIRMED** — 根日志已核对v5完整开始/转折/结束且未重复；本轮开始、实际机制转折及实际结束均只追加。audit/JOURNAL_APPEND_ONLY_FINAL.json验证原20376字节前缀逐字节不变，保留可接受后续追加的封包snapshot。

19. **CONFIRMED** — 所有owned物理子进程、supervisor、编排与评分服务已结束；audit/OWNED_PROCESS_FINAL.json剩余活跃owned=0。END与PACKAGE_VERIFICATION封包、只读VERIFY_PACKAGE复核，终态STOP，不自动启动下一轮。

详细证据：SMOOTHNESS_BASELINE_COMPARISON.md · CRITIC_MODEL_AUDIT.md · CRITIC_STATE_AND_LABEL_AUDIT.md · CRITIC_DECISION_VALUE.md · OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md · RESOURCE_AND_ATTEMPT_ACCOUNTING.json · PACKAGE_VERIFICATION.json。

CONFIRMED：O3身份审查先报告FAIL，随后按实际raw证据重分类，原失败审计保留为audit/O3_ACTUAL_PARENT_ALIAS_ORIGINAL_FINDING.json；修订后的独立性PASS只覆盖仍被声明独立的4+2状态。不能将PASS解释为O3的新状态资格。

实际结果图：[平顺性](figures/01_SMOOTHNESS_RETAINED.png) · [冻结决策](figures/02_CRITIC_DECISION_VALUE.png) · [真实候选尝试](figures/03_PROSPECTIVE_ATTEMPTS.png) · [native时序](figures/04_NATIVE_WAVEFORMS.png)。同名PDF可独立导出。
