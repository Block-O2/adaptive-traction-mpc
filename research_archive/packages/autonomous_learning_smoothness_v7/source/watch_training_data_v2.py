from pathlib import Path
import json,time,os,sys,shutil
from v6_data import group
P=Path(__file__).resolve().parents[1];a=json.loads((P/'ACTIVATION.json').read_text());groups=['DEV_O1']+json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups'];done=[]
(P/'owned/DATA_WATCH_V2_START.json').write_text(json.dumps(dict(pid=os.getpid(),unix=time.time())))
try:
 for g in groups:
  while not (P/'jobs'/g/'WORKER_DONE.json').exists():
   assert time.time()<a['hard_stop_unix']-2400-4500
   time.sleep(3)
  old=P/'data'/f'{g}.json';archive=P/'data/pre_whole_history'/f'{g}.json'
  if old.exists() and not archive.exists():archive.parent.mkdir(exist_ok=True);shutil.copy2(old,archive)
  rows=group(g,wrench=True);menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];h=[r for r in rows if r['horizon_s']==.5 and r['tag'] in menu];one=[r for r in rows if r['horizon_s']==1. and r['tag'] in menu];valid=[r for r in h if r['qualified']];s=min(h,key=lambda r:r['labels']['short_JF']);l=min(one,key=lambda r:r['labels']['short_JF']);best=min(valid,key=lambda r:r['labels']['full_remaining_JF']) if valid else None;compose=next(r for r in h if r['tag']=='COMPOSE')
  row=dict(group=g,half=s['tag'],one=l['tag'],full_qualified=None if best is None else best['tag'],half_qualified=s['qualified'],one_qualified=l['qualified'],half_regret_N_s=s['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'] if s['qualified'] and best is not None else None,fixed_compose_regret_N_s=compose['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'] if compose['qualified'] and best is not None else None,full_failures=[r['id'] for r in h if not r['qualified']],no_original_qualified_candidate=not valid);done.append(row)
  (P/'analysis/TRAINING_DECISION_GAP.json').write_text(json.dumps(done,indent=2)+'\n');print('GAP_V2',json.dumps(row),flush=True)
 (P/'jobs/TRAIN_DATA_V2_DONE.json').write_text(json.dumps(dict(groups=groups,unix=time.time())))
finally:(P/'owned/DATA_WATCH_V2_END.json').write_text(json.dumps(dict(pid=os.getpid(),unix=time.time())))
