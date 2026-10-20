from stream_runtime_evidence import *
from equivalence_gate import compare
from itertools import zip_longest
FIELDS=('time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm')
def signature(id):
 p=STUDY/'source/results'/id/'runtime_artifacts.json.gz';cached=STUDY/'reports'/(id+'_NATIVE_SIGNATURE.json');artifact_hash=sha(p)
 if cached.exists():
  out=json.loads(cached.read_text())
  if out['artifact_sha256']==artifact_hash:return out
 h=hashlib.sha256();ch=hashlib.sha256();n=0
 for row in array_items(p,'native_states_evaluation_only'):
  vals=np.asarray([row['time_s'],*row['qpos_evaluation_only'],*row['qvel_evaluation_only'],*row['command_torque_nm']],dtype='<f8');h.update(vals.tobytes());ch.update(json.dumps(row['contact_pairs_evaluation_only'],sort_keys=True).encode());n+=1
 out=dict(id=id,artifact_sha256=artifact_hash,native_step_count=n,physical_arrays_sha256=h.hexdigest(),contact_pairs_sha256=ch.hexdigest(),fields=FIELDS,host_diagnostic_timestamps_excluded=True);save(cached,out);return out
def full_compare(a,b):
 out=compare(a,b);issues=out['issues'];sa=signature(a);sb=signature(b);exact=sa['native_step_count']==sb['native_step_count'] and sa['physical_arrays_sha256']==sb['physical_arrays_sha256'] and sa['contact_pairs_sha256']==sb['contact_pairs_sha256'];errors={k:0. for k in FIELDS}
 if not exact:
  pa=STUDY/'source/results'/a/'runtime_artifacts.json.gz';pb=STUDY/'source/results'/b/'runtime_artifacts.json.gz'
  for i,(x,y) in enumerate(zip_longest(array_items(pa,'native_states_evaluation_only'),array_items(pb,'native_states_evaluation_only'))):
   if x is None or y is None:issues.append('NATIVE_STEP_COUNT_DIFFERENCE');break
   for k in FIELDS:
    xa=np.asarray(x[k]);ya=np.asarray(y[k]);d=float(np.max(np.abs(xa-ya)));errors[k]=max(errors[k],d)
   if x['contact_pairs_evaluation_only']!=y['contact_pairs_evaluation_only']:issues.append('CONTACT_DIFFERENCE:'+str(i));break
  for k,v in errors.items():
   if v>1e-10:issues.append('NATIVE_STEP_ARRAY:'+k)
 fa=json.loads((STUDY/'source/results'/a/'summary.json').read_text());fb=json.loads((STUDY/'source/results'/b/'summary.json').read_text());keys=['phase','executed_label','executed_action_delta_q_rad','selection_mode','plan_activated','activation_outcome','activation_rejected_reason','deadline_miss','stale','belief_sequence_used','reference_boundary_continuity']
 da=[{k:x.get(k) for k in keys} for x in fa.get('decisions',[])];db=[{k:x.get(k) for k in keys} for x in fb.get('decisions',[])];decision_exact=da==db
 if not decision_exact:issues.append('ACTIVATED_NATIVE_DECISION_OR_FALLBACK_DIFFERENCE')
 if fa.get('safety_mode_counts')!=fb.get('safety_mode_counts'):issues.append('SAFETY_MODE_COUNTS')
 def transitions(x):return [{k:v for k,v in row.items() if k!='actual_completion_commit_ns'} for row in x['task'].get('phase_transitions',[])]
 if transitions(fa)!=transitions(fb):issues.append('PHASE_TRANSITIONS')
 out.update(status='PASS' if not issues else 'FAIL',full_native_step_signature_exact=exact,full_native_step_max_errors=errors,native_step_counts=[sa['native_step_count'],sb['native_step_count']],activated_decision_and_fallback_exact=decision_exact);return out
def main():
 version=sys.argv[1];ids=sys.argv[2:5];assert len(ids)==3;rows=[full_compare(a,b) for a,b in zip(['002_T0_science_B','003_T0_science_M2','004_T0_science_deviation'],ids)];out=dict(version=version,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,no_tolerance_relaxation=True,scope='every 0.25ms MuJoCo native-step qpos/qvel/actual command/contact plus full5ms trace, reference q/dq/ddq, metrics, all candidate acceptance, activated decisions/fallback and exact phase transitions')
 p=STUDY/'versions'/(version+'_FULL_NATIVE_EQUIVALENCE_GATE.json')
 if p.exists():shutil.copy2(p,STUDY/'versions'/(version+'_FULL_NATIVE_GATE_HISTORY_'+sha(p)+'.json'))
 out['excluded_phase_transition_field']='actual_completion_commit_ns is a genuine host timestamp; phase time_s and state_source_time_s remain exact'
 save(p,out);print(json.dumps(dict(version=version,status=out['status'],rows=[{k:r[k] for k in ('status','issues','full_native_step_signature_exact','native_step_counts')} for r in rows])))
if __name__=='__main__':main()
