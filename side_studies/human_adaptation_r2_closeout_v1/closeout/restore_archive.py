"""Recover one archived evidence file without simulation or overwrite."""
from pathlib import Path
import argparse,json,hashlib,gzip,zipfile,shutil
def sha_stream(f):
 h=hashlib.sha256()
 while b:=f.read(4*1024*1024):h.update(b)
 return h.hexdigest()
def sha(p):
 with p.open('rb') as f:return sha_stream(f)
def payload(p):
 if p.suffix=='.gz':
  with gzip.open(p,'rb') as f:return {'kind':'gzip_decompressed_content','sha256':sha_stream(f)}
 if p.suffix=='.npz':
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   return {'kind':'npz_uncompressed_members','members':[{'name':n,'bytes':z.getinfo(n).file_size,'sha256':sha_stream(z.open(n))} for n in sorted(z.namelist())]}
 raise ValueError('Unsupported evidence')
parser=argparse.ArgumentParser();parser.add_argument('--index',type=Path,default=Path(__file__).parent/'RESTORE_INDEX.json');parser.add_argument('--original-path');parser.add_argument('--destination',type=Path);parser.add_argument('--list',action='store_true');a=parser.parse_args()
rows=json.loads(a.index.read_text())['files']
if a.list:
 for r in rows:print(r['absolute_path'],'->',r['archive_path'],r['sha256'])
else:
 assert a.original_path and a.destination,'Need original path and new destination'
 row=next(r for r in rows if r['absolute_path']==a.original_path);src=Path(row['archive_path']);dest=a.destination.expanduser().absolute()
 assert not dest.exists() and not dest.is_symlink(),'Refuse overwrite'
 assert sha(src)==row['sha256'] and payload(src)==row['decompressed_content']
 dest.parent.mkdir(parents=True,exist_ok=True)
 with src.open('rb') as f,dest.open('xb') as out:shutil.copyfileobj(f,out,4*1024*1024)
 assert sha(dest)==row['sha256'] and payload(dest)==row['decompressed_content']
 print('RESTORE_PASS',dest,row['sha256'])
