from pathlib import Path
import json,time,hashlib,subprocess,shutil,os
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
def load(n):return json.loads((S/n).read_text())
def put(n,x):(S/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
P=load('SEARCH_PROTOCOL.json');V=load('PACKAGE_VERIFICATION.json');sel=load('FROZEN_SELECTION.json');rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()];chosen=sel['discovery_results'];ids=['baseline_B0_repeat_1','baseline_NATIVE_SCALAR_18']+chosen
derived=[]
for ident in dict.fromkeys(ids+[r['id'] for r in rows if r['id'].startswith(('V','verify'))]):
 m=load('reports/'+ident+'_MEASURED.json');directory=S/'source/results'/ident
 with np.load(directory/'trace.npz') as z:
  j=z['stage']=='TASK';t=z['time_s'][j];f=np.linalg.norm(z['physical_cuff_force_world_n'][j],axis=1);jf=float(f[:-1]@np.diff(t));mi=float(np.linalg.norm(z['physical_cuff_moment_world_nm'][j],axis=1)[:-1]@np.diff(t))
 with np.load(S/'motion_series'/(ident+'.npz')) as z:
  t=z['time_s'];q=z['true_q_rad'];v=z['true_dq_rad_s'];a=np.gradient(v,t,axis=0,edge_order=2);jerk=np.gradient(a,t,axis=0,edge_order=2);max_error=0.
  for sig,value in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',jerk)]:
   d=np.rad2deg(value);stats=dict(max_abs=np.max(abs(d),axis=0),p95_abs=np.quantile(abs(d),.95,axis=0),rms=np.sqrt(np.mean(d*d,axis=0)))
   for k,x in stats.items():max_error=max(max_error,float(np.max(abs(x-np.asarray(m['motion']['raw']['full'][sig][k])))))
  excursion=float(np.max(abs(np.rad2deg(np.ptp(q,axis=0))-np.asarray(m['dose']['excursion_deg']))))
 row=dict(id=ident,force_integral_error_N_s=jf-m['J_F_N_s'],moment_integral_error_Nm_s=mi-m['moment_integral_Nm_s'],dense_derivative_statistics_error=max_error,excursion_error_deg=excursion,phase_integral_closure_error_N_s=sum(x['J_F_N_s'] for x in m['phase_cost']['phases'].values())-m['J_F_N_s']);assert all(abs(row[k])<1e-8 for k in row if k!='id');derived.append(row)
