"""Source-only same-live-parent component response models and one-grid choice.

No IO, NumPy import, fit, fixture or physics at import. fit_select() is a future
explicitly approved CPU computation. Inputs must come from the V2 evidence
adapter and the still-live original owner. Spreads are DATA_LIMITED_HEURISTICS.
"""
import hashlib,json,math,time

GRID=(-.25,-.125,0.,.125,.25)
ROLES=('B','H150','ZERO_MODAL','ILC_ENABLED_G025','ILC_ENABLED_G010',
       'ILC_HISTORY_DISABLED','FIXED_X3_MINUS025','FIXED_X3_PLUS025')
MODELS=('LINEAR','QUADRATIC','RBF_L025','MATERN32_L025','RBF_L050','MATERN32_L050')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def abstain(reason,**extra):
    return dict(status='ABSTAIN',reason=reason,source_scope='ONE_CURRENT_T3_LIVE_PARENT_ONLY',
        uncertainty='DATA_LIMITED_HEURISTICS_NOT_SAFETY_CALIBRATION',new_physics=0,**extra)


def validate(bundle):
    allowed={'schema','group','stage','stage_prefix','parent_snapshot_sha256','owner_live_quiescent','native_advanced_since_snapshot',
        'roles','observations','attempted_x3','margin_names','gates','exact_H150_candidate_sha256','source_identity_sha256','source_sha256',
        'zero_raw_gate','independent_original_scorer_replays','execution_evidence','excluded','duplicates','extraction_wall_s','scope','new_fit','new_physics','dataset_class'}
    if set(bundle)-allowed:return 'INPUT_LEAKAGE_TOP_LEVEL_ALLOWLIST'
    if bundle.get('schema')!='C2B_SAME_LIVE_PARENT_BUNDLE_V2':return 'INPUT_SCHEMA'
    if bundle.get('dataset_class') not in ('REAL_CURRENT_T3','SYNTHETIC_ONLY'):return 'DATASET_CLASS_REQUIRED'
    if bundle.get('scope')!='CURRENT_T3_ONLY_NO_OLD_TRIAL_POPULATION_VALUE_LABELS':return 'INPUT_OLD_OR_FUTURE_TRIAL_SCOPE'
    if bundle.get('stage')!=3 or bundle.get('native_advanced_since_snapshot') is not False:return 'PARENT_NOT_UNCHANGED_T3_OUT0'
    if bundle.get('owner_live_quiescent') is not True:return 'OWNER_NOT_LIVE_QUIESCENT'
    for gate in ('all_roles_completed_or_verified_alias','core_original_qualified','zero_raw_exact',
                 'signed_actual_nonzero_clean','same_full_parent_snapshot','same_full_H150_recipe',
                 'same_source_case_config_scorer_activation','child_END_joined'):
        if bundle.get('gates',{}).get(gate) is not True:return 'PREREQUISITE:'+gate
    if set(bundle.get('roles',{}))!=set(ROLES):return 'MISSING_OR_EXTRA_REGISTERED_T3_ROLE'
    role_ids={r['id'] for role,r in bundle['roles'].items() if role!='B'}
    role_actions={r['id']:r['action'] for role,r in bundle['roles'].items() if role!='B'}
    rows=bundle.get('observations',[])
    if not 3<=len(rows)<=8:return 'UNIQUE_ACTION_COUNT'
    margin_names=bundle.get('margin_names',[])
    if not margin_names or len(margin_names)+2>64:return 'MISSING_OR_TOO_MANY_COMPONENT_HEADS'
    seen=set()
    for row in rows:
        if set(row)-{'id','x3','action_sha256','delta_JF_N_s','delta_JM_Nm_s','motion_margins','qualified','clean_completed_legal_response',
            'parent_snapshot_sha256','phase_durations_s','phase_duration_deltas_vs_B_s'}:return 'INPUT_LEAKAGE_OBSERVATION_ALLOWLIST'
        if row['id']==bundle['roles']['B']['id']:return 'FAKE_B_AS_X3_ACTION'
        if row['id'] not in role_ids:return 'OBSERVATION_NOT_CURRENT_REGISTERED_CHILD'
        if row.get('action_sha256')!=digest(role_actions[row['id']]):return 'OBSERVATION_ACTION_SHA_MISMATCH'
        x=float(row['x3'])
        action=role_actions[row['id']]
        if action.get('family')=='H150':
            if x!=0. or set(action)-{'family','legacy'} or action.get('legacy',[0.,0.])!=[0.,0.]:return 'FULL_H150_ACTION_IDENTITY'
        elif action.get('family')=='modal8_retimed':
            coordinates=action.get('x',[])
            if len(coordinates)!=8 or float(coordinates[3])!=x or any(float(coordinates[j])!=0. for j in range(8) if j!=3) or action.get('legacy')!=[0.,0.] or set(action)-{'family','x','legacy'}:return 'MODAL_X3_ACTION_IDENTITY'
        else:return 'NON_H150_POLICY_AS_X3_ACTION'
        if not math.isfinite(x) or abs(x)>.5 or x in seen:return 'INVALID_OR_DUPLICATE_ACTION'
        seen.add(x)
        if row.get('clean_completed_legal_response') is not True:return 'UNCLEAN_RESPONSE_LABEL'
        if row.get('parent_snapshot_sha256')!=bundle.get('parent_snapshot_sha256'):return 'MIXED_PARENTS'
        if set(row['motion_margins'])!=set(margin_names):return 'MISSING_COMPONENT_MARGIN'
        values=[row['delta_JF_N_s'],row['delta_JM_Nm_s']]+list(row['motion_margins'].values())
        if not all(math.isfinite(float(v)) for v in values):return 'NONFINITE_LABEL'
    if not {-.25,0.,.25}.issubset(seen):return 'MISSING_ACTUAL_SIGNED_RESPONSE'
    center=next(r for r in rows if r['x3']==0.)
    if center['id']!=bundle['roles']['H150']['id']:return 'CENTER_NOT_ACTUAL_H150_CHILD'
    if abs(center['delta_JF_N_s'])>1e-12 or abs(center['delta_JM_Nm_s'])>1e-12:return 'CENTER_NOT_SAME_H150'
    if max(abs(r['delta_JF_N_s']) for r in rows if abs(r['x3'])==.25)<=1e-6:return 'JF_LOCAL_RESPONSE_UNIDENTIFIED'
    if not any(r.get('qualified') is True for r in rows):return 'NO_OBSERVED_QUALIFIED_COMPARATOR'
    return None


