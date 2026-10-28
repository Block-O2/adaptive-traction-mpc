"""Isolate the verified v6 closure. No historical file is modified or hardlinked."""
from pathlib import Path
import json,shutil,hashlib,time
P=Path(__file__).resolve().parents[1]; V=P.parent/'smoothness_critic_integration_v6';R=P/'runtime'
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
a=json.loads((P/'ACTIVATION.json').read_text());assert a['state']=='RUNNING'
assert not (P/'audit/CLOSURE_RELOCATION.json').exists(),'ALREADY_PREPARED'
original={};changes=[]
for sub in ['code','control','deps','source/stages']:
 shutil.copytree(V/'runtime'/sub,R/sub,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for sub in ['source/results','output','reports','motion_series','tmp/mpl']:(R/sub).mkdir(parents=True,exist_ok=True)
for f in (V/'source').glob('*.py'):
 if f.name not in ['prepare_v7.py']:shutil.copy2(f,P/'source'/f.name)
for n in ['ACTION_SET.json','FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json']:
 shutil.copy2(V/'runtime'/n,R/n)
shutil.copy2(V/'runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json',R/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for base in [R,P/'source']:
 for f in base.rglob('*'):
  if not f.is_file():continue
  rel=f.relative_to(P);old_origin=V/rel
  if old_origin.exists():original[str(old_origin)]=sha(old_origin)
  if f.suffix!='.py':continue
  old=f.read_text();new=old.replace(str(V/'runtime'),str(R))
  if base==P/'source':new=new.replace("get('ACL2_PACKAGE','"+str(V)+"')","get('ACL2_PACKAGE','"+str(P)+"')")
  if new!=old:
   f.write_text(new);changes.append({'file':str(rel),'before':hashlib.sha256(old.encode()).hexdigest(),'after':sha(f),'change':'absolute runtime/package default relocation'})
# aliases match inherited readers; the original activation time is not changed.
a.update(id=a['activation_id'],hard_stop_unix=a['deadline_unix'],t0_unix=a['T0_unix']);put('ACTIVATION.json',a)
d=a['deadline_unix'];plan={'t0_unix':a['T0_unix'],'hard_stop_unix':d,'physics_hard_stop_unix':d,'dispatch_cutoff_unix':d,'validation_dispatch_cutoff_unix':d,'no_new_physics_after_unix':d,'physical_timeout_s':600,'seed':2026102701,'all_physics_serial':True,'min_ram_gib':6,'min_disk_gib':20,'fixed_global_attempt_cap':None,'fixed_global_native_step_cap':None,'allocation':'Per-branch finite registered menus; dynamic hypothesis-driven continuation until scientific or safety stop or hard deadline','closeout_reserve_s':1800}
put('runtime/RUN_PLAN.json',plan)
put('audit/CLOSURE_RELOCATION.json',{'origin':str(V),'origin_manifest_sha256':sha(V/'OUTPUT_MANIFEST.json'),'changes':changes,'plant_guard_scorer_change':'none except runtime absolute path relocation','no_hardlinks':True})
put('audit/PROTECTED_EXECUTION_INPUTS.json',{'created_unix':time.time(),'files':original,'scope':'All copied historical source/deps/config assets; historical models/raw additionally bound by historical manifests'})
put('audit/EXECUTION_ENVIRONMENT.json',{'python':'/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python','versions_expected':{'numpy':'2.2.6','scipy':'1.15.3','mujoco':'3.10.0','gymnasium':'1.1.1'}})
print('PREPARED',P,'protected',len(original),'path_relocations',len(changes))
