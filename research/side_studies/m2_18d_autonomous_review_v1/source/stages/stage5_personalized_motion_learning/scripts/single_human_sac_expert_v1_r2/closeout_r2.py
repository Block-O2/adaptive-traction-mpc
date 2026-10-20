"""R2 scientific closeout and exact pre-existing index preservation audit."""
from pathlib import Path
import sys,json,time,datetime,subprocess,hashlib,shutil,csv,importlib.util,gzip
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1/source');S=R/'stages/stage5_personalized_motion_learning';D1=S/'docs/single_human_sac_expert_v1';D=D1/'r2';P=S/'scripts/single_human_sac_expert_v1_r2';O=S/'results/single_human_sac_expert_v1_r2';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2/output')
def read(name,default=None):return json.loads((D/name).read_text()) if (D/name).exists() else default
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
 return h.hexdigest()
def write(p,value):p.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True).strip()
def csvfile(path,rows,fields):
 with path.open('w',newline='') as f:
  writer=csv.DictWriter(f,fields);writer.writeheader()
  for row in rows:writer.writerow({k:json.dumps(row.get(k)) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in fields})
def main():
 state=read('STATE.json');pre=json.loads((D1/'GIT_PREFLIGHT_R2.json').read_text());seeds=read('SAC_SEED_SUMMARY.json',dict(seeds=[],total_steps=0));formal=state.get('formal_training_started',False);total=seeds.get('total_steps',state.get('training_steps',0));comparators=read('SAC_COMPARATOR_TABLE.json',dict(status='NOT_REACHED',rows=[]));confirm=read('SAC_BEST_CONFIRMATION.json',{});evaluations=[json.loads(p.read_text()) for p in sorted(D.glob('EVALUATION_*.json'))];best={k:v['selected'] for k,v in confirm.items() if v['pass_']};throughput=read('SAC_THROUGHPUT.json',{});contract=read('SAC_EXPERT_V1_CONTRACT.json',{});resources=read('RESOURCE_SAMPLES_R2.json',[])
 original_entries=set(pre['index_entries'].splitlines());current_entries=set(git('ls-files','--stage').splitlines());protected=pre['worktree_hashes'].copy();original_fingerprints=read('SOURCE_FINGERPRINTS.json',{})
 for group in ('protected_files','historical_docs','dirty_source'):protected.update(original_fingerprints.get(group,{}))
 bad=[p for p,h in protected.items() if not (R/p).is_file() or sha(R/p)!=h];index_ok=original_entries.issubset(current_entries)
 integrity=dict(pass_=not bad and index_ok and git('rev-parse','HEAD')==pre['head'] and git('branch','--show-current')==pre['branch'],changed_preexisting_files=bad,preexisting_index_entries_preserved=index_ok,preexisting_index_entry_count=len(original_entries),HEAD_unchanged=git('rev-parse','HEAD')==pre['head'],branch=git('branch','--show-current'),no_commit=True,no_push=True,no_merge=True,no_reset=True,no_stash=True)
 write(D1/'FINAL_SOURCE_INTEGRITY_R2.json',integrity)
 waiting=state.get('status')=='SAC_READY_WAITING_FOR_RESOURCES' or any(s.get('stop_reason')=='RESOURCE_RISK' for s in seeds['seeds'])
 trained=bool(formal and seeds['seeds'] and seeds['seeds'][0]['completed_steps']>=300000 and seeds['seeds'][0].get('gradient_updates',0)>0 and not any(s.get('error') for s in seeds['seeds']) and evaluations and integrity['pass_'])
 terminal='QUALIFIED_AND_TRAINED' if trained else 'PARTIAL' if formal else 'QUALIFIED_WAITING_FOR_RESOURCES' if waiting and comparators['status']=='PASS' else 'BLOCKED'
 profile=read('SAC_RUNTIME_PROFILE.json',{});analyses={}
 if best:
  sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'))
  import closeout as old
  analyses={scope:old.analysis_of_policy(r) for scope,r in best.items()}
 strongest={scope:min((r for r in comparators['rows'] if r['valid'] and r['scope']==scope),key=lambda r:r['J_F'],default=None) for scope in ('NATIVE','MATCHED')}
 old_native=next((r for r in comparators['rows'] if r['name']=='old_nominal' and r['scope']=='NATIVE'),None);fixed_native=next((r for r in comparators['rows'] if r['name']=='fixed_hip_lead' and r['scope']=='NATIVE'),None);old_matched=next((r for r in comparators['rows'] if r['name']=='old_nominal' and r['scope']=='MATCHED'),None);fixed_matched=next((r for r in comparators['rows'] if r['name']=='fixed_hip_lead' and r['scope']=='MATCHED'),None)
 effects={}
 if old_native and fixed_native and old_matched and fixed_matched:
  effects=dict(native_improvement_percent=100*(old_native['J_F']-fixed_native['J_F'])/old_native['J_F'],matched_improvement_percent=100*(old_matched['J_F']-fixed_matched['J_F'])/old_matched['J_F'],matched_J_F_difference=old_matched['J_F']-fixed_matched['J_F'],matched_residual_duration_s=old_matched['duration_s']-fixed_matched['duration_s'],maximum_cost_from_that_extra_time_given_200N_limit=200*abs(old_matched['duration_s']-fixed_matched['duration_s']),native_fixed_force_peak_change_percent=100*(fixed_native['force_peak']/old_native['force_peak']-1),native_fixed_moment_peak_change_percent=100*(fixed_native['moment_peak']/old_native['moment_peak']-1),causal_scope='Native contrast contains timing; matched contrast still combines coordination and within-phase pacing. Residual 15ms total-time difference alone is bounded by 3 N s under unchanged 200N limit; cannot explain the full ~93.7 N s matched contrast. No pure-coordination causal effect or generalization claim.')
 beat={}
 for scope,record in best.items():
  beat[scope]={r['name']:dict(beats=record['J_F']<r['J_F'],difference_n_s=r['J_F']-record['J_F'],force_peak_change=record['force_peak']-r['force_peak'],moment_peak_change=record['moment_peak']-r['moment_peak'],duration_change=record['duration_s']-r['duration_s']) for r in comparators['rows'] if r['valid'] and r['scope']==scope}
 valid_periodic=[r for r in evaluations if r['valid'] and r.get('tag')=='periodic'];learning_improving=None
 if len(valid_periodic)>=4:
  last=sorted(valid_periodic,key=lambda r:(r['seed'],r['training_step']))[-4:];learning_improving=max(r['J_F'] for r in last[:-1])-last[-1]['J_F']>=1.
 questions=[
  dict(question='What caused 1.020s HOLD?',answer='Two .5s stationary certified schedules, each with one 5ms asynchronous activation wait and one 5ms receipt-owned endpoint recognition. Phase transitions are checked every 5ms, before reference progress commit. No controller bug or SAC-period quantization.'),
  dict(question='What timing protocol is frozen and why?',answer='Physical .5s contiguous valid HOLD unchanged; MATCHED minima 9/1/9s, each upper bound +max(.020 policy tick, 2*(.005 activation+.005 receipt recognition))+.000000001s. Same range for every method, source-derived before SAC training.'),
  dict(question='Do original controller and strong comparators qualify fairly?',answer=comparators['status'],detail='Unchanged physical evaluator and model/initial conditions; old controller is fairly represented without modifying its planner. CEM is an archived descriptor transferred through this interface, not reproduction of its historical number.'),
  dict(question='Is fixed hip-leading ~877.7 primarily timing, coordination, or unresolved?',answer='Native reduction includes substantial duration effects. After common timing eligibility, a smaller matched benefit remains. Coordination versus within-phase pacing is unresolved as a causal decomposition.',detail=effects),
  dict(question='Did SAC train successfully?',answer='Formal CUDA optimization executed with finite logged losses; the resource stop prevented the meaningful >=300k campaign. No valid learned expert is confirmed.' if formal and not trained else 'Meaningful formal campaign completed; valid-policy success is assessed independently.' if trained else 'No formal optimization started.',meaningful_campaign_completed=trained,formal_started=formal,steps=total,gradient_updates=sum(s.get('gradient_updates',0) for s in seeds['seeds']),seeds=seeds['seeds']),
  dict(question='Best SAC NATIVE J_F?',answer=best.get('NATIVE',{}).get('J_F'),qualification_references_never_counted=True),
  dict(question='Best SAC MATCHED J_F?',answer=best.get('MATCHED',{}).get('J_F'),independent_two_reload_confirmation_required=True),
  dict(question='Does SAC beat original, fixed, CEM?',answer=beat or 'No confirmed valid SAC candidate, so no beating claim.'),
  dict(question='Does SAC discover different coordination?',answer=analyses or 'No confirmed valid SAC trajectory exists for this claim.',limit='Lead/lag descriptives do not establish novelty or a global optimum.'),
  dict(question='Does integral reduction increase peaks?',answer=beat or 'No SAC result. Fixed comparator reduces cost while its force/moment peaks exceed old nominal.',fixed_reference=effects),
  dict(question='Is learning still improving at stop?',answer=learning_improving,limit='Requires valid deterministic periodic evaluation evidence; episode reward alone is insufficient.'),
  dict(question='Is more SAC justified before TQC/PPO?',answer='Review measured warmup/reset throughput and valid independent checkpoint trend on this unchanged contract first. Do not switch algorithms to bypass an unresolved resource, throughput or valid-task limitation.')]
 analysis=dict(status='CONFIRMED_VALID_SAC' if best else 'NO_CONFIRMED_VALID_SAC',questions=questions,confirmed_policies=analyses,comparisons=beat,fixed_reference_timing_analysis=effects,valid_evaluation_count=sum(r['valid'] for r in evaluations),invalid_evaluation_count=sum(not r['valid'] for r in evaluations),learning_still_improving=learning_improving,single_fixed_exposed_Human_only=True,no_algorithm_reliability_or_global_optimum_claim=True)
 write(D1/'SAC_BEST_POLICY_ANALYSIS_R2.json',analysis)
 (D1/'SAC_BEST_POLICY_ANALYSIS_R2.md').write_text('# SAC R2 scientific analysis\n\n'+ '\n\n'.join(f'{i+1}. {r["question"]}\n\n{r["answer"]}' for i,r in enumerate(questions))+'\n\nDetailed phase metrics, raw traces, lead/lag statistics and comparisons are in JSON. Native and MATCHED-TIMING are separate rankings; timing allowance does not equalize within-phase pacing.\n')
 for name in ('SAC_THROUGHPUT','SAC_RUNTIME_PROFILE','SAC_TRAINING_CONFIG','SAC_LEARNING_CURVE','SAC_CHECKPOINT_EVALUATION'):
  extensions=('.csv',) if name.endswith('CURVE') or name.endswith('EVALUATION') else ('.json','.md')
  for ext in extensions:
   source=D/(name+ext)
   if source.exists():shutil.copy2(source,D1/(name+'_R2'+ext))
 for name in ('SAC_LEARNING_CURVE_R2.csv','SAC_CHECKPOINT_EVALUATION_R2.csv'):
  if not (D1/name).exists():csvfile(D1/name,[],['seed','training_step','scope','valid','J_F','status'])
 for name in ('SAC_THROUGHPUT_R2','SAC_RUNTIME_PROFILE_R2'):
  if not (D1/(name+'.json')).exists():write(D1/(name+'.json'),dict(status='NOT_REACHED',reason=state.get('blocker',state['phase'])))
  if not (D1/(name+'.md')).exists():(D1/(name+'.md')).write_text('# '+name+'\n\nNot reached; consult preserved STATE_R2 and exception evidence.\n')
 summary=dict(status=terminal,formal_steps=total,wall_s=time.time()-pre['started_unix'],training_wall_s=sum(s.get('wall_s',0) for s in seeds['seeds']),seeds=seeds['seeds'],best_confirmed={scope:{k:r.get(k) for k in ('seed','training_step','J_F','force_peak','moment_peak','duration_s','phase_durations','valid','checkpoint')} for scope,r in best.items()},strongest_comparators={scope:{k:r.get(k) for k in ('name','J_F','force_peak','moment_peak','duration_s','phase_durations')} if r else None for scope,r in strongest.items()},source_integrity=integrity,blocker=state.get('blocker'),stop_reasons=[s.get('stop_reason') for s in seeds['seeds']],latest_resource=resources[-1] if resources else None,fixed_reference_analysis=effects,scientific_qualification='SAC_EXPERT_V1_R2_QUALIFIED' if comparators['status']=='PASS' else comparators['status'],resource_state='SAC_READY_WAITING_FOR_RESOURCES' if waiting else 'NO_RECORDED_RESOURCE_STOP',minimum_meaningful_campaign_reached=bool(seeds['seeds'] and seeds['seeds'][0]['completed_steps']>=300000),ordinary_failed_training_episodes_not_scientific_blockers=True)
 write(D1/'SAC_EXPERT_V1_SUMMARY_R2.json',summary)
 report=[f'# Single-Human SAC Expert v1 R2\n\nStatus: **{terminal}**. Formal steps {total}; additional wall {summary["wall_s"]/3600:.3f} h. Stop/blocker: {state.get("blocker") or summary["stop_reasons"] or state["phase"]}.\n',
 '## Timing repair and qualification\n\nR1 blocked qualification is preserved byte-for-byte. The physical task requires minimum 0.5s continuously valid HOLD. The prior MATCHED 1s minimum is a comparison clock, not a new physical dwell requirement. The 1.020s old-controller HOLD is caused by two 0.5s references with one 5ms activation wait and one 5ms receipt-owned endpoint recognition each. Source plus transparent deterministic probe confirm this chain; no production controller or physical task edit was made.\n\nR2 common phase clocks are 9/1/9s. Each method must pass the unchanged independent physical evaluator and meet T_min-1e-9 <= actual T <= T_min+.020+1e-9. Slack is max(.020 policy tick, ceil(1/.5)*(.005 activation+.005 receipt confirmation)). Frozen at zero SAC training steps; all methods use exactly the same bounds. Every physical waiting interval remains in force cost.\n\nThe 55-D causal observation, independent 2-D full-ROM target action, reward, fixed normalization, 20ms policy cadence, commissioning-only Human model, CR12/cuff/Human plant, safety and evaluator are unchanged. Already passed action/reward/reset/CUDA/normalization evidence is reused by hash. Only affected timing/comparator gates are requalified. Native and matched are separate scopes.\n',
 '## Comparator requalification\n\n'+json.dumps([ {k:r.get(k) for k in ('name','scope','task_valid','matched_eligible','valid','phase_durations','duration_s','J_F','force_peak','moment_peak','clearance')} for r in comparators['rows']],indent=2)+'\n\nCEM transfer uses the pre-existing scheduler-screened reference target/phase-clock descriptor through the qualified online interface, never hidden Human trajectory. It is not a reproduction of historical CEM cost. Exact CSV and unchanged/new traces are in SAC_COMPARATOR_REQUALIFICATION.\n',
 '## Training, throughput and resources\n\n'+json.dumps(seeds,indent=2)+'\n\nFormal config uses SB3 SAC, CUDA, 2x256 ReLU, Adam3e-4, batch256, replay100k, learning_starts5000, gamma exp(-.02/150), tau .005, auto entropy and one environment. Benchmark weights/replay are discarded; training initializes from its seed. Deterministic native/matched checkpoint evaluations run at 25k intervals with optimizer/replay/normalization unchanged; selection uses valid physical J_F and two independent reload confirmations within1e-6 N s.\n\nMechanical benchmark learning_starts32 measures real CUDA updates; an additional exact formal-config random-action warmup measurement retains learning_starts5000. Resource samples record Windows free RAM, WSL available memory, swap, CPU, GPU/VRAM and other Python owners. No other study is killed, paused, reconfigured or reniced. Additional hard cap is12h from R2 preflight, with closeout reservation. Ordinary failed episodes remain learning data.\n',
 '## Required scientific questions\n\n'+'\n\n'.join(f'{i+1}. {r["question"]}\n\n{r["answer"]}' for i,r in enumerate(questions))+'\n',
 '## Interpretation limits\n\n'+json.dumps(effects,indent=2)+'\n\nMatched eligibility leaves within-phase pacing and up to60ms total residual timing variation. A smaller fixed-reference matched benefit does not by itself isolate pure coordination. No hidden-truth policy, held-out Human, generalization, algorithm reliability, hardware, or global-optimum claim follows.\n',
 '## Provenance and Git\n\n'+json.dumps(integrity,indent=2)+'\n\nExisting staged entries and worktree bytes were preserved exactly. New evidence and R2 scripts are staged individually; raw physics/checkpoints are inventoried outside the index. No commit/push/merge/reset/stash.\n',
 '## Next recommended step\n\nReview measured warmup/reset throughput and valid deterministic SAC checkpoint evidence before any separately authorized SAC extension or algorithm comparison.\n']
 (D1/'SAC_EXPERT_V1_REPORT_R2.md').write_text('\n'.join(report))
 state.update(status=terminal,resource_state=summary['resource_state'],scientific_qualification=summary['scientific_qualification'],phase='CLOSEOUT_COMPLETE_R2',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),training_steps=total,next_action='STOP. Preserve the qualified R2 contract, checkpoints, negative results and resource evidence; no other algorithms/studies.',resume_prerequisite='New resource-safe evidence before a separately recorded continuation of this same R2 checkpoint/replay; do not change observation/action/reward/normalization/adaptation to bypass failures.',committed=False,pushed=False,merged=False)
 write(D/'STATE.json',state);write(D1/'STATE_R2.json',state)
 # Preserve newly created compact physical artifacts losslessly and inventory.
 for raw in O.rglob('runtime_artifacts.json'):
  dest=Path(str(raw)+'.gz');original=sha(raw)
  with raw.open('rb') as src,gzip.open(dest,'wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(dest,'rb') as check:h=hashlib.sha256(check.read()).hexdigest()
  assert h==original;raw.unlink()
 staged=[]
 for root in (P,D):
  for path in sorted(root.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.json','.md','.csv','.txt'):
    relative=str(path.relative_to(R));subprocess.run(['git','-C',str(R),'add','--',relative],check=True);staged.append(relative)
 for path in sorted(D1.iterdir()):
  if path.is_file() and (path.name.endswith('_R2.json') or path.name.endswith('_R2.md') or path.name.endswith('_R2.csv') or path.name in ('SAC_TIMING_BLOCKER_DIAGNOSIS.json','SAC_TIMING_BLOCKER_DIAGNOSIS.md','SAC_COMPARATOR_REQUALIFICATION.json','SAC_COMPARATOR_REQUALIFICATION.csv')):
   relative=str(path.relative_to(R));subprocess.run(['git','-C',str(R),'add','--',relative],check=True);staged.append(relative)
 write(D1/'FINAL_GIT_STATE_R2.json',dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),status=git('status','--short'),preexisting_entries_exactly_preserved=original_entries.issubset(set(git('ls-files','--stage').splitlines())),new_stage_paths=staged,commit=False,push=False,merge=False))
 subprocess.run(['git','-C',str(R),'add','--',str((D1/'FINAL_GIT_STATE_R2.json').relative_to(R))],check=True)
 manifest=[]
 paths=list(P.rglob('*'))+list(D.rglob('*'))+list(O.rglob('*'))+[p for p in D1.iterdir() if p.is_file() and ('_R2' in p.name or p.name.startswith('SAC_TIMING_BLOCKER') or p.name.startswith('SAC_COMPARATOR_REQUALIFICATION'))]
 for p in sorted(set(paths)):
  if p.is_file() and '__pycache__' not in p.parts and p.name!='RAW_DATA_MANIFEST_R2.json':manifest.append(dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=sha(p),raw_or_checkpoint=O in p.parents))
 write(D1/'RAW_DATA_MANIFEST_R2.json',dict(files=manifest,manifest_self_excluded=True,preexisting_bytes_verified=integrity['pass_'],formal_steps=total));subprocess.run(['git','-C',str(R),'add','--',str((D1/'RAW_DATA_MANIFEST_R2.json').relative_to(R))],check=True)
 # Refresh final Git inventory after manifest staging; then refresh its single
 # manifest hash. The manifest excludes itself, so no circular hash exists.
 git_path=D1/'FINAL_GIT_STATE_R2.json';git_state=json.loads(git_path.read_text());git_state['status']=git('status','--short');write(git_path,git_state)
 for item in manifest:
  if item['path']==str(git_path.relative_to(R)):item.update(bytes=git_path.stat().st_size,sha256=sha(git_path))
 write(D1/'RAW_DATA_MANIFEST_R2.json',dict(files=manifest,manifest_self_excluded=True,preexisting_bytes_verified=integrity['pass_'],formal_steps=total))
 for path in (git_path,D1/'RAW_DATA_MANIFEST_R2.json'):subprocess.run(['git','-C',str(R),'add','--',str(path.relative_to(R))],check=True)
 W.mkdir(parents=True,exist_ok=True)
 for p in D1.iterdir():
  if p.is_file() and ('_R2' in p.name or p.name.startswith('SAC_TIMING_BLOCKER') or p.name.startswith('SAC_COMPARATOR_REQUALIFICATION')):shutil.copy2(p,W/p.name)
 assert original_entries.issubset(set(git('ls-files','--stage').splitlines()))
 print(json.dumps({k:summary[k] for k in ('status','formal_steps','wall_s','training_wall_s','strongest_comparators','blocker','stop_reasons')}),flush=True)
 print('REPORT: '+str(W/'SAC_EXPERT_V1_REPORT_R2.md'),flush=True)
if __name__=='__main__':main()
