"""Audit registered offline intervals/source bytes; do not add them to elapsed."""
from task_bootstrap import *
from collections import Counter
import math

def union(intervals):
 out=[]
 for a,b in sorted(intervals):
  if not out or a>out[-1][1]:out.append([a,b])
  else:out[-1][1]=max(out[-1][1],b)
 return out

def main():
 ledger=STUDY/'NONPHYSICS_JOBS.jsonl';rows=[json.loads(x) for x in ledger.read_text().splitlines() if x.strip()];wanted={r['source_sha256'] for r in rows};retained={};issues=[];now=time.time()
 paths=list((STUDY/'code').glob('*.py'))+list((STUDY/'code_history').glob('*/code/*.py'))
 for p in paths:
  digest=sha(p)
  if digest in wanted and digest not in retained:retained[digest]=str(p)
 reviewed=[]
 for index,r in enumerate(rows,1):
  errors=[];a=r['start_unix'];b=r['end_unix'];wall=r['wall_seconds']
  if not all(math.isfinite(v) for v in (a,b,wall)) or not START<=a<=b<=now+1 or wall<0 or abs(wall-(b-a))>.05:errors.append('WALL_INTERVAL')
  if r['kind']!='OFFLINE_NO_PHYSICS' or r['physics_attempts']!=0:errors.append('OFFLINE_COUNT_SCOPE')
  if r['source_sha256'] not in retained:errors.append('SOURCE_BYTES_NOT_RETAINED')
  if r.get('log_path') and not Path(r['log_path']).is_file():errors.append('REGISTERED_LOG_MISSING')
  if errors:issues.append(dict(ordinal=index,id=r['id'],issues=errors))
  reviewed.append(dict(ordinal=index,id=r['id'],returncode=r['returncode'],start_unix=a,end_unix=b,wall_seconds=wall,declared_source_sha256=r['source_sha256'],retained_declared_source=retained.get(r['source_sha256'])))
 intervals=union([(r['start_unix'],r['end_unix']) for r in rows]);counts=Counter(r['id'] for r in rows)
 out=dict(status='PASS_REGISTERED_OFFLINE_LEDGER' if not issues else 'FAIL',created_unix=time.time(),rows=reviewed,registered_offline_rows=len(rows),recorded_nonzero_return_rows=[dict(ordinal=i+1,id=r['id'],returncode=r['returncode']) for i,r in enumerate(rows) if r['returncode']!=0],repeated_ids={k:v for k,v in counts.items() if v>1},declared_source_variants=len(wanted),retained_source_variants=len(retained),sum_inclusive_wall_seconds=sum(r['wall_seconds'] for r in rows),union_registered_offline_wall_seconds=sum(b-a for a,b in intervals),issues=issues,ledger_sha256=sha(ledger),scope='Only registered offline jobs. Direct report/read-only maintenance helpers may be represented by final export/source manifests without a separate job row. Declared source SHA is recorded by the original wrapper at completion, not a module import-time attestation. Repeated ids, if present, retain append-only ordinal and timestamps. Nonzero returncodes are preserved negative evidence, not silently rewritten as success. Offline durations may overlap physics owners or one another; neither their sum nor union is added to package elapsed.',physics_attempts_added=0)
 save(STUDY/'reports/NONPHYSICS_LEDGER_CLOSURE.json',out);print(json.dumps({k:v for k,v in out.items() if k not in ('rows','scope')}));assert not issues
if __name__=='__main__':main()
