"""One bounded pass of original scorer and independently rebuilt raw motion."""
import os,sys,json,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];os.environ['ACL2_PACKAGE']=str(P);sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'source'),str(P/'legacy_source')]
import acl2_scorer_replay as replay
from acl2_shared import put,records
rows=records();groups=set(sys.argv[1:]);count=0
for r in rows:
 if r['event']!='START' or (groups and r.get('group') not in groups):continue
 out=P/'audit/scorer_replay'/(r['id']+'.json')
 if out.exists():continue
 try:d=replay.replay(r['id'],r.get('group','UNKNOWN'))
 except BaseException as e:d={'id':r['id'],'status':'SCORER_REPLAY_ERROR','error':repr(e)}
 put('audit/scorer_replay/'+r['id']+'.json',d);count+=1;print(r['id'],d['status'],flush=True)
print('SUMMARY',replay.summary(),flush=True)
