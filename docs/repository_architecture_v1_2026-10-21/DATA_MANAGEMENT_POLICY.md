# 科研数据与结果管理政策 v1

Git保存源码、必要小模型/vendor、configs、CPU依赖锁、原scorer/合同、合理大小真实fixture、测试、结果摘要和复现说明。大型raw/轨迹/checkpoint与临时构建缓存按用途分开管理，不能把旧实验负结果当缓存删除。没有自动LFS/Release/分卷迁移。

## 数据身份

deployment/data_catalog.json是当前入口，引用原EXTERNAL_DATA_MANIFEST及47份逐文件CSV，保持原bytes/SHA；每个CSV条目继承其数据组的实验来源、源码身份、用途、必需范围、恢复办法及portability，唯一ID=data_id:row.path@sha256:row.sha256。逐文件大小/SHA来自原index；源码版本由明确Git snapshot和原EXECUTION_CODE_MANIFEST hash共同记录；无法证明的原生成commit写UNKNOWN。

原D01R fixture32项现由Git提供，data_id=ihear-D01R-W1-original-fixture-v1；原TAR只是同机历史证据。其他旧raw/checkpoint索引中若条目在本轮已成为Git fixture，按当前fixture manifest优先解析；原index保留历史含义。缺远程可访问URL的外部组必须标NOT_PORTABLE，不能把本地绝对路径当下载地址，也不能说这些数据仅clone可恢复。

未来外部数据落地research-data/<data-id>/<immutable-version>，按manifest校验后只读使用。发布/迁移数据时另记可访问来源、授权范围、版本、SHA、大小、实验来源、生成源码、目的、是否必要和恢复命令。物理独立的第二存储才可称独立备份；同机TAR、在位SHA索引、Git blob去重均不是独立备份。本轮未采购、上传或连接外部存储。

## checkpoint与结果

保留原完整generation，禁止覆盖。RL-B模型ZIP、RNG PT和最后写入的JSON组成一个generation，任一缺失或hash/contract不符不得restore。B/H150父进程checkpoint缺失要明确记录，不能用qpos/qvel或causal摘要代替。

新执行使用runs/<experiment>/<UTC>-<commit>-<uuid>或.deployment-work/<new-id>；记录源码commit/dirty diff、模型和config hash、输入data_id及SHA、算法/合同hash、seed、环境锁与实际版本、完整命令、失败日志、输出身份。每个输出目录不可覆盖。新scorer自动写RUN_PROVENANCE/OUTPUT_MANIFEST；未来其他训练入口须在不破坏原资格门的独立版本中接入同一schema。

Git仅挑选可审查的摘要、关键指标、输入输出manifest和必要小fixture。全量raw与checkpoint留外部版本目录，catalog指向精确版本。记录失败/中断/partial，区分exploratory、formal、held-out、oracle与机械smoke，不事后重写门槛。

## 提交前门

审查显式路径staged diff、来源SHA、敏感内容、单文件大小和必要轻量检查。不提交密钥/凭证/私有恢复patch。native.json.gz是原scorer原生数据格式，按文件评审，不以宽泛忽略所有gzip掩盖必要fixture。大于普通Git限制的真实必要文件先报告具体用途和备选存储，不自动LFS或切片规避。

保留旧源路径和所有历史证据；数据结构优化先做引用闭包审计再版本化。近期德国服务器PPO状态单列UNVERIFIED，回收必须另行授权，不影响本轮封存CPU版本身份。
