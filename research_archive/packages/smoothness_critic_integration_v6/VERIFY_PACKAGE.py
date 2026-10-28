"""Read-only package verification: python -B VERIFY_PACKAGE.py [package directory]."""
from pathlib import Path
import hashlib,json,sys,time
P=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
SEAL={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json','END.json'}
def skip(rel):
    return str(rel) in SEAL or any(s in {'.venv','__pycache__'} for s in rel.parts) or rel.parts[:2]==('runtime','tmp')
def digest(f):
    h=hashlib.sha256()
    with f.open('rb') as s:
        for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
    return h.hexdigest()
def read(n):return json.loads((P/n).read_text())
def verify():
    errors=[];began=time.time();m=read('OUTPUT_MANIFEST.json');end=read('END.json');v=read('PACKAGE_VERIFICATION.json')
    for rel,r in m['files'].items():
        p=P/rel
        if not p.is_file() or p.stat().st_size!=r['bytes'] or digest(p)!=r['sha256']:errors.append('MANIFEST:'+rel)
    actual={str(f.relative_to(P)) for f in P.rglob('*') if f.is_file() and not skip(f.relative_to(P))}
    errors += ['UNMANIFESTED:'+r for r in sorted(actual-set(m['files']))]
    if end['state']!='STOP':errors.append('END_NOT_STOP')
    if end['ended_unix']>read('ACTIVATION.json')['hard_stop_unix']:errors.append('HARD_DEADLINE_EXCEEDED')
    if end['manifest_sha256']!=digest(P/'OUTPUT_MANIFEST.json'):errors.append('END_MANIFEST_IDENTITY')
    if end['verification_sha256']!=digest(P/'PACKAGE_VERIFICATION.json'):errors.append('END_VERIFICATION_IDENTITY')
    if v['status']!='PASS':errors.append('PACKAGE_VERIFICATION_NOT_PASS')
    a=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json')
    if a['physical_START']!=a['physical_END'] or a['unexpected_incomplete_ids']:errors.append('UNACCOUNTED_ATTEMPTS')
    if sum(r['actual_new_native_steps'] for r in a['attempts'])!=a['actual_new_native_steps']:errors.append('NATIVE_LEDGER_SUM')
    plan=read('runtime/RUN_PLAN.json')
    if a['physical_START']>plan['physics_budget'] or a['actual_new_native_steps']>plan['native_step_cap']:errors.append('RESOURCE_CAP')
    for name in ['audit/HISTORY_PROTECTION_FINAL.json','audit/V5_MANIFEST_FINAL.json',
                 'audit/EXECUTION_AND_CONTRACT_INTEGRITY.json','audit/OWNED_PROCESS_FINAL.json',
                 'audit/JOURNAL_APPEND_ONLY_FINAL.json','audit/UNCHANGED_SCORER_REPLAY.json',
                 'audit/FROZEN_TEST_ACTUAL_STATE_INDEPENDENCE.json','audit/NATIVE_STEP_LEDGER_REPLAY.json',
                 'audit/FREEZE_AND_CAUSAL_PREDICTION_CHRONOLOGY.json']:
        if read(name)['status']!='PASS':errors.append('FINAL_AUDIT:'+name)
    scorer=read('audit/UNCHANGED_SCORER_REPLAY.json')
    if scorer['audited']!=a['physical_START']:errors.append('RAW_SCORER_COVERAGE')
    native=read('audit/NATIVE_STEP_LEDGER_REPLAY.json')
    if native['audited']!=a['physical_START'] or native['independently_counted_new_native_steps']!=a['actual_new_native_steps']:errors.append('INDEPENDENT_NATIVE_LEDGER')
    j=read('audit/JOURNAL_APPEND_ONLY_FINAL.json');root_journal=P.parent/'RESEARCH_DECISION_JOURNAL.md'
    if root_journal.exists():
        b=root_journal.read_bytes()
        if hashlib.sha256(b[:j['snapshot_bytes']]).hexdigest()!=j['snapshot_sha256']:errors.append('JOURNAL_SNAPSHOT_PREFIX_CHANGED')
    for rel in v['required_artifacts']:
        if not (P/rel).is_file():errors.append('MISSING_REQUIRED:'+rel)
    return dict(status='PASS' if not errors else 'FAIL',files=len(m['files']),
                physical_START=a['physical_START'],native_steps=a['actual_new_native_steps'],
                elapsed_verification_s=time.time()-began,errors=errors,
                scope='Read-only hashes, ledger, unchanged original scorer/audit identities, STOP and hard deadline. '
                      'Seal files are outside manifest to avoid self-reference; END binds manifest and verification hashes.')
if __name__=='__main__':
    result=verify();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(result['status']!='PASS')
