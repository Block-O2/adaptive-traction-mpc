from pathlib import Path
import hashlib,json,difflib,collections,csv
r=Path(__file__).resolve().parents[1];g=r/'github';h=g/'research/rl_b_cpu_handoff_v1';c=r.parent/'rl_b_autonomous_replication_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def put(n,o):(r/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
def pair(a,b,scope):
 sa=sha(a);sb=sha(b);status='IDENTICAL' if sa==sb else 'CLOUD_MODIFIED' if sa and sb else 'CLOUD_ADDED' if sa else 'GITHUB_ONLY'
 d={'scope':scope,'cloud_path':str(a) if sa else None,'github_path':str(b) if sb else None,'cloud_sha256':sa,'github_sha256':sb,'status':status}
 if sa and sb and sa!=sb and a.suffix in {'.py','.json','.md','.sh','.txt'}:
  name=f"{scope}__{str(a.relative_to(c)).replace('/','__')}.diff";p=r/'source_diff'/name;p.write_text(''.join(difflib.unified_diff(b.read_text().splitlines(True),a.read_text().splitlines(True),fromfile=str(b),tofile=str(a))));d['exact_diff']=str(p.relative_to(r))
 return d
sm=json.loads((c/'SOURCE_MANIFEST.json').read_text());fm=json.loads((c/'FROZEN_CONTRACT_MANIFEST.json').read_text())['files']
identity=[]
for n,v in fm.items():identity.append({'path':n,'expected':v,'actual':sha(c/n),'match':sha(c/n)==v})
science=[]
for n,v in sm['files'].items():
 d=pair(c/'source'/n,h/'source'/n,'sealed_science');d['cloud_manifest_sha256']=v;d['cloud_manifest_match']=d['cloud_sha256']==v;science.append(d)
main=[pair(c/'source'/n,g/n,'active_main_science') for n in sm['files']]
cloud_files={p.relative_to(c).as_posix() for p in c.glob('*.py')}|{p.relative_to(c).as_posix() for p in (c/'configs').glob('*') if p.is_file()}
gh_files={p.relative_to(h).as_posix() for p in h.glob('*.py')}|{p.relative_to(h).as_posix() for p in (h/'configs').glob('*') if p.is_file()}
wrappers=[pair(c/n,h/n,'wrapper') for n in sorted(cloud_files|gh_files)]
# Vendor/model files outside original 414 manifest are included explicitly.
extra=[]
for p in sorted((c/'source').rglob('*')):
 if p.is_file() and p.relative_to(c/'source').as_posix() not in sm['files']:
  n=p.relative_to(c/'source');extra.append(pair(p,h/'source'/n,'extra_source_asset'))
history=[]
names=['rl_b_cloud_v1','rl_b_cloud_g4_repair_v1','rl_b_g4_closure_ppo_readiness_v1','rl_b_first_ppo_pilot_v1','rl_b_autonomous_replication_v1']
for left,right in zip(names,names[1:]):
 a=r.parent/left;b=r.parent/right;rows=[]
 for n in sorted({p.name for p in a.glob('*.py')}|{p.name for p in b.glob('*.py')}):
  sa=sha(a/n);sb=sha(b/n)
  if sa!=sb:
   d={'path':n,'before_sha256':sa,'after_sha256':sb,'status':'MODIFIED' if sa and sb else 'ADDED' if sb else 'ABSENT_LATER'}
   if sa and sb:
    dest=r/'source_diff'/f'lineage__{left}__{right}__{n}.diff';dest.write_text(''.join(difflib.unified_diff((a/n).read_text().splitlines(True),(b/n).read_text().splitlines(True),fromfile=str(a/n),tofile=str(b/n))));d['diff']=str(dest.relative_to(r))
   rows.append(d)
 history.append({'from':left,'to':right,'changed_root_python_files':rows})
# Map all root code through the protected baseline to avoid treating file names as provenance.
manifest={'actual_training_root':str(c),'actual_training_entry':'replication_run.py','training_log_rows':len((c/'ALL_TRAINING_LOG.jsonl').read_text().splitlines()),'frozen_contract_verification':identity,'all_frozen_contract_files_match':all(x['match'] for x in identity),'scientific_source_manifest':str(c/'SOURCE_MANIFEST.json'),'science':science,'active_main_science':main,'wrappers':wrappers,'additional_assets':extra,'historical_lineage':history}
for k in ['science','active_main_science','wrappers','additional_assets']:manifest[k+'_counts']=dict(collections.Counter(x['status'] for x in manifest[k]))
put('source_diff/FILE_SHA256_COMPARISON.json',manifest)
with (r/'source_diff/FILE_SHA256_COMPARISON.csv').open('w') as f:
 keys=['scope','status','cloud_path','github_path','cloud_sha256','github_sha256','exact_diff'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(science+main+wrappers+extra)
print(json.dumps({k:manifest[k] for k in manifest if k.endswith('_counts')},indent=2));print('frozen_identity',manifest['all_frozen_contract_files_match'])
