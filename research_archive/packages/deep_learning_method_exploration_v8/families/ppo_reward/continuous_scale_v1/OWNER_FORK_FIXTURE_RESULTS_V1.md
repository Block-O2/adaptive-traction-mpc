# SYNTHETIC_ONLY owner fork机械检查：PASS

主Agent明确批准一次≤60s。fixture与实际提取源SHA先绑定，AST通过后运行；所有旧源与Beta/Gate1新源均未改。实际wall0.045700s，self CPU0.029445s，child user0.004125s/system0.010539s。

从实际gate1_sequence_candidate_v2.py及beta_sampling_sequence_candidate_v1.py提取owner_pid/startticks赋值、assert_owner、put和GeneratorExit handler原AST；Beta put依赖的canonical也从实际common源AST提取。没有import Beta、worker、categorical或MuJoCo模块，没有调用完整真实sequence/adapter。Synthetic save仅写明示sentinel，不含learner、真实回执或on-policy伪证据。

| 源 | child关闭方式 | child共享文件写 | owner取消后sentinel |
|---|---|---:|---|
| Gate1 V2 | explicit close | 0 | 精确保留 |
| Gate1 V2 | del generator + gc.collect | 0 | 精确保留 |
| Beta sequence | explicit close | 0 | 精确保留 |
| Beta sequence | del generator + gc.collect | 0 | 精确保留 |

4个真实Linux child还各自尝试直接调用提取的put，均由实际assert_owner抛GeneratorExit拒绝。测试writer本身故意没有fixture owner过滤，若被测源允许child写，真实共享jsonl会记录child PID并失败；结果实际只有owner的8条共享写（READY4+owner cancellation4），child写0。child另用4条pipe report通信，未作为共享pending/error写入。child GeneratorExit handler4次静默返回，owner handler4次保留既有sentinel。

工作账：真实fork4、synthetic extracted generator实例4、提取put调用12个已核对路径（8owner成功、4child被实际guard拒绝）、full真实generator0、Beta初始化/restore/sample/forward/score/update0、环境/MuJoCo/physics0。fixture自己的60s机械时钟与真实Beta scientific window分开；真实Beta clock仍未初始化。

原START/END、各实际共享写jsonl、提取后编译AST源、source binding与主授权在owner_fork_fixture_v1/和OWNER_FIXTURE_*文件。本检查证明这两个owner/GeneratorExit分支在真实fork下的写入权限，不证明完整物理调度、所有save状态内容、Beta adapter真实artifact roundtrip、采样、更新或原资格。Gate1真实工程门和主sampling/update批准仍是独立前置条件。
