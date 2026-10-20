from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');i=sys.argv[1]
m=json.loads((S/'output'/(i+'_MULTIRATE.json')).read_text());print('LAST_REQUESTS',json.dumps(m['native_requests'][-2:],indent=2))
ipc=json.loads((S/'output'/(i+'_DIRECT_IPC.json')).read_text());print('IPC',json.dumps(ipc,indent=2))
rt=json.loads((S/'output'/(i+'_RESULT.json')).read_text());print('RESULT_STATUS',rt['status'],rt.get('error'),rt.get('metric',{}).get('phase_durations'))
s=S/'source/results'/i/'summary.json'
if s.exists():print('SUMMARY_ABORT',json.loads(s.read_text()).get('abort_reason'))