def _base_kernel(np,x,z,kind,length):
    distance=np.abs(np.asarray(x)[:,None]-np.asarray(z)[None,:])/length
    if kind=='RBF':return np.exp(-.5*distance*distance)
    s=math.sqrt(3.)*distance
    return (1.+s)*np.exp(-s)


def _kernel(np,x,z,kind,length):
    # Exact paired-deviation anchor at the actually observed H150 x=0.
    return _base_kernel(np,x,z,kind,length)-_base_kernel(np,x,[0.],kind,length)@_base_kernel(np,[0.],z,kind,length)


def _fit_predict(np,model,x,y,query):
    if model in ('LINEAR','QUADRATIC'):
        degree=1 if model=='LINEAR' else 2
        phi=np.column_stack([x**power for power in range(1,degree+1)])
        psi=np.column_stack([query**power for power in range(1,degree+1)])
        matrix=phi.T@phi+1e-6*np.eye(degree)
        inv=np.linalg.solve(matrix,np.eye(degree));weights=inv@phi.T@y
        mean=psi@weights;residual=phi@weights-y
        floor=np.maximum(.001,np.sqrt(np.mean(residual*residual,axis=0)))
        spread=np.sqrt(np.maximum(0.,np.sum((psi@inv)*psi,axis=1)))[:,None]*floor[None,:]
        return mean,spread,dict(kind=model,weights=weights.tolist(),residual_RMS_normalized=np.sqrt(np.mean(residual*residual,axis=0)).tolist())
    kind='RBF' if model.startswith('RBF') else 'MATERN32';length=.25 if model.endswith('025') else .5
    k=_kernel(np,x,x,kind,length);matrix=k+(.001**2+1e-10)*np.eye(len(x))
    inverse=np.linalg.solve(matrix,np.eye(len(x)));alpha=inverse@y;cross=_kernel(np,query,x,kind,length)
    mean=cross@alpha;solved=inverse@cross.T
    variance=np.maximum(0.,np.diag(_kernel(np,query,query,kind,length))-np.sum(cross*solved.T,axis=1))
    spread=np.repeat(np.sqrt(variance)[:,None],y.shape[1],axis=1)
    return mean,spread,dict(kind=kind,length_x3=length,noise_sd_normalized=.001,numerical_jitter=1e-10,
        train_x3=x.tolist(),alpha=alpha.tolist(),anchor='paired deviations f(0)=0')


