from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');ident=sys.argv[1]
d=json.loads((S/'output'/(ident+'_ADMISSION_CERTIFICATES.json')).read_text())
print(json.dumps(d,indent=2)[:14000])