put('INDEPENDENT_DERIVED_CHECKS.json',dict(status='PASS',rows=derived,raw_derivatives_no_filter_no_deleted_endpoints=True))
roots=load('preservation/GIT_BEFORE.json');after={}
for root,before in roots.items():
 r=Path(root)
 def g(*a):return subprocess.check_output(['git','-C',str(r),*a],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode()
 after[root]=dict(head=g('rev-parse','HEAD'),branch=g('branch','--show-current'),status=g('status','--porcelain=v1'),index=sha(r/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest(),unstaged=hashlib.sha256(g('diff','--binary').encode()).hexdigest())
 assert after[root]==before,'MAIN_GIT_CHANGED'
put('preservation/GIT_AFTER.json',after)
protected=load('preservation/REUSED_SOURCE_HASHES.json');changed=[p for p,h in protected.items() if sha(Path(p))!=h];assert not changed,'HISTORICAL_REUSED_FILE_CHANGED'
old=S.parent/'m2_lowforce_repair_explore_10h_v1';core_changed=[]
for d in ['source','deps','native','weights']:
 for p in (S/d).rglob('*'):
  if not p.is_file() or 'results' in p.relative_to(S).parts or '__pycache__' in p.parts:continue
  counterpart=old/p.relative_to(S)
  if not counterpart.exists():continue
  if p.suffix=='.py':equal=p.read_text().replace(str(S),str(old))==counterpart.read_text()
  else:equal=sha(p)==sha(counterpart)
  if not equal:core_changed.append(str(p))
assert not core_changed,'COPIED_B_CORE_OR_MODEL_CHANGED'
processes=subprocess.check_output(['ps','-eo','pid,ppid,args']).decode();live=[l for l in processes.splitlines() if 'sequential_runner.py' in l];assert not live,'PHYSICS_PROCESS_REMAINS'
starts=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(l)['event']=='START'];pre=[r for r in starts if not r.get('mode','').startswith(('V','verify'))];validation=[r for r in starts if r.get('mode','').startswith(('V','verify'))];assert len(starts)<=90 and len(pre)<=72
compute=[]
for p in (S/'output').glob('*_DATA.json'):
 x=json.loads(p.read_text());compute.append(dict(id=x['id'],complete=bool(x['metric']['task_valid']),actual_new_native_steps=x['metric']['actual_new_native_physics_steps'],actual_new_simulation_seconds=x['metric']['actual_new_simulation_seconds']))
for p in (S/'output').glob('*_PARTIAL_COMPUTE.json'):
 x=json.loads(p.read_text());compute.append(dict(id=p.name[:-21],complete=False,actual_new_native_steps=x.get('actual_new_native_physics_steps'),actual_new_simulation_seconds=x.get('actual_new_simulation_seconds')))
put('ACTUAL_PHYSICAL_WORK.json',dict(rows=compute,steps_lower_bound=sum(r['actual_new_native_steps'] or 0 for r in compute),sim_seconds_lower_bound=sum(r['actual_new_simulation_seconds'] or 0 for r in compute),inherited_prefix_not_double_counted=True,complete_attempts=sum(r['complete'] for r in compute),all_starts=len(starts)))
required=['REPORT.md','SEARCH_PROTOCOL.json','SEQUENTIAL_BRANCH_RESULTS.json','STRONG_MOTION_REPAIR.md','FORCE_MOTION_COMPARISON.json','OPTIONAL_TRAJECTORY_ORACLE.md','TEACHER_COORDINATION_INDEX.json','VALIDATION_RESULTS.json','PACKAGE_VERIFICATION.json'];assert all((S/n).exists() for n in required)
size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());assert size<6*2**30
end=time.time();assert end<P['hard_stop_unix'];assert all(r['unix']<=P['dispatch_cutoff_unix'] for r in starts)
V.update(status='PASS',final_unix=end,elapsed_s=end-P['t0_unix'],attempts=len(starts),prevalidation_attempts=len(pre),validation_repeat_attempts=len(validation),unused_reserved_validation_attempts=max(0,18-len(validation)),package_bytes=size,package_GiB=size/2**30,D_free_bytes=shutil.disk_usage('/mnt/d').free,all_physics_processes_exited=True,live_physics_processes=live,main_Git_exact_snapshot_equal=True,historical_protected_files_unchanged=not changed,copied_B_core_and_model_equal_except_absolute_relocation=True,independent_derived_checks='PASS',all_attempts_counted_including_failures=True,protocol_thresholds_unchanged=sha(S/'MOTION_ACCEPTANCE_PROTOCOL.json')==P['motion_protocol_sha256'],last_dispatch_unix=max(r['unix'] for r in starts),hard_deadline_remaining_after_last_dispatch_s=P['hard_stop_unix']-max(r['unix'] for r in starts),STOP=True)
assert V['all_started_attempts_have_end_or_failure'];put('PACKAGE_VERIFICATION.json',V)
put('PACKAGE_MANIFEST.json',{str(p.relative_to(S)):dict(size=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name!='PACKAGE_MANIFEST.json'})
mirror=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_sequential_teacher_oracle_v1_review');mirror.mkdir(exist_ok=True)
for n in required+['INDEPENDENT_DERIVED_CHECKS.json','ACTUAL_PHYSICAL_WORK.json','PACKAGE_MANIFEST.json','ATTEMPTS.jsonl','FROZEN_SELECTION.json','RETURN_DECISION_STATE_AUDIT.json']:
 shutil.copy2(S/n,mirror/n)
if (S/'figures').exists():shutil.copytree(S/'figures',mirror/'figures',dirs_exist_ok=True)
print(json.dumps(dict(status='PASS',attempts=len(starts),elapsed_min=V['elapsed_s']/60,package_GiB=V['package_GiB'],mirror=str(mirror))))
