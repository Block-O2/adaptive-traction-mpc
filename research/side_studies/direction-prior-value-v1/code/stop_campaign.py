"""Request clean shutdown only after every started physical attempt has ended."""
from freeze import *
def main():
 events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts={r['id'] for r in events if r['event']=='START'};ends={r['id'] for r in events if r['event']=='END'}
 assert starts<=ends and len(starts)<=300,'ACTIVE_PHYSICS_OR_BUDGET_ERROR'
 for name in ('STOP_DISPATCH','STOP_CONTROLLER','STOP_MONITOR'):(STUDY/name).touch()
 save(STUDY/'SHUTDOWN_REQUEST.json',dict(unix=time.time(),physics_attempts=len(starts),all_attempt_events_ended=True,method='clean stop markers; no signals or unknown-process kills'))
 print('CLEAN_SHUTDOWN_REQUESTED')
if __name__=='__main__':main()
