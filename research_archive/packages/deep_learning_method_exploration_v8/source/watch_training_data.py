from pathlib import Path
import json,time,sys
from v6_data import group
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());groups=['DEV_O1']+json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups'];done=[]
for g in groups:
 while not (P/'jobs'/g/'WORKER_DONE.json').exists():
  if time.time()>A['hard_stop_unix']-4500:raise TimeoutError('DATA_WATCH_RESERVE')
  time.sleep(3)
 status=json.loads((P/'jobs'/g/'WORKER_DONE.json').read_text());assert status['status'].startswith('PASS'),status
 rows=group(g,wrench=True);menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];half=[r for r in rows if r['horizon_s']==.5 and r['tag'] in menu];one=[r for r in rows if r['horizon_s']==1. and r['tag'] in menu];valid=[r for r in half if r['qualified']]
 s=min(half,key=lambda x:x['labels']['short_JF']);l=min(one,key=lambda x:x['labels']['short_JF']);f=min(valid,key=lambda x:x['labels']['full_remaining_JF'])
 row={'group':g,'half':s['tag'],'one':l['tag'],'full_qualified':f['tag'],'half_qualified':s['qualified'],'one_qualified':l['qualified'],'half_regret_N_s':s['labels']['full_remaining_JF']-f['labels']['full_remaining_JF'] if s['qualified'] else None,'fixed_compose_regret_N_s':next(r for r in valid if r['tag']=='COMPOSE')['labels']['full_remaining_JF']-f['labels']['full_remaining_JF'] if any(r['tag']=='COMPOSE' for r in valid) else None,'full_failures':[r['id'] for r in half if not r['qualified']]};done.append(row)
 (P/'analysis/TRAINING_DECISION_GAP.json').write_text(json.dumps(done,indent=2)+'\n');print('GAP',json.dumps(row),flush=True)
