"""One finite independent raw/scorer replay batch; never reads active outcomes."""
from pathlib import Path
import os,sys,json,time,signal,hashlib
P=Path(__file__).resolve().parents[1]
os.environ.update(ACL2_PACKAGE=str(P),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path[:0]=[str(P/'source'),str(P/'runtime/code'),str(P/'runtime/control')]
import v7_scorer_replay_v2 as replay
from acl2_shared import put,records
started=time.time();signal.alarm(1200)
identity=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),started_unix=started,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),groups=sys.argv[1:])
name='RAW_REPLAY_'+str(time.time_ns());put('owned/'+name+'_START.json',identity)
rows=[]
try:
 for group in sys.argv[1:]:
  end=json.loads((P/'owned'/(group+'_SUPERVISOR_END.json')).read_text())
  assert end['state']=='STOP' and not end['survivors'],'NEVER_REPLAY_ACTIVE_JOB'
  events=records();ended={r['id'] for r in events if r['event']=='END'}
  for row in events:
   if row['event']!='START' or row.get('group')!=group:continue
   assert row['id'] in ended,'MISSING_END'
   out=P/'audit/scorer_replay'/(row['id']+'.json')
   if out.exists():continue
   result=replay.replay(row['id'],group);put('audit/scorer_replay/'+row['id']+'.json',result);rows.append(result)
   print('RAW_REPLAY',row['id'],result['status'],flush=True)
 summary=replay.summary()
 put('owned/'+name+'_END.json',dict(**identity,ended_unix=time.time(),status='PASS' if summary['status']=='PASS' else 'REVIEW_REQUIRED',rows=len(rows)))
 assert summary['status']=='PASS','RAW_SCORER_REPLAY_MISMATCH'
except BaseException as error:
 put('owned/'+name+'_END.json',dict(**identity,ended_unix=time.time(),status='FAILED_PRESERVED',error=str(error)));raise
