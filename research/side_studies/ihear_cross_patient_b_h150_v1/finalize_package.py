"""Offline closeout, evidence inventory, and review mirror. Never runs physics."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
REQUIRED=['REPORT.md','HUMAN_MODEL_AUDIT.md','PATIENT_VARIATION_CONTRACT.md','VIRTUAL_PATIENT_COHORT.json','PATIENT_ADMISSIBILITY_RESULTS.json','FROZEN_B_H150_CONTRACT.md','CROSS_PATIENT_EXPERIMENT_RESULTS.json','CROSS_PATIENT_QUALIFICATION.json','PATIENT_SENSITIVITY_ANALYSIS.md','FAILURE_MECHANISM_REPORT.md','LEARNING_DATA_SCHEMA.json','LEARNING_DATA_MANIFEST.json','ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
def read(n,default=None):
    f=P/n
    return json.loads(f.read_text()) if f.exists() else default
def sha(f):
    h=hashlib.sha256()
    before=Path(f).stat()
    with Path(f).open('rb') as stream:
        for b in iter(lambda:stream.read(4*2**20),b''):h.update(b)
    after=Path(f).stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'FILE_CHANGED_DURING_HASH:'+str(f)
    return h.hexdigest()
def artifacts(value):
    if isinstance(value,dict):
        if 'path' in value and 'sha256' in value:yield value
        for child in value.values():yield from artifacts(child)
    elif isinstance(value,list):
        for child in value:yield from artifacts(child)
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def processes():
    found=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
        try:
            argv=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            exe=(proc/'exe').resolve().name
            cwd=(proc/'cwd').resolve()
        except (OSError,PermissionError):continue
        if 'python' in exe.lower() and (P.name in argv or cwd==P or P in cwd.parents):
            found.append(dict(pid=int(proc.name),argv=argv,cwd=str(cwd)))
    return found
def main():
    plan=read('RUN_PLAN.json');cohort=read('VIRTUAL_PATIENT_COHORT.json');reg=read('PREREGISTRATION.json')
    events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
    starts=[x for x in events if x['event']=='START'];ends=[x for x in events if x['event']=='END']
    owners=[read('audit/'+pid+'_OWNER.json',{}) for pid in cohort['order']]
    live=processes()
    code=read('EXECUTION_CODE_MANIFEST.json')
    code_errors=[f for f,h in code['files'].items() if not (P/f).is_file() or sha(P/f)!=h]
    patient_errors=[]
    for pid,h in reg['patient_case_sha256'].items():
        f=P/'patients'/pid/'case.json'
        if not f.exists() or sha(f)!=h:patient_errors.append(pid+':case')
        a=read('patients/'+pid+'/static/MODEL_STATIC_AUDIT.json',{})
        xml=P/'patients'/pid/'static/model.xml'
        if not xml.exists() or sha(xml)!=a.get('xml_sha256'):patient_errors.append(pid+':xml')
    independent=[];raw_binding_errors=[];raw_binding_count=0
    for pid in cohort['order']:
        d=read(pid+'_DONE.json',{})
        audit=read('audit/INDEPENDENT_COMPLETE_'+pid+'.json',{})
        preservation=read('audit/'+pid+'_FAILURE_PRESERVATION_AUDIT.json',{})
        dispatch=next((r for r in read('SERIAL_CAMPAIGN_DONE.json',{}).get('rows',[]) if r.get('patient_id')==pid),{})
        truthful_unrun=dispatch.get('status') in ['MODEL_NOT_ADMISSIBLE','NOT_RUN_BUDGET'] and not any(s.get('patient_id')==pid for s in starts)
        integrity=(audit.get('status')=='PASS' or (audit.get('status')=='PARTIAL_PRESERVED' and preservation.get('status')=='EVIDENCE_PRESERVATION_PASS') or truthful_unrun)
        independent.append(dict(patient_id=pid,completed=d.get('status'),audit_status=audit.get('status'),audit_exists=bool(audit),failure_preservation=preservation.get('status'),truthful_unrun=truthful_unrun,evidence_integrity_verified=integrity))
        for preserved in preservation.get('rows',[]):
            for f,h in preserved.get('source_hashes',{}).items():
                path=Path(f) if Path(f).is_absolute() else P/f
                raw_binding_count+=1
                if not path.is_file() or sha(path)!=h:raw_binding_errors.append(str(path))
        for arm in ['B','H150','parent']:
            measured=read('reports/'+pid+'_'+arm+'_MEASURED.json',{})
            for f,h in measured.get('sources',{}).items():
                path=Path(f) if Path(f).is_absolute() else P/f
                raw_binding_count+=1
                if not path.is_file() or sha(path)!=h:raw_binding_errors.append(str(path))
    aggregate_names=['PATIENT_ADMISSIBILITY_RESULTS.json','CROSS_PATIENT_EXPERIMENT_RESULTS.json','CROSS_PATIENT_QUALIFICATION.json','LEARNING_DATA_MANIFEST.json']
    aggregates={n:read(n,{}) for n in aggregate_names}
    snapshot_checks={n:bool(a and a.get('serial_campaign_done_present') and a.get('snapshot_status')=='NO_ACTIVE_STARTS_AT_SNAPSHOT' and not a.get('active_or_unclosed_attempt_ids') and not a.get('read_errors') and a.get('denominators',{}).get('registered_patients')==len(cohort['order'])) for n,a in aggregates.items()}
    figure=read('figures/FIGURE_MANIFEST.json',{});figure_errors=[]
    for rel,entry in figure.get('source_inputs',{}).items():
        path=Path(rel) if Path(rel).is_absolute() else P/rel
        if not path.is_file() or sha(path)!=entry['sha256']:figure_errors.append(rel)
    for row in figure.get('figures',[]):
        path=P/'figures'/row['file']
        if not path.is_file() or sha(path)!=row['sha256']:figure_errors.append(row['file'])
    denominator=aggregates['CROSS_PATIENT_EXPERIMENT_RESULTS.json'].get('denominators',{})
    figure_current=bool(figure and not figure_errors and figure.get('patient_count')==len(cohort['order']) and figure.get('complete_valid_pair_count')==denominator.get('full_integral_comparable_pairs') and len(figure.get('figures',[]))==6)
    report=read('derived/REPORT_STATISTICS.json',{})
    report_binding_errors=[];report_binding_count=0
    for entry in artifacts(report):
        path=Path(entry['path'])
        if not path.is_absolute():path=P/path
        if entry.get('exists') is False:
            if path.exists():report_binding_errors.append(str(path)+':stale_absence')
            continue
        report_binding_count+=1
        if not path.is_file() or sha(path)!=entry.get('sha256'):report_binding_errors.append(str(path))
    report_qualified_ids={r['patient_id'] for r in report.get('rows',[]) if r.get('final_complete_qualified_pair') is True}
    aggregate_qualified_ids={r['patient_id'] for r in aggregates['CROSS_PATIENT_QUALIFICATION.json'].get('rows',[]) if r.get('independently_verified_qualified_pair') is True}
    launcher_errors=[]
    for launch in report.get('launcher_gate',{}).get('checks',[]):
        if not launch.get('source_claimed_qualified'):continue
        for name in ['HIGH_ROM_CASE_RESULT.json','summary.json']:
            rel='source/results/'+launch['run_id']+'/'+name
            if read(rel,{}).get('status')!='COMPLETE':launcher_errors.append(rel)
    truthful_unrun_ids={r['patient_id'] for r in independent if r['truthful_unrun']}
    final_report_checks=bool(report.get('snapshot_status')=='FINAL_DISPATCH_FILE_PRESENT'
        and report.get('registered_patient_count')==len(cohort['order'])
        and report.get('launcher_gate',{}).get('status')=='PASS'
        and not report.get('read_errors')
        and report.get('comparisons',{}).get('all_valid_pairs',{}).get('gain_denominator')==denominator.get('full_integral_comparable_pairs')
        and not any(r.get('final_complete_qualified_pair') is None and r['patient_id'] not in truthful_unrun_ids for r in report.get('rows',[]))
        and report_binding_count>0 and not report_binding_errors and not launcher_errors
        and report_qualified_ids==aggregate_qualified_ids)
    synthesis=read('audit/CHINESE_REPORT_BINDING.json',{})
    synthesis_errors=[]
    for binding in [synthesis.get('inputs',{}),synthesis.get('outputs',{})]:
        for rel,h in binding.items():
            if not (P/rel).is_file() or sha(P/rel)!=h:synthesis_errors.append(rel)
    learning=read('audit/LEARNING_EXECUTION_FIELD_AUDIT.json',{})
    learning_rows=learning.get('rows',[])
    learning_valid=bool(len(learning_rows)==len(starts) and
        {r['id'] for r in learning_rows}=={s['id'] for s in starts} and
        all(r.get('status') in ['COMPLETE_EVIDENCE_INVENTORIED','PARTIAL_EVIDENCE_INVENTORIED'] and
            r.get('source_bytes_unchanged') is True and r.get('all_compact_observations_equal_trace') is True for r in learning_rows))
    telemetry=read('audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json',{})
    visual_review=read('audit_figures/root_final_review/QA.json',{})
    telemetry_errors=[]
    for row in telemetry.get('rows',[]):
        for rel,h in row.get('source_hashes',{}).items():
            path=Path(rel) if Path(rel).is_absolute() else P/rel
            if not path.is_file() or sha(path)!=h:telemetry_errors.append(rel)
    checks={
      'required_documents_present':all((P/f).is_file() and (P/f).stat().st_size for f in REQUIRED),
      'six_figures_present':len(list((P/'figures').glob('*.png')))>=6,
      'registered_cohort_unchanged':sha(P/'VIRTUAL_PATIENT_COHORT.json')==reg['cohort_sha256'],
      'patient_case_and_model_hashes_unchanged':not patient_errors,
      'frozen_execution_source_unchanged':not code_errors,
      'all_START_source_manifests_equal_frozen_final':all(x['source_sha256']==sha(P/'EXECUTION_CODE_MANIFEST.json') for x in starts),
      'preregistration_before_first_START':bool(starts) and reg['registered_unix']<min(x['unix'] for x in starts),
      'reference_reproduction':read('audit/REFERENCE_REPRODUCTION.json',{}).get('status')=='PASS',
      'all_registered_dispatch_finished':(P/'SERIAL_CAMPAIGN_DONE.json').exists(),
      'all_owner_children_joined':all(x.get('joined') is True or independent[i]['truthful_unrun'] for i,x in enumerate(owners)),
      'no_owned_python_processes_running':not live,
      'attempt_accounting_pass':read('ATTEMPT_ACCOUNTING.json',{}).get('status')=='PASS',
      'all_patient_evidence_integrity_verified':all(x['evidence_integrity_verified'] for x in independent),
      'final_raw_bytes_equal_independently_checked_measurement_sources':raw_binding_count>0 and not raw_binding_errors,
      'aggregate_snapshots_final_and_closed':all(snapshot_checks.values()),
      'figures_current_bound_inputs_and_outputs':figure_current,
      'six_final_figures_visually_reviewed':bool(visual_review.get('status')=='PASS' and
          len(visual_review.get('figures',[]))==6 and visual_review.get('final_manifest_sha256')==sha(P/'figures/FIGURE_MANIFEST.json')),
      'final_report_original_launcher_and_denominators_verified':final_report_checks,
      'chinese_synthesis_matches_final_inputs_and_outputs':bool(synthesis.get('inputs') and synthesis.get('outputs') and not synthesis_errors),
      'all_run_causal_learning_inventories_preserved':learning_valid,
      'all_run_applied_interval_telemetry_verified':bool(telemetry.get('status')=='PASS' and telemetry.get('runs')==len(starts) and not telemetry_errors),
      'history_and_git_preserved':read('audit/HISTORY_PRESERVATION.json',{}).get('status')=='PASS',
      'no_new_physics_in_final_45_minutes':all(x['unix']<plan['no_new_physics_after_unix'] for x in starts),
      'all_physics_ended_before_reserved_closeout':all(x['unix']<plan['physics_hard_stop_unix'] for x in ends),
      'within_eight_hour_budget':time.time()<plan['hard_stop_unix'],
    }
    # Every failure is preserved; a failed scientific hypothesis is not an archive failure.
    verification=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,missing_required=[f for f in REQUIRED if not (P/f).exists()],source_errors=code_errors,patient_errors=patient_errors,independent_patient_audits=independent,raw_binding_count=raw_binding_count,raw_binding_errors=raw_binding_errors,aggregate_snapshot_checks=snapshot_checks,figure_errors=figure_errors,live_owned_processes=live,highest_evidence='PHYSICAL_LEVEL1',physics_STARTs=len(starts),physics_ENDs=len(ends),clinical_evidence=False,P1_executed=False,learning_trained=False,parameter_search=False,work_package_B_started=False,git_mutations=False,canonical=str(P),unix=time.time(),wall_since_T0_s=time.time()-plan['t0_unix'])
    verification.update(report_binding_count=report_binding_count,report_binding_errors=report_binding_errors,
        independently_reread_launcher_errors=launcher_errors,report_qualified_patient_ids=sorted(report_qualified_ids),
        aggregate_qualified_patient_ids=sorted(aggregate_qualified_ids),synthesis_binding_errors=synthesis_errors,
        telemetry_binding_errors=telemetry_errors,learning_inventory_rows=len(learning_rows))
    put('PACKAGE_VERIFICATION.json',verification)
    assert verification['status']=='PASS',json.dumps({k:v for k,v in checks.items() if not v})
    put('PHYSICS_STOP.json',dict(reason='WORK_PACKAGE_A_COMPLETE',unix=time.time(),new_START_allowed=False,auto_resume=False))
    put('PHYSICS_CLOSED.json',dict(status='STOPPED',unix=time.time(),new_START_allowed=False,owned_processes=[],auto_resume=False))
    put('STATE.json',dict(phase='STOPPED',physics_starts=len(starts),owned_pids=[],next=None,no_automatic_work_package_B=True))
    inventory={}
    excluded={'EVIDENCE_MANIFEST.json','PACKAGE_CLOSED.json'}
    for f in sorted(P.rglob('*')):
        rel=f.relative_to(P)
        if not f.is_file() or str(rel) in excluded or any(x in rel.parts for x in ['tmp','__pycache__']):continue
        if f.suffix in ['.lock','.tmp']:continue
        inventory[str(rel)]=dict(size=f.stat().st_size,sha256=sha(f))
    put('EVIDENCE_MANIFEST.json',dict(files=inventory,count=len(inventory),bytes=sum(x['size'] for x in inventory.values()),scope='Canonical complete archive excluding transient caches/locks and self-referential closeout files',unix=time.time()))
    put('PACKAGE_CLOSED.json',dict(status='STOPPED_VERIFIED',unix=time.time(),evidence_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),all_owned_processes_closed=True))
    review=Path(read('ENVIRONMENT.json')['review'])
    # Full raw/native archives remain canonical; this is a small review mirror.
    copied=[]
    for f in sorted(P.rglob('*')):
        rel=f.relative_to(P)
        if not f.is_file():continue
        root_file=len(rel.parts)==1 and f.suffix in ['.json','.md','.py','.jsonl']
        sub_file=rel.parts[0] in ['audit','audit_human','audit_figures','audit_execution','audit_protocol','reports','derived','learning','patients','figures','analysis','provenance'] and f.suffix in ['.json','.md','.png','.py','.xml','.txt']
        if not (root_file or sub_file) or f.stat().st_size>25*2**20:continue
        dest=review/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);copied.append(str(rel))
    (review/'REVIEW_MIRROR.json').write_text(json.dumps(dict(canonical=str(P),review=str(review),raw_source_results_mirrored=False,motion_series_mirrored=False,mirrored_files=copied,canonical_evidence_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json')),indent=2,ensure_ascii=False)+'\n')
    closed=time.time()
    verification.update(closeout_unix=closed,wall_since_T0_s=closed-plan['t0_unix'])
    verification['checks']['within_eight_hour_budget']=closed<plan['hard_stop_unix']
    verification['status']='PASS' if all(verification['checks'].values()) else 'FAIL'
    put('PACKAGE_VERIFICATION.json',verification)
    inventory['PACKAGE_VERIFICATION.json']=dict(size=(P/'PACKAGE_VERIFICATION.json').stat().st_size,sha256=sha(P/'PACKAGE_VERIFICATION.json'))
    put('EVIDENCE_MANIFEST.json',dict(files=inventory,count=len(inventory),bytes=sum(x['size'] for x in inventory.values()),scope='Canonical complete archive excluding transient caches/locks and self-referential closeout files',unix=closed))
    put('PACKAGE_CLOSED.json',dict(status='STOPPED_VERIFIED' if verification['status']=='PASS' else 'STOPPED_VERIFICATION_FAILED',unix=closed,evidence_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),all_owned_processes_closed=True))
    for name in ['PACKAGE_VERIFICATION.json','EVIDENCE_MANIFEST.json','PACKAGE_CLOSED.json']:shutil.copy2(P/name,review/name)
    mirror=json.loads((review/'REVIEW_MIRROR.json').read_text());mirror['canonical_evidence_manifest_sha256']=sha(P/'EVIDENCE_MANIFEST.json')
    (review/'REVIEW_MIRROR.json').write_text(json.dumps(mirror,indent=2,ensure_ascii=False)+'\n')
    assert verification['status']=='PASS','CLOSEOUT_DEADLINE_EXCEEDED'
    print('PACKAGE_VERIFICATION_PASS',len(inventory),'FILES',len(starts),'STARTS','STOPPED',flush=True)
if __name__=='__main__':main()
