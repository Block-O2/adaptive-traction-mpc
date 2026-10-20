from pathlib import Path
import json, numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
D=S/'force_motion_coupling_diagnosis_v2'
for name in ['B0','18D']:
 z=np.load(D/'series'/f'{name}.npz')
 print('SERIES',name,{k:list(z[k].shape) for k in z.files})
rec=json.loads((D/'RAW_DERIVED_METRICS.json').read_text())['cases']
for r in rec:
 if r['label'] not in ['B0','18D']:continue
 print('REC',r['label'],r['source_root'],r['archive_case'])
 p=Path(r['source_root'])/'source/results'/r['archive_case']
 z=np.load(p/'trace.npz');print('TRACE_FIELDS',r['label'],{k:list(z[k].shape) for k in z.files})
 su=json.loads((p/'summary.json').read_text());print('SUMMARY_KEYS',list(su));print('DECISION_KEYS',list(su['decisions'][2]));print('LR',str(su['learning_records'][2])[:2400])
f=json.loads((D/'provenance/18D_FROZEN_SELECTION.json').read_text());print('18D_BEST',f['best']['candidate'])
O=S/'adaptive_continuous_coordination_optimization_v1'
for file in ['code/study_common.py','code/matched_harness.py','control/rebase_closure.py']:
 print('CODE',file);s=(O/file).read_text();print(s[:18000])
