"""Queue one real capture after branch slot frees and frozen models exist."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from research_campaign import D,C

if __name__=='__main__':
 while True:
  branches=D/'ONE_STEP_BRANCH_RESULTS.json';gate=D/'OFFLINE_MODEL_PROMOTION_GATE.json'
  if branches.exists() and len(json.loads(branches.read_text()))==135 and gate.exists():break
  if datetime.now(timezone.utc)>=datetime.fromisoformat(C['hard_deadline_utc']):
   raise RuntimeError('deadline reached before actual model capture prerequisites')
  time.sleep(20)
 subprocess.run([sys.executable,str(Path(__file__).with_name('collect_latency_capture.py'))],check=True)
