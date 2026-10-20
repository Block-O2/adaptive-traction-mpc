"""Positive and negative safety-contract tests; no stepping or physical START."""
from fixture import *
from dataclasses import replace,FrozenInstanceError
import pickle,hashlib,time,traceback,math
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import *
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation,validate_rolling_composite
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import FallbackLatch
from traction_mpc_stage5.human_waypoint_scheduler import _quintic_coefficients
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
f=fixture();rows=[];failures=[]
protocol=dict(unix=time.time(),q_dq_ddq_equivalence_tolerance=[1e-10,1e-10,1e-9],C2_tolerance=1e-10,limits='unchanged original reference fractions, original continuous body envelope, original mechanics screen plus per-piece checks',perturbation_deg=[0,.05],physical_starts=0)
if not (P/'tests/TEST_PROTOCOL.json').exists():(P/'tests/TEST_PROTOCOL.json').write_text(json.dumps(protocol,indent=2))
def test(name,fn,scope='UNIT_CONTRACT'):
 try:detail=fn();rows.append(dict(name=name,status='PASS',scope=scope,detail=primitive(detail)))
 except BaseException as e:
  detail=dict(name=name,error=repr(e),traceback=traceback.format_exc());failures.append(detail);rows.append(dict(name=name,status='FAIL',scope=scope,detail=detail));print('FAIL',name,repr(e),flush=True)

def adapt(amplitude):return adapt_decision(f['decision'],f['planner'],f['belief'],{**f['context'],'perturbation_deg':[0.,amplitude]}).executed.schedule
zero=adapt(0.);nonzero=adapt(.05)
def reseal(s,**kw):
 s=replace(s,**kw,path_certificate_json='{}',sealed_certificate_id='');object.__setattr__(s,'sealed_digest',digest(s.content()));return s

def cert(s,**kw):
 binding=json.loads(s.binding_json)
 return certify_path(s,f['belief'],kw.get('clearance',f['clearance']),spec=f['spec'],q_bounds=binding['task_q_bounds'],velocity_limits=binding['velocity_limits'],acceleration_limits=binding['acceleration_limits'])
def rejected_path(s,reason):
 r=cert(s);assert not r['feasible'] and reason in r['reasons'],r['reasons'];return dict(reasons=r['reasons'],jumps=r['joint_boundary_jumps'])
def changed_coefficient(s,piece,power,amount):
 ps=list(s.segments);c=ps[piece].coefficients;c[0,power]+=amount;ps[piece]=replace(ps[piece],values=tup(c));return reseal(s,segments=tuple(ps),canonical_zero=False)
def changed_node(s,*,qdelta=(0,0),vdelta=(0,0),adelta=(0,0)):
 knots=s.knots_s;original=s.original;states=[[original.sample(t).q_rad,original.sample(t).dq_rad_s,original.sample(t).ddq_rad_s2] for t in knots]
 states[2][0]+=np.asarray(qdelta);states[2][1]+=np.asarray(vdelta);states[2][2]+=np.asarray(adelta);ps=list(s.segments)
 for j in [1,2]:ps[j]=replace(ps[j],values=tup(hermite(*states[j],*states[j+1],knots[j+1]-knots[j])))
 return reseal(s,segments=tuple(ps),canonical_zero=False)
def current(s=nonzero,*,belief=None,phase=TaskPhase.OUTBOUND,request_phase=TaskPhase.OUTBOUND,remaining=8.,age=.005,future_changes=None):
 first=s.sample(0.);b=json.loads(s.binding_json);source=b['source_sample_time_s'];now=source+age
 future=dict(spec=f['spec'],estimated_state=np.r_[first.q_rad,first.dq_rad_s],observed_reference_state=np.r_[first.q_rad,first.dq_rad_s],estimated_acceleration=np.zeros(2),reference_acceleration=first.ddq_rad_s2,acceleration_valid=True,now_ns=b['sensor_capture_ns']+int(age*1e9),original_capture_ns=b['sensor_capture_ns'],revalidation_capture_ns=b['sensor_capture_ns']+int(age*1e9),original_sample_s=source,revalidation_sample_s=now,age_policy='simulation',request_plan_version=s.version)
 if future_changes:future.update(future_changes)
 return validate_activation(belief=belief or f['belief'],request_sequence=f['belief'].sequence,schedule=s,clearance=f['clearance'],phase=phase,request_phase=request_phase,remaining_s=remaining,reference_state=np.r_[first.q_rad,first.dq_rad_s],now_physics_s=now,future_handoff=future)
