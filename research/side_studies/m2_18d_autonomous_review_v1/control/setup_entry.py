from pathlib import Path
import shutil,subprocess,sys
LOCAL=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/LOCAL.name
assert (P/'STATE.json').exists(), 'Bootstrap must finish first'
for f in (LOCAL/'control').glob('*.py'):
 if f.name!='bootstrap.py':shutil.copy2(f,P/'control'/f.name)
for name in ['prepare.py','audit_history.py','preflight.py']:
 subprocess.run([sys.executable,'-B',str(P/'control'/name)],cwd=P,check=True)
