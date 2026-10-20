# 本地与云端同步差异

本轮未连接德国服务器，无 SSH/SCP/rsync、远端 shell、训练或部署。GitHub 同步只说明本地审阅源码已上传该分支。

## 已直接核实的本地差异

RL-B CPU 包 450 文件与原本地封存 manifest 全部一致。对其中 414 个 source 文件逐项比对本轮初始 WSL 主仓库，2 个不相同/不存在：

| payload 路径 | 主仓库存在 | 逐字节相同 |
|---|---|---|
| source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/rl_native_proposal.py | False | False |
| source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py | True | False |


新增 rl_native_proposal 及 runtime_sac_expert 的 native callback 版本在隔离 RL-B 包内保存；没有覆盖主仓库正式 runtime。SOURCE_COPY/VENDOR 和 payload SHA 清单保留，但本轮没有证明该本地封存包就是服务器当前版本。

## 必须回收、当前 UNVERIFIED

- 德国服务器当前 branch/HEAD、dirty diff、untracked 源码、依赖/runtime 锁及实际部署源码 manifest。
- 最近三 seed、共 240 episode 的精确 train/evaluate/native-event/reward/checkpoint/seed-accounting 实现、命令和合同版本。训练数量来自用户背景，本轮没有逐 episode 回收验证。
- 全部对应 checkpoint generation（policy、optimizer、RNG、计数、父恢复链）、原子完整标记及 SHA。
- 每 episode 原始 trace、外置 native journal、causal receipts、START/END、失败/partial、initial/final frozen evaluation 与资源 accounting。
- 服务器上原 B/H150 scorer 和其 import 闭包、fixtures 与本地上述原件的逐文件身份；若缺原 scorer，只传原版本，不造替代实现。

不能断言具体服务器文件已被本地更新，也不能把训练成功或 Git push 当成 server/local numerical parity。没有最新服务器 manifest 就无法精确枚举已回流/未回流文件；本清单的全部近期云端身份为 UNVERIFIED。

下一轮最小差异传输：先只回收服务器 source/hash/index/diff 和 episode/checkpoint 总台账；本地按 SHA 与本同步分支及 sealed RL-B manifest 比较，再仅传不同源码与必需数据。大 raw/checkpoint 使用独立归档，不经 Git，不覆盖任一端冻结结果。远端物理/训练一律等待新研究授权。
