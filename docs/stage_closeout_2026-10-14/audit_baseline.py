import base64, hashlib, html as html_lib, json, os, re, subprocess
from pathlib import Path
from collections import Counter

ROOT = Path('/home/hank/coding/adaptive-traction-mpc-learning')
SIDE = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OUT = ROOT / 'docs/stage_closeout_2026-10-14'
OUT.mkdir(exist_ok=True)
LOCAL = ROOT / '.stage_closeout_local_20261014'
LOCAL.mkdir(exist_ok=True)
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()
def save(name, obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

status=git('status','--porcelain=v1','-z')
if not (LOCAL/'initial_status.z').exists():
    (LOCAL/'initial_status.z').write_bytes(status)
    (LOCAL/'initial_cached.patch').write_bytes(git('diff','--cached','--binary'))
    (LOCAL/'initial_unstaged.patch').write_bytes(git('diff','--binary'))
status=(LOCAL/'initial_status.z').read_bytes()
index=git('ls-files','--stage','-z')
if not (LOCAL/'initial_index.z').exists(): (LOCAL/'initial_index.z').write_bytes(index)
assert index==(LOCAL/'initial_index.z').read_bytes()
tracked=set(git('ls-files','-z').decode().split('\0'))
counts=Counter(x[:2].decode() for x in status.split(b'\0') if x)
large=[]; directories=Counter(); caches=[]
for directory, subs, files in os.walk(ROOT, followlinks=False):
    if Path(directory)==ROOT: subs[:]=[s for s in subs if s not in ['.git','.stage_closeout_local_20261014']]
    for name in files:
        p=Path(directory)/name
        if p.is_symlink(): continue
        n=p.stat().st_size; rel=p.relative_to(ROOT).as_posix()
        directories[rel.split('/')[0]]+=n
        if n>=50*1024*1024: large.append({'path':rel,'bytes':n,'tracked_or_staged':rel in tracked})
        if '__pycache__' in p.parts and p.suffix=='.pyc' and rel not in tracked:
            assert p.resolve().is_relative_to(ROOT.resolve())
            caches.append({'path':rel,'bytes':n,'allocated_bytes':p.stat().st_blocks*512,'sha256':sha(p)})
audit={'starting_head':git('rev-parse','HEAD').decode().strip(),'branch':git('branch','--show-current').decode().strip(),
       'remote':git('remote','get-url','origin').decode().strip(),'status_counts':dict(counts),
       'preexisting_index_sha256':hashlib.sha256(index).hexdigest(),
       'cached_patch_sha256':sha(LOCAL/'initial_cached.patch'),
       'unstaged_patch_sha256':sha(LOCAL/'initial_unstaged.patch'),
       'current_remote_difference':git('rev-list','--left-right','--count','HEAD...origin/codex/expert-strength-value-adequacy-v1').decode().strip(),
       'main_difference':git('rev-list','--left-right','--count','HEAD...origin/main').decode().strip(),
       'working_tree_logical_bytes_by_top_directory':dict(directories),
       'large_files_50MiB_and_above':sorted(large,key=lambda x:-x['bytes']),
       'cache_candidates':caches,
       'side_studies_policy':'Read-only; no deletion or second archive campaign.'}
save('GIT_AND_STORAGE_AUDIT.json',audit)

prof=ROOT/'docs/professor_update_2026-10-14'
verified=[]
for row in json.loads((prof/'SOURCE_MANIFEST.json').read_text()):
    p=prof/row['file']; assert sha(p)==row['sha256'],str(p)
    verified.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
v=json.loads((prof/'SINGLE_HTML_VERIFICATION.json').read_text())
html=(prof/v['single_html_file']).read_text()
assert sha(prof/v['single_html_file'])==v['sha256']
embedded=[hashlib.sha256(base64.b64decode(s)).hexdigest() for s in re.findall(r'data:[^"\s]+?;base64,([A-Za-z0-9+/=]+)',html)]
for group in ['embedded_media','embedded_documents']:
    for name,row in v[group].items():
        assert sha(prof/name)==row['sha256'],name
        if group=='embedded_media': assert row['sha256'] in embedded,name
        else:
            text=re.search(r'<details[^>]*id="'+row['id']+r'"[^>]*>.*?<pre>(.*?)</pre>',html,re.S).group(1)
            assert hashlib.sha256(html_lib.unescape(text).encode()).hexdigest()==row['sha256'],name
assert not re.search(r'(?:src|href)=["\']https?://',html)
missing=[]
for link in re.findall(r'(?:src|href)=["\']([^"\']+)',(prof/'index.html').read_text()):
    if not link.startswith(('data:','#','http:','https:','mailto:')) and not (prof/link).exists(): missing.append(link)
assert not missing,missing
for row in json.loads((prof/'VIDEO_MANIFEST.json').read_text())['source_cases']:
    assert sha(row['trace_path'])==row['trace_sha256']
    verified.append({'path':row['trace_path'],'sha256':row['trace_sha256']})
for row in json.loads((prof/'evidence/CURRENT_METHOD_DETAILS.json').read_text())['source_files']:
    assert sha(row['path'])==row['sha256'],row['path']
    verified.append({'path':row['path'],'sha256':row['sha256']})
packages=['b_fast_runtime_completion_v1','b_hold_return_critical_path_v1','b_runtime_qualification_decoupling_v1',
          'b_multirate_realtime_v1','b_native_learning_matrix_v1','b_native_q_realtime_integration_v1',
          'direction-prior-value-v1','m2_neural_q_motion_v1','m2_free_trajectory_feasibility_v1',
          'ihear_overnight_research_retrospective_v1']
for name in packages:
    p=SIDE/name
    assert p.is_dir(),str(p)
    for file in p.rglob('*'):
        if file.is_file() and not file.is_symlink() and (
            file.parent==p and file.suffix in ['.md','.json'] or
            any(part in ['models','weights'] for part in file.relative_to(p).parts) and file.suffix in ['.npz','.pt','.pth','.json']):
            verified.append({'path':str(file),'bytes':file.stat().st_size,'sha256':sha(file)})
save('EVIDENCE_VERIFICATION.json',{'verified_files':verified,'embedded_payloads_verified':len(embedded),
     'missing_editable_html_resources':missing,'new_simulations':0,'new_training':0,
     'qualification':'LEVEL1 only for 18D best; no promotion of B, host or clinical qualification',
     'browser_execution':'Not newly verified by this script; structural checks and media hashes verified.'})
print(json.dumps({'status_counts':dict(counts),'cache_count':len(caches),'cache_bytes':sum(x['bytes'] for x in caches),
      'cache_allocated_bytes':sum(x['allocated_bytes'] for x in caches),'evidence_files_hashed':len(verified),
      'large_files':len(large),'logical_bytes':dict(directories)},indent=2))
