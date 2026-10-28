"""Source-only adapter: completed T3 children -> immutable same-parent bundle.

No runtime/worker imports, fit, physics, IO or numerical work at import. Future
approved invocation reads only already END/joined child outputs; parent stays
live and quiescent. All file IO is read-only. The owner provides the unchanged
original compare_raw callable, not a newly invented equivalence test.
"""
from pathlib import Path
import gzip,hashlib,json,math,sys,time
from c2b_component_selector_v2 import ROLES,digest


def read(path):return json.loads(Path(path).read_text())
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'tolist'):return clean(value.tolist())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()


class EvidenceError(ValueError):pass


class ArchivePath(type(Path())):
    def read_text(self,*a,**kw):
        if self.name=='runtime_artifacts.json' and not self.exists() and Path(str(self)+'.gz').exists():
            with gzip.open(str(self)+'.gz','rt',encoding='utf-8') as f:return f.read()
        return super().read_text(*a,**kw)


def motion_margins(measured,baseline,protocol):
    """Every continuous original compare requirement, identical numerical eps.

    Positive normalized values mean within that original requirement. Native
    state values are evaluation labels only, never inference state/history.
    """
    primary=protocol['primary'];out={}
    def add(name,slack,normalizer):out[name]=float(slack)/max(abs(float(normalizer)),1e-12)
    for signal,key in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
        for statistic in primary[key]:
            av=measured['motion']['raw']['full'][signal][statistic];bv=baseline['motion']['raw']['full'][signal][statistic]
            for joint in range(2):
                limit=bv[joint]*primary['burden_ratio']
                add(signal+'/'+statistic+'/'+str(joint),limit+1e-7-av[joint],limit)
    a=measured['dose'];b=baseline['dose']
    for phase in ('OUTBOUND','HOLD','RETURN'):
        limit=primary['each_phase_duration_abs_delta_s']
        add('phase_duration/'+phase,limit+1e-8-abs(measured['phase_durations'][phase]-baseline['phase_durations'][phase]),limit)
        for side in ('start_deg','end_deg'):
            for joint in range(2):
                limit=primary['endpoint_and_phase_boundary_abs_delta_deg']
                add('phase_boundary/'+phase+'/'+side+'/'+str(joint),limit+1e-7-abs(a['phase_boundaries'][phase][side][joint]-b['phase_boundaries'][phase][side][joint]),limit)
    for joint in range(2):
        limit=primary['excursion_abs_delta_deg'];add('excursion/'+str(joint),limit+1e-7-abs(a['excursion_deg'][joint]-b['excursion_deg'][joint]),limit)
        if b['cumulative_travel_deg'][joint]<=0:raise EvidenceError('ORIGINAL_B_TRAVEL_NOT_POSITIVE')
        ratio=a['cumulative_travel_deg'][joint]/b['cumulative_travel_deg'][joint]
        hi=primary['cumulative_ratio_upper'];lo=primary['cumulative_ratio_lower']
        add('travel_upper/'+str(joint),hi+1e-7-ratio,hi);add('travel_lower/'+str(joint),ratio-(lo-1e-7),lo)
        limit=primary['endpoint_and_phase_boundary_abs_delta_deg'];add('endpoint/'+str(joint),limit+1e-7-abs(a['endpoint_deg'][joint]-b['endpoint_deg'][joint]),limit)
        limit=primary['tracking_RMS_add_deg'];add('tracking/'+str(joint),limit+1e-7-(measured['tracking_RMS_deg'][joint]-baseline['tracking_RMS_deg'][joint]),limit)
    limit=primary['total_duration_abs_delta_s'];add('total_duration',limit+1e-8-abs(a['duration_s']-b['duration_s']),limit)
    for key,requirement in [('moment_integral_Nm_s','moment_integral_ratio'),('force_peak_N','force_peak_ratio'),('moment_peak_Nm','moment_peak_ratio')]:
        limit=baseline[key]*primary[requirement];add(key,limit+1e-7-measured[key],limit)
    if not all(math.isfinite(v) for v in out.values()):raise EvidenceError('NONFINITE_COMPONENT_MARGIN')
    return out


