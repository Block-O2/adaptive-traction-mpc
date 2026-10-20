from research_common import *
import subprocess,shutil,datetime
from offline_score import NeuralQ
def git_state(p):
 def run(*a):
  r=subprocess.run(['git','-C',str(p),*a],capture_output=True,text=True)
  return {'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
 return {'branch':run('branch','--show-current'),'head':run('rev-parse','HEAD'),'status':run('status','--porcelain=v1','--untracked-files=all'),'staged':run('diff','--cached','--binary'),'diff':run('diff','--binary'),'index_sha256':sha(p/'.git/index') if (p/'.git/index').is_file() else None}
def main():
 checks=[]
 def check(name,passed,detail=None):
  checks.append({'check':name,'passed':bool(passed),'detail':detail})
  if not passed:raise AssertionError(name)
 required=['REPORT.md','MOTION_BURDEN_AUDIT.md','MOTION_BURDEN_AUDIT.json','HISTORICAL_MLP_RECOVERY.md','DATASET_AUDIT.md','DATASET_AUDIT.json','TRAINING_MANIFEST.json','NEURAL_Q_EVALUATION.md','NEURAL_Q_EVALUATION.json','MODEL_AND_FEATURE_CONTRACT.json']
 for name in required:check('required:'+name,(OUT/name).is_file() and (OUT/name).stat().st_size>0)
 before=load(OUT/'PRESERVATION_BEFORE.json');git_after={p:git_state(Path(p)) for p in before['git']}
 check('git_branch_head_status_staged_diff_index_unchanged',git_after==before['git']);save('GIT_AFTER.json',git_after)
 changed=[]
 for f in before['files']:
  p=Path(f['path'])
  if not p.is_file() or p.stat().st_size!=f['size'] or sha(p)!=f['sha256']:changed.append(str(p))
 check('4461_historical_protected_files_unchanged',not changed,{'checked':len(before['files']),'changed':changed})
 check('frozen_Q_identity',sha(FROZEN/'weights.npz')=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9')
 branch=load(OUT/'BRANCH_LABELS.json')
 for f in branch['all_sources']:check('source_immutable:'+Path(f['path']).name,sha(f['path'])==f['sha256'])
 manifest=load(OUT/'TRAINING_MANIFEST.json');contract=load(OUT/'MODEL_AND_FEATURE_CONTRACT.json');check('chosen_model_hash',sha(contract['model'])==contract['sha256']);check('dataset_hash',sha(OUT/'NEURAL_DATASET.npz')==manifest['dataset_sha256'])
 model=NeuralQ(contract['model'])
 with np.load(OUT/'NEURAL_DATASET.npz') as z:x=z['x'];y=z['y'];splits=z['split'];groups=z['snapshot'];ids=z['source_ids']
 pred=model.score(x);check('finite_all_source_predictions',np.isfinite(pred).all())
 # Frozen evaluation rows must match scorer output at the exact source row.
 lookup={str(k):i for i,k in enumerate(ids)};e=load(OUT/'NEURAL_Q_EVALUATION.json');err=[]
 for part in e['models']['C_neural_challenger'].values():
  for g in part['groups']:
   for r in g['candidate_rows']:err.append(abs(r['pred_cost_N_s']-float(pred[lookup[r['id']]])))
 check('standalone_scorer_matches_export',max(err)<1e-6,{'max_error_N_s':max(err)})
 for bad in [np.zeros((1,119)),np.full((1,120),np.nan),np.zeros(120)]:
  caught=False
  try:model.score(bad)
  except ValueError:caught=True
  check('scorer_invalid_shape_nonfinite_rejected',caught)
 check('empty_batch_shape',model.score(np.zeros((0,120))).shape==(0,))
 def causal(i):return np.round(x[i,:58],4).tobytes()
 for a,b in [('train','validation'),('train','test'),('validation','test')]:
  check('snapshot_disjoint:'+a+':'+b,not set(groups[splits==a])&set(groups[splits==b]));check('causal58_disjoint:'+a+':'+b,not {causal(i) for i in np.flatnonzero(splits==a)}&{causal(i) for i in np.flatnonzero(splits==b)})
 for r in branch['rows']:
  source=load(r['source_file']);check('remaining_label_closure:'+r['id'],abs(r['y']-(source['metric']['J_F']-source['child']['start_J_F']))<1e-6)
  check('branch_trace_immutable:'+r['id'],sha(r['labels']['trace'])==r['labels']['trace_sha256'])
 m=load(OUT/'MOTION_BURDEN_AUDIT.json');check('eight_pairs_sixteen_runs',len(m['pairs'])==8 and len(m['run_audit_files'])==16)
 for f in m['run_audit_files']:
  r=load(f);check('native_mapping:'+r['id'],r['quality']['mapping_max_error_rad']<1e-8 and r['quality']['mapping_max_error_rad_s']<1e-8)
  for p,h in r['sources'].items():check('motion_source_immutable:'+r['id']+':'+Path(p).name,sha(p)==h)
  check('three_phase_complete:'+r['id'],all(r['actual_human']['raw']['phases'][ph]['velocity_deg_s']['n']>0 for ph in ['OUTBOUND','HOLD','RETURN']))
  check('filter_exports_complete:'+r['id'],set(r['actual_human'])=={'raw','savgol_5','savgol_21'})
 check('regret_direct_comparison_negative_result',e['models']['C_neural_challenger']['test']['mean_selection_regret_N_s']>e['models']['A_frozen_linear']['test']['mean_selection_regret_N_s'])
 check('all_configs_no_host_G_P_training',manifest['host_runs']==manifest['new_physical_rollouts']==manifest['G_P_training']==0)
 # No uncontrolled companion study process; this verifier is the only current owned process.
 companions=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:a=(p/'cmdline').read_bytes().split(b'\0')
  except OSError:continue
  if len(a)>1 and b'python' in a[0] and (b'/m2_neural_q_motion_v1/' in a[1]):companions.append({'pid':int(p.name),'argv':[v.decode(errors='replace') for v in a if v]})
 check('no_task_companion_processes',not companions,companions)
 # Start bound includes the first read-only inspection at 15:11:12 UTC.
 start=datetime.datetime(2026,10,8,15,11,12,tzinfo=datetime.timezone.utc).timestamp();wall=time.time()-start
 check('original_turn_wall_time_under_2_5h',0<=wall<9000,wall)
 src=Path(__file__).parent
 (OUT/'code').mkdir(exist_ok=True)
 for p in src.glob('*.py'):shutil.copy2(p,OUT/'code'/p.name)
 shutil.copy2(src/'offline_score.py',OUT/'offline_score.py')
 check('contract_scorer_path_exists',(OUT/contract['scorer']).is_file())
 save('VALIDATION_CHECKS.json',{'status':'PASS','checks':checks})
 files=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['PACKAGE_VERIFICATION.json','FULL_PACKAGE_MANIFEST.json','PROCESS_EXIT_CONFIRMATION.json']]
 save('FULL_PACKAGE_MANIFEST.json',{'schema':'sha256_relative_path_v1','files':files,'exclusions':'manifest itself, verification receipt and post-exit receipt to avoid recursive hashes'})
 save('PACKAGE_VERIFICATION.json',{'status':'PASS','meaning':'artifact/source/protection validation only; not model efficacy or real-time qualification','required_outputs':required,'checks_file':'VALIDATION_CHECKS.json','checks_count':len(checks),'historical_files_checked':len(before['files']),'frozen_Q_sha256':sha(FROZEN/'weights.npz'),'selected_model_sha256':contract['sha256'],'package_manifest_sha256':sha(OUT/'FULL_PACKAGE_MANIFEST.json'),'git_unchanged':True,'new_physical_rollouts':0,'new_host_runs':0,'budget_wall_seconds_from_first_inspection':wall,'wall_cap_seconds':9000,'task_companion_processes':companions,'process_exit_confirmation':'verifier completes normally; external pgrep result saved separately after exit','closed_unix':time.time(),'scientific_terminal_status':'EXPLORATORY_TRAINED_OFFLINE_ADVANTAGE_NOT_DEMONSTRATED','clinical_human_realtime_qualification':'NOT_EVALUABLE','next_work_package_started':False})
 # Export only to the explicitly authorized Windows study directory.
 dst=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_neural_q_motion_v1')
 shutil.copytree(OUT,dst,dirs_exist_ok=True)
 print(json.dumps({'verification':'PASS','checks':len(checks),'historical_files_unchanged':len(before['files']),'wall_minutes':wall/60,'Windows_export':str(dst)}),flush=True)
if __name__=='__main__':main()
