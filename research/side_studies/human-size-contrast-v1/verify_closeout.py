from pathlib import Path
import json,hashlib,ast,shutil
from datetime import datetime,timezone
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/human-size-contrast-v1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(W/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
now=datetime.now(timezone.utc)
state=json.loads((W/'STATE.json').read_text());state['finished_preparation_utc']=now.isoformat();state['frozen_contract_to_closeout_elapsed_s']=(now-datetime.fromisoformat(state['started_utc'])).total_seconds();state['harness_status']='PATH_HASH_SCORER_IMPORTS_VALIDATED; DYNAMIC_EXECUTION_AND_POSTPROCESSING_NOT_TESTED'
save('STATE.json',state)
resources=json.loads((W/'RESOURCE_OVERLAP_LOG.json').read_text())
resources['static_screen_overlap_bound_utc']={'start':datetime.fromtimestamp((W/'ENVIRONMENT.json').stat().st_mtime,timezone.utc).isoformat(),'end_upper_bound':now.isoformat(),'precision':'Import artifact mtime to closeout; conservative upper bound, not measured exact overlap duration'}
resources['performance_interference']='No SAC process/config changes. Static work used CPU concurrently for part of qualification; throughput/latency effect not quantified.'
save('RESOURCE_OVERLAP_LOG.json',resources)
report=W/'REPORT.md';report.write_text(report.read_text()+'\nRunner `human_qualification.py --check` passed hash verification for all 140 snapshot files, isolated imports and frozen physical/mode scorer imports. `--execute` is gated by an absent RESOURCE_RELEASE.json containing verified aggregate peak evidence, fresh resource samples, individual prior eligibility and total-time/budget caps; no release was fabricated. Resource callback raises a side-only stop exception and uses only SIDE_STOP in this directory. Dynamic runner/serialization/postprocessing are untested because no rollout is authorized by present resources.\n\nEffective reference pacing in inherited options is velocity fraction .5 and acceleration fraction .25; online reference defaults from the prior report are not substituted. Lower-ROM geometry screen used the same synthetic physical parameterization and was necessary geometry only. No smaller-goal result was relabeled as the primary task. Static CPU overlap may affect SAC host timing; its impact is unquantified.\n')
protocol='''# Resume / execution plan

This preparation is checkpointed, not an automatic campaign launcher. Current dynamics must remain off.

1. Read CONTRACT, STATE, resource evidence and feasibility audit. Preserve 9 registered rows; anatomy-prior-blocked rows remain NOT_RUN. Lower ROM does not fix 2m's full-shank prior.
2. Before any future dynamic run obtain trustworthy aggregate parent+planner peak memory evidence for this frozen runtime, current Windows/WSL headroom and current SAC stage. Formal SAC throughput/latency measurement blocks side simulation. Never create a RESOURCE_RELEASE file from the unverified planning estimate alone. Recheck total six-hour limit; no automatic budget reset.
3. Run check-only with the read-only adaptive-online-v1 environment, PYTHONDONTWRITEBYTECODE=1, OMP/OPENBLAS/MKL/NUMEXPR=1 and CUDA_VISIBLE_DEVICES empty. No dependency installs. Use one fresh owner process and one requested arm per case. No cross-arm checkpoint/data transfer. No shared STOP or changes to SAC.
4. Future dynamic invocation: `SIZE_STUDY_ARM=<registered-arm> ... python human_qualification.py --execute <case_key>`. Current release absent, so this must refuse. Parent and planner RSS, Windows/WSL availability, swap and overlap must be sampled through finalization; stop only side owner via runtime_capture stop_check if reserve deteriorates. Never kill SAC. Failed attempts consume a primary/diagnostic slot and remain visible.
5. Postprocess every actual attempt with the frozen evaluate_execution_mode/summarize_phase_b path. Use own temporary directory to expose compressed summary/runtime artifacts and trace.npz, registered absolute case path/hash, original PHASE_B_MATRIX scoring and SCIENTIFIC_SIMULATION launch record. Export physical_task.status, scientific_mode_validity.status, overall result and wall_characterization independently. Do not count commissioning failures as fabricated task outcomes. Keep setup/commissioning exception reasons.
6. Retain key NPZ traces and handoff beliefs; derive task metrics only from actual TASK intervals. Reconstruct planner worker numerical payload hashes from learning_transitions adaptive_state; link mechanics belief sequences to those hashes and actual execution wrapper hashes, with geometry signatures separate. Export initial/final beta/geometry/residual, update rejection reasons, model residuals and q/dq/ddq/torque/time ranges. Prediction residuals from training samples do not prove forecast gain.
7. Update the nine-row COMPARISON with actual verdicts and nullable absent metrics. B-A/C-B only within height and physically comparable completed trajectories; no cross-height absolute J_F or failed-short/full ranking. No beta-version/L2-only learning claim. No geometric/dynamic attribution without separately authorized ablation.
8. Do not launch more than 9 primary + 3 targeted diagnostics, do not exceed 2 harness/logging/serialization fixes with meaningful regression checks. Any parameterization/evaluation change requires another version. Produce MANIFEST and compact closeout; no main repository or Git writes.

Only import/hash/scorer/guard checks have run. Resource telemetry during dynamics, runtime behavior and complete metric extraction remain untested. This plan records those limits instead of claiming a completed campaign.
'''
(W/'EXECUTION_PLAN.md').write_text(protocol)
shutil.copy2(__file__,W/'verify_closeout.py')
prov=json.loads((W/'SOURCE_PROVENANCE.json').read_text());assert len(prov['files'])==140
assert all(sha(W/'snapshot'/p)==r['sha256'] for p,r in prov['files'].items())
required=['CONTRACT.json','HUMAN_PARAMETER_AND_FEASIBILITY_AUDIT.md','HUMAN_PARAMETER_AND_FEASIBILITY_AUDIT.json','MODEL_CONSUMPTION_EVIDENCE.json','COMPARISON.csv','COMPARISON.json','RESOURCE_OVERLAP_LOG.json','STATE.json','REPORT.md']
assert all((W/p).is_file() for p in required)
for p in W.glob('*.py'):ast.parse(p.read_text())
assert not (W/'runs').exists() and not (W/'RESOURCE_RELEASE.json').exists()
comparison=json.loads((W/'COMPARISON.json').read_text());assert len(comparison['runs'])==9 and all(r['task_status']=='NOT_RUN' for r in comparison['runs'])
assert state['primary_runs_executed']==state['diagnostic_runs_executed']==0
save('CLOSEOUT_VERIFICATION.json',{'status':'PASS_PREPARATION_ONLY','required_outputs_present':True,'source_hashes_verified':140,'registered_rows':9,'time_integration_steps':0,'dynamic_runs':0,'harness_check_only':json.loads((W/'HARNESS_VALIDATION.json').read_text())['status'],'dynamic_release_absent':True,'checks_utc':now.isoformat(),'scientific_conclusions':'INCONCLUSIVE_NOT_RUN; 2.00m unsupported anatomy prior'})
manifest={'created_utc':now.isoformat(),'contract_sha256':sha(W/'CONTRACT.json'),'retention':'KEEP_RAW minimal source and preparation evidence; no trajectories/checkpoints/training data','files':[{'path':str(p.relative_to(W)),'bytes':p.stat().st_size,'sha256':sha(p),'policy':'KEEP_RAW'} for p in sorted(W.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']}
save('MANIFEST.json',manifest)
assert all(sha(W/r['path'])==r['sha256'] for r in manifest['files'])
print(json.dumps({'status':state['status'],'source_files':140,'retained_files':len(manifest['files']),'retained_bytes':sum(r['bytes'] for r in manifest['files']),'contract_to_closeout_minutes':state['frozen_contract_to_closeout_elapsed_s']/60,'dynamic':0,'prior_issue':'2.00m shank .466m exceeds .460m','report':str(report)}))
