"""Fresh-process final byte/coverage/process verification; only writes excluded V."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,time
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def identity(pid):
    try:
        s=Path(f'/proc/{pid}/stat').read_text();f=s[s.rfind(')')+2:].split()
        return dict(pid=pid,start_ticks=f[19],state=f[0])
    except FileNotFoundError:return None
def alive(expected):
    actual=identity(expected['pid']) if expected else None
    return bool(actual and actual['start_ticks']==expected['start_ticks'] and actual['state']!='Z')
def main():
    hard=datetime.fromisoformat(read(ROOT/'START.json')['hard_stop_utc']).timestamp()
    assert time.time()<hard-10
    path=ROOT/'OUTPUT_MANIFEST.json';before=digest(path);m=read(path);v=read(ROOT/'PACKAGE_VERIFICATION.json')
    excluded={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}
    assert set(m['excludes'])==excluded and m['manifest_complete'] and m.get('after_final_manual_review')
    assert v['resealed_after_manual_final_review'] and v['manifest_sha256']==before
    entries=m['files'];names=[x['path'] for x in entries];assert len(set(names))==len(names)
    actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()}-excluded
    expected=set(names);assert actual==expected,dict(unlisted=sorted(actual-expected)[:20],missing=sorted(expected-actual)[:20])
    assert len(entries)==m['expected_file_count']==v['manifest_entries']==v['manifest_expected_files']
    bad=[];total=0
    for x in entries:
        assert time.time()<hard-5,'INDEPENDENT_VERIFIER_HARD_DEADLINE'
        p=ROOT/x['path'];assert p.resolve().is_relative_to(ROOT.resolve()),'MANIFEST_PATH_ESCAPES_PACKAGE'
        if p.stat().st_size!=x['bytes'] or digest(p)!=x['sha256']:bad.append(x['path'])
        total+=x['bytes']
    assert not bad,bad[:20]
    sources=['CAMPAIGN_PROCESS.json','WATCHDOG_START.json','STATUS_MONITOR_START.json','ANALYSIS_SERVICE_START.json','FAILSAFE_START.json','FINALIZER_IDENTITY.json','CLOSED_PACKAGE_RESEAL.json']
    sources += [str(p.relative_to(ROOT)) for folder in ['followup_queues','audit/observers','audit/frozen_rechecks'] for p in (ROOT/folder).glob('*/START.json')]
    live=[]
    for source in sources:
        p=ROOT/source
        if p.exists() and alive(read(p).get('identity')):live.append(source)
    for p in (ROOT/'owned').glob('*.json'):
        if alive(read(p).get('worker')):live.append(str(p.relative_to(ROOT)))
    assert not live,live
    unregistered=[]
    for p in Path('/proc').glob('[0-9]*'):
        if int(p.name)==os.getpid():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0')
            if any(a.decode(errors='replace').startswith(str(ROOT)+'/') and a.endswith(b'.py') for a in args):
                state=identity(int(p.name))
                if state and state['state']!='Z':unregistered.append(dict(identity=state,args=[a.decode(errors='replace') for a in args]))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    assert not unregistered,unregistered
    assert read(ROOT/'END.json')['status']=='STOP' and read(ROOT/'STOP.json')['status']=='STOP'
    ledger=read(ROOT/'LEDGER.json');assert not any(not a['settled'] for a in ledger['attempts'])
    assert digest(path)==before,'MANIFEST_CHANGED_DURING_INDEPENDENT_CHECK'
    assert read(ROOT/'SCIENTIFIC_REVIEW_STATUS.json')['review_sha256']==digest(ROOT/'SCIENTIFIC_REVIEW.md')
    assert read(ROOT/'COMPLETION_REQUIREMENTS.json')['overall_status']=='CONTENT_REVIEW_COMPLETE_WITH_DECLARED_SCIENTIFIC_LIMITS'
    result=dict(time_utc=datetime.now(timezone.utc).isoformat(),verifier_identity=identity(os.getpid()),
        verifier_source_sha256=digest(__file__),manifest_sha256=before,files_verified=len(entries),bytes_verified=total,
        exact_filesystem_coverage=True,hash_and_size_mismatches=bad,all_owned_workers_services_finalizer_resealer_exited=True,
        unregistered_package_python_processes=unregistered,no_open_reservations=True,verification_before_hard_deadline=time.time()<hard,
        scope='Independent fresh Python hashlib pass over every sealed file and exact filesystem set, including orphan writing files; no simulation or learning. The only persistent package change is the declared excluded verification file; its temporary atomic replacement is removed.')
    v.update(independent_final_verification_required=False,independent_final_verification_pass=True,independent_final_verification=result)
    temporary=ROOT/f'.PACKAGE_VERIFICATION.pending.{os.getpid()}'
    # Same-filesystem atomic replacement; no additional file remains after success.
    with temporary.open('w') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,ROOT/'PACKAGE_VERIFICATION.json')
    print(json.dumps(dict(independent_final_verification_pass=True,files_verified=len(entries),bytes_verified=total,manifest_sha256=before)))
if __name__=='__main__':main()
