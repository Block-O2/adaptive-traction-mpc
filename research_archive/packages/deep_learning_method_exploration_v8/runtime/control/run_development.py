"""Serial owner; no new work after failure/deadline; test parents require model freeze."""
from pathlib import Path
import os,sys,json,subprocess,time
P=Path(__file__).resolve().parents[1]
if str(P).startswith('/mnt/c/'):
    P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/P.name
groups=sys.argv[1:]
for group in groups:
    if (P/(group+'_DONE.json')).exists():raise RuntimeError('Never silently rerun completed group')
    cfg=json.loads((P/(group+'_PLAN.json')).read_text())
    if cfg['condition']['split']=='test':assert (P/'models/VALUE_FREEZE.json').exists(),'TEST_BEFORE_MODEL_FREEZE'
    mode='validation' if cfg['condition']['split']=='test' else 'development'
    print('DISPATCH_GROUP',group,time.time(),flush=True)
    r=subprocess.run([sys.executable,'-B',str(P/'control/owner_v2.py'),group,mode],cwd=P)
    if r.returncode:raise SystemExit(r.returncode)
    print('CLOSED_GROUP',group,time.time(),flush=True)
