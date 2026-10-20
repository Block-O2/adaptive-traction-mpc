from pathlib import Path
import os,sys,json,time,hashlib,shutil,ast
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
REVIEW=Path(__file__).resolve().parents[1];A=P.parent/'m2_18d_terminal_expanded_prefix_validation_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True
for n in ['round_planner.py','campaign.py','diagnose_prepare.py','register.py','owner.py']:
 shutil.copy2(REVIEW/'control'/n,P/'control'/n)
sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
from scipy.optimize import minimize
import study_common as sc,matched_harness as mh,analyze_matched as am
from round_planner import RoundPlanner,FixedDuration
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import _prepare_single_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import hermite,adapt_decision
def put(n,x):mh.put(P/n,sc.clean(x))
def fixture(index):
 su=json.loads((A/'source/results/V1_T/summary.json').read_text());lr=next(r for r in su['learning_records'] if r['decision_index']==index);d=su['decisions'][index];h=lr['adaptive_state'];sch=lr['selected_plan']['schedule']
 geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()})
 keys=['beta','state_residual_weights_nm','sequence','dynamics_sample_count','accepted_beta_update_count','residual_update_count','geometry_source','dynamics_source','residual_source','residual_limit_nm']
 belief=AdaptiveHumanBeliefV22(geometry=geo,rom_human=sc.rt.high_rom_deployable_prior(),**{k:np.asarray(h[k]) if k in ['beta','state_residual_weights_nm'] else h[k] for k in keys if k in h})
 spec=load_goal_task_spec(P/'source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/stage5_goal_task_120_v1.json')
 clr=CombinedRigidTableClearanceV1(sc.rt.SessionClearanceContract(geo),RigidTableReferenceEnvelopeV1(geo),use_monotonic_certificate=True)
 scheduler=QuinticHumanWaypointSchedulerV1(spec,belief.human_model(),reference_period_s=.005,clearance_evaluator=clr,preserve_task_endpoint_clearance_floor=True,require_continuous_nonpenetrating_path=True,use_duration_lower_bound=True,reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
 planner=RoundPlanner(spec,scheduler,HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True));planner.pass_through_waypoints=True;planner.robust_terminal_center=True;planner.robust_hold_reference=True;planner.safe_fallback_enabled=True;planner.causal_tracking_offset_clearance=True;planner.residual_spec={};planner.free_parameters=np.array(json.loads((P/'FROZEN_18D.json').read_text())['free_parameters'])
 snapshot=lr['selected_plan']['execution_screen']['causal_tracking_offset_clearance']['reference_snapshot'];planner.tracking_reference_snapshot={k:np.asarray(v) if isinstance(v,list) else v for k,v in snapshot.items()}
 ph=TaskPhase(d['phase']);planner.internal_reference_target_rad=np.array(spec.outbound_goal_target_rad if ph is TaskPhase.OUTBOUND else spec.start_return_target_rad)
 planner.round_forced_velocity=np.array(sch['target_dq_rad_s']);planner.scheduler=FixedDuration(scheduler,sch['duration_s'])
 args=dict(label='archived_exact_selected_target',state=np.array(d['deployable_state_rad_rad_s']),reference_state=np.array(d['reference_state_rad_rad_s']),phase=ph,phase_elapsed_s=d['phase_elapsed_s'],phase_remaining_s=d['phase_remaining_s'],action=np.array(sch['target_q_rad'])-np.array(d['deployable_state_rad_rad_s'])[:2],execution_feasibility_checker=lambda c,s:AdaptiveMechanicsScreenV22().evaluate(belief,c,s),value_state_or_belief=belief,candidate_value_evaluator=None)
 evaluated=planner._evaluate(**args);assert evaluated.feasible,evaluated.rejection_reason
 from types import SimpleNamespace
 # prepare_single_decision uses dataclasses.replace; obtain the original decision schema.
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22
 # Restore scheduler for original decide to populate complete decision fields, then replace selected schedule.
 planner.scheduler=scheduler;planner.round_forced_velocity=None
 da=dict(belief=belief,current_deployable_state=args['state'],current_reference_state=args['reference_state'],phase=ph,phase_elapsed_s=d['phase_elapsed_s'],phase_remaining_s=d['phase_remaining_s'],value_evaluator=None)
 base=AdaptiveHumanWaypointHWMPCV22(planner).decide(**da)
 from dataclasses import replace
 decision=replace(base,executed=evaluated)
 decision=_prepare_single_decision(decision,planner,belief)
 old=decision.executed.schedule
 assert max(abs(old.duration_s-sch['duration_s']),np.max(abs(old.sample(0).q_rad-np.array(sch['start_q_rad']))),np.max(abs(old.sample(old.duration_s).q_rad-np.array(sch['target_q_rad']))))<1e-10
 context=dict(request_id=d['timing_request_id'],source_sample_time_s=float(d['request_measurement_timestamp_s']),sensor_capture_ns=123456789,phase=d['phase'],phase_remaining_s=d['phase_remaining_s'],perturbation_deg=[0.,0.])
 return dict(decision=decision,planner=planner,belief=belief,context=context,schedule=old,archived=sch,decision_record=d,evaluate_args=args)
