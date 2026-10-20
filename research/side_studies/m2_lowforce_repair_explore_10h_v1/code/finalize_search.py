from pathlib import Path
import os,sys,json,time,hashlib,subprocess,gzip,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_lowforce_repair_explore_10h_v1')
def load(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,(np.integer,np.bool_)):return x.item()
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def put(name,x):
 p=S/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git(root):
 def g(*a):return subprocess.check_output(['git','-C',str(root),*a],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode()
 return dict(branch=g('branch','--show-current'),HEAD=g('rev-parse','HEAD'),status=g('status','--porcelain=v1'),index=sha(root/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest())
def maxburden(r):return max(max(v) for v in r['comparison']['burden_ratios'].values())
def main():
 protocol=load(S/'SEARCH_PROTOCOL.json');attempts=[json.loads(r) for r in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in attempts if r['event']=='START'];ends={r['id']:r for r in attempts if r['event']=='END'}
 rows=[json.loads(r) for r in (S/'RESULTS.jsonl').read_text().splitlines()] if (S/'RESULTS.jsonl').exists() else []
 task_failures=[load(p) for p in sorted((S/'reports').glob('*_TASK_FAILURE.json'))]
 put('TASK_FAILURES.json',dict(denominator=len(task_failures),candidates=task_failures,partial_integrals_never_ranked=True))
 selection=load(S/'FROZEN_SELECTION.json') if (S/'FROZEN_SELECTION.json').exists() else {'candidates':[],'status':'INCOMPLETE_DISCOVERY','eligible_count':0}
 catalog=load(S/'CANDIDATE_CATALOG.json')['candidates'];clook={r['id']:r for r in catalog};discover=[r for r in rows if r['id'].startswith('discovery_') and r['stage'] in ['C1','C2','C3','C4','REFERENCE'] and r['candidate_id']!='Frozen_M2'];eligible=[r for r in discover if r['comparison']['eligible']]
 valid=[]
 for c in selection['candidates']:
  cr=[r for r in rows if r['candidate_id']==c['id'] and r['id'].startswith(('H1_','H2_'))]
  failed=[r for r in task_failures if r['candidate_id']==c['id'] and r['id'].startswith(('H1_','H2_'))]
  ok=len(cr)==2 and not failed and all(r['comparison']['eligible'] for r in cr)
  valid.append(dict(candidate_id=c['id'],conditions=len(cr)+len(failed),PASS=ok,results=cr,task_invalid_conditions=failed))
 vstatus='NOT_RUN_DISCOVERY_GATE_FAILED' if not selection['candidates'] and selection['status']!='INCOMPLETE_DISCOVERY' else 'INCOMPLETE_DISCOVERY' if selection['status']=='INCOMPLETE_DISCOVERY' else 'SCI_VALIDATED' if any(r['PASS'] for r in valid) else 'DISCOVERY_NOT_VALIDATED' if all(r['conditions']==2 for r in valid) else 'INDEPENDENT_VALIDATION_INSUFFICIENT'
 put('VALIDATION_RESULTS.json',dict(status=vstatus,clock='SCIENTIFIC_MATCHED_EXECUTION',heldout_conditions=protocol['validation_conditions'],results=valid,no_reselection=True,selection_sha256=sha(S/'FROZEN_SELECTION.json') if (S/'FROZEN_SELECTION.json').exists() else None,conditions_not_used_for_search=True,new_Human=False,population_validation=False,host_clock_qualified=False,baseline_and_M2=[r for r in rows if r['candidate_id']=='Frozen_M2']))
 pareto=[]
 for r in discover:
  x=np.array([-r['comparison']['gain_percent'],maxburden(r),max(r['comparison']['excursion_delta_deg'])])
  if not any(np.all(np.array([-a['comparison']['gain_percent'],maxburden(a),max(a['comparison']['excursion_delta_deg'])])<=x+1e-12) and np.any(np.array([-a['comparison']['gain_percent'],maxburden(a),max(a['comparison']['excursion_delta_deg'])])<x-1e-12) for a in discover if a is not r):pareto.append(r)
 active=[r for r in discover if r['comparison']['actual_nonzero_count']>0]
 reps=dict(lowest_J_F=min(discover,key=lambda r:-r['comparison']['gain_percent']) if discover else None,smoothest=min(active,key=maxburden) if active else None,best_eligible=min(eligible,key=lambda r:-r['comparison']['gain_percent']) if eligible else None)
 put('FORCE_MOTION_PARETO.json',dict(axes=['actual full J_F','maximum raw B-relative motion burden','maximum excursion difference'],candidates=pareto,representatives=reps,Frozen_M2_reference=[r for r in rows if r['candidate_id']=='Frozen_M2' and r['id'].startswith('discovery_')],finite_sample_only=True,clinical_threshold=False))
 coverage={};executed_ids={r['candidate_id'] for r in discover}|{r['candidate_id'] for r in task_failures if r['id'].startswith('discovery_')}
 for dim in protocol['dimensions']:
  values=[];n=0
  for c in catalog:
   if c['id'] not in executed_ids:continue
   specs=[(ph,i,s) for ph,a in c.get('phases',{}).items() for i,s in enumerate(a) if s is not None]
   val={'phase':[ph for ph in c.get('phases',{})],'sign':[int(np.sign(s['amplitude'])) for _,_,s in specs],'amplitude':[s['amplitude'] for _,_,s in specs],'slot_mask':[(ph,i) for ph,i,_ in specs],'remaining_progress_onset':[s['support'][0] for _,_,s in specs],'remaining_progress_support':[s['support'] for _,_,s in specs],'PWL_knot_locations':[s['knots'] for _,_,s in specs],'PWL_shape':[s['shape'] for _,_,s in specs],'joint_phase_independent_parameters':[c.get('parameters')] if len(c.get('phases',{}))==2 else [],'within_phase_slot_combination':[(ph,[i for p,i,_ in specs if p==ph]) for ph in c.get('phases',{})]}.get(dim,[])
   if val:n+=1;values.extend(val)
  distinct=sorted({json.dumps(v,sort_keys=True) for v in values});coverage[dim]=dict(candidates_tested=n,distinct_values=len(distinct),values=[json.loads(v) for v in distinct])
 lines=[];states=collections.Counter();rejections=collections.Counter();actual_nonzero_attempts=0;native_nonzero_plans=0;actual_steps=0;completed=0
 metrics={};exports=0;invalid_exports=[];candidate_attempts=[]
 for a in starts:
  if not a['id'].startswith('discovery_'):continue
  match=next((c for c in catalog if a['id'].endswith('_'+c['id'])),None)
  if match and match['stage']!='RETURN_DIAGNOSTIC':candidate_attempts.append(dict(id=a['id'],candidate_id=match['id'],stage=match['stage'],parameters=match.get('parameters',{}),ended=ends.get(a['id'])))
 for a in starts:
  ident=a['id'];mp=S/'reports'/(ident+'_MEASURED.json');lp=S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');out=S/'output'/(ident+'.json')
  if out.exists():
   m=load(out);dp=S/'output'/(ident+'_DATA.json');account=load(dp)['metric'] if dp.exists() else m;actual_steps+=int(account.get('actual_new_native_physics_steps',account.get('native_physics_steps',0)));exports+=1
   if m.get('task_valid'):completed+=1
   else:invalid_exports.append(ident)
  elif (S/'output'/(ident+'_PARTIAL_COMPUTE.json')).exists():actual_steps+=int(load(S/'output'/(ident+'_PARTIAL_COMPUTE.json')).get('actual_new_native_physics_steps') or 0)
  if mp.exists():metrics[ident]=load(mp)
  if not lp.exists():continue
  l=load(lp);data_path=S/'output'/(ident+'_DATA.json');data=load(data_path) if data_path.exists() else {};fork_s=(data.get('child') or {}).get('physical_time_at_fork',0.)
  new_nonzero=[r for r in l['rows'] if r['physically_executed_nonzero'] and r['first_execution_physics_s']>=fork_s-1e-9]
  actual_nonzero_attempts+=bool(new_nonzero);native_nonzero_plans+=len(new_nonzero);nr=[]
  for r in l['rows']:
   meta=r['native_coordination_metadata'][0];admit=meta.get('status')=='ACCEPTED';act=r['selected_plan_activated'];exe=r['physically_executed_nonzero']
   new=r.get('proposal_physics_s') is not None and r['proposal_physics_s']>=fork_s-1e-9
   states['PROPOSED']+=new and meta.get('status') in ['ACCEPTED','REJECTED','PROPOSED'];states['NATIVE_FEASIBLE']+=new and admit;states['ADMITTED']+=new and admit and act;states['ACTIVATED']+=new and admit and act;states['NATIVE_PLAN_ACTIVATED_ANY']+=new and act;states['EXECUTED_NONZERO']+=new and exe
   if meta.get('status')=='REJECTED':rejections[str(meta.get('reason'))]+=1
   if r.get('rejection_reason'):rejections[str(r['rejection_reason'])]+=1
   nr.append({k:r[k] for k in ['decision_index','request_id','phase','proposal_physics_s','activation_outcome','selected_plan_activated','native_coordination_metadata','actual_native_steps','physically_executed_nonzero','first_execution_physics_s','stale','deadline_miss','rejection_reason']})
  lines.append(dict(id=ident,status=l['status'],receipt_count=l['receipt_count'],native_steps=l['native_steps'],actual_new_nonzero_count=len(new_nonzero),actual_new_nonzero_native_steps=sum(r['actual_native_steps'] for r in new_nonzero),full_trace_nonzero_count=l['actual_nonzero_count'],inherited_nonzero_count=l['actual_nonzero_count']-len(new_nonzero),physical_time_at_fork=fork_s,rows=nr,complete_receipts_path=str(lp),ownership_error_count=l['ownership_error_count'],expiry=l['expired_actual_write_receipts'],native_lifecycle=l['native_lifecycle']))
 put('NATIVE_EXECUTION_LINEAGE.json',dict(attempt_denominator=len(starts),actual_nonzero_attempts=actual_nonzero_attempts,native_nonzero_plans=native_nonzero_plans,states=dict(states),ADMITTED_evidence='native residual feasible metadata AND original successful lifecycle activation; activation implies original admission path completed, but does not imply physical execution',rejections=dict(rejections),runs=lines,proposal_or_activation_not_execution=True))
 phase_rows=[];interactions=[];dlookup={r['candidate_id']:r for r in discover}
 for r in discover:
  phase_rows.append(dict(candidate_id=r['candidate_id'],gain_percent=r['comparison']['gain_percent'],phase_delta_N_s=r['comparison']['phase_J_F_delta_N_s'],symmetric_decomposition=r['comparison']['symmetric_phase_decomposition'],executed_phases=r['comparison']['executed_phases']))
  p=clook[r['candidate_id']].get('parameters',{})
  if p.get('O_source') in dlookup and p.get('R_source') in dlookup:
   o=dlookup[p['O_source']];rr=dlookup[p['R_source']];same_parent=all(load(S/'output'/(x['id']+'_DATA.json'))['branch_start']['full_hash']==load(S/'output'/(r['id']+'_DATA.json'))['branch_start']['full_hash'] for x in [o,rr])
   interactions.append(dict(candidate=r['candidate_id'],O_source=p['O_source'],R_source=p['R_source'],interaction_gain_N_s=r['comparison']['gain_N_s']-o['comparison']['gain_N_s']-rr['comparison']['gain_N_s'],same_full_parent_state=same_parent,scope='same-full-parent factorial trajectory interaction' if same_parent else 'cross-parent descriptive contrast after exact zero-control comparability gate; not full-state factorial causal evidence',warning='total path interaction; independent RETURN effect cannot be inferred when O changes its entry state'))
 entries={}
 for ident,m in metrics.items():
  path=S/'motion_series'/(ident+'.npz')
  if not path.exists():continue
  with np.load(path) as z:
   j=np.flatnonzero(z['phase']=='RETURN')[0];entries[ident]=dict(physical_s=float(z['time_s'][j]),q_rad=z['true_q_rad'][j],dq_rad_s=z['true_dq_rad_s'][j])
 negative=[]
 import analyze_matched as am
 for r in discover:
  if r['comparison']['executed_phases']==['RETURN']:negative.append(am.negcontrol(r['id'],'discovery_B0_repeat_1'))
 attribution=dict(rows=phase_rows,matched_pair_interactions=interactions,RETURN_entry_states=entries,RETURN_only_preintervention_checks=negative,independent_RETURN_entry_result=[r for r in rows if r['stage']=='RETURN_DIAGNOSTIC'],moment_not_momentum=True,clock='SCIENTIFIC_MATCHED_EXECUTION')
 put('PHASE_ATTRIBUTION.json',attribution)
 (S/'PHASE_ATTRIBUTION.md').write_text('# 阶段归因\n\n完整匹配初态的阶段差见 PHASE_ATTRIBUTION.json。RETURN-only 的介入前全部 trace 字段执行精确负对照；双阶段收益是全轨迹作用，OUTBOUND 改变 RETURN 入口后不能称为 RETURN 独立因果收益。另从 B 历史的同 RETURN 入口直接比较冻结的单阶段候选。moment 指力矩，不是 momentum。\n\n'+json.dumps(clean(interactions),indent=2,ensure_ascii=False)+'\n')
 sensitivity=collections.Counter();fails=collections.Counter()
 for r in discover:
  fails.update(r['comparison']['failed_requirements'])
  for k,v in r['comparison']['burden_sensitivity'].items():sensitivity[k]+=bool(v)
 correlations=[]
 for ph in ['OUTBOUND','RETURN']:
  rr=[r for r in discover if r['stage']=='C1' and r['parameters'].get('phase')==ph]
  for prof in sorted({r['parameters'].get('profile') for r in rr}):
   g=[r for r in rr if r['parameters']['profile']==prof];x=[r['parameters']['amplitude'] for r in g];y=[r['comparison']['gain_percent'] for r in g];acc=[max(r['comparison']['burden_ratios']['acceleration_deg_s2/p95_abs']) for r in g]
   correlations.append(dict(phase=ph,profile=prof,n=len(g),descriptive_amplitude_force_gain_correlation=float(np.corrcoef(x,y)[0,1]) if len(g)>2 else None,descriptive_amplitude_p95_acceleration_correlation=float(np.corrcoef(x,acc)[0,1]) if len(g)>2 else None,not_independent_causal_parameter_effect=True))
 summary=dict(status=vstatus,attempt_denominator=len(starts),exported_trace_attempts=exports,completed_full_trace_attempts=completed,task_invalid_trace_attempts=invalid_exports,failed_or_incomplete=[dict(id=a['id'],end=ends.get(a['id'])) for a in starts if not (S/'output'/(a['id']+'.json')).exists()]+task_failures,search_candidates_evaluated=len(candidate_attempts),complete_search_comparisons=len(discover),candidate_attempts=candidate_attempts,counts_by_stage=dict(collections.Counter(r['stage'] for r in candidate_attempts)),nonzero_executed_attempts=actual_nonzero_attempts,nonzero_native_plans=native_nonzero_plans,actual_new_native_steps=actual_steps,eligible_discovery_count=len(eligible),motion_accepted_search_count=sum(r['comparison']['acceptance_pass'] for r in discover),acceptance_failures=dict(fails),sensitivity_motion_burden_only=dict(sensitivity),coverage=coverage,uncovered=['arbitrary finite PWL graph universe','continuous full 30D space','additional Human models','host-clock execution','new controller freedoms','all progress support/knots combinations'],representatives=reps,parameter_diagnostics=correlations,raw_metrics_index={i:str(S/'reports'/(i+'_MEASURED.json')) for i in metrics},all_evaluations_actual_native_physics=True,no_Q_training=True,actual_attempt_wall_s={a['id']:ends[a['id']]['unix']-a['unix'] for a in starts if a['id'] in ends},raw_host_elapsed_is_inherited_parent_clock_not_per_child_compute=True)
 line_lookup={r['id']:r for r in lines}
 summary['candidate_qualifications']={r['id']:dict(PROPOSED=True,ADMITTED=any(x['selected_plan_activated'] and x['native_coordination_metadata'][0].get('status')=='ACCEPTED' and (x.get('proposal_physics_s') or 0)>=line_lookup[r['id']]['physical_time_at_fork']-1e-9 for x in line_lookup[r['id']]['rows']),ACTIVATED=any(x['selected_plan_activated'] for x in line_lookup[r['id']]['rows']),EXECUTED=r['comparison']['actual_nonzero_count']>0,TASK_VALID=metrics[r['id']]['axes']['PHYSICAL_TASK_VALID']=='PASS',MOTION_ACCEPTED=r['comparison']['acceptance_pass'],DISCOVERY_ELIGIBLE=r['comparison']['eligible']) for r in discover if r['id'] in line_lookup and r['id'] in metrics}
 put('SEARCH_SUMMARY.json',summary)
 put('TRAINING_SOURCE_INDEX.json',dict(label_scope='actual complete SCI fork continuation with fixed candidate through full task; not HOST_CLOCK V_replan or clinical label',full_task_candidates=[dict(id=r['id'],candidate_id=r['candidate_id'],native_task_valid=True,motion_accepted=r['comparison']['acceptance_pass'],J_F_gain_percent=r['comparison']['gain_percent'],graph_parameters=clook[r['candidate_id']],decision_graph_path=str(S/'output'/(r['id']+'_DECISIONS.json')),metrics_path=r['metrics_path'],raw_trace_dir=str(S/'source/results'/r['id'])) for r in discover],task_failure_candidates=task_failures,action_encoding_warning='For raw_v2 rows, legacy action=[0,0,0] and previous K3 vector are logging placeholders, not the executed action. Use graph/registered_spec/expected_delta and actual native metadata. Rebuild a causal raw-PWL plan/history encoder before any Neural Q training; never treat the placeholders as zero-control labels.',independent_Human_count=1,independent_training_state_count='complete fork hashes are indexed per parent; repeated children do not create independent Human/state samples',no_training_performed=True))
 action=load(S/'ACTION_SPACE_MAP.json')
 for dim,v in action['dimensions'].items():
  v['evaluated_candidate_count']=coverage[dim]['candidates_tested'];v['distinct_parameter_values']=coverage[dim]['distinct_values'];v['execution_verified']=any(r['comparison']['actual_nonzero_count']>0 for r in discover)
 ranges={'phase':['OUTBOUND','RETURN'],'sign':[-1,0,1],'amplitude':[-.2,.2],'slot_mask':{'per_phase_indices':[0,1,2,3,4],'combinations':'registered subsets'},'remaining_progress_onset':'0 <= lo < hi <= 1','remaining_progress_support':'0 <= lo < hi <= 1','PWL_knot_locations':'strictly ordered interior fractions (0,1), this search uses 3; native accepts arbitrary finite graph','PWL_shape':['flat','ramp','taper','tent','reverse'],'joint_phase_independent_parameters':'separate OUTBOUND and RETURN slot graphs','within_phase_slot_combination':'up to 5 registered issued slots per phase'}
 for dim,v in action['dimensions'].items():v['range']=ranges[dim]
 action['actual_execution_scope']='verified finite registered candidates only; parameter-range endpoints or all graphs are not certified';put('ACTION_SPACE_MAP.json',action)
 (S/'ACTION_SPACE_MAP.md').write_text('# 可执行动作空间审计\n\n'+json.dumps(clean(action),indent=2,ensure_ascii=False)+'\n')
 samples=[json.loads(r) for r in (S/'RESOURCE_SAMPLES.jsonl').read_text().splitlines()];rawbytes=sum(p.stat().st_size for p in (S/'source/results').rglob('*') if p.is_file());bytes_=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())
 audit=dict(start_unix=protocol['t0_unix'],end_unix=time.time(),elapsed_wall_s=time.time()-protocol['t0_unix'],last_new_experiment_unix=max((a['unix'] for a in starts),default=None),dispatch_cutoff_unix=protocol['dispatch_cutoff_unix'],hard_stop_unix=protocol['hard_stop_unix'],within_time_cap=time.time()<=protocol['hard_stop_unix'],within_attempt_cap=len(starts)<=160,actual_new_native_steps=actual_steps,resource_samples=samples,min_D_free_bytes=min(r['D_free_bytes'] for r in samples),min_linux_available_bytes=min(r['linux_available_bytes'] for r in samples),max_child_rss_KiB=max(r.get('children_max_rss_KiB',0) for r in samples),joined_child_CPU_s=sum(max((r.get('joined_children_cpu_s',0) for r in samples if r['pid']==pid),default=0) for pid in {r['pid'] for r in samples}),total_package_bytes=bytes_,raw_evidence_bytes=rawbytes,deleted_files=[],no_windows_full_copy=True)
 put('RESOURCE_AND_STORAGE_AUDIT.json',audit)
 audit['joined_child_CPU_scope']='sum of last observed cumulative per-parent RUSAGE_CHILDREN; lower bound if a parent ended without final sampling (first failed parent). Not a continuous host CPU or scheduler-wait measurement.'
 win_path=S/'WINDOWS_RESOURCE_SAMPLES.jsonl'
 if win_path.exists():
  wr=[json.loads(r) for r in win_path.read_text(encoding='utf-8-sig').splitlines() if r.strip()];audit['windows_samples']=wr;audit['windows_min_sampled_free_physical_KiB']=min(r['FreePhysicalMemory'] for r in wr);audit['windows_min_sampled_free_virtual_KiB']=min(r['FreeVirtualMemory'] for r in wr)
 put('RESOURCE_AND_STORAGE_AUDIT.json',audit)
 before=load(S/'preservation/GIT_BEFORE.json');after={r:git(Path(r)) for r in before};put('preservation/GIT_AFTER.json',after)
 hashes=load(S/'preservation/PROTECTED_HASHES.json');changed=[p for p,h in hashes.items() if not Path(p).exists() or sha(Path(p))!=h]
 inventory=load(S/'preservation/HISTORY_INVENTORY.json');ichanged=[p for p,v in inventory.items() if not Path(p).exists() or [Path(p).stat().st_size,Path(p).stat().st_mtime_ns]!=v]
 old=S.parent/'m2_matched_bidirectional_exploration_v1';sourcechanges=[]
 for rel in ['source/stages','deps/fork_core.py']:
  pp=S/rel;files=[pp] if pp.is_file() else [p for p in pp.rglob('*') if p.is_file()]
  for p in files:
   original=old/p.relative_to(S)
   if not original.exists():sourcechanges.append(str(p));continue
   a=p.read_bytes();b=original.read_bytes()
   if p.suffix=='.py':b=b.replace(str(old).encode(),str(S).encode()).replace(b'm2_matched_bidirectional_exploration_v1',b'm2_comprehensive_coordination_search_v1')
   if a!=b:sourcechanges.append(str(p))
 processes=subprocess.check_output(['ps','-eo','pid,args'],text=True);owned=[r for r in processes.splitlines() if 'search_driver.py' in r and 'finalize_search.py' not in r]
 closure=[dict(id=i,force_error=m['phase_cost']['closure_error_N_s'],moment_error=m['phase_cost']['moment_closure_error_Nm_s']) for i,m in metrics.items()]
 verification=dict(unix=time.time(),git_exact_unchanged=before==after,protected_hash_count=len(hashes),protected_hash_changed=changed,history_inventory_count=len(inventory),history_metadata_changed=ichanged,B_and_fork_copy_path_only=not sourcechanges,source_copy_semantic_differences=sourcechanges,owned_physics_workers_remaining=owned,workers_exited=not owned,all_parent_checks_unchanged=all(x['unchanged'] and x['child_exitcode']==0 for p in (S/'reports').glob('*_PARENT_CHECKS.json') for x in load(p)),integral_closure=closure,within_attempt_cap=len(starts)<=160,within_time_cap=time.time()<=protocol['hard_stop_unix'],weights_training_count=0)
 verification['status']='PASS' if verification['git_exact_unchanged'] and not changed and not ichanged and not sourcechanges and not owned and verification['all_parent_checks_unchanged'] and verification['within_attempt_cap'] and verification['within_time_cap'] else 'FAIL'
 put('PACKAGE_VERIFICATION.json',verification)
 # Verification gates can supersede a performance-based recommendation.
 direction='A' if vstatus=='SCI_VALIDATED' else 'B' if eligible and vstatus in ['DISCOVERY_NOT_VALIDATED','INDEPENDENT_VALIDATION_INSUFFICIENT'] else 'D' if discover and max(r['comparison']['gain_percent'] for r in discover)>=.5 and not eligible else 'E'
 if verification['status']!='PASS' or vstatus=='INCOMPLETE_DISCOVERY':direction='E'
 best=reps['best_eligible'] or reps['lowest_J_F'];table=[]
 for name,r in reps.items():
  if r:table.append(f"| {name} | {r['candidate_id']} | {r['comparison']['gain_percent']:.6f}% | {'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'} | {maxburden(r):.6f} |")
 coverage_table='\n'.join(f"| {d} | {v['candidates_tested']} | {v['distinct_values']} |" for d,v in coverage.items())
 phase_table='\n'.join(f"| {name} / {ph} | {-r['comparison']['phase_J_F_delta_N_s'][ph]:.9f} |" for name,r in reps.items() if r for ph in ['OUTBOUND','HOLD','RETURN'])
 validation_table='\n'.join(f"| {r['id']} | {r['comparison']['gain_percent']:.6f}% | {'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'} | {', '.join(r['comparison']['failed_requirements']) or 'none'} |" for v in valid for r in v['results']) or '| 未运行 | — | — | 发现门限失败或验证未完成 |'
 frozen=next((r for r in rows if r['id']=='discovery_Frozen_M2'),None)
 frozen_text=f"匹配冻结 M2 的 J_F 收益为 {frozen['comparison']['gain_percent']:.6f}%，motion={'PASS' if frozen['comparison']['acceptance_pass'] else 'FAIL'}；失败项：{', '.join(frozen['comparison']['failed_requirements'])}。其 knee p95 velocity/acceleration/jerk 比为 {frozen['comparison']['burden_ratios']['velocity_deg_s/p95_abs'][1]:.6f}/{frozen['comparison']['burden_ratios']['acceleration_deg_s2/p95_abs'][1]:.6f}/{frozen['comparison']['burden_ratios']['jerk_deg_s3/p95_abs'][1]:.6f}。" if frozen else '冻结 M2 参照未完成。'
 shape_text=f"当前主要代表 {best['candidate_id']} 的最大 phase-shape 差为 {best['comparison']['phase_shape_max_delta_deg']:.6f}°。该指标不自动作为安全/运动失败，但表明任务运动的时间分布改变；研究接受 PASS 不等于临床舒适或治疗轨迹等效。" if best else '没有完成可用于 phase-shape 诊断的代表候选。'
 recommendation={'A':'已找到合格且可重复的协调方案，下一阶段建立正确编码的 Neural Q 训练数据；本轮不训练。','B':'已发现较好区域，需要另行有界局部优化；本轮停止。','C':'原有可执行空间不足，下一阶段研究新的协调自由度；本轮不扩接口。','D':'当前已测区域主要呈现运动质量与force的物理权衡；有限采样不证明全空间无解。','E':'当前实验或执行证据不足以识别可靠收益，先解决具体证据缺口。'}[direction]
 selection_audit=load(S/'SELECTION_BOOKKEEPING_REPAIR.json') if (S/'SELECTION_BOOKKEEPING_REPAIR.json').exists() else None
 if selection_audit:
  first_val=min(r['unix'] for r in starts if r['id'].startswith(('H1_','H2_')));verification['selection_frozen_before_heldout']=selection['unix']<first_val;verification['selection_parameters_unchanged']=selection_audit['parameters_revised'] is False;put('PACKAGE_VERIFICATION.json',verification)
 report=f'''# iHEAR Lab — Comprehensive Executable Coordination Search v1

终态：**{vstatus}**。唯一推荐方向：**{direction}**。完整性核验：**{verification['status']}**。

{recommendation}

新增实际 attempt **{len(starts)}/160**，完整任务 trace **{completed}**，导出 trace（含中止）**{exports}**，搜索候选 attempt **{len(candidate_attempts)}**，完整搜索比较 **{len(discover)}**，实际非零执行 attempt **{actual_nonzero_attempts}**，非零 native 计划 **{native_nonzero_plans}**，新增物理步 **{actual_steps}**。所有重型物理串行；原 B、commissioning、estimator、scheduler/governor、40ms bridge、100ms lifecycle、current-state admission、causal ownership、安全与 fallback 保持原合同。本轮没有 Q/Neural Q 训练、online adaptation、host-clock 资格试验或新 Human。

| 代表 | 候选 | 完整 J_F 收益 | motion | 最大 raw 负担比 |
|---|---|---:|---|---:|
{chr(10).join(table)}

主发现门限固定为 ≥0.5% J_F 改善。沿用 10% 速度/加速度 max、p95、RMS 及 jerk p95/RMS 非劣、0.5° excursion/endpoint/phase boundary、累计角位移±5%、全任务及每阶段时长±0.1s、moment integral≤25%、tracking RMS 增量≤0.5°及 peak≤5%补偿；原绝对安全与 clearance 必须 PASS。jerk max 仍测量，但按原冻结协议仅作诊断。0/5/10/25%敏感性仅作诊断，未替代主资格。phase-shape 单独保留；moment 是力矩。

{frozen_text}

{shape_text}

| 代表 / 阶段 | J_F 减少 N·s（负数表示变差） |
|---|---:|
{phase_table}

| 保留条件 / 冻结候选 | J_F 收益 | motion | 失败项 |
|---|---:|---|---|
{validation_table}

## 搜索覆盖与资格

实际阶段计数：{json.dumps(summary['counts_by_stage'],ensure_ascii=False)}。运动接受候选 {summary['motion_accepted_search_count']}，同时达到发现资格 {len(eligible)}。全部候选参数、实际分母、未执行/失败及 motion 失败项见 CANDIDATE_CATALOG.json、ATTEMPTS.jsonl、RESULTS.jsonl 和 SEARCH_SUMMARY.json。每个维度的不同参数值及测试候选数量见 SEARCH_SUMMARY.json 的 coverage；所有数值来自实际原生物理，而非 Q 预测。

| 搜索维度 | 已测候选数 | 不同参数值/组合数 |
|---|---:|---:|
{coverage_table}

接口审计区分固定 K3 库、连续 K3、raw v2、admission 与实际执行。raw v2 在每次原生目标请求处采样 PWL 图的一个值；改变图形并不授予持续时间或速度/加速度控制。非零执行通过 accepted metadata、activation、positive-step receipt 与逐 native torque/step ownership 核验。PROPOSED/ADMITTED/ACTIVATED 不代替 EXECUTED。raw 新图经相同原生接口，未直接施加隐藏 torque。

## 十二项研究判断

1. 本轮探索阶段、符号、幅度、slot mask、起始/持续进度、PWL结点/形状、独立双阶段参数及阶段内多slot组合。详见 ACTION_SPACE_MAP 和 coverage。
2. 每个维度测试数量在 SEARCH_SUMMARY.json 单独列出；重复 fork 是相同父条件的候选比较，不视作多个 Human。
3. 未覆盖任意 PWL 图、完整连续30维空间、额外 Human 和 host-clock；本轮有限采样不构成全局穷尽或数学最优。
4. 合格发现数为 {len(eligible)}；代表方案及实际 J_F、运动失败或接受见上表与 FORCE_MOTION_PARETO.json。
5. OUTBOUND/HOLD/RETURN 各自收益按完整积分精确分区，见 PHASE_ATTRIBUTION.json。RETURN-only 介入前 exact negative controls 保留，不能把早于残差的差异归因于 RETURN。
6. 双阶段与原单阶段来源的交互项按 G_OR−G_O−G_R 逐组合计算；完整父状态 hash 是否同一逐项标记。机械恢复前后的父状态命名/时钟上下文不同，即使零动作物理复现精确一致，跨父项仍只记描述性 contrast；不宣称同完整状态的 factorial 因果效应。O 改变 RETURN入口时不冒充 RETURN独立效应。独立 RETURN入口诊断另存。
7. 振幅与 force/加速度的 profile 内描述性关系见 parameter_diagnostics；形状、slot和幅度作用混合，相关性不升级为独立因果效应。
8. 两个保留 prefix 条件结果见 VALIDATION_RESULTS.json；不按验证表现重选参数，不声称已识别状态最优策略。
9. 独立验证状态为 {vstatus}。保留条件属于既有 Human 的有限合法扰动，不是人口泛化。若发现失败则正式成功验证不运行。
10. 固定候选库稀疏是覆盖限制；是否构成主要性能瓶颈由本轮实际结果限定，不能凭有限未成功搜索证明现接口无解。
11. 完整参数、原生执行链、真实密集 motion与force标签及Pareto区域可作未来数据来源；失败、未执行和零残差必须带资格标签，不能伪造成功训练标签。raw_v2 日志的旧 K3 action/previous=[0,0,0] 是记录占位符，实际动作必须从 graph/registered_spec 和 native metadata读取；未来需重新编码 raw PWL plan/history，不可直接把占位符送入旧120D Neural Q。TRAINING_SOURCE_INDEX.json 列出来源与限制。本轮不训练。
12. 唯一建议方向 {direction}，依据当前发现/验证状态；本轮停止后不扩大空间、不修改接口、不自动启动下一包。

## 复现、隔离、资源与退出

复现证据见 OUTBOUND_FORK_GATE.json、RETURN_FORK_GATE.json、PARENT_VS_CHILD_GATE.json 和每次完整 state manifest/parent check。Linux 完整地址空间 fork 保留 MuJoCo integration、控制器、commissioning、reference、lifecycle、RNG和 native handles；hash仅核验，不用于状态恢复。发现父条件与 H1/H2 验证条件隔离，候选冻结文件有时间和SHA256。SCIENTIFIC_MATCHED_EXECUTION 不等同 HOST_CLOCK_EXECUTION；后者 NOT_EVALUABLE。

本轮有一次搜索包装缺陷：原 fork 对 TASK_VALID=false 抛断言，父包装未区分任务失败与绝对安全/实际写入 ownership 失败，导致第一父进程退出。C1_020 的 +0.12 OUTBOUND flat 发生 NO_FEASIBLE_WAYPOINT；完整任务失败，原绝对安全条件与实际 receipt/native ownership 均 PASS。原失败、首父 partial compute 和代码版本保留。新增恢复注册只修正包装层的失败分类，并在同 case/seed/物理条件的新父进程上要求双零 child 精确复现及旧/新零动作全 trace/native/receipt/积分精确相等；未修改科学 fork、候选边界、阈值或测试条件，未重跑失败候选。每个原生任务失败保留未完成指标并排除完整 J_F 排名；安全/ownership FAIL 或连续3个候选任务失败仍按协议停止。额外恢复 attempt 全部计入160总预算。详见 IMPLEMENTATION_RECOVERY_REGISTRATION.json、FRESH_PARENT_COMPARABILITY_GATE.json、TASK_FAILURES.json 和 code_history。

验证前还修正了两项包装记账：冻结 M2 继承已执行共享 prefix 的 count/history，不重复 prefix；实际新残差计数排除 fork 前继承计划。代表选择的多样性项按原协议绑定实际 slot mask、shape、knots/support，而非 C4 缺失的 phase 简写。修正发生在任何保留条件运行前，未修改候选参数或资格阈值；初始选择与最终冻结均保留，见 SELECTION_BOOKKEEPING_REPAIR.json、FROZEN_SELECTION_INITIAL_IMPLEMENTATION.json、FROZEN_SELECTION.json。

截至汇总 wall {audit['elapsed_wall_s']/3600:.3f} h；保留原始证据 {rawbytes/2**30:.3f} GiB，包总量 {bytes_/2**30:.3f} GiB；监测 D 最少空闲 {audit['min_D_free_bytes']/2**30:.2f} GiB，Linux available 最少 {audit['min_linux_available_bytes']/2**30:.2f} GiB。每5次 dispatch 及父退出采样，非持续系统峰值监测。joined child CPU 与RSS计数见 RESOURCE_AND_STORAGE_AUDIT.json。没有新建Windows全量副本、没有删除历史文件或本轮证据。

主 Git branch/HEAD/status/index/staged diff 精确保护；历史 file size/mtime 全清单及源码、权重、报告、关键证据字节hash保护，覆盖范围与差异完整列于 PACKAGE_VERIFICATION.json。未将全历史 metadata 检查误称为全部大trace字节重hash。复制B源码/fork仅路径迁移核验。完整任务和阶段 J_F/moment积分闭合、所有 fork child JOIN、研究 worker退出见核验文件。

Canonical：`{S}`。STOP。
'''
 (S/'REPORT.md').write_text(report)
 manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name!='FINAL_MANIFEST.json'};put('FINAL_MANIFEST.json',manifest)
 print(json.dumps(dict(status=vstatus,direction=direction,attempts=len(starts),eligible=len(eligible),verification=verification['status'],elapsed_h=(time.time()-protocol['t0_unix'])/3600,raw_GiB=rawbytes/2**30),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
