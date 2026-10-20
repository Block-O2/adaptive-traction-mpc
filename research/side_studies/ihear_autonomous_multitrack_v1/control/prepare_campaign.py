from pathlib import Path
import os,sys,json,time,ast,shutil,hashlib,copy
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'m2_18d_early_return_motion_repair_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(P/'tmp/mpl'));sys.dont_write_bytecode=True
assert (P/'audit/PATH_REBASE.json').exists(),'BOOTSTRAP_NOT_COMPLETE'
assert not (P/'EXECUTION_CODE_MANIFEST.json').exists(),'FROZEN_ALREADY'
for n in ['terminal_approach_planner.py','prepare_campaign.py']:shutil.copy2(R/'control'/n,P/'control'/n)
s=(A/'control/campaign.py').read_text()
s=s.replace('from early_return_planner import EarlyReturnPlanner','from early_return_planner import EarlyReturnPlanner\nfrom terminal_approach_planner import TerminalApproachPlanner')
s=s.replace("'START_CAP_24'","'START_CAP_60'")
s=s.replace('planner.early_return_intent=None','planner.early_return_intent=None;planner.terminal_approach_intent=None')
s=s.replace("elif self.current['base']=='T':planner.__class__=EarlyReturnPlanner if self.current.get('early') else RoundPlanner","elif self.current['base']=='T':planner.__class__=TerminalApproachPlanner if self.current.get('approach') else (EarlyReturnPlanner if self.current.get('early') else RoundPlanner)")
s=s.replace("if self.child is not None:\n   for change in self.current.get('early',[]):","if self.child is not None:\n   for change in self.current.get('approach',[]):\n    if phase==change['phase'] and slot==change['slot']:planner.terminal_approach_intent=change\n   for change in self.current.get('early',[]):",1)
s=s.replace("    if self.fork(b,c['id'],np.zeros((2,5,3))):", "    if c.get('conditional_second'):\n     first=next(r for r in self.results if r['candidate']['id']=='AV090');parent=next(r for r in self.results if r['candidate']['id']=='ER')\n     fm=json.loads((P/first['metrics_path']).read_text());pm=json.loads((P/parent['metrics_path']).read_text())\n     if first['all_original_qualifications'] or not fm['dose']['excursion_deg'][1]<pm['dose']['excursion_deg'][1]-1e-6:\n      put(GROUP+'_SECOND_NOT_STARTED.json',dict(reason='First candidate qualified or did not improve knee excursion; stop blind velocity reduction',new_START=False));continue\n    if self.fork(b,c['id'],np.zeros((2,5,3))):")
s=s.replace("    row['all_original_qualifications']=", "    approach=[lr['selected_plan']['execution_screen']['terminal_approach_velocity'] for lr in su['learning_records'] if 'terminal_approach_velocity' in lr['selected_plan']['execution_screen']]\n    row['approach_execution']=approach;row['intervention_executed']=row['intervention_executed'] and len(approach)==len(c.get('approach',[])) and all(x['status']=='ACCEPTED' for x in approach)\n    row['all_original_qualifications']=")
s=s.replace("    if c.get('zero'):","    if CONFIG.get('reproduce_W1') and c['id']=='ER':\n     gate=bc.compare_raw(P/'source/results'/ident,P.parent/'m2_18d_early_return_motion_repair_v1/source/results/repair_ER110_R4_120');put('audit/'+ident+'_HISTORICAL_GATE.json',gate);assert gate['status']=='PASS','ER_REPRODUCTION_FAIL'\n    if c.get('zero'):")
start=s.index("    if c.get('early'):\n     dm=");end=s.index("   put(GROUP+'_PAIR_GATE.json'",start)
s=s[:start]+"""    if c.get('approach'):
     dm=json.loads((P/'reports'/(GROUP+'_ER_MEASURED.json')).read_text());df=dm['motion']['raw']['full'];mf=m['motion']['raw']['full'];new_failures=sorted(set(comp['failed_requirements'])-set(next(x for x in self.results if x['candidate']['id']=='ER')['motion']['failed_requirements']))
     peak_worse=any(np.any(np.asarray(mf[key][stat])>1.10*np.asarray(df[key][stat])+1e-8) for key,stat in [('acceleration_deg_s2','max_abs'),('jerk_deg_s3','rms')])
     tracking_worse=bool(np.any(np.asarray(m['tracking_RMS_deg'])>np.asarray(dm['tracking_RMS_deg'])+.5))
     if new_failures or peak_worse or tracking_worse:
      put(GROUP+'_MECHANISM_REVIEW_REQUIRED.json',dict(id=ident,new_failures=new_failures,peak_worse=bool(peak_worse),tracking_worse=tracking_worse,next_candidates_not_started=True));break
"""+s[end:]
s=s.replace("P/'REPAIR_FROZEN_SELECTION.json'","P/'NEW_FROZEN_SELECTION.json'")
(P/'control/campaign.py').write_text(s)
sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import study_common as sc,matched_harness as mh,analyze_matched as am
from round_planner import RoundPlanner,FixedDuration
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
src=(P.parent/'m2_18d_t_second_round_coordination_v1/control/register.py').read_text();tree=ast.parse(src)
fixture_src=ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='fixture')).replace('source/results/V1_T','source/results/repair_ER110_R4_120')
exec(fixture_src)
fx=fixture(11);prior=fixture(10);rows=[]
for factor in [.9,.8]:
 planner=fx['planner'];native=planner.scheduler;old=fx['schedule'];velocity=np.array(fx['archived']['target_dq_rad_s']);velocity[1]*=factor
 planner.scheduler=FixedDuration(native,old.duration_s);planner.round_forced_velocity=velocity
 try:r=planner._evaluate(**fx['evaluate_args'])
 finally:planner.scheduler=native;planner.round_forced_velocity=None
 row=dict(id='AV'+str(round(factor*100)).zfill(3),factor=factor,feasible=bool(r.feasible),reason=r.rejection_reason,fixture='historical ER RETURN3; causal belief/reference only',old_duration_s=old.duration_s,old_velocity_deg_s=np.rad2deg(fx['archived']['target_dq_rad_s']),new_velocity_deg_s=np.rad2deg(velocity))
 if r.feasible:
  prepared=_prepare_single_decision(replace(fx['decision'],executed=r),planner,fx['belief']);new=prepared.executed.schedule
  composite=RollingSuffixCompositeSchedule(prefix=prior['schedule'].safe_escape.bridge,prefix_start_s=0.,suffix=new,request_id=fx['context']['request_id']);d=fx['decision_record'];tr=np.load(A/'source/results/repair_ER110_R4_120/trace.npz');idx=int(np.argmin(abs(tr['time_s']-d['activation_timestamp_s'])));cur=composite.sample(0.)
  future=dict(spec=planner.spec,estimated_state=tr['estimated_human_state_rad_rad_s'][idx],estimated_acceleration=tr['actual_human_acceleration_rad_s2'][idx],reference_acceleration=cur.ddq_rad_s2,acceleration_valid=bool(tr['actual_human_acceleration_valid'][idx]),revalidation_capture_ns=105000000,now_ns=105000000,original_capture_ns=100000000,request_plan_version=new.version,original_sample_s=d['request_measurement_timestamp_s'],revalidation_sample_s=d['activation_timestamp_s'],age_policy='simulation')
  val=validate_rolling_composite(composite=composite,belief=fx['belief'],request_sequence=fx['belief'].sequence,clearance=native.clearance_evaluator,spec=planner.spec,phase=fx['evaluate_args']['phase'],request_phase=fx['evaluate_args']['phase'],remaining_s=fx['evaluate_args']['phase_remaining_s']-.005,current_reference_state=np.r_[cur.q_rad,cur.dq_rad_s],current_reference_acceleration=cur.ddq_rad_s2,future_handoff=future,now_physics_s=d['activation_timestamp_s'])
  row.update(status='PASS' if val['feasible'] else 'REJECTED',current_admission=val,safe_escape=True,certificate=new.continuous_clearance_certificate,new_ref_vmax_deg_s=np.rad2deg(new.maximum_reference_velocity_rad_s),new_ref_amax_deg_s2=np.rad2deg(new.maximum_reference_acceleration_rad_s2),coefficient_sha256=hashlib.sha256(new.coefficients.tobytes()).hexdigest(),unchanged_target_max_rad=float(np.max(abs(new.sample(new.duration_s).q_rad-old.sample(old.duration_s).q_rad))))
 else:row['status']='REJECTED'
 rows.append(row)
