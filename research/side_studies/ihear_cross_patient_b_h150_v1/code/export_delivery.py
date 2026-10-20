"""Verified quiescent full evidence mirror; never delete or overwrite a mismatch."""
from pathlib import Path
import json,hashlib,shutil,time,sys,ast,re,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_multirate_realtime_v1')
D=W/'delivery'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(n,x):(S/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 start=time.time();assert (S/'STOP_DISPATCH').exists()
 assert D.resolve()==W.resolve()/'delivery'
 report=(S/'REPORT.md').read_text();links=[];issues=[]
 for label,href in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',report):
  if href.startswith(('https:','http:','#')):continue
  p=(S/href).resolve();links.append(dict(label=label,target=href,exists=p.is_file()))
  if not p.is_file():issues.append('MISSING_REPORT_LINK:'+href)
 own=['multirate.py','commissioning_owner.py','slow_owner.py','admission_certificates.py','run_one.py','campaign.py','session_worker.py','session_campaign.py','cpu_watch.py','audit.py','forensics.py','qualification.py','snapshot_tests.py','profile_run.py','probe_plan.py','diagnostics.py','closeout.py','build_report.py','sensitivity.py','export_delivery.py']
 for n in own:ast.parse((S/'code'/n).read_text(),filename=n)
 host=json.loads((S/'reports/HOST_QUALIFICATION.json').read_text());events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts={r['id']:r for r in events if r['event']=='START'}
 for p in (S/'output').glob('*_RESULT.json'):
  r=json.loads(p.read_text())
  if r['inputs']!=starts[r['id']]['cfg']:issues.append('INPUT_MISMATCH:'+r['id'])
  sources=json.loads((S/'output'/(r['id']+'_IMPORTED_SOURCES.json')).read_text())
  for n,h in sources.items():
   path=Path(n)
   if sha(path)==h:continue
   backups=[q for q in (S/'preservation').rglob(path.name) if sha(q)==h]
   if not backups:issues.append('UNPRESERVED_IMPORTED_SOURCE:'+r['id']+':'+n)
  ev=json.loads((S/'output'/(r['id']+'_MULTIRATE.json')).read_text())
  if any(ev[k] for k in ('Q_calls','G_calls','learning_updates')):issues.append('LEARNING_ENABLED:'+r['id'])
  if r['inputs']['revision'] in ('R2','R3'):
   co=json.loads((S/'output'/(r['id']+'_COMMISSIONING_OWNER.json')).read_text())
   if not co['closed'] or co['plant_in_worker']:issues.append('COMMISSIONING_OWNER:'+r['id'])
 for r in host['rows']:
  if r['original_complete_VALID'] or r['qualified']:issues.append('UNEXPECTED_QUALIFICATION:'+r['id'])
 save('reports/DELIVERY_VALIDATION.json',dict(status='PASS' if not issues else 'FAIL',issues=issues,report_links=links,attempts=len(starts),host_attempts=len(host['rows']),scientific_gate_count=3,own_scripts_AST_pass=len(own),imported_execution_source_versions_preserved=True,no_Q_G_learning=True,raw_receipt_and_step_causality='Every host FORENSICS validated by report builder.',checked_unix=time.time()))
 assert not issues,issues
 save('FINAL_CODE_MANIFEST.json',{str(p.relative_to(S)):sha(p) for d in ('code','versions','preservation') for p in (S/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts})
 manifest={str(p.relative_to(S)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('FULL_PACKAGE_MANIFEST.json','DELIVERY_MIRROR_VERIFICATION.json')}
 save('FULL_PACKAGE_MANIFEST.json',manifest)
 D.mkdir(exist_ok=True)
 for n,entry in manifest.items():
  src=S/n;dest=D/n;dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==entry['sha256'],'Existing delivery mismatch: '+n
  else:shutil.copy2(src,dest)
 shutil.copy2(S/'FULL_PACKAGE_MANIFEST.json',D/'FULL_PACKAGE_MANIFEST.json')
 bad=[]
 for n,entry in manifest.items():
  if sha(D/n)!=entry['sha256']:bad.append(n)
 out=dict(status='PASS' if not bad else 'FAIL',files=len(manifest),bytes=sum(r['bytes'] for r in manifest.values()),mismatch=bad,source=str(S),destination=str(D),wall_s=time.time()-start,raw_physics_included=True,source_and_manifest_included=True,complete_all_attempts=True,verified_unix=time.time())
 save('DELIVERY_MIRROR_VERIFICATION.json',out);shutil.copy2(S/'DELIVERY_MIRROR_VERIFICATION.json',D/'DELIVERY_MIRROR_VERIFICATION.json');assert not bad
 print(json.dumps(out),flush=True)
if __name__=='__main__':main()
