from pathlib import Path
import json,subprocess,sys,time
r=Path(__file__).resolve().parents[1];plan=json.loads((r/'physical/EVALUATION_PLAN.json').read_text());out=[]
for case in plan['cases']:
 count=len(list((r/'physical/runtime/evaluations').glob('*/PHYSICS_START.json')))
 assert count<8,'PHYSICAL_BUDGET_EXHAUSTED'
 cmd=[sys.executable,str(r/'scripts/frozen_evaluation.py'),case['id']]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=360)
 logs=r/'physical'/f"{case['id']}.log";logs.write_text(p.stdout+'\nSTDERR\n'+p.stderr)
 status={'case':case,'returncode':p.returncode,'log':str(logs.relative_to(r))};out.append(status)
 (r/'physical/MANAGER_PROGRESS.json').write_text(json.dumps(out,indent=2))
 print(json.dumps(status),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
