from analyze import *

REVIEW=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/force_motion_coupling_diagnosis_v2')
def loadj(n):return json.loads((P/n).read_text())

def main():
    if Path(__file__).resolve()!=P/'control/finish_qa.py':shutil.copy2(__file__,P/'control/finish_qa.py')
    extra=P/'audit/inspection_sources';extra.mkdir(exist_ok=True)
    for f in (REVIEW/'control').glob('*.py'):
        if f.name.startswith(('inspect_','check_')):shutil.copy2(f,extra/f.name)
    lag=loadj('LAG_ANALYSIS.json')['cases'];rise=loadj('FORCE_RISE_LAGS.json')['cases'];contrast=loadj('PAIRED_DIFFERENCE_LAGS.json');summary=[]
    for label in ['B0','18D']:
        for ph in ['OUTBOUND','RETURN']:
            row={'case':label,'phase':ph,'acceleration_variation_firstdiff_SG':[],'force_rise_lag':{}}
            for fw in [0,21,101]:
                z=lag[label][f'0.05|SG{fw}|{ph}|acceleration_variation_rate|first_difference'];row['acceleration_variation_firstdiff_SG'].append({'window_samples':fw,'peak_r':z['peak_abs_r'],'peak_lag_s':z['peak_lag_s']})
            for feat in FEATURES[:3]:
                z=rise[label][f'0.05|{ph}|{feat}'];row['force_rise_lag'][feat]={k:z[k] for k in ['zero_lag_r','peak_abs_r','peak_lag_s']}
            if label=='18D':
                row['paired_difference']= {feat:{k:contrast[label][f'0.05|{ph}|{feat}'][k] for k in ['zero_lag_r','peak_abs_r','peak_lag_s']} for feat in FEATURES[:3]}
            summary.append(row)
    put('audit/SENSITIVITY_SUMMARY.json',summary);print('SENSITIVITY',json.dumps(clean(summary)),flush=True)
    qa={'status':'PASS','figures_inspected':['01_core_common_timeline','02_legal_common_timeline','03_force_and_18D_local_benefit','04_anomaly_force_motion_torque','05_phase_lag_first_difference','06_trend_sensitivity','07_historical_force_motion_tradeoff'],'method':'actual PNG image inspection through view_image, common axes/units/events/legends checked; SVG versions also retained','repair':'removed overlapping point annotations in figure07; no scientific data changes','limitations':'tiny differences of legal microperturbations cannot be resolved in full-task overlay; precise deltas are retained in JSON/CSV and anomaly close-up'}
    put('audit/VISUAL_QA.json',qa)
    v=loadj('PACKAGE_VERIFICATION.json');v['visual_QA']='PASS; seven actual PNGs inspected, figure07 labels repaired';put('PACKAGE_VERIFICATION.json',v)
    ac=loadj('EXECUTION/ATTEMPT_ACCOUNTING.json');qa_runs=ac.get('postprocessing',{}).get('final_QA_runs',0)+1;ac['accounting_scope']='Three main-analysis invocations (two failed audits, one completed recovery); separate archive postprocessing and visual render counts below; inspection commands are not physical/scientific candidates.';ac['postprocessing']={'enrich_runs':1,'figure_generation_runs':3,'closeout_runs':1,'final_QA_runs':qa_runs};put('EXECUTION/ATTEMPT_ACCOUNTING.json',ac)
    manifest=loadj('SOURCE_MANIFEST.json');SOURCE_FILES.update(manifest['files'])
    for name in ['code/explore_common.py','code/analyze_matched.py','code/stream_runtime_evidence.py','control/diagnostics.py','control/anomaly_mechanism.py','control/raw_audit_base.py']:
        source(OLD/name)
    manifest['files']=SOURCE_FILES;manifest['hash_registration_scope']='Successful recovery reconstructed source hash registry before final protection comparison. Initial failed analysis held its source hashes in memory only. These are not represented as a complete T0 byte snapshot.';put('SOURCE_MANIFEST.json',manifest)
    protect=loadj('audit/FINAL_PROTECTION.json');protect['consumed_source_hashes']=len(SOURCE_FILES);protect['source_hash_registration_scope']=manifest['hash_registration_scope'];protect['additional_readonly_audit_source_files']=6;put('audit/FINAL_PROTECTION.json',protect)
    report=(P/'REPORT.md').read_text();report=report.replace('保护审核范围和结果见`audit/FINAL_PROTECTION.json`。','主仓库的初始Git/metadata快照与最终一致；来源SHA登记在成功恢复后重建，最终核对一致，不冒充完整T0字节快照。9个代表case有多尺度lag、7个候选有paired差值lag，20个case均有完整指标与累计曲线。保护审核范围和结果见`audit/FINAL_PROTECTION.json`。')
    rise_summary='直接以 motion level 对 force-rise（窗口均力的后向一阶差分）做lag时，也存在应保留的正证据：50 ms窗的 acceleration-variation 在B/18D OUTBOUND分别为 r=+0.417/+0.388，最大峰均在+0.10 s；RETURN为 −0.313/−0.305，同在+0.10 s。100/250 ms窗口大体保留OUT正、RETURN负的结构，但250 ms的峰lag已移到+0.25 s；500 ms结果的峰lag和18D RETURN的符号进一步变化。它提示phase-dependent时序关联，不能称“完全没有force–motion关系”，也不能作为跨phase统一降低variation即可降力的规则。paired candidate−B差值没有得到稳定同向领先关系；SG敏感性也保留在audit/SENSITIVITY_SUMMARY。这些现象优先指向phase/姿态/reference/tracking与allocator的共同驱动，独立因果机制仍UNRESOLVED。'
    if rise_summary not in report:
        shutil.copy2(P/'REPORT.md',P/'audit/REPORT_PRE_FORCE_RISE_SUMMARY.md')
        report=report.replace('**CORRELATIONAL：**',rise_summary+'\n\n**CORRELATIONAL：**',1)
    linkline='[核心共同时间轴](figures/01_core_common_timeline.png) · [force与18D局部收益](figures/03_force_and_18D_local_benefit.png) · [异常窗口](figures/04_anomaly_force_motion_torque.png) · [分phase滞后](figures/05_phase_lag_first_difference.png)'
    if linkline not in report:report+='\n'+linkline+'\n'
    (P/'REPORT.md').write_text(report)
    omitted=['audit/git_staged_before.txt']
    put('REVIEW_EXPORT.json',{'canonical_package':str(P),'windows_review_directory':str(REVIEW),'omitted_large_snapshot_files':omitted,'raw_archives':'stay at source paths and hashes in SOURCE_MANIFEST; complete selected receipts and all20 derived motion/force arrays are included','extra_review_inspection_scripts':'local initial inspection scripts preserved canonically in audit/inspection_sources; not physical runners'})
    inventory={str(f.relative_to(P)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in P.rglob('*') if f.is_file() and f.name not in ['PACKAGE_MANIFEST.json','STORAGE.json']}
    put('PACKAGE_MANIFEST.json',{'files':inventory,'excluded':['PACKAGE_MANIFEST.json','STORAGE.json']});put('STORAGE.json',{'logical_bytes':sum(v['bytes'] for v in inventory.values()),'file_count':len(inventory),'raw_archives_shared_by_hash_reference':True})
    for rel in inventory:
        if rel in omitted:continue
        target=REVIEW/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,target)
    for name in ['PACKAGE_MANIFEST.json','STORAGE.json']:shutil.copy2(P/name,REVIEW/name)
    # Exact manifest and review-copy verification, all results including failures.
    assert all(sha(P/rel)==v['sha256'] for rel,v in inventory.items())
    assert all(sha(REVIEW/rel)==v['sha256'] for rel,v in inventory.items() if rel not in omitted)
    print('FINAL_PACKAGE_AND_REVIEW_HASHES_PASS',len(inventory),'files',flush=True)

if __name__=='__main__':main()
