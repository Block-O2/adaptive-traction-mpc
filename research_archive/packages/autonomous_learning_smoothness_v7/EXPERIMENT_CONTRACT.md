# v7 科学与执行合同

**CONFIRMED：** 唯一T0为2026-10-26 15:56:51.846771 UTC，硬截止2026-10-27 03:56:51.846771 UTC，见[ACTIVATION](ACTIVATION.json)。恢复、失败、子Agent及新分支均不重置。12小时是上限，不设全局仿真/episode/gradient额度；每个分支另登记身份、假设、有限预算、停止条件，初始队列结束不是全局停止理由。

## 原任务与保护

历史B/H150/18D/PPO/Critic、原scorer、Human/robot/cuff方程、原model/XML/guard和全部历史raw只读。独立复制闭包仅有登记的路径重定位、来源metadata/日志监管及上层策略差异，无历史hardlink写入。新case是预先声明的参数实例，不修改原case/物理方程，也不继承原资格。

实际继承matched任务为OUTBOUND 9.005s、HOLD 1.020s、RETURN 9.005s，共19.030s；不以文档整数9/1/9去缩短现任务。原HOLD、端点、ROM、torque、clearance、admission、receipt及motion门全部保留。JF/JM为原TASK含HOLD的5ms实测wrench模长左积分；native速度/加速度/jerk由原.25ms未滤波信号及原差分定义计算。失败完整和partial保留原积分与原因，均不作低成本成功排名。

额外质量界在最初结果前冻结：相对同状态完整V6PHASE（OUT0菜单使用同策略LATE_PHASE）髋/膝jerk RMS各≤1.001、native力模长变化率RMS≤1.004；双成本成功另要求JF严格下降、JM不增加且双方原合格。完整原不合格reference仅能作诊断比值，formal success=false；partial/缺失为NA，不能默认通过。额外界不是原motion门，原qualified基线即使不满足额外界仍保留权衡。

## 身份与分割

OUT1完整活内存fork保留原MuJoCo、belief/observer、scheduler、reference、lifecycle、guard与历史；须核对before/after/native/prefork及parent/B raw，不能以seed或q/dq相同代替。OUT0更早激活给出新动作机会，不是旧OUT1状态修复或新患者。host manifest/native integration/prefork causal/pure physical trace各有不同身份意义，不能混用hash。

DEVRT/DEVRC/DEVPC及LS/HS修订均为已暴露开发。二维九标签同真实父；跨组2351字段完整因果等价未证明，三维模型未训练。PFXV01/02在原nominal Human上共同事前冻结，真实native/causal/physical prefix互异并通过已知45个native过滤，但有历史缺trace/未snapshot覆盖限制；共享future RETURN0也按预冻结条件变化，非纯初态单因素或患者IID。

short_segments是原几何变体，原任务未缩短。原14菜单在首次结果前冻结；HOLDSS01零START导入失败、HOLDSS02标签映射失败后，HOLDSS03保持同case/seed/prefix/actions/合同，仅修正执行名字并先要求B exact raw重复。原B已在工程失败暴露，不能宣称完全未开封B测试；旧成本及缺RESULT证据均保留、不补资格。

CFH/CFL是两开发交叉参数实例：保留原各anthropometry/placement整包，只互换双关节K/D包；两case与七菜单在任一结果前共同冻结，原B先完整合格。只识别参数包闭环效应，非单独质量、K或D，也含commissioning响应改变；无患者因果结论。显式group→case_key/path/SHA及原合同硬绑定，禁止nominal默认回落。

## Learning边界

actor只读决策时已有的因果信息与预冻结模型/动作；true case/隐藏Human/native真值/未来tail、资格和receipt只作评价或真实结束后的标签。OUT0完整77D始终INVALID，目的限定三个commissioning scalar只在来源/时点/QA验证后用于stump；警告不删，不用OUT1回填。

stump原benefit为EARLY_H150完整原合格、JF<B、两关节native jerk各<B、力模长变化率<B；JM另列、不标量化。两CF原benefit均0，原V2开发门NOT_MET，CVNHS01/CVHNM01物理NOT_RUN。CFL metadata拒绝prospective NOT_TESTED不修补，资格替代标签只作失败解释，不能改原成功。静态driver/case准备不计训练部署或泛化。

方法有效、独立增量、计算效率和独立泛化四项结论分列；所有物理标签/训练计算计费。部分历史raw/模型缺档只给SUPPORTED，不制造旧结果；窗口/动作数不扩大独立患者数。

## 资源、恢复和结束

单物理supervisor/串行worker；offline最多3个单线程，owned CPU最多6/8核，RAM available≥6GiB、disk≥20GiB。PID/start_ticks、有限局部wall/attempt及唯一总截止、原子输出/checkpoint、唯一ID防覆盖/重启和失败保存有明确记录。本地断线只允许已启动有限任务继续，不假定Codex会持续思考或自动派发未来分支。

正式数值/物理/Agent任务登记START/END；若干前台static/metadata命令只有tool退出证据、未持久化完整PID身份，必须报告限制，不补造。HOLDSS01 preimport无worker SOURCE_MANIFEST及解释器/loaded-module身份缺口另列，不能声称完美metadata PASS。

不执行Git commit/push/merge/reset/stash/clean、正式Stage2、最终Campaign、扩容或硬件。科学停止需复核所有高价值已授权分支；到硬截止停止新计算，保留partial并安全退出。最终独立原积分/scorer/native、源/配置/模型/数据SHA、完整历史内容、START/END、日志追加前缀及owned退出全部核验后封包STOP，不自动下一轮。仿真不升级为硬件、临床舒适或患者安全。
