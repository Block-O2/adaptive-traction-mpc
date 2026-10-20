from pathlib import Path
import os,sys,json,time,hashlib,gzip,shutil,collections,subprocess,difflib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
sys.path.insert(0,str(S/'code'))
import numpy as np
from jitter_attribution import q
from bootstrap import sha,save,git_snapshot
def md(p,t):p.write_text(t+'\n',encoding='utf-8')
def main():
 assert not (S/'PACKAGE_CLOSED.json').exists()
 plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text());events=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
 starts=collections.Counter(r['id'] for r in events if r['event']=='START');ends=collections.Counter(r['id'] for r in events if r['event']=='END');assert starts==ends and all(v==1 for v in starts.values()) and set(starts)==set(ledger) and len(starts)<=20 and not any(r['status']=='RUNNING' for r in ledger.values())
 # Missing full exports must occupy their qualification rows without inventing metrics.
 for ident,v in ledger.items():
  p=S/'reports'/(ident+'_AXES.json')
  if not p.exists():
   assert v['worker_status']=='FAILED',ident
   save(p,dict(id=ident,label='RESEARCH_HOST_EXPERIMENT / RUNTIME_NOT_QUALIFIED',PHYSICAL_TASK_VALID='FAIL',HOST_EXECUTION_CAUSAL_VALID='NOT_EVALUABLE_FULL_EXPORT',FAST_RUNTIME_ENGINEERING_QUALIFIED='NOT_EVALUABLE',LEGACY_R2_MATCHED='NOT_EVALUABLE',LEGACY_STRICT55='NOT_EVALUABLE',worker_status=v['worker_status'],error=v.get('error'),native_steps=v['compute'].get('native_physics_steps'),secondary_raw_audit=str(S/'reports/005_M2_guard_off_retry_RECOVERED_EXECUTION_EVIDENCE.json') if ident.startswith('005_') else None,nonzero_execution_count=None,scope='Failed full task/export; no retrospective promotion from partial raw evidence.'))
 axes=[json.loads(p.read_text()) for p in sorted((S/'reports').glob('*_AXES.json'))];assert {r['id'] for r in axes}==set(ledger);valid=[r for r in axes if r['PHYSICAL_TASK_VALID']=='PASS' and r['HOST_EXECUTION_CAUSAL_VALID']=='PASS'];lean=[r for r in valid if not ledger[r['id']]['config'].get('attribution_only')]
 paired=json.loads((S/'PAIRED_RESULTS.json').read_text());history=json.loads((S/'reports/HISTORICAL_JITTER_ATTRIBUTION.json').read_text());diag=json.loads((S/'reports/THREAD_CPU_JITTER_DIAGNOSTICS.json').read_text());offline=json.loads((S/'reports/OFFLINE_INTERFACE_GATE.json').read_text())
 execution=[]
 for p in sorted((S/'reports').glob('*_EXECUTED_RESIDUAL_RECEIPTS.json')):
  record=json.loads(p.read_text())
  if record['rows']:execution.append(record)
 save(S/'EXECUTED_RESIDUAL_RECEIPTS.json',dict(status='AUDITED_ACTUAL_HOST_EXECUTION',full_exported_attempts=execution,partial_failed_export=str(S/'reports/005_M2_guard_off_retry_RECOVERED_EXECUTION_EVIDENCE.json'),new_Q_selection_executions=sum(r.get('new_selected_Q_executed',False) for a in execution for r in a['rows']),carried_learning_executions=sum(r.get('carried_learning_residual_executed',False) for a in execution for r in a['rows']),nonzero_native_plan_executions=sum(r['physically_executed_nonzero'] for a in execution for r in a['rows']),nonzero_native_plan_owned_steps=sum(r['actual_native_steps'] for a in execution for r in a['rows'] if r['physically_executed_nonzero']),step_scope='Actual native receipt steps owned by the accepted nonzero coordination segment, including its lawful continuation/fallback intervals. Native accepted delta and +/-progress identity independently checked. This is not a count of new Q decisions or a claim every .25ms interpolation sample has identical nonzero delta.',no_ACTIVATED_only_proof=True,Q_updates=0))
 receipts=json.loads((S/'EXECUTED_RESIDUAL_RECEIPTS.json').read_text());M2=[r for r in valid if ledger[r['id']]['config'].get('method')=='M2'];M2off=[r for r in M2 if not ledger[r['id']]['config'].get('strict55_guard',True)];on=next(r for r in axes if r['id']=='016_M2_guard_on_final');off=next(r for r in axes if r['id']=='017_M2_guard_off_export_retry')
 rows=[r for a in execution for r in a['rows'] if r.get('selected')];co=[r['worker'] for r in rows];latency=dict(selection_count=len(rows),new_proposal_late_carry_count=sum(r['late_carry'] for r in rows),Q_inference_ms=q([r['selection']['Q_inference_s']*1000 for r in rows]),context_ms=q([r['selection']['context_s']*1000 for r in rows]),native_candidate_certification_ms=q([r['selection']['validation_and_S_s']*1000 for r in rows]),worker_preproof_ms=q([e['worker_elapsed_ms'] for e in co]),source_age_at_preproof_ms=q([e['source_age_at_worker_return_ms'] for e in co]),original_full_TASK_compute_ms=q([r['lifecycle']['compute_ms'] for a in execution for r in a['rows'] if r['lifecycle'].get('compute_ms') is not None]),interpretation='Q inference is directly measured; difference in full worker latency between B/M2 includes context/candidate certification and different actual states, not pure Q inference. Inherited worker_elapsed/source_age labels stop before proof preparation; original lifecycle compute_finish is authoritative for full worker availability.')
 offrows=[r for a in execution if ledger[a['id']]['config'].get('method')=='M2' and not ledger[a['id']]['config'].get('strict55_guard',True) for r in a['rows'] if r.get('selected')]
 latency['guard_off_only']=dict(selection_count=len(offrows),late_carry=sum(r['late_carry'] for r in offrows),late_carry_fraction=sum(r['late_carry'] for r in offrows)/len(offrows),Q_inference_ms=q([r['selection']['Q_inference_s']*1000 for r in offrows]))
 save(S/'reports/M2_COMPUTE_AND_LATENESS.json',latency)
 # Complete original physical audits and force/moment metrics remain in axes.
 protected=json.loads((S/'preservation/PROTECTED_BEFORE.json').read_text());assert all(sha(Path(p))==v for p,v in protected.items());gb=json.loads((S/'preservation/GIT_BEFORE.json').read_text());ga=git_snapshot();assert ga==gb
 original_Q=S.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz';qhash=sha(original_Q);assert sha(S/'weights/frozen_Q_v1/weights.npz')==qhash=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'
 historical_raw=[]
 for r in history['rows']:
  for rel,h in r['raw_hashes'].items():assert sha(Path(r['folder'])/rel)==h;historical_raw.append(dict(path=str(Path(r['folder'])/rel),sha256=h))
 old=S.parent/'b_runtime_qualification_decoupling_v1';base=json.loads((old/'FINAL_CODE_MANIFEST.json').read_text());science=[];changes=[]
 for rel in base:
  if rel.split('/')[0] not in ('source','deps','native','build','code') or 'results' in Path(rel).parts:continue
  a,b=old/rel,S/rel
  if not b.exists():changes.append(dict(path=rel,status='MISSING'));continue
  if a.suffix=='.py' and rel.split('/')[0] in ('source','deps','code'):
   expected=a.read_text().replace(str(old),str(S)).replace('"b_runtime_qualification_decoupling_v1"','"m2_comprehensive_coordination_search_v1"').replace("'b_runtime_qualification_decoupling_v1'","'m2_comprehensive_coordination_search_v1'")
   equal=b.read_text()==expected
  else:equal=sha(a)==sha(b)
  if equal:science.append(rel)
  else:changes.append(dict(path=rel,status='CHANGED',before_sha256=sha(a),after_sha256=sha(b)))
 assert all(r['path'] in ('code/bootstrap.py','code/run_one.py','code/fast_task_ipc.py') for r in changes),changes
 source_diff=''
 for r in changes:
  a,b=old/r['path'],S/r['path'];source_diff+=''.join(difflib.unified_diff(a.read_text().splitlines(True),b.read_text().splitlines(True),fromfile='C13/'+r['path'],tofile='study/'+r['path']))
 md(S/'reports/FINAL_SOURCE_DIFF.patch',source_diff)
 save(S/'reports/FINAL_PRESERVATION.json',dict(status='PASS',Git_before_equals_after=True,Git=ga,protected_files_verified=len(protected),historical_raw=historical_raw,Q_sha256=qhash,Q_changed=False,unchanged_or_exact_relocated_files=len(science),changed_original_harness_files=changes,controller_Human_physics_safety_task_native_binary_unchanged=True,main_repo_written=False,historical_evidence_written=False))
 joins=[]
 for ident in ledger:
  p=S/'output'/(ident+'_DIRECT_IPC.json')
  if p.exists():
   ipc=json.loads(p.read_text());j=[r for r in ipc['rows'] if r['event']=='JOIN'];assert j and all(r['joined'] and r['exitcode']==0 for r in j),ident;joins.append(dict(id=ident,joins=j))
 live=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S/'code/fast_dispatch.py') in cmd or str(S/'code/run_one.py') in cmd or str(S/'code/run_registered_batch.py') in cmd:live.append(dict(pid=int(p.name),cmd=cmd))
  except OSError:pass
 assert not live,live
 save(S/'reports/WORKER_JOIN_AUDIT.json',dict(status='PASS',rows=joins,live_owned_dispatch_or_run_processes=live,START_END_bijection=True))
 import runner
 runner.sample(owner='FINAL_CLOSED_PACKAGE_PREFLIGHT')
 resource=[json.loads(l) for l in (S/'output/RESOURCE_LOG.jsonl').read_text().splitlines()];resources=dict(samples=len(resource),WSL_available_min_GiB=min(r['mem_available'] for r in resource)/2**30,Windows_available_min_GiB=min(r['windows'].get('available',2**60) for r in resource)/2**30,Windows_commit_headroom_min_GiB=min(r['windows'].get('commit_headroom',2**60) for r in resource)/2**30,owned_PSS_peak_GiB=max(r['PSS'] for r in resource)/2**30,swap_bytes_range=[min(r['swap_used'] for r in resource),max(r['swap_used'] for r in resource)],swap_in_delta=resource[-1]['swap_in']-resource[0]['swap_in'],swap_out_delta=resource[-1]['swap_out']-resource[0]['swap_out'],OOM_delta=resource[-1]['oom_kill']-resource[0]['oom_kill'],CPU_and_process_samples=str(S/'output/RESOURCE_LOG.jsonl'),settings_modified=False,unknown_processes_killed=False,power_mode='Windows Balanced scheme 381b4222-f694-41f0-9685-ff5bb260df2e; unchanged; readback HOST_POWER_MODE.txt; OEM quiet mode unobserved',scope='before/after dispatch and every45s during physics; no continuous resource monitoring claim')
 save(S/'reports/RESOURCE_SUMMARY.json',resources)
 assert all(v['compute'].get('native_physics_steps') is not None for v in ledger.values())
 api={key:dict(known_sum=sum(v['compute'][key] for v in ledger.values() if v['compute'].get(key) is not None),missing_attempts=[k for k,v in ledger.items() if v['compute'].get(key) is None]) for key in ('main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')}
 compute=dict(attempts=len(ledger),full_exported_physical_causal_valid=len(valid),full_exported_M2_valid=len(M2),failed_or_incomplete=[dict(id=k,status=v['worker_status'],error=v.get('error'),steps=v['compute'].get('native_physics_steps')) for k,v in ledger.items() if k not in {r['id'] for r in valid}],native_steps=sum(v['compute']['native_physics_steps'] for v in ledger.values()),simulation_seconds=sum(v['compute']['native_physics_steps'] for v in ledger.values())*.00025,offline_added_native_physics=0,Q_training=0,Q_online_updates=0,G_calls=0,START=dict(starts),END=dict(ends),model_API_counters=api,model_API_unknown_scope='warm/advisory/import counters not fully exported; no missing values treated as measured zero',wall_seconds=time.time()-plan['t0_unix'])
 save(S/'reports/COMPUTE_LEDGER.json',compute)
 def timing_table(rs):
  return '\n'.join(f"| {r['id']} | {r['service_gap_ms']['p50']:.3f} / {r['service_gap_ms']['p95']:.3f} / {r['service_gap_ms']['p99']:.3f} | {r['rolling_1s_ms']['max']:.3f} | {r['miss_fraction']:.2%} | {r['backlog']['maximum_backlog_s']*1000:.3f} | {r['FAST_RUNTIME_ENGINEERING_QUALIFIED']} |" for r in rs)
 historical_table='\n'.join(f"| {r['id']} | {r['FAST_gap_ms']['p50']:.3f} / {r['FAST_gap_ms']['p95']:.3f} / {r['FAST_gap_ms']['p99']:.3f} | {r['rolling_1s_ms']['max']:.3f} | {r['miss_fraction']:.2%} | {r['owner_work_ms']['p95']:.3f} | {r['native_step_compute_ms']['p95']*1000:.2f} |" for r in history['rows'])
 attribution=f'''# FAST Jitter Attribution

STATUS: **INCONCLUSIVE_ROOT_CAUSE / CURRENT_TESTED_FAST_PASS**. Historical degradation is real, while this package's lean runs returned close to 047/048 without a B performance repair. This does not retroactively qualify 002–005 or guarantee future scheduling.

| Historical run | FAST p50 / p95 / p99 ms | rolling1s max ms | miss | owner-work p95 ms | native-step p95 us |
|---|---|---|---|---|---|---|
{historical_table}

The historical native binaries are hash-identical. All controller, Human, physics, task, FAST adapter and measurement code match after exact package path relocation; only seven added authoring/bootstrap/report harness files differ. Timing start/finish semantics match. Matched nominal003/004 and deviation002/005 configurations preserve the physical/task settings; seed/report labels differ where explicitly recorded in HISTORICAL_JITTER_ATTRIBUTION.json. Per-phase OUTBOUND/HOLD/RETURN, planner-active/idle distributions and every >7.5/10/15ms cycle are retained in *_JITTER_CYCLES.json.

Evidence supports a broad owner-path slowdown: p95 owner work rose from 4.176–4.331ms to 6.599–7.571ms and native-step wall spans also widened. Planner-active tails are worse within runs, but idle p95 also rose from about5.39–5.42ms to7.79–9.54ms. The regression appears in multiple task phases, so rare handoffs cannot explain its frequency. Physics catch-up is separately counted per interval; it was not proved the dominant >50% contributor to these long cycles. Aggregate feedback/observer/receipt spans must not be mistaken for a single function's exclusive compute cost.

Historical per-service thread CPU and exact descheduling were not recorded, so compute-heavy vs descheduling remains unresolved. GC, frequency/power, Windows memory and WSL scheduler causation have not been established. Current native active-session GC deferral and recorded resource values are retained; no CPU-frequency or memory-policy change was made.

Two extra B host controls used thread-CPU/GC probes and remain attribution-only. The capture hook did not replace the compiled commissioning namespace; its initial cumulative owner-span interpretation was invalidated and retained as THREAD_CPU_JITTER_DIAGNOSTICS_v1_INVALID_OWNER_SCOPE.json. Valid adjacent marker differences use the same capture anchor and include scheduled wait plus physics catch-up. They distinguish CPU accumulation from off-CPU time for the observed restored runs, but cannot retrospectively establish why002–005 slowed. Raw diagnostics and limits are explicit. No additional random micro-optimization or controller repair was attempted.

Lean current runs:

| Run | FAST p50 / p95 / p99 ms | rolling1s max ms | miss | backlog max ms | frozen engineering axis |
|---|---|---|---|---|---|
{timing_table(lean)}

No local B implementation defect was proved to cause the historical regression. The M2 copied-namespace adapter defect is independently confirmed and repaired; it is not an explanation for B timing002–005.
'''
 md(S/'FAST_JITTER_ATTRIBUTION.md',attribution)
 m2report=f'''# Frozen M2 Host Execution

STATUS: **M2_HOST_RESEARCH_FEASIBLE**; all runs retain **RESEARCH_HOST_EXPERIMENT / RUNTIME_NOT_QUALIFIED**. This is actual host-clock MuJoCo evidence, not hardware deployment qualification.

Frozen Q SHA256: {qhash}. Pre/post original and copied Q match; training/online updates/G/adaptive-Q/P full-repetition optimizer/Human matrix expansion=0 or disabled. B control math, Human physics, native dt.25ms, target period5ms, safety, current-state admission, fallback and timestamps are unchanged.

Offline interface gate passed {len(offline['records'])} saved causal development contexts: 55+3+30+30+2=120D in exact order, issued proposal count/masks/carry, K3[.1,.4,.7], same-state candidate ranking, full-evaluate vs Q-first identity and zero residual matching native B. Count remains issued modifiable proposals; rejects can consume slots. Counts beyond5 leave no new modifiable slot and zero candidate action; they are not silently replaced with committed count.

The strict55 reserve36 was an engineering early-return reserve: guard-on min(40,55-36)=19ms; guard-off removes only strict55 reserve and keeps40ms. Original100ms lifecycle/final actual write age, current compatibility/mechanics/ROM and original handoff/fallback remain. Guard-on016 completed safely with {on['selection_count']} Q selections, {on['late_carry_count']} late carries and {on['nonzero_execution_count']} nonzero executions. Guard-off017 completed safely with {off['selection_count']} selections, {off['late_carry_count']} late carries and {off['nonzero_execution_count']} accepted nonzero native plan executions covering {off['nonzero_native_steps']:,} receipt-owned physical steps.

Execution chain is independently recorded: immutable feature/source inputs and Q ranking → candidate identity → accepted native differential metadata (modified progress minus nominal progress equals[delta,-delta]) → original lifecycle admission → original actual command receipts → integrated native steps. New Q selections, carry of earlier valid learning plans, cancellation and early rejection are separate. Total fully exported host evidence: {receipts['new_Q_selection_executions']} new selected-Q executions, {receipts['carried_learning_executions']} carried-learning executions, {receipts['nonzero_native_plan_executions']} nonzero native plan executions and {receipts['nonzero_native_plan_owned_steps']:,} associated native steps. Step counts include lawful native continuation/fallback in the owning segment; they are not counts of newly learned decisions or identical delta at every interpolation sample.

M2 physically/causally valid exported attempts={len(M2)}. Direct Q inference p50/p95/p99 ms={latency['Q_inference_ms'].get('p50',0):.4f}/{latency['Q_inference_ms'].get('p95',0):.4f}/{latency['Q_inference_ms'].get('p99',0):.4f}; full context/native candidate certification and lifecycle compute are reported separately in M2_COMPUTE_AND_LATENESS.json. Across selections, late carry={latency['new_proposal_late_carry_count']}/{latency['selection_count']}. Full-worker B/M2 differences include different actual states and native certificates; they cannot all be called Q inference overhead.

Negative attempts002/003 failed the envelope route before learning execution. Partial routing repair004 failed UNCONSUMED_NATIVE_REQUEST_HINT because commissioning_owner had cloned the loop globals before snapshot rebinding. The one integration repair cycle has two explicitly retained patch revisions; final binding preserves the original multirate snapshot logger. No selection repair cycle followed.005 reached the final native task path but PlanRequest in evidence prevented summary export; original failure and raw causal trace were retained, then evidence-only sc.clean serialization was corrected.005 is excluded from full valid tasks/pairs and retained separately as failed-export partial evidence. No failed run is relabeled successful.

The complete paired raw force, phase-duration/mean-force decomposition, moments, safety/clearance/tracking and runtime metrics are in PAIRED_RESULTS.json. Benefits are descriptive exposed-condition repeats, never a personalized/state×plan interaction proof or comparison against old scientific1335N·s. Persistent-session wrapper and extra independent prefix tests were NOT_RUN; each episode reinitializes Human/commissioning, never a continuous Human repetition.
'''
 md(S/'M2_HOST_EXECUTION_REPORT.md',m2report)
 pair_table='\n'.join(f"| {p['pair_id']} | {p.get('raw_B_J_F_N_s',float('nan')):.3f} | {p.get('raw_M2_J_F_N_s',float('nan')):.3f} | {p.get('valid_paired_gain') if p.get('valid_paired_gain') is not None else float('nan'):.3f} | {p.get('moment_delta_percent',float('nan')):+.2f}% | {p.get('nonzero_M2_execution_count',0)} | {p['status']} |" for p in paired['pairs'])
 phase_table='\n'.join(f"| {p['pair_id']} / {phase} | {v['B']['J_F_N_s']:.3f} / {v['M2']['J_F_N_s']:.3f} | {v['B']['phase_clock_duration_s']:.5f} / {v['M2']['phase_clock_duration_s']:.5f} | {v['B']['mean_force_N']:.3f} / {v['M2']['mean_force_N']:.3f} | {v['duration_contribution_N_s']:+.3f} | {v['mean_force_contribution_N_s']:+.3f} |" for p in paired['pairs'] if p['status']=='VALID_PAIR' for phase,v in p['phases'].items())
 physical_table='\n'.join(f"| {p['pair_id']} / {method} | {p['force_peak_N'][method]:.3f} | {p['raw_'+method+'_moment_integral_Nm_s']:.3f} / {p['moment_peak_Nm'][method]:.3f} | {p['physical_summary'][p[method+'_id']]['minimum_true_shank_clearance_m']*1000:.3f} / {p['physical_summary'][p[method+'_id']]['minimum_measured_sleeve_gap_m']*1000:.3f} | {' / '.join(format(x,'.3f') for x in p['physical_summary'][p[method+'_id']]['true_reference_tracking_RMS_deg'])} |" for p in paired['pairs'] if p['status']=='VALID_PAIR' for method in ('B','M2'))
 axis_table='\n'.join(f"| {r['id']} | {r['PHYSICAL_TASK_VALID']} | {r['HOST_EXECUTION_CAUSAL_VALID']} | {r['FAST_RUNTIME_ENGINEERING_QUALIFIED']} | {r['LEGACY_R2_MATCHED']} | {r['LEGACY_STRICT55']} |" for r in axes)
 next_step='On a new separately authorized bounded package, capture matched service-start/end thread CPU and scheduler wait on the actual compiled loop during a recurrence of the002–005 slowdown; preserve the frozen B/Q/40ms bridge and all safety contracts.'
 report=f'''# B FAST Jitter Attribution & Frozen M2 Host-Clock Execution v1

**STATUS**: Track A historical root cause remains unconfirmed; current tested FAST service recovered without B repair. Track B proves **M2_HOST_RESEARCH_FEASIBLE**. No **REALTIME_DEPLOYMENT_QUALIFIED** claim. Both tracks completed independently and no heavy physical runs overlapped.

**Track A — FAST**: historical047/048 p95 about5.4ms vs002–005 7.87–9.58ms was reconstructed read-only. Mathematical/source/native-binary/timing-boundary equality is confirmed; broad owner/physics wall slowdown and idle-phase regression are supported, a CPU-frequency/Windows-memory/descheduling root cause is not. Two low-cost B controls and their measurement limits are retained. No controller performance repair. Full tail events and p50/p95/p99, rolling1s, miss/backlog are in FAST_JITTER_ATTRIBUTION.md and per-run axes.

**Track B — M2**: offline120D/K3/issued slots/mask/Q identity PASS; guard-on19ms is separated from retained40ms bridge/100ms native lifecycle. Guard-on016={on['nonzero_execution_count']} nonzero executions, guard-off017={off['nonzero_execution_count']}. Fully exported M2 valid={len(M2)}, nonzero native plan executions={receipts['nonzero_native_plan_executions']}, associated native steps={receipts['nonzero_native_plan_owned_steps']:,}; new selection/carry separate. No Q training or online adaptation. Detailed lineage: EXECUTED_RESIDUAL_RECEIPTS.json. Compute and lateness: M2_COMPUTE_AND_LATENESS.json.

**Paired B vs M2**:

| Pair | raw B J_F N·s | raw M2 J_F N·s | B−M2 N·s | moment integral change | nonzero M2 plans | result |
|---|---|---|---|---|---|---|
{pair_table}

All four exposed-condition gains are positive, but moment integrals increase6.75–24.20%. Deviation pair1 force peak increases107.18→112.30N. True/estimated tracking and clearances are fully reported; M2 does not dominate every metric. The legal-deviation tests repeat one registered two-action prefix at two seeds; different independent prefixes were NOT_RUN, so no claim across arbitrary legal deviations is supported.

| Pair / phase | J_F B / M2 N·s | clock duration B / M2 s | mean force B / M2 N | duration contribution M2−B N·s | mean-force contribution M2−B N·s |
|---|---|---|---|---|---|
{phase_table}

| Pair / method | force peak N | moment integral Nm·s / peak Nm | true shank / measured sleeve minimum mm | true-reference TASK RMS tracking joint1 / joint2 deg |
|---|---|---|---|---|
{physical_table}

Phase-duration attribution uses the exact symmetric product decomposition per OUT/HOLD/RETURN: ΔJ=Δduration×average(mean force)+Δmean force×average(duration). Both physical phase-clock and integrated trace durations are retained, and phase sums close the original full-task integral. No HOLD clipping, shortening or fabricated time; mean-force contribution is evidence compatible with coordination, not a pure causal identification. Same physical setup/seed/waypoints/instrumentation is frozen within each pair; real-time measured commissioning fits may differ. Moment integrals/peaks, raw force/force peak, complete native physical safety/clearance/tracking, proposal age, all rejects/fallback and runtime axes remain in PAIRED_RESULTS.json. No old1335N·s subtraction.

**Qualification** (independent axes; diagnostics do not establish engineering qualification):

| Attempt | physical | causal host | FAST engineering | legacy R2 | legacy strict55 |
|---|---|---|---|---|---|
{axis_table}

All conclusions are finite actual host-clock development simulation results. Passing FAST numeric criteria on observed lean runs does not promote B/M2 to formal runtime or hardware qualification. Legacy R2 and strict55 are reported independently and historical results unchanged.

**Negative evidence**:002/003 failed envelope routing;004 retained a partial repair's unconsumed hint;005 failed artifact export and remains partial evidence only. One integration repair cycle has two source-binding/route patch revisions, followed by one evidence-only dataclass serialization correction. The diagnostic capture-hook scope was invalidated; adjacent marker differences are retained with scheduled-wait limits. Historical slowdown cause remains unknown. Late/cancelled Q proposals and consumed issued slots remain visible. No persistent Human session or personalization claim.

**Budget**: t0=2026-10-08 12:56:02+08; hard cap15:56:02; dispatch cutoff15:36:02. At report generation wall={compute['wall_seconds']/60:.2f}min, physical attempts={compute['attempts']}/20, native steps={compute['native_steps']:,}, physical simulation={compute['simulation_seconds']:.5f}s. START=END={len(starts)}. Added bytes/CRC/final close time are in FULL_PACKAGE_VERIFICATION.json and PACKAGE_CLOSED.json. All original TASK workers JOIN exitcode0; no task-owned process remains. WSL available minimum={resources['WSL_available_min_GiB']:.3f}GiB; Windows available minimum={resources['Windows_available_min_GiB']:.3f}GiB; commit headroom minimum={resources['Windows_commit_headroom_min_GiB']:.3f}GiB; swap in/out deltas={resources['swap_in_delta']}/{resources['swap_out_delta']}, OOM delta={resources['OOM_delta']}. Main Git branch/HEAD/status/index/staged diff, historical source/data and frozen Q remain unchanged. No WSL restart or power/RAM/swap/scheduler change; no unrelated process killed.

**NEXT**: {next_step}

**REPORT PATH**: /home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1/REPORT.md; Windows review copy C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1/REPORT.md.

STOP. No automatic follow-on work.
'''
 md(S/'REPORT.md',report)
 qualification=json.loads((S/'QUALIFICATION_CONTRACT.json').read_text());qualification['observed_results']=dict(per_attempt=[{k:r.get(k) for k in ('id','PHYSICAL_TASK_VALID','HOST_EXECUTION_CAUSAL_VALID','FAST_RUNTIME_ENGINEERING_QUALIFIED','LEGACY_R2_MATCHED','LEGACY_STRICT55')} for r in axes],Track_A='INCONCLUSIVE_ROOT_CAUSE_CURRENT_TESTED_FAST_PASS',Track_B='M2_HOST_RESEARCH_FEASIBLE',REALTIME_DEPLOYMENT_QUALIFIED=False,original_thresholds_unchanged=True);save(S/'QUALIFICATION_CONTRACT.json',qualification)
 authored=S/'code/host_v1_author_sources';authored.mkdir(exist_ok=True)
 for p in W.glob('*.py'):shutil.copy2(p,authored/p.name)
 now=time.time();closed=dict(status='CLOSED',t0_unix=plan['t0_unix'],closed_unix=now,wall_seconds=now-plan['t0_unix'],hard_stop_unix=plan['hard_stop_unix'],physics_attempts=len(ledger),native_steps=compute['native_steps'],START_END_balanced=True,active=[],no_auto_resume=True,physical_dispatch_permitted=False,budget_exhausted=False)
 save(S/'PACKAGE_CLOSED.json',closed);save(S/'STATE.json',closed|dict(phase='STOP'))
 fileslist=[p for p in S.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts]
 code={str(p.relative_to(S)):sha(p) for p in fileslist if p.relative_to(S).parts[0] in ('source','deps','code','native','build') and 'results' not in p.relative_to(S).parts};save(S/'FINAL_CODE_MANIFEST.json',code)
 crc=[]
 print('VERIFY_GZIP_AND_MANIFEST',len(ledger),'attempts',flush=True)
 for p in fileslist:
  if p.suffix=='.gz':
   n=0
   with gzip.open(p,'rb') as f:
    while b:=f.read(2**20):n+=len(b)
   crc.append(dict(path=str(p.relative_to(S)),uncompressed_bytes=n,CRC='PASS'))
 excludes={'FULL_PACKAGE_MANIFEST.json','reports/FULL_PACKAGE_VERIFICATION.json'}
 files={str(p.relative_to(S)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in S.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and str(p.relative_to(S)) not in excludes}
 save(S/'FULL_PACKAGE_MANIFEST.json',dict(status='SEALED',files=files,excluded=sorted(excludes)+['**/__pycache__/**']))
 assert all(sha(S/rel)==v['sha256'] for rel,v in files.items())
 verification=dict(status='PASS',files=len(files),code_files=len(code),added_bytes=sum(v['bytes'] for v in files.values()),gzip_CRC=crc,Git_Q_history_preserved=True,workers_joined=True,START_END_balanced=True,manifest_sha256=sha(S/'FULL_PACKAGE_MANIFEST.json'),report_sha256=sha(S/'REPORT.md'),verified_unix=time.time(),no_auto_resume=True)
 save(S/'reports/FULL_PACKAGE_VERIFICATION.json',verification)
 (W/'reports').mkdir(exist_ok=True)
 for name in ('REPORT.md','FAST_JITTER_ATTRIBUTION.md','M2_HOST_EXECUTION_REPORT.md','EXPERIMENT_CONTRACT.json','QUALIFICATION_CONTRACT.json','PAIRED_RESULTS.json','EXECUTED_RESIDUAL_RECEIPTS.json','RUN_PLAN.json','TASK_LEDGER.json','ATTEMPTS.jsonl','STATE.json','PACKAGE_CLOSED.json','FINAL_CODE_MANIFEST.json','FULL_PACKAGE_MANIFEST.json'):shutil.copy2(S/name,W/name)
 for p in (S/'reports').iterdir():
  if p.is_file():shutil.copy2(p,W/'reports'/p.name)
 print(json.dumps(dict(status='CLOSED',attempts=len(ledger),valid_host_tasks=len(valid),M2_valid=len(M2),nonzero=receipts['nonzero_native_plan_executions'],native_steps=compute['native_steps'],wall_minutes=closed['wall_seconds']/60,added_MiB=verification['added_bytes']/2**20,verification='PASS',paired_summary=paired['summary'],report=str(W/'REPORT.md'))),flush=True)
if __name__=='__main__':main()
