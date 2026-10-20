"""Lightweight monitoring of both existing campaign process trees; no dispatch."""
from runner import sample,STUDY
import time,json
def main():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text())
 while time.time()<cfg['deadline_unix'] and not (STUDY/'STOP_MONITOR').exists():
  start=time.time();sample(filename='RESOURCES_ALL_PROCESS_TREES.jsonl')
  while time.time()<start+45 and not (STUDY/'STOP_MONITOR').exists():time.sleep(1)
 print('ALL_PROCESS_RESOURCE_MONITOR_JOINED',flush=True)
if __name__=='__main__':main()
