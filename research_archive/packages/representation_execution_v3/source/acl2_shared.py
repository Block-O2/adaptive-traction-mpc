from pathlib import Path
import os,json,time,hashlib,datetime
P=Path(os.environ.get('ACL2_PACKAGE','/home/hank/ihear-lab/representation_execution_v3'));R=P/'runtime'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if hasattr(x,'tolist'):return clean(x.tolist())
 if hasattr(x,'item'):return x.item()
 return x
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_name(f.name+'.'+str(os.getpid())+'.tmp');tmp.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(f)
def read(n):return json.loads((P/n).read_text())
def append(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True)
 with f.open('a') as s:s.write(json.dumps(clean(x),ensure_ascii=False,allow_nan=False)+'\n');s.flush();os.fsync(s.fileno())
def decision(hypothesis,experiment,result,diagnosis,next_action,evidence):append('RESEARCH_DECISIONS.jsonl',dict(utc=utc(),hypothesis=hypothesis,experiment=experiment,result=result,diagnosis=diagnosis,decision=next_action,evidence=evidence))
def records():return [json.loads(s) for s in (R/'ATTEMPTS.jsonl').read_text().splitlines()] if (R/'ATTEMPTS.jsonl').exists() else []
def native_used():
 total=0
 for row in records():
  if row['event']!='START':continue
  for suffix in ['_DATA.json','_PARTIAL_COMPUTE.json']:
   f=R/'output'/(row['id']+suffix)
   if f.exists():
    d=json.loads(f.read_text());d=d.get('metric',d);total+=int(d.get('actual_new_native_physics_steps') or 0);break
 return total
