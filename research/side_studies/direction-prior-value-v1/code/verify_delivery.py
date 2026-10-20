"""Seal wall time after closeout QA and verify every compact deliverable hash."""
from freeze import *
import re,fcntl
def main():
 handles=[]
 for name in ('runner.lock','controller.lock'):
  handle=(STUDY/name).open('a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(handle)
 final=json.loads((STUDY/'FINAL_STATUS.json').read_text());assert final['all_owned_workers_joined']
 source=json.loads((STUDY/'FINAL_SOURCE_VERIFICATION.json').read_text());assert source['main_git_state_equal'] and not source['original_sources_changed'] and not source['final_code_manifest_mismatches']
 ledger=json.loads((STUDY/'COMPUTE_LEDGER.json').read_text());assert ledger['summary']['physics_attempts']<=300 and ledger['summary']['ended']==ledger['summary']['physics_attempts']
 for name in ('final','independent','fresh','extra','tail'):
  path=STUDY/f'ANALYSIS_v2_{name}.json'
  if not path.exists():continue
  data=json.loads(path.read_text())
  for row in data['rows']:
   if not row['valid']:continue
   for key in ('J_F','force_peak','moment_integral','moment_peak','physical_clearance'):assert isinstance(row['metric'][key],(int,float)),(name,row['id'],key)
   assert row['tracking_evaluation_only_deg']['RMS_per_joint'] and row['decision_wall_s']
 unix=time.time();elapsed=unix-1791222386;assert elapsed<16*3600,'ORIGINAL_HARD_DEADLINE_EXCEEDED'
 ledger['summary']['elapsed_wall_s']=elapsed;ledger['summary']['wall_time_basis']='original campaign start through final delivery seal; includes closeout QA';save(STUDY/'COMPUTE_LEDGER.json',ledger)
 report=(STUDY/'REPORT.md').read_text();report=re.sub(r'累计墙钟 [0-9.]+ h',f'累计墙钟 {elapsed/3600:.3f} h',report,count=1);(STUDY/'REPORT.md').write_text(report)
 final.update(elapsed_hours=elapsed/3600,delivery_sealed_unix=unix,closeout_QA_included=True);save(STUDY/'FINAL_STATUS.json',final)
 dest=LOCAL/'deliverables'
 for root in STUDY.glob('weights_v*'):
  if not root.is_dir():continue
  training=json.loads((root/'TRAINING.json').read_text());assert sha(dest/root.name/'networks.npz')==training['weights_sha256']
 for name in ('REPORT.md','COMPUTE_LEDGER.json','FINAL_STATUS.json','STATE.json','PROGRESS.md','ROOT_PHASE.json','ROOT_PHASE_HISTORY.jsonl'):shutil.copy2(STUDY/name,dest/name)
 save(dest/'DELIVERY_VERIFICATION.json',dict(sealed_unix=unix,elapsed_hours=elapsed/3600,original_start_unix=1791222386,physics_attempts=ledger['summary']['physics_attempts'],all_attempts_ended=True,qualified_metric_fields_complete=True,main_source_verification=source['main_git_state_equal']))
 manifest={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file() and p.name!='MANIFEST.json'};save(dest/'MANIFEST.json',manifest)
 assert all(sha(dest/name)==expected for name,expected in manifest.items())
 assert set(manifest)=={str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file() and p.name!='MANIFEST.json'}
 print(json.dumps(dict(status='DELIVERY_HASHES_PASS',files=len(manifest),manifest_sha256=sha(dest/'MANIFEST.json'),elapsed_hours=elapsed/3600,physics_attempts=ledger['summary']['physics_attempts'])))
if __name__=='__main__':main()
