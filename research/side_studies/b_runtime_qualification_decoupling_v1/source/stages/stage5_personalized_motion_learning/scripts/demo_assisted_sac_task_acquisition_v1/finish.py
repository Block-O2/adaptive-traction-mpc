"""Evidence reconciliation, storage retention, preservation audit; no training."""
from common import *
import collections

def read(name,default=None):
    p=D/name;return json.loads(p.read_text()) if p.exists() else default
def run():
    st=read('STATE.json');results=read('ARM_RESULTS.json',{});evaluations=read('ALL_EVALUATIONS.json',{'A':[],'B':[]});events=read('ALL_ACQUISITION_EVENTS.json',[])
    check_lock();pre=read('PRESERVATION_BEFORE.json')
    changed=[p for p,h in pre['files'].items() if not (R/p).is_file() or sha(R/p)!=h]
    index=subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)
    assert not changed,changed
    assert index==pre['index'],'Pre-existing Git index changed before staging'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pre['head']
    assert subprocess.check_output(['git','rev-parse','codex/single-human-sac-expert-v1'],cwd=R,text=True).strip()==pre['head']
    source=read('EXPERIMENT_SOURCE_LOCK.json')
    assert all(sha(Path(p))==h for p,h in source['files'].items())
    paired_complete=all(results.get(a,{}).get('steps')==50000 and results[a]['updates']==45000 for a in ('A','B'))
    first={}
    for arm in ('A','B'):
        first[arm]={}
        for endpoint in ('settled_outbound','hold_entry','hold_completed','return_entry','valid_complete'):
            selected=[e for e in events if e['arm']==arm and e['event']==endpoint]
            first[arm][endpoint]=min(selected,key=lambda x:(x['training_step'],x['scope']!='training')) if selected else None
        first[arm]['deterministic_by_scope']={scope:{endpoint:next((e for e in events if e['arm']==arm and e['scope']==scope and e['event']==endpoint),None) for endpoint in ('settled_outbound','hold_entry','hold_completed','return_entry','valid_complete')} for scope in ('NATIVE','MATCHED')}
    save('FIRST_SUCCESS_EVIDENCE.json',dict(first=first,events=events,settled_semantics='Existing causal task transition includes position+velocity+reference settled readiness. No numerical progress threshold substituted.',VALID='unchanged independent physical/scientific evaluator plus R2 scope eligibility'))
    prose('FIRST_SUCCESS_EVIDENCE.md','# First task-acquisition evidence\n\n'+json.dumps(first,ensure_ascii=False,indent=2)+'\n\nNull means the event was never observed within the fixed budget. Training (stochastic actor) and deterministic NATIVE/MATCHED events remain separately labeled. Position100% is not settled arrival.\n')
    best={}
    for scope in ('NATIVE','MATCHED'):
        candidates=[r for rows in evaluations.values() for r in rows if r['scope']==scope and r['independent_VALID']]
        best[scope]=min(candidates,key=lambda r:r['J_F']) if candidates else None
    save('BEST_VALID_POLICY_ANALYSIS.json',dict(best=best,ranking='complete independently VALID only, separate scopes',invalid_costs_not_ranked=True))
    prose('BEST_VALID_POLICY_ANALYSIS.md','# Best independently VALID policies\n\n'+json.dumps(best,ensure_ascii=False,indent=2)+'\n\nNo VALID candidate means no J_F ranking and no claimed expert performance. Checkpoints remain preserved even if subsequent performance regresses.\n')
    sampling={};phase={};health={}
    for arm in ('A','B'):
        path=O/f'{arm}_BATCH_SAMPLING.csv'
        if not path.exists():continue
        with path.open() as f:rows=list(csv.DictReader(f))
        nd=128 if arm=='B' else 0
        assert all(int(r['demo_count'])==nd and int(r['online_count'])==256-nd and float(r['demo_fraction'])==nd/256 for r in rows)
        assert all(int(r['online_steps'])>5000 for r in rows)
        assert all(sum(int(r['demo_'+p]) for p in ('OUTBOUND','HOLD','RETURN'))==nd for r in rows)
        assert all(sum(int(r['online_'+p]) for p in ('OUTBOUND','HOLD','RETURN'))==256-nd for r in rows)
        if arm in results:assert len(rows)==45000
        sampling[arm]=dict(status='PASS',batch_count=len(rows),min_demo_fraction=nd/256,max_demo_fraction=nd/256,demo_samples=sum(int(r['demo_count']) for r in rows),online_samples=sum(int(r['online_count']) for r in rows),demo_phase_counts={p:sum(int(r['demo_'+p]) for r in rows) for p in ('OUTBOUND','HOLD','RETURN')},online_phase_counts={p:sum(int(r['online_'+p]) for r in rows) for p in ('OUTBOUND','HOLD','RETURN')},first_learning_online_step=int(rows[0]['online_steps']) if rows else None,unique_demo_data=593 if nd else 0,repeated_samples_not_new_data=True)
        shutil.copy2(path,L/path.name)
        phase[arm]=results.get(arm,{}).get('online_phase',{})
        hp=D/f'{arm}_HEALTH.jsonl'
        histories=[json.loads(x) for x in hp.read_text().splitlines()] if hp.exists() else []
        episodep=D/f'{arm}_EPISODES.jsonl'
        episodes=[json.loads(x) for x in episodep.read_text().splitlines()] if episodep.exists() else []
        health[arm]=dict(snapshots=histories,all_finite=all(x['finite'] for x in histories),final=histories[-1] if histories else None,episode_termination_counts=dict(collections.Counter(x['abort_reason'] or x['status'] for x in episodes)),online_action= {k:results.get(arm,{}).get(k) for k in ('online_action_mean','online_action_std','online_near_bound_action_rate','previous_rejection_rate')},evaluation_near_bound_and_rejection=[{k:r[k] for k in ('training_step','scope','tag','near_bound_action_rate','rejection_rate','termination_reason')} for r in evaluations[arm]])
    save('PHASE_COVERAGE_COMPARISON.json',dict(online=phase,demo=dict(OUTBOUND=272,HOLD=35,RETURN=286),first=first))
    save('DEMO_SAMPLING_STATISTICS.json',sampling);save('SAC_HEALTH_COMPARISON.json',health)
    resources=[json.loads(x) for x in (D/'RESOURCE_WATCH.jsonl').read_text().splitlines()]
    peak=dict(tree_RSS_bytes=max(r['tree_rss_bytes'] for r in resources),tree_PSS_bytes=max(r['tree_pss_bytes'] for r in resources),swap_bytes=max(r['swap_used_bytes'] for r in resources),min_WSL_available_bytes=min(r['wsl']['MemAvailable'] for r in resources),min_Windows_available_bytes=min(r['windows']['AvailableBytes'] for r in resources),min_Windows_commit_headroom_bytes=min(r['windows']['CommitLimit']-r['windows']['CommittedBytes'] for r in resources),GPU_VRAM_MiB=max(float(r['gpu'].split(',')[0]) for r in resources),steps_s={a:results.get(a,{}).get('steps_s') for a in ('A','B')},windows_available_only_never_a_stop_gate=True,stop_reasons=[r['stop_reasons'] for r in resources if r['stop_reasons']])
    save('RESOURCE_SUMMARY.json',peak)
    comparators=read('COMPARATORS.json')
    if comparators is None:
        rows=json.loads((OLD/'SAC_COMPARATOR_TABLE.json').read_text())['rows']
        comparators=[{k:r.get(k) for k in ('name','scope','valid','J_F','force_mean','force_rms','force_peak','moment_integral','moment_peak','duration_s','phase_durations','trace','trace_sha256')} for r in rows if r['name'] in ('fixed_hip_lead','cem_reference_transfer','old_nominal')]
        assert all(sha(R/r['trace'])==r['trace_sha256'] for r in comparators)
        save('COMPARATORS.json',dict(rows=comparators,scope='historical same R2 qualified wrapper comparators, not new independent runs; no cross-scope pooling'))
    avalid=any(r['independent_VALID'] for r in evaluations['A']);bvalid=any(r['independent_VALID'] for r in evaluations['B'])
    aprogress=bool(first['A']['hold_entry']);bprogress=bool(first['B']['hold_entry'])
    if bvalid and not avalid:effect='B succeeds and A fails: evidence supports demo replay aiding task acquisition for this paired seed; no unique-cause claim.'
    elif avalid and bvalid:effect='Both succeed: task acquired in both arms; seed/optimization variability can also contribute to historical scratch300k failure.'
    elif bprogress and not bvalid:effect='B reaches settled HOLD/RETURN without VALID: positive acquisition signal, not completed task success.'
    else:effect='No completed task or settled phase progression benefit demonstrated at 50k; do not extend the budget automatically.'
    if aprogress and not bprogress:effect+=' Scratch shows more observed phase progression in this pair.'
    degradation={a:any(x['independent_VALID'] for x in evaluations[a]) and not any(x['independent_VALID'] for x in evaluations[a] if x['training_step']==50000 and x['tag']=='final') for a in ('A','B')}
    conclusion=dict(status='PAIRED_50K_COMPLETE_STOP' if paired_complete else 'PAUSED_PRESERVED_STOP',results=results,first=first,best=best,demo_effect=effect,success_then_regression=degradation,resource=peak,historical_scratch300k='Separate historical negative control; not the paired A50k arm',scientific_changes=[],limitations=['one previously exposed Human and one paired seed','Q counterfactual preference does not establish physical validity','demo train sampling changes data distribution, not original SAC objective'],next='Design a separate expert optimization study only after VALID acquisition' if bvalid else 'Analyze value propagation and absolute-target settling with these preserved checkpoints before any new training budget')
    save('TASK_ACQUISITION_COMPARISON.json',conclusion)
    lines=['# Demo-Assisted SAC Task Acquisition v1','',f'STATUS: {conclusion["status"]}','',effect,'','Historical Scratch300k, Paired Scratch50k (A) and Demo-Assisted50k (B) are distinct experiments. All R2 scientific variables stayed byte-identical. No old actor, critics, replay, optimizer or normalization statistics were inherited. Same fresh weights/empty Adam, seed20261003, first5000 random actions, hyperparameters, single advancing physics owner, evaluation schedule. B executed before A; no parallel training.','', 'The NATIVE teacher archive has593 transitions: OUTBOUND272/HOLD35/RETURN286. Exact same-wrapper reproduction verified every observation, raw/executed action, reward, next observation, phase and termination flag and remained independently VALID. B batches always128 demo+128 online; A standard256 online. No demo-triggered early updates, BC, teacher override, pretraining, curriculum or hyperparameter change. Original installed SB3 SAC.train remains unchanged.','', '|Arm|Online steps|Updates|First settled HOLD|First RETURN|First VALID|Final NATIVE|Final MATCHED|','|---|---:|---:|---|---|---|---|---|']
    def label(ev):return f'{ev["training_step"]} ({ev["scope"]}; {ev["rollout_id"]})' if ev else 'not observed'
    for a in ('A','B'):
        final={r['scope']:r for r in evaluations[a] if r['tag']=='final'}
        lines.append(f'|{a}|{results.get(a,{}).get("steps",st["steps"][a])}|{results.get(a,{}).get("updates","partial")}|{label(first[a]["hold_entry"])}|{label(first[a]["return_entry"])}|{label(first[a]["valid_complete"])}|{final.get("NATIVE",{}).get("termination_reason","not reached")}|{final.get("MATCHED",{}).get("termination_reason","not reached")}|')
    lines+=['','Only full independently VALID tasks enter J_F rankings. Max synchronized positional progress is diagnostic; arrival requires the original position, velocity and reference readiness. Online stochastic endpoints and deterministic scope-specific endpoints remain distinguished in FIRST_SUCCESS_EVIDENCE.json.','', '## Deterministic checkpoints','', '|Arm|Step|Scope|Tag|Reason|Progress|HOLD|RETURN|VALID|J_F (unranked when invalid)|','|---|---:|---|---|---|---:|---|---|---|---:|']
    for a in ('B','A'):
        for r in evaluations[a]:lines.append(f'|{a}|{r["training_step"]}|{r["scope"]}|{r["tag"]}|{r["termination_reason"]}|{r["max_synchronized_OUTBOUND_progress"]:.5f}|{r["entered_HOLD"]}|{r["started_RETURN"]}|{r["independent_VALID"]}|{r["J_F"]:.6f}|')
    lines+=['','## Best VALID by scope','',json.dumps(best,ensure_ascii=False,indent=2),'','## SAC diagnostics','',json.dumps({a:dict(final=health.get(a,{}).get('final'),terminations=health.get(a,{}).get('episode_termination_counts'),online_phase=phase.get(a),sampling=sampling.get(a),success_then_regression=degradation[a]) for a in ('A','B')},indent=2),'','Q teacher-vs-online-action differences are evaluated at the same teacher states and preserve RNG/optimizer. The alternative raw actions come from online replay; their Q preference is not a physical validation. Actor-vs-teacher MAE is measured on demo states, so it is not by itself evidence of visiting those states. Online replay phase counts and actual task events answer visitation. Actual actor/critic/entropy losses are appended throughout training, with separately labeled read-only Q/TD/entropy diagnostics.','', '## Resources','',json.dumps(peak,indent=2),'','Resource priority: preserve checkpoints and both buffers on pressure; corrected combined host/guest monitor. All high-frequency raw retention decisions are in RAW_DATA_MANIFEST.json. Scalar histories remain; only STATE carries the latest summary.','', '## Interpretation and next action','',effect,'','One exposed Human/one seed does not establish population robustness or unique causation. No cross-scope J_F comparison. Best checkpoint evidence remains available if later evaluations regress.','',conclusion['next'], '', 'STOP after the predefined paired50k budgets. No additional SAC/TQC/PPO/BC/curriculum/multi-Human/hardware work. No commit/push/merge.']
    prose('TASK_ACQUISITION_COMPARISON.md','\n'.join(lines)+'\n')
    # Retain first VALID, best VALID, first informative failure and final representative evaluation.
    keep=set()
    for a in ('A','B'):
        for r in evaluations[a]:
            if r['tag']=='final':keep.add(str((R/r['trace']).parent))
        for scope in ('NATIVE','MATCHED'):
            rows=[r for r in evaluations[a] if r['scope']==scope]
            for pred in (lambda r:r['independent_VALID'],lambda r:not r['independent_VALID']):
                chosen=next((r for r in rows if pred(r)),None)
                if chosen:keep.add(str((R/chosen['trace']).parent))
    for r in best.values():
        if r:keep.add(str((R/r['trace']).parent))
    for a in ('A','B'):
        ev=first[a]['valid_complete']
        if ev and ev['scope']=='training':
            keep.add(str(O/a/'training'/ev['rollout_id'].split('_online_')[1]))
        phasefail=next((p for p in sorted((O/a/'training').glob('episode_*')) if (p/'trace.npz').exists()),None)
        if phasefail:keep.add(str(phasefail))
    raw=[]
    # Delete only named raw files created inside this new campaign root, after computing hashes.
    removable={'trace.npz','runtime_artifacts.json.gz','runtime_artifacts.json','learning_transitions.jsonl'}
    for p in sorted(O.rglob('*')):
        if not p.is_file():continue
        assert p.resolve().is_relative_to(O.resolve())
        entry=dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),retained=True)
        if p.name in removable and str(p.parent) not in keep:
            entry.update(retained=False,reason='preregistered compact retention; summary/scalars/policy-rate action evidence retained');p.unlink()
        raw.append(entry)
    save('RAW_DATA_MANIFEST.json',dict(root=str(O),entries=raw,retained_high_frequency_directories=sorted(keep),historical_evidence_untouched=True,online_buffers_and_sampler_rng_preserved=True))
    save('PRESERVATION_VERIFICATION.json',dict(status='PASS',protected_files=len(pre['files']),changed_files=changed,HEAD_unchanged=True,old_branch_ref_unchanged=True,preexisting_index_unchanged_before_staging=True,experimental_sources_unchanged_during_formal=True,paired_initialization=read('PAIRED_INITIALIZATION_AUDIT.json'),batch_audit=sampling))
    st.update(status=conclusion['status'],phase='REPORT_COMPLETE_STOP',completed_unix=time.time(),next='STOP. No automatic additional experiment.',demo_effect=effect,best={s:dict(arm=r['arm'],step=r['training_step'],J_F=r['J_F']) if r else None for s,r in best.items()},commit=False,push=False,merge=False)
    save('STATE.json',st)
    # Stage new compact files individually; pre-existing staged entries must be identical.
    for p in (W/NAME).glob('*.py'):shutil.copy2(p,P/p.name)
    staged=[]
    for folder in (P,D):
        for p in sorted(folder.iterdir()):
            if not p.is_file() or p.name in ('PRESERVATION_BEFORE.json','USER_REQUEST.txt') or p.suffix not in ('.py','.md','.json','.csv'):continue
            subprocess.run(['git','add','--',str(p.relative_to(R))],cwd=R,check=True);staged.append(str(p.relative_to(R)))
    old_index=dict(x.split('\t',1)[::-1] for x in pre['index'].splitlines())
    new_index=dict(x.split('\t',1)[::-1] for x in subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True).splitlines())
    assert all(new_index.get(p)==v for p,v in old_index.items())
    save('FINAL_GIT_STATE.json',dict(branch=BRANCH,head=pre['head'],individually_staged=staged,preexisting_index_entries_unchanged=True,no_commit=True,no_push=True,no_merge=True))
    subprocess.run(['git','add','--',str((D/'FINAL_GIT_STATE.json').relative_to(R))],cwd=R,check=True)
    save('CHAT_SUMMARY.json',conclusion)
    print(json.dumps(clean(dict(status=conclusion['status'],steps={a:results.get(a,{}).get('steps',st['steps'][a]) for a in ('A','B')},demo_effect=effect,best=st['best'],resource=peak,report=str(L/'TASK_ACQUISITION_COMPARISON.md')))),flush=True)
if __name__=='__main__':run()
