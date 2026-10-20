from pathlib import Path
import json, subprocess, hashlib, os, time, gzip
import numpy as np
P=Path(__file__).resolve().parents[1]
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
Q=S/'m2_18d_baseline_qualification_v1'; A=S/'m2_18d_autonomous_review_v1'
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
for d in ['audit','derived','figures','provenance','logs']: (P/d).mkdir(exist_ok=True)
def put(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''): h.update(b)
 return h.hexdigest()
def git():
 return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
if not (P/'RUN_PLAN.json').exists():
 put('RUN_PLAN.json',dict(t0='2026-10-17T14:05:15+08:00',t0_unix=1792217115,hard_stop_unix=1792231515,no_new_physics_after_unix=1792228815,physics_START_limit=20,question='N2 terminal response mechanism and one bounded lawful intervention',diagnosis_first=True,unchanged='B, plant, task, HOLD, thresholds, truth firewall, bridge 40ms, lifecycle 100ms, admission, age, native ownership, receipts, carry and fallback',primary='N2 matched full-state B/E/intervention; repeat only after complete motion/safety/causal and >=1% gain vs B; one new prefix if permitted',stop='No identifiable lawful independent factor: E; unidentifiable actual response: D; failed motion: C, no blind shrink; no training; STOP on completion'))
 put('audit/GIT_BEFORE.json',git())
 inv={}; hashes={}
 for root in [MAIN,S]:
  for f in root.rglob('*'):
   if '.git' in f.parts or '__pycache__' in f.parts or not f.is_file() or f.is_symlink():continue
   st=f.stat();inv[str(f)]=[st.st_size,st.st_mtime_ns]
   if root==MAIN or f.is_relative_to(Q) or f.is_relative_to(A): hashes[str(f)]=sha(f)
 put('audit/HISTORY_METADATA_BEFORE.json',inv);put('audit/PROTECTED_SHA_BEFORE.json',hashes)
 print('PROTECTED',len(inv),len(hashes),flush=True)
out={}
for root,g,arm in [(A,'N2',a) for a in ['B','E','C','R']]+[(Q,'N1',a) for a in ['B','E']]:
 f=root/'source/results'/f'{g}_{arm}';su=json.loads((f/'summary.json').read_text());tr=np.load(f/'trace.npz')
 key=f'{root.name}/{g}_{arm}'
 out[key]=dict(trace={k:[str(tr[k].dtype),list(tr[k].shape)] for k in tr.files},summary_keys=list(su),decision_sample=su['decisions'][4],learning_sample=su['learning_records'][4],files=[str(p.relative_to(f)) for p in f.rglob('*') if p.is_file()])
 if arm=='E' and g=='N2':
  for name in ['runtime_artifacts.json.gz','native_reference.npz']:
   if name.endswith('.gz'):
    z=json.loads(gzip.open(f/name,'rt').read());out[key]['runtime_keys']=list(z) if isinstance(z,dict) else ['LIST',len(z)];out[key]['runtime_example']=str(z)[:1500]
   else:
    z=np.load(f/name);out[key]['reference_schema']={k:[str(z[k].dtype),list(z[k].shape),z[k][:2].tolist()] for k in z.files}
 put('derived/SCHEMA.json',out)
 print('SCHEMA',key,'decisions',len(su['decisions']),'learning',len(su['learning_records']),flush=True)
print('DONE',flush=True)
