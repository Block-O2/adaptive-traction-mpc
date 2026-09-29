# Architecture audit closeout

**SCIENTIFIC_MODE_MODERATE_REFACTOR.** 可以通过有限、可验证的 scheduler/lifecycle 重构实现 dual-mode；无需重写 controller 数学。当前只有静态设计证据，尚未实现或动态验证。

1. Wall-clock 经 catch-up 的旧 torque 积分、request/write expiry、RSS primary/fallback 选择、RETURN commit 和 cleanup 进入实际物理轨迹。
2. 单纯 pause 不消除上述 validity、legacy latency replay 和 terminal host horizon。
3. 推荐 B：保留 async worker，冻结整个科学 epoch 后收结果。
4. 采用 episode/state/phase/model/reference/request 版本；结果 receipt 与延后 activation 分别绑定原 snapshot 和新鲜验证 snapshot。
5. RSS C2/geometry 保留；Safe Fallback 继续处理已有覆盖范围内的算法失败，scientific host delay 不触发 fallback。
6. Commissioning 使用相同 torque law，计算后推进恰好5 ms；150 ms计算只增加真实耗时，不证明硬件能力。
7. ClockProvider/ExecutionPolicy/Scheduler 注入隔离；默认 realtime 保留，fake-clock differential tests 保护历史行为。现有 command >100 边界缺口必须显式处理。
8. 预计6–7个已有文件与3–4个新模块；详见 MINIMAL_REFACTOR_PLAN.md。
9. 必过 determinism、0/100/200/500 ms delay invariance、snapshot firewall、RSS staged activation、fallback fault、commissioning、controller/scorer equivalence、terminal/cleanup、resource interruption。
10. Value ranking 可在 frozen epoch 中干净接入，真实推理时间单独记录；本轮未实现。
11. Moderate，主要风险在 runtime orchestration，不在 controller equations。
12. Account-wide用量开始33%，已核查到34%；以STATE记录最新值，百分比非任务专属且工具只有整数精度。
13. 建议下一轮Sol High按该有界设计实施并通过验收；本轮完成后停止。

交付物为本目录所有md/json。执行过 cat/sed/rg、Git只读状态查询、usage读取、Python静态AST/哈希/文档生成与JSON核验。一次搜索使用不存在的 reference_stream.py 路径，随后使用实际 receipt_reference_governor.py；无源码修复。未运行production测试、MuJoCo、30-repeat、value/RL；新实验PASS/FAIL不适用。保留全部历史FAIL、WSL inconclusive与scorer证据。

本轮只新增文档/审计JSON。控制器、plant、task、安全约束、代价、solver、时长、noise、参数和配置未改；执行系统科学假设未改。新文档提出独立simulation-time模式假设，不能追溯改变旧证据。未stage/commit/push/merge/reset/stash/clean/delete，未分支切换，无hardware操作。

文档生成首次调用 python 时环境无该别名（exit127），改用 python3 成功；未修改环境。所有既有tracked文件以SHA256逐个核对；文档JSON解析与git diff --check结果见STATE。