def fit_select(bundle,*,parent_fit_approval,wall_cap_s=120.,on_fit_receipt=None):
    """Future approved single-CPU fit; returns a freezeable pure JSON result.

    The caller owns clocks, source/data SHA freeze, owner quiescence and any
    separately authorized original physical fork. This function never dispatches.
    """
    if parent_fit_approval.get('authorized') is not True or not parent_fit_approval.get('approval_id'):
        return abstain('EXPLICIT_PARENT_FIT_APPROVAL_REQUIRED',fits_executed=0)
    if parent_fit_approval.get('dataset_class')!=bundle.get('dataset_class'):
        return abstain('SYNTHETIC_REAL_APPROVAL_CLASS_MISMATCH',fits_executed=0)
    if wall_cap_s>120. or wall_cap_s<=0:return abstain('UNAPPROVED_CPU_TIME_BUDGET',fits_executed=0)
    reason=validate(bundle)
    if reason:return abstain(reason,fits_executed=0,input_sha256=digest(bundle))
    import numpy as np
    start=time.monotonic();cpu=time.process_time();fit_count=0
    def fitted(model,phase,held_x3=None):
        nonlocal fit_count
        fit_count+=1
        if on_fit_receipt is not None:on_fit_receipt(dict(index=fit_count,model=model,phase=phase,held_x3=held_x3,
            scalar_heads=y.shape[1],dataset_class=bundle['dataset_class'],wall_s=time.monotonic()-start,cpu_s=time.process_time()-cpu))
    def guard():
        if time.monotonic()-start>=wall_cap_s or time.process_time()-cpu>=120.:raise TimeoutError('REGISTERED_C2B_CPU_BUDGET')
    rows=sorted(bundle['observations'],key=lambda r:r['x3']);names=['delta_JF_N_s','delta_JM_Nm_s']+list(bundle['margin_names'])
    center=next(r for r in rows if r['x3']==0.);base=np.asarray([center['motion_margins'][k] for k in names[2:]])
    x=np.asarray([r['x3'] for r in rows],float);scales=np.asarray([1.,.1]+[1.]*len(base))
    y=np.asarray([[r['delta_JF_N_s'],r['delta_JM_Nm_s']]+[r['motion_margins'][k]-center['motion_margins'][k] for k in names[2:]] for r in rows])/scales
    query=np.asarray(GRID);predictions={};fits={};loo={}
    for model in MODELS:
        guard();mean,spread,fit=_fit_predict(np,model,x,y,query);fitted(model,'FULL_GRID')
        mean=mean*scales;spread=spread*scales;mean[:,2:]+=base
        train_mean,_,_=_fit_predict(np,model,x,y,x);fitted(model,'IN_SAMPLE_DIAGNOSTIC')
        # This repeated fit is counted; no hidden free training/optimization.
        errors=[]
        for index in range(len(x)):
            if x[index]==0.:continue
            guard();keep=np.arange(len(x))!=index
            held,_,_=_fit_predict(np,model,x[keep],y[keep],x[index:index+1]);fitted(model,'LEAVE_ONE_NONZERO_ACTION_OUT',float(x[index]))
            errors.append(dict(held_x3=float(x[index]),residual=(held[0]-y[index]).tolist()))
        predictions[model]=[dict(x3=float(q),mean=dict(zip(names,m.tolist())),spread=dict(zip(names,s.tolist()))) for q,m,s in zip(query,mean,spread)]
        fits[model]=fit;loo[model]=dict(in_sample_residual_RMS_normalized=np.sqrt(np.mean((train_mean-y)**2,axis=0)).tolist(),leave_one_nonzero_action_out=errors,
            interpretation='exposed local diagnostic; not independent validation or calibrated safety')
    best=min([r for r in rows if r['qualified']],key=lambda r:(r['delta_JF_N_s'],abs(r['x3']),r['x3']))
    fixed=min([r for r in rows if r['qualified'] and r['x3'] in (-.25,0.,.25)],key=lambda r:(r['delta_JF_N_s'],abs(r['x3']),r['x3']))
    attempted=[float(v) for v in bundle['attempted_x3']];candidates=[]
    for index,q in enumerate(query):
        reasons=[]
        if any(abs(q-v)<=1e-12 for v in attempted):reasons.append('ALREADY_ATTEMPTED_SEMANTIC_X3')
        upperJF=[];upperJM=[];lowermargins=[]
        for model in MODELS:
            p=predictions[model][index];mean=p['mean'];spread=p['spread']
            upperJF.append(mean[names[0]]+2.*spread[names[0]])
            upperJM.append(mean[names[1]]+2.*spread[names[1]])
            lowermargins.extend(mean[k]-2.*spread[k] for k in names[2:])
        worstJF=max(upperJF);worstJM=max(upperJM);minimumMargin=min(lowermargins)
        if worstJF>best['delta_JF_N_s']-.01:reasons.append('NO_ALL_MODEL_CONSERVATIVE_FORCE_INCREMENT')
        if worstJM>0.:reasons.append('JM_COMPONENT_RISK')
        if minimumMargin<0.:reasons.append('ORIGINAL_MOTION_COMPONENT_RISK')
        candidates.append(dict(x3=float(q),eligible=not reasons,reasons=reasons,worst_model_JF_upper_N_s=worstJF,
            worst_model_JM_upper_Nm_s=worstJM,minimum_model_component_lower_margin=minimumMargin))
    eligible=[r for r in candidates if r['eligible']]
    cost_only=[r for r in candidates if 'ALREADY_ATTEMPTED_SEMANTIC_X3' not in r['reasons']]
    cost_only_best=min(cost_only,key=lambda r:(r['worst_model_JF_upper_N_s'],abs(r['x3']),r['x3'])) if cost_only else None
    selected=min(eligible,key=lambda r:(r['worst_model_JF_upper_N_s'],-r['minimum_model_component_lower_margin'],abs(r['x3']),r['x3'])) if eligible else None
    signed={r['x3']:r for r in rows};finite_difference={}
    def vector(r):return [r['delta_JF_N_s'],r['delta_JM_Nm_s']]+[r['motion_margins'][k] for k in names[2:]]
    minus,zero,plus=[vector(signed[v]) for v in (-.25,0.,.25)]
    for i,name in enumerate(names):finite_difference[name]=dict(central_first=(plus[i]-minus[i])/.5,central_second=(plus[i]-2.*zero[i]+minus[i])/(.25**2))
    guard()
    return dict(status='PROPOSE_ONE_FROZEN_GRID_ACTION' if selected else 'ABSTAIN',reason=None if selected else 'NO_REGISTERED_GRID_POINT_MEETS_COMPONENT_RULE',
        selected_x3=None if selected is None else selected['x3'],selected_action=None if selected is None else dict(family='modal8_retimed',x=[0.,0.,0.,selected['x3'],0.,0.,0.,0.],legacy=[0.,0.]),
        input_sha256=digest(bundle),parent_snapshot_sha256=bundle['parent_snapshot_sha256'],head_names=names,
        predictions=predictions,model_fits=fits,diagnostics=loo,finite_difference=finite_difference,
        best_observed_qualified=dict(id=best['id'],x3=best['x3'],delta_JF_N_s=best['delta_JF_N_s']),
        strongest_observed_fixed=dict(id=fixed['id'],x3=fixed['x3'],delta_JF_N_s=fixed['delta_JF_N_s']),
        grid_audit=candidates,cost_only_grid_ranking_first=cost_only_best,fit_matrix_solves=fit_count,unique_actions=len(rows),scalar_heads=len(names),
        wall_s=time.monotonic()-start,cpu_s=time.process_time()-cpu,parent_fit_approval=parent_fit_approval,
        dataset_class=bundle['dataset_class'],real_data_training_runs=0 if bundle['dataset_class']=='SYNTHETIC_ONLY' else 1,
        uncertainty='DATA_LIMITED_HEURISTICS_NOT_SAFETY_CALIBRATION',new_physics=0,
        final_gate='Any future real task must pass unchanged original full physical/scientific/R2/motion gates; no automatic dispatch')
