from extension_common import *
from datetime import datetime,timezone,timedelta

def load(name):return json.loads((EXT/name).read_text())
def link(label,name):return '['+label+'](<'+str(WIN_EXT/'delivery'/name).replace('/mnt/c/','C:/')+'>)'
def first(label,name):return '['+label+'](<'+str(FIRST_DELIVERY/name).replace('/mnt/c/','C:/')+'>)'
def q(v):return '未观测' if v is None else f'{v:.3f}'

def main():
    close=load('CLOSEOUT_STATUS.json');timer=load('TIMER_SERVICE.json');native=load('NATIVE_STAGE_PROFILE.json');back=load('BACKLOG_AND_RAW_AUDIT.json');res=load('RESOURCE_SUMMARY.json');pres=load('PRESERVATION_AUDIT.json');data=load('DATA_ACCOUNTING.json');sources=load('SOURCE_RETENTION.json');new=back['new_diagnostic']
    text=['# B-Native Q — 用户授权至中午 12:00 的延期补充报告','',f'FINAL / 原科学等价 PASS / 实际实时资格 NOT_QUALIFIED / ADAPTATION NOT_RUN。报告生成：{datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")}。',f'用户追加指令：“如果时间提前到了允许执行到12点整”。新时间上限为 2026-10-07 12:00 上海时间；原 160 次物理上限、最多两次公共 B 修复、原科学与控制语义继续适用。累计已达 160/160，有限离线诊断完成后关闭，不等待到上限凑时间。',f'首版交付保持原字节：{first("完整 13 节首版报告","REPORT.md")}；本补充只更新新增证据、尝试总数与恢复状态。首版 73 组正式 host-clock 分母保持不变；新增 instrumentation 诊断单独列示。','']
    def section(n,title):text.extend([f'## {n}. {title}',''])
    section(1,'原 B / M2 请求到处置时间线')
    text += ['保留请求共 339：TASK 75、前置 264；按 method × stage 分组，取消/过期与实际激活分开。请求终止后才到达的检查点不用于激活预算归因。55 ms 头寸严格按原始 source_capture 计算；没有重置来源时间。缺失检查点保持截断，非零缺失不记作 0 ms。','40 ms 是 bridge 时长，<55 ms 是严格 evaluator 激活年龄条件，100 ms 是原生命周期过期规则；三者的起点和比较规则未合并。',link('分阶段完整预算与时间戳','BACKLOG_AND_RAW_AUDIT.json'),'','| 方法/阶段 | 请求 | 最早记录到的预算耗尽检查点 |','| --- | ---: | --- |']
    for k,g in back['groups'].items():text.append(f'| {k} | {g["requests"]} | {json.dumps(g["first_recorded_budget_exhaustion"],ensure_ascii=False)} |')
    text += ['','NOT_EXHAUSTED_AT_RECORDED_CHECKPOINTS 仅表示保留检查点未记录耗尽；不代表完整任务通过，也不覆盖未采到的终止区间。各分量的中位数不能相加得到整体中位数。','']
    section(2,'阻塞根因与离线服务隔离证据')
    text += ['22 个已经发生的 causal 保存状态，四轮独立会话，9 个条件。共 792 条记录：88 条 timer-only 对照、704 条含原 B 计算的计时任务；process_duplicate 还保留主线程重复的 B 计算。状态数与会话数不等于 88 个独立 Human。条件顺序按会话轮转；每条件另起 spawn 进程，C2 不泄漏至 T0。','定时主循环按固定 5 ms 网格计量，迟到时仅记录一次服务机会和跳过周期，不补造 callback。没有传感器、反馈计算、4 kHz 植物、receipt catchup 或动作激活，故本图不能证明真实实时资格。','','| 条件 | 最大服务间隔 p50 / p95 ms | job 收取 p50 ms | 跳过 timer 周期 |','| --- | ---: | ---: | ---: |']
    for k,g in timer['groups'].items():text.append(f'| {k} | {q(g["max_service_gap_ms"]["p50"])} / {q(g["max_service_gap_ms"]["p95"])} | {q(g["elapsed_ms"]["p50"])} | {g["skipped_periods"]} |')
    text += ['',f'![离线服务间隔](<{str(WIN_EXT/"delivery/figures/offline_timer_service.png").replace("/mnt/c/","C:/")}>)','进程隔离将 T0 服务间隔 p50 从 44.213 ms 降至 5.138 ms；但 job 收取 p50 为 47.565 ms，较 main 的 44.216 ms 更长。它支持服务隔离方向，不能称端到端加速。加入主线程重复工作后服务间隔 p50 回到 50.533 ms。线程条件 p50 间隔 7.420 ms，不能据此宣称 Python 线程已保证 5 ms。',link('全部逐行结果和会话','TIMER_SERVICE.json'),'','原 B 保存状态细分：22 次初次无 wrapper 测量 p50 40.285 ms；另一次带 elapsed wrapper 的 native decision 和 cProfile 仅作定位。mechanics 235 次 p50 1.629 ms、候选 evaluate 191 次 p50 2.733 ms、scheduler certificate 191 次 p50 1.030 ms；这些是嵌套调用，不可相加。初次与后续会受 warm/host 波动影响，不能把差值称 instrumentation 收益。',link('细分记录和 cProfile 源码定位','NATIVE_STAGE_PROFILE.json'),'']
    section(3,'版本与优化推广边界')
    text += ['此次新增优化推广 0、公共 B 工程修复 0；此前两次公共 B 修复额度已用完。C2 是既有 mechanics batching 版本，在此仅作保存状态诊断。研究 timer 不是原生调度器，没有替换 B 控制逻辑。内部 S 保留；没有删除原生 safety / mechanics / clearance / tracking / fallback 检查。','先前 context reuse、Q-first、既有 TASK worker、观察日志迁移的正式结果见首版。SCI 描述性 p50 232.44→53.56 ms 与实际 E5 34.76 ms coordinator / 75–78 ms activation 保持原解释，不跨 wall epoch 作因果速度比较。','']
    section(4,'科学等价证据')
    text += ['704 条含 B 的 timer 记录均对同一保存状态的原始完整返回 decision 作既有 1e-10 比较，通过。重复主线程计算未代替计时 worker 的原决策。该离线子集不能替代 B / M2 / legal deviation 三套完整物理回归。此前 12 个版本完整原生回归仍是首版冻结证据；延期没有新的可推广版本。',link('预登记条件与边界','TIMER_SERVICE_CONTRACT.json'),'']
    section(5,'实际 host-clock 资格与第 160 次失败')
    text += ['原正式集合：B 合格 0/36，M2 合格 0/37；TASK 激活 51 次，其中 46 次年龄≥55 ms（90.196%），8/75 TASK 请求 EXPIRED，31 个学习 proposal late discard。整任务 qualification 仍为 NOT_QUALIFIED。',f'第 160 次独立登记为 {new["id"]}，基于原冻结 native B 空 prefix / 无 Q 路径，seed 与旧 324 相同；两次 wall epoch 不构成速度因果配对。原 runtime 抛出：`{new["error"]}`。仅发生 commissioning，TASK 请求 {new["task_requests"]}，完整任务无效。','诊断原计划在原 current-model validation 入口复制输入，并把复制耗时真实留在 host-clock；运行未到达该入口，捕获数为 0。其重放耗时、完整输出等价性及 C2 对比均为 CENSORED_ACTIVATION_ENTRY_NOT_REACHED，不是 0 ms 或 PASS。初版空集合分析标题已修正，历史文件和脚本版本保留。',link('截断状态','ACTIVATION_REPLAY.json'),link('唯一新物理任务配置','SINGLE_CAPTURE_CONFIG.json'),'']
    section(6,'学习动作实际执行')
    text += ['延期仅执行无 Q 的 B 诊断；实际非零学习执行仍为 0。原五条 <55 ms 的 TASK 激活为 HOLD/no-Q 或当前 mask 输出零动作，不能作为非零学习证明。attempted count 不等于动作已实际提交；没有修改 counter/mask 语义。','']
    section(7,'科学收益与代价保持原冻结结论')
    text += ['四组原 SCI：B J_F 1440.752→6-candidate M2 1337.925 N·s，paired 7.14%，nominal 8.38% / legal deviation 5.90%，moment +25.27%。新合法前缀 8/8 正收益、平均 paired 5.50%。延期未新增科学评分，新的失败前缀成本不排名，也未用它声称收益保持于真实实时执行。','']
    section(8,'Q 结构与状态依赖')
    text += ['冻结线性 Q 的状态项是候选共同偏置，计划差异来自固定 masked 系数，没有 state × plan interaction；STATE_DEPENDENCE_LIMITED。候选池/可行性和执行仍依赖当前原生状态，不能把整个 M2 称 open loop。延期没有新模型、新特征、训练或参数更新。','']
    section(9,'Repetition / adaptation')
    text += ['ADAPTATION NOT_RUN：实际实时资格及非零学习执行前提未满足，延期时间不替代这些 gate。先前冻结 SCI Rep1 与 B 相同、Rep2/3 M2 J_F 1327.697/1312.598，Rep4 R2 HOLD 1.030>1.020，无效；没有 Rep5 或 adaptive 对照。标签未用于训练。','']
    section(10,'Candidate-count tradeoff')
    text += ['原 6/4/2 candidate SCI paired 改善为 7.14% / 6.52% / 5.32%；4/2 标为非严格等价。actual latency 在前置失败时保持截断。延期的 C2 是 mechanics batching 名称，与 2-candidate 预算不是同一概念；没有重新训练 Q。','']
    section(11,'资源、计算与尝试台账')
    text += [f'累计 160 START / 160 END，active=0；延期新增物理尝试 1，公共 B 修复新增 0。首版已核对 11,731,042 步（含独立 inter-rep 120 步），新失败 epoch 全部 19,698 步；总计 **{back["authoritative_total_native_steps"]:,}** 步、**{back["authoritative_total_physics_seconds"]:.4f} s**。新 raw state / held receipt / 原始 wall-record 三方一致，finite/dt/torque 检查 PASS，先于实际命令写入而计算的步为 0。',f'新 epoch 仍有 {new["raw_provenance"]["actual_wall_new_command_steps_on_grid_before_host_write"]} 个名义网格步起点早于真实写入，最大 {new["raw_provenance"]["actual_wall_max_grid_start_lead_ms"]:.6f} ms；它们是在真实写入后计算的，不是连续硬件及时部署。provenance PASS 不等于 qualification PASS。',f'延期实验 job 台账 {close["jobs_started"]} START / {close["jobs_ended"]} END，包括显式解释修正的离线 r1/r2；每个已 join，无未知进程被 kill。原父/子重叠 wall 不相加；timer/native 保存状态计算不计入新增物理步。',link('延期任务台账','TASK_LEDGER.jsonl'),link('完整原生步审计','BACKLOG_AND_RAW_AUDIT.json'),'','资源样本记录如下；PSS 是采样 scope 内已观测峰值，不是全部进程真实峰值。短物理诊断未到下一次 45 s 样本，故其峰值未观测。早期分开监控 job 与 authoring 之间空档保留，后来报告监控每 45 s 采样；不补造样本。',f'样本 {res["samples"]}；最大记录空档 {res["max_gap_s"]:.1f} s；WSL MemAvailable 最低 {res["WSL_mem_available_min"]/2**30:.3f} GiB；owned PSS 观测最高 {res["owned_PSS_max"]/2**30:.3f} GiB。Windows commit headroom 最低 {res["Windows_commit_headroom_min"]/2**30:.3f} GiB，available 最低 {res["Windows_available_min"]/2**30:.3f} GiB，C 可用最低 {res["disk_C_min"]/2**30:.3f} GiB。swap {res["swap_used_min"]/2**20:.3f}–{res["swap_used_max"]/2**20:.3f} MiB；swap-in/out 页增量 {res["swap_in_delta"]}/{res["swap_out_delta"]}；OOM 增量 {res["oom_delta"]}。未改 RAM/swap、重启 WSL 或 drop cache。',link('资源原始记录','RESOURCE_LOG.jsonl'),link('采样 scope 与空档','RESOURCE_SUMMARY.json'),f'两处工作包目录的点时逻辑文件字节合计 {data["total_bytes"]/2**30:.4f} GiB，计入两端复制和代码历史，低于 10 GiB。测量后的交付副本/manifest 增量另由交付核对；不是 allocated-block 测量。',link('数据点时测量','DATA_ACCOUNTING.json'),'']
    section(12,'源代码、权重与主项目保护')
    text += [f'保护审计 PASS：首版 {pres["first_delivery_files_checked"]} 个文件及完整文件集合保持字节；旧研究 {pres["old_protected_files_checked"]} 个保护文件、当前 relocated control {pres["frozen_control_sources_checked"]} 个文件无变化；Q hash unchanged。WSL 主项目 branch / HEAD / status / index / staged diff 与最初 dirty 状态一致。无 Git mutations。未声称整个原 unstaged tree 的字节证明，未声称 Windows Git snapshot。',link('独立保护审计','PRESERVATION_AUDIT.json'),f'保留 {sources["unique_variants"]} 个 source path/hash 版本，缺失 0；启动脚本 hash、实际物理 config 声明 source 和完成时 import 文件 hash 分别记录，不伪装 per-module import-time attestation。',link('精确历史源代码保留','SOURCE_RETENTION.json'),'']
    section(13,'关闭与恢复状态')
    text += [f'状态 STOPPED_AND_RECONCILED，关闭时累计 elapsed {close["elapsed_package_h"]:.3f} h；新上限为今天 12:00（不是已运行到 12:00）。物理剩余额度 0、公共 B 修复剩余额度 0；原 STOP_DISPATCH 保留，原 runner 未重启，所有延期子任务及 resource watcher 已结束。无 pending / auto resume。',link('关闭记录','CLOSEOUT_STATUS.json'),link('恢复说明','RESUME.md'),'后续唯一建议：在新的明确预算内，先隔离公共 B commissioning／当前模型重验对真实 5 ms 反馈线程的阻塞，并保留原时钟、阈值、当前状态证书和真实物理推进完成 B 全套资格，再接 M2。','STOP','']
    (EXT/'REPORT.md').write_text('\n'.join(text))
    print(json.dumps(dict(status='REPORT_CREATED',sections=13,bytes=(EXT/'REPORT.md').stat().st_size)))

if __name__=='__main__':main()
