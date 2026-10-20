"""Rescore actual saved wall trajectories; no physical attempt is repeated."""
from study_common import *
from task_bootstrap import save as write
import mode_metadata
import gzip

def main():
 mode_metadata.install();case,_=load_case_options();rows=[]
 for p in sorted((STUDY/'queue').glob('070_v1_wall_*.json')):
  req=json.loads(p.read_text());r=json.loads(Path(req['result_path']).read_text());folder=O/req['id'];summary=json.loads((folder/'summary.json').read_text());assert summary['execution_mode']=='REALTIME_CHARACTERIZATION'
  before={name:sha(folder/name) for name in ('trace.npz','runtime_artifacts.json.gz')}
  meta=folder/'HIGH_ROM_CASE_RESULT.json';old=folder/'HIGH_ROM_CASE_RESULT.original_metadata_error.json'
  if meta.exists() and not old.exists():shutil.copy2(meta,old)
  env=types.SimpleNamespace(episode_dir=folder,summary=summary,case=case,host_start=time.monotonic()-r['wall_seconds'],rejections=0,action_records=[])
  # Restore the losslessly archived scalar/runtime evidence for the original
  # evaluator, which accepts only its original JSON filename. No history is
  # expanded into additional samples and no physics is repeated.
  raw=folder/'runtime_artifacts.json';restored=not raw.exists()
  if restored:
   with gzip.open(folder/'runtime_artifacts.json.gz','rb') as src,raw.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
   restored_sha=sha(raw)
  try:
   m=r2.metric(env,req['id'],'MATCHED');m.pop('raw_actions',None)
  finally:
   if restored:
    assert sha(raw)==restored_sha,'RESCORE_CHANGED_RESTORED_EVIDENCE'
    assert sha(folder/'runtime_artifacts.json.gz')==before['runtime_artifacts.json.gz']
    raw.unlink()
  assert all(sha(folder/name)==h for name,h in before.items()),'RESCORE_CHANGED_RAW_EVIDENCE'
  out=dict(id=req['id'],status='RESCORED_EXISTING_EXECUTION',metric=m,inputs=req,original_worker_status=r['status'],original_error=r.get('error'),physics_attempts_added=0,source_sha256=before,metadata_only_repair=True,P_full_performance_calls=0)
  save(req['id']+'_RESCORED_RESULT.json',out);rows.append(dict(id=req['id'],valid=m['valid'],status=m['status'],abort_reason=summary.get('abort_reason'),J_F_unranked=m['J_F']))
 write(STUDY/'WALL_RESCORE_v1.json',dict(rows=rows,added_physics_attempts=0,original_failed_results_retained=True,classification='raw actual host-clock execution, corrected mode metadata, unchanged full evaluator'))
 print(json.dumps(rows))
if __name__=='__main__':main()
