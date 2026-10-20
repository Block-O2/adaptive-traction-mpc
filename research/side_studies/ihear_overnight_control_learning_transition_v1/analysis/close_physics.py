"""Close the campaign only after all owned launchers have exited."""
from pathlib import Path
import os,json,time,fcntl
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
for name in ['CONTINUATION','LEARNING_PIPELINE','REPETITION_PIPELINE']:
    assert (P/'audit'/(name+'_EXIT.json')).exists(),name
if (P/'REPETITION_RETRY_PROTOCOL.json').exists():assert json.loads((P/'REPETITION_RETRY_OWNER.json').read_text())['joined']
rs=[json.loads(s) for s in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
starts=[r['id'] for r in rs if r['event']=='START'];ends=[r['id'] for r in rs if r['event']=='END'];assert sorted(starts)==sorted(ends)
handles=[]
for name in ['OWNER.lock','PHYSICS.lock']:
    h=(P/name).open('a');fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(h)
for name in ['PHYSICS_STOP_v2.json','PHYSICS_STOP_v3.json','PHYSICS_STOP_v4.json','PHYSICS_STOP_v5.json','PHYSICS_STOP_v6.json']:
    if not (P/name).exists():put(name,dict(reason='FINAL_RESEARCH_STOP',unix=time.time()))
put('STOP_MONITOR.json',dict(reason='FINAL_STOP',unix=time.time()))
put('STOP_ANALYSIS.json',dict(reason='FINAL_STOP',unix=time.time()))
put('PHYSICS_CLOSED.json',dict(status='CLOSED',unix=time.time(),starts=len(starts),ends=len(ends),physics_and_owner_locks_exclusive=True,P2_training_started=False,new_studies_forbidden=True))
put('STATE.json',dict(phase='FINAL_AUDIT_NO_NEW_PHYSICS',physics_starts=len(starts),physics_ends=len(ends),unix=time.time()))
print('PHYSICS_CLOSED',len(starts),'START_END_PAIRS',flush=True)
