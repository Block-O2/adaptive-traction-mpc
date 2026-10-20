"""Post-execution measured evidence only, never tune or dispatch."""
from pathlib import Path
import sys, os, json, time, hashlib, collections
sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1')
OLD=S.parent/'b_fast_jitter_m2_host_v1'
sys.path.insert(0,str(S/'code'))
import numpy as np
from stream_runtime_evidence import array_items
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def load(p):return json.loads(p.read_text())
def save(name,value):
    unavailable=[]
    def clean(x,path='$'):
        if isinstance(x,dict):return {k:clean(v,path+'.'+str(k)) for k,v in x.items()}
        if isinstance(x,list):return [clean(v,path+'['+str(i)+']') for i,v in enumerate(x)]
        if isinstance(x,float) and not np.isfinite(x):
            unavailable.append(dict(path=path,raw_nonfinite=str(x),exported_value=None,meaning='NOT_EVALUABLE; original raw artifact retained'))
            return None
        return x
    result=clean(value)
    result['raw_nonfinite_fields']=unavailable
    (S/name).write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(x):
    return dict(n=len(x),values=x,min=float(np.min(x)),max=float(np.max(x)),mean=float(np.mean(x)),median=float(np.median(x)),sample_sd=float(np.std(x,ddof=1)) if len(x)>1 else None) if x else dict(n=0,values=[],min=None,max=None,mean=None,median=None,sample_sd=None)
def traces(base,ident):
    with np.load(base/'source/results'/ident/'trace.npz') as z:return {k:z[k].copy() for k in z.files}
def boundary_state(z,t):
    ix=int(np.argmin(np.abs(z['time_s']-t)))
    return dict(requested_physics_s=t,actual_trace_physics_s=float(z['time_s'][ix]),nearest_sample_offset_s=float(z['time_s'][ix]-t),true_human_q_dq_deg_deg_s=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][ix]).tolist(),estimated_human_q_dq_deg_deg_s=np.rad2deg(z['estimated_human_state_rad_rad_s'][ix]).tolist(),reference_q_deg=np.rad2deg(z['reference_q_rad'][ix]).tolist(),force_N=float(np.linalg.norm(z['physical_cuff_force_world_n'][ix])),moment_Nm=float(np.linalg.norm(z['physical_cuff_moment_world_nm'][ix])),measured_sleeve_gap_m=float(z['dev_d_measured_sleeve_gap_m'][ix]),session_shank_clearance_m=float(z['session_shank_clearance_m'][ix]))
def commissioning(base,ident,z,summary):
    m=load(base/'reports'/(ident+'_AXES.json'))['metric'];c=summary['commissioning'];first=summary['learning_records'][0]['adaptive_state']
    out={k:m.get(k) for k in ('initial_estimated_state','initial_reference','model_beta','model_residual','model_updates_task')}
    out.update(adaptive_state_at_first_task_request=first,commissioning_top_keys=list(c),commissioning_compact={k:v for k,v in c.items() if 'history' not in k and len(json.dumps(v))<12000},trace_first_task_beta=z['task_beta'][0].tolist(),trace_first_task_residual_weights_nm=z['task_residual_weights_nm'][0].tolist())
    return out
