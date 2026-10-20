from pathlib import Path
import os,sys,json,time,ast,shutil,copy,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_autonomous_multitrack_v1';H=P.parent/'m2_18d_early_return_motion_repair_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(P/'tmp/mpl'));sys.dont_write_bytecode=True
assert (P/'audit/PATH_REBASE.json').exists();assert not (P/'EXECUTION_CODE_MANIFEST.json').exists()
for n in ['terminal_planner.py','terminal_control.py','prepare.py']:shutil.copy2(R/'control'/n,P/'control'/n)
plan=json.loads((P/'RUN_PLAN.json').read_text());plan['dispatch_cutoff_unix']=plan['no_new_physics_after_unix'];(P/'RUN_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import study_common as sc,matched_harness as mh,analyze_matched as am
from round_planner import RoundPlanner,FixedDuration
from terminal_control import TerminalIntent
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import _prepare_single_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_rolling_composite
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from dataclasses import replace
def put(n,x):mh.put(P/n,sc.clean(x))
# Existing exact historical reference fixture, with explicit source redirect.
src=(P.parent/'m2_18d_t_second_round_coordination_v1/control/register.py').read_text();tree=ast.parse(src)
fixture_src=ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='fixture')).replace('source/results/V1_T','source/results/Adev_ER')
exec(fixture_src)
fx=fixture(13);prior=fixture(12);rows=[]
for factor in [1.5,.75]:
 planner=fx['planner'];native=planner.scheduler;old=fx['schedule'];duration=float(np.ceil(old.duration_s*factor/.005-1e-10)*.005)
 planner.scheduler=FixedDuration(native,duration);planner.round_forced_velocity=np.array(fx['archived']['target_dq_rad_s'])
 try:r=planner._evaluate(**fx['evaluate_args'])
 finally:planner.scheduler=native;planner.round_forced_velocity=None
 row=dict(id='H'+str(round(factor*100)).zfill(3),factor=factor,feasible=bool(r.feasible),reason=r.rejection_reason,original_duration_s=old.duration_s,new_duration_s=duration)
 if r.feasible:
  prepared=_prepare_single_decision(replace(fx['decision'],executed=r),planner,fx['belief']);new=prepared.executed.schedule
  composite=RollingSuffixCompositeSchedule(prefix=prior['schedule'].safe_escape.bridge,prefix_start_s=0.,suffix=new,request_id=fx['context']['request_id']);d=fx['decision_record'];tr=np.load(A/'source/results/Adev_ER/trace.npz');idx=int(np.argmin(abs(tr['time_s']-d['activation_timestamp_s'])));cur=composite.sample(0.)
  future=dict(spec=planner.spec,estimated_state=tr['estimated_human_state_rad_rad_s'][idx],estimated_acceleration=tr['actual_human_acceleration_rad_s2'][idx],reference_acceleration=cur.ddq_rad_s2,acceleration_valid=bool(tr['actual_human_acceleration_valid'][idx]),revalidation_capture_ns=105000000,now_ns=105000000,original_capture_ns=100000000,request_plan_version=new.version,original_sample_s=d['request_measurement_timestamp_s'],revalidation_sample_s=d['activation_timestamp_s'],age_policy='simulation')
  val=validate_rolling_composite(composite=composite,belief=fx['belief'],request_sequence=fx['belief'].sequence,clearance=native.clearance_evaluator,spec=planner.spec,phase=fx['evaluate_args']['phase'],request_phase=fx['evaluate_args']['phase'],remaining_s=fx['evaluate_args']['phase_remaining_s']-.005,current_reference_state=np.r_[cur.q_rad,cur.dq_rad_s],current_reference_acceleration=cur.ddq_rad_s2,future_handoff=future,now_physics_s=d['activation_timestamp_s'])
  ss=[new.sample(t) for t in np.linspace(0,duration,401)]
  row.update(status='PASS' if val['feasible'] else 'REJECTED',current_admission=val,certificate=new.continuous_clearance_certificate,knee_q_deviation_max_rad=max(abs(s.q_rad[1]-new.candidate.q_waypoint_rad[1]) for s in ss),knee_velocity_max_rad_s=max(abs(s.dq_rad_s[1]) for s in ss),coefficient_sha256=hashlib.sha256(new.coefficients.tobytes()).hexdigest())
 else:row['status']='REJECTED'
 rows.append(row)
