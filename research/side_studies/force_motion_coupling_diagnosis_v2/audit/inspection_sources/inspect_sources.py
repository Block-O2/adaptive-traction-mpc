from pathlib import Path
import json
import numpy as np

S = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
P = S / 'adaptive_continuous_coordination_optimization_v1'
for name in ['CANDIDATE_PLAN.json', 'PHYSICAL_ARM_RESULTS.json', 'NEW_PHYSICAL_DIAGNOSTICS.json', 'CANDIDATE_RESULTS.jsonl']:
    f = P / name
    x = json.loads(f.read_text().splitlines()[0]) if f.suffix == '.jsonl' else json.loads(f.read_text())
    print(name, str(x)[:6500])
for ident in ['development_B0', 'development_legacy005']:
    run = P / 'source/results' / ident
    print('FILES', ident, [(f.name, f.stat().st_size) for f in run.iterdir()])
    for f in [run / 'trace.npz', P / 'motion_series' / (ident + '.npz')]:
        z = np.load(f)
        print('ARRAYS', str(f), {k: (z[k].shape, str(z[k].dtype)) for k in z.files})
    summary = json.loads((run / 'summary.json').read_text())
    print('SUMMARY_KEYS', list(summary))
    print('TASK', str(summary['task'])[:3000])
    print('DECISION', str(summary['decisions'][1])[:7000])
print('motion_files', [f.name for f in (P / 'motion_series').glob('*.npz')])
