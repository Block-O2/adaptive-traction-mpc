from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
i=sys.argv[1]
for suffix in ('RESULT','FAULT_INJECTION','ADMISSION_CERTIFICATES'):
 p=S/'output'/(i+'_'+suffix+'.json')
 if p.exists():print(suffix,p.read_text()[:5500])
p=S/'output'/(i+'_MULTIRATE.json')
if p.exists():
 m=json.loads(p.read_text());print('REQUESTS',json.dumps(m['native_requests'],indent=2)[:14000])
p=S/'source/results'/i/'runtime_artifacts.json.gz'
if p.exists():
 for r in array_items(p,'command_receipts'):
  if r.get('apply_ns') is not None:print('RECEIPT',json.dumps(r,indent=2)[:5500]);break
