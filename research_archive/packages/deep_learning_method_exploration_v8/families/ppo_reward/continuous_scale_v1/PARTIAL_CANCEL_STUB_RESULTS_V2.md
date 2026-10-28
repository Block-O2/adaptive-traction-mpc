# V2失败闭合取消与mkdir持久化：STUB_ONLY通过

独立审查的两处确定问题已在三个新V2源修正，原V1及其全部188个冻结文件保持SHA不变。新源执行前AST/依赖/主授权冻结后，唯一获批≤60s fixture完成：实际END wall.123887s、self CPU.115729s，PID1151291/startticks60939146，单CPU。RSS20024→21612KiB；ru_maxrss612080KiB在START已有且未增加。

隔离的STUB_ONLY_PACKAGE共11情形：FAILED B而无完整parent raw、尚未dispatch B、已消费numerical RNG reservation、END缺hash但有原格式prefix证据均按取消门通过；显式parent_hash_equal=false不能被另一个true proof覆盖；缺prefix证据、pending hard=true、逐attempt review hard=true、unknown safety、未join child均拒绝。四个允许取消的情形没有生成B receipt或parent raw PASS，原pending/RNG对象SHA均不变。它们只是metadata可取消性检查，没有真正执行BetaArm.cancel。

另一个情形调用实际core V2 initialize流程、注入纯stub initializer，实际fsync日志严格为：run父目录fsync完成→RUN_IDENTITY→TRANSACTION_ATTEMPT fsync→stub initializer；无真实actor。四checkpoint字典带STUB_ONLY标记，不是Beta checkpoint或训练父。

精确API入口：actual evidence verify10、hard_gate10、cancel closure7、RNG chain32；core durable initialize1、stub initializer1、stub checkpoint dict4。stub adapter0，真实Beta import/initialize/restore/sample/forward/gradient/update、真实adapter、原raw/receipt/job、physics全0。所有合成START/END/FAILED worker/review/证明留在fixture隔离目录并带STUB_ONLY标记，不能当genuine物理证据。

commit完整原B/两closed job/每job10 START-END/完整parent raw PASS门保持原样；本次未通过stub冒称真实commit integration。V2 cancellation要求逐实际parent/child START的主原安全resolution以及每child父prefix证据，真实应用仍需主Agent独审、新source closure与真实授权。真实Beta clock未初始化，全局T0/截止不重置。先前V1发布故障、数学和owner fork检查继续保留各自范围与账，不能据这些机械检查宣称连续轴或真实控制收益。
