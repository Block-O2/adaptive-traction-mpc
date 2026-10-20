from pathlib import Path
import os,sys,json,time,ast,shutil,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
REVIEW=Path(__file__).resolve().parents[1];A=P.parent/'m2_18d_w1_d_qualification_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True
for n in ['early_return_planner.py','register.py']:shutil.copy2(REVIEW/'control'/n,P/'control'/n)
for n in ['diagnose.py']:shutil.copy2(REVIEW/'analysis'/n,P/'analysis'/n)
# Assemble the inherited matched harness using exact, reviewable textual changes.
s=(A/'control/campaign.py').read_text().replace('from round_planner import RoundPlanner','from round_planner import RoundPlanner\nfrom early_return_planner import EarlyReturnPlanner')
s=s.replace("'START_CAP_20'","'START_CAP_24'")
s=s.replace("assert n<PLAN['physics_budget'],'START_CAP_24'","assert n<PLAN['physics_budget'],'START_CAP_24'\n assert MODE!='development' or n<PLAN['development_cap'],'VALIDATION_RESERVE'")
s=s.replace("planner.round_posture=None","planner.round_posture=None;planner.early_return_intent=None")
s=s.replace("elif self.current['base']=='T':planner.__class__=RoundPlanner","elif self.current['base']=='T':planner.__class__=EarlyReturnPlanner if self.current.get('early') else RoundPlanner")
s=s.replace("if self.child is not None:\n   for change", "if self.child is not None:\n   for change in self.current.get('early',[]):\n    if phase==change['phase'] and slot==change['slot']:planner.early_return_intent=change\n   for change",1)
s=s.replace("row['posture_execution']=postures;row['intervention_executed']=len(postures)==len(c.get('posture',[])) and all(x['status']=='ACCEPTED' for x in postures)","early=[lr['selected_plan']['execution_screen']['early_return_duration'] for lr in su['learning_records'] if 'early_return_duration' in lr['selected_plan']['execution_screen']]\n    row['posture_execution']=postures;row['early_execution']=early;row['intervention_executed']=len(postures)==len(c.get('posture',[])) and all(x['status']=='ACCEPTED' for x in postures) and len(early)==len(c.get('early',[])) and all(x['status']=='ACCEPTED' for x in early)")
start=s.index("    if GROUP=='W1' and c['id'] in ['B','T']:")
end=s.index("    if c.get('zero'):",start)
s=s[:start]+"    if CONFIG.get('reproduce_W1') and c['id'] in ['B','T','D']:\n     gate=bc.compare_raw(P/'source/results'/ident,P.parent/'m2_18d_w1_d_qualification_v1/source/results'/('W1_'+c['id']));put('audit/'+ident+'_HISTORICAL_GATE.json',gate);assert gate['status']=='PASS','W1_REPRODUCTION_FAIL'\n"+s[end:]
s=s.replace("   put(GROUP+'_PAIR_GATE.json'", "    if c.get('early'):\n     dm=json.loads((P/'reports'/(GROUP+'_D_MEASURED.json')).read_text());df=dm['motion']['raw']['full'];mf=m['motion']['raw']['full'];new_failures=sorted(set(comp['failed_requirements'])-set(next(x for x in self.results if x['candidate']['id']=='D')['motion']['failed_requirements']))\n     peak_worse=any(np.any(np.asarray(mf[key][stat])>1.10*np.asarray(df[key][stat])+1e-8) for key,stat in [('acceleration_deg_s2','max_abs'),('jerk_deg_s3','rms')])\n     tracking_worse=bool(np.any(np.asarray(m['tracking_RMS_deg'])>np.asarray(dm['tracking_RMS_deg'])+.5))\n     if new_failures or peak_worse or tracking_worse:\n      put(GROUP+'_MECHANISM_REVIEW_REQUIRED.json',dict(id=ident,new_failures=new_failures,peak_worse=bool(peak_worse),tracking_worse=tracking_worse,next_candidates_not_started=True));break\n   put(GROUP+'_PAIR_GATE.json'")
s=s.replace("if MODE=='validation':assert json.loads((P/'FROZEN_SELECTION.json').read_text())['primary'] is not None","if MODE=='validation':assert json.loads((P/'REPAIR_FROZEN_SELECTION.json').read_text())['primary'] is not None")
(P/'control/campaign.py').write_text(s)
sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import study_common as sc,matched_harness as mh,analyze_matched as am
from early_return_planner import EarlyReturnPlanner
from round_planner import RoundPlanner,FixedDuration
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import _prepare_single_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation,validate_rolling_composite
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from dataclasses import replace
def put(n,x):mh.put(P/n,sc.clean(x))
# Read-only offline fixture: deployable belief/reference only; never native state replay.
src=(A.parent/'m2_18d_t_second_round_coordination_v1/control/register.py').read_text();tree=ast.parse(src)
fixture_src=ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='fixture')).replace('source/results/V1_T','source/results/W1_D')
exec(fixture_src)
fx=fixture(9);prior=fixture(8);base=fx['decision'];planner=fx['planner'];old=fx['schedule'];sch=fx['archived'];args=fx['evaluate_args'];rows=[]
for factor in [1.10,1.20]:
 duration=float(np.ceil(old.duration_s*factor/.005-1e-10)*.005);native=planner.scheduler;planner.scheduler=FixedDuration(native,duration);planner.round_forced_velocity=np.array(sch['target_dq_rad_s'])
 try:r=planner._evaluate(**args)
 finally:planner.scheduler=native;planner.round_forced_velocity=None
 row=dict(id='ER'+str(round(factor*100)),duration_factor=factor,slot=1,original_duration_s=old.duration_s,proposed_duration_s=duration,feasible=bool(r.feasible),reason=r.rejection_reason)
 if r.feasible:
  prepared=_prepare_single_decision(replace(base,executed=r),planner,fx['belief']);new=prepared.executed.schedule
  bridge=prior['schedule'].safe_escape.bridge
  composite=RollingSuffixCompositeSchedule(prefix=bridge,prefix_start_s=0.,suffix=new,request_id=fx['context']['request_id'])
  d=fx['decision_record'];tr=np.load(A/'source/results/W1_D/trace.npz');idx=int(np.argmin(abs(tr['time_s']-d['activation_timestamp_s'])));observed=tr['estimated_human_state_rad_rad_s'][idx];acc=tr['actual_human_acceleration_rad_s2'][idx];cur=composite.sample(0.)
  future=dict(spec=planner.spec,estimated_state=observed,estimated_acceleration=acc,reference_acceleration=cur.ddq_rad_s2,acceleration_valid=bool(tr['actual_human_acceleration_valid'][idx]),revalidation_capture_ns=105000000,now_ns=105000000,original_capture_ns=100000000,request_plan_version=new.version,original_sample_s=d['request_measurement_timestamp_s'],revalidation_sample_s=d['activation_timestamp_s'],age_policy='simulation')
  val=validate_rolling_composite(composite=composite,belief=fx['belief'],request_sequence=fx['belief'].sequence,clearance=native.clearance_evaluator,spec=planner.spec,phase=args['phase'],request_phase=args['phase'],remaining_s=args['phase_remaining_s']-.005,current_reference_state=np.r_[cur.q_rad,cur.dq_rad_s],current_reference_acceleration=cur.ddq_rad_s2,future_handoff=future,now_physics_s=d['activation_timestamp_s'])
  row.update(activation_precheck=val,prepared_safe_escape=True,C2=True,unchanged_target_max_error=float(np.max(abs(new.sample(duration).q_rad-old.sample(old.duration_s).q_rad))),unchanged_pass_velocity_max_error=float(np.max(abs(new.sample(duration).dq_rad_s-old.sample(old.duration_s).dq_rad_s))),reference_vmax_deg_s=np.rad2deg(new.maximum_reference_velocity_rad_s).tolist(),reference_amax_deg_s2=np.rad2deg(new.maximum_reference_acceleration_rad_s2).tolist(),reference_coefficient_sha256=hashlib.sha256(new.coefficients.tobytes()).hexdigest(),certificate=new.continuous_clearance_certificate)
  row['status']='PASS' if val['feasible'] else 'REJECTED'
 else:row['status']='REJECTED'
 rows.append(row)