def action_x3(action):
    family=action.get('family')
    if family=='B':return None
    if family=='H150':
        if set(action)-{'family','legacy'} or action.get('legacy',[0.,0.])!=[0.,0.]:raise EvidenceError('DIFFERENT_FULL_H150_ACTION')
        return 0.
    if family!='modal8_retimed' or set(action)-{'family','x','legacy'}:raise EvidenceError('UNREGISTERED_POLICY')
    x=action['x']
    if len(x)!=8 or any(float(x[j])!=0. for j in range(8) if j!=3) or action.get('legacy')!=[0.,0.]:raise EvidenceError('NOT_PURE_RETURN_X3')
    if not math.isfinite(float(x[3])) or abs(x[3])>.5:raise EvidenceError('X3_TRUST_REGION')
    return float(x[3])


def _verify_original_mode(root,ident,cfg):
    scripts=root/'runtime/source/stages/stage5_personalized_motion_learning/scripts/high_rom_v1'
    sys.path.insert(0,str(scripts));import evaluate_execution_mode as mode
    if not Path(mode.__file__).resolve().is_relative_to(scripts.resolve()):raise EvidenceError('WRONG_IMPORTED_SCORER_PACKAGE')
    casepath=root/cfg['case_path'];case=read(casepath)
    if sha(casepath)!=cfg['case_sha256']:raise EvidenceError('CASE_CONFIG_SHA_CHANGED')
    descriptor=dict(case_key=case['case_key'],physical_variant=case['cell']['family'],candidate=case['coordination_candidate'],path=str(casepath.relative_to(root/'runtime/source')),sha256=sha(casepath))
    scoring=read(root/'runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring']
    path=root/'runtime/source/results'/ident
    if read(path/'summary.json').get('qualification',{}).get('hidden_case_evaluation_only')!=case:raise EvidenceError('ACTUAL_CASE_SUMMARY_MISMATCH')
    if read(path/'HIGH_ROM_CASE_RESULT.json').get('case_sha256')!=sha(casepath):raise EvidenceError('LAUNCH_CASE_SHA_MISMATCH')
    fresh=clean(mode.evaluate(ArchivePath(path),descriptor,scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg']))
    cached=read(root/'runtime/output'/(ident+'_DATA.json'))['metric']['physical_audit']['unchanged_evaluator']
    for key in ('physical_task_result','scientific_validity','overall_result_for_mode','raw_scorer_v2'):
        if fresh[key]!=cached[key]:raise EvidenceError('ORIGINAL_SCORER_REPLAY_MISMATCH:'+ident+':'+key)
    return dict(overall=fresh['overall_result_for_mode'],result_sha256=digest(fresh),
        source_sha256={str(Path(p).relative_to(root)):sha(p) for p in [mode.__file__,mode.score.__code__.co_filename]})


def _nonzero_execution(row,summary,lineage,trace,zero_trace,np):
    owner={r['decision_index']:r for r in lineage['rows']};nonzero=[];unclean=[]
    for record in summary['learning_records']:
        meta=record.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')
        if meta is None:continue
        if not np.array_equal(np.asarray(meta['parameters']),np.asarray(row['action']['x'])):raise EvidenceError('MODAL_PARAMETER_IDENTITY')
        changed=np.max(np.abs(np.asarray(meta['proposed_target_rad'])-np.asarray(meta['original_target_rad'])))>1e-12
        if not changed:continue
        own=owner.get(record['decision_index'],{})
        good=bool(meta.get('status')=='ACCEPTED' and record.get('selected_plan_activated') is True and own.get('actual_native_steps',0)>0
            and np.allclose(record['selected_plan']['target_q_rad'],meta['proposed_target_rad'],rtol=0,atol=1e-12))
        proof=dict(decision_index=record['decision_index'],request_id=summary['decisions'][record['decision_index']]['timing_request_id'],
            accepted=meta.get('status'),activated=record.get('selected_plan_activated'),positive_native_steps=own.get('actual_native_steps',0),
            phase=summary['decisions'][record['decision_index']]['phase'],window_start_s=record['start_time_s'],window_end_s=record['end_time_s'],
            selected_target_matches_accepted_proposal=good)
        (nonzero if good else unclean).append(proof)
    t=trace['time_s'];z=zero_trace['time_s'];indices=np.clip(np.searchsorted(z,t),0,len(z)-1)
    left=np.maximum(indices-1,0);indices=np.where(abs(z[left]-t)<abs(z[indices]-t),left,indices)
    common=abs(z[indices]-t)<=1e-8
    actual_reference_difference=float(np.max(abs(trace['reference_q_rad'][common]-zero_trace['reference_q_rad'][indices[common]]),initial=0.))
    return dict(clean=bool(nonzero and not unclean and actual_reference_difference>1e-12),
        accepted_activated_positive_windows=nonzero,unclean_nonzero_windows=unclean,
        issued_reference_max_difference_rad_vs_zero_at_common_real_time=actual_reference_difference,
        common_control_timestamps=int(common.sum()))


def build_bundle(root,group,stage_prefix,*,owner_state,compare_raw,expected_compare_source_sha256):
    """Future approved extraction; no fit/physics; raises instead of filling gaps.

    owner_state must be captured from the original still-live owner at OUT0:
    {stage=3, phase=OUTBOUND, slot=0, full_snapshot_sha256, live_quiescent,
     native_advanced_since_snapshot=False}.
    compare_raw is the existing original full trace/native/receipt gate.
    """
    import numpy as np
    root=Path(root).resolve();started=time.monotonic()
    compare_path=Path(compare_raw.__code__.co_filename).resolve()
    if sha(compare_path)!=expected_compare_source_sha256:raise EvidenceError('ORIGINAL_RAW_COMPARE_SOURCE_CHANGED')
    if owner_state.get('stage')!=3 or owner_state.get('phase')!='OUTBOUND' or owner_state.get('slot')!=0:raise EvidenceError('NOT_T3_OUT0_OWNER')
    if owner_state.get('live_quiescent') is not True or owner_state.get('native_advanced_since_snapshot') is not False:raise EvidenceError('OWNER_NOT_SAME_LIVE_OUT0')
    cfgpath=root/'experiments'/(group+'.json');cfg=read(cfgpath);manifestpath=root/'jobs'/group/'SOURCE_MANIFEST.json'
    manifest=read(manifestpath)
    if manifest['config_sha256']!=sha(cfgpath):raise EvidenceError('CONFIG_SHA_CHANGED')
    for relative,expected in manifest['files'].items():
        if sha(root/relative)!=expected:raise EvidenceError('FROZEN_JOB_SOURCE_CHANGED:'+relative)
    protocolpath=root/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json';protocol=read(protocolpath)
    events=[json.loads(s) for s in (root/'runtime/ATTEMPTS.jsonl').read_text().splitlines() if s.strip()]
    roles={};resolved={};bindings={};source_paths={cfgpath,manifestpath,protocolpath,root/'ACTIVATION.json',root/cfg['case_path'],compare_path}
    for role in ROLES:
        original=stage_prefix+'_'+role;ident=original;alias=root/'audit/persistent'/(ident+'_ALIAS.json')
        alias_row=None
        if alias.exists():
            alias_row=read(alias);ident=alias_row['alias_of'];source_paths.add(alias)
            if alias_row['new_native_steps']!=0:raise EvidenceError('ALIAS_ADDED_PHYSICS')
        resultpath=root/'attempts'/(ident+'_RESULT.json')
        if not resultpath.is_file():raise EvidenceError('REGISTERED_ROLE_NOT_COMPLETED:'+role)
        row=read(resultpath)
        if row.get('stage')!=3 or row.get('source_scope')!='REAL_CONTINUOUS_SESSION_LIVE_PARENT_FORK':raise EvidenceError('NOT_CURRENT_REAL_T3_CHILD:'+role)
        if alias_row and digest(alias_row['action'])!=digest(row['action']):raise EvidenceError('ALIAS_ACTION_NOT_IDENTICAL')
        starts=[r for r in events if r.get('id')==ident and r['event']=='START'];ends=[r for r in events if r.get('id')==ident and r['event']=='END']
        if len(starts)!=1 or len(ends)!=1 or ends[0].get('joined') is not True or ends[0].get('returncode')!=0:raise EvidenceError('CHILD_NOT_COMPLETE_JOINED:'+role)
        if starts[0].get('config_sha256')!=sha(cfgpath) or starts[0].get('job_source_sha256')!=sha(manifestpath):raise EvidenceError('CHILD_SOURCE_CONFIG_BINDING')
        if row.get('complete') is not True:raise EvidenceError('PARTIAL_REGISTERED_ROLE:'+role)
        bindingpath=root/'audit/persistent'/(ident+'_ACTUAL_PLANT_BINDING_EVALUATION_ONLY.json');binding=read(bindingpath)
        if binding['case_sha256']!=cfg['case_sha256']:raise EvidenceError('ACTUAL_PARAMETER_CASE_SHA')
        bindings[ident]=binding['model_parameter_fingerprint'];source_paths.add(bindingpath)
        snap=root/'runtime/reports'/(ident+'_SNAPSHOT.json');snapshot=read(snap)
        if snapshot['hash']!=owner_state['full_snapshot_sha256']:raise EvidenceError('DIFFERENT_FULL_PARENT_SNAPSHOT:'+role)
        roles[role]=dict(id=ident,alias_of=None if ident==original else ident,qualified=row['qualified'],END=ends[0],action=row['action'])
        resolved[ident]=row;source_paths.update([resultpath,snap])
    if len(set(bindings.values()))!=1:raise EvidenceError('MIXED_PHYSICAL_PARAMETER_FINGERPRINTS')
    for role in ('B','H150','ZERO_MODAL','FIXED_X3_MINUS025','FIXED_X3_PLUS025'):
        if roles[role]['qualified'] is not True:raise EvidenceError('REQUIRED_CORE_ORIGINAL_GATE_FAIL:'+role)
    h_id=roles['H150']['id'];z_id=roles['ZERO_MODAL']['id'];h=resolved[h_id]
    if h.get('full_H150_component_execution',{}).get('status')!='PASS':raise EvidenceError('H150_COMPONENT_ACTUAL_EXECUTION')
    if action_x3(roles['FIXED_X3_MINUS025']['action'])!=-.25 or action_x3(roles['FIXED_X3_PLUS025']['action'])!=.25:raise EvidenceError('SIGNED_REGISTERED_ACTION_IDENTITY')
    rawgate=compare_raw(root/'runtime/source/results'/h_id,root/'runtime/source/results'/z_id)
    if rawgate['status']!='PASS':raise EvidenceError('ZERO_RAW_NOT_EQUIVALENT')
    measuredB=read(root/'runtime/reports'/(roles['B']['id']+'_MEASURED.json'))
    fresh_B=_verify_original_mode(root,roles['B']['id'],cfg)
    if fresh_B['overall']!='PASS':raise EvidenceError('B_ORIGINAL_SCORER_REPLAY_FAILED')
    bpath=root/'runtime/source/results'/roles['B']['id']
    source_paths.update([bpath/'trace.npz',bpath/'summary.json',bpath/'runtime_artifacts.json.gz',bpath/'HIGH_ROM_CASE_RESULT.json',
        root/'runtime/output'/(roles['B']['id']+'_DATA.json'),root/'runtime/reports'/(roles['B']['id']+'_EXECUTED_RESIDUAL_RECEIPTS.json')])
    source_paths.add(root/'runtime/reports'/(roles['B']['id']+'_MEASURED.json'))
    with np.load(root/'runtime/source/results'/z_id/'trace.npz',allow_pickle=False) as z:
        use=z['stage']=='TASK';zero_trace={k:z[k][use].copy() for k in ('time_s','reference_q_rad')}
    observations=[];excluded=[];execution={};attempted=[];fresh={roles['B']['id']:fresh_B};duplicate_audit=[]
    for ident,row in resolved.items():
        x=action_x3(row['action'])
        if x is None:continue
        attempted.append(x);path=root/'runtime/source/results'/ident
        measuredpath=root/'runtime/reports'/(ident+'_MEASURED.json');lineagepath=root/'runtime/reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
        summarypath=path/'summary.json';tracepath=path/'trace.npz';rawpath=path/'runtime_artifacts.json.gz';datapath=root/'runtime/output'/(ident+'_DATA.json')
        source_paths.update([measuredpath,lineagepath,summarypath,tracepath,rawpath,datapath,path/'HIGH_ROM_CASE_RESULT.json'])
        measured=read(measuredpath);summary=read(summarypath);lineage=read(lineagepath)
        replay=_verify_original_mode(root,ident,cfg);fresh[ident]=replay
        with np.load(tracepath,allow_pickle=False) as z:
            use=z['stage']=='TASK';trace={k:z[k][use].copy() for k in ('time_s','reference_q_rad')}
            tt=trace['time_s']
            if len(tt)<4 or not np.allclose(np.diff(tt),.005,rtol=0,atol=1e-8) or not bool(z['terminal_boundary_node'][np.flatnonzero(use)[-1]]):raise EvidenceError('COMPLETE_TASK_5MS_BOUNDARIES_REQUIRED')
            jf=float(np.linalg.norm(z['physical_cuff_force_world_n'][use][:-1],axis=1)@np.diff(tt))
            jm=float(np.linalg.norm(z['physical_cuff_moment_world_nm'][use][:-1],axis=1)@np.diff(tt))
            if abs(jf-row['JF'])>1e-8 or abs(jm-row['JM'])>1e-8:raise EvidenceError('RAW_FULL_TASK_COST_LABEL_MISMATCH')
        clean=True
        if x!=0.:
            execution[ident]=_nonzero_execution(row,summary,lineage,trace,zero_trace,np);clean=execution[ident]['clean']
        original_legal=bool(replay['overall']=='PASS' and measured['native_physical_audit']['pass_'] and lineage['status']=='PASS'
            and measured['axes']['PHYSICAL_TASK_VALID']=='PASS' and measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS'
            and measured['axes']['LEGACY_R2_MATCHED']=='PASS')
        if not original_legal:raise EvidenceError('REGISTERED_ROLE_NOT_ORIGINAL_COMPLETE_LEGAL:'+ident)
        if not clean:
            excluded.append(dict(id=ident,x3=x,reason='NOT_CLEAN_COMPLETE_LEGAL_RESPONSE',execution=execution.get(ident),cost_already_paid=True));continue
        margins=motion_margins(measured,measuredB,protocol)
        observation=dict(id=ident,x3=x,action_sha256=digest(row['action']),delta_JF_N_s=row['JF']-h['JF'],delta_JM_Nm_s=row['JM']-h['JM'],
            motion_margins=margins,qualified=row['qualified'],clean_completed_legal_response=True,parent_snapshot_sha256=owner_state['full_snapshot_sha256'])
        observation['phase_durations_s']=measured['phase_durations']
        observation['phase_duration_deltas_vs_B_s']={ph:measured['phase_durations'][ph]-measuredB['phase_durations'][ph] for ph in ('OUTBOUND','HOLD','RETURN')}
        previous=next((r for r in observations if abs(r['x3']-x)<=1e-12),None)
        if previous:
            if abs(previous['delta_JF_N_s']-observation['delta_JF_N_s'])>1e-8 or abs(previous['delta_JM_Nm_s']-observation['delta_JM_Nm_s'])>1e-8 or any(abs(previous['motion_margins'][k]-margins[k])>1e-8 for k in margins):raise EvidenceError('NONSTATIONARY_DUPLICATE_RESPONSE')
            exact=compare_raw(root/'runtime/source/results'/previous['id'],path)
            if exact['status']!='PASS':raise EvidenceError('DUPLICATE_X3_NOT_SAME_RAW_POLICY')
            duplicate_audit.append(dict(id=ident,collapsed_into=previous['id'],x3=x,raw_exact=True));continue
        observations.append(observation)
    for role in ('FIXED_X3_MINUS025','FIXED_X3_PLUS025'):
        if not execution.get(roles[role]['id'],{}).get('clean'):raise EvidenceError('SIGNED_RESPONSE_NOT_CLEAN_ACTUALLY_CHANGED:'+role)
    hashes={str(p.relative_to(root)):sha(p) for p in source_paths}
    return dict(schema='C2B_SAME_LIVE_PARENT_BUNDLE_V2',dataset_class='REAL_CURRENT_T3',group=group,stage=3,stage_prefix=stage_prefix,
        parent_snapshot_sha256=owner_state['full_snapshot_sha256'],owner_live_quiescent=True,native_advanced_since_snapshot=False,
        roles=roles,observations=observations,attempted_x3=sorted(set(attempted)),margin_names=sorted(observations[0]['motion_margins']),
        gates={k:True for k in ('all_roles_completed_or_verified_alias','core_original_qualified','zero_raw_exact','signed_actual_nonzero_clean',
            'same_full_parent_snapshot','same_full_H150_recipe','same_source_case_config_scorer_activation','child_END_joined')},
        exact_H150_candidate_sha256=digest(cfg['H150']),source_identity_sha256=digest(hashes),source_sha256=hashes,
        zero_raw_gate=rawgate,independent_original_scorer_replays=fresh,execution_evidence=execution,excluded=excluded,duplicates=duplicate_audit,
        extraction_wall_s=time.monotonic()-started,scope='CURRENT_T3_ONLY_NO_OLD_TRIAL_POPULATION_VALUE_LABELS',new_fit=0,new_physics=0)
