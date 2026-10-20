from pathlib import Path
import sys,importlib.util,json,time,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
spec=importlib.util.spec_from_file_location('independent_arithmetic',P/'control/independent_recompute.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
ids=sys.argv[1:] or [r['id'] for r in events if r['event']=='END' and r['returncode']==0]
checks=[]
for ident in ids:
 assert any(r['event']=='END' and r['id']==ident and r['returncode']==0 for r in events)
 dest=P/'derived'/(ident+'_INDEPENDENT.json')
 if dest.exists():
  record=json.loads(dest.read_text());assert record['status']=='PASS'
  metric=json.loads((P/'reports'/(ident+'_MEASURED.json')).read_text())
  for name,h in metric['sources'].items():assert mod.sha(Path(name))==h
 else:record=mod.measure(ident)
 checks.append(record)
bad=[n for n in sys.modules if 'mujoco' in n or 'planner' in n or n in ['study_common','campaign','sac_env','runner']];assert not bad,bad
out=dict(status='PASS',unix=time.time(),checks=checks,imports_physics_or_controller=False,scope='separate arithmetic implementation: original raw complete/phase force and moment, native derivatives/dose/ROM boundaries, tracking, receipt torque and unique native step ownership, source SHA; one agent, not independent person/agent',new_physical_starts=0)
(P/'audit/INDEPENDENT_VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n')
print('INDEPENDENT_PASS',len(checks),flush=True)
