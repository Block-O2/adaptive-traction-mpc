"""Reseal after manual final review; refuse a live research package."""
from pathlib import Path
import argparse,json,os,time
from research_common import ROOT,HARD_STOP,read,atomic,sha,now,same_pid,pid_identity
EXCLUDE={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}

def inspection():
    sources=['CAMPAIGN_PROCESS.json','WATCHDOG_START.json','STATUS_MONITOR_START.json','ANALYSIS_SERVICE_START.json','FAILSAFE_START.json','FINALIZER_IDENTITY.json']
    sources += [str(p.relative_to(ROOT)) for folder in [ROOT/'audit/observers',ROOT/'followup_queues',ROOT/'audit/frozen_rechecks'] for p in folder.glob('*/START.json')]
    live=[]
    for name in sources:
        d=read(ROOT/name,{})
        if same_pid(d.get('identity')):live.append(dict(source=name,identity=d['identity']))
    for p in (ROOT/'owned').glob('*.json'):
        d=read(p)
        if same_pid(d.get('worker')):live.append(dict(source=str(p.relative_to(ROOT)),identity=d['worker']))
    ledger=read(ROOT/'LEDGER.json');unsettled=[a['id'] for a in ledger['attempts'] if not a['settled']]
    checks=dict(authoritative_END_STOP=read(ROOT/'END.json',{}).get('status')=='STOP',
        STOP_record=read(ROOT/'STOP.json',{}).get('status')=='STOP',admission_stopped=(ROOT/'STOP_REQUESTED').exists(),
        no_live_owned=not live,no_open_reservations=not unsettled,
        original_verification_exists=(ROOT/'PACKAGE_VERIFICATION.json').is_file(),before_deadline=time.time()<HARD_STOP-10)
    return dict(time_utc=now(),ready=all(checks.values()),checks=checks,live=live,open_reservations=unsettled)

def reseal():
    checked=inspection();assert checked['ready'],'CLOSED_PACKAGE_REQUIRED:'+json.dumps(checked)
    review=read(ROOT/'SCIENTIFIC_REVIEW_STATUS.json');matrix=read(ROOT/'COMPLETION_REQUIREMENTS.json')
    assert not review.get('required_final_update',True) and review.get('review_sha256')==sha(ROOT/'SCIENTIFIC_REVIEW.md'),'FINAL_MANUAL_REVIEW_NOT_CLOSED'
    assert matrix['overall_status']!='OPEN_RESEARCH_RUNNING','COMPLETION_CONTENT_AUDIT_STILL_OPEN'
    atomic(ROOT/'CLOSED_PACKAGE_RESEAL.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),inspection=checked,
        scientific_review_sha256=sha(ROOT/'SCIENTIFIC_REVIEW.md'),completion_matrix_sha256=sha(ROOT/'COMPLETION_REQUIREMENTS.json'),
        source_sha256=sha(Path(__file__)),scope='Final documents were reviewed after finalizer exit. Hash all closed-package files including orphan temporary data. This resealer exits silently after writing manifest/verification; a separate independent read must verify afterward.'))
    print('RESEALING_CLOSED_PACKAGE',flush=True)
    files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and str(p.relative_to(ROOT)) not in EXCLUDE]
    entries=[]
    for p in files:
        assert time.time()<HARD_STOP-5,'RESEAL_HARD_DEADLINE'
        entries.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)))
    atomic(ROOT/'OUTPUT_MANIFEST.json',dict(time_utc=now(),files=entries,excludes=sorted(EXCLUDE),
        evidence_scope='Every closed-package file including orphaned temporary files, except the two declared self-referential files',
        expected_file_count=len(files),manifest_complete=len(entries)==len(files),hard_stop_reached=False,
        after_final_manual_review=True))
    verification=read(ROOT/'PACKAGE_VERIFICATION.json')
    verification.update(time_utc=now(),scientific_review_status=review['status'],scientific_review_sha256=sha(ROOT/'SCIENTIFIC_REVIEW.md'),
        completion_requirements_status=matrix['overall_status'],manifest_expected_files=len(files),manifest_entries=len(entries),
        manifest_complete=True,manifest_sha256=sha(ROOT/'OUTPUT_MANIFEST.json'),
        resealed_after_manual_final_review=True,reseal_before_deadline=time.time()<HARD_STOP,
        independent_final_verification_required=True,independent_final_verification_pass=False)
    atomic(ROOT/'PACKAGE_VERIFICATION.json',verification)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inspect-only',action='store_true');a=p.parse_args()
    if a.inspect_only:print(json.dumps(inspection()))
    else:reseal()
