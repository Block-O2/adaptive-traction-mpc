from pathlib import Path
import os,sys,json,hashlib,subprocess,shutil,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');O=P.parent/'adaptive_continuous_coordination_optimization_v1';M=Path('/home/hank/coding/adaptive-traction-mpc-learning');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
sys.path.insert(0,str(P/'control'))
from analyze_mechanism import put,sha
assert (P/'PHYSICAL_DONE.json').exists()
before=json.loads((P/'audit/PROTECTION_BEFORE.json').read_text());git={}
for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
 b=subprocess.check_output(['git','-C',str(M),*args]);git[k]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
 if k in ['head','branch']:git[k]['value']=b.decode().strip()
 (P/'audit'/('git_'+k+'_after.txt')).write_bytes(b)
git['index']=sha(M/'.git/index');meta={str(f.relative_to(M)):[f.stat().st_size,f.stat().st_mtime_ns] for f in M.rglob('*') if f.is_file() and '.git' not in f.relative_to(M).parts}
consumed=json.loads((P/'audit/ARCHIVE_INPUTS.json').read_text());bad_archive=[f for f,r in consumed.items() if sha(Path(f))!=r['sha256']];assert not bad_archive
code=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text());changed_execution=[f for f,h in code['files'].items() if sha(P/f)!=h];assert not changed_execution,changed_execution
same=dict(main_git=git==before['git'],main_file_metadata=meta==before['files'],consumed_archives=not bad_archive,execution_manifest_unchanged=not changed_execution,motion_protocol_bytes=(P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()==(O/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes())
assert all(same.values()),same
source_diff=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or '__pycache__' in f.parts or 'results' in f.relative_to(P).parts:continue
  old=O/f.relative_to(P)
  if not old.exists():source_diff.append(str(f.relative_to(P)));continue
  a=old.read_bytes();b=f.read_bytes()
  if a!=b:
   try:equal=a.decode().replace(str(O),str(P))==b.decode()
   except UnicodeError:equal=False
   if not equal:source_diff.append(str(f.relative_to(P)))
assert not source_diff,source_diff
put('audit/FINAL_PROTECTION.json',dict(status='PASS',checks=same,production_or_historical_writes=False,source_closure_semantic_changes=source_diff,scope='Main Git/index/staged/unstaged/status plus main file size/mtime inventory; hashes of consumed historical raw archives; exact executed closure manifest; copied physics source/deps/code/weights differ from prior closure only by path relocation. No claim of hashing every unrelated historical file.'))
attempts=[json.loads(l) for l in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in attempts if r['event']=='START'];ends=[r for r in attempts if r['event']=='END'];assert {r['id'] for r in starts}=={r['id'] for r in ends};assert len(starts)==len(ends)<=14
put('EXECUTION/ATTEMPT_ACCOUNTING.json',dict(physical_START=len(starts),physical_END=len(ends),all_joined=all(r.get('joined') for r in ends),returncode_failures=[r for r in ends if r.get('returncode')!=0],starts=starts,ends=ends,scope='Includes initial stopped parent, completed B recovered without new physics, repair parent/B, all zero/opposite/smooth/half/repeat arms. Kinematic reconstruction has zero integration steps and is not a physical START.'))
put('EXECUTION/ENGINEERING_ATTEMPTS.json',dict(attempts=[
 dict(stage='WSL archive read',failure='sandbox WSL access denied',repair='same read authorized through sandbox escalation',physics=0),
 dict(stage='offline design 1',failure='scalar polynomial evaluator returned one joint scalar; rejected before physics',repair='explicit array time evaluation',physics=0),
 dict(stage='offline design 2',failure='midpoint knot fixes original reference velocity extremum so position-only TV objective has no improvement',repair='use registered fractions .2/.4/.8; no force objective',physics=0),
 dict(stage='target fixture',failure='first default fixture not intended window, then request IDs confused with 0-based decision indices',repair='actual OUT slot3 / RETURN slot3 fixture indices3/11; all rejected prephysics',physics=0),
 dict(stage='opposite .05deg',failure='O/R unchanged velocity certificate rejected',repair='one prephysical quarter-amplitude control, original rejection retained in TARGETED_MATH_TESTS',physics=0),
 dict(stage='startup 1',failure='missing copied shared action contract',repair='copy byte-identical prior contract',log='logs/physics.log',physics=0),
 dict(stage='startup 2',failure='missing new motion_series output directory after B completed; parent stopped at task entry',repair='recover evaluator on saved B; new legal complete parent and B; 2 extra engineering START allowance before nonzero results',log='logs/physics_attempt2.log',physics_START=2),
 dict(stage='allocator plot',failure='axvspan c keyword invalid',repair='color keyword only; numerical analysis unaffected',physics=0)
 ],all_scientific_negative_results_retained=True))
put('STATE.json',dict(status='COMPLETE_STOPPED_AFTER_REGISTERED_TARGETED_STUDY',physical_starts=len(starts),all_children_joined=True,no_automatic_next_search=True,report='REPORT.md',last_update_unix=time.time()))
for f in (L/'control').glob('*.py'):
 # Analysis/postprocessing scripts added after physics are preserved separately
 # from the immutable execution manifest rather than rewriting that manifest.
 if not (P/'control'/f.name).exists():shutil.copy2(f,P/'control'/f.name)
put('ANALYSIS_CODE_MANIFEST.json',{str(f.relative_to(P)):sha(f) for f in (P/'control').glob('*.py')})
print('PROTECTION_PASS',same,'START_END',len(starts),len(ends))
