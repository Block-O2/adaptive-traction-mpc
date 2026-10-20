# 未入库数据与恢复办法

本轮库存中保留于外部、且没有已存在初始 HEAD 或本轮提交副本的普通文件：**113696 个，133740648114 bytes（124.556 GiB）**。这些不是删除清单。逐文件 `bytes` 与 `sha256` 在 `manifests/excluded/*.csv`；按根/研究包拆分避免单个清单过大。被 Git 忽略的原证据同样保留。

| root 别名 | 原位置 |
|---|---|
| main | `/home/hank/coding/adaptive-traction-mpc-learning` |
| side | `/home/hank/coding/adaptive-traction-mpc-side-studies` |
| windows | `C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc` |

包含大型 raw/轨迹/native journal、checkpoint/optimizer/RNG、冻结权重、branch dataset、训练日志、ZIP、未选旧代码快照和密集历史结果。venv、GPU/site-packages 与可重建 cache 没有作为科学证据逐文件保全，不应把其排除误读为数据删除。

恢复：先从指定 root+relative_path 找到原文件或已有外部备份，复制到**新的空归档/恢复目录**，核对 CSV 的字节数和 SHA256 后再交给原 evaluator；不覆盖本地原件，不用摘要替代 raw。Windows D 盘外置数据由 `linux_links.json` 给出链接目标；本轮只核实链接存在，外置目标 SHA 为 NOT_HASHED_EXTERNAL，应在将来实际传输前校验其既有归档 manifest。

Git LFS 本机调用不可用（git lfs 无法执行），没有安装或迁移历史。拟提交最大文件 5538225 bytes，均小于本轮 50 MiB 保守门；不需要靠 LFS 绕过大文件限制。大数据采用独立归档+本清单路线，本轮不新打 GB 包、不删除或重生 checkpoint。

本地恢复 bundle、原 index 和完整 diff 在 Windows 本轮 work 目录私有保存，未提交。密钥/token/账号目录不在白名单；清单只记录研究文件位置和内容身份，不包含凭证值。
