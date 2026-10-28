# 二十问科学审阅

最终科学审阅UTC：2026-10-21T04:02:39.786996+00:00。主研究START为2026-10-20T18:52:04+00:00，最终STOP/END为2026-10-21T03:58:41.200797+00:00，实际9.110334小时（约9小时6分37秒）。最后冻结队列于2026-10-21T03:45:55.851479+00:00闭合；其后为保存证据独立复算和审计。最终manifest封存/独立字节核验另记实际时间于PACKAGE_VERIFICATION.json。

H2/R0与R1都保住两个所选成功父的已测mean长窗口；H1只保住一个父。最终预锁R1/60的两个模型在四条未见动作流中各完成3/4，不能宣称随机稳健或全面性能冠军。G4_STRICT_PASS=FAIL，Stage2和正式Campaign仍NOT_READY。

以下mean均为完整19.03秒同父开发参照。JF/JM为原5ms传感器左积分、覆盖真实已执行区间；Human运动来自0.25ms native状态。每对运动值按hip/knee顺序。没有新B/H150 live matched收益资格。

|策略|父seed|JF N·s|JM Nm·s|对原050 JF%|对原050 JM%|tracking RMS °|jerk RMS °/s³|
|---|---|---|---|---|---|---|---|
|原050|1495656323|1446.792925|101.532803|0|0|0.48888 / 0.55496|416.43535 / 1061.28382|
|RETENTION_H2/60|1495656323|1435.949543|103.494314|-0.749477|+1.931898|0.48597 / 0.47244|381.02585 / 881.50815|
|RETENTION_R1/60|1495656323|1438.416202|103.108369|-0.578986|+1.551780|0.48487 / 0.50320|381.91328 / 907.37959|
|原050|1630784693|1437.053824|102.749452|0|0|0.50563 / 0.58036|388.44481 / 810.60601|
|RETENTION_H2/60|1630784693|1432.539740|103.621209|-0.314121|+0.848430|0.50085 / 0.63000|379.25315 / 797.37817|
|RETENTION_R1/60|1630784693|1429.253998|104.463512|-0.542765|+1.668195|0.49658 / 0.63344|362.35665 / 778.07537|

最终固定动作流逐条如下；失败的剂量明确为partial，不能与完整任务争优。共同RNG不表示不同物理初态，各父四次都恢复同一个锁定模型。

|父seed|动作RNG|原任务结果|TASK s|JF N·s|JM Nm·s|积分身份|
|---|---|---|---|---|---|---|
|1495656323|2026102191|COMPLETE|19.03000|1396.374953|105.384105|COMPLETE_TASK|
|1495656323|2026102192|COMPLETE|19.32500|1558.389179|92.419439|COMPLETE_TASK|
|1495656323|2026102193|ABORTED|17.91000|1419.053733|67.394006|FAILED_PARTIAL_TASK|
|1495656323|2026102194|COMPLETE|19.03000|1417.636282|104.124934|COMPLETE_TASK|
|1630784693|2026102191|COMPLETE|19.03000|1419.614310|101.566881|COMPLETE_TASK|
|1630784693|2026102192|ABORTED|0.00500|0.394471|0.063241|FAILED_PARTIAL_TASK|
|1630784693|2026102193|COMPLETE|19.07500|1527.684211|77.602723|COMPLETE_TASK|
|1630784693|2026102194|COMPLETE|19.03000|1416.696491|104.607483|COMPLETE_TASK|

1. **本轮实际研究运行多久？** T0为2026-10-20 18:52:04 UTC（北京时间10月21日02:52:04），STOP/END为2026-10-21T03:58:41.200797+00:00；START→END共9.110334小时。390训练attempt、52冻结评价attempt、42,865,780 native steps、6,885 RL decisions、1,760真实Adam；全部442物理attempt已结算，无open预留。另80次合成Adam属工程测试，未计MuJoCo训练。所有训练在最终pair锁定前结束，未越过UTC04:07:04新训练截止；所有关闭与封存计算受04:52:04硬停约束，最终独立核验时间见PACKAGE_VERIFICATION.json。

