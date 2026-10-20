"""Owned read-only progress observer; mirrors compact status to the new Windows package."""
from pathlib import Path
import json,time,os,shutil
R=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
assert P.name==R.name and R.name=='ihear_overnight_control_learning_transition_v1'
plan=json.loads((P/'RUN_PLAN.json').read_text());seen=set()
(P/'audit/MONITOR_OWNER.json').write_text(json.dumps(dict(pid=os.getpid(),started=time.time()))+'\n')
try:
    while time.time()<plan['hard_stop_unix'] and not (P/'STOP_MONITOR.json').exists():
        attempts=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()] if (P/'ATTEMPTS.jsonl').exists() else []
        starts=[r for r in attempts if r['event']=='START'];ended={r['id'] for r in attempts if r['event']=='END'}
        rows=[]
        for f in P.glob('*_RESULTS.json'):
            if f.name in ['EXPERIMENT_RESULTS.json','LEARNING_RESULTS.json']:continue
            try:data=json.loads(f.read_text())
            except json.JSONDecodeError:continue
            for r in data.get('rows',[]):
                if 'J_F_N_s' not in r:continue
                brief=dict(id=r['id'],J_F=r['J_F_N_s'],qualified=r['all_original_qualifications'],failed=r['motion']['failed_requirements'])
                rows.append(brief)
                if r['id'] not in seen:print(json.dumps(brief),flush=True);seen.add(r['id'])
        status=dict(unix=time.time(),elapsed_s=time.time()-plan['t0_unix'],starts=len(starts),ends=len(ended),active=[r['id'] for r in starts if r['id'] not in ended],results=rows)
        for dest in [P/'PROGRESS.json',R/'PROGRESS.json']:
            temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(status,indent=2)+'\n');temp.replace(dest)
        time.sleep(15)
finally:
    (P/'audit/MONITOR_EXIT.json').write_text(json.dumps(dict(pid=os.getpid(),ended=time.time()))+'\n')
    print('MONITOR_EXIT',flush=True)
