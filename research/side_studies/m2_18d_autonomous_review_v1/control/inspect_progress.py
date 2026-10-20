from pathlib import Path
import json,time,sys
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
rows=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()] if (P/'ATTEMPTS.jsonl').exists() else []
starts=[r for r in rows if r['event']=='START'];ends=[r for r in rows if r['event']=='END'];closed={r['id'] for r in ends}
print(json.dumps(dict(elapsed_min=(time.time()-1792214779)/60,START=len(starts),END=len(ends),active=[dict(id=r['id'],elapsed_s=time.time()-r['unix'],pid=r['pid']) for r in starts if r['id'] not in closed])))
for f in P.glob('*_RESULTS.json'):
 try:r=json.loads(f.read_text())
 except (ValueError,OSError):continue
 print(f.name,[(x['arm'],round(x['J_F_N_s'],9),x['motion']['acceptance_pass'],x['motion']['failed_requirements']) for x in r['rows']])
for f in (P/'logs').glob('*.log'):
 print(f.name, '\n'.join(f.read_text(errors='replace').splitlines()[-3:])[:1800])
