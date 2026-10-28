"""Owned-only identity audit; cleanup is allowed only after explicit local closeout."""
from pathlib import Path
import os,json,time,signal,sys
P=Path(__file__).resolve().parents[1]
def proc(pid):
    try:
        q=Path('/proc')/str(pid);s=(q/'stat').read_text();v=s[s.rindex(')')+2:].split()
        raw=(q/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        try:cwd=os.readlink(q/'cwd')
        except OSError:cwd=''
        return dict(pid=pid,ppid=int(v[1]),start_ticks=int(v[19]),state=v[0],cmdline=raw,cwd=cwd)
    except (OSError,ValueError):return None
def ancestors():
    out={os.getpid()};x=proc(os.getpid())
    while x and x['ppid']>0 and x['ppid'] not in out:
        out.add(x['ppid']);x=proc(x['ppid'])
    return out
skip=ancestors();known={};files=[]
for f in sorted((P/'owned').glob('*.json')):
    try:d=json.loads(f.read_text())
    except ValueError:continue
    files.append(f.name)
    for r in [d.get('identity'),d.get('worker')]+list(d.get('known_owned',{}).values()):
        if r and r.get('start_ticks') is not None:known.setdefault(int(r['pid']),set()).add(int(r['start_ticks']))
def owned():
    rows=[]
    for q in Path('/proc').iterdir():
        if not q.name.isdigit() or int(q.name) in skip:continue
        r=proc(int(q.name))
        if r is None:continue
        identity=r['start_ticks'] in known.get(r['pid'],set())
        explicit=(str(P)+'/') in r['cmdline'] or (P.name+'/source/') in r['cmdline']
        located=r['cwd'].startswith(str(P)+'/')
        if identity or explicit or located:
            r['ownership_evidence']=[k for k,v in [('recorded_pid_start_ticks',identity),('isolated_script_path',explicit),('isolated_working_directory',located)] if v]
            # Store only owned script names, never arbitrary external command text.
            r['script_tokens']=[z for z in r.pop('cmdline').split() if P.name in z and not z.startswith(('"',"'"))][:4]
            rows.append(r)
    return rows
began=time.time();before=owned();actions=[]
if '--cleanup' in sys.argv:
    assert (P/'CLOSURE_START.json').exists(),'CLOSURE_REQUIRED_BEFORE_OWNED_CLEANUP'
    for sig,seconds in [(signal.SIGTERM,12),(signal.SIGKILL,3)]:
        targets=[r for r in owned() if r['state']!='Z']
        for old in targets:
            now=proc(old['pid'])
            if now and now['start_ticks']==old['start_ticks']:
                try:os.kill(old['pid'],sig);actions.append(dict(pid=old['pid'],start_ticks=old['start_ticks'],signal=int(sig)))
                except ProcessLookupError:pass
        stop=time.time()+seconds
        while time.time()<stop and any(r['state']!='Z' for r in owned()):time.sleep(.25)
after=owned();live=[r for r in after if r['state']!='Z']
out=dict(status='PASS' if not live else 'OWNED_STILL_ACTIVE',started_unix=began,ended_unix=time.time(),
         lifecycle_files_checked=files,known_identities=sum(map(len,known.values())),before=before,
         actions=actions,remaining_live=live,zombies=[r for r in after if r['state']=='Z'],
         audit_process_and_tool_ancestors_excluded=sorted(skip),
         scope='Only exact recorded PID+start_ticks or isolated-package script/cwd; unrelated processes untouched.')
name='OWNED_PROCESS_FINAL.json' if '--cleanup' in sys.argv else 'OWNED_PROCESS_PROGRESS.json'
(P/'audit'/name).write_text(json.dumps(out,indent=2)+'\n')
print('OWNED_AUDIT',out['status'],'live',len(live),'signals',len(actions),flush=True)
if '--cleanup' in sys.argv and live:raise SystemExit(1)
