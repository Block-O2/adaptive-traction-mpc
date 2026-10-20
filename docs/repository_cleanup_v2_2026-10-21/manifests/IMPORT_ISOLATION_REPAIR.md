# 原始依赖隔离修复记录

第一轮从 GitHub 克隆后的强隔离检查发现 attribution 将旧绝对 code 路径插入 sys.path，随后会读取本机 stream reader。第二轮显露该 reader 的真实 stdlib bootstrap 依赖 task_bootstrap；其原始 SHA 已由 EXECUTION_CODE_MANIFEST_v6 核对。第三轮发现 explore_common 的解析仍可能经过旧路径。失败日志原样保留。

最终恢复入口对原文件按依赖顺序显式加载，每次导入后清除历史搜索路径，验证每个模块来自新目录。原 task_bootstrap、stream reader、attribution、analyze_matched、explore_common、independent_recompute 均保持原字节，没有删除 promotion assert 或修改阈值。强隔离下旧研究目录、Windows 研究目录和旧环境根的 open 被禁止，最终网络克隆复核 PASS。早期只在本机运行通过的结果不再单独用作独立恢复证据。
