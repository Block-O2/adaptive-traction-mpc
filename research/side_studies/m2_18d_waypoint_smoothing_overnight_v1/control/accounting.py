"""Read-only attempt and resource accounting; writes only current package."""
from pathlib import Path
import json,time,hashlib,os
P=Path(__file__).resolve().parents[1]
def main():
 records=[json.loads(l) for l in (P/'ATTEMPTS.jsonl').read_text().splitlines()] if (P/'ATTEMPTS.jsonl').exists() else []
 starts=[r for r in records if r['event']=='START'];ends=[r for r in records if r['event']=='END'];assert len(set(r['id'] for r in starts))==len(starts)
 rows=[]
 for s in starts:
  e=next((e for e in ends if e['id']==s['id']),None);partial=P/'output'/(s['id']+'_PARTIAL_COMPUTE.json');data=P/'output'/(s['id']+'_DATA.json');result={}
  if data.exists():result=json.loads(data.read_text())['metric']
  elif partial.exists():result=json.loads(partial.read_text())
  steps=result.get('actual_new_native_physics_steps');failed=bool(e and e['returncode']!=0)
  rows.append(dict(id=s['id'],kind=s.get('kind'),start_unix=s['unix'],end_unix=None if e is None else e['unix'],returncode=None if e is None else e['returncode'],actual_new_native_steps=steps,partial=failed or (bool(e) and not result.get('task_valid',False)),failure_reason=None if e is None else e.get('error'),full_task=result.get('task_valid',False),joined=None if e is None else e.get('joined'),parent_hash_equal=None if e is None else e.get('parent_hash_equal')))
 owned=[]
 for f in Path('/proc').glob('[0-9]*/cmdline'):
  try:
   cmd=f.read_bytes().replace(b'\0',b' ').decode(errors='replace');pid=int(f.parent.name)
   if str(P/'control/campaign.py') in cmd and 'python' in cmd and pid!=os.getpid() and not cmd.startswith(('bash ','sh ')):owned.append(dict(pid=pid,command=cmd))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 output=dict(updated_unix=time.time(),physical_START=len(starts),physical_END=len(ends),cap=120,development_cap=90,validation_reserve=30,remaining_total=120-len(starts),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows),native_steps_exact=all(r['actual_new_native_steps'] is not None for r in rows),active_owned=owned,package_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()),rows=rows)
 (P/'ATTEMPT_ACCOUNTING.json').write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps({k:output[k] for k in ['physical_START','physical_END','actual_new_native_steps','native_steps_exact','package_bytes','active_owned']}))
if __name__=='__main__':main()