2. **为什么选择这些实验分支？** 两个原成功050在Control继续30集后mean均失败，先只改LR检验H1；单集/短rollout、singleton与弱critic问题推动H2完整episode聚合。共同PPO上再测R1的完整成功与剂量平衡、R2的二次potential和更强online运动代理，最后用R3整体单位除30检验数值耦合。H2/R1同窗口延长到60，再先锁模型后打开最终8流；没有无界参数搜索。

3. **H1是否减少PPO退化？** 只有部分支持。149的10/20/30 mean全部失败；163三个mean均完整19.03秒。两父30 sample均失败，原Control80 mean均失败，因此不能授一致两父保持。H1训练完成14/30、15/30，446/451 decisions、200/204 Adam；Control对应19/30、11/30、561/424 decisions、220/188 Adam。严格各5集复演通过后复用原Control51–80，不把历史重用计入新增成本。H1较小局部KL没有保证保持，PPO ratio clip fraction与动作边界clip分开统计。

4. **H2或其他稳定性方案效果如何？** H2/R0、LR3e-4、跨完整episode>=64 transitions、4epochs、batch16（singleton尾并前批）、gamma1、GAE.95、clip.2、joint norm clip.5、vf.5、entropy0、target_kl=None。两父已测30/60 mean均完整；60最新sample也完整，但163/30 sample失败仍保留。各60训练累计28/60完成，935/922采样=优化transitions、248/244 Adam，0singleton、终末pending0。实际Adam高于旧失败Control，单凭更少总更新不足以解释保持；组织/频率/数据访问混合，尚无唯一优化根因。H2未测10/20，也未证明每个中间或超过60的保持。

5. **Agent生成了哪些Reward版本？** R0原pilot作对照；R1为2Δp、成功20/失败−15、0.0005JF+0.005JM+0.02V及失败cost floor15；R2改为2Δ(p²/3)、V权重.10；R3把R1所有项和floor统一除30。V是online Human估计加速度平方积分代理，不能替代native运动评价。失败potential0，成功p3属于显式成功bonus；gamma1下正确计phase差分，不声称跨终末身份的policy invariance。完整公式/权重/旧新source SHA及实际父配置见REWARD_CANDIDATES.md与REWARD_VERSION_MANIFEST.json。

6. **每个Reward为何接受或拒绝？** R1/R2各10/30两父mean/sample均完整。R1较简单linear potential及当前native jerk使其优先进入60，R2保留短窗口备选；R2四个关节/父组合的jerk RMS都高于R1，同时改变potential和V，不能唯一归因。R3四条10集评价均完整，但149 mean JF−0.279504%/JM+1.368140%，163 JF+0.325382%/JM−1.241229%，没有一致force或Pareto优势，不延长。R3两父采样172/160、优化152/160、pending20/0、Adam40/44，未作十集额外flush。三个新增候选、两轮反思修订，无R4；不比较不同Reward总数值或value loss来选优。

7. **哪些策略保持原runtime完整任务成功？** H1仅163在已测mean窗口保持；H2两父30/60，R1两父10/30/60，R2两父10/30的mean均保持。R3仅10四种父/模式完成，不能当较长保持。R1最新60的mean/sample开发四条均完成，最终新流各3/4；完整与失败逐job保留。不同checkpoint、模式和开发/最终流不能合并成单策略成功率。

8. **是否真正降低完整JF？** 在相同父、19.03秒mean开发任务上有小幅描述性下降：H2/60为−0.749477%/−0.314121%，R1/60为−0.578986%/−0.542765%。R1/30为−0.534922%/−0.349395%，R2/30为−0.471300%/−0.354002%。最终随机完整JF范围149为1396.375–1558.389、163为1416.696–1527.684，不能用某条最低值代替整个策略或宣称超过原B/H150；不同duration/模式不计算直接收益，失败partial更不能争优。

