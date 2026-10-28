# 训练准入审计

ACTIVATION UTC：2026-10-21T06:07:13.137817+00:00。硬截止：2026-10-21T14:07:13.137817+00:00。物理收尾窗口：2026-10-21T13:22:13.137817+00:00 起。

原正式 launcher 的 inspect() 未修改并在隔离启动器中原样执行，核对模板、447 文件合同、完整父 ZIP/RNG/metadata 和硬预算。新启动器因本轮 STD 总量 80 与最后 45 分钟要求，版本化修正队列；未修改原模板或历史 ACTIVATION。

准入独立进程未 reset 物理或调用 Adam；两父 snapshot、actor mean/critic hash、log_std trainable 与 Adam 参数归属、空 pending、原分布与新分布密度检查均通过。旧 log_prob 在修改 STD 后被测试拒绝。R1/R4 保存轨迹重放、失败 floor、potential 闭环测试通过。

保存轨迹 Reward 重放 56 项，历史包 2300 文件 SHA 核验；预留流检索 588 项，无已执行命中。

log_std 初始化保留既有 Adam 一阶/二阶矩和 step；这是明确的继承合同，不等同于重置优化器。之后 std 可以变化；更新前 evaluate_actions 必须重现每个旧 log_prob，raw Gaussian 用于 PPO ratio，clip 只用于物理执行。

只接受完整 generation metadata 与 payload SHA；episode pending 保存 policy/reward 身份；Reward 分叉与 STD 改分布前 pending 必须为空。partial Adam 不自动晋级。

最终独立全量审计：True

源码：audit/launch.py、audit/ISOLATED_TEMPLATE_IDENTITY.json、ACTIVATION.json、source_versions/。原物理/任务/硬安全/准入/scorer 不变；没有 Git 写入、Stage2 或最终大规模 Campaign。
