"""Close only this completed study; never dispatch experiments or touch git."""
from task_bootstrap import *
import os,statistics,collections

def read(name):return json.loads((STUDY/name).read_text())
def jlines(name):return [json.loads(s) for s in (STUDY/name).read_text().splitlines()]
def fmt(v,n=3):return 'NA' if v is None else f'{v:.{n}f}'

def main():
 assert (STUDY/'RUNNER_STOP.json').exists(),'JOIN_OWN_RUNNER_BEFORE_FINALIZATION'
 events=jlines('ATTEMPTS.jsonl');starts={r['id']:r for r in events if r['event']=='START'};ends={r['id']:r for r in events if r['event']=='END'}
 assert set(starts)==set(ends) and len(starts)<=240
 ledger=read('TASK_LEDGER.json');assert not [p for p in (STUDY/'queue').glob('*.json') if p.stem not in ledger]
 assert read('RECOVERY_AUDIT.json')['status']=='PASS'
 analyses={v:read('ANALYSIS_'+v+'.json') for v in ('v1','v1_repeat')}
 assert all(len(a['rows'])==20 for a in analyses.values())
 diagnostic=read('DIAGNOSTIC_ANALYSIS_v1.json');assert diagnostic['replay_gate']['status']=='PASS'
 wall=read('WALL_ANALYSIS_v1.json');assert len(wall['rows'])==7
 rows=jlines('COMPUTE_LEDGER.jsonl');assert len(rows)==len(starts)
 corrections={r['id']:r for r in jlines('COMPUTE_CORRECTIONS.jsonl')}
 effective=[]
 for original in rows:
  r=dict(original)
  if r['id'] in corrections:
   c=corrections[r['id']]
   for k in ('actual_new_simulation_s','actual_new_native_steps','main_model_calls'):r[k]=c.get(k)
   r['native_worker_model_calls']=c.get('native_worker_model_calls_separate');r['correction_basis']=c['basis']
  effective.append(r)
 fields=('actual_new_simulation_s','actual_new_native_steps','main_model_calls','native_worker_model_calls')
 compute=dict(attempts=len(starts),entries=len(effective),totals_lower_bound={k:sum(r.get(k) or 0 for r in effective) for k in fields},unknown_ids={k:[r['id'] for r in effective if r.get(k) is None] for k in fields},parent_wall_s=sum(r['wall_s'] for r in effective if r['wall_role'].startswith('top-level')),child_wall_never_added=True,main_native_counts_not_added_together=True,correction_ids=list(corrections),original_append_only_ledger_retained=True)
 save(STUDY/'COMPUTE_EFFECTIVE_SUMMARY.json',compute)
 resource=jlines('output/RESOURCES.jsonl')
 resources=dict(samples=len(resource),sample_interval_s=45,min_WSL_available_GiB=min(r['mem_available'] for r in resource)/2**30,min_windows_commit_GiB=min(r['windows'].get('commit_headroom',float('inf')) for r in resource)/2**30,max_owned_PSS_GiB=max(r['PSS'] for r in resource)/2**30,max_owned_process_count=max(r['owned_count'] for r in resource),swap_start_MiB=resource[0]['swap_used']/2**20,swap_end_MiB=resource[-1]['swap_used']/2**20,swap_in_delta=resource[-1]['swap_in']-resource[0]['swap_in'],swap_out_delta=resource[-1]['swap_out']-resource[0]['swap_out'],oom_delta=resource[-1]['oom_kill']-resource[0]['oom_kill'],last=resource[-1],recovery_file_present=(STUDY/'RESOURCE_STATE.json').exists(),unrelated_processes_never_killed=True)
 save(STUDY/'RESOURCE_SUMMARY.json',resources)
 allscience=[r for a in analyses.values() for r in a['rows']]
 p_calls=[]
 for r in allscience:
  original=read('output/'+r['id']+'_RESULT.json');p_calls.append(original['P_full_performance_calls']);assert original['P_import_blocker']
  assert all(str(STUDY) in p for p in original['import_sources'].values())
 assert not any(p_calls)
 methods={}
 for m in ('M0','M1','M2','M3','M4'):
  rr=[r for r in allscience if r['method']==m and r['valid']];pp=[p for a in analyses.values() for p in a['paired'] if p['method']==m and p['valid_comparable']]
  methods[m]=dict(valid=len(rr),attempts=8,J_F_mean=statistics.mean(r['J_F'] for r in rr) if rr else None,moment_mean=statistics.mean(r['moment_integral'] for r in rr) if rr else None,duration_mean=statistics.mean(r['duration_s'] for r in rr) if rr else None,paired_J_F_improvement_pct=statistics.mean(p['J_F_improvement_pct'] for p in pp) if pp else None,paired_range_pct=[min(p['J_F_improvement_pct'] for p in pp),max(p['J_F_improvement_pct'] for p in pp)] if pp else None,moment_change_pct=statistics.mean(p['moment_change_pct'] for p in pp) if pp else None,coordinator_max_ms=max(r.get('coordinator_max_s',0) for r in rr)*1000 if rr else None,quality_repeat_benefit=all(analyses[v]['summary'][m]['quality_engineering_gate'] for v in analyses),actual_online_qualified=False)
 save(STUDY/'COMBINED_MATRIX.json',dict(methods=methods,versions=list(analyses),scientific=True,P_calls=sum(p_calls),new_human_claim=False,nominal_replication_not_new_state=True))
 components={};subgroups={}
 for m in ('M1','M2','M3','M4'):
  selections=[json.loads((STUDY/'output'/(r['id']+'_SELECTIONS.json')).read_text()) for r in allscience if r['method']==m]
  sr=[s for f in selections for s in f['rows']]
  components[m]=dict(decisions=len(sr),Q_candidate_evaluations=sum(f['network_Q_calls'] for f in selections),G_calls=sum(f['network_G_calls'] for f in selections),coordinator_late_fraction=sum(s['late'] for s in sr)/len(sr),components_mean_ms={k:1000*statistics.mean(s[k] for s in sr) for k in ('context_s','generation_s','validation_and_S_s','Q_inference_s','submission_s','end_to_end_s')})
  subgroups[m]={}
  for group in ('nominal','deviation'):
   pairs=[p for a in analyses.values() for p in a['paired'] if p['method']==m and p['valid_comparable'] and group in p['group']]
   subgroups[m][group]=dict(n=len(pairs),paired_improvement_mean_pct=statistics.mean(p['J_F_improvement_pct'] for p in pairs),range_pct=[min(p['J_F_improvement_pct'] for p in pairs),max(p['J_F_improvement_pct'] for p in pairs)])
 save(STUDY/'LATENCY_COMPONENT_SUMMARY.json',components);save(STUDY/'SUBGROUP_SUMMARY.json',subgroups)
 pilot=dict(status='NOT_RUN',reason='actual host-clock execution not qualified; scientific force reduction alone cannot authorize adaptive online pilot',hardware_runs=0)
 save(STUDY/'PILOT_STATUS.json',pilot)
 # All essential raw traces remain unique; hashes stream without loading history.
 files=[]
 for p in sorted(STUDY.rglob('*')):
  if not p.is_file() or p.name in ('FINAL_MANIFEST.json','FINAL_STATUS.json','FINAL_REPORT.md','FINAL_AUDIT.json','DELIVERY_MANIFEST.json','CHECKPOINT.json','PROGRESS.md','RESUME.md') or p.suffix in ('.lock','.tmp'):continue
  files.append(dict(path=str(p.relative_to(STUDY)),bytes=p.stat().st_size,sha256=sha(p)))
 total=sum(r['bytes'] for r in files);assert total<12*2**30,'NEW_FILE_TARGET_EXCEEDED'
 manifest=dict(unix=time.time(),files=files,total_bytes=total,streaming_hash=True,raw_unique_evidence_retained=True)
 save(STUDY/'FINAL_MANIFEST.json',manifest)
 elapsed=time.time()-START
 status=dict(status='COMPLETE_STOPPED',elapsed_h=elapsed/3600,physics_attempts=len(starts),bytes=total,methods=methods,P_calls=0,quality_effective=methods['M2']['quality_repeat_benefit'],online_qualified=False,pilot=pilot,substantive_development_rounds=1,independent_initialization_fits=2,metadata_repairs=2,completed=['frozen B boundary','exact zero regression and repair regression','CPU fork/restore gate','9 distinct causal state groups','linear/2x128 Q and 3-head G','two complete 20-run paired matrices','7 actual host-clock runs including 2 metadata-repaired retests','committed versus rolling attribution','negative evidence preservation','resources/compute/source/recovery audit'],uncompleted=['online-qualified learning execution','conditional pilot: not eligible'],stop_reason='all planned work and meaningful authorized extensions complete; early close, not ordinary negative-gate hard stop',next_single_recommendation='profile and reuse native context/candidate certification to reduce end-to-end latency, retaining original control/safety and bridge; then repeat actual host-clock qualification')
 save(STUDY/'FINAL_STATUS.json',status)
 text=['# B-Native Learning Matrix v1 — final report','',f'STATUS: COMPLETE_STOPPED. {elapsed/3600:.3f} h; {len(starts)}/240 physical attempts; {total/2**30:.3f} GiB under this isolated study.','',
 '学习直接接到冻结 B 后，在本已暴露人体的科学仿真中，Q 降低完整任务力积分，独立初始化/新合法前缀复验仍成立。G 没有稳定的额外力积分收益。真实 host-clock 执行未合格，不能认为已满足 B 在线时限，未进行 pilot 或硬件。','',
 '## Scope and scientific integrity','',
 'Primary `/home/hank/coding/adaptive-traction-mpc-learning` preserved including dirty worktree/index/head. No stage/commit/push/merge/reset/stash, framework reinstall or system setting changes. `RECOVERY_AUDIT.json` records source/hash/git checks. Frozen source snapshot imports are explicitly audited; old results were not copied as fresh labels.','',
 'B chain: causal commissioning/observer → original adaptive human-waypoint MPC/local predictions → native scheduler/quintic and receipt governor → original ROM/mechanics/clearance/tracking certificates and current-model revalidation → native simulated plant and fallback. Original HOLD/phase/terminal authority remains B. See `B_BOUNDARY.json` and `SOURCE.json`.','',
 'P Predictor/full repetition performance, known_model truth provisioning, research V_base, 2×8 CEM/SearchInterface and P-specific timing screening are excluded. Import firewall and runtime call stacks record 0 P full-performance calls for all 40 formal scientific runs. Native safety lookahead remains intact.','',
 '`B_ZERO_GATE.json` and `B_ZERO_CONTEXT_REPAIR_GATE.json`: full frozen B traces match exactly, including reference/physical fields and costs (no relaxed tolerance). CPU forks restore native MuJoCo/planner/observer/sensor/history/RNG state, and parents remain hash-identical after joined children. `BRANCH_GATE.json` and per-state snapshots retain evidence.','',
 '## Frozen method and data contracts','',
 'M0 original B; M1 same six ordinary plans plus original B current-segment score S; M2 same ordinary plans plus direct remaining-cost Q; M3 three ordinary/B/carry + three G heads with same S; M4 same mixed pool with Q. S uses original cloned native decide/_evaluate, not an invented repetition force predictor. Six online candidates everywhere; offline attribution union of nine is permanently outside fitting.','',
 'Q input 120D = 55D causal commissioned B information + 3 residual history + 30 masked candidate U + 30 masked legal carry + 2 issued counts. Output N·s of remaining current repetition, actual full executed J_F minus already measured prefix. Continuation commits declared K3 suffix with unchanged native accept/reject/fallback; completed suffix returns to B. No future truth, P base or next-repetition cost. Rolling re-selection and committed labels are analyzed separately. K3 knots are spatial points inside one native request, not three independent control steps.','',
 'First collection: three physical parents, four anchors each, six distinct coherent candidates each; duplicate initial/normal states leave nine distinct 55D causal state groups. Parent and branches stay together in train/dev; nominal 58D causal states and near duplicate dev states are excluded from fitting. Adjacent states and new RNG seeds are not new Humans. See `DATASET_AUDIT.json`, weight `TRAINING.json` and `DATASET.npz`. G has only two independent training anchor states and three development anchors after exclusions; coverage is weak.','',
 'One substantive development round, then an independent initialization on exactly the same train/dev data. Both dev-selected linear Q; independent 2×128 MLP and three-head 2×128 G fits were performed, but deterministic linear refitting is not a distinct learned Q. Model selection never uses final test outcomes. Q dev RMSE 8.524 N·s; regret 0 on three informative groups (five raw groups include two zero-spread duplicates). Deployment NumPy/GPU parity passes.','',
 '## Scientific closed-loop results','',
 'Eight paired runs per method across two versions: four nominal same-trajectory/search-seed replications plus four genuinely different legal deviation prefixes. Same physical initial state, commissioned belief, task, R2 evaluator, authority, six-candidate budget and matching group seed. Complete VALID tasks alone rank J_F.','',
 '| Method | VALID | J_F mean (N·s) | Moment integral mean (N·m·s) | Duration (s) | Paired J_F reduction | Worst coordinator (ms) |',
 '|---|---:|---:|---:|---:|---:|---:|']
 for m,r in methods.items():text.append(f"| {m} | {r['valid']}/8 | {fmt(r['J_F_mean'])} | {fmt(r['moment_mean'])} | {fmt(r['duration_mean'])} | {fmt(r['paired_J_F_improvement_pct'])}% | {fmt(r['coordinator_max_ms'],1)} |")
 text += ['', 'Per-version results remain separate in `ANALYSIS_v1.json`, `ANALYSIS_v1_repeat.json` and the two CSVs; `COMBINED_MATRIX.json` is a descriptive pooled summary, not a significance test. M0 and interface/non-learning search are reported separately. Moment rises under Q despite force reduction; this is a force–moment tradeoff, not an unqualified coordination improvement.','',
 f"M2 nominal mean paired reduction {subgroups['M2']['nominal']['paired_improvement_mean_pct']:.3f}%, legal deviation {subgroups['M2']['deviation']['paired_improvement_mean_pct']:.3f}%; M4 {subgroups['M4']['nominal']['paired_improvement_mean_pct']:.3f}% / {subgroups['M4']['deviation']['paired_improvement_mean_pct']:.3f}%. See SUBGROUP_SUMMARY.json for all methods and paired ranges.",'',
 'Phase duration equality does not imply equal executed common progress. Each pair records OUT/HOLD/RETURN, peak force/moment, tracking, clearance, plan changes/accept/fallback and interpolated reference/physical common and differential wave RMS/peaks. No claim of arbitrary Human, noise or hardware generalization.','',
 '## Timing and actual host-clock execution','',
 'Source-grounded interior bridge is 40 ms; evaluator activation condition is independently 55 ms, generic command expiration 100 ms. Current public hook starts after native request at boundary, before snapshot/submit; no early-precompute authority has been established. Full path includes context, proposal generation, Q/G, native validation, submission/snapshot, native worker, current-model revalidation, receipt and activation. Baseline already consumes the margin; no invented 100 ms budget or retroactive action writes.','',
 'Scientific simulations freeze physical epochs during host computation and measure quality only. Actual original WallPhysicsSession was run for all five methods and repeated for M0/M2 after a mode-metadata logger repair. Seven actual runs all invalid: original B stale-at-apply and interface methods stale-command age. Failed/truncated J_F values are unranked. New M2 decision in the corrected retest is explicitly late-discarded to carry; unchanged native safety owns final fallback/abort.','',
 f"M2 mean coordinator components (ms): context {components['M2']['components_mean_ms']['context_s']:.3f}, generation {components['M2']['components_mean_ms']['generation_s']:.3f}, native validation/S {components['M2']['components_mean_ms']['validation_and_S_s']:.3f}, Q {components['M2']['components_mean_ms']['Q_inference_s']:.3f}, submission {components['M2']['components_mean_ms']['submission_s']:.3f}, total {components['M2']['components_mean_ms']['end_to_end_s']:.3f}. Repeated original candidate validation dominates the tiny Q inference. LATENCY_COMPONENT_SUMMARY.json records all methods, late fractions and Q/G invocation counters.",'',
 'First five physical runs also failed post-execution metadata consistency because an old qualification helper hard-coded SCIENTIFIC_SIMULATION. Only that log constant was corrected to the actual summary mode. Original FAILED results and original metadata are retained; raw trace/archive hashes unchanged; offline rescore adds zero physical attempts. Two fresh actual retests have consistent mode and still fail physics/timing. `WALL_ANALYSIS_v1.json`, `WALL_RESCORE_v1.json`, `MODE_METADATA_REPAIR.json` and raw artifacts contain the distinction.','',
 f"Pilot: {pilot['status']}; {pilot['reason']}. No hardware runs.",'',
 '## Representative committed-suffix attribution','',
 'An already-exposed successful M2 path is recreated by legal native action replay, with exact causal-context and every final trace field equality required. At OUT2 and RETURN1, preserved ordinary six plus frozen G three are committed in CPU branches, not relabeled from the rolling controller. Diagnostic outcomes are never training data or independent final-test evidence.','']
 for r in diagnostic['rows']:text.append(f"- {r['phase']} {r['index']}: valid {r['valid_count']}/9; Q top1 regret {fmt(r['Q_top1_regret'])} N·s; S regret {fmt(r['S_top1_regret'])}; G-best gain over ordinary {fmt(r['G_best_improvement_over_ordinary'])}; chosen committed minus rolling remaining {fmt(r['continuation_difference_N_s'])} N·s.")
 text += ['', '## Failures, resources and recovery','',
 'All failed imports, branch exceptions, invalid full/short tasks and retries count. Advisory context geometry rejection was caught without relaxing native B; exact zero regression passed afterward. One physically complete development branch failed original science version/activation criteria and is excluded from success labels. Unsafe short outcomes are never cheap positive labels. G-negative findings did not stop Q/nonlearning/independent/timing work.','',
 f"Resources: {resources['samples']} 45-second samples, WSL MemAvailable min {resources['min_WSL_available_GiB']:.2f} GiB, Windows commit headroom min {resources['min_windows_commit_GiB']:.2f} GiB, owned PSS max {resources['max_owned_PSS_GiB']:.2f} GiB; OOM delta {resources['oom_delta']}; swap {resources['swap_start_MiB']:.1f}→{resources['swap_end_MiB']:.1f} MiB. Stable nonzero swap/low Windows available did not trigger an artificial global stop. GPU fitting runs separately without physics and retains peak RSS/CUDA allocation in each TRAINING.json. One physics owner; children joined; no unknown process killed, cache drop, WSL restart or RAM/swap changes.",'',
 f"Compute: {len(starts)} counted attempts; actual added simulation {compute['totals_lower_bound']['actual_new_simulation_s']:.3f} s, native steps {compute['totals_lower_bound']['actual_new_native_steps']}; main model API lower bound {compute['totals_lower_bound']['main_model_calls']}; separate native worker calls lower bound {compute['totals_lower_bound']['native_worker_model_calls']}. Main and native-worker counts are not added because same-process calls may overlap. Unknown calls remain explicitly listed, including original failed geometry branch. Parent-inclusive wall and child wall are not double counted. Append-only original ledger plus corrections retained.",'',
 'Compressed runtime logs are losslessly verified before removal of their generated uncompressed duplicates; no historical or unique evidence deleted. FINAL_MANIFEST.json hashes all retained essential source, weights, inputs, results, raw compressed logs, traces and code histories by streaming reads. Checkpoint/resume uses completed unique IDs and original deadline/cap; final closed state does not auto-start another project.','',
 '## One next recommendation','',status['next_single_recommendation'], '', 'Completed required boundary/zero/data/model/matrix work plus independent initialization/new paired groups, actual latency and causal attribution. Early close is because meaningful authorized work is complete; unmet online qualification is preserved as a negative result. STOP.']
 (STUDY/'FINAL_REPORT.md').write_text('\n'.join(text)+'\n')
 save(STUDY/'CHECKPOINT.json',dict(phase='COMPLETE_STOPPED',unix=time.time(),attempts=len(starts),open_attempts=[],pending_tasks=[],deadline_unix=START+9*3600,report=str(STUDY/'FINAL_REPORT.md'),manifest_sha256=sha(STUDY/'FINAL_MANIFEST.json'),next='none; stopped; a new project requires a new user request'))
 (STUDY/'PROGRESS.md').write_text(f'COMPLETE_STOPPED\n{elapsed/3600:.3f} h, {len(starts)}/240 attempts, {total/2**30:.3f} GiB.\nReport FINAL_REPORT.md. No pending physics tasks.\n')
 (STUDY/'RESUME.md').write_text('COMPLETE_STOPPED. This package is finished; do not restart the queue automatically.\nRead FINAL_REPORT.md, FINAL_STATUS.json, CHECKPOINT.json, FINAL_MANIFEST.json, RECOVERY_AUDIT.json.\nFor read-only recovery verify manifest hashes; original start clock/deadline/cap remain in RUN_PLAN.json. Unique completed task IDs are never replayed. A future independent experiment needs a new user request and directory.\n')
 print(json.dumps(status))
if __name__=='__main__':main()
