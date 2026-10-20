# 基线复核

权威执行环境为 `Ubuntu-Research-Verify`，主仓库 `/home/hank/coding/adaptive-traction-mpc-learning`，Side Studies `/home/hank/coding/adaptive-traction-mpc-side-studies`。Windows 当前目录是交付镜像，不是主 Git checkout。已读取权威 AGENTS.md；没有 Git mutation 权限，也没有作此操作。

工作包 A 的 12 个患者为已暴露历史：B 12/12 完整资格；H150 8/12；10 个完整积分配对平均降力 2.323%，范围 1.927–2.730%。P05/P08 的失败是相对 motion 工程资格，不是 absolute safety；P06/P10 在终末 knee-reference-constant 前提失败而中止，partial 不参加完整 J_F 排名。H150 的 moment、knee tracking 和 RETURN knee undershoot 在完整配对中均有代价。

上轮 learning 为同一 Human、11 个不同 prefix 父状态的 44 个动作结果；实际训练仅 6 个父状态。旧可分离线性 Q 的 state 项在动作比较中相消；后续显式交互模型虽然修复这一表达限制，测试仍全选 H150。真实连续重复 pilot 的记忆权重更新为 -1.553142 N·s，但动作未改变、相对固定 H150 额外收益为零。纯 PPO/SAC baseline 未训练。这些不是本包新实验，原负结果保持。

可复用内容：被冻结的源码闭包、执行/receipt/native 检查、完整 raw trace 的因果列、原 motion 协议、病人生成与静态模型校验。旧冷初始化/P0 单次完整轨迹可指导设计，不能冒充本轮连续 Trial 2 标签。旧序列化失败只能用于有界 harness 修复；旧回报不能当作未执行新动作的回报。

新包从工作包 A 按目录复制 source/code/deps/control，并仅重定位包路径。正式 B/H150、plant 与原阈值源码不编辑。新的 `bounded_planner.py` 是独立中间 knee intent 适配器，执行仍由原证书、admission、allocator 和安全层负责；不自动提升正式 B。

保护证据：`audit/GIT_BEFORE.json` 保存 branch、HEAD、完整 staged/unstaged binary diff、untracked 清单及 index SHA；`audit/HISTORY_BEFORE.json` 保存主仓库和 Side Studies 的历史文件 SHA。结案重新核验并列出任何不一致，不能仅用报告存在推断历史未变。
