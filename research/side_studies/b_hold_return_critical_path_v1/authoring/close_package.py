"""Seal this completed negative research package; never freeze or run B."""
from pathlib import Path
import os,json,time,hashlib,shutil,gzip,collections,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
WDISPLAY='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1'
def read(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def ownfiles():
 for parent,dirs,files in os.walk(S,followlinks=False):
  dirs[:]=[d for d in dirs if d!='__pycache__' and not (Path(parent)/d).is_symlink()]
  for name in files:
   p=Path(parent)/name
   if not p.is_symlink():yield p
def main():
 assert not (S/'PACKAGE_CLOSED.json').exists(),'Never rewrite a sealed package'
 plan=read(S/'RUN_PLAN.json');r=read(S/'reports/PACKAGE_RESULTS.json');p=read(S/'preservation/FINAL_PRESERVATION.json')
 assert p['status']=='PASS' and r['complete_original_R2_PASS']==0 and r['attempts']==42
 assert time.time()<plan['hard_stop_unix'] and not any(x['status']=='RUNNING' for x in read(S/'TASK_LEDGER.json').values())
 # Preserve authoring and delivery utilities. Canonical runtime stays the
 # exact restored C13; rejected C14/C15/C16 experiments remain recoverable.
 (S/'authoring').mkdir(exist_ok=True)
 for f in W.iterdir():
  if f.is_file() and f.suffix in ('.py','.ps1','.md') and f.name!='REPORT.md':shutil.copy2(f,S/'authoring'/f.name)
 shutil.copy2(W/'reproduce_hold.py',S/'code/reproduce_hold.py');shutil.copy2(W/'dependency_table.md',S/'reports/HOLD_TRANSITION_DEPENDENCY_TABLE.md')
 failures=dict(status='PRESERVED',physical_steps_of_saved_input_tests=0,not_physical_attempts=True,records=[
  dict(test='RETURN inconsistent-source probe',error='Original planner rejects changed q when tracking_snapshot.source_state is not refreshed',model_API_counter='UNKNOWN for failed first invocation; successful probes separately counted'),
  dict(test='C9 budget harness before alignment',error='Original continuous_hold_reference flag was missing; cache not exercised',known_failed_model_API_calls=84,additional_earlier_counter='UNKNOWN'),
  dict(test='C13 AST matching harness',error='Textual tuple formatting mismatch; fixed by AST structural comparison',model_API_counter='UNKNOWN; baseline calls occurred before failure',preserved='versions/C13_AST_MATCH_FAILED_task_decode_once.py'),
  dict(test='C14 harness model perturbation, two failures',error='First tried tuple item assignment; second tried read-only q_min_rad property. Fixed by perturbing copied beta array.',model_API_counter='UNKNOWN after each failed invocation; comparisons before failure passed'),
  dict(test='C16 two harness coverage failures',error='Actual StateResidualHumanModel excluded by initial exact-type guard; pose comparisons passed but allocator cache not exercised',model_API_counter='UNKNOWN after failed invocations; final C16/C16a/C16b successful counters separate')],policy='Failure records are retrospective descriptions of observed tool outputs, not fabricated raw logs. Existing failed raw files and variants are preserved; unknown counters are not set to zero.')
 save(S/'reports/OFFLINE_FAILURES.json',failures)
 save(S/'reports/STARTUP_023_PHYSICAL_ZERO.json',dict(status='VERIFIED_ZERO_NATIVE_STEPS',id='023_C11_science_nominal',authority='logs/023_C11_science_nominal.log and code/run_one.py',failure='INSTALLED_RUNTIME_VERSION_CHANGED at commissioning_owner.install, before PrefixBInterface creation and before sc.run',native_physical_steps=0,warm_import_model_API_calls='UNKNOWN',budget_attempts=1))
 # Existing native receipts are the step authority. The sole unreported
 # native count is the startup failure proven to precede physical execution.
 native_unknown=[x['id'] for x in r['records'] if x['compute'].get('native_physics_steps') is None];assert native_unknown==['023_C11_science_nominal']
 quiet=r['quiet_C13'];nom=next(x for x in quiet if x['kind']=='nominal');dev=next(x for x in quiet if x['kind']=='legal_deviation')
 old=read(S/'reports/HOLD_CRITICAL_PATH_EXISTING.json')['rows']
 resources=[json.loads(x) for x in (S/'output/RESOURCE_LOG.jsonl').read_text().splitlines()]
 resource_summary=dict(samples=len(resources),first_unix=resources[0]['unix'],last_unix=resources[-1]['unix'],minimum_linux_available_bytes=min(x['mem_available'] for x in resources),maximum_owned_PSS_bytes=max(x['PSS'] for x in resources),minimum_windows_commit_headroom_bytes=min(x['windows'].get('commit_headroom',float('inf')) for x in resources),oom_kill_delta=resources[-1]['oom_kill']-resources[0]['oom_kill'],swap_in_delta=resources[-1]['swap_in']-resources[0]['swap_in'],swap_out_delta=resources[-1]['swap_out']-resources[0]['swap_out'],monitoring='Before/after dispatch and every45s during a physical run; analysis intervals do not claim continuous45s sampling',process_policy='Only this package process handles are joined. No unrelated process termination, WSL restart, memory/power/swap setting change.')
 save(S/'reports/RESOURCE_SUMMARY.json',resource_summary)
 old_table='\n'.join('| '+x['id']+' | '+x['kind']+' | '+f"{x['HOLD_s']:.3f}"+' | '+f"{x['HOLD_start_to_first_reference_ms']:.3f}"+' | '+f"{x['second_HOLD_start_minus_first_nominal_endpoint_ms']:.3f}"+' | '+f"{x['scored_exit_minus_last_nominal_endpoint_ms']:.3f}"+' |' for x in old)
 host_table='\n'.join('| '+x['id']+' | '+str(x['worker_status'])+' | '+('yes' if x['full_physical'] else 'no')+' | '+(f"{x['HOLD_s']:.3f}" if x['HOLD_s'] is not None else 'not reached')+' | '+str(x['original_R2'])+' | '+str(x['legacy_strict55'])+' |' for x in r['records'] if x['mode']!='SCIENTIFIC_SIMULATION')
 science_table='\n'.join('| '+x['id']+' | '+str(x['scientific'])+' | '+('cache bypass; excluded for C8 validation' if not x['cache_exercised_scientific'] else 'full native/trace gate')+' |' for x in r['records'] if x['mode']=='SCIENTIFIC_SIMULATION')
 steps=r['physical_native_steps_known'];offline_known=sum(x['model_API_calls'] or 0 for x in r['offline_compute_records'])
 report=f'''# B HOLD → RETURN Critical Path v1

STATUS: 完成 focused work package，结果 **NOT_FROZEN**。42 次新 START 均有唯一 END；19 次 host 全任务完成，**0 次 complete + original R2 PASS**。未降低任何任务或安全门槛，未创建 B_RUNTIME_BASELINE_V1。本包在原 t0 的预计 2–4 h 范围内结束；这不是“预算耗尽”或“不可能通过”的证明。

原 t0：2026-10-07 15:05:30 UTC；dispatch cutoff：19:35:30 UTC；hard stop：20:05:30 UTC；最多 80 次尝试。历史封存包只读。当前包 canonical 路径：`{S}`。Windows 报告及只读入口：`{W}`。

## ROOT CAUSE

原假设“RETURN request/result/validation 导致 scored HOLD 额外延迟”不符合实际程序顺序：**原 guarded HOLD exit 先记录，随后才创建 RETURN request**。提前 RETURN 工作能减少之后的写入延迟，但无法缩短已经记录的 scored HOLD。

真正的 scored HOLD 临界路径是：第一段原始 0.5 s HOLD 的 actual reference start，第一段真实 endpoint receipt，第二段原始 HOLD request/collection/current admission/actual reference start，第二段真实 endpoint receipt，下一次原始 guarded phase 检查。两个 reference 起点都受真实 worker/feedback/admission/physics catch-up 串行工作影响。实际 endpoint 写入前，原 governor completion 不能为 true。

以下各行都来自**同一次 transition**。后三列与两段 0.5 s 相加闭合该行 scored HOLD；不相加跨 run median。第二列间隔包含第一 endpoint 迟到及第二次交接，不再另外重复加这些费用。

| Historical run | Case | HOLD s | Entry→first reference ms | First nominal endpoint→second reference ms | Last nominal endpoint→scored exit ms |
|---|---|---:|---:|---:|---:|
{old_table}

完整事件、source/request/actual write/first native ownership 在 `reports/HOLD_CRITICAL_PATH_EXISTING.json`。旧 traces 没有保存每次 dwell/minimum 函数调用的 host timestamp；这些缺口明确标记，1 s 阈值的派生位置不冒充观测事件。新增 `_CRITICAL_TRACE.json` 和 `_EXACT_TRANSITION.json` 给出实际 guard 调用证据。

具体新增 041 实例：HOLD entry 19.225 s，first actual reference 19.2375 s，first endpoint physical 19.7435 s，second reference 19.75325 s，second endpoint physical 20.258 s，scored exit source 20.255 s。source 20.250 s 的检查中 reference progress 仍为 0.4975 s，`active_segment_complete=False`。sensor dwell 约 0.505 s 已提出 RETURN；shared minimum 采用原短路顺序，只在 reference ready 后才实际调用。原 completion 在真实 endpoint commit 后达到 0.5 s，随后原 guard 允许 RETURN。该 run scored HOLD=1.030 s；之后 RETURN request→actual write=44.874106 ms。

最终安静 C13 nominal 047：scored HOLD={nom['HOLD_s']:.3f} s。entry→first reference=14.0 ms，first nominal endpoint→second reference=16.5 ms，last nominal endpoint→scored exit=4.5 ms，共 35.0 ms。合法偏差 048：对应 11.0、12.75、1.25 ms，共 25.0 ms。原始 sensor dwell、minimum 和 completion 都保留。

R2 clock audit：这是 reference 实际完成与串行交接/服务成本导致的真实时序开销。5 ms 服务机会会影响什么时候重新读取状态，但整数倍本身不是量化误差证明。dwell 在约 0.505 s 已满足，不是 1 s 后的主要阻塞；原 reference completion 在上界附近仍为 false。未发现可以通过改 timestamp、backdate 或给未来 completion 记账修复的 bookkeeping bug。

## FIX / A–B–C dependency

详表：`reports/HOLD_TRANSITION_DEPENDENCY_TABLE.md`。

A 可提前：固定 task endpoint、存储、消息结构、不可变几何。B 可准备但必须刷新：精确值和 model/reference 绑定的 mechanics/schedule context。C 保留在当下：最终 q/dq、reference completion、terminal/stationary 条件、sensor dwell、shared minimum、freshness、phase ownership、current mechanics/native admission、feedback command 和真实写入。

实现保持的最小 C13 链：C7 在原真实 HOLD endpoint commit 后请求一次当前 service；C8a 在已有 OUTBOUND worker 工作之后准备无 actuation authority 的纯 HOLD mechanics context，advisory decision 丢弃；C9 复用精确原 HOLD schedule，但每次保留原请求验证及当前剩余时间 budget；C10 用完整原系数/时长识别原 sample 序列，避免重复生成 key samples；C11a/C12 在实际发出 HOLD request 后进行有界 collection-only service，原旧 command 继续承担真实 physics，下一原循环重读当前状态并完整审查；C13 将同一实际不可变 TASK payload 的两次 decode 合成一次，原 execute/prepare AST 除 decode assignment 外相同。

没有提前执行 RETURN、提前切 phase、复用过期 native certificate 或推测未来 q/dq。保留 0.5 s dwell、1 s shared minimum、R2 upper 1.020000001 s、1e-12 completion、5 ms service 和 0.25 ms native dt。

RETURN base-plan dependency probe：两个保存输入按原路径重算一致；当 deployable current q 和 tracking_snapshot.source_state 一起改变 1e-6 rad，原 RETURN target、polynomial、cost/terms 和 execution screen 均改变。单独只改 q 会被原 snapshot 一致性检查拒绝。因此固定 task endpoint 不足以把原完整 RETURN base plan 当静态计划。

仅 source/deps 中一处实现改变：runtime_coordination_residual_v2.py 的 HOST-only 已发出 HOLD request collection callback。其余原 controller/physics/safety/task 源码及原生源/二进制保留 hash。source 注册修复采用新的版本化 generated-runtime 文件名，并保留原 `INSTALLED_RUNTIME_VERSION_CHANGED` 断言。早期 START manifest 未包含 source/deps；保留 end imported-source hashes、C11 patch 和 compiled-owner 版本历史，不伪造过去的 START source hash。自 043 起 START 已包含 source/deps。

## SCIENTIFIC

20 个完整 SCI gates PASS，native qpos/qvel/command/contact 和 trace errors 为零；原选定计划、参考 q/dq/ddq、J_F/force/moment/tracking/clearance/safety/fallback 保持一致。最终恢复的 C13 使用 035/036 gate。HOST-only scheduling 的 scientific 路径按原 no-delay 语义运行；未修改 scientific HOLD duration。

005/006 的 C8 cache 未在 scientific mode 开启，明确不能作为 cache validation；009/010 重新启用 cache 并通过完整 gate。023 在 source-registration startup 前失败，没有 SCI 结果，也没有实际 native step。所有 substantive 已进入 host 的版本都有先行保存输入 gate 和两个完整 SCI gate；C16 系列只有局部数学 PASS，速度无收益，因此没有新物理尝试。

| SCI ID | Gate | Scope |
|---|---|---|
{science_table}

## HOST R2 / FAST

正式 cold nominal VALID=0；正式 same-interpreter nominal VALID=0；正式 legal-deviation VALID=0。正式 ladder **未 dispatch**，不能把 cold-process development smoke 计作 formal VALID。先行 nominal 均 FAIL，因而没有无依据地扩展 4+4+2 qualification。

21 次 host 尝试，19 次全任务完成；所有 complete original R2 均 FAIL。完整 host HOLD min/p50/p95/max：1.025/1.030/1.0355/1.040 s；19 个值完整保存在 `reports/PACKAGE_RESULTS.json`。013 同时有 service protocol failures；该次还发生大体积 Git baseline 文本读取，不能作为安静性能对比，但其失败不会删除。011 和 021 不计入 complete HOLD 分布。

| HOST ID | Export/worker status | Complete task | HOLD s | Original R2 | Legacy strict55 |
|---|---|---|---:|---|---|
{host_table}

最终安静 C13：

| Metric | 047 nominal | 048 legal deviation |
|---|---:|---:|
| OUTBOUND s | {nom['phase_durations']['OUTBOUND']:.6f} | {dev['phase_durations']['OUTBOUND']:.6f} |
| HOLD s | {nom['HOLD_s']:.6f} | {dev['HOLD_s']:.6f} |
| RETURN s | {nom['phase_durations']['RETURN']:.6f} | {dev['phase_durations']['RETURN']:.6f} |
| FAST feedback gap p50 ms | {nom['service_gap_ms']['p50']:.6f} | {dev['service_gap_ms']['p50']:.6f} |
| p95 ms | {nom['service_gap_ms']['p95']:.6f} | {dev['service_gap_ms']['p95']:.6f} |
| p99 ms | {nom['service_gap_ms']['p99']:.6f} | {dev['service_gap_ms']['p99']:.6f} |
| max ms | {nom['service_gap_ms']['max']:.6f} | {dev['service_gap_ms']['max']:.6f} |
| RETURN actual request→actual write ms | {nom['transition']['request_to_actual_write_ms']:.6f} | {dev['transition']['request_to_actual_write_ms']:.6f} |
| RETURN source→actual write ms | {nom['transition']['source_to_actual_write_ms']:.6f} | {dev['transition']['source_to_actual_write_ms']:.6f} |
| Maximum physics backlog ms | {nom['maximum_backlog_s']*1000:.6f} | {dev['maximum_backlog_s']*1000:.6f} |

最终两次所有 functional checks 中只有 original_R2 FAIL；physical/safety/current admission、meaningful plans、bounded age/backlog、FAST service 条件和 actual native command ownership 均 PASS。Legacy strict55 独立 FAIL，不作为唯一 promotion criterion。

每次 RETURN 的 request/snapshot/enqueue/queue/compute/ready-collect/current validation/actual write 都有 non-overlapping 分解且相加闭合实际 request→write。actual write 的 receipt `apply_ns` 与 lifecycle activation return 不是同一事件；first native step 由真实 write availability 向上取 0.25 ms grid，迟到前的每个 native interval 使用旧 receipt command。全部有完整证据的 host 无 causal ownership violation。

FAST gap 统计只测量原 `_execute_interval` feedback service。C11/C12 collection-only iterations 不是 feedback/actuation service，begin/socket-ready/finish 和旧 command native steps 单独保存；没有把 collection 通知充作 FAST 写入。all-actual-write command age 分布、TASK source→lifecycle activation、misses、meaningful plans、backlog 和 causal 原始审查在各 `_FUNCTIONAL.json` 及 `_TRANSITION_METRICS.json`。

## ROBUSTNESS

条件性真实 RETURN delay/stale/model-version/current-mismatch/reject suite **NOT RUN**：nominal primary success 未满足。保存输入测试证明改变 model/reference/screen/budget 时原重算或原拒绝、无效 advisory preparation 会丢弃；这些不冒充真实 transition robustness qualification，也不声称未来/过期 RETURN 已通过物理故障测试。

## B STATUS / M2 READINESS

**B_FROZEN = FALSE；B_RUNTIME_BASELINE_V1 = NOT_FROZEN。** 本包研究结束并封存，不代表 B baseline 冻结。最终可复核实现为恢复后的 C13，不是被拒绝的 C14/C15/C16。

M2 readiness：未启动，兼容性未判定。冻结 Q weights SHA256 `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` 与旧包保护快照一致。无 Q/G 修改、无 Q inference readiness smoke、无 M2 physics、无 adaptation/retraining、无 Human matrix 扩展。

## NEGATIVE RESULTS

1. C7–C13 的合法 endpoint/collection/context/decode 优化未使原始 R2 通过；关闭详细 transition 诊断的 C13 smoke 也失败。
2. C14 完整 mapping key 因逐周期 label 改变而无实际 hit；C15 去除非数值 label 后 SCI 只有少量 hit，原微小非零 dq 仍变化。没有把这些原值归零，也没有得到 host R2 PASS；最终恢复 C13。
3. C16/C16a/C16b 的精确几何/allocator partial reuse 局部逐位一致，但典型原 prepare 约 0.33–0.36 ms，复用约 0.34–0.42 ms，未获得速度收益。无 host dispatch。
4. 011 原 motion/commissioning safety 路径失败；021 actual first TASK IPC queue 约 366 ms 后原任务 ABORT；023 generated-source consistency startup 失败。全部保留原输入、日志、失败记录与预算身份，没有丢弃或当完整任务成功。

## Accounting / preservation / reproduction

42 个 START/END 一一对应，20 个 SCI completed gates 加 1 个 SCI startup failure；21 个 host attempts。所有实际 native steps：{steps:,}（{steps*.00025:.4f} s）；023 原 counter 未导出，但 traceback 证明在物理入口前失败，native=0。主模型已报告 API calls 933,771；native worker 已报告 114,345；advisory preparation 1,680 次从每 run 最后累计 snapshot 单独取一次，未相加重叠 snapshots。warm/import/failed-partial 未完整导出的 model counters 明确 UNKNOWN，不能据此声称完整 model 总数。成功离线和一个已导出失败离线测试的已知 model calls 下界 {offline_known:,}；未导出失败 counter UNKNOWN；保存输入测试 native steps=0。

资源检查 {len(resources)} 条，physical run 中每45s及 dispatch 前后采样，analysis 不声称连续45s采样。完整 resource/headroom/PSS/swap/OOM 在 `reports/RESOURCE_SUMMARY.json`。未改变 power/memory/swap/WSL 设置，未终止无关进程。所有观察到的 TASK owner JOIN 及 commissioning close 已核对。

旧封存包 10 个保护文件及 frozen-Q 文件逐位 hash 保持，原 Linux 主 repo branch/HEAD/status/index/staged binary diff 均一致；主 Git 状态未写入。`preservation/FINAL_PRESERVATION.json` 保留校验证据。native source/build binary 与本包初始值一致。

只读复核：Windows `run_readonly.ps1 -Mode Check`，或 `-Mode Review -TaskId 047_C13_host_nominal_quiet`。它只核对 ledger/manifest 或读现有结果，不启动物理。原历史 runner/reproduce 脚本的继承入口不作为本包复跑授权。封存后 dispatcher/cohort guard 拒绝新增 physical attempt。

原始 outputs/inputs/results/logs、version snapshots、作者脚本、源代码和 manifests 保留在 canonical 包；Windows 镜像仅复制本报告和紧凑审查文件。`FULL_PACKAGE_MANIFEST.json` 对全部本包非缓存常规文件记录 SHA256；只读历史 symlink 单独记录 target。排除 manifest 自身、生成后的 verification 文件和 `__pycache__`，避免自引用。gzip 全量解压 CRC 检查记录在 `reports/FULL_PACKAGE_VERIFICATION.json`。

## NEXT

对已封存的两段 HOLD request→实际 reference activation 链做独立实现审查，再决定是否值得继续 B 优化。

REPORT PATH: `{W/'REPORT.md'}`；canonical `{S/'REPORT.md'}`。

STOP.
'''
 report=report.replace(str(W),WDISPLAY)
 (S/'REPORT.md').write_text(report);(W/'REPORT.md').write_text(report)
 (W/'reports').mkdir(exist_ok=True)
 for name in ('PACKAGE_RESULTS.json','HOLD_CRITICAL_PATH_EXISTING.json','HOLD_TRANSITION_DEPENDENCY_TABLE.md','RESOURCE_SUMMARY.json','047_C13_host_nominal_quiet_TRANSITION_METRICS.json','048_C13_host_deviation_quiet_TRANSITION_METRICS.json'):
  shutil.copy2(S/'reports'/name,W/'reports'/name)
 shutil.copy2(S/'preservation/FINAL_PRESERVATION.json',W/'reports/FINAL_PRESERVATION.json')
 (S/'PROGRESS.md').open('a').write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime())} UTC: Focused branches reviewed, C13 quiet smoke fails R2; close NOT_FROZEN. No formal ladder/conditional robustness/M2 dispatch.\n')
 code_manifest={str(f.relative_to(S)):sha(f) for f in ownfiles() if f.relative_to(S).parts[0] in ('source','deps','code','native','build') and 'results' not in f.relative_to(S).parts}
 save(S/'FINAL_CODE_MANIFEST.json',code_manifest)
 now=time.time();closed=dict(status='CLOSED',B_FROZEN=False,B_RUNTIME_BASELINE_V1='NOT_FROZEN',t0_unix=plan['t0_unix'],closed_unix=now,elapsed_hours=(now-plan['t0_unix'])/3600,attempts=42,physical_dispatch_permitted=False,reason='Evidence-supported focused branches did not achieve original R2; final quiet smoke also fails. Local static geometry offers no speed benefit. No unsupported qualification or unrelated changes.',budget_exhausted=False,not_global_impossibility_claim=True)
 # Verify raw payload CRC before publishing the final CLOSED marker.
 gz=[]
 for f in ownfiles():
  if f.suffix=='.gz':
   count=0
   with gzip.open(f,'rb') as stream:
    while b:=stream.read(1024*1024):count+=len(b)
   gz.append(dict(path=str(f.relative_to(S)),uncompressed_bytes=count,CRC='PASS'))
 save(S/'STATE.json',closed|dict(active=[],phase='STOP'));save(S/'PACKAGE_CLOSED.json',closed);save(S/'NOT_FROZEN.json',closed)
 excludes={'FULL_PACKAGE_MANIFEST.json','reports/FULL_PACKAGE_VERIFICATION.json'}
 files={str(f.relative_to(S)):dict(sha256=sha(f),bytes=f.stat().st_size) for f in ownfiles() if str(f.relative_to(S)) not in excludes}
 links={str(f.relative_to(S)):os.readlink(f) for f in S.rglob('*') if f.is_symlink()}
 save(S/'FULL_PACKAGE_MANIFEST.json',dict(status='SEALED',files=files,symlinks=links,excluded=sorted(excludes)+['**/__pycache__/**'],read_only_historical_reference_symlinks=True))
 assert all(sha(S/rel)==x['sha256'] for rel,x in files.items())
 bytes_total=sum(x['bytes'] for x in files.values());assert bytes_total<plan['bytes_target']
 verification=dict(status='PASS',verified_regular_files=len(files),verified_code_files=len(code_manifest),gzip_CRC= gz,bytes_accounted=bytes_total,GiB=bytes_total/2**30,below_4GiB_target=True,manifest_sha256=sha(S/'FULL_PACKAGE_MANIFEST.json'),final_code_manifest_sha256=sha(S/'FINAL_CODE_MANIFEST.json'),package_closed=True,B_FROZEN=False,verified_unix=time.time(),START_END_bijection=True,report_sha256=sha(S/'REPORT.md'))
 save(S/'reports/FULL_PACKAGE_VERIFICATION.json',verification);shutil.copy2(S/'reports/FULL_PACKAGE_VERIFICATION.json',W/'reports/FULL_PACKAGE_VERIFICATION.json');shutil.copy2(S/'PACKAGE_CLOSED.json',W/'PACKAGE_CLOSED.json')
 print(json.dumps(dict(status='CLOSED',B_FROZEN=False,attempts=42,files=len(files),gzip_files=len(gz),GiB=verification['GiB'],elapsed_hours=closed['elapsed_hours'],report=str(W/'REPORT.md'))))
if __name__=='__main__':main()
