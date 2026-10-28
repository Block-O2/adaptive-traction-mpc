# 删除服务器的影响

本轮不删除、重建或关闭服务器，也不制作整盘备份或Snapshot。归档不是完整磁盘备份。

## 明确不在本次上传范围内

大规模历史native raw、重复轨迹/实验副本、全部中间策略/Adam/RNG训练状态、所有模型缓存、virtualenv、pip缓存、大型zip研究包、编辑器和用户主目录、SSH/Git/云凭据、主机配置不上传。本轮专用SSH私钥保留在归档树外，也不会上传；新主机须另行配置GitHub认证。未归档的历史材料若服务器被删除且用户无其他备份，将不可从本归档恢复。可从代码重新生成的结果也不保证数值逐字等同旧运行。

## 保留与不能恢复的边界

主要传统源码/plant与资产依赖、完整任务和评价、安全执行逻辑、历史版本与条件、现代强传统两个完整raw、若干完整native数组、代表Learning模型和接口、代码与配置保留。旧D01R原raw已在既有Git对象中保留。完整动态复现会建立新的合法父状态，不将未保存的Python/ MuJoCo活地址空间虚构成磁盘checkpoint。

更早History/ILC/BO部分历史训练数据和权重原本就缺档；源码与报告不能补回这些数值。仅native保存的heavy H150/18D、v8持续ILC轨迹不能单靠该数组重放全部安全/ownership scorer。代表性权重不能恢复全部训练中间状态或每个seed的原优化器。

选定文件精确身份见 [selected_files.json](research_archive/manifests/selected_files.json)，代表证据见 [evidence_selection.json](evidence_selection.json)。未选资料见 [逐路径盘点](research_archive/manifests/omitted_research_assets.csv) 和 [汇总](research_archive/manifests/server_research_inventory_summary.json)。该清单的“未选”指未按该原相对路径复制，不证明每个文件独有；重复内容可能已在旧Git别处保留。主要不可恢复的是未选的独有native raw、训练中间权重/Adam/RNG、未保存的活模拟器/控制状态，以及本来已经缺失的历史数据。

## 可能继续产生Hetzner费用的资源

本任务所在计算服务器仍保持运行；如果它属于Hetzner付费实例，计算实例及其附属计费项目仍可能持续计费。另须由用户在Hetzner Console核对所有Project中的服务器、Volume、Primary/Floating IP、Load Balancer、Object Storage、既有Backup/Snapshot及其他订阅。未获得云账户资源清单，无法确认它们是否实际存在、数量或金额；没有擅自推定已停止计费。

本轮没有新建付费云实例、整盘备份或Snapshot，没有调用删除/关机/重建API。删除需用户另行明确确认，且应先核实最终交接和所有需要保留的本地独有资料。