def current_reject(**kw):
 r=current(**kw);assert not r['feasible'],r;return r

def old_single():
 p=f['decision'].executed.schedule;first=p.sample(0.);r=validate_activation(belief=f['belief'],request_sequence=f['belief'].sequence,schedule=p,clearance=f['clearance'],phase=TaskPhase.OUTBOUND,request_phase=TaskPhase.OUTBOUND,remaining_s=8,reference_state=np.r_[first.q_rad,first.dq_rad_s]);assert r['feasible'];return dict(feasible=True,shape=list(p.coefficients.shape))
test('M0_original_single_legal',old_single)
def old_reject():
 p=f['decision'].executed.schedule
 try:replace(p,coefficients=np.stack([s.coefficients for s in zero.segments]))
 except ValueError as e:assert '2x6' in str(e);return str(e)
 raise AssertionError('old schema accepted multi')
test('old_schema_still_rejects_4x2x6',old_reject)
math_rows=[]
def equivalence():
 for directory in ['historical_B','historical_18D']:
  summary=json.loads((P/'key_traces'/directory/'summary.json').read_text())
  for i,row in enumerate(summary['learning_records']):
   d=row['selected_plan']['schedule'];T=d['duration_s'];candidate=HumanWaypointCandidate(label='equivalence',phase=TaskPhase(d['phase']),phase_goal_rad=np.radians([120,120]) if d['phase']!='RETURN' else np.radians([5,10]),q_waypoint_rad=np.asarray(d['target_q_rad']),dq_waypoint_rad_s=np.asarray(d['target_dq_rad_s']))
   names=['maximum_reference_velocity_rad_s','maximum_reference_acceleration_rad_s2','maximum_causal_20ms_reference_acceleration_rad_s2','maximum_nominal_tracking_acceleration_rad_s2','nominal_completion_time_s','minimum_reference_shank_clearance_m']
   original=QuinticHumanWaypointSchedule(candidate=candidate,start_q_rad=np.asarray(d['start_q_rad']),start_dq_rad_s=np.asarray(d['start_dq_rad_s']),duration_s=T,coefficients=_quintic_coefficients(np.asarray(d['start_q_rad']),np.asarray(d['start_dq_rad_s']),np.asarray(d['target_q_rad']),np.asarray(d['target_dq_rad_s']),T),**{k:d[k] for k in names})
   multi=build_reference(original,binding={});errors=np.zeros(3)
   for piece,lo,hi in zip(multi.segments,multi.knots_s,multi.knots_s[1:]):
    for t in np.linspace(lo,hi,101):
     a=piece.sample(float(max(0.,t-lo)));b=original.sample(float(t));errors=np.maximum(errors,[np.max(abs(getattr(a,k)-getattr(b,k))) for k in ['q_rad','dq_rad_s','ddq_rad_s2']])
   assert np.all(errors<np.array([1e-10,1e-10,1e-9]));math_rows.append(dict(source=directory,index=i,errors=errors.tolist()))
 return dict(schedules=len(math_rows),max_errors=np.max([r['errors'] for r in math_rows],axis=0))
test('M1_piecewise_restriction_28_frozen_schedules',equivalence,'MATH_VERIFIED')
def local_math():
 ts=np.linspace(0,zero.duration_s,2001);diff=[]
 for t in ts:
  a=zero.sample(float(t));b=nonzero.sample(float(t));diff.append(b.q_rad-a.q_rad)
 diff=np.array(diff);outside=(ts<zero.knots_s[1]-1e-10)|(ts>zero.knots_s[3]+1e-10)
 assert np.max(abs(diff))>.0005 and np.max(abs(diff[outside]))<1e-10
 jumps=[]
 for p,q in zip(nonzero.segments,nonzero.segments[1:]):
  a,b=p.sample(p.duration_s),q.sample(0.);jumps.append([np.max(abs(getattr(a,k)-getattr(b,k))) for k in ['q_rad','dq_rad_s','ddq_rad_s2']])
 assert np.max(jumps)<1e-10
 assert nonzero.certificate['feasible']
 return dict(max_q_change_rad=np.max(abs(diff)),support_s=[zero.knots_s[1],zero.knots_s[3]],outside_max_rad=np.max(abs(diff[outside])),C2_max=np.max(jumps,axis=0),endpoints_preserved=True)
