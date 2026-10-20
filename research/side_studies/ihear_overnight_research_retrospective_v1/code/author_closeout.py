from pathlib import Path
import os,sys,time,json,hashlib,shutil,subprocess,collections,gzip,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1')
OLD=S.parent/'b_hold_return_critical_path_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_runtime_qualification_decoupling_v1')
sys.path.insert(0,str(W));from bootstrap import sha,save,git_snapshot
def ownfiles():
 for root,dirs,files in os.walk(S,followlinks=False):
  dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink() and d!='__pycache__']
  for name in files:
   p=Path(root)/name
   if not p.is_symlink():yield p
def phase_cost(ident,metric):
 folder=S/'source/results'/ident;summary=json.loads((folder/'summary.json').read_text())
 with np.load(folder/'trace.npz') as z:
  mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
 trans={r['to']:r['time_s'] for r in summary['task']['phase_transitions']}
 bounds=[t[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']];rows={}
 for phase,a,b in zip(('OUTBOUND','HOLD','RETURN'),bounds,bounds[1:]):
  dt=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));used=dt>0;duration=float(dt.sum());jf=float(f[:-1]@dt);mi=float(m[:-1]@dt)
  rows[phase]=dict(J_F_N_s=jf,moment_integral_Nm_s=mi,phase_clock_duration_s=metric['phase_durations'][phase],integrated_trace_duration_s=duration,mean_force_N=jf/duration,force_peak_N=float(f[:-1][used].max()),moment_peak_Nm=float(m[:-1][used].max()))
 assert abs(sum(r['J_F_N_s'] for r in rows.values())-metric['J_F'])<1e-8
 assert abs(sum(r['moment_integral_Nm_s'] for r in rows.values())-metric['moment_integral'])<1e-8
 return dict(phases=rows,raw_full_J_F_N_s=metric['J_F'],OUTBOUND_RETURN_J_F_N_s=rows['OUTBOUND']['J_F_N_s']+rows['RETURN']['J_F_N_s'],method='Unchanged original left-endpoint TASK trace quadrature, partitioned at actual phase transitions; split crossing interval lengths only, no physics or HOLD removed/added',integrated_trace_duration_s=float(t[-1]-t[0]),task_phase_clock_duration_s=sum(metric['phase_durations'].values()),final_completion_after_last_evaluation_sample_s=float(trans['COMPLETE']-t[-1]),full_J_F_closure_error_N_s=sum(r['J_F_N_s'] for r in rows.values())-metric['J_F'])
