from pathlib import Path
import hashlib,json,shutil,time
P=Path(__file__).resolve().parents[1];OLD=P.parent/'force_mechanism_waypoint_v3';L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/force_mechanism_waypoint_v3')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
manifest=json.loads((OLD/'EXECUTION_CODE_MANIFEST.json').read_text());rows=[]
for name,key in [('CANDIDATE_PLAN.json','original_plan_sha256'),('EXECUTABLE_PLAN.json','executable_plan_sha256')]:
 source=L/name;assert source.exists()
 # Final execution manifest independently binds the preserved review mirror.
 print('RECOVERY_CANDIDATE',name,sha(source),manifest.get(key) if key else None)
 assert sha(source)==manifest[key]
 shutil.copy2(OLD/name,P/'audit'/('misdirected_'+name));shutil.copy2(source,OLD/name)
 rows.append(dict(file=name,restored_sha256=sha(OLD/name),mirror_sha256=sha(source)))
for name in ['audit/HISTORICAL_INPUTS.json','derived/HISTORICAL_WINDOWS.json','BASELINE_REPRODUCTION.json','HISTORICAL_18D_PARAMETERS.json']:
 assert not (L/name).exists(),'Do not remove a historical file'
 source=OLD/name;assert source.is_file();dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
 shutil.move(str(source),str(dest));rows.append(dict(new_misdirected_file_moved=name))
# Rebase literal package names too; these were missed by absolute-path-only migration.
changes=[]
for d in ['source','code','deps','tests','control']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml'] or f.name in ['prepare.py','repair_isolation.py']:continue
  try:s=f.read_text()
  except UnicodeError:continue
  t=s.replace("S/'force_mechanism_waypoint_v3'","S/'"+P.name+"'")
  if t!=s:f.write_text(t);changes.append(str(f.relative_to(P)))
# Registered design survived in the saved misdirected plans, restore to intended package.
for n in ['CANDIDATE_PLAN.json','EXECUTABLE_PLAN.json']:shutil.copy2(P/'audit'/('misdirected_'+n),P/n)
(P/'audit/ISOLATION_REPAIR.json').write_text(json.dumps(dict(unix=time.time(),physics_starts=0,incident='analysis helper retained literal old package name; old plan files restored from preserved mirror, newly created analysis files moved',recovered=rows,rebase=changes),indent=2))
print('REPAIRED',rows)