9. **JM与Human平顺性是否恶化？** 存在明确取舍。H2/60 mean JM较父+1.931898%/+0.848430%，R1/60为+1.551780%/+1.668195%。R1两父mean jerk RMS均低于原父，但163 knee tracking RMS0.633442°高于父0.580361°，RETURN knee overshoot2.360245°；H2对应0.629999°及2.653867°。R1首父mean jerk为381.913/907.380，sample为441.075/1148.933°/s³，不能混称同样平顺。速度/加速度/jerk RMS与峰值、terminal误差和overshoot全部另列；jerk仅诊断，没有自造阈值或全面motion改进结论。

10. **与父checkpoint相比有什么变化？** 原050始终保留，所有分支完整恢复policy/Adam/Python-Numpy-Torch RNG/计数。R1累计60训练为21/60、31/60完成，893/872 transitions、240/236 Adam；H2对应28/60各、935/922、248/244。30→60从已发生030终末flush的状态延长，并非无flush连续60。共享obs上的policy/actor/critic漂移另见CHECKPOINT_POLICY_DIAGNOSTICS.json。四Reward首80/77条物理输入、full prestate和更新实现相同、各20真实Adam；R3 actor L2为R1的1.887/1.953倍，KL却为2.576/0.230倍，参数距离与功能漂移不可等同，不能给唯一根因。

11. **deterministic与stochastic差异是否改善？** 开发端点的模式一致性比H1更好，但随机稳健仍未建立。R1/60两父mean/sample dev1均完整；在选择与SHA锁定后打开的2191–2194各完成3/4。149/2193在17.910秒RETURN几何拒绝，163/2192在0.005秒初始OUTBOUND几何拒绝；相同RNG也不意味着同样结果。Gaussian std仍约1，实际sample+clip和mean+clip不同；没有真实STD变体试验，.2/.1只做过解析反事实。最终未见结果后没有训练、改Reward/PPO/std或换候选。

12. **是否存在reward hacking或安全异常？** 已记录attempt均通过原独立Reward/执行/receipt/运动安全检查，没有发现新的正失败回报、未来Human truth或已执行硬安全漏洞；仍不推断所有未见路径安全。失败R1累计约−30、R3约−1来自单位，不能作质量排名。原准入拒绝是失败身份，不等同执行碰撞；fallback事件按原标签保存。极短0.005秒partial JF0.394471/JM0.063241明确失败。关闭后已由独立进程从保存raw重新计算全部52冻结结果，原终止、Reward、native ownership、receipt、JF/JM和真实Human安全检查全部通过；覆盖完整任务及所有失败partial，0新物理/Adam。冻结policy前后SHA相同、实际0更新且原worker执行optimizer前后hash断言；未虚构不存在的单独post-optimizer序列化文件。

13. **是否有独立合法初态改善？** 没有。当前冻结PPO reset seed/options不改变nominal物理初始化；task.start字段同时改变RETURN目标，未擅自使用。BLOCKED_CURRENT_FROZEN_PPO_INITIAL_STATE_INTERFACE。最终四RNG仅动作流holdout，不能冒充独立物理初态、患者或人群泛化。

14. **多seed是否一致？** H1不一致；H2和R1在两个所选成功父的明确长mean端点一致，最终R1新流各3/4但失败RNG/阶段不同。R2只到30、R3只到10。它们是两条成功050的继续训练研究，不是从零三seed复现，也不是患者群体统计。两个不同模型的四条流不能合成一个稳健率。

15. **哪个checkpoint、Reward、PPO最值得保留？** 原两050、H2/R0两060与R1两060全部保留。最终协议在任何60结果前锁定；H2/R1同任务/保持/最新模式层且有剂量和运动trade-off，按预定诊断优先选择R1，未宣称Pareto冠军。固定pair为runtime/jobs/RETENTION_R1_seed1495656323_to060/checkpoints/episode_060与相应seed1630784693路径；全部ZIP/RNG/metadata SHA见FINAL_FROZEN_SELECTION.json。配置为R1、LR3e-4、aggregate64及上述原PPO/std。最终各3/4仅使其成为保留的mean保持与随机失败机制候选，不能晋级全面随机稳健或正式训练冠军。

