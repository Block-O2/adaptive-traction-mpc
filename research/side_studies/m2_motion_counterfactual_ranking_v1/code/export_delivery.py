from common import *
import shutil
from datetime import datetime,timezone,timedelta
WIN=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_motion_counterfactual_ranking_v1')
assert WIN.parent==Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
assert OUT.name==WIN.name and OUT.name=='m2_motion_counterfactual_ranking_v1'
assert load(OUT/'PACKAGE_VERIFICATION.json')['status']=='PASS'
shutil.copytree(OUT,WIN,dirs_exist_ok=True)
bad=[];copied=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file():
  target=WIN/p.relative_to(OUT)
  if not target.is_file() or sha(target)!=sha(p):bad.append(str(p.relative_to(OUT)))
  copied.append(dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size))
assert not bad,bad
process=subprocess.run(['ps','-eo','pid,ppid,etimes,args'],capture_output=True,text=True).stdout
active=[s for s in process.splitlines() if str(OUT) in s and 'python' in s and str(os.getpid()) not in s and 'bash -lc' not in s]
assert not active,active
save('PROCESS_EXIT_CONFIRMATION.json',dict(other_task_workers=active,physics_workers_started=0,audit_commands_joined=True,exporter_exits_immediately_after_delivery=True,process_inventory=process,created_unix=time.time()))
save('DELIVERY_VERIFICATION.json',dict(status='PASS',canonical=str(OUT),windows='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_motion_counterfactual_ranking_v1',files_byte_compared=len(copied),bytes_byte_compared=sum(r['bytes'] for r in copied),mismatches=bad,meaning='Export byte identity only, not scientific promotion. Final metadata is copied after generation.'))
closed=load(OUT/'PACKAGE_CLOSED.json');closed.update(status='CLOSED',closed_local=datetime.now(timezone(timedelta(hours=8))).isoformat(),elapsed_wall_min=(time.time()-load(OUT/'EXPERIMENT_PROTOCOL.json')['start_unix'])/60,windows_export_verified=True,other_task_processes=0);save('PACKAGE_CLOSED.json',closed)
save('FULL_PACKAGE_MANIFEST.json',dict(files=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['FULL_PACKAGE_MANIFEST.json','PACKAGE_CLOSED.json']]))
for name in ['PROCESS_EXIT_CONFIRMATION.json','DELIVERY_VERIFICATION.json','PACKAGE_CLOSED.json','FULL_PACKAGE_MANIFEST.json']:
 shutil.copy2(OUT/name,WIN/name);assert sha(OUT/name)==sha(WIN/name)
print('DELIVERY_VERIFIED',len(copied),'elapsed_wall_min',closed['elapsed_wall_min'],flush=True)