test('M2_M5_nonzero_local_time_and_boundary',local_math,'MATH_VERIFIED')
def pickle_immutable():
 s=pickle.loads(pickle.dumps(nonzero,protocol=5));s.assert_integrity();before=s.sample(s.duration_s/2).q_rad.copy();a=s.segments[1].coefficients;a[:]=999;b=s.certificate;b['feasible']=False;cc=s.candidate.q_waypoint_rad;cc[:]=999
 assert np.array_equal(before,s.sample(s.duration_s/2).q_rad)
 try:s.knots_s=(0,1)
 except FrozenInstanceError:pass
 else:raise AssertionError('mutable')
 return dict(roundtrip_id=s.sealed_digest,detached_array_and_certificate_mutations_no_effect=True)
test('M3_immutable_after_pickle_and_detached_arrays',pickle_immutable)
def tamper_payload():
 s=replace(nonzero,segments=changed_coefficient(nonzero,1,0,.001).segments)
 return current_reject(s=s)
test('M3_edited_coefficients_old_identity_rejected',tamper_payload)
test('M3_edited_certificate_rejected',lambda:current_reject(s=replace(nonzero,path_certificate_json='{"feasible":true}')))
def forged_alias():
 s=reseal(nonzero,canonical_zero=True)
 try:cert(s)
 except ValueError as e:assert str(e)=='CANONICAL_ALIAS_NOT_EQUIVALENT';return str(e)
 raise AssertionError('forged alias accepted')
test('M3_nonzero_cannot_use_zero_alias',forged_alias)
for label,power in [('q',0),('dq',1),('ddq',2)]:test('M4_internal_'+label+'_discontinuity',lambda power=power:rejected_path(changed_coefficient(nonzero,1,power,.001),'INTERNAL_C2'))
test('M4_intermediate_ROM_violation',lambda:rejected_path(changed_node(nonzero,qdelta=(0.,3.)),'REFERENCE_ROM'))
test('M4_intermediate_velocity_violation',lambda:rejected_path(changed_node(nonzero,vdelta=(0.,5.)),'REFERENCE_VELOCITY'))
test('M4_intermediate_acceleration_violation',lambda:rejected_path(changed_node(nonzero,adelta=(0.,100.)),'REFERENCE_ACCELERATION'))
test('M4_intermediate_continuous_clearance_violation',lambda:rejected_path(changed_node(nonzero,qdelta=(-.4,1.4)),'CONTINUOUS_CLEARANCE_OR_ROM'))
def bad_tracking():
 b=json.loads(nonzero.binding_json);b['tracking_offset_rad']=[-.5,.5];return rejected_path(reseal(nonzero,binding_json=encode(b)),'TRACKING_OFFSET_PATH')
test('tracking_offset_full_piece_path_rejected',bad_tracking)
test('current_valid_multisegment',lambda:dict(result=current()['feasible']) if current()['feasible'] else (_ for _ in ()).throw(AssertionError('valid current rejected')))
test('expired_original_source_rejected',lambda:current_reject(age=.101))
test('model_sequence_regression_rejected',lambda:current_reject(belief=replace(f['belief'],sequence=f['belief'].sequence-1)))
test('same_version_modified_model_content_rejected',lambda:current_reject(belief=replace(f['belief'],beta=f['belief'].beta+np.r_[.001,np.zeros(10)])))
test('reference_version_mismatch_rejected',lambda:current_reject(future_changes={'request_plan_version':'wrong_version'}))
test('source_retry_cannot_refresh_capture',lambda:current_reject(future_changes={'original_capture_ns':999999999}))
test('phase_change_rejected',lambda:current_reject(phase=TaskPhase.HOLD))
test('insufficient_future_stop_time_rejected',lambda:current_reject(remaining=nonzero.duration_s+.001))
test('missing_future_stop_bundle_rejected',lambda:rejected_path(reseal(nonzero,safe_escape=None),'MISSING_FUTURE_ESCAPE'))
def invalid_stop():
 e=nonzero.safe_escape;c=e.stop.coefficients;c[1,0]+=2.;stop=replace(e.stop,values=tup(c));return rejected_path(reseal(nonzero,safe_escape=replace(e,stop=stop)),'FUTURE_ESCAPE_INVALID')
