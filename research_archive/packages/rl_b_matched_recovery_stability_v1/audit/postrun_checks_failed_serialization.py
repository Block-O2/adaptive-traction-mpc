from pathlib import Path
import json,hashlib,sys,subprocess,os,collections,gzip
import numpy as np
r=Path(__file__).resolve().parents[1];g=r/'github';runtime=r/'physical/runtime';c=r.parent/'rl_b_autonomous_replication_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(n,o):(r/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
# Same random-number stream is tested from stored raw samples, without any physics.
rows=[]
for seed in [1495656323,1630784693]:
 for rng in [2026102101,2026102102]:
  a=json.loads((runtime/f'evaluations/seed{seed}_ep050_rng{rng}/POLICY_SAMPLES.json').read_text())['samples'];b=json.loads((runtime/f'evaluations/seed{seed}_ep080_rng{rng}/POLICY_SAMPLES.json').read_text())['samples'];n=min(len(a),len(b));eps=[]
  for x,y in zip(a[:n],b[:n]):eps.append(np.max(np.abs((np.array(x['raw_action'])-x['deterministic_mean'])/x['std']-(np.array(y['raw_action'])-y['deterministic_mean'])/y['std'])))
  rows.append({'seed':seed,'evaluation_rng_seed':rng,'common_action_draws':n,'standardized_noise_max_difference':float(max(eps)),'common_random_numbers_verified':max(eps)<1e-6})
put('stability/COMMON_RANDOM_NUMBERS_AUDIT.json',{'pairs':rows,'all_pass':all(x['common_random_numbers_verified'] for x in rows),'new_physics':0,'new_gradient_updates':0})
# Fixed baseline and every recorded checkpoint file checked separately.
evals=[json.loads(s) for s in (c/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()];fixed=[x for x in evals if x['kind']=='fixed_legal_plus_one'];assert len(fixed)==1
z=np.load(c/fixed[0]['run']/'transitions_0.npz');assert np.all(z['actions']==1)
fm=json.loads((runtime/'FROZEN_CONTRACT_MANIFEST.json').read_text())['files'];copied=[{'path':k,'expected':v,'actual':sha(runtime/k),'pass':v==sha(runtime/k)} for k,v in fm.items()];assert all(x['pass'] for x in copied)
put('audit/PHYSICAL_RUNTIME_IDENTITY_END.json',{'files':copied,'all_pass':True,'count':len(copied),'fixed_plus_one_baseline_actions_verified':True,'historical_PPO_deterministic_forward_evaluations':len(evals)-1,'fixed_legal_baseline_evaluations':1})
# Hash the untouched Git checkout without mutation or refresh.
env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}
def git(*args):return subprocess.check_output(['git','-C',str(g),*args],env=env,text=True).strip()
status=git('status','--porcelain=v1','--untracked-files=all');head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}');expected=json.loads((r/'audit/STUDY_START.json').read_text())['requested_commit'];assert head==expected and not status
put('audit/GITHUB_FINAL_IDENTITY.json',{'head':head,'expected_commit':expected,'head_matches':head==expected,'tree':tree,'origin':git('remote','get-url','origin'),'porcelain':status,'clean':not status,'detached':subprocess.run(['git','-C',str(g),'symbolic-ref','-q','HEAD'],env=env,capture_output=True).returncode!=0,'only_git_mutations':'new isolated clone and authorized detached checkout; no stage/commit/push/merge/rebase/reset/stash/clean','remote_ref':(r/'logs/remote_ref.txt').read_text().strip()})
# Original scorer sealed output manifest is verified in full, including native fixture copies.
manifest=json.loads((r/'scorer/original-001/OUTPUT_MANIFEST.json').read_text())['files'];mismatch=[]
for rel,expected in manifest.items():
 p=r/'scorer/original-001'/rel
 if p.stat().st_size!=expected['bytes'] or sha(p)!=expected['sha256']:mismatch.append(rel)
assert not mismatch
put('audit/SCORER_OUTPUT_MANIFEST_VERIFICATION.json',{'files':len(manifest),'mismatches':mismatch,'pass':not mismatch})
# Confirm all new compressed streams roundtrip to the exact bytes audited before compression.
compression=[]
for p in sorted((runtime/'evaluations').glob('*/LOSSLESS_RAW_COMPRESSION.json')):
 report=json.loads(p.read_text())
 for x in report['files']:
  target=p.parent/(x['path']+'.gz');h=hashlib.sha256();size=0
  with gzip.open(target,'rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b);size+=len(b)
  compression.append({'path':str(target.relative_to(r)),'original_sha256':x['original_sha256'],'decompressed_sha256':h.hexdigest(),'uncompressed_bytes':size,'pass':h.hexdigest()==x['original_sha256'] and size==x['uncompressed_bytes'] and sha(target)==x['gzip_sha256']})
assert all(x['pass'] for x in compression)
put('audit/LOSSLESS_RAW_FINAL_VERIFICATION.json',{'streams':compression,'all_pass':True,'count':len(compression)})
print(json.dumps({'runtime_identity_files':len(copied),'common_rng_pairs':len(rows),'common_rng_all_pass':all(x['common_random_numbers_verified'] for x in rows),'scorer_output_files':len(manifest),'compression_streams':len(compression),'github_clean':not status}))
