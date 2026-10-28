"""Read-only package verifier. Run python -B VERIFY_PACKAGE.py [package]."""
from pathlib import Path
import json,hashlib,sys,re
P=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
m=json.loads((P/'OUTPUT_MANIFEST.json').read_text());bad=[]
for rel,entry in m['files'].items():
 p=P/rel
 if not p.is_file() or p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:bad.append(rel)
v=json.loads((P/'PACKAGE_VERIFICATION.json').read_text());end=json.loads((P/'END.json').read_text());a=json.loads((P/'ACTIVATION.json').read_text())
actual={str(p.relative_to(P)) for p in P.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and '.git' not in p.parts}
extra=actual-set(m['files'])-set(m['excluded_self_referential_seal_files'])
assert not extra,sorted(extra)[:20]
assert not bad,bad[:20]
assert v['status']=='PASS' and v['manifest_sha256']==sha(P/'OUTPUT_MANIFEST.json')
assert end['state']=='STOP' and end['activation_id']==a['id'] and end['T0_unix']==a['t0_unix'] and end['hard_stop_unix']==a['hard_stop_unix']
assert end['package_verification_sha256']==sha(P/'PACKAGE_VERIFICATION.json') and end['output_manifest_sha256']==sha(P/'OUTPUT_MANIFEST.json')
assert end['ended_unix']<=a['hard_stop_unix'] and end['active_owned_processes']==0
assert end['physical_START']==end['physical_END'] and end['no_automatic_next_round']
assert not end['new_PPO_training_episodes'] and end['true_physical_attempt_savings']==0
for doc in P.glob('*.md'):
 for target in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',doc.read_text()):
  target=target.strip().strip('<>')
  if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):continue
  target=target.split('#',1)[0]
  assert (doc.parent/target).exists(),(doc.name,target)
print(json.dumps(dict(status='PASS',manifest_files=len(m['files']),bytes=sum(x['bytes'] for x in m['files'].values()),activation_id=a['id'],elapsed_hours=end['elapsed_seconds']/3600,physical_START=end['physical_START'],new_native_steps=end['actual_new_native_steps'],state=end['state']),ensure_ascii=False))
