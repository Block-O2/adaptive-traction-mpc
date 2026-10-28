"""Read-only final owned PID/start_ticks audit; never signals unrelated processes."""
from pathlib import Path
import os,json,datetime
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');known={}
def collect(x,origin):
 if isinstance(x,dict):
  if isinstance(x.get('pid'),int) and isinstance(x.get('start_ticks'),int):
   key=(x['pid'],x['start_ticks']);known.setdefault(key,[]).append(origin)
  for v in x.values():collect(v,origin)
 elif isinstance(x,list):
  for v in x:collect(v,origin)
for f in (P/'owned').glob('*.json'):
 try:collect(json.loads(f.read_text()),str(f.relative_to(P)))
 except json.JSONDecodeError:pass
snapshot=P/'audit/OWNED_PROCESS_IDENTITY_SNAPSHOTS.jsonl'
if snapshot.exists():
 for line in snapshot.read_text().splitlines():collect(json.loads(line),'audit/OWNED_PROCESS_IDENTITY_SNAPSHOTS.jsonl')
def current(pid):
 q=Path('/proc')/str(pid)
 try:
  stat=(q/'stat').read_text();s=stat[stat.rfind(')')+2:].split();cmd=(q/'cmdline').read_bytes().replace(b'\x00',b' ').decode()
  return dict(pid=pid,ppid=int(s[1]),state=s[0],start_ticks=int(s[19]),command=cmd)
 except (FileNotFoundError,ProcessLookupError,PermissionError):return None
rows=[];active=[];zombies=[]
for (pid,ticks),origins in sorted(known.items()):
 c=current(pid);status='IDENTITY_NO_LONGER_PRESENT'
 if c and c['start_ticks']==ticks:
  status='EXITED_ZOMBIE_REAP_PENDING' if c['state']=='Z' else 'OWNED_STILL_ACTIVE'
  if status=='OWNED_STILL_ACTIVE':active.append(c)
  else:zombies.append(c)
 rows.append(dict(pid=pid,start_ticks=ticks,status=status,origins=sorted(set(origins)),current=c if c and c['start_ticks']==ticks else None))
untracked=[];exclude={os.getpid(),os.getppid()}
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name) in exclude:continue
 c=current(int(q.name))
 if not c or c['state']=='Z':continue
 cmd=c['command']
 if str(P) in cmd and '/bin/bash -c' not in cmd and 'python3 -' not in cmd and 'v5_owned_audit.py' not in cmd and (c['pid'],c['start_ticks']) not in known:untracked.append(c)
deps=json.loads((P/'queue/FINAL_AUDIT_DEPENDENCIES.json').read_text())['required_queue_end'];missing=[n for n in deps if not (P/n).is_file()]
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if not active and not untracked and not missing else 'REVIEW_REQUIRED',known_kernel_process_identities=len(rows),active_owned_processes=active,untracked_package_processes=untracked,exited_zombie_reap_pending=zombies,missing_required_queue_END=missing,rows=rows,scope='Exact PID plus Linux kernel start_ticks; PID reuse does not authorize killing another process. Scientific workers, supervisor descendants and queue/services included. Current short audit command/tool shell excluded and exits when this command returns.',signals_sent_by_this_audit=0)
(P/'audit/OWNED_PID_FINAL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('OWNED_PID_AUDIT',out['status'],'known',len(rows),'active',len(active),'untracked',len(untracked),'missing_END',missing);assert out['status']=='PASS','OWNED_PROCESS_OR_QUEUE_NOT_CLOSED'