def lineage_run(base,ident):
    axis=load(base/'reports'/(ident+'_AXES.json'));ep=base/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');ev=load(ep);summ=load(base/'source/results'/ident/'summary.json');z=traces(base,ident);m=axis['metric']
    rows=[]
    for r in ev['rows']:
        ss=r['selection'];receipt=r['actual_command_receipts'];meta=r['native_coordination_metadata'];accepted=[x for x in meta if x.get('status')=='ACCEPTED']
        start=min([v['start_physics_s'] for v in receipt] or [ss['physical_source_s'] if ss else 0]);end=max([v['end_physics_s'] for v in receipt] or [start]);phase=None if ss is None else ss['context']['phase']
        row=dict(request_id=r['request_id'],decision_source_capture_ns=r['source_capture_ns'],decision_physics_s=None if ss is None else ss['physical_source_s'],phase=phase,selected_K3=r['applied_current_K3'],proposed_K3=r['proposed_current_K3'],selected_delta_d=[x.get('delta') for x in accepted],candidate_identity=r['candidate_identity'],raw_ranking=None if ss is None else ss.get('q_first_order'),raw_scores=None if ss is None else ss.get('q_all'),candidate_records=None if ss is None else ss['candidate_records'],admission=r['worker']['admission'],lifecycle=r['lifecycle'],native_coordination_metadata=meta,physically_executed_nonzero=r['physically_executed_nonzero'],new_selection_executed=r['new_selected_Q_executed'],carry_executed=r['carried_learning_residual_executed'],receipt_count=len(receipt),native_steps=r['actual_native_steps'],receipts=receipt,execution_start_physics_s=start,execution_end_physics_s=end,decision_trace_state=None if ss is None else boundary_state(z,ss['physical_source_s']),execution_start_trace_state=boundary_state(z,start),execution_end_trace_state=boundary_state(z,end),ownership_join=r['receipt_join'])
        rows.append(row)
    phase={p:dict(selected=sum(r['phase']==p for r in rows),activated=sum(r['phase']==p and r['lifecycle'].get('outcome')=='ACTIVATED' for r in rows),executed_nonzero=sum(r['phase']==p and r['physically_executed_nonzero'] for r in rows),native_steps=sum(r['native_steps'] for r in rows if r['phase']==p and r['physically_executed_nonzero']),new_selection=sum(r['phase']==p and r['new_selection_executed'] for r in rows),carry=sum(r['phase']==p and r['carry_executed'] for r in rows)) for p in ('OUTBOUND','HOLD','RETURN')}
    co=load(base/'output'/(ident+'_HOST_COORDINATOR.json'));requests=load(base/'output'/(ident+'_MULTIRATE.json'))['native_requests'];task=[r for r in requests if r['stage']=='TASK'];functional=load(base/'reports'/(ident+'_FUNCTIONAL.json'));art=base/'source/results'/ident/'runtime_artifacts.json.gz'
    command_stats=collections.Counter();command_examples={}
    for r in array_items(art,'command_receipts'):
        for key in ('command_kind','reference_source','mode','cancelled_before_write_reason','command_expired','fallback','expired'):
            if r.get(key) is not None:
                label=key+':'+str(r[key]);command_stats[label]+=1
                if label not in command_examples:command_examples[label]={k:r.get(k) for k in ('receipt_index','source_capture_ns','apply_ns','start_physics_s','end_physics_s','native_steps',key)}
    compact=commissioning(base,ident,z,summ)
    sourcefiles=[ep,base/'reports'/(ident+'_AXES.json'),base/'output'/(ident+'_RESULT.json'),base/'output'/(ident+'_HOST_COORDINATOR.json'),base/'output'/(ident+'_MULTIRATE.json'),base/'source/results'/ident/'trace.npz',base/'source/results'/ident/'summary.json',art,base/'queue'/(ident+'.json')]
    return dict(id=ident,status='PASS' if axis['PHYSICAL_TASK_VALID']=='PASS' and axis['HOST_EXECUTION_CAUSAL_VALID']=='PASS' else 'FAIL',source_files=[dict(path=str(p),sha256=sha(p)) for p in sourcefiles],rows=rows,phase_execution=phase,request_outcomes=axis['request_outcomes'],native_task_requests=len(task),coordinator_proposals=len(co['rows']),Q_selections=axis['selection_count'],new_selection_executed=sum(r['new_selection_executed'] for r in rows),carry_executed=sum(r['carry_executed'] for r in rows),activations=sum(r['outcome']=='ACTIVATED' for r in task),nonzero_plans=axis['nonzero_execution_count'],nonzero_native_steps=axis['nonzero_native_steps'],all_physical_native_steps=axis['native_steps'],late_carry=axis['late_carry_count'],rejections=axis['rejections'],receipt_event_counts=dict(command_stats),receipt_event_examples=command_examples,expired_actual_write_receipts=functional['expired_actual_write_receipts'],phase_boundaries=summ['task']['phase_transitions'],commissioning=compact)