def poly(c,u,T,d=0):return np.array([np.polynomial.polynomial.polyval(np.atleast_1d(u),np.polynomial.polynomial.polyder(row,d)) for row in c]).T/T**d
design=[]
for name,index,phase,slot in [('S_O',1,'OUTBOUND',1),('S_R',13,'RETURN',5)]:
 fx=fixture(index);s=fx['schedule'];T=s.duration_s;co=s.coefficients;fs=np.array([0,.25,.5,.75,1]);states=[[poly(co,u,T,k)[0] for k in range(3)] for u in fs]
 def samples(x,d):
  ss=[[v.copy() for v in a] for a in states]
  for i,de in enumerate(np.radians(np.asarray(x).reshape(3,2))):ss[i+1][0]+=de
  return np.vstack([poly(hermite(*ss[i],*ss[i+1],T*(fs[i+1]-fs[i])),np.linspace(0,1,161),T*(fs[i+1]-fs[i]),d) for i in range(4)])
 def objective(x):
  v=samples(x,1);a=samples(x,2)
  return float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum()) if name=='S_O' else float(np.max(abs(a[:,0]))+.02*np.linalg.norm(np.diff(a,axis=0),axis=1).sum())
 bounds=[(-.05,.05)]*6 if name=='S_O' else [(-.05,.05),(0.,0.)]*3
 opt=minimize(objective,np.zeros(6),method='SLSQP',bounds=bounds,options={'maxiter':150,'ftol':1e-11});assert opt.success,opt.message
 change=dict(phase=phase,slot=slot,spec=dict(fractions=fs[1:-1].tolist(),deltas_deg=opt.x.reshape(3,2).tolist()),purpose='reduce early outbound actual velocity variation and following knee response' if name=='S_O' else 'flatten return terminal hip acceleration without changing outer duration or state',expected_force_window=[1.57,3.2] if name=='S_O' else [16.54,17.2])
 row=dict(id=name,base='T',changes=[change],posture=[],objective_before=objective(np.zeros(6)),objective_after=objective(opt.x),optimizer=dict(method='offline reference-only SLSQP; no physical force objective',nfev=opt.nfev),success='original full gates plus full motion/force preregistered selection criteria',failure='certificate reject, gates fail, absent actual motion response, or full/downstream burden offsets local improvement')
 try:
  new=adapt_decision(fx['decision'],fx['planner'],fx['belief'],{**fx['context'],'study_spec':change['spec']}).executed.schedule
  row['offline_certificate']=dict(status='PASS',reference_id=new.sealed_digest,certificate_id=new.sealed_certificate_id)
 except ValueError as e:row['offline_certificate']=dict(status='REJECTED',reason=str(e))
 design.append(row)
# Mechanism-directed posture perturbation and its signed counter-control, at a single RETURN intermediate target.
posture=[];fx=fixture(11)
for name,delta in [('P_more',[.3,-.3]),('P_counter',[-.3,.3])]:
 args=fx['evaluate_args'].copy();args['action']=args['action']+np.radians(delta)
 planner=fx['planner'];scheduler=planner.scheduler;planner.scheduler=FixedDuration(scheduler,fx['schedule'].duration_s);planner.round_forced_velocity=np.array(fx['archived']['target_dq_rad_s'])
 try:r=planner._evaluate(**args)
 finally:planner.scheduler=scheduler;planner.round_forced_velocity=None
 posture.append(dict(id=name,base='T',posture=[dict(phase='RETURN',slot=3,delta_deg=delta)],changes=[],purpose='test stronger hip-leading/knee-leading spatial separation aligned with the prior low-force RETURN posture; opposite control identifies direction',expected_force_window=[13.9,16.6],expected_motion='alter actual intermediate posture while preserving full variation; not assumed smoother',offline_certificate=dict(status='PASS' if r.feasible else 'REJECTED',reason=r.rejection_reason),unchanged='18D coefficients/plateau; changed segment duration and pass velocity; phase/task endpoints; T1.5; all safety and execution contracts'))
