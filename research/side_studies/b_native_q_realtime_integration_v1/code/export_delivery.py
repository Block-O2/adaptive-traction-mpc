"""Copy compact reviewable deliverables to the authorized Windows workspace."""
from task_bootstrap import *
def main():
 src=STUDY/'delivery';target=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery');target.mkdir(parents=True,exist_ok=True)
 entries=[]
 def copy(p,rel):
  dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest);entries.append(dict(relative_path=str(rel),sha256=sha(p),bytes=p.stat().st_size,raw_source=str(p)))
 for p in src.rglob('*'):
  if p.is_file() and p.name not in ('DELIVERY_EXPORT_MANIFEST.json','DELIVERY_MANIFEST.json','DELIVERY_VALIDATION.json'):copy(p,p.relative_to(src))
 for folder in ('reports','versions'):
  for p in sorted((STUDY/folder).glob('*.json')):
   if 'HISTORY_' not in p.name:copy(p,Path('evidence')/folder/p.name)
 for name in ('RUN_PLAN.json','TASK_LEDGER.json','AUDIT_TASK_LEDGER.json','CHECKPOINT.json','PROGRESS.md','RESUME.md','ATTEMPTS.jsonl','COMPUTE_LEDGER.jsonl','NONPHYSICS_JOBS.jsonl','CODE_MANIFEST.json','SOURCE.json','GIT_BEFORE.json','Q_STRUCTURE_AUDIT.json','USER_REQUEST.txt','TIMING_BASELINE.json','TIMING_PROFILE_00.json','TIMING_PROFILE_01.json','RUNNER_STOP.json','STOP_DISPATCH'):
  p=STUDY/name
  if p.exists():copy(p,Path('evidence')/name)
 for name in ('RESOURCE_LOG.jsonl','OFFLINE_RESOURCE_LOG.jsonl'):
  p=STUDY/'output'/name
  if p.exists():copy(p,Path('evidence')/name)
 evidence=STUDY/'reports/SOURCE_EVIDENCE_INDEX.json'
 if evidence.exists():
  for row in json.loads(evidence.read_text())['rows']:copy(Path(row['path']),Path('source')/Path(row['path']).name)
 for p in (STUDY/'code').glob('*.py'):copy(p,Path('code')/p.name)
 for p in sorted((STUDY/'output').glob('*_RESULT.json')):copy(p,Path('evidence/results')/p.name)
 for folder in ('queue','inputs'):
  for p in sorted((STUDY/folder).glob('*.json')):copy(p,Path('evidence')/folder/p.name)
 out=dict(status='COMPACT_VERIFIED_EXPORT',created_unix=time.time(),raw_WSL_study=str(STUDY),Windows_review_path='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery',raw_traces_remain_in_WSL=True,raw_trace_export=False,entries=entries,total_exported_bytes=sum(r['bytes'] for r in entries))
 save(target/'DELIVERY_MANIFEST.json',out);save(target/'DELIVERY_EXPORT_MANIFEST.json',out);save(src/'DELIVERY_EXPORT_MANIFEST.json',out);print(json.dumps(dict(status=out['status'],files=len(entries),bytes=out['total_exported_bytes'],Windows_review_path=out['Windows_review_path'])))
if __name__=='__main__':main()