def pair_enrich(base,p):
    p=dict(p);p['delta_J_F_M2_minus_B_N_s']=p['raw_M2_J_F_N_s']-p['raw_B_J_F_N_s'];p['relative_delta_J_F_percent']=-p['gain_percent'];p['classification']='NEW_PREREGISTERED_HOST_PAIR' if base==S else 'HISTORICAL_HOST_PAIR'
    b=p['B_id'];m=p['M2_id'];cfgb=load(base/'queue'/(b+'.json'));cfgm=load(base/'queue'/(m+'.json'))
    p['prefix']=cfgb['prefix'];p['seed']=cfgb['seed'];p['config_identity_diff']={k:[cfgb.get(k),cfgm.get(k)] for k in cfgb.keys()|cfgm.keys() if cfgb.get(k)!=cfgm.get(k)}
    assert not(set(p['config_identity_diff'])-{'id','method','durable_config_path'})
    records={}
    for ident in (b,m):
        z=traces(base,ident);summary=load(base/'source/results'/ident/'summary.json');a=load(base/'reports'/(ident+'_AXES.json'));trans={r['to']:r['time_s'] for r in summary['task']['phase_transitions']};scorer=a['metric']['physical_audit']['unchanged_evaluator']['raw_scorer_v2'];physical=p['physical_summary'][ident]
        safety_thresholds={}
        first=summary['learning_records'][0];screen=first['selected_plan']['execution_screen'] if 'selected_plan' in first else {}
        # Only actual frozen execution-screen thresholds are used; no guessed ROM/speed limits.
        for rr in summary['learning_records']:
            plan=rr.get('selected_plan',{});screen=plan.get('execution_screen',{})
            for key in ('force_limit_n','moment_limit_nm'):
                if key in screen:safety_thresholds.setdefault(key,[]).append(screen[key])
        limits={k:min(v) for k,v in safety_thresholds.items()}
        margin=dict(force_headroom_N=None if 'force_limit_n' not in limits else limits['force_limit_n']-a['metric']['force_peak'],moment_headroom_Nm=None if 'moment_limit_nm' not in limits else limits['moment_limit_nm']-a['metric']['moment_peak'],robot_torque_fraction_headroom=1-scorer['peak_robot_torque_fraction'],true_shank_clearance_to_contact_m=scorer['minimum_true_shank_clearance_m'],measured_sleeve_gap_to_contact_m=scorer['minimum_measured_sleeve_gap_m'],session_shank_clearance_to_contact_m=scorer['minimum_session_shank_clearance_m'],all_original_safety_conditions=scorer['conditions'],force_moment_limits_source='actual selected native execution_screen, unchanged',unsupplied_threshold_margins='NOT_EVALUABLE; preserve original condition result and raw peak, never invent thresholds')
        task=z['stage']=='TASK';err=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][task,:2]-z['reference_q_rad'][task]);phase_stats={}
        for ph in ('OUTBOUND','HOLD','RETURN'):
            ix=task&(z['task_phase']==ph);e=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][ix,:2]-z['reference_q_rad'][ix]);phase_stats[ph]=dict(true_reference_tracking_RMS_deg=np.sqrt(np.mean(e**2,axis=0)).tolist(),measured_min_clearance_m=float(z['dev_d_measured_sleeve_gap_m'][ix].min()),session_min_clearance_m=float(z['session_shank_clearance_m'][ix].min()),samples=int(ix.sum()))
        records[ident]=dict(force_mean_N=a['metric']['force_mean'],phase_weighted_mean_force_N=a['metric']['J_F']/a['phase_cost']['integrated_trace_duration_s'],moment_integral_Nm_s=a['metric']['moment_integral'],force_peak_N=a['metric']['force_peak'],moment_peak_Nm=a['metric']['moment_peak'],physical=physical,safety_margins=margin,phase_tracking_clearance=phase_stats,entry_HOLD=boundary_state(z,trans['HOLD']),entry_RETURN=boundary_state(z,trans['RETURN']),initial_TASK=boundary_state(z,z['time_s'][task][0]),commissioning=commissioning(base,ident,z,summary),phase_clock_duration_s=a['metric']['phase_durations'],integrated_duration_s=a['phase_cost']['integrated_trace_duration_s'])
    bd=records[b];md=records[m];p['evaluation_records']=records
    p['commissioning_difference']=dict(beta_delta=(np.asarray(md['commissioning']['trace_first_task_beta'])-bd['commissioning']['trace_first_task_beta']).tolist(),residual_weights_delta_nm=(np.asarray(md['commissioning']['trace_first_task_residual_weights_nm'])-bd['commissioning']['trace_first_task_residual_weights_nm']).tolist(),beta_delta_l2=float(np.linalg.norm(np.asarray(md['commissioning']['trace_first_task_beta'])-bd['commissioning']['trace_first_task_beta'])),residual_weights_delta_l2=float(np.linalg.norm(np.asarray(md['commissioning']['trace_first_task_residual_weights_nm'])-bd['commissioning']['trace_first_task_residual_weights_nm'])),interpretation='Measured real host commissioning fit differences; initial physical case/seed matched, fits not forced equal and effects not identified')
    p['entry_RETURN_true_state_delta_deg_deg_s']=(np.asarray(md['entry_RETURN']['true_human_q_dq_deg_deg_s'])-bd['entry_RETURN']['true_human_q_dq_deg_deg_s']).tolist()
    p['tradeoff_deltas']=dict(moment_integral_Nm_s=md['moment_integral_Nm_s']-bd['moment_integral_Nm_s'],force_peak_N=md['force_peak_N']-bd['force_peak_N'],moment_peak_Nm=md['moment_peak_Nm']-bd['moment_peak_Nm'],true_reference_RMS_deg=(np.asarray(md['physical']['true_reference_tracking_RMS_deg'])-bd['physical']['true_reference_tracking_RMS_deg']).tolist(),true_clearance_m=md['physical']['minimum_true_shank_clearance_m']-bd['physical']['minimum_true_shank_clearance_m'],measured_clearance_m=md['physical']['minimum_measured_sleeve_gap_m']-bd['physical']['minimum_measured_sleeve_gap_m'])
    p['phase_integral_closure_error_N_s']={ident:sum(p['phases'][ph]['B' if ident==b else 'M2']['J_F_N_s'] for ph in ('OUTBOUND','HOLD','RETURN'))-(p['raw_B_J_F_N_s'] if ident==b else p['raw_M2_J_F_N_s']) for ident in (b,m)}
    assert max(abs(x) for x in p['phase_integral_closure_error_N_s'].values())<1e-8
    return p
