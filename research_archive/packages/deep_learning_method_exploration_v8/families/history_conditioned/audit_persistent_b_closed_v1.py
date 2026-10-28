"""Independent read-only audit of a CLOSED B -> boundary -> B engineering job.

Never imports worker/study/plant code, runs physics, updates a root report, or
assumes group_B exists. --source-only is safe before a job has finished. Reading
trial artifacts additionally requires --closed-job-approved and all close gates.
"""
from pathlib import Path
import argparse, ast, collections, datetime, gc, gzip, hashlib, importlib.util
import inspect, json, math, os, re, sys, time, types

FAMILY = Path(__file__).resolve().parent
DEFAULT_ROOT = FAMILY.parents[1]
sys.dont_write_bytecode = True
DT = .00025


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''): h.update(block)
    return h.hexdigest()


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if hasattr(value, 'tolist'): return clean(value.tolist())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def write(path, value):
    path = Path(path).resolve()
    if FAMILY not in path.parents: raise ValueError('OUTPUT_OUTSIDE_OWNED_FAMILY')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def pid_identity(pid):
    try:
        row = Path('/proc')/str(pid)/'stat'
        fields = row.read_text().rsplit(')', 1)[1].split()
        return dict(pid=int(pid), start_ticks=int(fields[19]), state=fields[0])
    except (FileNotFoundError, ProcessLookupError): return None


def closure(root, group):
    """Metadata only. Do not read a Trial artifact until every gate has passed."""
    paths = dict(done=root/'jobs'/group/'WORKER_DONE.json',
                 exit=root/'owned'/(group+'_EXIT.json'),
                 supervisor=root/'owned'/(group+'_SUPERVISOR.json'),
                 supervisor_end=root/'owned'/(group+'_SUPERVISOR_END.json'))
    errors = ['MISSING_CLOSURE:'+k for k,p in paths.items() if not p.is_file()]
    docs = {k:read(p) for k,p in paths.items() if p.is_file()}
    end = docs.get('supervisor_end', {})
    if end and (end.get('state') != 'STOP' or end.get('survivors')):
        errors.append('SUPERVISOR_NOT_CLOSED_OR_SURVIVORS')
    identities = list(end.get('known_owned', {}).values())
    start = docs.get('supervisor', {})
    identities += [v for k,v in start.items() if k in ('identity','worker') and isinstance(v,dict)]
    live = []
    for old in identities:
        if 'pid' not in old or 'start_ticks' not in old: continue
        now = pid_identity(old['pid'])
        if now and now['start_ticks'] == old['start_ticks'] and now['state'] != 'Z': live.append(now)
    if live: errors.append('OWNED_PROCESS_STILL_LIVE')
    if docs.get('exit',{}).get('active_child') is not None: errors.append('EXIT_ACTIVE_CHILD')
    ledger = root/'runtime/ATTEMPTS.jsonl'
    records = [json.loads(s) for s in ledger.read_text().splitlines() if s.strip()] if ledger.exists() else []
    rows = [r for r in records if r.get('group') == group or r.get('id','').startswith(group+'_')]
    expected = [group+'_T1_B', group+'_BOUNDARY_1_2', group+'_T2_B']
    counts = {}
    for ident in expected:
        starts = [r for r in rows if r.get('id') == ident and r.get('event') == 'START']
        ends = [r for r in rows if r.get('id') == ident and r.get('event') == 'END']
        counts[ident] = dict(START=len(starts), END=len(ends))
        if len(starts)!=1 or len(ends)!=1: errors.append('UNCLOSED_OR_DUPLICATED_ATTEMPT:'+ident)
        elif ends[0].get('joined') is not True: errors.append('END_NOT_JOINED:'+ident)
    allstarts = collections.Counter(r['id'] for r in rows if r.get('event')=='START')
    allends = collections.Counter(r['id'] for r in rows if r.get('event')=='END')
    if allstarts != allends: errors.append('GROUP_STARTED_END_COUNT_MISMATCH')
    return dict(status='CLOSED' if not errors else 'NOT_CLOSED_DO_NOT_READ_TRIALS', errors=errors,
                paths={k:str(p) for k,p in paths.items()}, live_owned=live, counts=counts,
                metadata=docs, ledger_records=rows)


