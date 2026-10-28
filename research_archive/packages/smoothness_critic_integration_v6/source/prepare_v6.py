from pathlib import Path
import json,shutil,hashlib,datetime
V=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');P=Path('/tmp/ihear_v6_path').read_text().strip();P=Path(P);R=P/'runtime'
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
changes=[]
for sub in ['code','control','deps','source/stages']:
 shutil.copytree(V/'runtime'/sub,R/sub,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for sub in ['source/results','output','reports','motion_series','tmp/mpl']:(R/sub).mkdir(parents=True,exist_ok=True)
for sub in ['owned','history','attempts','predictions','experiments']:(P/sub).mkdir(exist_ok=True)
for f in (V/'runtime').glob('*.json'):
 if 'TEST_PLAN' not in f.name: shutil.copy2(f,R/f.name)
shutil.copy2(V/'runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json',R/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for f in (V/'source').glob('*.py'):shutil.copy2(f,P/'source'/f.name)
for base in [R,P/'source']:
 for f in base.rglob('*.py'):
  old=f.read_text();new=old.replace(str(V/'runtime'),str(R))
  if base==P/'source':new=new.replace("get('ACL2_PACKAGE','"+str(V)+"')","get('ACL2_PACKAGE','"+str(P)+"')")
  if old!=new:
   f.write_text(new);changes.append({'file':str(f.relative_to(P)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'change':'absolute runtime root relocation only'})
a=json.loads((P/'ACTIVATION.json').read_text());a['id']=a['activation_id'];a['t0_unix']=a['T0_unix'];put('ACTIVATION.json',a)
d=a['hard_stop_unix'];plan={'t0_unix':a['T0_unix'],'hard_stop_unix':d,'physics_hard_stop_unix':d-900,'dispatch_cutoff_unix':d-1500,'validation_dispatch_cutoff_unix':d-1500,'no_new_physics_after_unix':d-1500,'physical_timeout_s':420,'physics_budget':150,'native_step_cap':15000000,'development_cap':100,'seed':2026102601,'all_physics_serial':True,'min_ram_gib':6,'min_disk_gib':18,'allocation':'finite hypothesis-led menus; no obligation to exhaust cap'};put('runtime/RUN_PLAN.json',plan)
put('audit/CLOSURE_RELOCATION.json',{'origin':str(V),'origin_manifest_sha256':hashlib.sha256((V/'OUTPUT_MANIFEST.json').read_bytes()).hexdigest(),'changes':changes,'plant_guard_scorer_change':'none except root relocation','no_hardlinks':True})
put('audit/EXECUTION_ENVIRONMENT.json',{'python':'/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python','same_versions_as_v5':{'numpy':'2.2.6','scipy':'1.15.3','mujoco':'3.10.0','gymnasium':'1.1.1'},'unused_v6_venv_bootstrap':'created before exact v5 environment located; not used for results'})
(P/'source/prepare_v6.py').write_text(Path(__file__).read_text())
print('SETUP_READY',P,'path relocations',len(changes),flush=True)