zero=dict(id='T_zero',base='T',zero=True,posture=[],changes=[{**r['changes'][0],'spec':{**r['changes'][0]['spec'],'deltas_deg':np.zeros((3,2)).tolist()}} for r in design])
arms=[dict(id=a,base=a,posture=[],changes=[]) for a in ['B','E','T']]+[zero]+[c for c in posture+design if c['offline_certificate']['status']=='PASS']
config=dict(frozen_unix=time.time(),condition=dict(name='dev',seed=2026101901,prefix={'OUTBOUND':[[-.045,-.075,-.055]]}),fork_after_prefix=1,archive_condition='V1',arms=arms)
put('dev_PLAN.json',config);put('CANDIDATE_PLAN.json',dict(frozen_unix=time.time(),all_candidates=posture+design,zero=zero,development=config))
selection=dict(full_gates='complete TASK, absolute safety, original motion/fairness vs matched B, receipt/current admission/native ownership; no partial force ranking',force_gain_signal_N_s=.5,motion_noninferiority_relative=.002,motion_signal_full_relative=.005,force_neutrality_N_s=.2,criteria='Qualified candidate: either delta J_F <= -0.5 N s and combined full TV_v/TV_a/jerk RMS each <=1.002*T; OR at least one full TV_v/TV_a/jerk RMS improves >=0.5%, other two <=1.002*T and J_F<=T+0.2 N s. Peak-only improvements remain diagnostic. Motion qualification is always original gates vs B, never these scientific selection criteria.',tie_break='primary by largest fractional full velocity-TV improvement among eligible; then full acceleration-TV, jerk RMS, J_F; no validation reselection',conditional='Combine posture and shape only if each independently eligible; at most one half-size refinement per informative direction; signed control no sweep. Stop after 3 uninformative candidates per direction. Parameters/code frozen before validation.',validation='Reserve >=10 START. Selected candidate deterministically repeat from same parent condition; then at least two new registered legal prefixes, paired B/E/T/primary plus primary repeat if budget allows. No primary reselection from validation.')
put('SELECTION_RULE.json',selection)
(P/'BASELINE_CONTRACT.md').write_text('''# Frozen baseline and scope\n\nFormal B J_F=1438.613498467 N s; historical development 18D=1400.697221153 N s (2.635613%). Those scalar values are historical, not the V1 development pairing. All 18 coefficients and RETURN plateau -0.020/-0.022 remain byte-identical in FROZEN_18D.json. T is applied only after the original final OUTBOUND goal selection: ceil((old suffix duration*1.5)/.005-1e-10)*.005. T does not mean a single fixed suffix duration. Four historical legal prefix conditions N2/U1/V1/V2 pass original task/safety/motion/causal gates, same Human only. N2 gain2.410231%, U1 2.417010%, V1 2.405167%, V2 2.422045%; the approximately2.24–2.42% description is conservative, the four named T rows span2.405–2.422%.\n\nThe existing MATCHED non-HOLD phase minimum9s and HOLD minimum1s remain; actual OUTBOUND/HOLD/RETURN9.005/1.020/9.005s, TASK19.030s. Extended suffix uses endpoint TRACK waiting, not extra/shortened task time. Bridge40ms, lifecycle100ms, source age, current-state admission, continuous geometry/mechanics, truth firewall, causal receipts, carry/braking/fallback unchanged. B/plant/Human/robot/contact/gravity/actuator/ROM/torque/endpoint/task limits unchanged. Original motion protocol byte-identical.\n\nThe additive middle-posture intervention changes one internal target only after frozen T/18D choice, keeping that selected segment duration and pass velocity. All task/phase endpoints stay fixed; subsequent live decisions and T original-duration computation may respond causally. Shape changes only certified internal q knots within original0.05deg path bound, retaining outer q/dq/ddq/duration. Neither changes18D coefficients.\n\nHistorical 18D motion failures remain: retrospective0/4, baseline qualification N2 acceleration failure; T repairs the named finite conditions only. No cross-patient, clinical, hardware, Native LEVEL2 or host LEVEL3 qualification is inferred.\n''')
(P/'INTERVENTION_PROTOCOL.md').write_text('# Preregistered second-round protocol\n\n'+json.dumps(selection,indent=2,ensure_ascii=False)+'\n\nAll candidates, purpose, parameters, expected motion/force windows and mathematical screening are in CANDIDATE_PLAN.json. Develop on already observed V1; hold out new legal prefixes until selection/code freeze. Full parent is actual commissioning+prefix, then exact live address-space fork, never Human state assignment or replay. All physics serial. Cap40 START including every parent/fork/failure/repeat; development cap30 retains10. Cutoff45minutes before6h hard limit, with additional15minute completion reserve. Safety/task/causal failure stops physics. Original motion failure excludes ranking and is retained.\n')
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
assert sc.sha(P/'FROZEN_18D.json')==sc.sha(A/'FROZEN_18D.json')
assert sc.sha(P/'code/terminal_repair.py')==sc.sha(A/'code/terminal_repair.py')
assert sc.sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sc.sha(A/'MOTION_ACCEPTANCE_PROTOCOL.json')
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
files={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','BASELINE_CONTRACT.md','INTERVENTION_PROTOCOL.md','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:files[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),base_manifest_sha256=sc.sha(A/'EXECUTION_CODE_MANIFEST.json'),original_T_byte_identity=True,source_changes='exact previously qualified type-specific smoothing extension plus isolated round_planner; no B kernel changes'))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),imports_isolated=True,original_parameters_T_motion_byte_identical=True,AST=True,mathematical_rows=posture+design,live_certification_and_admission_still_required=True))
print(json.dumps(dict(status='PASS',arms=[c['id'] for c in arms],design=design,posture=posture)),flush=True)
