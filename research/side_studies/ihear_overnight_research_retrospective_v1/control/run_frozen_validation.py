"""Foreground serial orchestration; every phase owns and joins its children."""
from pathlib import Path
import json,subprocess,sys,time
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path']);P=json.loads((S/'RUN_PLAN.json').read_text())
assert json.loads((S/'development_repair2_DONE.json').read_text())['all_children_joined']
assert json.loads((S/'control/LAUNCH_development_repair2.json').read_text())['outer_joined']
subprocess.run([sys.executable,str(W/'pin_freeze.py')],check=True)
for mode in ['repeat','V1','V2','V3','V4']:
    assert time.time()<P['dispatch_cutoff_unix']-600,'VALIDATION_DISPATCH_DEADLINE'
    assert not (S/(mode+'_DONE.json')).exists(),'DO_NOT_REPEAT_ALREADY_COMPLETED_PHASE'
    result=subprocess.run([sys.executable,str(W/'launch_phase.py'),mode])
    record=dict(mode=mode,unix=time.time(),returncode=result.returncode)
    with (S/'control/FROZEN_VALIDATION_SEQUENCE.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
    if mode.startswith('V'):
        subprocess.run([sys.executable,str(W/'analyze_overnight.py')],check=True)
        subprocess.run([sys.executable,str(W/'analyze_validation.py')],check=True)
        validation=json.loads((S/'VALIDATION_RESULTS.json').read_text())
        if any(r['status']!='PASS' for r in validation['pre_intervention_negative_controls']):
            raise SystemExit('STOP_NEW_PHYSICS_CAUSAL_AUDIT_FAILURE')
print('FROZEN_VALIDATION_SEQUENCE_COMPLETE',flush=True)
