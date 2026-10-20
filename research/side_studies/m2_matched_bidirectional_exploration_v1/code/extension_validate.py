"""Independent exported-byte, denominator, source, preservation, closure checks."""
from extension_common import *
import re

def main():
    target=WIN_EXT/'delivery';manifest=json.loads((target/'DELIVERY_MANIFEST.json').read_text());issues=[];links=0
    def read(name):return json.loads((target/name).read_text())
    seen=set()
    for r in manifest['entries']:
        p=target/r['path']
        if r['path'] in seen:issues.append('DUPLICATE:'+r['path'])
        seen.add(r['path'])
        if not p.is_file() or sha(p)!=r['sha256'] or p.stat().st_size!=r['bytes']:issues.append('BYTES:'+r['path'])
        if p.suffix=='.json':
            try:json.loads(p.read_text())
            except ValueError:issues.append('JSON:'+r['path'])
    extra={str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()}-seen-{'DELIVERY_MANIFEST.json','DELIVERY_VALIDATION.json'}
    if extra:issues.append('EXTRA:'+str(sorted(extra)))
    report=(target/'REPORT.md').read_text()
    if re.findall(r'^## (\d+)\.',report,re.M)!=list(map(str,range(1,14))):issues.append('SECTIONS')
    for raw in re.findall(r'\]\(<([^>]+)>\)',report):
        if raw.startswith(('https:','http:')):continue
        p=Path('/mnt/c/'+raw[3:]) if raw.startswith('C:/') else Path(raw);links+=1
        if not p.is_file():issues.append('LINK:'+raw)
    close=read('CLOSEOUT_STATUS.json');plan=read('RUN_PLAN.json');pres=read('PRESERVATION_AUDIT.json');proc=read('PROCESS_CLOSEOUT.json');timer=read('TIMER_SERVICE.json');back=read('BACKLOG_AND_RAW_AUDIT.json');replay=read('ACTIVATION_REPLAY.json');fig=read('FIGURE_MANIFEST.json');data=read('DATA_ACCOUNTING.json');source=read('SOURCE_RETENTION.json')
    if close['status']!='STOPPED_AND_RECONCILED' or close['attempts']!=160 or close['ended']!=160 or close['active_physics'] or close['auto_resume'] or close['remaining_physics_attempts']:issues.append('CLOSEOUT')
    if plan['status']!='CLOSED' or plan['deadline_unix']!=DEADLINE or not plan['physics_dispatch_disabled'] or plan['auto_resume']:issues.append('PLAN')
    if close['Q_updates'] or close['actual_nonzero_learning_execution'] or close['adaptation']!='NOT_RUN' or close['new_optimization_promoted']:issues.append('UNEXPECTED_POSITIVE_CLAIM')
    if pres['status']!='PASS' or pres['issues'] or proc['status']!='RECORDED_EXTENSION_IDENTITIES_ABSENT' or proc['unexpected_live']:issues.append('PRESERVATION_OR_PROCESS')
    if len(timer['rows'])!=792 or len(timer['sessions'])!=36 or any(not r['decision_exact'] for r in timer['rows']) or timer['physics_attempts_added']:issues.append('TIMER_MATRIX')
    if back['retained_all_request_rows']!=339 or back['retained_task_request_rows']!=75 or back['retained_pre_task_request_rows']!=264 or back['cumulative_attempts']!=160 or back['new_raw_status']!='PASS' or back['authoritative_total_native_steps']!=11750740:issues.append('DENOMINATORS_OR_RAW')
    if replay['status']!='CENSORED_ACTIVATION_ENTRY_NOT_REACHED' or replay['captures']!=0 or replay['captured_final_record_mismatches'] is not None or replay['existing_C2_output_mismatches'] is not None:issues.append('EMPTY_REPLAY_SCOPE')
    approved='4133c0d1002d237aad689e47b085b31eef3536e9e28b064a33d91b5c7e6c1f40'
    if fig['status']!='VISUALLY_VERIFIED' or fig['approved_sha256']!=approved or sha(target/'figures/offline_timer_service.png')!=approved or sha(target/'TIMER_SERVICE.json')!=next(iter(fig['inputs'].values())):issues.append('FIGURE_QA')
    if source['status']!='PASS' or source['missing']:issues.append('SOURCE_RETENTION')
    for r in source['rows']:
        rel=Path(r['retained_path']).relative_to(EXT)
        if sha(target/rel)!=r['sha256']:issues.append('RETAINED_SOURCE:'+str(rel))
    before=read('BEFORE.json')
    for name,digest in before['accepted_files'].items():
        p=Path(name)
        if not p.is_file() or sha(p)!=digest:issues.append('FIRST_DELIVERY_CHANGED:'+name)
    actual_data=data['total_bytes']+manifest['bytes']+2**20
    if data['status']!='PASS' or actual_data>=10*2**30:issues.append('DATA_BUDGET')
    # Verify actual cumulative ledger/root closed state after the supplement.
    from accounting import rows
    events=rows();starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
    if len(starts)!=160 or len(ends)!=160 or {r['id'] for r in starts}!={r['id'] for r in ends}:issues.append('ACTUAL_ATTEMPT_LEDGER')
    if not (STUDY/'STOP_DISPATCH').is_file() or not (EXT/'RESOURCE_WATCH_STOP.json').is_file():issues.append('STOP_MARKERS')
    checkpoint=json.loads((STUDY/'CHECKPOINT.json').read_text())
    if checkpoint['attempts']!=160 or checkpoint['ended']!=160 or checkpoint['active'] or checkpoint['auto_resume'] or checkpoint['hard_deadline_unix']!=DEADLINE:issues.append('ROOT_CHECKPOINT')
    out=dict(status='PASS' if not issues else 'FAIL',unix=time.time(),files=len(manifest['entries']),bytes=manifest['bytes'],local_links=links,report_sections=13,cumulative_attempts=160,native_steps=11750740,first_delivery_files_preserved=len(before['accepted_files']),added_data_upper_bound_bytes=actual_data,issues=issues,physics_added=0,manifest_sha256=sha(target/'DELIVERY_MANIFEST.json'))
    save(target/'DELIVERY_VALIDATION.json',out);print(json.dumps(out));assert not issues

if __name__=='__main__':main()