def main():
 plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text());assert not any(r['status']=='RUNNING' for r in ledger.values())
 events=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=collections.Counter(r['id'] for r in events if r['event']=='START');ends=collections.Counter(r['id'] for r in events if r['event']=='END');assert starts==ends and all(v==1 for v in starts.values()) and set(starts)==set(ledger) and len(starts)<=50
 new_ids=sorted(k for k,v in ledger.items() if v.get('worker_status')=='COMPLETE');records=[];joins=[]
 for ident in new_ids:
  r=json.loads((S/'reports'/(ident+'_RUNTIME_QUALIFICATION.json')).read_text());f=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());a=json.loads((S/'reports'/(ident+'_AUDIT.json')).read_text())
  age=f['legacy_result']['activation_age_ms'];r['legacy_engineering_composite']=r['LEGACY_STRICT55'];r['LEGACY_STRICT55']='PASS' if age.get('n',0)>0 and age['max']<55 else 'FAIL';r['strict55_activation_age_ms']=age;r['phase_cost']=phase_cost(ident,r['metric']);r['miss_rate']=a['miss_rate'];r['service_compute_ms']=a['service_compute_ms'];r['rolling_1s_mean_ms']=f['rolling_1s_mean_ms']
  physical=r['metric']['physical_audit']['unchanged_evaluator']['raw_scorer_v2'];r['tracking_max_error_deg']=physical['maximum_estimation_error_deg'];r['clearance_min_true_m']=physical['minimum_true_shank_clearance_m'];r['clearance_min_measured_sleeve_m']=physical['minimum_measured_sleeve_gap_m']
  ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());requests=[q for q in ev['native_requests'] if q['stage']=='TASK'];r['fallback_intervals']=sum(q.get('fallback_intervals',0) for q in requests);r['fallback_physics_s']=sum(q.get('fallback_physics_s',0) for q in requests)
  ipc=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text());j=[q for q in ipc['rows'] if q['event']=='JOIN'];co=json.loads((S/'output'/(ident+'_COMMISSIONING_OWNER.json')).read_text());assert j and all(q['joined'] and q['exitcode']==0 for q in j);joins.append(dict(id=ident,TASK=j,commissioning=co));save(S/'reports'/(ident+'_RUNTIME_QUALIFICATION.json'),r);records.append(r)
 # The standalone <55ms axis is independent; preserve old combined labels.
 existing=[]
 for ident in ('047_C13_host_nominal_quiet','048_C13_host_deviation_quiet'):
  r=json.loads((S/'reports'/(ident+'_RUNTIME_QUALIFICATION.json')).read_text());f=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());age=f['legacy_result']['activation_age_ms'];r['legacy_engineering_composite']=r['LEGACY_STRICT55'];r['LEGACY_STRICT55']='PASS' if age['max']<55 else 'FAIL';r['strict55_activation_age_ms']=age;save(S/'reports'/(ident+'_RUNTIME_QUALIFICATION.json'),r);existing.append(dict(id=ident,runtime=r['status'],R2=r['LEGACY_R2_MATCHED'],strict55=r['LEGACY_STRICT55'],old_composite=r['legacy_engineering_composite'],age_max_ms=age['max']))
 assert len(records)==4 and all(r['status']=='FAIL' for r in records)
 protected=json.loads((S/'preservation/PROTECTED_BEFORE.json').read_text());after={p:sha(p) for p in protected};assert after==protected
 git_before=json.loads((S/'preservation/GIT_BEFORE.json').read_text());git_after=git_snapshot();assert git_before==git_after
 # Verify the archived raw evidence actually used, without touching it.
 oldmanifest=json.loads((OLD/'FULL_PACKAGE_MANIFEST.json').read_text())['files'];raw_verified=[]
 for rel,value in oldmanifest.items():
  if any(ident in rel for ident in ('047_C13_host_nominal_quiet','048_C13_host_deviation_quiet')):
   assert sha(OLD/rel)==value['sha256'],rel;raw_verified.append(rel)
 # Every C13 implementation copied to this package is unchanged except exact
 # package-name/path relocation; additions are separately authored harness files.
 oldcode=json.loads((OLD/'FINAL_CODE_MANIFEST.json').read_text());same=[];relocated=[]
 for rel in oldcode:
  p=OLD/rel;current=S/rel
  assert current.exists(),rel
  if p.suffix=='.py' and rel.split('/')[0] in ('source','deps','code'):
   text=p.read_text();expected=text.replace(str(OLD),str(S)).replace('"b_hold_return_critical_path_v1"','"m2_comprehensive_coordination_search_v1"').replace("'b_hold_return_critical_path_v1'","'m2_comprehensive_coordination_search_v1'")
   assert current.read_text()==expected,rel
   (same if text==expected else relocated).append(rel)
  else:assert sha(p)==sha(current),rel;same.append(rel)
 preservation=dict(status='PASS',protected_hashes=after,Git_unchanged=git_after,old_raw_verified_files=len(raw_verified),old_raw_files=raw_verified,byte_identical_C13_files=len(same),exact_path_only_C13_files=len(relocated),source_control_law_physics_safety_task_changes=False,Q_changed=False,no_staging_commit_push_reset_delete=True)
 save(S/'preservation/FINAL_PRESERVATION.json',preservation)
 proc=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S/'code/fast_dispatch.py') in cmd or str(S/'code/run_one.py') in cmd:proc.append(dict(pid=int(p.name),cmd=cmd))
  except OSError:pass
 assert not proc,proc
 save(S/'reports/WORKER_JOIN_AUDIT.json',dict(status='PASS',rows=joins,live_owned_dispatch_or_run_processes=proc,first_failed_attempt='No physical environment/task worker created: failure in PrefixBInterface constructor before sc.run',START_END_bijection=True))
 resource=[json.loads(l) for l in (S/'output/RESOURCE_LOG.jsonl').read_text().splitlines()];resource_summary=dict(samples=len(resource),monitoring='dispatch before/after and every45s while physical run active; no claim of continuous analysis monitoring',WSL_min_available_bytes=min(r['mem_available'] for r in resource),Windows_min_available_bytes=min(r['windows'].get('available',2**60) for r in resource),Windows_min_commit_headroom_bytes=min(r['windows'].get('commit_headroom',2**60) for r in resource),PSS_peak_bytes=max(r['PSS'] for r in resource),swap_bytes_range=[min(r['swap_used'] for r in resource),max(r['swap_used'] for r in resource)],swap_in_delta=resource[-1]['swap_in']-resource[0]['swap_in'],swap_out_delta=resource[-1]['swap_out']-resource[0]['swap_out'],OOM_delta=resource[-1]['oom_kill']-resource[0]['oom_kill'],sustained_pressure_backoff=False,settings_modified=False,unknown_processes_killed=False,power_or_quiet_mode='Unchanged; no causal attribution of service slowdown to power mode')
 save(S/'reports/RESOURCE_SUMMARY.json',resource_summary)
 guardfiles=['async_native_worker.py','q_first_method.py','native_method.py'];guard_sources={f:sha(S/'code'/f) for f in guardfiles}
 guards=dict(status='AUDITED_NO_CHANGE',source_hashes=guard_sources,classification=[dict(kind='A_native_lifecycle',source='online_planning.PlanLifecycle.maximum_age_ns=100_000_000 and activation_validation original/revalidation ages <100ms',action='RETAINED'),dict(kind='B_strict55_research',source='async_native_worker.execute deadline=min(40.,55.-activation_reserve_ms); historical reserve36 =>19ms proposal return guard',action='May disable strict55-derived early rejection in separately versioned M2 adapter after B freeze; NOT_APPLIED because B not frozen'),dict(kind='mixed_or_unclear',source='native_method/q_first_method min(.040-compute_reserve,.055-compute_reserve-command_reserve) shadow budget',action='Preserved; actual delay_replay control and original bridge40 responsibility require adapter review; no mixed responsibility removal')],issued_count='Historical count increments at proposal choose/apply and masks consumed proposal slots, not committed physical actions; exact admitted/executed request ownership must be logged by M2 adapter. No count/authority changes made.',M2_integrations=0)
 save(S/'reports/STRICT55_GUARD_AUDIT.json',guards)
 compute=dict(attempts=len(starts),complete_host_tasks=len(records),failed_startups=1,actual_native_steps=sum(r['actual_native_steps'] for r in records),simulation_seconds=sum(r['actual_native_steps'] for r in records)*.00025,main_model_API_calls=sum(v['compute'].get('main_model_inverse_dynamics_api_calls') or 0 for v in ledger.values()),native_worker_model_API_calls=sum(v['compute'].get('native_worker_model_inverse_dynamics_api_calls') or 0 for v in ledger.values()),unknown_counter_scope='001 pre-physics startup has no exported model counter, known native steps0; warm/import/advisory model calls not silently estimated',offline_physics_added=0,source_validation_files=1283,Q_updates=0,START=starts,END=ends)
 save(S/'reports/COMPUTE_LEDGER.json',compute)
 blocked=dict(status='STOP_CURRENT_HOST_FAST_SERVICE',B_RUNTIME_MOTION_EXISTING_EVIDENCE='PASS',B_RUNTIME_MOTION_QUALIFIED=False,B_RUNTIME_FROZEN=False,B_RUNTIME_BASELINE_V1='NOT_FROZEN',LEGACY_R2_MATCHED='FAIL',LEGACY_STRICT55='FAIL',M2_feature_compatibility='NOT_RUN_B_NOT_FROZEN',M2_nonzero_learning_physical_execution_count=0,M2_attempts=0,M2_VALID=0,paired_host_matrix='NOT_RUN',repetition_smoke='NOT_RUN; native persistent actual-clock interface currently unsupported and B freeze gate unmet',movement_isolation='NOT_RUN; full-task segments used, task state machine unchanged',repair_versions=0,existing_rows=existing,records=records,no_auto_resume=True,reason='All four current host confirmations fail frozen practical FAST tail/rolling service requirements, despite physical/safety/current admission/causal/bounded backlog PASS. Existing two prior quiet runs remain PASS under new retrospective axis; no claim B is inherently incapable.',interpretation='Four timing repeats on two exposed nominal/legal conditions; no generalized robustness, personalized learning, hardware readiness, or independent Human generalization claim')
 save(S/'reports/PACKAGE_RESULTS.json',blocked)
 table='\n'.join(f"| {r['id']} | {r['status']} | {r['phase_durations']['OUTBOUND']:.6f} / {r['phase_durations']['HOLD']:.6f} / {r['phase_durations']['RETURN']:.6f} | {r['service_gap_ms']['p50']:.3f} / {r['service_gap_ms']['p95']:.3f} / {r['service_gap_ms']['p99']:.3f} | {r['rolling_1s_mean_ms']['max']:.3f} | {r['miss_rate']:.2%} | {r['strict55_activation_age_ms']['max']:.3f} |" for r in records)
 costrows=[]
 for r in records:
  attribution=' / '.join(format(r['phase_cost']['phases'][p]['J_F_N_s'],'.3f') for p in ('OUTBOUND','HOLD','RETURN'))
  costrows.append(f"| {r['id']} | {r['metric']['J_F']:.3f} | {attribution} | {r['metric']['moment_integral']:.3f} / {r['metric']['moment_peak']:.3f} | {r['metric']['force_peak']:.3f} |")
 costs='\n'.join(costrows)
 wall=(time.time()-plan['t0_unix'])/60
 report=f'''# B Runtime Qualification Decoupling and Frozen M2 Host Clock Validation v1

STATUS: **STOP_CURRENT_HOST_FAST_SERVICE / NOT_FROZEN**。三轴判定已拆开，历史 R2 FAIL 不变。旧 047/048 的原始证据按新增合同复核均为 runtime PASS；本轮四次完整 host-clock 确认均 physical、安全、current admission、因果、有界 backlog PASS，但 FAST 服务尾延迟未达预注册门槛，因此不能把旧 evidence 的 PASS 当作当前 host 持续服务通过。B 未冻结，M2 未运行。

t0：2026-10-08 02:34:42 +08；hard stop：06:34:42；停止新重任务时间：06:04:42。提前停止原因是同类服务问题在最后安静复核仍出现，继续需要本轮禁止的 B 优化或放宽已冻结门槛。未耗尽4小时/50次预算。

QUALIFICATION SPLIT

- B_RUNTIME_MOTION_EXISTING_EVIDENCE = PASS（047/048，回顾性新增轴，不改原标签）。
- B_RUNTIME_MOTION 当前确认 = FAIL（4/4），B_RUNTIME_FROZEN = FALSE，B_RUNTIME_BASELINE_V1 = NOT_FROZEN。
- LEGACY_R2_MATCHED = FAIL（旧结果及本轮4次）。
- LEGACY_STRICT55 = FAIL（本轮4次 TASK 最大 activation age 均 >=55ms）。旧047仅 standalone <55ms age metric PASS（52.634693ms），旧048 FAIL（86.010587ms）；历史含R2/服务的 engineering composite 两次仍 FAIL。两种指标单列，避免重新耦合。

新增合同在任何新 physics 之前保存。实际采用旧 practical runtime 服务门槛：p50<=5.5ms，p95<=7.5ms，p99<=10ms，gap>10ms比例<=5%，miss fraction<=15%，rolling1s平均最大<=6ms，最大 unresolved backlog<=100ms；这些属于本合同 engineering qualification，不声称它们是运动完成的必要物理条件。没有在观察失败后修改门槛。原100ms lifecycle/current-state safety和native数学不变。

B STATUS / MOVEMENT / RUNTIME

| Run | Runtime | OUT / HOLD / RETURN s | FAST p50 / p95 / p99 ms | Rolling 1s mean max ms | Miss fraction | TASK activation max ms |
|---|---|---|---|---|---|---|
{table}

四次完整 OUTBOUND、RETURN 和真实受控 HOLD 全部通过原独立 physical scorer；HOLD dwell0.5s、shared minimum1s、两段reference completion及目标保持不变。HOLD 1.030–1.040s 只影响旧R2，当前runtime失败来自FAST服务门槛。最大backlog范围 {min(r['backlog']['maximum_backlog_s'] for r in records)*1000:.3f}–{max(r['backlog']['maximum_backlog_s'] for r in records)*1000:.3f}ms，未发现无限等待或失控backlog；每次 meaningful B native计划10或11个。所有 {compute['actual_native_steps']:,} 个真实native steps归属核对，causal violation=0，expired actual write=0。拒绝/取消、合法旧command承担等待区间及fallback逐request保存在各RUNTIME_QUALIFICATION和MULTIRATE，未用ACTIVATED冒充physical执行。

已有证据：047/048 FAST p50约5.004ms、p95约5.4ms，原始117046/116985步全部重审；旧raw文件 {len(raw_verified)} 个核验封存hash。当前四次与旧测量不同，不能据此推断硬件/未来资源状态的一般能力。

FORCE / MOMENT ATTRIBUTION

| Run | Raw full J_F N s | OUT / HOLD / RETURN J_F N s | Moment integral Nm s / peak Nm | Force peak N |
|---|---|---|---|---|
{costs}

逐阶段时长、积分覆盖时长、mean force、F/M peak、tracking和clearance见PACKAGE_RESULTS。分解使用原TASK trace左端force/moment积分，按实际transition拆分跨边界interval，三阶段和闭合原raw J_F；没有裁掉或补造HOLD。最后一个evaluation sample与实际COMPLETE commit的原始小间隔单列，不向raw J_F补未来样本。无M2，因此无coordination gain或moment tradeoff比较；不能把这四个B run互相比作学习收益。

M2

Frozen Q SHA256：3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9，前后核验一致，Q/G更新0。120D feature/selection replay NOT_RUN（用户要求B冻结后执行）；native M2 proposal、learning receipts和nonzero learning physical executions均0；M2 VALID/attempts=0/0；2smoke、paired matrix和B/M2 J_F均NOT_RUN，非零学习执行未证明。

Strict55 guard source audit已保存。历史E5 `min(40,55-reserve36)=19ms` 为strict55派生提前proposal拒绝，可在后续冻结B后的版本化M2 adapter单独关闭；本轮未关闭。100ms原生expiry/current ownership/current-state/safety/causal write保留；40ms bridge和mixed shadow budget职责未明的部分没有混删。历史count是issued modifiable proposal slots，不是执行次数；没有偷偷改成committed count，没有开发或反复修M2。

REPETITION SMOKE

NOT_RUN。B gate未通过；已有persistent session wrapper明确只支持SCIENTIFIC_SIMULATION，不能冒充actual host persistent session。不重构状态机或session接口。

NEGATIVE RESULTS

1. 001缺少隔离包action contract，在physical入口前startup失败；保留START/END及traceback，已仅复制原不可变输入文件修复，retry用新ID。
2. 四次新完整host确认的p95/p99/rolling1s服务门槛均FAIL；其中002的miss fraction也FAIL。安静复核仍失败，未挑选或删除失败。
3. HOLD仍使旧R2 FAIL；未做HOLD优化或放宽R2。
4. B未冻结，因此M2、paired force收益和repetition稳定性均未验证。

ACCOUNTING / PRESERVATION

5 attempts = 1 pre-physics startup failure + 4 complete host tasks；START=END=5。Added native steps={compute['actual_native_steps']:,}，physical simulation={compute['simulation_seconds']:.4f}s；已导出main model API calls={compute['main_model_API_calls']:,}，native worker calls={compute['native_worker_model_API_calls']:,}。warm/import/advisory未完整counter的部分标UNKNOWN；没有把缺失当0。所有TASK实际owner exitcode0/JOIN核对，commissioning close evidence保存，无当前task-owned运行进程。No auto-resume。

{resource_summary['samples']}条资源采样；WSL available最低{resource_summary['WSL_min_available_bytes']/2**30:.3f}GiB，Windows available最低{resource_summary['Windows_min_available_bytes']/2**30:.3f}GiB，commit headroom最低{resource_summary['Windows_min_commit_headroom_bytes']/2**30:.3f}GiB，swap稳定且无新增swap I/O/OOM。短时Windows内存低仅记录；没有持续真实压力，因此无需backoff，没有更改RAM/swap/power/WSL或终止无关进程。服务变慢的具体原因未被证实。

主repo branch/HEAD/status/index/staged diff与起点完全一致（见preservation/GIT_BEFORE与FINAL_PRESERVATION），未staged/commit/push/reset/delete。C13 {len(same)}文件逐位一致，{len(relocated)}文件仅精确package路径/名称替换，controller/Human/physics/safety/task数学/原expiry没有改变。历史封存包报告/ledger/manifest和frozen Q保护hash不变。新报告与新账本只在本包写入。

完整源/config/runner/source relocation/contract及输出hash、gzip CRC、compute/resource ledger保留在canonical包；Windows保留作者脚本、紧凑报告/manifest/账本/复核结果。新增文件范围仅本包装配、qualification audit、报告与最少确认配置；无B architecture/control或Q修改。

TOTAL：当前报告生成wall约{wall:.1f}min；最终close时间和added-data bytes见PACKAGE_CLOSED及FULL_PACKAGE_VERIFICATION。50attempt预算未耗尽，4小时预算未耗尽，不声称B原理上不可能通过。

NEXT：只读审查当前host的FAST服务尾延迟与原5ms反馈计算预算，定位它与047/048性能差异的来源，再决定下一包是否具备冻结条件。

REPORT PATH：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_runtime_qualification_decoupling_v1/REPORT.md

STOP。
'''
 (S/'REPORT.md').write_text(report);(W/'REPORT.md').write_text(report)
 for p in W.glob('*.py'):shutil.copy2(p,S/'code'/('author_'+p.name))
 code_manifest={str(p.relative_to(S)):sha(p) for p in ownfiles() if p.relative_to(S).parts[0] in ('source','deps','code','native','build') and 'results' not in p.relative_to(S).parts};save(S/'FINAL_CODE_MANIFEST.json',code_manifest)
 now=time.time();closed=dict(status='CLOSED',reason=blocked['status'],B_RUNTIME_FROZEN=False,physics_attempts=5,t0_unix=plan['t0_unix'],closed_unix=now,wall_seconds=now-plan['t0_unix'],hard_stop_unix=plan['hard_stop_unix'],physical_dispatch_permitted=False,no_auto_resume=True,budget_exhausted=False,START_END_balanced=True)
 save(S/'PACKAGE_CLOSED.json',closed);save(S/'STATE.json',closed|dict(active=[],phase='STOP',B_RUNTIME_MOTION='FAIL',M2='NOT_RUN'))
 gz=[]
 for p in ownfiles():
  if p.suffix=='.gz':
   n=0
   with gzip.open(p,'rb') as f:
    while b:=f.read(1048576):n+=len(b)
   gz.append(dict(path=str(p.relative_to(S)),uncompressed_bytes=n,CRC='PASS'))
 excludes={'FULL_PACKAGE_MANIFEST.json','reports/FULL_PACKAGE_VERIFICATION.json'}
 files={str(p.relative_to(S)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in ownfiles() if str(p.relative_to(S)) not in excludes};links={str(p.relative_to(S)):os.readlink(p) for p in S.rglob('*') if p.is_symlink()}
 save(S/'FULL_PACKAGE_MANIFEST.json',dict(status='SEALED',files=files,symlinks=links,excluded=sorted(excludes)+['**/__pycache__/**'],historical_symlinks_read_only=True))
 assert all(sha(S/rel)==v['sha256'] for rel,v in files.items())
 verification=dict(status='PASS',files=len(files),code_files=len(code_manifest),added_bytes=sum(v['bytes'] for v in files.values()),gzip_CRC=gz,START_END_balanced=True,workers_joined=True,Git_and_Q_protected=True,manifest_sha256=sha(S/'FULL_PACKAGE_MANIFEST.json'),report_sha256=sha(S/'REPORT.md'),verified_unix=time.time(),no_auto_resume=True)
 save(S/'reports/FULL_PACKAGE_VERIFICATION.json',verification)
 for name in ('PACKAGE_CLOSED.json','RUN_PLAN.json','STATE.json','TASK_LEDGER.json','ATTEMPTS.jsonl','FINAL_CODE_MANIFEST.json','FULL_PACKAGE_MANIFEST.json') :shutil.copy2(S/name,W/name)
 (W/'reports').mkdir(exist_ok=True)
 for p in (S/'reports').glob('*.json'):
  if p.name.endswith(('_FUNCTIONAL.json','_AUDIT.json','_QUALIFICATION.json')) and not p.name.endswith('_RUNTIME_QUALIFICATION.json'):continue
  shutil.copy2(p,W/'reports'/p.name)
 shutil.copy2(S/'preservation/FINAL_PRESERVATION.json',W/'reports/FINAL_PRESERVATION.json')
 print(json.dumps(dict(status='CLOSED_NOT_FROZEN',attempts=5,steps=compute['actual_native_steps'],wall_minutes=closed['wall_seconds']/60,added_MiB=verification['added_bytes']/2**20,files=verification['files'],CRC_files=len(gz),verification='PASS',report=str(W/'REPORT.md'))))
if __name__=='__main__':main()
