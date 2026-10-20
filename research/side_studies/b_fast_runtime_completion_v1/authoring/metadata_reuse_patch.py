from pathlib import Path
import shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
p=S/'code/mode_metadata.py';text=p.read_text()
if 'INSTALLED_AUDIT=None' not in text:
 shutil.copy2(p,S/'versions/REUSE_MODE_METADATA_NEGATIVE.py')
 text=text.replace('def install():','INSTALLED_AUDIT=None\n\ndef install():\n global INSTALLED_AUDIT')
 anchor=' import final_qualification as f\n'
 assert text.count(anchor)==1
 text=text.replace(anchor,anchor+" if INSTALLED_AUDIT is not None:\n  assert q.physical_audit is INSTALLED_AUDIT and f.physical_audit is INSTALLED_AUDIT,'METADATA_AUDIT_OWNER_CHANGED'\n  return\n")
 anchor=" q.physical_audit=f.physical_audit=namespace['physical_audit']"
 assert text.count(anchor)==1
 text=text.replace(anchor,anchor+"\n INSTALLED_AUDIT=q.physical_audit")
 p.write_text(text)
print('S2_METADATA_IDEMPOTENCE_PATCHED')
