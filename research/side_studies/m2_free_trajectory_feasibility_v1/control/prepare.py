from pathlib import Path
import json, shutil, hashlib, subprocess, time
BASE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OLD=BASE/'m2_sequential_teacher_oracle_v1'
NEW=BASE/'m2_free_trajectory_feasibility_v1'
CTRL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control')
T0=1791889117.0
assert not NEW.exists(), 'Never overwrite a study'
NEW.mkdir()
for d in ['reports','logs','preservation','output','motion_series','queue','control']: (NEW/d).mkdir()
for d in ['source','code','deps','build','native','weights']:
    shutil.copytree(OLD/d,NEW/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for d in ['source','code','deps']:
    for p in (NEW/d).rglob('*.py'):
        txt=p.read_text(); replaced=txt.replace(str(OLD),str(NEW))
        if txt!=replaced:p.write_text(replaced)
(NEW/'source/results').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,x):(NEW/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
for name in ['MOTION_ACCEPTANCE_PROTOCOL.json','TIMING_BASELINE.json','CANDIDATE_CATALOG.json']:
    shutil.copy2(OLD/name,NEW/name)
for name in ['SHARED_COORDINATION_ACTION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json']:
    shutil.copy2(OLD/'output'/name,NEW/'output'/name)
roots=[BASE.parent/'adaptive-traction-mpc-learning',BASE.parent/'adaptive-traction-mpc-human-closeout-git']
def git(r):
    def g(*a):return subprocess.check_output(['git','-C',str(r),*a],env={'PATH':'/usr/bin:/bin','GIT_OPTIONAL_LOCKS':'0'}).decode()
    return dict(head=g('rev-parse','HEAD'),branch=g('branch','--show-current'),status=g('status','--porcelain=v1'),index=sha(r/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest(),unstaged=hashlib.sha256(g('diff','--binary').encode()).hexdigest())
put('preservation/GIT_BEFORE.json',{str(r):git(r) for r in roots})
put('preservation/REUSED_SOURCE_HASHES.json',{str(p):sha(p) for d in ['source','code','deps','build','native','weights'] for p in (OLD/d).rglob('*') if p.is_file() and 'results' not in p.parts and '__pycache__' not in p.parts})
protocol=dict(version='FREE_TRAJECTORY_FEASIBILITY_v1',question='Can independent waypoint progress and pass-through velocities improve full-task force with unchanged dynamics and motion gates?',registered_unix=time.time(),t0_unix=T0,hard_stop_unix=T0+14400,dispatch_cutoff_unix=T0+12600,search_cutoff_unix=T0+10800,physics_budget=96,search_cap=84,validation_reserved=12,seed=2026101303,clock='SCIENTIFIC_SIMULATION',motion_protocol_sha256=sha(NEW/'MOTION_ACCEPTANCE_PROTOCOL.json'),storage_target_GiB=4,storage_hard_GiB=8,baseline_cap=12,initial_cap=16,main_cap=40,repair_cap=16,parameter_names=['O_common','O_diff_constant','O_diff_tilt','O_velocity_common','O_velocity_diff','R_common','R_diff_constant','R_diff_tilt','R_velocity_common','R_velocity_diff'],parameter_scales=[.015,.025,.025,.20,.20]*2,normalized_bounds=[-1.,1.],parameterization='At current original nominal waypoint m: envelope sin(pi*m)^2; add common + differential polynomial to normalized targets; multiply existing bounded hip/knee pass-through velocity by 1+envelope*(vcommon +/- vdiff). Original piecewise quintic determines continuous q/dq/ddq. Endpoint and HOLD exactly untouched. No arbitrary continuous raw-v2 PWL claim.',methods=['axis probes','bounded COBYLA with measured full-task constraints and cache','multi-seed targeted repair'],seed_families=['B0','NATIVE_SCALAR_18','M2_fixed_actions','C2_pair_1_2'],baseline='zero extension must exactly repeat original B and matched historical B before optimization',tracking='actual human q minus actually receipt-owned generalized reference; same original task goals/boundaries/dose plus unchanged physical tracking condition; phase shape independent diagnostic',validation_conditions=[dict(name='W1',seed=2026101319,prefix={'RETURN':[[.018,.018,.018]]}),dict(name='W2',seed=2026101320,prefix={'RETURN':[[-.018,-.018,-.018]]})],validation='Two new same-Human legal RETURN0 prefix conditions; fork after physical prefix at RETURN1. Compare complete paired tasks; audit actual q/dq difference. Prefix consumes native slot0, so report remaining frozen suffix rather than independent original full action sequence. No validation feedback into selection.',selection='highest full-task gain passing original absolute safety, complete task, ownership and ALL frozen motion/dose/tracking/compensation gates; freeze before held-out; no minimum manufactured gain',truth_firewall='fixed offline parameters; current native request state only in planner; future trace only in offline objective and diagnosis; no learning',stop_conditions=['absolute safety fail','unknown ownership','parent mutation','integral closure fail','D free <40GiB','study >=8GiB','available memory <1GiB','96 attempts','dispatch after t0+3.5h','hard wall t0+4h'],levels={'0':'MATHEMATICAL_CANDIDATE','1':'DYNAMICS_FEASIBLE only after all task/safety/motion gates','2':'NATIVE_B_EXECUTABLE only unextended original interface','3':'HOST_CLOCK_VALIDATED not run'},clinical_thresholds=False)
put('TRAJECTORY_OPTIMIZATION_PROTOCOL.json',protocol);put('SEARCH_PROTOCOL.json',protocol);put('RUN_PLAN.json',protocol)
for name in ['free_planner.py','runner.py']:
    shutil.copy2(CTRL/name,NEW/'code'/name)
put('INITIALIZED.json',dict(unix=time.time(),package=str(NEW),elapsed_s=time.time()-T0))
print(json.dumps(dict(package=str(NEW),elapsed_s=time.time()-T0)))