put('audit/TRACK_A_PRECHECKS.json',dict(rows=rows,no_physics=True,truth_inputs=False,live_checks_mandatory=True))
oldplan=json.loads((A/'repair_PLAN.json').read_text());arms=copy.deepcopy(oldplan['arms']);arms[-1]['id']='ER'
for arm in arms:arm['approach']=[]
for r in rows:
 if r['status']=='PASS':
  c=copy.deepcopy(arms[-1]);c['id']=r['id'];c['approach']=[dict(phase='RETURN',slot=3,knee_velocity_factor=r['factor'])]
  if r['factor']==.8:c['conditional_second']=True
  arms.append(c)
condition=copy.deepcopy(oldplan['condition']);condition['name']='Adev';condition['role']='already exposed W1 development, frozen Early RETURN parent'
put('Adev_PLAN.json',dict(frozen_unix=time.time(),condition=condition,fork_after_prefix=1,reproduce_W1=True,arms=arms))
rule=dict(version='multi_track_v1',eligibility='Full original task/safety/motion/receipt plus actual intervention acceptance; gain>=1% vs own matched B and retain>=80% of ER saving; terminal overshoot must decrease vs ER',selection='Prefer AV090 if eligible. AV080 only if AV090 remains ineligible but reduces excursion without new failed axes or >10% raw amax/jerk RMS increase vs ER. No minimum-force search. At most two A candidates.',validation='Freeze first eligible identity before one deterministic repeat and unused legal W2 matched B/T/D/ER/candidate. Never retune on W2.',stop='Task, absolute safety, causal failure stops all physics. New motion failed requirement vs ER or >10% amax/jerk RMS vs ER or tracking RMS>ER+.5deg pauses further A candidates; record and switch tracks.',budget='60 total START, development <=42, reserve18; all parents/forks/failures count; serial only')
put('CANDIDATE_SELECTION_RULE.json',rule)
put('CANDIDATE_PLAN.json',dict(parent_manifest_sha256=sc.sha(A/'EXECUTION_CODE_MANIFEST.json'),parent_candidate=oldplan['arms'][-1],hypothesis='Lower RETURN3 knee pass speed reduces state entering RETURN4 deceleration and may reduce true knee undershoot; opposite effects on mid-segment speed, hip coupling, replan duration and force are falsifiers',prechecks=rows,arms=arms,frozen_unix=time.time()))
(P/'INTERVENTION_PROTOCOL.md').write_text('# Track A — 物理前协议\n\n最新Early RETURN的RETURN1×1.10、RETURN4×1.20，D的RETURN2/3[+0.3,-0.3]°，18D全部参数/plateau与T规则冻结。新干预仅RETURN3膝通过速度×0.90；有条件第二候选×0.80。该槽原选目标、髋通过速度、原选时长不变；后续活态重规划可因果响应。每次重建原fixed-duration证书、安全逃逸、40ms bridge与当前状态准入。\n\n实际膝参考停稳前已有下冲，故不预设纯惯性唯一原因。失败、未执行和局部/完整代价分别记录。\n\n'+json.dumps(rule,indent=2,ensure_ascii=False)+'\n')
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','control/round_planner.py','control/early_return_planner.py','code/terminal_repair.py']:assert sc.sha(P/n)==sc.sha(A/n),n
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
files={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','CANDIDATE_SELECTION_RULE.json','INTERVENTION_PROTOCOL.md','CANDIDATE_PLAN.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json','RUN_PLAN.json']:files[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),parent_manifest_sha256=sc.sha(A/'EXECUTION_CODE_MANIFEST.json'),source_changes='path rebasing and isolated terminal approach wrapper/harness only; B execution/plant/safety unchanged'))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS' if any(x['status']=='PASS' for x in rows) else 'BLOCKED',no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),AST=True,imports_isolated=True,original_parent_rules_byte_identical=True,live_checks_required=True))
for f in [P/'CANDIDATE_PLAN.json',P/'Adev_PLAN.json',P/'INTERVENTION_PROTOCOL.md',P/'CANDIDATE_SELECTION_RULE.json',P/'audit/TRACK_A_PRECHECKS.json']:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(sc.clean(dict(status='PASS',arms=[c['id'] for c in arms],prechecks=[{k:r[k] for k in ['id','status','reason']} for r in rows]))),flush=True)
