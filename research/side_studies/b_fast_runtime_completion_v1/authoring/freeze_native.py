from pathlib import Path
import json,hashlib,shutil,sys,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
version=sys.argv[1];dest=S/'versions'/version
assert not dest.exists(),dest
dest.mkdir()
files=list((S/'build').glob('fast_native*.so'))+[S/'native/fast_native.cpp',S/'native/build_native.py',S/'code/native_interface_adapter.py',S/'code/native_vectors.py']
for p in files:shutil.copy2(p,dest/p.name)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file()}
(dest/'MANIFEST.json').write_text(json.dumps(dict(version=version,unix=time.time(),files=manifest),indent=2)+'\n')
print('FROZEN',version)
