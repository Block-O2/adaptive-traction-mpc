"""Preserve failed nonphysics preflight; complete path-only rebasing in the new copy."""
from pathlib import Path
import json,shutil,time
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'ihear_model_terminal_compensation_v1';audit=P/'audit/preflight_attempt1'
audit.mkdir(exist_ok=False)
assert not (P/'ATTEMPTS.jsonl').exists()
for f in [P/'control/prepare_campaign.py',P/'control/bootstrap.py',P/'ACTION_SET.json',P/'SPLIT_REGISTRATION.json',P/'LEARNING_PROTOCOL.json']:
    shutil.copy2(f,audit/f.name)
rebased=[]
for folder in ['source','code','deps','weights']:
    for f in (P/folder).rglob('*'):
        if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml']:continue
        try:s=f.read_text()
        except UnicodeDecodeError:continue
        if str(A) in s:f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
(audit/'FAILURE_AND_REPAIR.json').write_text(json.dumps(dict(status='NONPHYSICS_PREFLIGHT_FAILED_AND_REPAIRED',unix=time.time(),original_failure='isolation path equality: source/.../adaptive_human_online_interface_v1/bootstrap.py',cause='bootstrap filename exclusion was overly broad; comparison also needed text newline normalization for rebased files',repair='only new copied closure paths rebased; identity comparator reproduces original read_text/write_text transformation',files=rebased,physics_starts=0,scientific_parameters_changed=False),indent=2)+'\n')
shutil.copy2(R/'control/repair_preflight.py',P/'control/repair_preflight.py')
print('PREFLIGHT_REPAIR',len(rebased),flush=True)
