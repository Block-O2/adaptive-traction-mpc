"""Read-only OS observer of the SAC process tree during evaluation; no simulation."""
import json,time,sys,subprocess
from pathlib import Path
import memory_test_v1 as m
out=m.LOCAL;rows=[];pid=None
def tree(root):
    all_rows=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            s={k:v.strip() for k,v in (l.split(':',1) for l in (p/'status').read_text().splitlines())}
            all_rows.append(dict(pid=int(p.name),ppid=int(s['PPid']),name=s['Name'],state=s['State']))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    owned={root}
    while True:
        nxt=owned|{r['pid'] for r in all_rows if r['ppid'] in owned}
        if nxt==owned:break
        owned=nxt
    result=[]
    for r in all_rows:
        if r['pid'] in owned:
            try:r.update(m.memfile(f"/proc/{r['pid']}/smaps_rollup"));result.append(r)
            except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return result
def run():
    global pid
    deadline=time.monotonic()+90*60
    while time.monotonic()<deadline:
        latest=json.loads((out/'LATEST.json').read_text());step=latest.get('step')
        if pid is None and step is not None:pid=latest['processes']['owned'][0]['pid']
        if pid and not Path(f'/proc/{pid}').exists():break
        active=latest['tag'].startswith(('before_periodic_evaluations','before_final_eval','after_final_eval','milestone_25000','milestone_30000','after_training_close'))
        if step is not None and step>=24500:
            procs=tree(pid);row=dict(unix=time.time(),observed_parent_tag=latest['tag'],step=step,processes=procs,owned_count=len(procs),tree_pss_bytes=sum(r.get('Pss',0) for r in procs),windows=m.windows(),wsl=m.memfile('/proc/meminfo'),nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip())
            rows.append(row);text=json.dumps(rows,indent=2)+'\n';(out/'EVALUATION_PEAK_SAMPLES.json').write_text(text);(m.D/'EVALUATION_PEAK_SAMPLES.json').write_text(text)
            if active:print(json.dumps(dict(step=step,tag=latest['tag'],owned=len(procs),tree_pss_mib=row['tree_pss_bytes']/2**20)),flush=True)
        time.sleep(2 if active else 10)
    print('READ_ONLY_PEAK_MONITOR_STOP',flush=True)
if __name__=='__main__':run()
