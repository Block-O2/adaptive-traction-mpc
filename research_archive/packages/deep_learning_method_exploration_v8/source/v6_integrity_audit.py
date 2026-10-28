"""Final read-only checks of execution identities, original contract and v5 raw."""
from pathlib import Path
import hashlib,json,time,sys,datetime
P=Path(__file__).resolve().parents[1]; V=P.parent/'smoothness_critic_research_v5'
def read(f):return json.loads(f.read_text())
def digest(f):
    h=hashlib.sha256()
    with f.open('rb') as s:
        for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
    return h.hexdigest()
def put(name,x):(P/'audit'/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
    start=time.time(); cache={}; errors=[]; rows=[];pending=[]
    def sha(f):
        key=str(f)
        if key not in cache:cache[key]=digest(f)
        return cache[key]
    for f in sorted((P/'jobs').glob('*/SOURCE_MANIFEST.json')):
        m=read(f);group=f.parent.name;bad=[]
        for rel,h in m['files'].items():
            q=P/rel
            if not q.exists() or sha(q)!=h:bad.append(rel)
        config=P/'experiments'/f'{group}.json'
        if sha(config)!=m['config_sha256']:bad.append('CONFIG_IDENTITY')
        done=P/'jobs'/group/'WORKER_DONE.json'
        if done.exists():
            wd=read(done)
            if not wd.get('all_children_joined',False):bad.append('CHILDREN_NOT_JOINED')
            if not all(r['unchanged'] for r in wd.get('parent_checks',[])):bad.append('FORK_PARENT_CHANGED')
        elif '--progress' not in sys.argv:bad.append('WORKER_END_MISSING')
        rows.append(dict(group=group,source_files=len(m['files']),mismatches=bad))
        errors += [group+':'+b for b in bad]
    events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
    starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
    if len({r['id'] for r in starts})!=len(starts):errors.append('NON_UNIQUE_START')
    for s in starts:
        group=s['group']; source=P/'jobs'/group/'SOURCE_MANIFEST.json'
        if sha(source)!=s['job_source_sha256']:errors.append('EVENT_SOURCE:'+s['id'])
        if sha(P/'experiments'/f'{group}.json')!=s['config_sha256']:errors.append('EVENT_CONFIG:'+s['id'])
        ee=[r for r in ends if r['id']==s['id']]
        if not ee and '--progress' in sys.argv:pending.append(s['id'])
        elif len(ee)!=1 or ee[0]['unix']<s['unix']:errors.append('START_END_PAIR:'+s['id'])
    modelrows=[]
    for name in ['COMMON_COMPOSE_FROZEN.json','COMMON_COMPOSE_NO_HISTORY_FROZEN.json']:
        m=read(P/'models'/name);bad=[]
        for rel,h in m.get('source_sha256',{}).items():
            if sha(P/rel)!=h:bad.append(rel)
        for g,h in m.get('train_data_sha256',{}).items():
            if sha(P/'data'/f'{g}.json')!=h:bad.append('TRAIN_DATA:'+g)
        modelrows.append(dict(model=name,mismatches=bad));errors+=bad
    original=[]
    for d in ['runtime/code','runtime/control','runtime/deps','runtime/source/stages']:
        for f in sorted((P/d).rglob('*')):
            if not f.is_file() or '__pycache__' in f.parts:continue
            rel=f.relative_to(P);old=V/rel
            if not old.exists():errors.append('UNEXPECTED_ORIGINAL_RUNTIME_FILE:'+str(rel));continue
            a=old.read_bytes();b=f.read_bytes()
            expected=a.replace(str(V).encode(),str(P).encode()) if f.suffix=='.py' else a
            if b!=expected:errors.append('NON_PATH_ORIGINAL_RUNTIME_CHANGE:'+str(rel))
            original.append(dict(path=str(rel),original_sha256=sha(old),isolated_sha256=sha(f),path_relocation_only=a!=b))
    for name in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','PARAMETER_MAP.json','ACTION_SET.json']:
        if sha(P/'runtime'/name)!=sha(V/'runtime'/name):errors.append('ORIGINAL_PROTOCOL_CHANGED:'+name)
    put('EXECUTION_INTEGRITY_PROGRESS.json' if '--progress' in sys.argv else 'EXECUTION_AND_CONTRACT_INTEGRITY.json',dict(status='PASS' if not errors else 'FAIL',
        started_unix=start,ended_unix=time.time(),jobs=rows,models=modelrows,
        attempts=len(starts),original_runtime_files=len(original),errors=errors,pending_END=pending,
        allowed_change='Only literal old package root replacement in copied runtime .py files; '
        'all physics, guard, scorer, thresholds, formal B/H150/18D protocols retain original bytes/semantics.',
        runtime_file_identity=original))
    if '--v5-full' in sys.argv:
        began=time.time();manifest=read(V/'OUTPUT_MANIFEST.json');bad=[]
        for rel,record in manifest['files'].items():
            q=V/rel
            if not q.exists() or q.stat().st_size!=record['bytes'] or sha(q)!=record['sha256']:bad.append(rel)
        put('V5_MANIFEST_FINAL.json',dict(status='PASS' if not bad else 'FAIL',
            started_unix=began,ended_unix=time.time(),files=len(manifest['files']),mismatches=bad,
            manifest_sha256=sha(V/'OUTPUT_MANIFEST.json')))
    print('INTEGRITY', 'PASS' if not errors else 'FAIL',len(starts),'attempts',len(original),'runtime files',errors[:10],flush=True)
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
