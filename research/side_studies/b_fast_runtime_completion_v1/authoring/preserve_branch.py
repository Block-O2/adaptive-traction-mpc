from pathlib import Path
import sys,shutil,json,hashlib,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
name=sys.argv[1];paths=sys.argv[2:];dest=S/'versions'/name;assert not dest.exists();dest.mkdir()
manifest={}
for rel in paths:
 p=S/rel;assert p.is_file() and p.resolve().is_relative_to(S);out=dest/p.name;assert not out.exists();shutil.copy2(p,out);manifest[p.name]=dict(original=str(p),sha256=hashlib.sha256(out.read_bytes()).hexdigest())
(dest/'MANIFEST.json').write_text(json.dumps(dict(unix=time.time(),files=manifest),indent=2)+'\n');print('PRESERVED',name)