def main():
    reg=load(S/'reports/PAIR_REGISTRATION.json');ledger=load(S/'TASK_LEDGER.json')
    # Existing unchanged pair evaluator provides full-trace metrics. Incomplete rows stay visible.
    import paired_results
    paired_results.main()
    raw=load(S/'PAIRED_RESULTS.json');pairs=[];incomplete=[]
    # The inherited helper assumes two repeats per condition. Correct only this
    # new derived file's summary schema; never alter its frozen evaluator.
    for condition,summary in raw['summary'].items():
        summary.pop('both_improved',None)
        summary['all_improved']=bool(summary['gain_N_s'] and min(summary['gain_N_s'])>0)
    save('PAIRED_RESULTS.json',raw)
    for p in raw['pairs']:
        if p['status']=='VALID_PAIR' and load(S/'reports'/(p['M2_id']+'_AXES.json'))['nonzero_execution_count']>0:
            p=pair_enrich(S,p);p['status']='PASS';pairs.append(p)
        else:incomplete.append({**p,'status':'NOT_RUN' if p['status']=='NOT_RUN' else 'PARTIAL'})
    all_runs=[]
    for r in reg['pairs']:
        for ident in r['ids']:
            ep=S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
            if ep.exists() and (S/'reports'/(ident+'_AXES.json')).exists():
                a=load(S/'reports'/(ident+'_AXES.json'))
                if a.get('PHYSICAL_TASK_VALID')=='PASS':all_runs.append(lineage_run(S,ident))
    hist=[pair_enrich(OLD,p) for p in load(OLD/'PAIRED_RESULTS.json')['pairs'] if p['status']=='VALID_PAIR']
    historical_m2=[lineage_run(OLD,p['M2_id']) for p in hist]
    jf=stats([p['delta_J_F_M2_minus_B_N_s'] for p in pairs]);rel=stats([p['relative_delta_J_F_percent'] for p in pairs]);duration=sum(p['duration_contribution_sum_N_s'] for p in pairs);force=sum(p['mean_force_contribution_sum_N_s'] for p in pairs);delta=sum(p['delta_J_F_M2_minus_B_N_s'] for p in pairs);totalB=sum(p['raw_B_J_F_N_s'] for p in pairs)
    aggregate=dict(valid_pairs=len(pairs),planned_pairs=4,improved_pairs=sum(p['delta_J_F_M2_minus_B_N_s']<0 for p in pairs),delta_J_F_N_s=jf,relative_delta_J_F_percent=rel,pooled_delta_J_F_N_s=delta,pooled_delta_percent=100*delta/totalB if totalB else None,duration_contribution_N_s=duration,mean_force_contribution_N_s=force,mean_force_fraction_of_total_delta=force/delta if delta else None,RETURN_delta_J_F_N_s=sum(p['phases']['RETURN']['delta_J_F_M2_minus_B_N_s'] for p in pairs),RETURN_fraction_of_total_delta=sum(p['phases']['RETURN']['delta_J_F_M2_minus_B_N_s'] for p in pairs)/delta if delta else None,statistical_scope='Descriptive n=4 matched pairs, only two prescribed perturbations and one nominal Human. Seeds repeat across prefixes; no independent-population significance or online personalization claim.')
    out=dict(status='PASS' if len(pairs)==4 else 'PARTIAL',pairs=pairs+incomplete,summary=aggregate,historical_pairs_separate=hist,preregistration_sha256=sha(S/'EXPERIMENT_MANIFEST.json'),no_outcome_exclusion=True,primary_sign='Delta J_F=M2-B; negative improves',Q_updates=0)
    save('PAIRED_HOST_RESULTS.json',out)
    lineage=dict(status='PASS' if len(all_runs)==8 else 'PARTIAL',runs=all_runs,historical_M2_runs_separate=historical_m2,nonzero_plans=sum(r['nonzero_plans'] for r in all_runs),nonzero_native_steps=sum(r['nonzero_native_steps'] for r in all_runs),all_physical_native_steps=sum(r['all_physical_native_steps'] for r in all_runs),receipt_proof='Q selection -> original certified native proposal -> unchanged current-state admission -> actual command receipts -> every native step audited; ACTIVATED alone never counted',Q_updates=0,G_calls=0,training_calls=0)
    save('EXECUTION_LINEAGE.json',lineage)
    trade=dict(status=out['status'],pairs=[{k:p[k] for k in ('pair_id','delta_J_F_M2_minus_B_N_s','relative_delta_J_F_percent','moment_delta_percent','tradeoff_deltas','evaluation_records')} for p in pairs],summary=dict(moment_integral_delta_percent=stats([p['moment_delta_percent'] for p in pairs]),knee_RMS_delta_deg=stats([p['tradeoff_deltas']['true_reference_RMS_deg'][1] for p in pairs]),hip_RMS_delta_deg=stats([p['tradeoff_deltas']['true_reference_RMS_deg'][0] for p in pairs]),force_peak_delta_N=stats([p['tradeoff_deltas']['force_peak_N'] for p in pairs]),true_clearance_delta_mm=stats([p['tradeoff_deltas']['true_clearance_m']*1000 for p in pairs]),measured_clearance_delta_mm=stats([p['tradeoff_deltas']['measured_clearance_m']*1000 for p in pairs]),force_gain_with_moment_increase_count=sum(p['delta_J_F_M2_minus_B_N_s']<0 and p['tradeoff_deltas']['moment_integral_Nm_s']>0 for p in pairs),force_gain_with_knee_RMS_increase_count=sum(p['delta_J_F_M2_minus_B_N_s']<0 and p['tradeoff_deltas']['true_reference_RMS_deg'][1]>0 for p in pairs)),no_new_weighted_reward=True)
    save('MULTIOBJECTIVE_TRADEOFFS.json',trade)
    runtime=[]
    for run in all_runs:
        ident=run['id'];a=load(S/'reports'/(ident+'_AXES.json'));f=load(S/'reports'/(ident+'_FUNCTIONAL.json'));e=load(S/'output'/(ident+'_MULTIRATE.json'));services=e['rows']['fast'];intervals=np.diff([r['service_start_ns'] for r in services])/1e6;compute=[(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in services if r.get('service_finish_ns') is not None];task=[r for r in e['native_requests'] if r['stage']=='TASK'];ages=[r['activation_age_ms'] for r in task if r.get('activation_age_ms') is not None]
        def pct(x):return dict(n=len(x),p50=float(np.percentile(x,50)),p95=float(np.percentile(x,95)),p99=float(np.percentile(x,99)),max=float(max(x))) if x else dict(n=0)
        runtime.append(dict(id=ident,observed_FAST_status=a['FAST_RUNTIME_ENGINEERING_QUALIFIED'],formal_runtime_qualification='NOT_RUN',service_start_gap_ms=a['service_gap_ms'],service_wall_compute_ms=pct(compute),rolling_1s_mean_ms=a['rolling_1s_ms'],callback_miss_fraction=a['miss_fraction'],gap_over10ms_fraction=f['gap_over_10_fraction'],backlog=a['backlog'],proposal_compute_ms=pct([r['compute_ms'] for r in task if r.get('compute_ms') is not None]),activation_age_ms=pct(ages),request_outcomes=a['request_outcomes'],late_carry=a['late_carry_count'],rejections=a['rejections'],expired_actual_writes=f['expired_actual_write_receipts'],legacy_R2=a['LEGACY_R2_MATCHED'],legacy_strict55=a['LEGACY_STRICT55'],physical=a['PHYSICAL_TASK_VALID'],causal_host=a['HOST_EXECUTION_CAUSAL_VALID'],thread_CPU_scheduler_wait='NOT_RUN unless historical slowdown recurrence on actual compiled loop'))
    fast=dict(status='PASS' if len(runtime)==8 and all(r['observed_FAST_status']=='PASS' for r in runtime) else 'PARTIAL',runs=runtime,historical_slowdown_cause='NOT_EVALUABLE / remains unknown',formal_runtime_qualification='NOT_RUN',hardware_deployment='NOT_RUN',resource_log_path=str(S/'output/RESOURCE_LOG.jsonl'),instrumentation='unchanged lean native timing and45s resource sampling; no added CPU/wait hooks in paired physics',no_engineering_changes=True)
    save('FAST_RUNTIME_OBSERVATIONS.json',fast)
    return_text='# RETURN 收益归因\n\n状态：'+out['status']+'。完整 TASK trace 按实际 OUTBOUND/HOLD/RETURN 转换边界分区，以原 left-endpoint quadrature 计算。保留 phase-clock 与 integrated-trace durations；无 HOLD 裁剪。\n\n| Pair | ΔJ_F N·s | ΔRETURN N·s | 时长贡献 N·s | 平均力贡献 N·s | RETURN 非零计划 / OUTBOUND 非零计划 |\n|---|---:|---:|---:|---:|---:|\n'
    runmap={r['id']:r for r in all_runs}
    for p in pairs:
        r=runmap[p['M2_id']];return_text+=f"| {p['pair_id']} | {p['delta_J_F_M2_minus_B_N_s']:.6f} | {p['phases']['RETURN']['delta_J_F_M2_minus_B_N_s']:.6f} | {p['duration_contribution_sum_N_s']:.6f} | {p['mean_force_contribution_sum_N_s']:.6f} | {r['phase_execution']['RETURN']['executed_nonzero']} / {r['phase_execution']['OUTBOUND']['executed_nonzero']} |\n"
    return_text+=f"\n合并 ΔJ_F={delta:.9f} N·s；时长项 {duration:.9f}，平均力项 {force:.9f} N·s。RETURN 占合并差值比例 {aggregate['RETURN_fraction_of_total_delta'] if delta else None}，平均力项占 {aggregate['mean_force_fraction_of_total_delta'] if delta else None}。各阶段满足 ΔJ=(T_M−T_B)(F̄_M+F̄_B)/2+(F̄_M−F̄_B)(T_M+T_B)/2，阶段积分闭合误差均 <1e−8 N·s。各阶段分解、完整时钟、真实 hip/knee/reference/force/moment/clearance 边界状态与真实 commissioning fit 差值在 PAIRED_HOST_RESULTS.json。\n"
    return_text+='\nQ decision source time、raw ranking、所选 K3 与 native Δd、admission/lifecycle、真实 receipt 与 native steps、开始/结束物理状态在 EXECUTION_LINEAGE.json 逐请求对齐。OUTBOUND 与 RETURN 各自执行数和 native steps 明确区分。当前接口不对 HOLD 发 Q 选择。旧4对结果独立存储，不能扩充本轮 n。\n\n机制判断：线性 Q 对固定 masked plan 的偏好不具有状态交互；重复 residual 与 RETURN 效应更符合固定 residual 偏好经过 native feasibility、mask 与 carry 筛选的解释。进入 RETURN 的真实状态差值已测量；OUTBOUND 残余、commissioning fit 与 host timing 的贡献没有被独立随机化，不能将阶段分解或平均力下降宣称为严格因果识别。B/M2 配对保留同一合法 prefix；比较的是公共扰动后 residual coordination 的附加价值。\n'
    (S/'RETURN_ATTRIBUTION.md').write_text(return_text)
    save('reports/ANALYSIS_SUMMARY.json',dict(status=out['status'],aggregate=aggregate,tradeoff_summary=trade['summary'],execution_summary={k:lineage[k] for k in ('nonzero_plans','nonzero_native_steps','all_physical_native_steps')},runs=[{k:r[k] for k in ('id','observed_FAST_status','physical','causal_host','legacy_R2','legacy_strict55')} for r in runtime]))
    print(json.dumps(dict(status=out['status'],aggregate=aggregate,tradeoffs=trade['summary'],native_plans=lineage['nonzero_plans']),ensure_ascii=False))
if __name__=='__main__':main()
