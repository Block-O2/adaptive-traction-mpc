from audit_common import *
def main():
 while time.time()<START+6*3600:
  q={p.stem for p in (STUDY/'queue').glob('*.json')};p=STUDY/'TASK_LEDGER.json';ledger=read(p) if p.exists() else {}
  if q<=set(ledger) and all(r['status']!='RUNNING' for r in ledger.values()):
   (STUDY/'STOP_DISPATCH').touch();save(STUDY/'DISPATCH_COMPLETE.json',dict(unix=time.time(),queued=len(q),all_top_level_returned=True));print('REGISTERED_QUEUE_FINISHED',flush=True);return
  time.sleep(30)
 print('WATCH_DEADLINE_REACHED',flush=True)
if __name__=='__main__':main()
