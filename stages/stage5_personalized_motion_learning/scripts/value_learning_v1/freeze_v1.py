"""Freeze the requested research contract and verify historical provenance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, time, platform
R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/value_learning_research_v1'
O=S/'docs/coordination_pacing_exploration_v1'
RAW=S/'results/value_learning_research_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()
def save(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n')
def git(*args): return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
now=datetime.now(timezone.utc).isoformat()
contract={
 'schema':'learning_research_v1_contract','status':'FROZEN_BEFORE_IMPLEMENTATION',
 'campaign_start_utc':'2026-09-30T14:07:00+00:00','hard_deadline_utc':'2026-09-30T23:07:00+00:00',
 'target_wall_hours':[5,8],'hard_max_hours':9,'source_branch':'codex/coordination-pacing-exploration-v1',
 'source_head':'8654cf0b6704fdecce3b4ccf1f00eb599aa5248c','branch':'codex/value-learning-research-v1',
 'primary_objective':'Minimize completed-repetition J_F_task = integral norm(F_cuff_measured(t)) dt, in N s; task and scientific validity are hard gates.',
 'accounting':'Frozen baseline_accounting_v2.task_wrench_cost: TASK-only left endpoint measured physical cuff norm on verified 5 ms grid; includes OUTBOUND/HOLD/RETURN; excludes pre-task bootstrap/boundary, which remain separately logged.',
 'separate_metrics':['mean_force_n','rms_force_n','peak_force_n','moment_integral_nm_s','moment_peak_nm','duration_s','minimum_clearance_m','dq_rms_rad_s','ddq_rms_rad_s2','J_F_session_n_s'],
 'action':'Actual next hip/knee target q, executed by original model-based planner/scheduler/feedback/safety stack. Research proposals support replayed executed targets, smooth path descriptors and diverse local alternatives, not just legacy lattice.',
 'value':'Q(x,a | continuation context) estimates cumulative measured interaction cost from decision through repetition termination under recorded continuation policy. Lower is better; no Q* or global optimum claim.',
 'continuation_context':'Frozen phase path descriptor, current phase waypoint index, remaining targets/schedule durations, horizon/return rule, model/value version and previous executed action. Policy-improvement rows carry active model digest. Identical (x,a) with different continuation are never pooled without these fields.',
 'ranking':'Separate scalar cost-to-go ranking among hard-screened candidates. Raw N s never added to dimensionless legacy cost. Legacy score retained as comparator/tie-breaker/fallback.',
 'unchanged':['controller mathematics','Human/plant dynamics','safety/clearance/ROM/velocity/acceleration/mechanics limits','scientific scheduler','original task completion set','5 ms sensor grid','raw scorer'],
 'truth_firewall':{'allowed':['estimated Human q/dq','receipt-owned reference q/dq','task geometry/progress','deployable Human model/belief and version','scheduler/proposal memory'],
  'evaluation_only':['native Human q/dq','actual future forces','hidden physical parameters','best-known simulated future'],
  'rule':'No evaluation-only quantity enters candidate proposals, features, safety screens, or online ranking. Future reference control points are a causal policy plan, never future observations.'},
 'splits':{'train':['low_ordinary_early','low_ordinary_late','balanced_middle','hip_ordinary','sync_120'],
  'validation':['knee_ordinary','balanced_high'],'test':['elevated_start','variable_start_120'],
  'unit':'physical condition/session; both low_ordinary adaptation states remain together',
  'limitation':'All source conditions have historical exploration outcomes. Test means held out from fitting/tuning this value model, not previously unseen science. Test reference-search rollouts never enter prior training.'},
 'expressivity':{'sources':['validation_sync_120_000_matched','validation_variable_start_120_000_matched','coarse_balanced_high_017_matched','refinement_hip_ordinary_007_matched'],
  'requirements':'All four beneficial VALID sources replay through exact future research target-screen-execution interface at identical starting state with no weakened safety.',
  'tolerances':{'target_max_error_rad':1e-10,'realized_q_max_error_rad':1e-8,'force_max_error_n':1e-6,'J_F_abs_error_n_s':1e-6},
  'promotion':'Value training forbidden until all four sources are VALID and meet all replay tolerances. If interface fails expand proposals only, preserve rejected runs.'},
 'reference_search':{'conditions':['sync_120','variable_start_120','balanced_high','hip_ordinary','low_ordinary_early','low_ordinary_late'],
  'levels':{'L0':'baseline and known observed patterns','L1':'signed lead amplitude, interior catch-up peak, categorical H1/H2/H3/H4','L2':'three endpoint-zero early/middle/late smooth offset coefficients, horizon','L3':'five endpoint-zero smooth normalized-progress coordination control points, horizon'},
  'L4':'Only preregistered development extension if L3 remains clearly improving; otherwise omitted.',
  'method':'CEM: two deterministic restarts per condition/level, three generations, eight candidates per generation, three elites, 25% fresh uniform exploration, variance floor. Warm-start baseline, known hip-leading and legal diverse descriptors. Real frozen simulation every evaluated proposal; infeasible paths not safety-repaired.',
  'budget_evaluations':864,'seed_base':20260930,'timing':'1.3 x original registered baseline segment durations (rounded to 5 ms); unchanged fixed-duration checks. Actual phase timing residual is measured; only equal-count, <=25ms phase residual comparisons are called timing-isolated.',
  'adaptive_resource_rule':'Stop launching search units after 4.75 campaign hours, preserve completed generations and all proposals, reserve remaining budget for branch data/models/timing/pilot/analysis. Hard max 9h. Smaller completed budget is disclosed, never claimed as 864 completed.',
  'convergence':'Curves per condition/level/restart/evaluation; no global optimality. Optimizer plateau is descriptive last-generation improvement and restart spread.'},
 'branch_data':{'conditions':'all nine source rows, separate splits','states':['OUTBOUND index 0','OUTBOUND index 2','RETURN index 0'],
  'actions':'baseline, signed normalized offsets -0.04,-0.02,+0.02,+0.04 with opposite hip/knee displacement; screened unmodified.',
  'continuation':'matched baseline path, one action changed only. Deterministic prefix re-execution from immutable source checkpoint reproduces exact branch state; verify state/model/reference/prefix equality. Failure/truncation kept outside cost regression.',
  'budget_evaluations':135},
 'models':{'simple':'scaled ridge regression with regularization chosen on validation conditions','MLP':'small two-hidden-layer network, 32 units each; scaled input and return; CPU mandatory, GPU optional if useful; deterministic seeds 20260930/31/32',
  'ablation':['SHORT next 1.5 s measured cost','FULL remaining repetition cost'],
  'offline_metrics':['MAE','RMSE','within-branch-state Spearman','top1 accuracy with numerical ties','top-k capture','selected-action candidate regret','comparable best-known reference regret'],
  'gate':'Dataset return sum/split/provenance validation PASS; best validation full model has positive within-state ranking correlation and lower mean action regret than legacy comparator on material branch groups; timing study has plausible architecture path.'},
 'pilot':{'development_conditions':['sync_120'],'modes':['SCRATCH no cross-condition value initialization','PRIOR trained only other training conditions, excludes sync_120'],
  'max_repetitions_per_mode':8,'update':'versioned immutable model; prepare/validate new candidate between repetitions, switch only at settled boundary; if update not ready use previous validated model; measure update time; no in-place task update',
  'exploration':'bounded phase-coherent proposals; no random opposite alternation at each waypoint; record candidate diversity',
  'five_repetitions':'inspection timescale only; never forced freeze',
  'convergence':'Inspect plateau, pattern stability, Q error/rank changes, safe alternate probes, feasibility and latency jointly. Freeze provisional numerical criteria after development distributions, apply prospectively in later experiment.'},
 'benefit_capture':'KNOWN-BENEFIT CAPTURE = (matched baseline J - learned J)/(matched baseline J - best-known J), where same starting state/continuation/schedule comparison is supported. Noncomparable or zero/negative denominator -> unavailable, with reason. Beating reference requires independent replay confirmation.',
 'latency':'Measure search wall time; model update; inference; proposals; feasibility/scheduling; full observation-ready to validated-reference latency, median/p95/p99/max and candidate-count scaling. CPU ridge/MLP required. GPU with transfer/batch/cold overhead only if available. Derive budget from actual replan/buffer/horizon, do not invent 5ms.',
 'gates':['source hashes and native baseline reproduction','expressivity','validated dataset','offline meaningful ranking','plausible full-decision timing path','small pilot'],
 'repair_cycles_max':6,
 'stop_conditions':['baseline cannot reproduce','safety weakening required','deployable hidden truth required','unexpected controller mathematics/Human dynamics change required','irreparable provenance','systemic infrastructure failures after six bounded repairs'],
 'terminal_states':['VALUE_LEARNING_RESEARCH_V1_COMPLETE','VALUE_LEARNING_RESEARCH_V1_PARTIAL','VALUE_LEARNING_RESEARCH_V1_BLOCKED'],
 'hardware_boundary':'RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS; no hardware/realtime qualification; no final 30-repetition learning experiment',
 'freeze_utc':now}
D.mkdir(parents=True,exist_ok=True); RAW.mkdir(parents=True,exist_ok=True)
if (D/'LEARNING_RESEARCH_V1_CONTRACT.json').exists(): raise RuntimeError('contract already frozen')
save(D/'LEARNING_RESEARCH_V1_CONTRACT.json',contract)
md='# Learning Research v1 — frozen contract\n\n'
for k,v in contract.items(): md+=f'## {k}\n\n'+(v if isinstance(v,str) else '```json\n'+json.dumps(v,indent=2)+'\n```')+'\n\n'
(D/'LEARNING_RESEARCH_V1_CONTRACT.md').write_text(md)
save(D/'STATE.json',{'status':'RUNNING','phase':'SOURCE_FREEZE','start_utc':contract['campaign_start_utc'],'hard_deadline_utc':contract['hard_deadline_utc'],'source_head':contract['source_head'],'branch':git('branch','--show-current'),'repair_cycles_used':0,'next_action':'verify raw provenance; native baseline and expressivity replay'})
files={str(p.relative_to(R)):sha(p) for folder in ['stages/stage3_full3d/src','stages/stage4_adaptive_control/src','stages/stage5_personalized_motion_learning/src'] for p in (R/folder).rglob('*.py')}
docs={str(p.relative_to(R)):sha(p) for folder in ['coordination_pacing_exploration_v1','zero_value_30rep_baseline_v3','scientific_execution_architecture_v1','repetition_boundary_v1'] for p in (S/'docs'/folder).rglob('*') if p.is_file()}
save(D/'SOURCE_FINGERPRINTS.json',{'source_head':contract['source_head'],'source_branch':contract['source_branch'],'startup_git_status':'','remote_source_head':git('ls-remote','origin','refs/heads/codex/coordination-pacing-exploration-v1'),'production_files_sha256':files,'frozen_evidence_sha256':docs,'environment':platform.platform(),'contract_sha256':sha(D/'LEARNING_RESEARCH_V1_CONTRACT.json')})
start=time.monotonic(); failures=[]; count=0; total=0
manifest=json.loads((O/'RAW_DATA_MANIFEST.json').read_text())
for i,entry in enumerate(manifest['rollouts']):
 out=S/'results/coordination_pacing_exploration_v1/runs'/entry['run_id']
 result=out/'rollout_result.json'
 if sha(result)!=entry['result_sha256']: failures.append(str(result))
 row=json.loads(result.read_text())
 for name,digest in row.get('raw_files_sha256',{}).items():
  p=out/name; count+=1; total+=p.stat().st_size
  if sha(p)!=digest: failures.append(str(p))
 if i%50==0: print(json.dumps({'hash_progress':i,'files':count,'bytes':total}),flush=True)
cpbase=S/'results/zero_value_30rep_baseline_v3/formal_session_01'
for name,digest in json.loads((S/'docs/zero_value_30rep_baseline_v3/RAW_DATA_MANIFEST_V3.json').read_text()).items():
 p=cpbase/name; count+=1; total+=p.stat().st_size
 if sha(p)!=digest: failures.append(str(p))
save(D/'SOURCE_RAW_VERIFICATION.json',{'status':'PASS' if not failures else 'FAIL','exploration_rollouts':len(manifest['rollouts']),'raw_files_verified':count,'bytes_verified':total,'failures':failures,'wall_s':time.monotonic()-start,'timestamp_utc':datetime.now(timezone.utc).isoformat()})
print(json.dumps({'verification_complete':not failures,'files':count,'wall_s':time.monotonic()-start}),flush=True)
if failures: raise RuntimeError('source hashes invalid')
