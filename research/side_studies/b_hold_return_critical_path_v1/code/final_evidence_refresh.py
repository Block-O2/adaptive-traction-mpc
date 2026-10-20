"""Bounded joined read-only refresh after the last registered physics attempt."""
from task_bootstrap import *
def main():
 scripts=['host_qualification_summary.py','request_timing_reconciliation.py','host_failure_forensics.py','admission_headroom_audit.py','native_count_authority_audit.py','frozen_selection_integrity.py','suffix_label_audit.py','source_closure_audit.py','retain_actor_sources.py','source_evidence_index.py','make_source_guide.py','activation_chain_components.py','native_wall_utilization.py','audit_compute_reconciliation.py']
 rows=[]
 for index,name in enumerate(scripts):
  start=time.time();p=STUDY/'code'/name;log=STUDY/'output'/('FINAL_REFRESH_'+name+'.log')
  with log.open('w') as f:code=subprocess.call([sys.executable,str(p)],stdout=f,stderr=subprocess.STDOUT)
  row=dict(id='FINAL_REFRESH_'+name,kind='OFFLINE_NO_PHYSICS',start_unix=start,end_unix=time.time(),wall_seconds=time.time()-start,source_sha256=sha(p),returncode=code,physics_attempts=0,log_path=str(log));rows.append(row)
  with (STUDY/'NONPHYSICS_JOBS.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  print(json.dumps(dict(script=name,returncode=code,wall_seconds=row['wall_seconds'],index=index+1,total=len(scripts))),flush=True)
  assert code==0,log.read_text()[-4000:]
 prior=STUDY/'reports/RAW_PHYSICS_PROVENANCE_AUDIT.json'
 if prior.exists():shutil.copy2(prior,STUDY/'reports'/('RAW_PHYSICS_PROVENANCE_HISTORY_'+sha(prior)+'.json'))
 save(STUDY/'reports/FINAL_REFRESH_STATUS.json',dict(status='JOINED',rows=rows,physics_added=0))
if __name__=='__main__':main()
