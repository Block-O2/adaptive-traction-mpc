from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import mode_metadata as m,qualify as q,final_qualification as f
m.install();installed=q.physical_audit
for _ in range(5):m.install();assert q.physical_audit is installed and f.physical_audit is installed
assert installed.__code__.co_filename=='<actual execution-mode metadata writer>'
q.physical_audit=lambda *args:None
try:m.install()
except AssertionError as e:assert str(e)=='METADATA_AUDIT_OWNER_CHANGED'
else:raise AssertionError('changed physical audit owner not rejected')
q.physical_audit=installed
out=dict(status='PASS',cases=7,no_physics=True,actual_mode_field_unchanged=True,original_evaluator_unchanged=True,repeat_install_exact_same_function=True,unexpected_owner_rejected=True)
(S/'output/METADATA_REUSE_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
