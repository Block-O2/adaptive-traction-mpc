"""Build transparent scientific summaries after owned experiments stop."""
from pathlib import Path
import sys,os,json,time,hashlib,collections,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
from repetition_paths import GROUP as repeat_group,rep_path,RepeatRoot
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read_rep(n):return read(rep_path(n))
RP=RepeatRoot()
assert (P/'audit/REPETITION_PIPELINE_EXIT.json').exists(),'WAIT_FOR_ALL_OWNED_PHYSICS'
sys.path.insert(0,str(P/'learning'))
import evaluate_early
evaluate_early.main()
events=[json.loads(s) for s in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END']
assert len({e['id'] for e in starts})==len(starts)
assert collections.Counter(e['id'] for e in starts)==collections.Counter(e['id'] for e in ends),'OPEN_STARTS'
rows=[];groups=[]
for file in sorted(P.glob('*_RESULTS.json')):
    ob=json.loads(file.read_text())
    if not isinstance(ob,dict) or 'condition' not in ob or 'rows' not in ob:continue
    group=file.name.removesuffix('_RESULTS.json');groups.append(group)
    bm=read('reports/'+group+'_B_MEASURED.json')
    for row in ob['rows']:
        ident=row['id'];m=read('reports/'+ident+'_MEASURED.json')
        with np.load(P/'motion_series'/(ident+'.npz')) as z:
            q=np.rad2deg(z['true_q_rad']);v=np.rad2deg(z['true_dq_rad_s']);a=np.rad2deg(z['acceleration_rad_s2']);ret=z['phase']=='RETURN'
            overshoot=max(0.,9.5-float(q[ret,1].min()))
            tv=np.sum(abs(np.diff(v,axis=0)),axis=0).tolist();av=np.sum(abs(np.diff(a,axis=0)),axis=0).tolist()
        excursion=(np.array(m['dose']['excursion_deg'])-bm['dose']['excursion_deg']).tolist()
        rows.append(dict(id=ident,parent=group,split=ob['condition']['split'],action=row['candidate']['id'],J_F_N_s=m['J_F_N_s'],gain_vs_B_percent=100*(1-m['J_F_N_s']/bm['J_F_N_s']),qualified=row['all_original_qualifications'],force_cost_rankable=row['all_original_qualifications'],task=row['task'],causal=row['receipt'],absolute_safety=row['absolute_safety'],accepted_and_applied=row['intervention_executed'],failed=row['motion']['failed_requirements'],knee_undershoot_deg=overshoot,excursion_delta_B_deg=excursion,excursion_gate_margin_deg=.5-max(abs(x) for x in excursion),moment_integral_Nm_s=m['moment_integral_Nm_s'],moment_cost_delta_B_percent=100*(m['moment_integral_Nm_s']/bm['moment_integral_Nm_s']-1),force_peak_N=m['force_peak_N'],moment_peak_Nm=m['moment_peak_Nm'],tracking_RMS_deg=m['tracking_RMS_deg'],tracking_RMS_delta_B_deg=(np.array(m['tracking_RMS_deg'])-bm['tracking_RMS_deg']).tolist(),velocity_TV_deg_s=tv,acceleration_variation_deg_s2=av,native_motion=m['motion']['raw']['full'],dose=m['dose'],phase_durations=m['phase_durations'],evidence=row['metrics_path']))
        rows[-1].update(proposed_action=row['candidate'],actual_posture_execution=row['posture_execution'],actual_timing_execution=row['timing_execution'],actual_early_execution=row['early_execution'],receipt_path='reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
        decision=P/'output'/(group+'_'+row['candidate']['id']+'_POLICY_DECISION.json')
        if decision.exists():rows[-1]['actual_policy_decision']=json.loads(decision.read_text())
attempts=[]
for s in starts:
    ident=s['id'];e=next(x for x in ends if x['id']==ident);metric_file=P/'output'/(ident+'_DATA.json')
    metric=json.loads(metric_file.read_text())['metric'] if metric_file.exists() else None
    steps=metric.get('actual_new_native_physics_steps') if metric else e.get('actual_new_native_steps')
    reconciled=read('audit/PARTIAL_COST_RECONCILIATION.json')['rows'] if (P/'audit/PARTIAL_COST_RECONCILIATION.json').exists() else {}
    if steps is None and ident in reconciled:steps=reconciled[ident]['native_steps']
    # Failed import has an explicit zero; no unknown partial is silently zero.
    attempts.append(dict(id=ident,kind=s.get('kind'),start_unix=s['unix'],end_unix=e['unix'],wall_span_s=e['unix']-s['unix'],returncode=e.get('returncode'),joined=e.get('joined'),native_steps=steps,full_task=bool(metric and metric.get('task_valid')),code_manifest_sha256=s.get('code_manifest_sha256'),source='output/'+ident+'_DATA.json' if metric else 'ATTEMPTS.jsonl'))
    if s.get('retrospective_pre_worker_failure'):attempts[-1].update(wall_span_s=None,event_time_semantics=s['event_time_semantics'])
    if ident in reconciled:attempts[-1]['native_cost_evidence']='audit/PARTIAL_COST_RECONCILIATION.json'
account=dict(status='CLOSED' if all(x['native_steps'] is not None for x in attempts) else 'CLOSED_WITH_UNKNOWN_PARTIAL_COST',P1_START=len(starts),P1_END=len(ends),P1_cap=100,P2_episodes=0,P2_native_steps=0,P2_training_updates=0,actual_new_native_steps=sum(x['native_steps'] or 0 for x in attempts),unknown_native_cost_ids=[x['id'] for x in attempts if x['native_steps'] is None],wall_accounting='Parent lifetime includes waits for serial children; do not sum overlapping parent and child wall spans as CPU time.',physics_accounting='Parent includes legal commissioning/prefix and actual resumed-task bootstrap; forks count only steps after fork, no inherited-prefix duplication. Boundary counts separately.',rows=attempts)
put('ATTEMPT_ACCOUNTING.json',account)
put('EXPERIMENT_RESULTS.json',dict(status='COMPLETED',rows=rows,groups=groups,complete_branch_count=len(rows),qualified_branch_count=sum(r['qualified'] for r in rows),all_failures_retained=True,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',independent_Human_count=1,gate_protocol_sha256=sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')))
lr=read('LEARNING_RESULTS.json');ds=read('derived/DATASET_all.json');freeze=read('models/VALUE_FREEZE.json')
assert sha(P/'models/Q_value_ridge.npz')==freeze['model_sha256']
test=[r for r in lr['rows'] if r['split']=='test']
recoveries=[r['parent'] for r in test if r['selection_qualified'] and not r['qualified']['H150']]
qdetails=dict(qualified_recovery_test_parents=recoveries,qualified_force_gain_test_parents=[r['parent'] for r in test if r['improvement_vs_H150_N_s'] is not None and r['improvement_vs_H150_N_s']>.01],state_conditioned_force_ranking_demonstrated=len(set(r['direct_argmin'] for r in test))>1,qualified_recovery_is_not_lower_force_than_qualified_H150=True)
# A simple condition baseline, evaluated retrospectively from training labels.
# It is explicitly NOT a new live policy experiment and does not alter Q.
data=np.load(P/'derived/DATASET_all.npz');tr=np.flatnonzero(data['splits']=='train');te=np.flatnonzero(data['splits']=='test');model=np.load(P/'models/Q_value_ridge.npz');nn=[]
for i in te:
    near=tr[np.argmin(np.linalg.norm((data['X'][tr]-data['X'][i])/model['cost_sd'],axis=1))]
    good=np.flatnonzero(data['qualified'][near]);choice=int(good[np.argmin(data['J'][near,good])]) if len(good) else 0
    nn.append(dict(parent=str(data['groups'][i]),nearest_training_parent=str(data['groups'][near]),choice=str(data['actions'][choice]),qualified=bool(data['qualified'][i,choice]),J_F_N_s=float(data['J'][i,choice]),execution='retrospective evaluation on registered same-parent fixed branches; no actual online rule branch',test_labels_used_to_choose=False))
qdetails['nearest_training_parent_rule']=nn;put('derived/QUALIFICATION_LEARNING_DIAGNOSTICS.json',qdetails)
rep=dict(status='NOT_COMPLETED',run_prefix=repeat_group,FEW_REPETITION_LEARNING_PASS=False,actual_feedback_update=(RP/'models/REPETITION_MEMORY_V1.json').exists(),actual_second_policy_run=(RP/'output/REP_MEMORY_POLICY_DECISION.json').exists(),exposed_prefix_pilot=True,independent_test=False)
if (RP/'audit/REPETITION_FAILURE.json').exists():rep['failure']=read_rep('audit/REPETITION_FAILURE.json')
if repeat_group=='REPR':rep['prior_failed_pilot']=read('audit/REPETITION_FAILURE.json');rep['pre_worker_log_failure']=read('audit/OWNER_LAUNCH_FAILURE_v5.json')
if rep['actual_feedback_update']:rep['memory']=read_rep('models/REPETITION_MEMORY_V1.json')
if rep['actual_second_policy_run']:rep['decision']=read_rep('output/REP_MEMORY_POLICY_DECISION.json')
if (RP/'REP_DONE.json').exists():
    rr={r['action']:r for r in rows if r['parent']==repeat_group}
    assert all(a in rr for a in ['B','H150','MEMORY'])
    memory=rep['memory'];d=rep['decision']
    assert memory['online_updates']==1 and memory['created_unix']<next(e['unix'] for e in starts if e['id']==rep_path('REP_parent'))
    assert memory['truth_consumed'] is False and memory['future_comparator_consumed'] is False
    qualified=rr['MEMORY']['qualified'] and rr['H150']['qualified'];gain=rr['H150']['J_F_N_s']-rr['MEMORY']['J_F_N_s'] if qualified else None
    rep.update(status='TWO_ACTUAL_REPETITIONS_COMPLETED',second_rows=rr,qualified_improvement_vs_H150_N_s=gain,action_changed=d['selected']!='H150',feedback_changed_choice=d['feedback_changed_choice'],FEW_REPETITION_LEARNING_PASS=bool(qualified and gain>.01 and d['selected']!='H150' and d['feedback_changed_choice']),continuity=read_rep('output/REPETITION_CONTINUITY_BEFORE_SECOND.json'))
    boundary=read_rep('output/REP_INTER_BOUNDARY.json');native=read_rep('output/REP_BOUNDARY_NATIVE.json');nr=native['rows']
    assert native['held_control']==native['prior_final_positive_receipt']['command_torque_nm'],'BOUNDARY_RECEIPT_CONTROL_MISMATCH'
    assert len(nr)==round((boundary['end_time_s']-boundary['start_time_s'])/.00025)
    assert all(abs(r['end_s']-r['start_s']-.00025)<1e-9 and r['actual_control']==native['held_control'] for r in nr)
    assert all(abs(a['end_s']-b['start_s'])<1e-9 for a,b in zip(nr,nr[1:]))
    samples=boundary['samples'];t=np.array([s['time_s'] for s in samples]);f=np.linalg.norm([s['force_world_n'] for s in samples],axis=1);m=np.linalg.norm([s['moment_world_nm'] for s in samples],axis=1)
    rep['boundary_audit']=dict(native_steps=len(nr),all_native_intervals_contiguous=True,held_actual_control_unchanged=True,held_control_equals_prior_receipt_torque=True,prior_receipt_index=native['prior_final_positive_receipt']['receipt_index'],receipt_semantics='Original inter-repetition API deliberately carries the last physical command outside the completed TASK receipt interval; not a newly issued TASK command. Every added native step records unchanged actual ctrl and source receipt.',force_left_integral_N_s=float(f[:-1]@np.diff(t)),moment_left_integral_Nm_s=float(m[:-1]@np.diff(t)),reported_cost=boundary['cost'],physics_reset=False)
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained');ids=['REP_FIRST','REP_H150','REP_MEMORY'];vals=[read_rep('reports/'+n+'_MEASURED.json')['J_F_N_s'] for n in ids];ax.bar(['First actual task\nH150','Second task\nfixed H150','Second task\nfeedback value'],vals,color=['#7f7f7f','#0072b2','#e69f00']);ax.set_ylabel('Full-task cuff force integral (N s)');ax.set_title('Continuous-session pilot; second task has matched live-state branches')
    for i,v in enumerate(vals):ax.text(i,v+3,f'{v:.3f}',ha='center')
    ax.set_ylim(0,max(vals)*1.12);fig.savefig(P/'figures/06_actual_repetition.png',dpi=170);plt.close(fig)
elif rep['actual_feedback_update']:
    import textwrap
    first_value=read_rep('reports/REP_FIRST_MEASURED.json')['J_F_N_s']
    fig,axs=plt.subplots(1,2,figsize=(11,5),gridspec_kw={'width_ratios':[1,2]},layout='constrained')
    axs[0].bar(['First complete task\nH150'],[first_value],color='#0072b2')
    axs[0].text(0,first_value+15,f'{first_value:.3f}',ha='center');axs[0].set_ylim(0,first_value*1.15);axs[0].set_ylabel('Full-task force integral (N s)')
    axs[1].axis('off')
    status='Actual measured feedback update: YES\nBounded value correction: '+f"{rep['memory']['online_kernel_weight_N_s']:.6f} N s"+'\nSecond policy decision recorded: '+str(rep['actual_second_policy_run'])+'\nTwo complete repetitions: NOT DEMONSTRATED\n\nFailure: '+textwrap.fill(rep.get('failure',{}).get('error','See retained pipeline error'),58)+'\n\nNo partial cost is plotted as a completed-task reward.'
    axs[1].text(.02,.9,status,va='top',fontsize=11,linespacing=1.6)
    fig.suptitle('Continuous-session feedback pilot: failed stages remain visible')
    fig.savefig(P/'figures/06_actual_repetition.png',dpi=170);plt.close(fig)
put('derived/REPETITION_EVALUATION.json',rep)
lr['FEW_REPETITION_LEARNING_PASS']=rep['FEW_REPETITION_LEARNING_PASS'];lr['few_repetition_evidence']='derived/REPETITION_EVALUATION.json';lr['qualification_diagnostics']='derived/QUALIFICATION_LEARNING_DIAGNOSTICS.json'
early=read('EARLY_VALUE_EVALUATION.json');lr.update(EARLY_VALUE_TRAINED=True,EARLY_CONDITIONAL_BENEFIT_PASS=early['EARLY_CONDITIONAL_BENEFIT_PASS'],earlier_value_evidence='EARLY_VALUE_EVALUATION.json',earlier_value_does_not_use_previous_repetition_feedback=True)
put('LEARNING_RESULTS_FINAL.json',lr)
# Preserve the original frozen-policy evaluation; final report points to both.
put('audit/SCIENCE_SUMMARY_DONE.json',dict(unix=time.time(),groups=groups,attempts=len(attempts),primary_result_preserved=True,final_result='LEARNING_RESULTS_FINAL.json'))
print('SCIENCE_SUMMARY_DONE',len(rows),'BRANCHES',len(attempts),'STARTS',flush=True)
