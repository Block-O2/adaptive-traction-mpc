# 根事务source与STUB_ONLY发布故障检查

新增source及CLI/API合同已冻结。唯一获批≤60s fixture通过，wall0.243875s/self CPU0.165806s；真实Beta初始化/restore/sample/forward/score/update、真实adapter、真实job/receipt、环境/physics均0，真实Beta clock仍未初始化。

| 故障/分支 | 已观察结果 |
|---|---|
| durable intent后、尚无computed bytes | CURRENT保持旧四臂；拒绝重fit；recover拒绝缺COMPUTATION |
| COMPUTATION后、部分STAGING、generation rename后、pointer replace前 | CURRENT保持旧四臂；保留已付费stub工作；从完整computed bytes恢复，全四一次发布 |
| pointer replace后抛异常 | CURRENT已经是完整四臂新generation；recover核对后幂等返回 |
| 第三private arm失败 | 三次已消耗stub optimizer调用保存在失败证据；CURRENT旧版；无部分publish或重fit |
| 四臂cancel | stub optimizer0、cancel4；权重不变，已消耗stub RNG标记保留 |
| 实际hard_gate源的三值检查 | true先于工程censor；review/receipt unknown不默认safe；原证据核验本身未用stub假装完成 |

五个具备完整COMPUTATION的故障情形都验证了恢复前后stub backend计数完全不变、四checkpoint bytes逐字节相等。六次recover API包括1次intent-only缺输出拒绝、4次实际metadata恢复和1次已发布幂等核对。没有调用真实Beta backend，未验证真实artifact adapter roundtrip、真实两job链、完整Beta构造/restore/梯度或物理部署。

精确instrumented core API entry（包括失败）：initialize8、prepare8、commit15、recover6、materialize17、pointer_replace15、write_bytes_new157。Stub单列：initializer8、stub actor objects32、stub adapter prepare16、stub compute7、stub optimizer23（20完成+3未发布失败）、stub cancel4；这些不是Beta模型初始化、训练或梯度。测试无真实fork/worker/MuJoCo。

实际PID1145715/startticks60804219，START→END RSS19808→21256KiB。ru_maxrss612080KiB在START时已经存在，END不变，不能归作本fixture峰值增量。原global hard stop1793114740.0保持；本次60s时钟只是stub fixture窗口。

每个故障保留原intent/FAILED、部分STAGING、COMPUTATION/seal、immutable generation/CURRENT及恢复证据，位于durable_publication_stub_fixture_v1/。旧Beta V2/axis/所有冻结sampling/categorical/onpolicy与root脚本SHA保持原样。最终source manifest另封存全部实际fixture文件及旧闭包验证。

未来真实init/prepare/update/cancel要先由root审新源码与合同、冻结主授权和真实plan，初始mean.5 Gate1完整原资格门仍有效。真实init需主授权新增initialization参数子对象SHA和显式initialization许可；init/prepare/commit不创建或重置原科学clock。recover无backend接口，只能发布已计算且seal通过的原字节。source及stub通过不能作为连续轴已可行、真实on-policy已训练或独立泛化证据。
