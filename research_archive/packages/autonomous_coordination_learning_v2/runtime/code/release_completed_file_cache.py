from pathlib import Path
import os,json,time
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime').resolve()
def memory():return {r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()}
def main():
 records=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
 ended={r['id'] for r in records if r['event']=='END' and r.get('joined')}
 before=memory();rows=[]
 for ident in sorted(ended):
  for name in ['runtime_artifacts.json.gz','trace.npz']:
   p=(S/'source/results'/ident/name).resolve()
   assert p.is_relative_to(S)
   if not p.is_file():continue
   st=p.stat();fd=os.open(p,os.O_RDONLY)
   try:
    os.fsync(fd)
    os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
   finally:os.close(fd)
   after=p.stat();assert st.st_size==after.st_size and st.st_mtime_ns==after.st_mtime_ns
   rows.append(dict(path=str(p),bytes=st.st_size,data_unchanged=True))
 audit=dict(unix=time.time(),operation='POSIX_FADV_DONTNEED only for ended new-study archived files; no deletion or global cache operation',before=before,after=memory(),files=rows)
 with (S/'FILE_CACHE_ADVICE.jsonl').open('a') as f:f.write(json.dumps(audit)+'\n')
 print(json.dumps(dict(files=len(rows),bytes=sum(r['bytes'] for r in rows),available_before_GiB=before['MemAvailable']/2**30,available_after_GiB=audit['after']['MemAvailable']/2**30)),flush=True)
if __name__=='__main__':main()
