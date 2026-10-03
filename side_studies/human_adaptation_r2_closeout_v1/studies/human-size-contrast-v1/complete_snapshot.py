from pathlib import Path
import ast,json,hashlib,subprocess
W=Path('<SIDE_STUDIES_ROOT>/human-size-contrast-v1');R=Path('<PRIMARY_REPOSITORY>');F=W/'snapshot';S='stages/stage5_personalized_motion_learning/';C='41cdddef117caa4b191a52129c4ff83e481fd5a8'
def sha(b):return hashlib.sha256(b).hexdigest()
m=json.loads((W/'SOURCE_PROVENANCE.json').read_text());finger=json.loads((R/S/'docs/adaptive_human_online_interface_v1/SOURCE_FINGERPRINTS.json').read_text());tree=subprocess.check_output(['git','-C',str(R),'ls-tree','-r','--name-only',C],text=True).splitlines()
names=set()
for p in F.rglob('*.py'):
 for n in ast.walk(ast.parse(p.read_bytes())):
  if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith('.json'):names.add(Path(n.value).name)
for p in sorted(set(tree)|set(finger)):
 if ('/configs/' in p and Path(p).name in names) or (p.endswith('_prefix_native.cpython-310-x86_64-linux-gnu.so')) or p=='stages/stage3_full3d/models/ur10e_torque.xml':
  if p in m['files']:continue
  if p in finger:
   b=(R/p).read_bytes();assert sha(b)==finger[p];assert b==(R/p).read_bytes();via='verified_1544_file_manifest'
  else:b=subprocess.check_output(['git','-C',str(R),'show',C+':'+p]);via='git_object:'+C
  q=F/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);m['files'][p]={'sha256':sha(b),'bytes':len(b),'provenance':via}
# The prior campaign contract was created after the fingerprint; use as provenance
# evidence only, not as executable snapshot input. Our own frozen CONTRACT replaces it.
m.setdefault('non_executable_evidence_missing_from_original_manifest',m.get('missing',[]));m['missing']=[]
m['snapshot_bytes']=sum(x['bytes'] for x in m['files'].values());(W/'SOURCE_PROVENANCE.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps({'files':len(m['files']),'bytes':m['snapshot_bytes'],'names':sorted(names)}))
