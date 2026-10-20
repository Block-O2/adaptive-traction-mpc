from pathlib import Path
import sys,re,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1')
if sys.argv[1]=='find':
 root=Path(sys.argv[2]);pattern=sys.argv[3]
 for p in root.rglob(pattern):print(p)
elif sys.argv[1]=='read':
 p=Path(sys.argv[2]);lines=p.read_text().splitlines();start=int(sys.argv[3]);end=int(sys.argv[4])
 for i,line in enumerate(lines[start-1:end],start):print(f'{i}: {line}')
elif sys.argv[1]=='grep':
 p=Path(sys.argv[2]);pattern=sys.argv[3].replace(",","|");radius=int(sys.argv[4]) if len(sys.argv)>4 else 2
 lines=p.read_text().splitlines();hit=set()
 for i,line in enumerate(lines):
  if re.search(pattern,line):hit.update(range(max(0,i-radius),min(len(lines),i+radius+1)))
 for i in sorted(hit):print(f'{i+1}: {lines[i]}')
elif sys.argv[1]=='status':
 for name in ['CHECKPOINT.json','TASK_LEDGER.json','RESOURCE_STATE.json']:
  p=S/name
  if p.exists():print(name,p.read_text()[:6000])
 rows=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];print('ATTEMPTS',sum(x['event']=='START' for x in rows));print('LAST',rows[-3:])
