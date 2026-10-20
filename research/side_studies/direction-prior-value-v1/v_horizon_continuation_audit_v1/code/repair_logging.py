from audit_common import *
import fcntl
def main():
 handle=(STUDY/'runner.lock').open('a');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
 history=STUDY/'code_history/logging_adapter_v0';history.mkdir(parents=True,exist_ok=True)
 for name in ('audit_physics.py','worker.py','CODE_MANIFEST.json'):
  source=STUDY/name if name=='CODE_MANIFEST.json' else STUDY/'code'/name
  if not (history/name).exists():shutil.copy2(source,history/name)
 sys.path.insert(0,str(STUDY/'code'));from accounting import record,rows
 data=rows();ended={r['id'] for r in data if r['event']=='END'}
 for row in data:
  if row['event']=='START' and row['id'] not in ended:record('END',row['id'],status='INTERRUPTED_LOGGING_ADAPTER_REPAIR',owner_joined=True)
 old=read(STUDY/'queue/010_state_0_normal.json');old['id']='009_state_0_normal_logging_retry1';old['result_path']=str(STUDY/'output'/(old['id']+'_RESULT.json'));old['retry_of']='010_state_0_normal'
 save(STUDY/'queue'/(old['id']+'.json'),old)
 save(STUDY/'LOGGING_REPAIR.json',dict(unix=time.time(),reason='missing branch_output_dir attribute required by unchanged native runtime at line3257',fix='initialize None; set unique child output_dir on fork before first native return',changes_scientific_semantics=False,old_source_archive=str(history),all_failed_attempts_retained=True,budget_not_reset=True))
 (STUDY/'STOP_DISPATCH').unlink()
 print(json.dumps(dict(status='LOGGING_ONLY_REPAIR_REGISTERED',prior_attempts=sum(r['event']=='START' for r in data))))
if __name__=='__main__':main()