16. **Stage2科学资格具备吗？** STAGE2_READY=NOT_READY。DEVELOPMENT_TRAINING_VALID、明确nominal mean保持、完整mean force小降、观察到的motion安全审计与正式资格分别列出。开发成功、有限新动作流以及离线scorer通过都不能代替Stage2。

17. **G4和live matched仍缺什么？** G4_STRICT_PASS=FAIL：历史自然极端失败路径及严格安全全矩阵仍未闭合。新PPO缺原同父prefix的完整可移植状态恢复和B/H150同链live matched执行证据。固定1adb1de177d6f5f32de6d01c4e629cbfae9ce121的原离线B/H150 scorer复现PASS继续有效，但没有转换成新PPO优于它们的证据。

18. **值得开始正式大规模训练吗？** 现在不应开始，FINAL_CAMPAIGN_READY=NOT_READY，用户也明确未授权。本轮得到两个成功父的mean保持候选，却保留随机动作反例、force/moment/motion取舍以及G4/live matched/独立初态缺口。没有启动最终Campaign、下一研究包、硬件动作、迁移或扩容。

19. **CCX33仍适合后续研究吗？** 适合当前单物理环境、单Torch/BLAS线程的CPU开发。已关闭job测得约训练1401、评价1281 native steps/s（含保存/审计开销，非保证）；可用RAM观察最低约27.73GiB，高于6GiB准入门，磁盘和输出也有硬限。完整吞吐join见audit/CPU_THROUGHPUT_SUMMARY.json，最终资源与逐job时钟见RESOURCE_USAGE.json；扩大预算前应按实测吞吐核算，未租赁/扩容。

20. **下一轮最值得解决什么？** 唯一建议：固定R1/60两模型，检验Gaussian探索尺度对OUTBOUND/RETURN准入拒绝的贡献；下一包若获授权，仅比较原std与一个预声明std=.2冻结消融，Reward/均值/物理/硬安全不动，不训练、不做尺度网格。使用全新预锁开发/未见动作流，当前2191–2194已成为已见证据，不能循环调参后再作测试。它只隔离动作分布机制，不保证解决唯一根因或正式资格。详见FINAL_NEXT_RESEARCH_DECISION.md；本轮没有执行该建议。

最终关闭核验：52/52冻结保存raw独立复算通过，442/442物理attempt账目闭合；69,384历史保护文件与447运行合同文件经关闭程序及另一独立Python进程逐字节核对，均无差异。75个内容地址source bundle、141个普通checkpoint ZIP/RNG generation、118个pre-Adam generation及完整输入SHA核验通过。固定Git HEAD/branch/科学工作树与起点一致，FETCH_HEAD元数据范围限制如下保留。全部owned物理worker、常驻服务、观察/队列/重算进程和finalizer已按PID启动身份核对退出。最终人工内容审阅后重新封存；最终全文件SHA、精确文件覆盖与resealer退出证明的权威记录为PACKAGE_VERIFICATION.json。

工程与溯源范围：正常完整pending已有真实59+24=83顺序恢复和连续/分段合成全状态等价证据；partial/emergency父在接口/预留前拒绝。显式pre-Adam恢复入口存在，实际partial-Adam故障重放未运行，不能称测试通过。早期Control保存时磁盘Reward SHA不能证明已导入模块重载，原导入源码按创建记录精确恢复、R0语义与严格复演一致；之后使用内容地址bundle。原队列物理闭合后的重复状态字段工程异常已有保留与零物理修复核验，不掩盖旧错误。

Git保护范围：固定HEAD/branch/科学工作树身份与原科学文件字节保护单独核验。`.git/FETCH_HEAD`在运行期间更新，实际命令记录未观察到fetch、来源未能归因；未恢复/删除它，也不声称所有Git元数据未变。见audit/GIT_METADATA_UPDATE_ATTRIBUTION.json。没有自动commit/push/merge/rebase/reset/stash/clean或主科学树覆盖。
