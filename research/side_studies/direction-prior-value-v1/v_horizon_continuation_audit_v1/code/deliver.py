from audit_common import *
import ast
def main():
 dest=LOCAL/'deliverables';dest.mkdir(exist_ok=True)
 for p in STUDY.iterdir():
  if p.is_file() and p.suffix in ('.md','.json','.jsonl','.csv','.png','.pdf'):shutil.copy2(p,dest/p.name)
 for name in ('code','deps','code_history'):
  shutil.copytree(STUDY/name,dest/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 # Copy compact output evidence, never duplicate all raw physics traces.
 out=dest/'output';out.mkdir(exist_ok=True)
 for p in (STUDY/'output').iterdir():
  if p.is_file() and p.suffix in ('.json','.jsonl','.log'):shutil.copy2(p,out/p.name)
 for name,h in read(STUDY/'AUDIT_CONTRACT.json')['weights_sha256'].items():
  p=Path(name);target=dest/'frozen_weights'/p.parent.name/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);assert sha(target)==h
 for p in LOCAL.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
 request=Path('/mnt/c/Users/HankL/.codex/attachments/e216524a-cdad-4af6-b075-2944f5431114/已粘贴的文本.txt');shutil.copy2(request,dest/'USER_REQUEST.txt')
 (dest/'README.md').write_text('Audit completed and stopped. REPORT.md contains the scientific verdict.\n\nThe compact delivery includes outcomes/search logs, frozen weights, actual harness, contracts and hashes. Large raw traces and the frozen runtime remain at:\n\n'+str(STUDY)+'\n\nOld read-only evidence remains at:\n\n'+str(OLD)+'\n\nThis is not a self-contained Windows runtime. Recorded harness paths require that preserved WSL study and Python environment. Do not run bootstrap/register/repair again. Read-only analysis can be rerun with the corresponding code/offline_audit.py, analyze_diagnostics.py, analyze_attribution.py, trace_pair_checks.py and event_clock_audit.py scripts; runner/worker are stopped and no additional physics is authorized by this delivery.\n',encoding='utf-8')
 manifest={str(p.relative_to(dest)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in dest.rglob('*') if p.is_file() and p.name!='DELIVERY_MANIFEST.json'};save(dest/'DELIVERY_MANIFEST.json',dict(unix=time.time(),files=manifest,total_bytes=sum(r['bytes'] for r in manifest.values())))
 assert all(sha(dest/name)==r['sha256'] for name,r in manifest.items());print(json.dumps(dict(delivery=str(dest),files=len(manifest),bytes=sum(r['bytes'] for r in manifest.values()),report_sha=sha(dest/'REPORT.md'))))
if __name__=='__main__':main()
