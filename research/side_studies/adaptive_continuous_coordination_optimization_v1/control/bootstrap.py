from pathlib import Path
import shutil,json,time,hashlib,subprocess
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_continuous_coordination_optimization_v1')
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1')
P=OLD.parent/LOCAL.name
assert not P.exists(), 'Never overwrite a campaign'
P.mkdir()
for d in ['control','reports','figures','motion_series','output','logs','tmp','audit']:(P/d).mkdir()
for d in ['code','deps','weights','source']:
 shutil.copytree(OLD/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for f in (P/'code').glob('*.py'):
 text=f.read_text();text=text.replace(str(OLD),str(P));f.write_text(text)
for n in ['MOTION_ACCEPTANCE_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json']:
 shutil.copy2(OLD/n,P/n)
shutil.copy2(OLD/'control/physical_runner.py',P/'control/interface_base.py')
shutil.copy2(OLD/'control/audit_physics.py',P/'control/raw_audit_base.py')
for f in (LOCAL/'control').glob('*.py'):
 if f.name!='bootstrap.py':shutil.copy2(f,P/'control'/f.name)
t=time.time()
plan=dict(t0_unix=t,hard_stop_unix=t+3600,physics_hard_stop_unix=t+3300,dispatch_cutoff_unix=t+2700,physical_timeout_s=240,physics_budget=28,seed=2026101303,clock='SCIENTIFIC_SIMULATION',hypotheses=['H1 force-motion window association','H2 bounded smoothing force sensitivity','H3 density controllability','H4 density penalties'],development='one complete forked parent seed 2026101303',validation='conditional frozen primary vs paired B, legal prefix conditions; never reselect',inputs='original estimated state and commissioned belief; offline archived truth diagnosis only',hidden='native Human state evaluation only',gate='unchanged MOTION_ACCEPTANCE_PROTOCOL plus full task/safety/receipt; force ranking only full feasible runs',stop='60 min wall / 28 START / 3-5 uninformative failures per direction',no_training=True,no_production_writes=True)
(P/'RUN_PLAN.json').write_text(json.dumps(plan,indent=2))
git=Path('/home/hank/coding/adaptive-traction-mpc-learning')
state={k:subprocess.check_output(['git','-C',str(git),*args],text=True) for k,args in [('branch',['branch','--show-current']),('HEAD',['rev-parse','HEAD']),('status',['status','--short'])]}
(P/'audit/INITIAL_GIT_STATE.json').write_text(json.dumps(state,indent=2))
manifest={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for d in ['source','code','deps','weights'] for f in (P/d).rglob('*') if f.is_file()}
(P/'audit/INITIAL_SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
(P/'STATE.json').write_text(json.dumps(dict(status='DIAGNOSTICS',physics_starts=0,plan=plan)))
print(json.dumps(dict(package=str(P),files=len(manifest),plan=plan)))