test('future_stop_path_or_boundary_infeasible_rejected',invalid_stop)
def late_latch():
 latch=FallbackLatch(nonzero.safe_escape);assert not latch.choose_primary(validated=True,age_ns=100_000_000);assert latch.commit();assert not latch.choose_primary(validated=True,age_ns=1);latch.stopped();assert not latch.resume(fresh=False,validated=True,age_ns=1)
 return dict(expired_and_late_after_brake_rejected=True,original_latch_unmodified=True)
test('late_plan_cannot_replace_committed_fallback',late_latch,'ORIGINAL_UNIT_MECHANISM_NOT_HOST_STRESS')
def worker_payload():
 f['planner'].multisegment_intent={**f['context'],'perturbation_deg':[0.,.05]};adaptive=AdaptiveHumanWaypointHWMPCV22(f['planner']);payload=op.snapshot_task_call(adaptive,f['args']);d=op.execute_task_snapshot(payload);assert isinstance(d.executed.schedule,MultiSegmentReference);d.executed.schedule.assert_integrity()
 import task_decode_once
 task_decode_once.install();decoded=pickle.loads(payload);dd=task_decode_once.EXECUTE(decoded);assert dd.executed.schedule.sealed_digest==d.executed.schedule.sealed_digest
 proof=task_decode_once.PREPARE(decoded,dd);assert len(proof['proofs'])==3 and proof['model_sequence']==f['belief'].sequence
 return dict(normal_worker_and_decode_once_route=True,mechanics_prepare_proofs=len(proof['proofs']),reference_id=d.executed.schedule.sealed_digest)
test('M6_original_worker_and_decode_once_routes',worker_payload,'INTERFACE_CERTIFIED_UNIT_SCOPE')
# Explicitly preserve the cross-knot 20ms grid as ONE history, not per-piece reset.
def window_formula():
 dt=nonzero.reference_period_s;times=np.minimum(np.arange(int(math.ceil(nonzero.duration_s/dt-1e-12))+1)*dt,nonzero.duration_s);v=np.array([nonzero.sample(float(t)).dq_rad_s for t in times]);ext=np.vstack([np.repeat(v[:1],4,axis=0),v]);expected=np.max(abs((ext[4:]-ext[:-4])/.02),axis=0);assert np.array_equal(expected,nonzero.causal_acceleration());return dict(max_acceleration=expected,whole_reference_history=True)
test('cross_boundary_20ms_history_not_reset',window_formula)
def serialized_piece_times_and_identity():
 for obj in [zero,nonzero]:
  r=primitive(obj.record());assert digest(r['identity_payload'])==r['reference_id']
  assert digest([r['reference_id'],encode(r['path_certificate'])])==r['certificate_id']
  assert abs(sum(x['duration_s'] for x in r['segments'])-r['duration_s'])<1e-12
  for i,row in enumerate(r['segments']):
   assert abs(row['duration_s']-(r['knots_s'][i+1]-r['knots_s'][i]))<1e-12
   p=obj.segments[i]
   assert np.array_equal(row['start_q_rad'],p.sample(0.).q_rad)
   assert np.array_equal(row['target_ddq_rad_s2'],p.sample(p.duration_s).ddq_rad_s2)
 return dict(local_durations_accurate=True,complete_identity_reconstructed=True)
test('serialization_actual_piece_times_boundaries_and_complete_identity',serialized_piece_times_and_identity)
output=dict(status='PASS' if not failures else 'FAIL',unix=time.time(),tests=rows,pass_count=sum(r['status']=='PASS' for r in rows),test_count=len(rows),failures=failures,physical_starts=0,not_certified=['host-clock deadline stress','hardware or clinical safety','continuous future wrench or tracking invariant','all arbitrary trajectory families'],fixture_provenance='archived causal commissioned belief/reference fixture; not a new physical condition; evaluation truth never supplied to planner')
(P/'CERTIFICATION_TEST_RESULTS.json').write_text(json.dumps(primitive(output),indent=2,allow_nan=False));(P/'MATH_VALIDATION.json').write_text(json.dumps(primitive(dict(status=output['status'],M0_M6=[r for r in rows if r['name'].startswith('M')],equivalence_28=math_rows,protocol=protocol,physical_starts=0)),indent=2,allow_nan=False))
if failures:
 (P/'audit'/('TEST_FAILURE_'+str(int(time.time()))+'.json')).write_text(json.dumps(primitive(output),indent=2,allow_nan=False))
 print('CERTIFICATION_FAIL',len(failures),flush=True);raise SystemExit(1)
print('CERTIFICATION_PASS',len(rows),flush=True)
