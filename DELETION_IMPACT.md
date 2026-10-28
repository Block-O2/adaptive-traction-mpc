# 删除服务器的影响

**本轮没有删除、重建或关闭Hetzner服务器，也没有制作整盘备份或Snapshot。** GitHub已保留可实际运行的科研闭包和代表证据，但不是全部历史数据备份。删除须用户另行确认。

## 已可从GitHub恢复

原B、H150、18D及关键传统优化/平顺性版本的源码、模型/mesh/XML与参数/任务/评分/安全依赖；原Git研究历史；v1–v8及更早Learning代表实现/接口/合同与少量已训练checkpoint；14份综合主文档、真实图/CSV和实际远端核验回执。原B19.03s、强传统组合和D01R B/H150已从独立远端clone实际跑通，见 [核验报告](ARCHIVE_VERIFICATION.md)。

[选定原文件清单](research_archive/manifests/selected_files.json)为23,756项、1,214,474,476bytes；[122项代表证据](evidence_selection.json)为151,544,024bytes。另保留新原B完整native/5ms trace与紧凑实际回执约12.46MB。相同快照由Git去重，不上传整包ZIP。

## 删除后不能保证恢复的内容

|内容|丢失或恢复限制|
|---|---|
|未选的独有历史native raw、完整轨迹、各失败/分支的全部receipt|不能从PNG/CSV/摘要补回；重新运行也不保证所有旧字节/状态相同|
|全部中间模型、Adam/RNG、pending rollout、每seed训练状态|只保留代表checkpoint，不能从头到尾精确续训每个历史分支|
|活MuJoCo/Python地址空间与fork父状态|未序列化为跨机完整checkpoint；新验证是重新commission，不是恢复旧内存|
|更早部分History/ILC/BO主要权重/训练集与完整ledger|本来已缺，源码/报告不能制造缺失数值；未称独立完整复算|
|legacy Stage1的40项模型引用、旧m2未找回对象|现代B不依赖这些；不宣称完整旧磁盘镜像|
|只保留native的heavy H150/18D、v8持续ILC|可读运动数组与历史指标，不能仅凭native重放全安全/ownership评分|
|本轮新复现的全部gzip raw|保留关键回执与原B native/trace，其余scratch大raw未全上传；完整旧D01R与现代B/组合代表raw已保留|
|虚拟环境、缓存、编辑器/主目录、主机配置、云/SSH/Git凭据|不在归档；软件依赖按锁文件在线新装已验证。本轮专用SSH私钥在归档树外，不上传，新机须重新认证|

原具名研究包和根ZIP的[未选逐路径盘点](research_archive/manifests/omitted_research_assets.csv)共 **79,019项 / 111,789,741,362bytes**，约111.79GB。它不是“全部独有资料丢失”的证明：副本可能在旧Git其它路径，模型缓存可重建，ZIP可与已归档源重复。旧m2的38个缺位置对象中22项已有原SHA相同[归档别名](research_archive/manifests/historical_alias_recovery.json)，包括四个旧linear Q文件，不应误列为全局丢失。

盘点仅限任务中的具名研究包，不是所有主目录、挂载盘或其它云资源的普查。删除前若用户还需要未选的独有资料或范围外文件，必须另行保存；本任务未制作全服务器备份。

## 公开历史与认证

新树排除PRIVATE工作树状态和非必需用户原文，见 [排除记录](research_archive/manifests/public_exclusions.json)。旧公开提交已有的副本不能通过新分支删除而撤回；本轮遵守不重写历史、不force push、不改可见性的边界。未发现必须另建Private仓库才能保留的本轮选定仿真数据；不能将此当成对全部旧历史敏感内容的穷尽保证。

## 可能继续产生Hetzner费用的资源

当前服务器保持运行。如果它是Hetzner付费实例，实例与附属资源仍可能持续计费。用户还须在Hetzner Console核对所有Project中的服务器、Volume、Primary/Floating IP、Load Balancer、Object Storage、既有Backup/Snapshot及其它订阅。云账户资源清单/账单没有访问或核验，数量、是否存在和金额均为UNKNOWN；不能声称已停止计费。

本轮没有创建新的付费云实例、Backup或Snapshot，没有调用关机/删除/重建API。科研归档结束后STOP，服务器处置等待用户另行明确确认。