put('audit/TIMING_PRECHECKS.json',dict(rows=rows,no_physics=True,live_checks_mandatory=True))
baseplan=json.loads((A/'Adev_PLAN.json').read_text());arms=copy.deepcopy(baseplan['arms'][:4]);parent=arms[-1]
for arm in arms:arm.pop('approach',None)
for row in rows:
 if row['status']=='PASS':
  c=copy.deepcopy(parent);c.update(id=row['id'],timing=[dict(phase='RETURN',slot=5,duration_factor=row['factor'])]);arms.append(c)
control_configs={
 'KD120':dict(mode='DAMPING',kd_fraction=.20),
 'PD':dict(mode='PD',kp_aux=14.,kd_aux=4.4),
 'FF':dict(mode='FF',ff_fraction=.5),
 'PDFF':dict(mode='PDFF',kp_aux=14.,kd_aux=4.4,ff_fraction=.5)}
for c in control_configs.values():c.update(acceleration_cap_rad_s2=.2,rate_cap_rad_s3=1.)
tr=np.load(A/'source/results/Adev_ER/trace.npz');ix=tr['stage']=='TASK';tt=tr['time_s'][ix];xx=tr['estimated_human_state_rad_rad_s'][ix];qr=tr['reference_q_rad'][ix];vr=tr['reference_dq_rad_s'][ix];ar=tr['reference_ddq_rad_s2'][ix];ph=tr['task_phase'][ix];offline=[]
for name,config in control_configs.items():
 intent=TerminalIntent(config)
 for i,t in enumerate(tt):intent.evaluate(state=xx[i],qref=qr[i],vref=vr[i],aref=ar[i],goal=np.radians([5.5,9.5]),phase=ph[i],sample_s=t,now_s=t)
 delta=np.array([r['delta_rad_s2'] for r in intent.rows]);assert np.max(abs(delta))<=.2+1e-10;assert np.max(abs(np.diff(delta,axis=0)))<=.005+1e-8
 assert not np.any(delta[ph!='RETURN']);stale=intent.evaluate(state=xx[-1],qref=qr[-1],vref=vr[-1],aref=ar[-1],goal=np.radians([5.5,9.5]),phase='RETURN',sample_s=tt[-1]+.005,now_s=tt[-1]+.2);assert stale['stale'] and not np.any(stale['delta_rad_s2'])
 c=copy.deepcopy(parent);c.update(id=name,controller=config);arms.append(c)
 offline.append(dict(id=name,status='PASS_INTERFACE_ONLY',max_abs_delta_rad_s2=np.max(abs(delta),axis=0),max_rate_rad_s3=np.max(abs(np.diff(delta,axis=0)/.005),axis=0),active_samples=int(np.any(delta!=0,axis=1).sum()),first_active_task_s=float(tt[np.flatnonzero(np.any(delta!=0,axis=1))[0]]-tt[0]),stale_returns_zero=True,independent_truth_input=False))