def source_review(root, group):
    cfgpath=root/'experiments'/(group+'.json'); cfg=read(cfgpath)
    checks=[]
    for relative,expected in cfg.get('frozen_artifacts',{}).items():
        p=root/relative
        actual=sha(p) if p.is_file() else None
        checks.append(dict(path=relative,expected=expected,actual=actual,pass_=actual==expected))
    paths=[Path(__file__),root/'source/v8_persistent_b_worker_v1.py', FAMILY/'persistent_worker_v1.py',
           FAMILY/'persistent_session_bridge.py', FAMILY/'trial_interface.py',
           root/'runtime/code/explore_common.py', root/'runtime/code/analyze_matched.py',
           root/'runtime/source/stages/stage5_personalized_motion_learning/scripts/high_rom_v1/evaluate_execution_mode.py',
           root/'runtime/source/stages/stage5_personalized_motion_learning/scripts/high_rom_v1/summarize_phase_b.py']
    parsed={str(p.relative_to(root)):dict(sha256=sha(p),ast_parse=bool(ast.parse(p.read_text()))) for p in paths}
    return dict(status='SOURCE_REVIEW_PASS' if all(x['pass_'] for x in checks) else 'FROZEN_SOURCE_MISMATCH',
                config_sha256=sha(cfgpath), frozen_checks=checks, parsed_sources=parsed,
                closure=closure(root,group), queue=read(root/'queue/FROZEN_TRANSFER_PROGRESS.json')
                if (root/'queue/FROZEN_TRANSFER_PROGRESS.json').exists() else None,
                trial_artifacts_read=False, physics_steps=0, model_fits=0,
                method='AST/source/plan/queue/closure metadata only; frozen B code untouched')


def array_items(path,key):
    """Pure bounded gzip JSON array reader; no runtime-module imports."""
    with gzip.open(path,'rt') as f:
        buf='';needle='"'+key+'":';decoder=json.JSONDecoder()
        while True:
            part=f.read(65536)
            if not part: raise ValueError('ARRAY_NOT_FOUND:'+key)
            buf+=part;pos=buf.find(needle)
            if pos>=0:
                buf=buf[pos+len(needle):].lstrip()
                while not buf: buf+=f.read(65536);buf=buf.lstrip()
                if not buf.startswith('['): raise ValueError('NOT_ARRAY:'+key)
                buf=buf[1:];break
            buf=buf[-len(needle):]
        while True:
            buf=buf.lstrip(', \n\r\t')
            if buf.startswith(']'): return
            try: value,end=decoder.raw_decode(buf)
            except json.JSONDecodeError:
                part=f.read(65536)
                if not part: raise ValueError('INCOMPLETE_ARRAY:'+key)
                buf+=part
                if len(buf)>4*2**20: raise ValueError('ITEM_EXCEEDS_BOUND:'+key)
                continue
            yield value;buf=buf[end:]


class ArchivePath(type(Path())):
    def read_text(self,*args,**kwargs):
        if self.name=='runtime_artifacts.json' and not self.exists() and Path(str(self)+'.gz').exists():
            with gzip.open(str(self)+'.gz','rt',encoding='utf-8') as f: return f.read()
        return super().read_text(*args,**kwargs)


