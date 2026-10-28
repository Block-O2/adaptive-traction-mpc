from pathlib import Path
import json,shutil,time
from v6_data import group
P=Path(__file__).resolve().parents[1]
assert (P/'jobs/TRAIN_DATA_V2_DONE.json').exists()
for g in ['DEV_O1']+json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups']:
 old=P/'data'/f'{g}.json';arc=P/'data/pre_guard_history24'/f'{g}.json'
 if old.exists() and not arc.exists():arc.parent.mkdir(exist_ok=True);shutil.copy2(old,arc)
 r=group(g,wrench=True);assert all(len(x['history_risk_features'])==24 for x in r);print('RECOLLECTED',g,flush=True)
(P/'jobs/TRAIN_DATA_V3_DONE.json').write_text(json.dumps(dict(unix=time.time())))
