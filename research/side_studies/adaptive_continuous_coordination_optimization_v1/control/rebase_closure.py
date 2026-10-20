from pathlib import Path
import json
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');old=str(P.parent/'adaptive_continuous_coordination_interface_v1');changed=[]
for d in ['source','deps']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if old in s:f.write_text(s.replace(old,str(P)));changed.append(str(f.relative_to(P)))
(P/'audit/PATH_REBASE.json').write_text(json.dumps(dict(reason='Copied sac_env and operational_memory absolute paths inserted original closure before new source. No physical START occurred. Rebase path strings only.',files=changed),indent=2));print('REBASED',len(changed))