put('audit/CONTROLLER_OFFLINE_CHECKS.json',dict(rows=offline,no_physics=True,proof_scope='Causal interface, bounds, rate, phase and stale handling; closed-loop stability and safety require actual execution',local_ideal_PD_poles=dict(original_knee=np.roots([1,22,140]).astype(complex).tolist().__str__(),KD120_knee=np.roots([1,26.4,140]).astype(complex).tolist().__str__()),original_physical_filter_required=True))
# Each controller variation retains reference certificates and obtains a fresh
# current-output feasibility check after the entire new action transform.
control_contract=dict(version='terminal_acceleration_intent_v1',causal_inputs=['current estimated q/dq','current issued q/dq/ddq','registered/internal phase target','current model mass matrix','source time','task phase','own previous correction'],new_action='u_original + M(q_est)*bounded_delta_accel BEFORE original transfer/projection/clearance/filter/supervisor',limits=dict(acceleration_rad_s2=.2,rate_rad_s3=1.,period_s=.005,stale_max_s=.1),certificates=dict(reference='original newly generated geometry/mechanics/escape/current-state certificate still describes the same reference',control_output='old certificate is NOT a certificate for the changed controller; every augmented action is freshly passed through original full executable filter, allocator, supervisor and actual-write checks; full native audit required',stability='ideal local PD poles only; no global physical stability claim'),receipt='new version/candidate hash/causal source/delta/generalized correction bound to actual positive-step receipt',no_new_fast_entry=True,original_B_controller_unmodified=True)
put('CONTROL_EXTENSION_CONTRACT.json',control_contract)
s=(A/'control/campaign.py').read_text()
s=s.replace('from terminal_approach_planner import TerminalApproachPlanner','from terminal_planner import TerminalTimingPlanner\nfrom terminal_control import TerminalIntent,bind_boundary')
s=s.replace('self.current=None;self.references={};self.sample_rows=[]','self.current=None;self.references={};self.sample_rows=[];self.terminal_intent=None')
s=s.replace('planner.terminal_approach_intent=None','planner.terminal_timing_intent=None')
s=s.replace("TerminalApproachPlanner if self.current.get('approach')", "TerminalTimingPlanner if self.current.get('timing')")
s=s.replace("self.current.get('approach',[])","self.current.get('timing',[])").replace('planner.terminal_approach_intent=change','planner.terminal_timing_intent=change')
s=s.replace('  ib.Interface.boundary(self,b)','  ib.Interface.boundary(self,b)\n  if self.terminal_intent is not None:bind_boundary(b,self.terminal_intent,self.current[\'candidate_hash\'])')
s=s.replace("  put('output/'+metric['name']+'_REFERENCE_OBJECTS.json'", "  if self.terminal_intent is not None:put('output/'+metric['name']+'_CONTROL_INTENT.json',dict(candidate=self.current,rows=self.terminal_intent.rows,contract='CONTROL_EXTENSION_CONTRACT.json'))\n  put('output/'+metric['name']+'_REFERENCE_OBJECTS.json'")
start=s.index("    if c.get('conditional_repeat'):");end=s.index("    if self.fork(b,c['id']",start);s=s[:start]+s[end:]
s=s.replace('     self.current=c;self.references={};self.sample_rows=[]','     self.current=c;self.references={};self.sample_rows=[];self.terminal_intent=TerminalIntent(c[\'controller\']) if c.get(\'controller\') else None')
s=s.replace("'terminal_approach_velocity'","'terminal_hip_timing'").replace("c.get('approach',[])","c.get('timing',[])").replace("row['approach_execution']","row['timing_execution']")
start=s.index("    if c.get('approach'):");end=s.index("   put(GROUP+'_PAIR_GATE.json'",start);s=s[:start]+s[end:]
s=s.replace("'START_CAP_60'","'START_CAP_80'")
s=s.replace("P/'NEW_FROZEN_SELECTION.json'","P/'NEW_FROZEN_SELECTION.json'")
(P/'control/campaign.py').write_text(s)
hashes={n:sc.sha(P/'control'/n) for n in ['campaign.py','terminal_planner.py','terminal_control.py','round_planner.py','early_return_planner.py']}
for arm in arms:arm['candidate_hash']=sc.digest(dict(parameters=arm,source_hashes=hashes,control_contract_sha=sc.sha(P/'CONTROL_EXTENSION_CONTRACT.json')))
cond=copy.deepcopy(baseplan['condition']);cond.update(name='Dev',role='W1 exposed development; original full live parent prefix')
put('Dev_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,reproduce_W1=True,arms=arms))
selection=dict(eligibility='Full 19.030s original task/safety/motion/receipt/native ownership; knee excursion difference<=0.5deg; actual intervention applied; J_F saving>=80% of ER saving vs matched B and >=1%; overshoot must improve >=0.05deg vs ER',priority='Prefer reference-only H if eligible; then existing DAMPING, FF, PD, PDFF. No tuning on held-out. No sole numerical gate-boundary search.',stops='Any task/safety/causal failure stops group for review; motion fail preserved and does not prevent independent next track; no more than one bounded revision per direction; all starts<=80, last60min no physics.',next='Freeze selected candidate, deterministic full repeat, then unused W2 with matched B/ER/new candidate. W2 failure never retuned as blind.',predictions='Causal rolling offline evaluation does not certify closed-loop prediction; only reuse sufficiently accurate predictor with validated uncertainty; timing contrast may test mechanism independently.')
put('CANDIDATE_SELECTION_RULE.json',selection)
put('CANDIDATE_PLAN.json',dict(frozen_unix=time.time(),hypotheses=dict(H='Hip-only terminal time change can causally affect knee stopping, tested with constant knee reference; may be too late to repair pre-stop error',KD120='20% bounded increase of existing knee velocity feedback near RETURN terminal improves damping without extra module',PD='braking-only bounded final-goal knee PD may have independent value',FF='half of known reference ddq, bounded, complements existing inverse dynamics which has no direct reference ddq term',PDFF='same PD and FF parameters, shared documented total bound; test additivity and clipping interaction'),source_hashes=hashes,arms=arms,selection=selection))
(P/'INTERVENTION_PROTOCOL.md').write_text('# 物理前研究协议\n\nW1为已暴露开发条件；匹配B/T/D/ER保持。H只改变RETURN5髋终末时长，膝参考恒定。KD120只增加现有膝速度误差反馈20%；PD使用Kp=14、Kd=4.4的终点制动意图；FF使用当前合法参考加速度的0.5倍。PDFF复用同参数，共同受±0.2rad/s²及1rad/s³限制。全部由位置、速度和停止距离触发，不使用绝对秒数或Human truth。新修正位于原逆动力学之后、原补偿/加速度约束/allocator/输出安全过滤之前；不新增时钟入口。旧证书只保留其原参考范围，新控制输出每周期重新过滤并绑定receipt。\n\n每次运行完整task19.030s，原motion含0.5°excursion门。单次/partial不得排名。原18D/T/D/ER身份、plant、Human、gravity、cuff、contact、torque、HOLD、bridge40ms、lifecycle100ms、安全门全部冻结。\n\n'+json.dumps(selection,indent=2,ensure_ascii=False)+'\n')
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','control/round_planner.py','control/early_return_planner.py','code/terminal_repair.py']:assert sc.sha(P/n)==sc.sha(A/n)
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
files={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','CANDIDATE_SELECTION_RULE.json','INTERVENTION_PROTOCOL.md','CANDIDATE_PLAN.json','CONTROL_EXTENSION_CONTRACT.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json','RUN_PLAN.json']:files[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),parent_manifest_sha256=sc.sha(A/'EXECUTION_CODE_MANIFEST.json'),source_changes='path rebasing only in original closure; new isolated timing/controller wrappers and experiment harness'))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',AST=True,imports_isolated=True,no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),original_B_safety_plant_source_unchanged=True,timing_prechecks=rows,control_interface_prechecks=offline,live_checks_required=True))
for f in [P/'CANDIDATE_PLAN.json',P/'Dev_PLAN.json',P/'INTERVENTION_PROTOCOL.md',P/'CANDIDATE_SELECTION_RULE.json',P/'CONTROL_EXTENSION_CONTRACT.json',P/'PREPHYSICAL_CHECKS.json']:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(sc.clean(dict(status='PASS',arms=[c['id'] for c in arms],timing=rows,controller=offline))),flush=True)
