from pathlib import Path
import json, shutil, hashlib, time, subprocess
BASE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OLD=BASE/'m2_lowforce_repair_explore_10h_v1'
NEW=BASE/'m2_sequential_teacher_oracle_v1'
CTRL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_sequential_teacher_oracle_v1_control')
T0=1791872262.0 # first successful clock: 2026-10-13 14:17:42 +08
assert not NEW.exists(), 'new package must be independent'
NEW.mkdir()
for d in ['reports','logs','preservation','output','motion_series','queue']:(NEW/d).mkdir()
for d in ['source','deps','code','native','build','weights']:
 shutil.copytree(OLD/d,NEW/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for d in ['source','deps','code']:
 for p in (NEW/d).rglob('*.py'):
  txt=p.read_text();new=txt.replace(str(OLD),str(NEW))
  if new!=txt:p.write_text(new)
(NEW/'source/results').mkdir()
def put(n,x):(NEW/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['MOTION_ACCEPTANCE_PROTOCOL.json','TIMING_BASELINE.json']:shutil.copy2(OLD/n,NEW/n)
shutil.copy2(OLD/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',NEW/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
cat=json.loads((OLD/'CANDIDATE_CATALOG.json').read_text())['candidates'];lookup={c['id']:c for c in cat}
ids=['NATIVE_SCALAR_18','M2_fixed_actions','C2_pair_1_2','repair2_2_0']
put('CANDIDATE_CATALOG.json',dict(candidates=[lookup[i] for i in ids]))
P=dict(version='SEQUENTIAL_TEACHER_ORACLE_v1',t0_unix=T0,t0_local='2026-10-13T14:17:42+08:00',registered_unix=time.time(),hard_stop_unix=T0+10800,dispatch_cutoff_unix=T0+9000,search_cutoff_unix=T0+7200,physics_budget=90,search_cap=72,validation_reserved=18,seed=2026101201,clock='SCIENTIFIC_SIMULATION',search_bound=[-.2,.2],issued_slots_per_phase=5,milestones_percent=[2,5],motion_protocol_sha256=sha(NEW/'MOTION_ACCEPTANCE_PROTOCOL.json'),selection_rule='highest full-task gain with unchanged motion and physical gates; retain at most two diverse feasible leaders and one informative infeasible diagnostic; freeze before V',methods=['full-task OUTBOUND intervention','legal later-boundary live fork from replayed leader prefix','bounded suffix coordinate improvement','strong seed slot redistribution'],continuation='original B native physical segments; fixed registered PWL or frozen historical M2 reference',validation_conditions=[dict(name='V1',seed=2026101317,prefix={'RETURN':[[.025,.025,.025]]}),dict(name='V2',seed=2026101318,prefix={'RETURN':[[-.025,-.025,-.025]]})],validation_generation='existing legal shared RETURN slot0 K3 prefix, +/-0.005 graph; root at OUTBOUND0, all candidates share prefix; audit actual state at RETURN1, no synthetic state',stop_conditions=['parent mutation or fork mismatch','absolute safety or ownership failure','3 incomplete tasks per family','90 total starts,72 prevalidation','D free<40GiB','package>=6GiB','available memory<1GiB','150min no new physics','180min all children joined'],storage_target_GiB=4,storage_hard_GiB=6,truth_firewall='current causal observation/model/history logged separately; full future trajectory and J_F only offline teacher labels; no Q training',clinical_thresholds=False,optional_oracle='only if native stages insufficient and a reusable solver is available within reserved wall/attempt quota')
put('SEARCH_PROTOCOL.json',P);put('RUN_PLAN.json',P)
put('preservation/REUSED_SOURCE_HASHES.json',{str(p):sha(p) for d in ['source','deps','native','weights'] for p in (OLD/d).rglob('*') if p.is_file() and 'results' not in p.relative_to(OLD).parts and '__pycache__' not in p.parts})
roots=[BASE.parent/'adaptive-traction-mpc-learning',BASE.parent/'adaptive-traction-mpc-human-closeout-git']
def git(r):
 def g(*a):return subprocess.check_output(['git','-C',str(r),*a],env={'PATH':'/usr/bin:/bin','GIT_OPTIONAL_LOCKS':'0'}).decode()
 return dict(head=g('rev-parse','HEAD'),branch=g('branch','--show-current'),status=g('status','--porcelain=v1'),index=sha(r/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest(),unstaged=hashlib.sha256(g('diff','--binary').encode()).hexdigest())
put('preservation/GIT_BEFORE.json',{str(r):git(r) for r in roots})
shutil.copy2(CTRL/'runner.py',NEW/'code/sequential_runner.py')
put('INITIALIZED.json',dict(unix=time.time(),elapsed_s=time.time()-T0,old=str(OLD),new=str(NEW)))
print(json.dumps(dict(package=str(NEW),elapsed_s=time.time()-T0)))
