from pathlib import Path
import sys,json
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');sys.path.insert(0,str(P/'control'))
from raw_audit_base import raw_audit
rows=[json.loads(x) for x in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()]
for r in rows:
 if r['status']=='COMPLETE' and not (P/'reports'/(r['id']+'_INDEPENDENT_AUDIT.json')).exists():raw_audit(r['id'])
print('PROGRESS_RAW_AUDIT_COMPLETE',sum(r['status']=='COMPLETE' for r in rows))
