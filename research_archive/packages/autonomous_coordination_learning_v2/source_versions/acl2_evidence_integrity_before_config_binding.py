"""Rebind audit caches, physical manifests and frozen locks to current files."""
from pathlib import Path
import json,time
from acl2_shared import P,put,read,sha,utc,records

def audit(final=False):
    started=time.time();cache={};errors=[];sources=[];bindings=0;pending=[]
    def digest(path):
        path=Path(path)
        if path not in cache:cache[path]=sha(path) if path.exists() else None
        return cache[path]
    def check(path,expected,scope):
        if digest(path)!=expected:errors.append(dict(scope=scope,path=str(Path(path).relative_to(P)),expected_sha256=expected,actual_sha256=digest(path)))
    for f in sorted((P/'jobs').glob('*/SOURCE_MANIFEST.json')):
        d=json.loads(f.read_text());before=len(errors)
        for name,expected in d['files'].items():check(P/name,expected,'PHYSICAL_SOURCE:'+f.parent.name)
        sources.append(dict(group=f.parent.name,files=len(d['files']),pass_=len(errors)==before))
    for f in sorted((P/'jobs').glob('*/START.json')):
        d=json.loads(f.read_text());cmd=d.get('command',[])
        if len(cmd)>1 and d.get('source_sha256'):check(Path(cmd[1]),d['source_sha256'],'QUEUE_JOB_START:'+f.parent.name)
    starts=[r for r in records() if r['event']=='START']
    for r in starts:
        for kind in ['independent','scorer_replay']:
            f=P/'audit'/kind/(r['id']+'.json')
            if not f.exists():pending.append(dict(id=r['id'],audit=kind));continue
            d=json.loads(f.read_text())
            for name,expected in d.get('input_sha256',{}).items():check(P/name,expected,kind+':'+r['id']);bindings+=1
            for name,expected in d.get('unchanged_scorer_sources',{}).items():check(P/name,expected,'ORIGINAL_SCORER:'+r['id']);bindings+=1
    validation=P/'VALIDATION_INPUT_LOCK.json'
    if validation.exists():
        lock=read('VALIDATION_INPUT_LOCK.json');frozen=read('FROZEN_SELECTION.json');check(P/'FROZEN_SELECTION.json',lock['selection_sha256'],'VALIDATION_INPUT_LOCK');check(P/'VALIDATION_ALLOCATION.json',lock['validation_allocation_sha256'],'VALIDATION_ALLOCATION');check(P/'source/acl2_validation_worker.py',lock['validation_worker_sha256'],'VALIDATION_WORKER')
        for name,expected in lock['configs'].items():check(P/name,expected,'LOCKED_CONFIG')
        for name,expected in frozen['source_files'].items():check(P/name,expected,'FROZEN_SOURCE')
        if frozen.get('model_path'):check(P/frozen['model_path'],frozen['model_sha256'],'FROZEN_GP')
        check(P/'models/MODAL_NOMINAL_TABLE.json',frozen['nominal_table_sha256'],'FROZEN_NOMINAL')
        extension=P/'VALIDATION_TIME_EXTENSION_LOCK.json'
        if extension.exists():
            ext=read('VALIDATION_TIME_EXTENSION_LOCK.json');check(validation,ext['original_validation_lock_sha256'],'EXTENSION_ORIGINAL_LOCK');check(P/'FROZEN_SELECTION.json',ext['frozen_selection_sha256'],'EXTENSION_FIXED_CANDIDATES');check(P/'source/acl2_validation_extension.py',ext['source_sha256'],'EXTENSION_SOURCE')
            for name,expected in ext['configs'].items():check(P/name,expected,'EXTENSION_CONFIG')
    if final and pending:errors.append(dict(scope='MISSING_FINAL_AUDITS',pending=pending))
    out=dict(utc=utc(),status='PASS' if not errors and not pending else 'PENDING_LIVE' if not errors else 'FAIL',final=final,physical_START=len(starts),physical_manifest_checks=sources,audit_hash_bindings=bindings,unique_files_hashed=len(cache),pending_audits=pending,errors=errors,wall_s=time.time()-started,scope='Current scientific files rehashed against per-job pre-execution sources, original-scorer replay and independent raw audit inputs, and one-use validation locks. No native integration or result edits.',source_sha256=sha(__file__))
    put('audit/EVIDENCE_INPUT_HASH_INTEGRITY.json',out);return out

if __name__=='__main__':
    r=audit();print('EVIDENCE_INTEGRITY',r['status'],'hashes',r['unique_files_hashed'],'errors',len(r['errors']),flush=True)
