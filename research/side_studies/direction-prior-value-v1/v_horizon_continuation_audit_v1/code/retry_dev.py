from freeze import *
import sys,os
sys.path.insert(0,str(STUDY/'code'))
from accounting import record
def main():
 oldname='011_parent_dev_0';name=oldname+'_retry1';events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ends={r['id'] for r in events if r['event']=='END'}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except (OSError,UnicodeError):continue
  assert not (str(STUDY/'queue'/(oldname+'.json')) in cmd and str(STUDY/'code/worker.py') in cmd),'DEV_WORKER_STILL_ACTIVE'
 for event in events:
  if event['event']=='START' and event['id'].startswith('parent_dev_0_') and event['id'] not in ends:record('END',event['id'],status='FAILED_FORK_HASH',reason='dead original development parent; mismatch preserved in original RESULT/log, explicit retry retains completed prefix labels')
 old=STUDY/'queue'/(oldname+'.json');request=json.loads(old.read_text());request.update(id=name,resume_of=oldname,result_path=str(STUDY/'output'/(name+'_RESULT.json')),original_input_sha256=sha(old),seed=2026100600);assert not (STUDY/'queue'/(name+'.json')).exists();save(STUDY/'queue'/(name+'.json'),request);print(name)
if __name__=='__main__':main()
