"""Independent final development review. No physics or optimizer calls."""
from pathlib import Path
import json,sys,importlib.util
from research_common import ROOT,RUNTIME,read,atomic,sha,now
sys.path.insert(0,str(RUNTIME))
from cloud_case_audit import audit
from force_audit import audit as force
from native_boundary_motion_audit import audit as motion
from checkpoints import contract
from motion_metrics import metrics

def main():
 rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (ROOT/'ALL_ATTEMPTS.jsonl').exists() else []
 records=[]
 for row in rows:
  if row['mode']!='evaluation':continue
  run=Path(row['run']);a=audit(run);f=force(run/'env/episode_0001');m=motion(run);mm=metrics(run)
  assert abs(mm['JF']-row['JF'])<1e-7 and abs(mm['JM']-row['JM'])<1e-7
  records.append(dict(run=str(run),pass_=a['pass'] and f['pass'] and m['pass'],JF=mm['JF'],JM=mm['JM'],integral_scope=mm['integral_scope']))
 ledger=read(ROOT/'LEDGER.json');checks=dict(all_attempts_settled=all(x['settled'] for x in ledger['attempts']),native_sum=ledger['native_steps']==sum(x['native_steps'] for x in ledger['attempts']),all_frozen_raw_audits=all(x['pass_'] for x in records),contract_unchanged=contract()==read(ROOT/'ACTIVATION.json')['contract_sha256'])
 atomic(ROOT/'INDEPENDENT_SAVED_REVIEW.json',dict(time_utc=now(),checks=checks,pass_=all(checks.values()),evaluations=records,G4_STRICT_PASS='FAIL',NEW_LIVE_MATCHED_READY='NOT_READY',STAGE2_READY='NOT_READY',FINAL_CAMPAIGN_READY='NOT_READY'))
 print(json.dumps(dict(checks=checks,evaluations=len(records))));assert all(checks.values())

if __name__=='__main__':main()
