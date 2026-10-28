"""Lossless new-campaign storage with original-content and archive hashes."""
from pathlib import Path
import gzip,hashlib,json

def read_json(path):
 path=Path(path)
 if path.exists():return json.loads(path.read_text())
 with gzip.open(str(path)+'.gz','rt') as f:return json.load(f)
def file_sha(path):
 path=Path(path);h=hashlib.sha256()
 f=path.open('rb') if path.exists() else gzip.open(str(path)+'.gz','rb')
 with f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def archive_outputs(out,root):
 """Archive new run JSON only, never historical evidence or live files."""
 out=Path(out).resolve();root=Path(root).resolve()
 if root not in out.parents:raise ValueError('archive scope escaped NEW campaign root')
 rp=out/'rollout_result.json';record=read_json(rp)
 if record['status']=='RUNNING':raise ValueError('cannot archive live rollout')
 entries=record.setdefault('lossless_archives',[])
 for rep in out.glob('rep_*'):
  for name in ('runtime_artifacts.json','summary.json','learning_transitions.jsonl'):
   p=rep/name
   if not p.exists():continue
   dest=Path(str(p)+'.gz');original=file_sha(p);original_bytes=p.stat().st_size
   if not dest.exists():
    with p.open('rb') as source,gzip.open(dest,'wb',compresslevel=1) as output:
     for b in iter(lambda:source.read(1024*1024),b''):output.write(b)
   h=hashlib.sha256()
   with gzip.open(dest,'rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
   if h.hexdigest()!=original:raise ValueError('archive content hash mismatch')
   compressed=file_sha(dest)
   entries.append({'original_path':str(p.relative_to(out)),'archive_path':str(dest.relative_to(out)),'original_sha256':original,'gzip_sha256':compressed,'original_bytes':original_bytes,'gzip_bytes':dest.stat().st_size,'lossless_verified':True})
   record.setdefault('raw_files_sha256',{})[str(dest.relative_to(out))]=compressed
   p.unlink() # resolved scope checked; verified redundant NEW file only
 rp.write_text(json.dumps(record,indent=2,sort_keys=True,allow_nan=False)+'\n')
 return record
