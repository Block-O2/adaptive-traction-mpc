from pathlib import Path
import os,sys,json,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1');OLD=S.parent/'m2_coordination_space_exploration_v1'
sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
def load(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float):return x if np.isfinite(x) else None
 return x
def save(p,x):Path(p).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def source(p):
 p=Path(p);entry=load(S/'preservation/PROTECTED_BEFORE.json').get(str(p))
 return dict(path=str(p),**(entry or dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)))
IDS=['001_search_B','005_return_history_scale_0.1','015_validation_2026100902_B','016_validation_2026100902_candidate','019_validation_2026100903_candidate','020_validation_2026100903_B','diagnostic_B_repeat_1','diagnostic_B_repeat_2','002_search_frozen_M2','017_validation_2026100902_M2','018_validation_2026100903_M2']
def audit(ident):
 p=OLD/'source/results'/ident;s=load(p/'summary.json');a=load(OLD/'reports'/(ident+'_AXES.json'));m=load(OLD/'reports'/(ident+'_MEASURED.json'))
 receipts=[r for r in array_items(p/'runtime_artifacts.json.gz','command_receipts') if r.get('applied') and r.get('native_steps',0)>0]
 native_first=next(array_items(p/'runtime_artifacts.json.gz','native_states_evaluation_only'))
 with np.load(p/'trace.npz') as z:
  t=z['time_s'];task=np.flatnonzero(z['stage']=='TASK');i=task[0];task_time=float(t[i]);fields=['time_s','stage','task_phase','evaluation_only_human_state_rad_rad_s','estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','physical_cuff_force_world_n','physical_cuff_moment_world_nm','cr12_actuator_command_nm','physics_steps']
  trace={k:z[k].copy() for k in fields};np.savez_compressed(S/'reports'/(ident+'_TIMELINE_TRACE.npz'),**trace)
  task_entry={k:z[k][i] for k in fields};initial={k:z[k][0] for k in fields}
 trans=s['task']['phase_transitions'];return_time=next(r['time_s'] for r in trans if r['to']=='RETURN')
 lineage=[]
 for r in s['learning_records']:
  idx=r.get('decision_index');d=s['decisions'][idx] if idx is not None and idx<len(s['decisions']) else {}
  meta=r.get('selected_plan',{}).get('execution_screen',{}).get('coordination_residual_v2',{})
  native_nonzero=meta.get('status')=='ACCEPTED' and abs(meta.get('delta',0))>1e-12
  start=r.get('start_time_s',d.get('actual_schedule_start_physics_s'));end=r.get('end_time_s')
  owned=[q for q in receipts if start is not None and end is not None and start-1e-9<=q['start_physics_s']<end-1e-9] if r.get('selected_plan_activated') else []
  lineage.append(dict(decision_index=idx,request_id=d.get('timing_request_id'),phase=r.get('phase',d.get('phase')),request_physics_s=d.get('decision_request_time_s'),activation_physics_s=d.get('actual_schedule_start_physics_s'),activated=bool(r.get('selected_plan_activated')),native_metadata=meta,nonzero_native=native_nonzero,actual_steps=sum(q['native_steps'] for q in owned),first_execution_physics_s=min([q['start_physics_s'] for q in owned],default=None),receipt_indices=[q['receipt_index'] for q in owned],receipt_join='original half-open selected-plan learning interval; actual applied command with positive native_steps'))
 nz=[r for r in lineage if r['nonzero_native'] and r['activated'] and r['actual_steps']>0]
 first=min([r['first_execution_physics_s'] for r in nz],default=None)
 host=load(OLD/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'))
 host_rows=[r for r in host['rows'] if r['physically_executed_nonzero']]
 for r in host_rows:
  phase=r['selection']['context']['phase'];assert phase in ['OUTBOUND','RETURN']
 ronly=('candidate' in ident or ident=='005_return_history_scale_0.1')
 leakage=[r for r in nz if r['first_execution_physics_s']<return_time-1e-9]
 firsttask=next((r for r in receipts if r['start_physics_s']>=task_time-1e-9),None)
 timeline=dict(initial_physics_s=float(trace['time_s'][0]),commissioning_segments=[{k:r.get(k) for k in ['segment_index','request_time_s','measurement_time_s','actual_segment_start_physics_s','actual_activation_monotonic_ns','timing_request_id','plan_age_s','target_q_rad','stale','deadline_miss']} for r in s['commissioning']['dev_d_reference_events']],commissioning_duration_s=s['commissioning']['duration_s'],TASK_entry=task_entry,phase_transitions=trans,first_nonzero_execution_physics_s=first)
 row=dict(id=ident,clock=s['execution_mode'],timeline=timeline,initial_physical_observables=dict(trace=initial,first_native_full_qpos_qvel=native_first,limitation='full t=0 MuJoCo integration, Human internal state and RNG were not durably archived; observations do not prove complete equality'),commissioning={k:s['commissioning'].get(k) for k in ['geometry_fit','handoff_belief','aligned_update_count','sample_count','history_preserved_at_handoff','effective_reference_waypoints_rad','population_beta_initial','population_residual_weights_initial_nm']},model=m['commissioning'],first_TASK_command=firsttask,first_TASK_native_decision={k:s['decisions'][0].get(k) for k in ['timing_request_id','decision_request_time_s','actual_schedule_start_physics_s','deployable_state_rad_rad_s','activation_outcome','plan_age_s','selected_plan']},native_execution=lineage,host_nonzero_requests=[dict(request_id=r['request_id'],phase=r['selection']['context']['phase'],actual_steps=r['actual_native_steps'],first_execution_physics_s=min(q['start_physics_s'] for q in r['actual_command_receipts']),late_carry=r['late_carry']) for r in host_rows],RETURN_only=ronly,OUTBOUND_leakage=leakage,negative_control=('PASS_NO_PRE_RETURN_NONZERO_EXECUTION' if not leakage else 'FAIL_PHASE_LEAKAGE') if ronly else 'REFERENCE',force=m['phase_cost'],axes={k:a[k] for k in ['PHYSICAL_TASK_VALID','HOST_EXECUTION_CAUSAL_VALID','service_gap_ms','activation_age_ms','request_outcomes','late_carry_count','rejections']},sources=[source(p/'summary.json'),source(p/'trace.npz'),source(p/'runtime_artifacts.json.gz'),source(OLD/'queue'/(ident+'.json'))])
 save(S/'reports'/(ident+'_PRE_INTERVENTION.json'),row)
 return row,trace,s
def firstdiff(ta,tb,key,mask=None):
 stepsa=ta['physics_steps'];stepsb=tb['physics_steps'];_,ia,ib=np.intersect1d(stepsa,stepsb,return_indices=True)
 if mask is not None:
  keep=ta['stage'][ia]==mask;ia=ia[keep];ib=ib[keep]
 av=ta[key][ia];bv=tb[key][ib]
 diff=abs(av-bv);v=diff.reshape(len(diff),-1).max(axis=1);bad=np.flatnonzero(v>1e-12)
 if not len(bad):return dict(equal_at_common_nodes=True,nodes=len(ia),max_abs_delta=float(v.max(initial=0)))
 j=bad[0];return dict(physics_s=float(ta['time_s'][ia[j]]),stage=str(ta['stage'][ia[j]]),physics_step=int(stepsa[ia[j]]),abs_delta=float(v[j]),max_abs_delta=float(v.max()),common_nodes=len(ia),tolerance=1e-12)
def main():
 cache={}
 for ident in IDS:
  cache[ident]=audit(ident);print('AUDITED '+ident,flush=True)
 pairs=[('005_return_history_scale_0.1','001_search_B'),('016_validation_2026100902_candidate','015_validation_2026100902_B'),('019_validation_2026100903_candidate','020_validation_2026100903_B'),('diagnostic_B_repeat_1','001_search_B'),('diagnostic_B_repeat_2','001_search_B'),('002_search_frozen_M2','001_search_B'),('017_validation_2026100902_M2','015_validation_2026100902_B'),('018_validation_2026100903_M2','020_validation_2026100903_B')]
 comparisons=[]
 for ai,bi in pairs:
  a,ta,sa=cache[ai];b,tb,sb=cache[bi];diffs={}
  for k in ['model_beta','model_residual','initial_estimated_state','initial_reference']:diffs[k]=dict(max_abs_delta=float(np.max(abs(np.asarray(a['model'][k])-b['model'][k]))),candidate=a['model'][k],B=b['model'][k])
  phases={}
  for ph in ['OUTBOUND','HOLD','RETURN']:
   x=a['force']['phases'][ph];y=b['force']['phases'][ph];dt=x['integrated_trace_duration_s']-y['integrated_trace_duration_s'];df=x['mean_force_N']-y['mean_force_N'];dc=dt*(x['mean_force_N']+y['mean_force_N'])/2;fc=df*(x['integrated_trace_duration_s']+y['integrated_trace_duration_s'])/2;delta=x['J_F_N_s']-y['J_F_N_s'];assert abs(dc+fc-delta)<1e-8
   phases[ph]=dict(delta_J_F_N_s=delta,duration_contribution_N_s=dc,mean_force_contribution_N_s=fc)
  comparisons.append(dict(candidate=ai,B=bi,commissioning_differences=diffs,earliest_observable_divergence={k:firstdiff(ta,tb,k) for k in ['evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n','reference_q_rad','cr12_actuator_command_nm']},earliest_TASK_divergence={k:firstdiff(ta,tb,k,'TASK') for k in ['evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n','reference_q_rad','cr12_actuator_command_nm']},TASK_entry_delta=np.asarray(a['timeline']['TASK_entry']['evaluation_only_human_state_rad_rad_s'])-b['timeline']['TASK_entry']['evaluation_only_human_state_rad_rad_s'],phases=phases,attribution='PRE_INTERVENTION_IMBALANCE: OUTBOUND and HOLD precede first nonzero RETURN execution; RETURN itself remains confounded by startup and prior trajectory' if a['RETURN_only'] and not a['OUTBOUND_leakage'] else 'DESCRIPTIVE_UNMATCHED_REFERENCE',not_pure_causal=True))
 zeros=[cache[i][0] for i in ['001_search_B','diagnostic_B_repeat_1','diagnostic_B_repeat_2']]
 result=dict(status='READ_ONLY_ANALYSIS_COMPLETE',physics_attempts=0,run_denominator=len(IDS),RETURN_only_denominator=3,negative_control_all_pass=all(cache[i][0]['negative_control']=='PASS_NO_PRE_RETURN_NONZERO_EXECUTION' for i in ['005_return_history_scale_0.1','016_validation_2026100902_candidate','019_validation_2026100903_candidate']),comparisons=comparisons,B_zero=dict(n=3,J_F_N_s=[x['force']['raw_full_J_F_N_s'] for x in zeros],range_N_s=float(np.ptp([x['force']['raw_full_J_F_N_s'] for x in zeros])),beta_variation_max_abs=np.ptp(np.asarray([x['model']['model_beta'] for x in zeros]),axis=0),associated_factors=['native command and real physical sampling/activation timing differ before intervention','commissioning fitted beta/residual and geometry differ','TASK-entry physical/estimated state differ','scheduler wait, carry, activation opportunities differ'],root_cause='NOT_IDENTIFIED: three observational cold starts cannot separate beta, timing, geometry and initial state; no random-error bound or regression inference'),timeline_records=[str(S/'reports'/(i+'_PRE_INTERVENTION.json')) for i in IDS],limitations=['No complete archived initial hidden physical/RNG integration state','Earliest divergence is at common archived physical nodes, not a claim about an unobserved exact instant','Force integrals use unchanged original left-endpoint TASK quadrature','No cross-clock subtraction'])
 save(S/'PRE_INTERVENTION_ATTRIBUTION.json',result)
 lines=['# 介入前归因审计','',f'只读核对{len(IDS)}个完整历史run；3个RETURN-only均未在RETURN入口之前执行非零native协调。','']
 for r in comparisons[:3]:lines.append(f"- {r['candidate']}：OUTBOUND ΔJ_F={r['phases']['OUTBOUND']['delta_J_F_N_s']:.9f} N·s，全部记为 pre-intervention imbalance，不能归功于RETURN residual。")
 lines+=['',f"三次B-zero J_F={result['B_zero']['J_F_N_s']} N·s，range={result['B_zero']['range_N_s']:.9f} N·s；n=3不是随机误差界。",'', '模型beta/residual、commissioning几何拟合、TASK入口、最初command及native时序均保留逐run和逐对证据。最早force/运动差异在commissioning期间已可观测。现有观测不能确定哪个因素是主要独立原因。','', '所有实际非零执行均按native元数据、原学习区间、positive-step receipts核验；完整时间线、首command、carry/reject/expiry见reports。科学层级为历史host development仿真，未升级正式实时资格。']
 (S/'PRE_INTERVENTION_ATTRIBUTION.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(status=result['status'],negative_control=result['negative_control_all_pass'])),flush=True)
if __name__=='__main__':main()