def original_functions(root):
    # Neither module has import-time filesystem mutation; do not import am/sc.
    scripts=root/'runtime/source/stages/stage5_personalized_motion_learning/scripts'
    sys.path.insert(0,str(scripts/'high_rom_v1'))
    import evaluate_execution_mode as mode
    spec=importlib.util.spec_from_file_location('independent_original_explore',root/'runtime/code/explore_common.py')
    ec=importlib.util.module_from_spec(spec);spec.loader.exec_module(ec)
    src=inspect.getsource(ec.compare)
    if src.count("a['axes']['HOST_EXECUTION_CAUSAL_VALID']")!=1: raise ValueError('ORIGINAL_COMPARE_BINDING_CHANGED')
    src=src.replace("a['axes']['HOST_EXECUTION_CAUSAL_VALID']","a['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']")
    namespace=dict(ec.__dict__);exec(compile(src,'<unchanged comparison; original scientific ownership binding>','exec'),namespace)
    # Compile the actual timing function and its actual constant assignments,
    # without importing campaign_r2 (which would import a plant environment).
    timing_path=scripts/'single_human_sac_expert_v1_r2/campaign_r2.py'
    tree=ast.parse(timing_path.read_text());selected=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'NUMERIC_EPS','PHASE_MIN','DECISION_ALLOWANCE'} for t in node.targets): selected.append(node)
        if isinstance(node,ast.FunctionDef) and node.name=='matched_eligible': selected.append(node)
    ns={'math':math,'rt':types.SimpleNamespace(CONTROL_DT_S=.005)}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(timing_path),'exec'),ns)
    return mode,namespace['compare'],ns['matched_eligible']


