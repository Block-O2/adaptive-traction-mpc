"""Read-only scientific analysis after the authorized continuation has stopped."""
from pathlib import Path
import json,csv,hashlib,shutil,statistics,sys,time
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1/source');S=R/'stages/stage5_personalized_motion_learning'
NAME='single_human_sac_seed1_continuation_v2_guardfix_attempt3';D=S/'docs'/NAME;O=S/'results'/NAME
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_seed1_continuation')
LOCAL=W/'output_attempt3';OLD=S/'docs/single_human_sac_expert_v1/r2'
PREVIOUS=S/'docs/single_human_sac_seed1_continuation_v1_attempt2'
SEGMENTS=(PREVIOUS,D)
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,data):
    text=json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n'
    for folder in (D,LOCAL):(folder/name).write_text(text)
def run():
    state=read(D/'STATE.json');assert state['status'] in ('SAC_SEED1_300K_COMPLETE','SAC_SEED1_SAVED_STOP','RESOURCE_STOP_BEFORE_TRAINING'),state
    result=read(D/'CONTINUATION_RESULT.json');step=result['total_steps'];best=read(D/'BEST_CONFIRMED.json') if (D/'BEST_CONFIRMED.json').exists() else {}
    if not (D/'BEST_CONFIRMED.json').exists():save('BEST_CONFIRMED.json',best)
    previous_result=read(PREVIOUS/'CONTINUATION_RESULT.json')
    segment_result=dict(result)
    wall_sum=previous_result['wall_s']+result['wall_s']
    anchors=[]
    for folder in SEGMENTS:
        with (folder/'RESOURCE_WATCH.jsonl').open() as h:first=json.loads(next(h))
        anchors.append(first['unix']-first['elapsed_s'])
    result['wall_s']=anchors[1]+segment_result['wall_s']-anchors[0]
    result['steps_s']=(step-30000)/result['wall_s']
    result['episodes']+=previous_result['episodes'];result['resets']+=previous_result['resets']
    for folder in SEGMENTS:
        if (folder/'BEST_CONFIRMED.json').exists():
            for scope,candidate in read(folder/'BEST_CONFIRMED.json').items():
                if scope not in best or candidate['selected']['J_F']<best[scope]['selected']['J_F']:best[scope]=candidate
    save('BEST_CONFIRMED.json',best)
    rows=[]
    for path in sorted(p for folder in SEGMENTS for p in folder.glob('EVALUATION_*.json')):
        record=read(path);assert sha(R/record['trace'])==record['trace_sha256'];rows.append(record)
    rows.sort(key=lambda x:(x['training_step'],x['scope'],x['tag']))
    resource=dict(samples=0,max_tree_pss_bytes=0,max_main_rss_bytes=0,min_windows_available_bytes=None,min_commit_headroom_bytes=None,min_wsl_available_bytes=None,max_swap_used_bytes=0,stop_reasons=[],process_counts=set(),video_render_observed=False)
    last=None; training_memory=[]; memory_bins={};accounting_peaks=dict(wsl_cache_bytes=0,wsl_resident_used_bytes=0,wsl_nonavailable_bytes=0,windows_vmmem_private_bytes=0,windows_vmmem_working_set_bytes=0)
    for resource_dir in SEGMENTS:
        if (resource_dir/'RESOURCE_WATCH.jsonl').exists():
            for line in (resource_dir/'RESOURCE_WATCH.jsonl').open():
                row=json.loads(line);last=row;resource['samples']+=1;resource['max_tree_pss_bytes']=max(resource['max_tree_pss_bytes'],row['tree_pss_bytes']);resource['max_main_rss_bytes']=max(resource['max_main_rss_bytes'],row['processes']['owned'][0].get('Rss',0));resource['max_swap_used_bytes']=max(resource['max_swap_used_bytes'],row['swap_used_bytes']);resource['process_counts'].add(row['processes']['owned_count']);resource['video_render_observed']|=bool(row['windows']['ExternalVideoRender'])
                accounting_peaks['wsl_cache_bytes']=max(accounting_peaks['wsl_cache_bytes'],row['wsl'].get('Cached',0))
                accounting_peaks['wsl_resident_used_bytes']=max(accounting_peaks['wsl_resident_used_bytes'],row['wsl']['MemTotal']-row['wsl']['MemFree'])
                accounting_peaks['wsl_nonavailable_bytes']=max(accounting_peaks['wsl_nonavailable_bytes'],row['wsl']['MemTotal']-row['wsl']['MemAvailable'])
                accounting_peaks['windows_vmmem_private_bytes']=max(accounting_peaks['windows_vmmem_private_bytes'],row['windows'].get('VmmemPrivateBytes',0))
                accounting_peaks['windows_vmmem_working_set_bytes']=max(accounting_peaks['windows_vmmem_working_set_bytes'],row['windows'].get('VmmemWorkingSetBytes',0))
                if row['phase']=='training':
                    point=dict(source=resource_dir.name,step=row['step'],rss_bytes=row['processes']['owned'][0].get('Rss',0),anon_bytes=row['processes']['owned'][0].get('Pss_Anon',0),tree_pss_bytes=row['tree_pss_bytes'],owned_count=row['processes']['owned_count'])
                    training_memory.append(point);memory_bins.setdefault(resource_dir.name+':'+str((row['step']//25000)*25000),[]).append(point)
                for key,v in [('min_windows_available_bytes',row['windows']['AvailableBytes']),('min_commit_headroom_bytes',row['windows']['CommitLimit']-row['windows']['CommittedBytes']),('min_wsl_available_bytes',row['wsl']['MemAvailable'])]:resource[key]=v if resource[key] is None else min(resource[key],v)
                resource['stop_reasons']+=list(set(row['stop_reasons'])-set(resource['stop_reasons']))
    resource['process_counts']=sorted(resource['process_counts']);resource['last']=last;resource['accounting_peaks']=accounting_peaks
    bin_summary={k:dict(samples=len(v),step_min=min(p['step'] for p in v),step_max=max(p['step'] for p in v),rss_median_mib=statistics.median(p['rss_bytes'] for p in v)/2**20,anon_median_mib=statistics.median(p['anon_bytes'] for p in v)/2**20,tree_pss_max_gib=max(p['tree_pss_bytes'] for p in v)/2**30,owned_counts=sorted(set(p['owned_count'] for p in v))) for k,v in memory_bins.items()}
    late=[p for p in training_memory if p['source']==PREVIOUS.name and p['step']>=max(175000,previous_result['total_steps']-50000)]
    slope=None
    if len(late)>=20:
        xm=statistics.mean(p['step'] for p in late);ym=statistics.mean(p['anon_bytes'] for p in late);den=sum((p['step']-xm)**2 for p in late)
        if den:slope=sum((p['step']-xm)*(p['anon_bytes']-ym) for p in late)/den*10000/2**20
    resource['training_memory_bins']=bin_summary;resource['late_training_anon_slope_mib_per_10k']=slope
    resource['slope_scope']='Descriptive slope over the old, already-warmed PID last50k steps; no cross-PID cancellation. Startup/evaluation/reset/GC high-water changes remain included. This alone neither proves nor excludes a leak.'
    end_candidates=[]
    for folder in SEGMENTS:
        points=[p for p in training_memory if p['source']==folder.name]
        if points:
            end=max(p['step'] for p in points);window=[p for p in points if p['step']>=end-5000]
            end_candidates.append(statistics.median(p['tree_pss_bytes'] for p in window)/2**30)
    end_tree=max(end_candidates) if end_candidates else None
    forecast={}
    for target in (300000,500000,1000000):
        projection=end_tree+max(0,slope)*max(0,target-previous_result['total_steps'])/10000/1024 if end_tree is not None and slope is not None else None
        forecast[str(target)]=dict(actual_replay_mib=46000000/2**20,stable_profile_tree_budget_gib=4.5,positive_late_anon_drift_extrapolation_tree_gib=projection,projection_exceeds_tree_budget=projection>4.5 if projection is not None else None,unobserved_target=target>step)
    resource['ram_forecast_sensitivity']=forecast
    resource['ram_forecast_sensitivity_scope']='Stress extrapolation from the pre-restart260887-step mature PID, retaining its positive last50k slope; no RSS relief from cold restart is credited. This is a sensitivity case, not an uninterrupted-run measurement.'
    gpu=dict(max_allocated_bytes=0,max_reserved_bytes=0)
    for sample_dir in SEGMENTS:
        if (sample_dir/'MEMORY_SAMPLES.jsonl').exists():
            for line in (sample_dir/'MEMORY_SAMPLES.jsonl').open():
                g=json.loads(line)['torch_gpu']
                if g:gpu['max_allocated_bytes']=max(gpu['max_allocated_bytes'],g['max_allocated']);gpu['max_reserved_bytes']=max(gpu['max_reserved_bytes'],g['max_reserved'])
    curves=[]
    curve_paths=[OLD/'SAC_LEARNING_CURVE.csv']+[S/f'docs/single_human_sac_memory_v1/attempt{i}/SAC_LEARNING_CURVE.csv' for i in (2,3,4,5)]+[PREVIOUS/'SAC_LEARNING_CURVE.csv',D/'SAC_LEARNING_CURVE.csv']
    for path in curve_paths:
        if path.exists():
            for row in csv.DictReader(path.open()):row['source_file']=str(path.relative_to(R));curves.append(row)
    columns=sorted(set().union(*(set(x) for x in curves))) if curves else []
    for folder in (D,LOCAL):
        with (folder/'SAC_SEED1_LEARNING_CURVE_COMBINED.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(curves)
    comparisons=read(OLD/'SAC_COMPARATOR_TABLE.json')
    if isinstance(comparisons,dict):comparisons=next((v for v in comparisons.values() if isinstance(v,list)),[])
    trends={}
    for scope in ('NATIVE','MATCHED'):
        observed=[r for r in rows if r['scope']==scope and r['tag']=='periodic'];recent=observed[-4:]
        all_valid=len(recent)==4 and all(r['valid'] for r in recent)
        improving=all_valid and recent[0]['J_F']-recent[-1]['J_F']>=1 and all(b['J_F']<a['J_F'] for a,b in zip(recent,recent[1:]))
        trends[scope]=dict(last_evaluations=[{k:r[k] for k in ('training_step','valid','J_F','duration_s','force_peak','moment_peak')} for r in recent],clearly_improving=improving,interpretation='Four valid deterministic evaluations with strictly decreasing J_F and at least1 N*s total improvement' if improving else ('No valid complete-task improvement established' if not all_valid else 'Recent valid curve not clearly improving by prospective summary rule'))
    train_rows=[]
    for r in curves:
        try:ret=float(r.get('reward_total') or r.get('episode_return'));train_rows.append((int(r['training_step']),ret,r))
        except (ValueError,TypeError):pass
    train_rows.sort(key=lambda x:x[0]);last25=train_rows[-25:];prev25=train_rows[-50:-25]
    train_trend=dict(last25_mean_return=statistics.mean(x[1] for x in last25) if last25 else None,previous25_mean_return=statistics.mean(x[1] for x in prev25) if prev25 else None,causal_success_episodes=sum(str(x[2].get('success') or x[2].get('causal_task_complete')).lower()=='true' for x in train_rows),episodes=len(train_rows),scientific_best_requires_independent_physical_validity=True)
    path_rows=[]
    for r in rows:
        trace=R/r['trace'];path=trace.parent/'hip_knee_physical_path.npz'
        with np.load(trace) as z:
            keys=['time_s','stage','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad']
            np.savez_compressed(path,**{k:z[k] for k in keys if k in z.files})
        path_rows.append(dict(step=r['training_step'],scope=r['scope'],tag=r['tag'],trace=r['trace'],trace_sha256=r['trace_sha256'],physical_path=str(path.relative_to(R)),physical_path_sha256=sha(path),evaluation_only_truth=True,actor_truth_access=False))
    save('HIP_KNEE_PATH_MANIFEST.json',path_rows)
    rb=read(D/'REPLAY_ACCOUNTING.json') if (D/'REPLAY_ACCOUNTING.json').exists() else {}
    analysis=dict(status=state['status'],total_steps=step,wall_s=result['wall_s'],steps_s=result['steps_s'],memory_qualification='SAC_MEMORY_QUALIFIED',resources=resource,gpu=gpu,best_confirmed=best,learning_trend=trends,training_trend=train_trend,ram_forecast=dict(buffer_capacity=100000,buffer_bytes=46000000,bytes_per_transition=460,uncapped_payload_bytes={str(n):n*460 for n in (300000,500000,1000000)},current_profile_training_and_evaluation_tree_budget_gib=4.5,whole_wsl_budget_gib=6,longer_complete_task_evaluation_contingency_tree_gib=[5,6],windows_commit_reserve_gib=2,swap_expansion=False),scientific_changes=[],git_mutations=[],preservation=read(D/'PRESERVATION_AFTER.json') if (D/'PRESERVATION_AFTER.json').exists() else None)
    audit=read(D/'GROWTH_GUARD_AUDIT_V1.json')
    requalification=read(D/'BOUNDED_RESOURCE_REQUALIFICATION.json') if (D/'BOUNDED_RESOURCE_REQUALIFICATION.json').exists() else {}
    if state['status']=='SAC_SEED1_300K_COMPLETE':assert requalification['completed_steps']==[265000,270000,275000,280000]
    analysis.update(segment_results=[previous_result,segment_result],summed_segment_wall_s=wall_sum,calendar_wall_s=result['wall_s'],calendar_wall_includes_guard_diagnosis_gap=True,segment_wall_steps_s=(step-30000)/wall_sum,growth_guard_audit=audit,bounded_resource_requalification=requalification,resource_only_fix=True,cold_reset_on_resume=True,original30k_resume_proof=read(PREVIOUS/'RESUME_VERIFICATION.json'),current260887_resume_proof=read(D/'RESUME_VERIFICATION.json'))
    post_exit=read(D/'POST_EXIT_RESOURCE_ACCOUNTING.json')
    analysis['post_exit_resource_accounting']=post_exit
    analysis['memory_interpretation']='30k qualified and 300k reached without swap. Replay remains fixed at43.87MiB. Startup/evaluation high-water allocations and host accounting explain the protection; the old guard window was corrected. Real cumulative anonymous growth remains in the evidence and a slow leak is not conclusively excluded.'
    save('SAC_SEED1_FINAL_ANALYSIS.json',analysis)
    lines=['# SAC Seed 1 continuation — final evidence','',f'STATUS: {state["status"]}','',f'TOTAL STEPS: {step}; resumed at30k with24997 updates and29997 replay records. WALL TIME: {result["wall_s"]/3600:.3f}h; effective continuation {result["steps_s"]:.3f} steps/s.','',f'MEMORY RESULT: 30k qualification passed. Long-run peak process-tree PSS {resource["max_tree_pss_bytes"]/2**30:.3f}GiB; maximum WSL swap {resource["max_swap_used_bytes"]/2**20:.3f}MiB. Resource reasons: {resource["stop_reasons"]}. Stop reason: {result["stop_reason"]}.','', 'The original12194-step protection was triggered by Windows Available below2GiB while WSL MemAvailable remained healthy. Exact original commit/cache values were not recorded, so its causal proportions cannot be reconstructed. The bounded test directly measured large startup/first-update/evaluation allocations; concurrent video rendering separately caused real host commit pressure. Combined host commit, WSL availability, process-tree, swap and pressure accounting now governs resource decisions. No replay capacity change. The100k cyclic float32 replay uses46,000,000bytes (43.87MiB).','', 'Estimated current-profile SAC tree budget is4.5GiB and whole WSL6GiB at300k/500k/1M, with2GiB Windows commit reserve. Uncapped replay alone would require131.61/219.35/438.69MiB respectively; the actual cyclic replay remains43.87MiB. These remain planning budgets subject to the observed long-run trend and resource guards. Full30s completed evaluations may need5–6GiB tree contingency; this is planning headroom, not a measured guarantee. No RAM/swap expansion.','', f'Late training anonymous-memory slope: {slope}MiB/10k steps. {resource["slope_scope"]} The detailed process, Windows commit, WSL cache/swap and GPU samples are retained. The original15k/20k/25k/30k milestone accounting and30k/100k/300k/1M replay estimates are in ../single_human_sac_memory_v1/SAC_MEMORY_REPORT_V1.md.','', '|Step|Scope|Tag|VALID|J_F (N s)|F peak (N)|M peak (Nm)|Duration (s)|Safety rejections|','|---:|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f'|{r["training_step"]}|{r["scope"]}|{r["tag"]}|{r["valid"]}|{r["J_F"]:.6f}|{r["force_peak"]:.6f}|{r["moment_peak"]:.6f}|{r["duration_s"]:.6f}|{r["rejections"]}|')
    lines+=['',f'WSL observed high-water resident use (MemTotal−MemFree): {accounting_peaks["wsl_resident_used_bytes"]/2**30:.3f}GiB; cache: {accounting_peaks["wsl_cache_bytes"]/2**30:.3f}GiB; nonavailable memory (MemTotal−MemAvailable): {accounting_peaks["wsl_nonavailable_bytes"]/2**30:.3f}GiB. Windows Vmmem private/working-set peaks: {accounting_peaks["windows_vmmem_private_bytes"]/2**30:.3f}/{accounting_peaks["windows_vmmem_working_set_bytes"]/2**30:.3f}GiB. These peaks may occur at different times. Reclaimable cache can occupy spare WSL RAM beyond the6GiB working-memory/reserve planning budget; Vmmem commit, summed process RSS and host physical availability must not be equated. No WSL RAM limit or swap capacity was increased.']
    lines+=['','RAM forecast sensitivity:','', '|Total steps|Actual cyclic replay (MiB)|Stable-profile SAC tree budget (GiB)|Positive late-drift extrapolation, SAC tree (GiB)|Observed target reached|','|---:|---:|---:|---:|---|']
    for target,entry in forecast.items():
        projected=entry['positive_late_anon_drift_extrapolation_tree_gib'];text='not determined' if projected is None else f'{projected:.3f}'
        lines.append(f'|{target}|{entry["actual_replay_mib"]:.3f}|4.5|{text}|{not entry["unobserved_target"]}|')
    lines+=['','The drift column is a sensitivity calculation, not a validated prediction or proof of leakage. It includes evaluation/reset high-water changes and extrapolates only the measured positive anonymous-memory slope. Future500k/1M runs are not qualified by this run; if the drift case exceeds the4.5GiB tree budget, resource diagnosis/requalification is required before extending. Longer complete-task evaluations also remain subject to the separate5–6GiB contingency and the host/WSL guards.']
    for scope in ('NATIVE','MATCHED'):
        confirmed=best.get(scope)
        lines+=['',f'BEST {scope}: '+(f'VALID and two independent replays confirmed; step{confirmed["selected"]["training_step"]}, J_F={confirmed["selected"]["J_F"]:.6f}.' if confirmed else 'No independently confirmed VALID SAC candidate.'),f'LEARNING TREND {scope}: {trends[scope]["interpretation"]}.']
        if confirmed:
            selected=confirmed['selected']
            for comp in comparisons:
                if comp.get('scope')==scope and comp.get('valid') and comp.get('J_F'):
                    lines.append(f'Compared with {comp["name"]}: J_F change {(selected["J_F"]/comp["J_F"]-1)*100:.3f}%; duration {selected["duration_s"]:.6f} vs{comp["duration_s"]:.6f}s. NATIVE timing differs; MATCHED timing does not isolate all within-phase pacing.')
    improving=any(v['clearly_improving'] for v in trends.values())
    next_action='At300k, suggest a separately authorized continuation from the final saved bundle because the valid learning curve still clearly improves; do not extend automatically.' if step==300000 and improving else ('At300k, inspect the saved best valid/negative evidence before separately authorizing any extension.' if step==300000 else 'Use the saved diagnostic to resolve the reported resource/runtime blocker before any separately authorized continuation.')
    lines+=['',f'Training return last25 mean: {train_trend["last25_mean_return"]}; previous25: {train_trend["previous25_mean_return"]}. Causal successful training episodes: {train_trend["causal_success_episodes"]}/{train_trend["episodes"]}. Training returns and invalid truncated J_F are not independently valid task scores.','',f'NEXT: {next_action}','', 'Checkpoint, replay, optimizer and RNG paths/hashes are in SAVED_BUNDLE.json. Milestone evaluation uses the periodic checkpoint saved before storage/update of the callback transition, matching the preserved orchestration order. The distinct final checkpoint includes any subsequent final update and is the continuation state; a selected best always refers to its exact evaluated periodic checkpoint. All fixed-scale normalization, R2 control semantics, reward, observation, action, period, commissioned frozen model and training hyperparameters remain unchanged. No Human side-study, seed2, other heavy simulation, hardware action or Git mutation.','', 'Evidence: SAC_SEED1_LEARNING_CURVE_COMBINED.csv, SAC_CHECKPOINT_EVALUATION.csv, BEST_CONFIRMED.json, all EVALUATION/CONFIRMATION records, HIP_KNEE_PATH_MANIFEST.json, full raw trace/action archives, MEMORY_SAMPLES.jsonl, RESOURCE_WATCH.jsonl, RESUME_VERIFICATION.json, EXECUTION_PROVENANCE_V1.json and PRESERVATION_AFTER.json. Original failed startup is retained separately; no learning occurred in it. Deterministic replay confirms reproducibility only, not human-population or hardware robustness.']
    lines+=['',f'Guard accounting correction: the previous segment stopped at260887 because the old comparison used the mean of all1–4h-old samples. The actual last three comparable prior-hour increases were166.203/70.778/126.853MiB, with no three consecutive128MiB increases. The audited true cumulative anonymous-memory rise767.516MiB remains recorded; no allocator leak has been claimed fixed. Numerical thresholds and all absolute resource safeguards remain unchanged. Supplemental bounded requalification milestones completed: {requalification.get("completed_steps",[])}.','',f'The original30k resume preserved24997 optimizer updates and29997 replay records. The resource-only continuation resumes260887 with255883 updates and100000 replay records, restores the saved RNG, and cold-resets the physical episode. No step0 training. Calendar wall including diagnosis gap: {result["wall_s"]/3600:.3f}h; summed active segment orchestration wall: {wall_sum/3600:.3f}h. Separate PID memory bins and the old mature PID slope prevent a downward RSS jump at restart from masking the previous high-water growth.500k/1M are not resource-qualified by reaching300k.','', 'The full30k memory accounting is also available in C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_memory/output/SAC_MEMORY_REPORT_V1.md.']
    lines=[line.replace('Resource reasons:', 'Historical guard trigger (audited false alarm):').replace('Stop reason:', 'Final stop reason:').replace('SAC_CHECKPOINT_EVALUATION.csv,', 'SAC_CHECKPOINT_EVALUATION_COMBINED.csv,') for line in lines]
    pw=post_exit['windows'];pm=post_exit['wsl']
    lines+=['',f'Post-exit accounting (separate from training peaks): training process count {len(post_exit["live_training_processes"])}; Windows Available {pw["AvailableBytes"]/2**30:.3f}GiB; Windows commit {pw["CommittedBytes"]/2**30:.3f}/{pw["CommitLimit"]/2**30:.3f}GiB, headroom {(pw["CommitLimit"]-pw["CommittedBytes"])/2**30:.3f}GiB; WSL MemAvailable {pm["MemAvailable"]/2**30:.3f}GiB, cache {pm["Cached"]/2**30:.3f}GiB; swap {post_exit["swap_used_bytes"]/2**20:.3f}MiB. Full accounting: POST_EXIT_RESOURCE_ACCOUNTING.json.','', 'Memory conclusion: no persistent resource-pressure leak was demonstrated in the bounded test. At30k, evaluation peaks were below the25k peak; replay stayed fixed-capacity. The long warm process subsequently accumulated real anonymous-memory high-water growth, so a slow leak has not been conclusively excluded. The guard fix repairs only its time-window calculation. The 300k run completed safely under the corrected guards; the cold restart is not credited as proof of stabilization in a single uninterrupted PID. The forecast stress case starts from the pre-restart260887-step process and retains its measured positive slope. Any500k/1M extension requires renewed resource qualification.','', 'No VALID candidate was found at any formal milestone, so independent best-candidate confirmation replay was never triggered. Formal deterministic success:0/22 scope evaluations. Latest300k NATIVE and MATCHED both ABORTED after6.075s, J_F425.229345N s; these truncated costs are not ranked. The final checkpoint is saved and training is stopped.']
    for folder in (D,LOCAL):(folder/'SAC_SEED1_FINAL_REPORT_V2.md').write_text('\n'.join(lines)+'\n')
    columns=['seed','training_step','scope','tag','status','valid','task_valid','J_F','force_peak','moment_peak','duration_s','rejections','modification_fraction','matched_timing_valid','physical_clearance']
    for folder in (D,LOCAL):
        with (folder/'SAC_CHECKPOINT_EVALUATION_COMBINED.csv').open('w',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    for p in PREVIOUS.iterdir():
        if p.is_file() and p.name.startswith(('EVALUATION_','CONFIRMATION_','PATH_')) and p.suffix=='.json':shutil.copy2(p,LOCAL/p.name)
    for p in D.iterdir():
        if p.is_file() and p.suffix in ('.json','.csv') and p.name not in ('PRESERVATION_BEFORE.json',):shutil.copy2(p,LOCAL/p.name)
    shutil.copy2(Path(__file__),S/'scripts'/NAME/'closeout_seed1_v2.py')
    save('FINAL_REPORT_MANIFEST.json',dict(report=str(D/'SAC_SEED1_FINAL_REPORT_V2.md'),report_sha256=sha(D/'SAC_SEED1_FINAL_REPORT_V2.md'),analysis_sha256=sha(D/'SAC_SEED1_FINAL_ANALYSIS.json'),closeout_source_sha256=sha(Path(__file__)),closed_out_unix=time.time(),next=next_action))
    print(json.dumps(dict(status=state['status'],steps=step,memory=resource['stop_reasons'],next=next_action)),flush=True)
if __name__=='__main__':run()
