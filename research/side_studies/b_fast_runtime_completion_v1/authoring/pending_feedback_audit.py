"""Stream physical owners and real source/command changes during pending plans."""
from pathlib import Path
import sys,json,collections,bisect,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
ident=sys.argv[1];m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());artifact=S/'source/results'/ident/'runtime_artifacts.json.gz'
receipts=list(array_items(artifact,'command_receipts'));byid={r['receipt_index']:r for r in receipts};requests=sorted(m['native_requests'],key=lambda r:r['request_ns']);starts=[r['request_ns'] for r in requests];ends=[r.get('disposition_ns',r.get('activation_ns',r.get('compute_finish_ns',r['request_ns']))) for r in requests]
owners=[collections.Counter() for r in requests]
for state in array_items(artifact,'native_states_evaluation_only'):
 ns=state['native_grid_start_ns'];i=bisect.bisect_right(starts,ns)-1
 if i>=0 and ns<ends[i]:owners[i][state['command_id']]+=1
rows=[]
for i,r in enumerate(requests):
 actual=[byid[k] for k in owners[i]];fresh=[x for x in actual if x.get('apply_ns') is not None and starts[i]<=x['apply_ns']<ends[i]]
 capture_services=[x for x in m['rows']['fast'] if starts[i]<=x['service_start_ns']<ends[i]]
 torques={np.asarray(x['command_torque_nm'],dtype=np.float64).tobytes() for x in actual};refs={np.asarray(x.get('q_ref_rad',x.get('validation_reference_q_rad',[])),dtype=np.float64).tobytes() for x in actual}
 rows.append(dict(request_id=r['request_id'],stage=r['stage'],outcome=r.get('outcome'),pending_wall_ms=(ends[i]-starts[i])/1e6,physical_native_steps=sum(owners[i].values()),physical_receipt_owners=dict(owners[i]),real_service_opportunities=len(capture_services),new_applied_feedback_receipts=len(fresh),distinct_source_captures=len({x['source_capture_ns'] for x in fresh}),distinct_actual_torques=len(torques),distinct_committed_human_references=len(refs),source_samples_s=[x['source_sample_time_s'] for x in fresh],supervisor_modes=sorted({x.get('mode',x.get('supervisor_mode','UNKNOWN')) for x in actual}),reference_during_wait='original committed/prefetch reference; stationary HOLD references legitimately need not change'))
track=[x for x in receipts if x.get('apply_ns') is not None and x.get('mode')=='TRACK'];missing_track=[x['receipt_index'] for x in track if any(x.get(k) is None for k in ('actual_robot_reference_rotation','actual_robot_reference_translation','actual_robot_reference_twist'))]
offline=[x for x in receipts if x.get('apply_ns') is None and x.get('applied')];missing_offline=[x['receipt_index'] for x in offline if any(x.get(k) is None for k in ('offline_actual_write_ns','offline_support_model_sha256','offline_support_command_sha256'))]
phases=collections.Counter(x['phase'] for x in m['rows']['fast']);version_changes=sum(a.get('model_version')!=b.get('model_version') for a,b in zip(m['rows']['fast'],m['rows']['fast'][1:]))
out=dict(id=ident,status='PASS' if not missing_track and not missing_offline else 'FAIL',rows=rows,missing_actual_TRACK_reference=missing_track,missing_offline_actual_write_authority=missing_offline,actual_TRACK_receipts=len(track),offline_support_receipts=len(offline),service_counts_by_phase=dict(phases),service_model_version_changes=version_changes,interpretation='Observed physical command owners and fresh source captures, not callback-only continuity. Short requests may complete before another service. Stationary reference is distinct from constant torque; source and torque changes are reported separately.',no_threshold_retuning=True)
(S/'reports'/(ident+'_PENDING_FEEDBACK.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(id=ident,status=out['status'],service_counts_by_phase=dict(phases),service_model_version_changes=version_changes,rows=rows)))