def rebuild(root, ident, np):
    path=root/'runtime/source/results'/ident;summary=read(path/'summary.json')
    metric=read(root/'runtime/output'/(ident+'.json')); data=read(root/'runtime/output'/(ident+'_DATA.json'))
    errors=[]
    with np.load(path/'trace.npz',allow_pickle=False) as z:
        ix=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ix]
        if len(t)<4 or not np.all(np.diff(t)>0): raise ValueError('NON_MONOTONIC_OR_MISSING_TASK_BOUNDARIES')
        if not bool(z['terminal_boundary_node'][ix[-1]]): errors.append('NO_TERMINAL_BOUNDARY')
        truth=z['evaluation_only_human_state_rad_rad_s'][ix];ref=z['reference_q_rad'][ix]
        F=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1)
        M=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1)
        estimated=z['estimated_human_state_rad_rad_s'][ix]
    dt=np.diff(t)
    if not np.allclose(dt,.005,rtol=0,atol=1e-8): errors.append('TASK_NOT_COMPLETE_5MS_BOUNDARY_GRID')
    jf=float(F[:-1]@dt);jm=float(M[:-1]@dt)
    transitions={r['to']:r['time_s'] for r in summary['task']['phase_transitions']}
    bounds=[t[0],transitions['HOLD'],transitions['RETURN'],transitions['COMPLETE']]
    phasecost={};durations={}
    for ph,a,b in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
        weights=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));used=weights>0
        phasecost[ph]=dict(J_F_N_s=float(F[:-1]@weights),moment_integral_Nm_s=float(M[:-1]@weights),
            integrated_trace_duration_s=float(weights.sum()),mean_force_N=float(F[:-1]@weights/weights.sum()))
        durations[ph]=float(b-a)
    if abs(sum(x['J_F_N_s'] for x in phasecost.values())-jf)>1e-8 or abs(sum(x['moment_integral_Nm_s'] for x in phasecost.values())-jm)>1e-8: errors.append('PHASE_QUADRATURE_CLOSURE')
    for label,m in [('metric',metric),('DATA',data['metric'])]:
        if abs(jf-m['J_F'])>1e-6 or abs(jm-m['moment_integral'])>1e-6: errors.append(label+'_JF_JM_MISMATCH')
    history=read(root/'history'/(ident+'_COMPLETE_HISTORY.json'))
    if abs(jf-history['JF_N_s'])>1e-6 or abs(jm-history['JM_Nm_s'])>1e-6: errors.append('COMPLETE_HISTORY_JF_JM_MISMATCH')
    raw=path/'runtime_artifacts.json.gz'
    receipts=list(array_items(raw,'command_receipts'))
    positive=sorted([r for r in receipts if r.get('applied') and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s'])
    starts=np.asarray([r['start_physics_s'] for r in positive]);ends=np.asarray([r['end_physics_s'] for r in positive])
    if not len(positive) or np.max(abs(starts[1:]-ends[:-1]),initial=0)>1e-8: errors.append('NONCONTIGUOUS_POSITIVE_RECEIPTS')
    counts=collections.Counter();native_count=0;rows=[];first=None;last=None;lineage_errors=[]
    lookup={r['receipt_index']:r for r in positive}
    for row in array_items(raw,'native_states_evaluation_only'):
        native_count+=1
        if first is None: first=row
        if last is not None and abs(row['time_s']-last['time_s']-DT)>1e-9: lineage_errors.append('NATIVE_GRID')
        begin=row.get('physical_interval_start_s',row['time_s']-DT)
        cid=row.get('command_id')
        if cid is None:
            k=int(np.searchsorted(starts,begin+1e-9,side='right')-1)
            cid=positive[k]['receipt_index'] if k>=0 and begin<ends[k]-1e-9 else None
        receipt=lookup.get(cid);counts[cid]+=1
        if receipt is None or not receipt['start_physics_s']-1e-8<=begin<receipt['end_physics_s']+1e-8: lineage_errors.append('UNOWNED_NATIVE_INTERVAL')
        elif not np.array_equal(row['command_torque_nm'],receipt['command_torque_nm']): lineage_errors.append('NATIVE_RECEIPT_TORQUE_MISMATCH')
        if t[0]-1e-9<=row['time_s']<=t[-1]+1e-9: rows.append((row['time_s'],row['qpos_evaluation_only'],row['qvel_evaluation_only']))
        last=row
    for cid,count in counts.items():
        if cid not in lookup or lookup[cid]['native_steps']!=count: lineage_errors.append('POSITIVE_RECEIPT_STEP_COUNT')
    errors+=sorted(set(lineage_errors))
    nt=np.asarray([r[0] for r in rows]);qp=np.asarray([r[1] for r in rows]);vp=np.asarray([r[2] for r in rows]);del rows
    if len(nt)<3: raise ValueError('NO_COMPLETE_NATIVE_TASK')
    mi=np.clip(np.searchsorted(nt,t),0,len(nt)-1);left=np.maximum(mi-1,0)
    mi=np.where(abs(nt[left]-t)<abs(nt[mi]-t),left,mi);close=abs(nt[mi]-t)<1e-8
    eq=np.max(abs(qp[mi[close],:,None]-truth[close,None,:2]),axis=0)
    ev=np.max(abs(vp[mi[close],:,None]-truth[close,None,2:]),axis=0)
    qi=np.argmin(eq,axis=0);vi=np.argmin(ev,axis=0)
    mapping=float(max(np.max(eq[qi,np.arange(2)]),np.max(ev[vi,np.arange(2)])))
    if mapping>=1e-8 or len(set(qi.tolist()))!=2 or len(set(vi.tolist()))!=2: errors.append('INDEPENDENT_NATIVE_HUMAN_MAPPING')
    q=qp[:,qi];v=vp[:,vi];a=np.gradient(v,nt,axis=0,edge_order=2);j=np.gradient(a,nt,axis=0,edge_order=2)
    def stats(y): return dict(max_abs=np.max(abs(y),axis=0),p95_abs=np.quantile(abs(y),.95,axis=0),rms=np.sqrt(np.mean(y*y,axis=0)))
    full={k:stats(np.degrees(y)) for k,y in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]}
    phase=np.full(len(nt),'OUTBOUND',dtype='<U10')
    for ph in ['OUTBOUND','HOLD','RETURN']:
        if ph in transitions: phase[nt>=transitions[ph]-1e-9]=ph
    boundaries={};shapes={}
    for ph in ['OUTBOUND','HOLD','RETURN']:
        ix=np.flatnonzero(phase==ph)
        if len(ix)<3: raise ValueError('MISSING_FULL_NATIVE_PHASE:'+ph)
        u=(nt[ix]-nt[ix[0]])/(nt[ix[-1]]-nt[ix[0]])
        boundaries[ph]=dict(start_deg=np.degrees(q[ix[0]]),end_deg=np.degrees(q[ix[-1]]))
        shapes[ph]=np.degrees(np.column_stack([np.interp(np.linspace(0,1,201),u,q[ix,d]) for d in range(2)]))
    measured=dict(id=ident,J_F_N_s=jf,moment_integral_Nm_s=jm,force_peak_N=float(F.max()),moment_peak_Nm=float(M.max()),
        tracking_RMS_deg=np.degrees(np.sqrt(np.mean((truth[:,:2]-ref)**2,axis=0))),phase_durations=durations,
        phase_cost=dict(phases=phasecost),motion=dict(raw=dict(full=full)),
        dose=dict(duration_s=float(nt[-1]-nt[0]),excursion_deg=np.degrees(np.ptp(q,axis=0)),
            cumulative_travel_deg=np.degrees(np.sum(abs(np.diff(q,axis=0)),axis=0)),endpoint_deg=np.degrees(q[-1]),phase_boundaries=boundaries,phase_shapes=shapes),
        axes=dict(PHYSICAL_TASK_VALID='PASS' if metric['task_valid'] else 'FAIL',SCIENTIFIC_EXECUTION_CAUSAL_VALID='PASS' if not lineage_errors else 'FAIL'))
    return measured,dict(id=ident,errors=errors,JF_N_s=jf,JM_Nm_s=jm,task_boundary_nodes=len(t),task_intervals=len(dt),
        task_start_s=float(t[0]),task_end_s=float(t[-1]),phase_cost=phasecost,native_count=native_count,
        native_start_s=None if first is None else first['time_s']-DT,native_end_s=None if last is None else last['time_s'],
        first_native=first,last_native=last,receipt_count=len(receipts),positive_receipt_count=len(positive),
        native_mapping=dict(qpos_indices=qi,qvel_indices=vi,max_error=mapping,common_boundary_nodes=int(close.sum())),
        incremental_metric=data['metric']['actual_new_native_physics_steps'],absolute_metric_native_steps=metric.get('native_physics_steps'),
        source_hashes={str(p.relative_to(root)):sha(p) for p in [path/'trace.npz',path/'summary.json',raw,root/'runtime/output'/(ident+'_DATA.json')]})


def audit_closed(root,group,closed):
    if closed['status']!='CLOSED': raise RuntimeError('NOT_CLOSED_DO_NOT_READ_TRIALS')
    import numpy as np
    mode,compare,matched=original_functions(root)
    cfg=read(root/'experiments'/(group+'.json'));casepath=root/cfg['case_path'];case=read(casepath)
    descriptor=dict(case_key=case['case_key'],physical_variant=case['cell']['family'],candidate=case['coordination_candidate'],path=str(casepath.relative_to(root/'runtime/source')),sha256=sha(casepath))
    scoring=read(root/'runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring']
    trials=[];all_errors=[]
    cfgpath=root/'experiments'/(group+'.json');manifestpath=root/'jobs'/group/'SOURCE_MANIFEST.json'
    manifest=read(manifestpath)
    if manifest['config_sha256']!=sha(cfgpath) or cfg.get('case_sha256')!=sha(casepath):all_errors.append('FROZEN_CONFIG_OR_CASE_SHA_MISMATCH')
    for event in closed['ledger_records']:
        if event['event']=='START' and (event.get('config_sha256')!=sha(cfgpath) or event.get('job_source_sha256')!=sha(manifestpath)):
            all_errors.append('START_CONFIG_SOURCE_IDENTITY:'+event['id'])
    for relative,expected in manifest['files'].items():
        if sha(root/relative)!=expected:all_errors.append('JOB_FROZEN_SOURCE_CHANGED:'+relative)
    for number in (1,2):
        ident=group+'_T'+str(number)+'_B';path=root/'runtime/source/results'/ident
        fresh=clean(mode.evaluate(ArchivePath(path),descriptor,scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg']))
        gc.collect();data=read(root/'runtime/output'/(ident+'_DATA.json'));old=data['metric']['physical_audit']['unchanged_evaluator']
        measured,result=rebuild(root,ident,np)
        for key in ['physical_task_result','scientific_validity','overall_result_for_mode','raw_scorer_v2']:
            if fresh[key]!=old[key]:result['errors'].append('CACHE_BYPASS_ORIGINAL_SCORER_MISMATCH:'+key)
        motion=compare(measured,measured)
        cached=read(root/'runtime/reports'/(ident+'_MEASURED.json'))
        for signal in measured['motion']['raw']['full']:
            for stat,value in measured['motion']['raw']['full'][signal].items():
                if not np.allclose(value,cached['motion']['raw']['full'][signal][stat],atol=1e-9,rtol=1e-12):
                    result['errors'].append('INDEPENDENT_NATIVE_MOTION_MISMATCH:'+signal+'/'+stat)
        qual=bool(motion['acceptance_pass'] and matched(measured['phase_durations']) and fresh['overall_result_for_mode']=='PASS')
        expected=read(root/'attempts'/(ident+'_RESULT.json'))
        if qual!=expected['qualified']:result['errors'].append('FINAL_QUALIFICATION_MISMATCH')
        summary=read(path/'summary.json');launch=read(path/'HIGH_ROM_CASE_RESULT.json')
        if summary.get('qualification',{}).get('hidden_case_evaluation_only')!=case: result['errors'].append('ACTUAL_CASE_SUMMARY_MISMATCH')
        if launch.get('case_sha256')!=sha(casepath): result['errors'].append('LAUNCH_CASE_SHA_MISMATCH')
        bindingpath=root/'audit/persistent'/(ident+'_ACTUAL_PLANT_BINDING_EVALUATION_ONLY.json')
        if not bindingpath.exists():result['errors'].append('MISSING_ACTUAL_PARAMETER_BINDING')
        else:
            binding=read(bindingpath)
            if binding.get('case_sha256')!=sha(casepath):result['errors'].append('ACTUAL_PARAMETER_CASE_SHA')
            result['parameter_binding']=binding
        delta=read(root/'audit/persistent'/(ident+'_PERSISTENT_DELTA_ACCOUNTING.json'))
        n=result['native_count']
        if n!=delta['actual_new_native_steps'] or n!=result['incremental_metric']: result['errors'].append('INCREMENT_NATIVE_RECOUNT_MISMATCH')
        result.update(original_fresh_evaluator=fresh,motion_vs_own_trial_self=motion,independent_qualified=qual,
            mode='SCIENTIFIC_SIMULATION',truth_use='EVALUATION_ONLY_IN_AUDIT',delta=delta)
        trials.append(result);all_errors.extend(ident+':'+e for e in result['errors'])
        del measured;gc.collect()
    boundary_id=group+'_BOUNDARY_1_2'
    boundary=read(root/'audit/persistent'/(boundary_id+'_PERSISTENT_BOUNDARY.json'))
    steps=boundary['steps'];be=[];n=boundary['actual_new_native_steps']
    if n!=len(steps) or n!=boundary['observed_native_steps']:be.append('BOUNDARY_NATIVE_COUNT')
    previous=boundary['before']['physical_time_s']
    for s in steps:
        if abs(s['start_s']-previous)>1e-8 or abs(s['end_s']-s['start_s']-DT)>1e-8:be.append('BOUNDARY_NATIVE_GRID')
        if s['command']!=boundary['held_command'] or s['inherited_receipt_index']!=boundary['prior_positive_receipt']:be.append('BOUNDARY_HELD_COMMAND_RECEIPT')
        previous=s['end_s']
    stamps=[trials[0]['delta']['after'],boundary['before'],boundary['after'],trials[1]['delta']['before'],trials[1]['delta']['after']]
    identities={(r.get('pid'),r.get('start_ticks')) for r in closed['ledger_records'] if r['event']=='START'}
    if len(identities)!=1:be.append('DIRECT_B_BOUNDARY_PROCESS_IDENTITY_CHANGED')
    for key in ['plant_identity','observer_identity','measurement_layer_identity','updater_identity']:
        if len({s[key] for s in stamps})!=1:be.append('SESSION_OBJECT_CHANGED:'+key)
    if [s['repetition_index'] for s in stamps]!=[1,1,1,1,2]:be.append('REPETITION_SEQUENCE')
    if abs(stamps[0]['physical_time_s']-stamps[1]['physical_time_s'])>1e-8 or abs(stamps[2]['physical_time_s']-stamps[3]['physical_time_s'])>1e-8:be.append('SESSION_CLOCK_DISCONTINUITY')
    if abs(trials[0]['native_end_s']-stamps[0]['physical_time_s'])>1e-8 or abs(trials[1]['native_start_s']-stamps[3]['physical_time_s'])>1e-8:be.append('ARCHIVE_DELTA_CLOCK_BOUNDARY')
    if any(s['wall_active'] or s['planner_request_outstanding'] for s in stamps):be.append('NONQUIESCENT_EPOCH_BOUNDARY')
    total=sum(t['native_count'] for t in trials)+n
    if total!=closed['metadata']['done'].get('actual_new_native_steps'):be.append('DONE_TOTAL_DOUBLE_COUNT_OR_MISSING')
    for ident,count in [(t['id'],t['native_count']) for t in trials]+[(boundary_id,n)]:
        end=next(r for r in closed['ledger_records'] if r['id']==ident and r['event']=='END')
        if end.get('actual_new_native_steps')!=count:be.append('LEDGER_DELTA_MISMATCH:'+ident)
    all_errors+=be
    return dict(status='INDEPENDENT_PERSISTENT_B_AUDIT_PASS' if not all_errors else 'AUDIT_REVIEW_REQUIRED',
        errors=all_errors,trials=trials,boundary=boundary,actual_new_native_steps=total,
        evidence_level='Known-heavy B-only persistent engineering; no learning or independent-patient performance evidence',
        no_reset_evidence=dict(same_process_native_objects=True if not be else 'SEE_ERRORS',
            native_clock_and_increment_reconciled=not be,original_resume_source_preserves_plant=True,
            limitation='Boundary bridge logs native step times/control, not every boundary qpos/qvel; object IDs, native clock, original source, receipts and increments support continuation. Full hidden-state equality through unlogged boundary states is not independently measured.'),
        sources={str(p.relative_to(root)):sha(p) for p in [Path(mode.__file__),Path(mode.score.__code__.co_filename),root/'runtime/code/explore_common.py',root/'runtime/code/analyze_matched.py']},
        writes='ONLY_OWNED_FAMILY_AUDIT',physics_steps=0,model_fits=0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    ap.add_argument('--group',default='V8PERSISTB01');ap.add_argument('--source-only',action='store_true')
    ap.add_argument('--closed-job-approved',action='store_true',help='Explicit parent approval AFTER job closure, never inferred from elapsed time')
    args=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+',args.group):raise ValueError('GROUP_ID')
    root=args.root.resolve();started=time.time();review=source_review(root,args.group)
    if args.source_only:result=review;label='SOURCE_ONLY'
    elif not args.closed_job_approved:raise RuntimeError('EXPLICIT_CLOSED_JOB_ANALYSIS_APPROVAL_REQUIRED')
    else:
        try:result=audit_closed(root,args.group,review['closure'])
        except Exception as exc:
            result=dict(status='CLOSED_AUDIT_REFUSED_OR_ERROR_NOT_RANKED',error=type(exc).__name__+':'+str(exc),
                physics_steps=0,model_fits=0,qualified_replay=False)
        result['source_review']=review;label='CLOSED'
    result.update(audit_source_sha256=sha(__file__),wall_s=time.time()-started,
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    out=FAMILY/'audit'/('PERSISTENT_B_'+args.group+'_'+label+'.json');write(out,result)
    print(json.dumps(dict(output=str(out),status=result['status'],physics_steps=0,model_fits=0)))


if __name__=='__main__': main()
