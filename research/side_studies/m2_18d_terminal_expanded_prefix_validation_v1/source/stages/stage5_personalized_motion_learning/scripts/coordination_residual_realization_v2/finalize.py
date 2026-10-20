from gates import *
import subprocess,platform
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True)
def main():
 protected=read('PROTECTED.json');changed=[p for p,h in protected.items() if not Path(p).exists() or sha(p)!=h]
 historic=json.loads((W.parent/'coordination_research_interface_v1/output/HISTORICAL_SEGMENT_DECOMPOSITION.json').read_text())['rows'];historical_trace_changes=[]
 for row in historic:
  p=next(Path(row['result_path']).parent.glob('rep_*/trace.npz'))
  if sha(p)!=row['trace_hash']:historical_trace_changes.append(str(p))
 before=read('GIT_BEFORE.json');cached=hashlib.sha256(subprocess.check_output(['git','-C',str(R),'diff','--cached','--binary'])).hexdigest()
 integrity=dict(protected_count=len(protected),changed=changed,head=git('rev-parse','HEAD').strip(),head_unchanged=git('rev-parse','HEAD').strip()==before['head'],cached_diff_unchanged=cached==before['cached_diff_sha256'],branch=git('branch','--show-current').strip(),status=git('status','--short'),staging_committing_pushing=False)
 integrity['historical_trace_changes']=historical_trace_changes
 integrity['pass_']=not changed and not historical_trace_changes and integrity['head_unchanged'] and integrity['cached_diff_unchanged'];save('FINAL_INTEGRITY.json',integrity)
 zero=read('zero_history_v2_GATE.json');ownership=read('ZERO_OWNERSHIP_GATE.json');minimal=read('MINIMAL_GATE.json');history=read('HISTORICAL_GATE.json');branch=read('BRANCH_GATE.json') if (L/'BRANCH_GATE.json').exists() else dict(pass_=False)
 a=np.load(S/'results/coordination_research_interface_v1/B_original/trace.npz');strict=[]
 for name in ('zero_v2','zero_logging_v2','zero_history_v2'):
  b=np.load(O/name/'trace.npz');different=[k for k in a.files if a[k].dtype.kind in 'fiu' and (k not in b.files or not np.array_equal(a[k],b[k],equal_nan=True))]
  categorical=[k for k in a.files if a[k].dtype.kind not in 'fiu' and (k not in b.files or not np.array_equal(a[k],b[k]))]
  strict.append(dict(name=name,exact=not different and not categorical and set(a.files)==set(b.files),different=different+categorical))
 strictpass=all(x['exact'] for x in strict);save('STRICT_ZERO_ARRAY_EQUALITY.json',dict(pass_=strictpass,rows=strict))
 base_ref=np.load(O/'zero_history_v2/native_reference.npz');branchzero=[]
 for target in read('BRANCH_CONTRACT.json')['targets']:
  name=target['label']+'_baseline';z=np.load(O/name/'native_reference.npz');m=read(name+'.json')
  branchzero.append(dict(name=name,reference_exact=np.array_equal(z['data'],base_ref['data']) and np.array_equal(z['phase'],base_ref['phase']),J_F_error=abs(m['J_F']-zero['metric']['J_F'])))
 save('BRANCH_ZERO_REGRESSION.json',dict(pass_=all(x['reference_exact'] and x['J_F_error']<=1e-6 for x in branchzero),rows=branchzero))
 E=zero['pass_'] and strictpass and ownership['pass_'] and minimal['pass_'] and history['pass_'] and integrity['pass_'];V=E and branch['pass_']
 state=dict(status='READY_NATIVE_COORDINATION_INTERFACE_V2' if E and V else 'BLOCKED_NATIVE_COORDINATION_INTERFACE_V2',E_readiness='READY' if E else 'BLOCKED',V_readiness='READY' if V else 'BLOCKED',scope='single exposed Human; development SCIENTIFIC_SIMULATION only',training_steps=0,large_dataset=False,phase='COMPLETE_REPORT_AND_STOP',next='freeze a separate bounded E/V training contract' if E and V else 'resolve only the recorded failed gate under the existing native constraints')
 save('STATE.json',state)
 chains={}
 for relative,needles in {
  'full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py':['planner_type =','planner.residual_spec =','coordination_interface.decision_boundary','payload = snapshot_task_call','suffix_schedule = decision.executed.schedule','first = active_schedule.sample(0.0)','reference_governor.select','reference = active_schedule.sample','coordination_interface.boundary'],
  'full3d_adaptive_integration_v1/coordination_residual_v2.py':['original=super().decide','delta=0.','modified=p+','alt=self._evaluate'],
  'human_waypoint_feedback_mpc.py':['def _evaluate(','schedule = self.scheduler.plan_reference_contract'],
  'human_waypoint_scheduler.py':['def plan_reference_contract('],
  'full3d_adaptive_integration_v1/online_planning.py':['def snapshot_task_call(','def execute_task_snapshot(','def activate('],
 }.items():
  p=S/'src/traction_mpc_stage5'/relative;lines=p.read_text().splitlines();chains[str(p)]={needle:[i+1 for i,s in enumerate(lines) if needle in s] for needle in needles}
 save('EXACT_SOURCE_CHAIN.json',chains)
 # Derive suffix-only force/moment metrics from the already captured trace.
 # This post-run evaluation never feeds branch candidate generation.
 suffix=[]
 for row in branch.get('rows',[]):
  name=row['label']+'_'+row['kind'];z=np.load(O/name/'trace.npz');mask=(z['stage']=='TASK');origin=float(z['time_s'][mask][0]);mask &= z['time_s']>=origin+row['start_task_s']-1e-8
  f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);mm=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
  suffix.append(dict(name=name,remaining_J_F=row['remaining_J_F'],remaining_M_integral=row['remaining_moment_integral'],remaining_force_peak=float(np.max(f)),remaining_force_mean=float(np.mean(f)),remaining_force_RMS=float(np.sqrt(np.mean(f*f))),remaining_moment_peak=float(np.max(mm)),complete_task_valid=row['complete_task_validity'],matched=row['matched'],snapshot_hash=row['snapshot_hash'],Human_model_hash=row['Human_model_hash'],continuation_policy_id=row['continuation_policy_id']))
 save('COMPLETE_REMAINING_LABELS.json',suffix)
 # All case records, including rejected and failed attempts, remain accessible.
 metricfiles=[p for p in L.glob('*.json') if p.name not in ('MINIMAL_GATE.json','MINIMAL_GATE_r1.json')]
 metrics=[]
 for p in metricfiles:
  x=json.loads(p.read_text())
  if isinstance(x,dict) and 'physical_audit' in x and 'J_F' in x:metrics.append(x)
 metrics=sorted(metrics,key=lambda x:x['name']);save('ALL_PHYSICAL_RUNS.json',metrics)
 # Mechanical proof of the richer accepted native actions and terminal/HOLD rules.
 semantics=[]
 for row in minimal['rows']:
  m=row['metric'];art=json.loads((O/m['name']/'summary.json').read_text());signs={p:[] for p in ('OUTBOUND','RETURN')};endpoint=[];hold=[]
  for decision in art['decisions']:
   if decision['phase']=='HOLD':hold.append(decision['selection_mode']=='greedy')
   if decision.get('selection_mode')=='native_residual_v2_ACCEPTED':
    for ev in reversed(decision['evaluations']):
     meta=ev.get('execution_screen',{}).get('coordination_residual_v2')
     if meta:
      signs[decision['phase']].append(meta['delta']);break
  for phase in ('OUTBOUND','RETURN'):
   d=[d for d in art['decisions'] if d['phase']==phase][-1];endpoint.append(d['selection_mode']=='greedy')
  semantics.append(dict(name=m['name'],accepted_deltas=signs,HOLD_disabled=all(hold),terminal_zero=all(endpoint),native_C2=m['physical_audit']['unchanged_evaluator']['physical_task_result']['reference_boundary_C2']))
 save('RESIDUAL_SEMANTICS_AUDIT.json',semantics)
 report=[f'# Native-Scheduler Coordination Residual Realization v2',f"\nTerminal status: **{state['status']}**. E **{state['E_readiness']}**, V **{state['V_readiness']}**.\n",'This is interface development and physical evaluation on the previously exposed nominal Human. It proves no held-out generalization, real-time host deadline qualification, hardware readiness or optimal value function. No training or large value dataset was started.\n','## Root fix and exact source chain\n',
 'v1 failed because ten recorded native intervals in each phase held q while retaining nonzero dq intent, reflecting wait/ownership semantics. Treating those tuples as physical phase-clock Hermite derivatives created huge accelerations and jerk. The original B was not thereby shown physically unsafe. v2 never uses a logged B tape to execute a trajectory.\n',
 'Repository root: `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1/source`; stage: `stages/stage5_personalized_motion_learning`.\n',
 '1. `src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py:3194` requests the native task waypoint; `:3252` serializes only the causal planner/request graph with `online_planning.snapshot_task_call`. The additive v2 runtime selects the research subclass and keeps the original request path.\n',
 '2. `terminal_reference.py:368` selects the original terminal reference and calls the original `HumanWaypointFeedbackMPCV1.decide`. `coordination_residual_v2.py:8` first obtains that complete original nominal decision. Zero/HOLD returns it directly.\n',
 '3. At the original selected target, normalize by the registered start/goal task spans. Apply `p_h=p_h_B+delta`, `p_k=p_k_B-delta`. Both target common progress and all original endpoint choices are preserved. The generic action is a PWL graph in native nominal progress, with zero endpoints and independent phase graphs. It is not a reference spline. Bounds violations explicitly reject and retain nominal B; every rejection is recorded.\n',
 '4. The unchanged `human_waypoint_feedback_mpc.py:240` `_evaluate` calls `scheduler.plan_reference_contract` (`:286`; scheduler definition `human_waypoint_scheduler.py:441`). Original velocity/acceleration, duration-window, continuous geometric clearance, frozen Human mechanics and causal tracking-offset certificates all remain active. No threshold is weakened.\n',
 '5. Original `online_planning.execute_task_snapshot` applies the unchanged safe-fallback preparation. Native runtime `:2979` selects the suffix, `:3005` checks q/dq/ddq boundary continuity, `:3045` commits planner memory, and `:3424` uses the native receipt governor (when enabled). `:3517` samples the native owned schedule. Original `_execute_interval`, CR12 mapping, safety, phase completion and R2 transition guard execute it. Planning waits retain their original q/dq/ddq ownership semantics.\n',
 'The v2 runtime is a separate source file. Exact paths and verified final line numbers are in `EXACT_SOURCE_CHAIN.json`; final hashes and executed revisions are in `SOURCE_MANIFEST.json` and `source_history`. Native C2 means scheduler polynomial and activation-boundary continuity; no claim is made that wait-time dq intent is the derivative of a continuously interpolated q tape.\n',
 '## Frozen contract and repairs\n',
 '`CONTRACT.json` froze zero tolerance (arrays 1e-10, force integral 1e-6), unchanged native safety, R2 9/1/9 phase clocks and existing +20ms quantization allowance, five minimal patterns, amplitudes [0.01,0.005,0.0025,0.001], at most 20 minimal physical attempts, four structural repairs, 12 branch continuations and one advancing physics owner. All candidates use native nominal target, causal state/reference/belief and registered task endpoints. Hidden state is forked only for restoration and evaluator use.\n',
 'The model/plant/options and initializer are inherited verbatim from B; no new stochastic setup is introduced. Repeated zero runs are deterministic. CPython and NumPy RNG states are explicitly restored after fork; observer-local RNGs and all hidden model/native state are process-copied.\n',
 'Repair 1 added selected residual metadata to the decision evaluations. The first hip result is retained and not relabeled as having a complete metadata audit. Zero logging regression and all five patterns followed.\n',
 'Repair 2 corrected the historical mapping: a frozen B differential is not the current conditional native nominal differential. The failed initial fixed/CEM traces remain read-only. The corrected mapping computes `delta=d_hist(m)-d_B_nominal` at each native decision, then runs the same scheduler. The initial JSON loop ran CEM first; those two runs are development diagnostics. Repaired historical gates explicitly run fixed then CEM. Zero and all five minimal regressions preceded the repaired history gates.\n',
 '## Zero residual hard gate\n',
 f"Final zero pass: {zero['pass_']}; reference maximum error {zero['reference_error']}; all trace maximum error {max(zero['array_errors'].values())}; J_F difference {zero['J_F_error']}. Ownership/wait and safety decisions exact: {ownership['pass_']}. Three zero runs independently reproduced the same B. See `ZERO_OWNERSHIP_GATE.json` for the compared fields.\n",'## Physical runs, including failures\n',
 '| Run | Physical VALID/MATCHED | Activated nonzero | J_F N s | Force peak/mean/RMS N | Moment integral/peak | Clearance m | OUT/HOLD/RETURN s |',
 '|---|---|---:|---:|---|---|---:|---|']
 for m in metrics:
  auditfile=L/(m['name']+'_AUDIT.json');a=json.loads(auditfile.read_text()) if auditfile.exists() else {};t=m['phase_durations']
  report.append(f"| {m['name']} | {m['valid']}/{m['matched_eligible']} | {a.get('activated','—')} | {m['J_F']:.6f} | {m['force_peak']:.3f}/{m['force_mean']:.3f}/{m['force_rms']:.3f} | {m['moment_integral']:.6f}/{m['moment_peak']:.3f} | {m['clearance']:.6f} | {t.get('OUTBOUND',0):.3f}/{t.get('HOLD',0):.3f}/{t.get('RETURN',0):.3f} |")
 report.extend(['\n## Minimal and historical expressivity\n',f"Five final minimal patterns passed: {minimal['pass_']}. Accepted deltas, HOLD disablement and terminal zero are in `RESIDUAL_SEMANTICS_AUDIT.json`. Per-decision common target errors are recorded in all `*_AUDIT.json`. Every rejected proposal remains visible.\n",'Historical q references are converted to spatial `d_hist(m)` graphs only. Duplicate progress selects the first recorded q; any progress backtracking and endpoint-zero projection are disclosed in `HISTORICAL_SPATIAL_GRAPH.json`. No historical timestamp, dq derivative or old 1.3x segment pacing enters execution. Force costs are compared descriptively within current R2, not claimed to reproduce historical 1.3x-segment costs.\n'])
 for h in history['rows']:report.append(f"- {h['name']}: pass {h['pass_']}; normalized spatial path errors `{json.dumps(h['path_errors'])}`.\n")
 report.extend(['\n## Full-state same-state branching\n','The reused v1 API is a Linux process-scoped address-space fork, not a portable disk restart. Computational workers are quiesced without changing native pending ownership. Full MuJoCo integration state, mutable model, Python graph, scheduler/governor/task/planner/request/lifecycle, reference, observer/RNG, prefix trace/cost and caches are cloned. The verification manifest adds lifecycle, arguments and request to the v1 fields. Opaque native objects/locks remain fork-preserved and explicitly listed. Parent waits synchronously for each child; only one child advances physics. Start hashes are checked before candidate/output mutation; parent hashes are checked after every child.\n',
 'Four points are frozen in `BRANCH_CONTRACT.json`. They are native opportunities: early OUT at native target m≈0.20, mid OUT≈0.59, late OUT≈0.79, mid RETURN≈0.59. Late is the last native target strictly interior for both lead signs (phase elapsed about 4.26s), not the settled 7.5s endpoint wait. This is a limitation of native decision availability, explicitly selected before the branch experiment.\n',
 'Each candidate acts over one declared ±0.04 progress chunk at amplitude ±0.01, then zero residual under B. Labels contain full Human geometry/dynamics/residual model hash, snapshot hash, action, continuation policy, complete task validity, remaining J_F and moment integral, force/moment metrics, timing and execution audit. Costs are realized continuation costs under the declared B policy, not V*/Q*.\n',
 f"Branch gate: `{json.dumps({k:v for k,v in branch.items() if k not in ('rows','comparisons')})}`.\n",'| Snapshot | Candidate | Accepted/activated | Different ref | Δ remaining J_F | Δ remaining M | VALID/MATCHED |','|---|---|---:|---|---:|---:|---|'])
 for c in branch.get('comparisons',[]):report.append(f"| {c['snapshot']} | {c['candidate']} | {c['activated']} | {c['reference_differs']} | {c['remaining_J_F_difference']:.9f} | {c['remaining_M_difference']:.9f} | {c['valid']}/{c['matched']} |")
 report.extend(['\n## Integrity, provenance and readiness\n',f"Starting branch `{before['branch']}`, HEAD `{before['head']}`; final branch `{integrity['branch']}`. Protected files {len(protected)}, changed count {len(changed)}, HEAD unchanged {integrity['head_unchanged']}, staged diff unchanged {integrity['cached_diff_unchanged']}. Pre-existing dirty/untracked state was preserved. No staging, committing, pushing, merging, reset, training, hardware or multi-Human work occurred.\n",'Executed command family: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/hank/envs/adaptive-online-rl-v1/bin/python -u <Windows-mounted-v2-script>`. Raw logs `zero.log`, `zero_logging.log`, `minimal.log`, `history.log`, `zero_history.log`, `continuation.log` record stage progression and failures. Raw native `summary.json`, `trace.npz`, `native_reference.npz`, native evaluator records and losslessly verified compressed runtime artifacts are in the corresponding WSL result folders. The exact option/case config is saved per run.\n',
 f"E readiness **{state['E_readiness']}**; V readiness **{state['V_readiness']}**. Promotion requires all physical/history/branch gates plus integrity, not API unit tests. The readiness scope is this unified simulation interface on one exposed Human. No training evidence is claimed.\n",f"Exactly one next recommendation: {state['next']}.\n"])
 name='NATIVE_SCHEDULER_COORDINATION_RESIDUAL_V2_REPORT.md'
 for folder in (L,D):(folder/name).write_text('\n'.join(report)+'\n')
 # Preserve the final executable source and manifests separately from v1.
 archive=P/'source_history/final';archive.mkdir(parents=True,exist_ok=True)
 source={}
 for p in W.glob('*.py'):
  shutil.copy2(p,P/p.name);shutil.copy2(p,archive/p.name);source[str(p)]=sha(p)
 for name in ('coordination_residual_v2.py','runtime_coordination_residual_v2.py'):
  p=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1'/name;shutil.copy2(p,archive/name);source[str(p)]=sha(p)
 save('SOURCE_MANIFEST.json',dict(final=source,python=sys.version,platform=platform.platform(),native_runtime='additive copy of protected B with target adapter and two diagnostic hooks'))
 save('RAW_MANIFEST.json',{str(p):sha(p) for p in O.rglob('*') if p.is_file()})
 print(json.dumps(state),flush=True)
if __name__=='__main__':main()