put('audit/OFFLINE_PRECHECKS.json',dict(status='PASS' if any(x['status']=='PASS' for x in rows) else 'BLOCKED',fixtures='archived W1 D RETURN0/1, deployable belief + actual reference, offline only; live admission remains mandatory',rows=rows))
posture=[dict(phase='RETURN',slot=i,delta_deg=[.3,-.3]) for i in [2,3]]
arms=[dict(id=i,base='B' if i=='B' else 'T',posture=posture if i=='D' else [],early=[],changes=[]) for i in ['B','T','D']]
for r in rows:
 if r['status']=='PASS':arms.append(dict(id=r['id'],base='T',posture=posture,early=[dict(phase='RETURN',slot=1,duration_factor=r['duration_factor'])],changes=[]))
condition=json.loads((A/'W1_PLAN.json').read_text())['condition']
put('dev_PLAN.json',dict(frozen_unix=time.time(),condition=condition,fork_after_prefix=1,reproduce_W1=True,arms=arms))
selection=dict(full_gates='Every original task, safety, complete motion/fairness vs matched B, actual intervention acceptance, causal/native ownership',meaningful_gain_percent=1.,major_gain_retention_fraction=.8,eligibility='all original gates; J_F gain>=1% vs same matched B; retain>=80% of matched frozen D saving',selection='Among eligible prefer smaller duration factor; no minimum-force search. Freeze before any validation.',bounded_repair='At most one subsequent development revision, prospectively registered after mechanism analysis; no validation-based reselection.',stop='Original task/safety/causal fail stops all physics. New failed metric vs D, >10% raw acceleration max or jerk RMS vs D, or tracking RMS>D+0.5deg pauses remaining candidates for mechanism review.',validation='Reserve11 START; selected same-W1 cold parent B/T/D/primary/repeat (6); one never-used legal prefix B/T/D/primary (5). If no eligible primary, no validation. All serial.')
put('REPAIR_SELECTION_RULE.json',selection)
put('CANDIDATE_PLAN.json',dict(frozen_unix=time.time(),hypothesis='RETURN1 duration only can remove early high-velocity samples; fixed endpoint velocities mean improvement is not guaranteed and later causal choices may change',candidates=rows,arms=arms,old_D_identity_unchanged=True))
(P/'INTERVENTION_PROTOCOL.md').write_text('# Early RETURN Repair v1 — 物理前冻结协议\n\nRETURN1选后suffix duration倍率1.10/1.20，原规则向上5ms对齐；同活态原目标与通过速度保持。18D参数、RETURN plateau、T1.5选后规则、D RETURN2/3 [+0.3,-0.3]°冻结。每条新quintic重做原certificate、mechanics、escape、40ms桥接与current admission；没有复用旧曲线证书或改变正式接口。\n\n'+json.dumps(selection,indent=2,ensure_ascii=False)+'\n\n开发条件W1，真实完整commissioning及合法OUTBOUND0父状态后serial live fork。B/T/D须逐字段复现旧W1；全部候选完整19.030s任务及各phase合同不变。先原始dense统计，再SG5/21敏感性；完整matched-B相对门不改变。单因子虽保留D规则，后续实际选定duration/目标可因果响应，须记录。所有失败/partial保留。\n\n最多24 START（父/子/失败/重复/验证均计），开发最多13保留11验证。T0 2026-10-18 14:36:39+08，18:36:39硬截止，17:51:39后无新START，另保留900s完成在途运行。禁止Human真实状态赋值/回放、RL、gain/plant/ROM/阈值修改、Git提交或分支操作。具体参数和预检见CANDIDATE_PLAN.json、audit/OFFLINE_PRECHECKS.json。\n')
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','control/round_planner.py','code/terminal_repair.py']:assert sc.sha(P/n)==sc.sha(A/n),n
for folder in ['source','code','deps','control']:
 for f in (P/folder).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
files={str(f.relative_to(P)):sc.sha(f) for folder in ['source','code','deps','weights','control'] for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','REPAIR_SELECTION_RULE.json','INTERVENTION_PROTOCOL.md','CANDIDATE_PLAN.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:files[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),base_manifest_sha256=sc.sha(A/'EXECUTION_CODE_MANIFEST.json'),source_changes='path-only rebasing; isolated early_return_planner and inherited matched harness extension; no production safety semantic changes'))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS' if len(arms)>3 else 'BLOCKED',unix=time.time(),no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),imports_isolated=True,original_T_D_parameters_motion_byte_identical=True,AST=True,offline_prechecks='audit/OFFLINE_PRECHECKS.json',live_certificate_and_current_admission_required=True))
print(json.dumps(dict(status='PASS',arms=[x['id'] for x in arms],prechecks=[dict(id=x['id'],status=x['status']) for x in rows])),flush=True)
